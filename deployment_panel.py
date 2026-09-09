"""AI 创意工作台独立部署控制面板。"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import threading
import webbrowser
from enum import Enum
from pathlib import Path
from tkinter import messagebox, filedialog, ttk
import tkinter as tk
from typing import Any, Callable

from deployment_control.firewall_manager import FirewallManager
from deployment_control.health_checker import HealthChecker
from deployment_control.operation_log import OperationLogger
from deployment_control.port_inspector import PortInspector
from deployment_control.release_manager import ReleaseManager
from deployment_control.service_manager import ServiceManager


PUBLIC_URL = "http://42.194.220.18:8775/"
LOCAL_URL = "http://127.0.0.1:8775/"
MANAGED_PORTS = (7896, 8775, 8780)


class _SystemProcessRunner:
    """Minimal Windows adapter kept behind ServiceManager's injectable seam."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def enumerate_processes(self) -> list[Any]:
        from deployment_control.service_manager import ProcessRecord

        query = "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return []
        try:
            payload = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            payload = [payload]
        records: list[ProcessRecord] = []
        for item in payload:
            if not isinstance(item, dict) or not str(item.get("ProcessId", "")).isdigit():
                continue
            command = str(item.get("CommandLine") or "")
            normalized = command.replace("\\", "/").lower()
            root = str(self.project_root).replace("\\", "/").lower()
            if "chat2api/main.py" in normalized or "chat2api\\main.py" in command.lower():
                cwd = str(self.project_root / "chat2api")
            elif "proxy-bridge.yaml" in normalized:
                cwd = str(self.project_root / ".runtime")
            elif root in normalized or "launcher.py" in normalized or "creative_studio.app" in normalized:
                cwd = str(self.project_root)
            else:
                cwd = ""
            records.append(ProcessRecord(int(item["ProcessId"]), str(item.get("ExecutablePath") or ""), command, cwd))
        return records

    def launch(self, command: Any, cwd: Path, env: dict[str, str]) -> Any:
        return subprocess.Popen(
            list(command),
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def launch_batch(self, path: Path, cwd: Path) -> Any:
        return subprocess.Popen(["cmd.exe", "/c", str(path)], cwd=cwd)

    def terminate(self, pid: int) -> None:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)

    def send_launcher_close(self, pid: int) -> None:
        # WM_CLOSE is intentionally delegated to the launcher when available.
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True, check=False)

    def wait_for_exit(self, pid: int, timeout: float) -> bool:
        deadline = __import__("time").monotonic() + timeout
        while __import__("time").monotonic() < deadline:
            if not any(item.pid == pid for item in self.enumerate_processes()):
                return True
            __import__("time").sleep(0.1)
        return False


class _SystemFirewallRunner:
    def inspect_rule(self, name: str) -> list[Any]:
        from deployment_control.firewall_manager import FirewallRule

        command = f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue | Get-NetFirewallPortFilter"
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not completed.stdout.strip():
            return []
        return [FirewallRule(name, 8775, "TCP", "Inbound", "Allow", True)]

    def _run(self, command: str) -> None:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False)

    def create_rule(self, name: str, local_port: int, protocol: str, direction: str, action: str) -> None:
        self._run(f"New-NetFirewallRule -DisplayName '{name}' -Direction {direction} -Protocol {protocol} -LocalPort {local_port} -Action {action} -Profile Any")

    def enable_rule(self, name: str) -> None:
        self._run(f"Enable-NetFirewallRule -DisplayName '{name}'")

    def disable_rule(self, name: str) -> None:
        self._run(f"Disable-NetFirewallRule -DisplayName '{name}'")

    def remove_rule(self, name: str) -> None:
        self._run(f"Remove-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue")


class _ServicePortAdapter:
    """Translate read-only inspection records to ServiceManager bindings."""

    def __init__(self, inspector: PortInspector) -> None:
        self.inspector = inspector

    def inspect(self, port: int) -> list[Any]:
        from deployment_control.service_manager import PortBinding

        bindings: list[PortBinding] = []
        for inspection in self.inspector.inspect(port):
            listener = inspection.listener
            bindings.append(PortBinding(listener.port, listener.address, listener.pid))
        return bindings


class PanelState(str, Enum):
    ALL_CLOSED = "全部关闭"
    LAUNCHER_OPEN = "启动器已打开"
    STARTING = "本地服务启动中"
    LOCAL_READY = "本地服务就绪"
    SWITCHING_PUBLIC = "公网切换中"
    PUBLIC_RUNNING = "公网运行中"
    STOPPING = "下线中"
    ANOMALY = "存在异常"


def determine_panel_state(
    *,
    launcher_open: bool,
    web_running: bool,
    web_public: bool,
    gateway_running: bool,
    bridge_running: bool,
    has_unknown_conflict: bool,
) -> PanelState:
    """根据观测到的端口和进程事实计算顶层状态。"""
    if has_unknown_conflict:
        return PanelState.ANOMALY
    if web_public and web_running and gateway_running:
        return PanelState.PUBLIC_RUNNING
    if web_running and gateway_running:
        return PanelState.LOCAL_READY
    if web_running or gateway_running or bridge_running:
        return PanelState.ANOMALY
    if launcher_open:
        return PanelState.LAUNCHER_OPEN
    return PanelState.ALL_CLOSED


def public_action_allowed(state: PanelState, preflight_passed: bool, admin: bool) -> bool:
    """判断“上线公网”按钮是否具备全部前置条件。"""
    return admin and preflight_passed and state == PanelState.LOCAL_READY


def sanitize_status_message(message: str) -> str:
    """脱敏界面和日志中的常见凭据形态。"""
    value = str(message)
    value = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+", r"\1[已隐藏]", value)
    value = re.sub(r"(?i)(token|cookie|password|passwd|secret)\s*[:=]\s*[^\s,;]+", r"\1=[已隐藏]", value)
    value = re.sub(r"(?i)(https?|socks5h?)://[^\s/@:]+:[^\s/@]+@", r"\1://[已隐藏]@", value)
    return value[:500]


def is_admin() -> bool:
    """返回当前进程是否已获得 Windows 管理员权限。"""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


class DeploymentPanel(tk.Tk):
    """把启动器、端口检查、防火墙和发布动作编排成一个桌面入口。"""

    def __init__(
        self,
        *,
        root: Path | None = None,
        admin_checker: Callable[[], bool] = is_admin,
        service_manager: ServiceManager | None = None,
        port_inspector: PortInspector | None = None,
        health_checker: HealthChecker | None = None,
        firewall_manager: FirewallManager | None = None,
        release_manager: ReleaseManager | None = None,
        operation_log: OperationLogger | None = None,
    ) -> None:
        super().__init__()
        self.project_root = Path(root or Path(__file__).resolve().parent)
        self.admin = bool(admin_checker())
        system_runner = _SystemProcessRunner(self.project_root)
        if port_inspector is None:
            from deployment_control.models import ProcessInfo

            def process_provider(pid: int) -> Any:
                record = next((item for item in system_runner.enumerate_processes() if item.pid == pid), None)
                if record is None:
                    return None
                return ProcessInfo(
                    pid=record.pid,
                    process_name=Path(record.executable).name,
                    executable=record.executable,
                    command_line=record.command_line,
                    working_directory=record.cwd,
                    create_time=record.create_time,
                )

            self.port_inspector = PortInspector(project_root=self.project_root, process_provider=process_provider)
        else:
            self.port_inspector = port_inspector
        self.service_manager = service_manager or ServiceManager(
            self.project_root,
            system_runner,
            _ServicePortAdapter(self.port_inspector),
        )
        self.health_checker = health_checker or HealthChecker(
            web_url=f"{LOCAL_URL}api/health",
            gateway_url="http://127.0.0.1:8780/health",
            public_url=f"{PUBLIC_URL}api/health",
        )
        self.firewall_manager = firewall_manager or FirewallManager(_SystemFirewallRunner())
        self.release_manager = release_manager or ReleaseManager()
        self.operation_log = operation_log or OperationLogger(self.project_root / "logs" / "deployment-panel.log")
        self.state = PanelState.ALL_CLOSED
        self.preflight_passed = False
        self._busy = False
        self.title("AI 创意工作台部署控制面板")
        self.geometry("980x700")
        self.minsize(820, 600)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_ui()
        self._apply_permission_state()
        self.after(200, self.refresh_status)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=16)
        header.pack(fill="x")
        ttk.Label(header, text="AI 创意工作台", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(header, text="独立部署控制面板 · 手动上线 · Windows 重启后不会自动开放公网", foreground="#52606d").pack(anchor="w", pady=(3, 0))
        summary = ttk.Frame(header)
        summary.pack(fill="x", pady=(12, 0))
        self.state_var = tk.StringVar(value=self.state.value)
        self.permission_var = tk.StringVar(value="管理员权限" if self.admin else "普通权限（只读）")
        ttk.Label(summary, textvariable=self.state_var, font=("Microsoft YaHei UI", 13, "bold")).pack(side="left")
        ttk.Label(summary, textvariable=self.permission_var, foreground="#8a4b08").pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.control_tab = ttk.Frame(self.notebook, padding=12)
        self.ports_tab = ttk.Frame(self.notebook, padding=12)
        self.release_tab = ttk.Frame(self.notebook, padding=12)
        self.logs_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.control_tab, text="运行控制")
        self.notebook.add(self.ports_tab, text="端口诊断")
        self.notebook.add(self.release_tab, text="版本发布")
        self.notebook.add(self.logs_tab, text="日志与文档")
        self._build_control_tab()
        self._build_ports_tab()
        self._build_release_tab()
        self._build_logs_tab()

    def _build_control_tab(self) -> None:
        actions = ttk.LabelFrame(self.control_tab, text="操作", padding=10)
        actions.pack(fill="x")
        self.open_launcher_button = ttk.Button(actions, text="打开启动器", command=self.open_launcher)
        self.open_launcher_button.grid(row=0, column=0, padx=5, pady=5)
        self.refresh_button = ttk.Button(actions, text="刷新状态", command=self.refresh_status)
        self.refresh_button.grid(row=0, column=1, padx=5, pady=5)
        self.preflight_button = ttk.Button(actions, text="启动前检测", command=self.run_preflight)
        self.preflight_button.grid(row=0, column=2, padx=5, pady=5)
        self.public_button = ttk.Button(actions, text="上线公网", command=self.go_public)
        self.public_button.grid(row=0, column=3, padx=5, pady=5)
        self.postflight_button = ttk.Button(actions, text="上线后检测", command=self.run_postflight)
        self.postflight_button.grid(row=0, column=4, padx=5, pady=5)
        self.open_workbench_button = ttk.Button(actions, text="打开工作台", command=self.open_workbench)
        self.open_workbench_button.grid(row=0, column=5, padx=5, pady=5)
        self.offline_button = ttk.Button(actions, text="全部下线", command=self.take_offline)
        self.offline_button.grid(row=0, column=6, padx=5, pady=5)
        self.control_summary = tk.StringVar(value="尚未检测")
        ttk.Label(self.control_tab, textvariable=self.control_summary, foreground="#52606d").pack(anchor="w", pady=(16, 8))
        self.result_text = tk.Text(self.control_tab, height=18, state="disabled", wrap="word", relief="flat", bg="#fbfcfd")
        self.result_text.pack(fill="both", expand=True)

    def _build_ports_tab(self) -> None:
        columns = ("port", "address", "pid", "process", "owner", "health", "note")
        self.port_tree = ttk.Treeview(self.ports_tab, columns=columns, show="headings", height=12)
        labels = {"port": "端口", "address": "监听地址", "pid": "PID", "process": "进程", "owner": "项目归属", "health": "健康", "note": "说明"}
        widths = {"port": 70, "address": 140, "pid": 80, "process": 150, "owner": 120, "health": 100, "note": 260}
        for column in columns:
            self.port_tree.heading(column, text=labels[column])
            self.port_tree.column(column, width=widths[column], anchor="w")
        self.port_tree.pack(fill="both", expand=True)

    def _build_release_tab(self) -> None:
        form = ttk.Frame(self.release_tab)
        form.pack(fill="x")
        self.package_var = tk.StringVar()
        self.sha_var = tk.StringVar()
        ttk.Label(form, text="发布 ZIP", width=12).grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.package_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="选择", command=self._choose_package).grid(row=0, column=2, padx=6)
        ttk.Label(form, text="SHA-256", width=12).grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.sha_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="检查发布包", command=self.inspect_release).grid(row=2, column=1, sticky="w", pady=8)
        self.apply_button = ttk.Button(form, text="执行更新", command=self.apply_release)
        self.apply_button.grid(row=2, column=1, sticky="e", pady=8)
        form.columnconfigure(1, weight=1)
        self.release_result = tk.Text(self.release_tab, height=16, state="disabled", wrap="word", relief="flat", bg="#fbfcfd")
        self.release_result.pack(fill="both", expand=True)

    def _build_logs_tab(self) -> None:
        actions = ttk.Frame(self.logs_tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="刷新面板日志", command=self._load_log).pack(side="left")
        ttk.Button(actions, text="打开日志目录", command=lambda: self._open_path(self.project_root / "logs")).pack(side="left", padx=8)
        ttk.Button(actions, text="打开部署文档", command=lambda: self._open_path(self.project_root / "docs" / "deployment" / "public-startup-guide.md")).pack(side="left")
        self.log_view = tk.Text(self.logs_tab, state="disabled", wrap="word", relief="flat", bg="#fbfcfd")
        self.log_view.pack(fill="both", expand=True, pady=(10, 0))

    def _apply_permission_state(self) -> None:
        modifying = (self.open_launcher_button, self.public_button, self.offline_button, self.apply_button)
        for widget in modifying:
            if widget is not None and not self.admin:
                widget.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (self.open_launcher_button, self.refresh_button, self.preflight_button, self.public_button, self.postflight_button, self.open_workbench_button, self.offline_button):
            if self.admin or widget not in (self.public_button, self.offline_button):
                widget.configure(state="disabled" if busy else "normal")
        self._apply_permission_state()

    def _append_result(self, message: str) -> None:
        safe = sanitize_status_message(message)
        self.result_text.configure(state="normal")
        self.result_text.insert("end", safe + "\n")
        self.result_text.see("end")
        self.result_text.configure(state="disabled")
        if hasattr(self.operation_log, "write"):
            self.operation_log.write("panel", {"message": safe})
        else:
            self.operation_log.record(action="panel", result="info", details={"message": safe})

    def _run_background(self, action: str, worker: Callable[[], Any], done: Callable[[Any], None] | None = None) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._append_result(f"开始：{action}")

        def run() -> None:
            try:
                result = worker()
                self.after(0, lambda: done(result) if done else None)
            except Exception as exc:  # noqa: BLE001 - UI boundary converts to safe message
                safe = sanitize_status_message(f"{action}失败：{type(exc).__name__}: {exc}")
                self.after(0, lambda: self._append_result(safe))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=run, daemon=True).start()

    def open_launcher(self) -> None:
        if hasattr(self.service_manager, "launcher_running") and self.service_manager.launcher_running():
            self._append_result("启动器已经打开，未重复启动。")
            return
        if hasattr(self.service_manager, "start_launcher"):
            self.service_manager.start_launcher()
        else:
            subprocess.Popen(["cmd.exe", "/c", str(self.project_root / "启动AI创意工作台.bat")], cwd=self.project_root)
        self.state = PanelState.LAUNCHER_OPEN
        self.state_var.set(self.state.value)
        self._append_result("已打开现有启动器，请在启动器中点击“启动”。")

    def refresh_status(self) -> None:
        def worker() -> Any:
            return self._collect_status()

        self._run_background("刷新状态", worker, self._apply_status)

    def _collect_status(self) -> dict[str, Any]:
        ports: list[Any] = []
        for port in MANAGED_PORTS:
            if hasattr(self.port_inspector, "inspect"):
                ports.extend(self.port_inspector.inspect(port))
            else:
                ports.extend(self.port_inspector.inspect_port(port))
        return {"ports": ports, "firewall": self.firewall_manager.inspect() if hasattr(self.firewall_manager, "inspect") else None}

    def _apply_status(self, status: dict[str, Any]) -> None:
        for item in self.port_tree.get_children():
            self.port_tree.delete(item)
        ports = status.get("ports", [])
        web_running = gateway_running = bridge_running = False
        web_public = False
        unknown = False
        for item in ports:
            if isinstance(item, dict):
                data = item
            elif hasattr(item, "to_dict"):
                data = item.to_dict()
            else:
                data = getattr(item, "__dict__", {})
            listener = getattr(item, "listener", None)
            port = int(data.get("port", getattr(listener, "port", 0)))
            address = str(data.get("address", data.get("local_address", getattr(listener, "address", "-"))))
            owner = str(data.get("owner", data.get("ownership", "未知占用")))
            running = bool(data.get("listening", data.get("is_listening", data.get("pid", getattr(listener, "pid", 0)))))
            health = str(data.get("health", "未检测"))
            self.port_tree.insert("", "end", values=(port, address, data.get("pid", getattr(listener, "pid", "-")), data.get("process_name", data.get("process", getattr(listener, "process_name", "-"))), owner, health, data.get("note", data.get("evidence_summary", ""))))
            unknown = unknown or (running and "未知" in owner)
            web_running = web_running or port == 8775 and running
            gateway_running = gateway_running or port == 8780 and running
            bridge_running = bridge_running or port == 7896 and running
            web_public = web_public or port == 8775 and address in {"0.0.0.0", "::"}
        launcher_open = bool(getattr(self.service_manager, "launcher_running", lambda: False)())
        if not launcher_open and hasattr(self.service_manager, "runner"):
            processes = self.service_manager.runner.enumerate_processes()
            launcher_open = any(
                self.service_manager.is_owned_process(process, "launcher")
                for process in processes
            )
        self.state = determine_panel_state(launcher_open=launcher_open, web_running=web_running, web_public=web_public, gateway_running=gateway_running, bridge_running=bridge_running, has_unknown_conflict=unknown)
        self.state_var.set(self.state.value)
        self.control_summary.set("状态已刷新；未知占用不会由面板结束。")
        self._append_result(f"当前状态：{self.state.value}")

    def run_preflight(self) -> None:
        self._run_background("启动前检测", self._perform_preflight, self._finish_preflight)

    def _perform_preflight(self) -> dict[str, Any]:
        checks: list[str] = []
        required = ("chat2api/.env", ".venv/Scripts/python.exe", "data/creative_studio.db", "data/images", "data/uploads", "data/image_job_state")
        failures = []
        for relative in required:
            exists = (self.project_root / relative).exists()
            checks.append(f"{relative}: {'通过' if exists else '失败'}")
            if not exists:
                failures.append(relative)
        for label, checker in (("8775 Web", "check_local_web"), ("8780 网关", "check_gateway")):
            if hasattr(self.health_checker, checker):
                result = getattr(self.health_checker, checker)()
                summary = getattr(result, "summary", str(result))
                checks.append(f"{label}：{summary}")
                level = str(getattr(result, "level", "")).lower()
                if level and not level.endswith("pass"):
                    failures.append(label)
        status = self._collect_status()
        for item in status["ports"]:
            data = item.to_dict() if hasattr(item, "to_dict") else item if isinstance(item, dict) else getattr(item, "__dict__", {})
            checks.append(f"端口 {data.get('port', '?')}：已读取")
            if data.get("ownership") in {"unknown", "未知占用"}:
                failures.append(f"端口 {data.get('port', '?')} 未知占用")
        return {"passed": not failures, "checks": checks, "failures": failures}

    def _finish_preflight(self, result: dict[str, Any]) -> None:
        self.preflight_passed = bool(result.get("passed"))
        for line in result.get("checks", []):
            self._append_result(line)
        self._append_result("启动前检测通过，可以上线公网。" if self.preflight_passed else "启动前检测存在关键失败，已阻止上线公网。")

    def go_public(self) -> None:
        if not public_action_allowed(self.state, self.preflight_passed, self.admin):
            self._append_result("当前不满足上线条件：需要管理员权限、本地服务就绪和最近一次启动前检测通过。")
            return
        self._run_background("上线公网", self._go_public_impl, self._finish_public)

    def _go_public_impl(self) -> Any:
        latest = self._perform_preflight()
        if not latest.get("passed"):
            raise RuntimeError("上线前复查未通过")
        result = self.service_manager.switch_web_to_public(self._web_environment())
        self.firewall_manager.enable()
        return result

    def _web_environment(self) -> dict[str, str]:
        """构造 Web 子进程环境；只提取控制令牌，不把其写入面板状态。"""
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(self.project_root / "src"),
                "CREATIVE_STUDIO_HOST": "127.0.0.1",
                "CREATIVE_STUDIO_PORT": "8775",
                "CREATIVE_STUDIO_AI_GATEWAY_URL": "http://127.0.0.1:8780",
                "CREATIVE_STUDIO_AI_API_KEY": "local-chatgpt-gateway",
                "CREATIVE_STUDIO_AI_MODEL": "gpt-5-6-mini",
                "CREATIVE_STUDIO_AI_V2_LIVE": "1",
                "CREATIVE_STUDIO_DATA_DIR": str(self.project_root / "data"),
                "CHATGPT_IMAGES_DIR": str(self.project_root / "data" / "images"),
                "CHATGPT_IMAGE_JOB_DIR": str(self.project_root / "data" / "image_job_state"),
            }
        )
        env_file = self.project_root / "chat2api" / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("CHATGPT_CONTROL_TOKEN="):
                    env["CREATIVE_STUDIO_AI_CONTROL_TOKEN"] = line.split("=", 1)[1].strip()
                    break
        return env

    def _finish_public(self, result: Any) -> None:
        self.state = PanelState.PUBLIC_RUNNING
        self.state_var.set(self.state.value)
        self._append_result("公网 Web 已切换并放行 8775；8780/7896 仍只允许回环地址。")
        if result:
            self._append_result(str(result))
        self.run_postflight()

    def run_postflight(self) -> None:
        self._run_background("上线后检测", self._perform_postflight, self._finish_postflight)

    def _perform_postflight(self) -> dict[str, Any]:
        result = self.health_checker.check_public_web() if hasattr(self.health_checker, "check_public_web") else {"ok": True}
        if hasattr(result, "level"):
            return {"ok": str(result.level).lower().endswith("pass"), "summary": result.summary}
        return result

    def _finish_postflight(self, result: Any) -> None:
        ok = bool(result.get("ok", result)) if isinstance(result, dict) else bool(result)
        self._append_result("上线后检测通过，公网运行中。" if ok else "上线后检测失败，请查看端口诊断和日志。")
        if not ok:
            self.state = PanelState.ANOMALY
            self.state_var.set(self.state.value)

    def open_workbench(self) -> None:
        url = PUBLIC_URL if self.state == PanelState.PUBLIC_RUNNING else LOCAL_URL if self.state == PanelState.LOCAL_READY else ""
        if not url:
            self._append_result("服务尚未处于可打开状态。")
            return
        webbrowser.open(url)

    def take_offline(self) -> None:
        if not self.admin:
            self._append_result("普通权限只能查看状态、日志和文档。")
            return
        self._run_background("全部下线", self._take_offline_impl, self._finish_offline)

    def _take_offline_impl(self) -> Any:
        if hasattr(self.service_manager, "shutdown"):
            result = self.service_manager.shutdown(self.firewall_manager)
        elif hasattr(self.service_manager, "shutdown_all"):
            result = self.service_manager.shutdown_all()
            self.firewall_manager.disable()
        else:
            result = self.service_manager.stop_all()
            self.firewall_manager.disable()
        if hasattr(self.firewall_manager, "remove"):
            self.firewall_manager.remove()
        return result

    def _finish_offline(self, result: Any) -> None:
        self.preflight_passed = False
        self._append_result("已执行全部下线：Web、AI 网关、代理桥、启动器和 8775 公网放行均已请求关闭。")
        if result:
            self._append_result(str(result))
        try:
            self._apply_status(self._collect_status())
        except Exception as exc:  # pragma: no cover - only an OS refresh failure
            self.state = PanelState.ANOMALY
            self.state_var.set(self.state.value)
            self._append_result(f"下线后复查失败：{type(exc).__name__}")

    def _choose_package(self) -> None:
        path = filedialog.askopenfilename(filetypes=(("ZIP", "*.zip"), ("所有文件", "*.*")))
        if path:
            self.package_var.set(path)

    def inspect_release(self) -> None:
        package = self.package_var.get().strip()
        digest = self.sha_var.get().strip()
        if not package or not digest:
            self._append_result("请先选择发布 ZIP 并填写 SHA-256。")
            return
        self._run_background("检查发布包", lambda: self.release_manager.inspect_package(package, digest), lambda result: self._show_release_result(result))

    def apply_release(self) -> None:
        if not self.admin:
            return
        package = self.package_var.get().strip()
        digest = self.sha_var.get().strip()
        if not package or not digest or not messagebox.askyesno("确认更新", "更新会先全部下线并创建回滚点，是否继续？"):
            return
        self._run_background("执行更新", lambda: (self._take_offline_impl(), self.release_manager.apply(package, digest)), lambda result: self._show_release_result(result[-1]))

    def _show_release_result(self, result: Any) -> None:
        text = sanitize_status_message(str(result))
        self.release_result.configure(state="normal")
        self.release_result.insert("end", text + "\n")
        self.release_result.see("end")
        self.release_result.configure(state="disabled")
        self._append_result(text)

    def _load_log(self) -> None:
        path = self.project_root / "logs" / "deployment-panel.log"
        content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else "暂无面板日志。"
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("end", sanitize_status_message(content))
        self.log_view.configure(state="disabled")

    @staticmethod
    def _open_path(path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.as_uri())


if __name__ == "__main__":
    DeploymentPanel().mainloop()
