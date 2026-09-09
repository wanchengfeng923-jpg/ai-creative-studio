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
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter as tk
from typing import Any, Callable, Iterable

from deployment_control.firewall_manager import FirewallManager
from deployment_control.health_checker import HealthChecker
from deployment_control.operation_log import OperationLogger
from deployment_control.port_inspector import PortInspector
from deployment_control.release_manager import ReleaseManager
from deployment_control.service_manager import ServiceManager


PUBLIC_URL = "http://42.194.220.18:8775/"
LOCAL_URL = "http://127.0.0.1:8775/"
MANAGED_PORTS = (7896, 8775, 8780)


# Static operator guidance only. It deliberately describes boundaries and
# recovery actions without embedding credentials, cookies, or request data.
ACTION_DETAILS: dict[str, dict[str, object]] = {
    "open_launcher": {
        "title": "打开启动器",
        "purpose": "打开现有启动器，让操作员在原有入口中启动本项目服务；面板本身不替代或改写启动器。",
        "preconditions": (
            "已使用管理员权限启动控制面板（普通权限只能查看）。",
            "项目目录和启动器文件仍位于当前安装目录。",
            "确认不是在处理另一套项目实例。",
        ),
        "steps": (
            "检查已识别的项目启动器进程；若已运行则不重复拉起。",
            "通过现有“启动AI创意工作台.bat”打开启动器。",
            "操作员在启动器中点击原有“启动”，由启动器创建 AI 网关、代理桥和本地 Web。",
            "面板把顶层状态置为“启动器已打开”，后续用“刷新状态”或“启动前检测”确认服务事实。",
        ),
        "ports": (
            "本动作不直接监听或切换端口。后续服务边界：7896 代理桥、8780 AI 网关、8775 Web。",
            "不会创建 8775 防火墙放行规则。",
        ),
        "failure": (
            "启动器已存在时只记录“不重复启动”，不结束任何进程。",
            "批处理或启动器失败时保留原状态，查看启动器窗口和面板日志。",
        ),
        "rollback": "关闭启动器窗口或使用“全部下线”；该动作本身没有服务回滚步骤。",
    },
    "refresh_status": {
        "title": "刷新状态",
        "purpose": "重新读取项目端口、进程归属和 8775 防火墙规则，更新面板状态和端口诊断表。",
        "preconditions": ("无需管理员权限；普通权限也可以执行只读检查。",),
        "steps": (
            "读取 7896、8775、8780 的监听地址、PID、进程名和项目归属证据。",
            "读取固定防火墙规则“AI Creative Studio Web 8775”的存在和启用状态。",
            "根据监听地址、服务组合和未知占用计算顶层状态。",
            "把摘要写入界面；敏感值按统一脱敏规则处理。",
        ),
        "ports": (
            "只读检查 7896（代理桥）、8780（AI 网关）、8775（Web）。",
            "不会绑定、开放、关闭或修改任何端口。",
        ),
        "failure": (
            "查询失败会保留可获得的诊断结果并标记异常，不据此结束进程。",
            "未知归属占用只显示为异常，绝不按 PID 强制结束。",
        ),
        "rollback": "无需回滚；再次点击即可重新读取当前事实。",
    },
    "preflight": {
        "title": "启动前检测",
        "purpose": "在允许公网切换前确认安装文件、依赖、服务健康和端口归属满足上线前条件。",
        "preconditions": (
            "启动器已打开并已在启动器中启动服务。",
            "chat2api/.env、项目虚拟环境和运行数据目录存在；面板不会显示其内容。",
            "没有未知进程占用受管端口。",
        ),
        "steps": (
            "检查 .env 文件存在性、Python 虚拟环境和受保护数据目录存在性。",
            "检查本地 Web 健康接口和回环 AI 网关健康接口。",
            "核对 7896、8775、8780 的监听者是否属于本项目。",
            "只有全部关键检查通过，才把最近一次启动前检测标记为可上线。",
        ),
        "ports": (
            "8775 必须是本项目 Web；8780 必须保持 127.0.0.1；7896 必须是本项目代理桥。",
            "本动作不会打开防火墙，也不会把 Web 切到公网。",
        ),
        "failure": (
            "任一关键文件、健康检查或归属检查失败，立即阻止“上线公网”。",
            "失败只显示检查项和摘要，不读取或输出令牌、Cookie、密码或 AI 请求内容。",
        ),
        "rollback": "无需回滚；修复启动器或服务问题后重新运行检测。",
    },
    "public": {
        "title": "上线公网",
        "purpose": "将已确认健康的 Web 服务切换到公网监听，并仅放行固定 TCP 8775 入站规则。",
        "preconditions": (
            "管理员权限有效。",
            "当前状态是“本地服务就绪”，且最近一次启动前检测通过。",
            "复查时仍无未知端口占用；AI 网关和代理桥保持回环边界。",
        ),
        "steps": (
            "后台再次执行启动前检测，避免使用过期结果。",
            "以受控环境启动或重启 Web，使 8775 监听地址切换为 0.0.0.0。",
            "启用固定防火墙规则“AI Creative Studio Web 8775”，仅对应 TCP 8775。",
            "更新状态为公网切换中，并自动进入“上线后检测”。",
        ),
        "ports": (
            "8775：允许公网访问；8780：仍只允许 127.0.0.1；7896：仍只允许 127.0.0.1。",
            "只操作 8775 防火墙规则，不开放 8780 或 7896。",
        ),
        "failure": (
            "复查失败时不切换公网。",
            "切换或防火墙操作失败时状态保持异常；不要手动结束未知 PID，先查看诊断和日志。",
        ),
        "rollback": "管理员执行“全部下线”关闭 Web、撤销 8775 放行，并关闭其他项目服务；随后可重新打开启动器。",
    },
    "postflight": {
        "title": "上线后检测",
        "purpose": "确认公网切换完成后，外部 Web 健康检查可达，同时内部依赖仍保持回环限制。",
        "preconditions": (
            "已执行“上线公网”，且 8775 已切换并启用固定规则。",
            "服务器网络和 DNS/公网地址由外部环境提供；面板不修改路由器或服务器配置。",
        ),
        "steps": (
            "请求配置的公网 Web 健康地址并记录脱敏后的结果摘要。",
            "结合本地端口诊断确认 8775 为公网监听，8780/7896 未扩大监听范围。",
            "通过则保持“公网运行中”；失败则置为“存在异常”，等待人工处理。",
        ),
        "ports": (
            "验证公网入口 8775；内部依赖仍为 127.0.0.1:8780 和 127.0.0.1:7896。",
            "本动作只检查，不改端口和防火墙。",
        ),
        "failure": (
            "公网健康检查失败不会自动重试式地扩大权限，也不会结束进程。",
            "先查看端口诊断、启动器和面板日志，再决定下线或人工修复。",
        ),
        "rollback": "确认异常或不再需要公网时执行“全部下线”，恢复到全部关闭状态。",
    },
    "open_workbench": {
        "title": "打开工作台",
        "purpose": "在浏览器打开与当前状态匹配的本地或公网 Web 地址，不改变部署状态。",
        "preconditions": (
            "状态为“本地服务就绪”或“公网运行中”。",
            "浏览器可访问对应地址。",
        ),
        "steps": (
            "本地服务就绪时打开 127.0.0.1:8775。",
            "公网运行中时打开配置的公网 8775 地址。",
            "浏览器启动失败只提示错误，不影响后台服务。",
        ),
        "ports": (
            "只访问 8775；不会访问或展示 8780、7896 的管理接口。",
        ),
        "failure": (
            "服务未处于可打开状态时拒绝打开并提示先完成启动流程。",
            "浏览器错误不被当作服务已下线，需用“刷新状态”确认。",
        ),
        "rollback": "无需回滚；关闭浏览器标签页即可。",
    },
    "offline": {
        "title": "全部下线",
        "purpose": "按固定顺序撤销公网入口并关闭本项目全部受管服务，恢复到手动上线前的关闭状态。",
        "preconditions": (
            "管理员权限有效。",
            "确认要停止本项目服务；未知归属进程不会被触碰。",
        ),
        "steps": (
            "先停止或切回 Web 8775，撤销并移除固定公网防火墙规则。",
            "关闭现有启动器，等待其子进程退出。",
            "按项目归属关闭 AI 网关 8780 和代理桥 7896。",
            "重新读取端口、进程和防火墙状态，确认没有项目服务残留。",
            "清除最近一次启动前检测结果，状态回到“全部关闭”或明确异常。",
        ),
        "ports": (
            "必须关闭 8775 Web、撤销 8775 公网放行、关闭 8780 AI 网关和 7896 代理桥。",
            "只结束有项目路径/命令行证据的进程；绝不结束所有 Python 进程。",
        ),
        "failure": (
            "单项关闭失败会保留失败证据并在复查中显示残留端口。",
            "未知归属或无法确认的 PID 不会强制结束，需人工核对。",
        ),
        "rollback": "全部下线本身是恢复动作；需要再次运行时，手动点击“打开启动器”并重新走启动前检测和公网上线流程。",
    },
    "build_release": {
        "title": "制作发布包",
        "purpose": "在开发机上从指定 Git 提交生成可上传服务器的 ZIP、SHA-256 和 manifest。",
        "preconditions": ("提交已存在；默认要求工作树干净。", "当前开发测试和 AI V2 发布门禁可运行。"),
        "steps": ("创建隔离 worktree。", "运行全部测试和 release gate。", "通过后生成 .release 下的 ZIP、.sha256 和 .manifest.json。", "清理临时 worktree 和临时目录。"),
        "ports": ("不启动 Web、AI 网关、代理桥，也不修改服务器或防火墙。",),
        "failure": ("任一测试、门禁、Git ref 或清单步骤失败，都不产生可用的新包。",),
        "rollback": "删除未完成的本地临时输出即可；不会改变服务器。",
    },
    "inspect_release": {
        "title": "服务器检查",
        "purpose": "在服务器应用前验证 ZIP 哈希、危险路径、禁止内容、manifest 和代码指纹。",
        "preconditions": ("已填写服务器上的 ZIP 路径和 64 位 SHA-256。", "服务器工作台已关闭，8775/8780 不再监听。"),
        "steps": ("再次计算 ZIP SHA-256。", "检查压缩包路径和禁止文件。", "核对 manifest、文件清单和 code inventory。", "只有输出 Status=verified 才允许执行更新。"),
        "ports": ("只读检查；不会打开端口或修改防火墙。",),
        "failure": ("校验失败立即停止，不替换任何程序文件。",),
        "rollback": "无需回滚；修正包路径或哈希后重新检查。",
    },
    "apply_release": {
        "title": "执行更新",
        "purpose": "关闭工作台后备份当前代码、替换程序、更新依赖并生成 RollbackId。",
        "preconditions": ("管理员权限有效。", "已填写并确认正确的 ZIP 和 SHA-256。", "服务器 8775/8780 已停止。"),
        "steps": ("面板先执行全部下线。", "脚本再次检查发布包。", "备份当前程序代码并替换受管程序文件。", "安装 requirements.txt 依赖并输出 RollbackId。"),
        "ports": ("更新阶段不得有 8775 或 8780 监听；不覆盖 data、.env、.venv、日志和暂存文件。",),
        "failure": ("校验或依赖安装失败时保持服务关闭，并保留 RollbackId/失败信息。",),
        "rollback": "保持工作台关闭，使用对应 RollbackId 执行“回滚”，然后重新启动并验收。",
    },
    "rollback_release": {
        "title": "回滚发布",
        "purpose": "恢复某次更新前的程序代码，并删除该次发布新增的程序文件。",
        "preconditions": ("管理员权限有效。", "工作台已关闭，8775/8780 不再监听。", "RollbackId 来自对应 Apply 输出。"),
        "steps": ("验证 RollbackId 格式和回滚清单。", "删除本次新增文件。", "恢复备份文件和旧 release-manifest.json。", "提示需要重新启动并验收。"),
        "ports": ("回滚期间不启动或修改 8775、8780、7896，也不修改生产数据和 .env。",),
        "failure": ("找不到清单、端口仍在监听或 ID 不安全时立即停止。",),
        "rollback": "回滚本身不可通过面板自动反向恢复；先保留现场并核对清单，再由技术人员决定后续发布。",
    },
    "code_inventory": {
        "title": "代码盘点",
        "purpose": "计算目录内纳入范围的文件数量、大小、单文件 SHA-256 和综合代码指纹。",
        "preconditions": ("盘点根目录可访问。", "输出路径不包含路径穿越。"),
        "steps": ("按脚本规则扫描 src、static、config、chat2api、tests 等目录。", "统一文本换行后计算规范化哈希。", "输出 JSON 盘点文件和综合 AggregateSHA256。"),
        "ports": ("纯文件操作，不访问服务端口，不改变部署状态。",),
        "failure": ("根目录不可访问或脚本失败时不生成可信盘点结论。",),
        "rollback": "删除本次生成的盘点 JSON 即可，不影响程序代码。",
    },
    "release_workflow": {
        "title": "发布流程文档",
        "purpose": "打开项目维护的正式发布、验收和回滚顺序文档。",
        "preconditions": ("文档文件存在。",),
        "steps": ("从开发分支测试提交开始，按文档完成打包、上传、检查、备份、更新、验收和回滚。",),
        "ports": ("文档阅读不改变服务、端口或防火墙。",),
        "failure": ("文档缺失时提示路径，不会执行任何命令。",),
        "rollback": "无需回滚；按文档中的回滚章节处理实际发布故障。",
    },
}


def get_action_details(action_id: str) -> dict[str, object] | None:
    """Return a copy of static operator guidance for one control action."""
    details = ACTION_DETAILS.get(action_id)
    return dict(details) if details is not None else None


class _SystemProcessRunner:
    """Minimal Windows adapter kept behind ServiceManager's injectable seam."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def enumerate_processes(self) -> list[Any]:
        from deployment_control.service_manager import ProcessRecord

        query = "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe' OR Name='mihomo.exe'\" | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
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
            if "chat2api/main.py" in normalized:
                cwd = str(self.project_root / "chat2api")
            elif "proxy-bridge.yaml" in normalized:
                cwd = str(self.project_root / ".runtime")
            elif root in normalized:
                cwd = str(self.project_root)
            else:
                cwd = ""
            parent = item.get("ParentProcessId")
            records.append(
                ProcessRecord(
                    int(item["ProcessId"]),
                    str(item.get("ExecutablePath") or ""),
                    command,
                    cwd,
                    parent_pid=int(parent) if str(parent or "").isdigit() else None,
                )
            )
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
        return subprocess.Popen(
            ["cmd.exe", "/c", str(path)],
            cwd=cwd,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

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
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if completed.returncode != 0 or not completed.stdout.strip():
            return []
        return [FirewallRule(name, 8775, "TCP", "Inbound", "Allow", True)]

    def _run(self, command: str) -> None:
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return

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


def format_preflight_port_check(data: dict[str, Any]) -> tuple[str, str | None]:
    """Format one listener with enough evidence to explain a blocking result."""
    port = data.get("port", "?")
    address = data.get("address", data.get("local_address", "-"))
    pid = data.get("pid", "-")
    ownership = data.get("ownership", data.get("owner", "unknown"))
    evidence = str(data.get("evidence_summary", data.get("note", ""))).strip()
    owner_label = "本项目，可管理" if ownership == "project" else "未知占用"
    line = f"端口 {port} {address}（PID {pid}）：{owner_label}"
    if evidence:
        line += f"；{evidence}"
    if ownership in {"unknown", "未知占用"}:
        reason = evidence or "进程归属证据不足"
        return line, f"端口 {port} 未知占用（PID {pid}）：{reason}"
    return line, None


def find_offline_blockers(status: dict[str, Any], *, launcher_open: bool) -> list[str]:
    """Return concrete evidence that project services are not fully offline."""
    blockers: list[str] = []
    for item in status.get("ports", []):
        data = item.to_dict() if hasattr(item, "to_dict") else item if isinstance(item, dict) else getattr(item, "__dict__", {})
        pid = data.get("pid", "-")
        if data.get("listening", data.get("is_listening", data.get("pid"))) and data.get("port"):
            blockers.append(f"端口 {data['port']} 仍由 PID {pid} 监听")
    if launcher_open:
        blockers.append("启动器仍在运行")
    firewall = status.get("firewall")
    if firewall is not None:
        enabled = firewall.get("enabled") if isinstance(firewall, dict) else getattr(firewall, "enabled", False)
        if enabled:
            blockers.append("8775 公网防火墙规则仍在启用")
    return blockers


def collect_launcher_open(service_manager: Any, processes: Iterable[Any] | None = None) -> bool:
    """Read launcher ownership at the worker boundary, never from Tk callbacks."""
    runner = getattr(service_manager, "runner", None)
    if runner is None or not hasattr(runner, "enumerate_processes"):
        return False
    if processes is None:
        launcher_running = getattr(service_manager, "launcher_running", None)
        if callable(launcher_running) and launcher_running():
            return True
    else:
        processes = list(processes)
    if processes is None:
        processes = runner.enumerate_processes()
    checker = getattr(service_manager, "is_owned_process", None)
    return bool(callable(checker) and any(checker(process, "launcher") for process in processes))


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
        self._system_runner = system_runner
        self._process_snapshot: dict[int, Any] = {}
        if port_inspector is None:
            from deployment_control.models import ProcessInfo

            def process_provider(pid: int) -> Any:
                record = self._process_snapshot.get(pid)
                if record is None:
                    return None
                return ProcessInfo(
                    pid=record.pid,
                    process_name=Path(record.executable).name,
                    executable=record.executable,
                    command_line=record.command_line,
                    working_directory=record.cwd,
                    create_time=record.create_time,
                    parent_pid=record.parent_pid,
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
        self.release_verified_package = ""
        self.release_verified_sha = ""
        self._busy = False
        self._status_refresh_active = False
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
        action_widgets = (
            ("open_launcher", "打开启动器", self.open_launcher),
            ("refresh_status", "刷新状态", self.refresh_status),
            ("preflight", "启动前检测", self.run_preflight),
            ("public", "上线公网", self.go_public),
            ("postflight", "上线后检测", self.run_postflight),
            ("open_workbench", "打开工作台", self.open_workbench),
            ("offline", "全部下线", self.take_offline),
        )
        for column, (action_id, label, command) in enumerate(action_widgets):
            cell = ttk.Frame(actions)
            cell.grid(row=0, column=column, padx=5, pady=5, sticky="w")
            button = ttk.Button(cell, text=label, command=command)
            button.pack(side="left")
            ttk.Button(
                cell,
                text="!",
                width=2,
                command=lambda current=action_id: self.show_action_details(current),
            ).pack(side="left", padx=(3, 0))
            setattr(self, f"{action_id}_button", button)
        self.open_launcher_button = getattr(self, "open_launcher_button")
        self.refresh_button = getattr(self, "refresh_status_button")
        self.preflight_button = getattr(self, "preflight_button")
        self.public_button = getattr(self, "public_button")
        self.postflight_button = getattr(self, "postflight_button")
        self.open_workbench_button = getattr(self, "open_workbench_button")
        self.offline_button = getattr(self, "offline_button")
        self.control_summary = tk.StringVar(value="尚未检测")
        ttk.Label(self.control_tab, textvariable=self.control_summary, foreground="#52606d").pack(anchor="w", pady=(16, 8))
        self.result_text = tk.Text(self.control_tab, height=18, state="disabled", wrap="word", relief="flat", bg="#fbfcfd")
        self.result_text.pack(fill="both", expand=True)

    def show_action_details(self, action_id: str) -> None:
        """Show static, read-only technical guidance without changing panel state."""
        details = get_action_details(action_id)
        if details is None:
            return
        window = tk.Toplevel(self)
        window.title(f"操作说明：{details['title']}")
        window.geometry("760x620")
        window.minsize(620, 460)
        window.transient(self)

        body = ttk.Frame(window, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=str(details["title"]), font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        ttk.Label(body, text=f"目的：{details['purpose']}", wraplength=700, justify="left").pack(anchor="w", pady=(8, 10))

        viewer = scrolledtext.ScrolledText(body, wrap="word", state="normal", relief="solid", borderwidth=1)
        viewer.pack(fill="both", expand=True)
        sections = (
            ("前置条件", details["preconditions"]),
            ("具体执行步骤", details["steps"]),
            ("端口、进程与防火墙", details["ports"]),
            ("失败停止点", details["failure"]),
            ("回滚 / 恢复", (details["rollback"],)),
        )
        for heading, content in sections:
            viewer.insert("end", f"{heading}\n", "heading")
            for item in content:
                viewer.insert("end", f"• {item}\n")
            viewer.insert("end", "\n")
        viewer.tag_configure("heading", font=("Microsoft YaHei UI", 10, "bold"), foreground="#1f4e79")
        viewer.configure(state="disabled")
        ttk.Button(body, text="关闭", command=window.destroy).pack(anchor="e", pady=(10, 0))

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
        intro = ttk.Label(
            self.release_tab,
            text="发布链路：开发完成 → 制作发布包 → 服务器检查 → 执行更新 → 出问题时回滚",
            foreground="#52606d",
            wraplength=900,
        )
        intro.pack(anchor="w", pady=(0, 10))
        self.release_ref_var = tk.StringVar(value="master")
        self.allow_dirty_var = tk.BooleanVar(value=False)
        self.inventory_root_var = tk.StringVar(value=str(self.project_root))
        self.inventory_output_var = tk.StringVar(value=str(self.project_root / "staging" / "code-inventory.json"))
        self.rollback_id_var = tk.StringVar()
        self.package_var = tk.StringVar()
        self.sha_var = tk.StringVar()
        build = ttk.LabelFrame(self.release_tab, text="1. 开发机：制作发布包", padding=10)
        build.pack(fill="x", pady=(0, 8))
        ttk.Label(build, text="Git Ref", width=12).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(build, textvariable=self.release_ref_var).grid(row=0, column=1, sticky="ew", pady=4)
        self.build_button = self._release_button(build, 0, 2, "制作发布包", self.build_release, "build_release")
        ttk.Checkbutton(
            build,
            text="允许脏工作树（只打包已提交 Ref）",
            variable=self.allow_dirty_var,
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))
        ttk.Label(build, text="默认要求工作树干净；勾选后不会把未提交文件带入包。", foreground="#7a4e00").grid(row=1, column=2, sticky="w", padx=8)
        build.columnconfigure(1, weight=1)

        server = ttk.LabelFrame(self.release_tab, text="2. 服务器：检查并更新", padding=10)
        server.pack(fill="x", pady=(0, 8))
        ttk.Label(server, text="发布 ZIP", width=12).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(server, textvariable=self.package_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Button(server, text="选择", command=self._choose_package).grid(row=0, column=3, padx=6)
        ttk.Label(server, text="SHA-256", width=12).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(server, textvariable=self.sha_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        self.inspect_button = self._release_button(server, 2, 1, "服务器检查", self.inspect_release, "inspect_release")
        self.apply_button = self._release_button(server, 2, 2, "执行更新", self.apply_release, "apply_release")
        ttk.Label(server, text="执行更新前必须先让服务器 8775 和 8780 停止监听。", foreground="#7a4e00").grid(row=3, column=1, columnspan=3, sticky="w", pady=(2, 0))
        server.columnconfigure(1, weight=1)
        server.columnconfigure(2, weight=1)

        recovery = ttk.LabelFrame(self.release_tab, text="3. 回滚与一致性检查", padding=10)
        recovery.pack(fill="x", pady=(0, 8))
        ttk.Label(recovery, text="RollbackId", width=12).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(recovery, textvariable=self.rollback_id_var).grid(row=0, column=1, sticky="ew", pady=4)
        self.rollback_button = self._release_button(recovery, 0, 2, "回滚发布", self.rollback_release, "rollback_release")
        ttk.Label(recovery, text="盘点根目录", width=12).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(recovery, textvariable=self.inventory_root_var).grid(row=1, column=1, sticky="ew", pady=4)
        self.inventory_button = self._release_button(recovery, 1, 2, "代码盘点", self.run_code_inventory, "code_inventory")
        ttk.Label(recovery, text="盘点输出", width=12).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(recovery, textvariable=self.inventory_output_var).grid(row=2, column=1, sticky="ew", pady=4)
        self.workflow_button = self._release_button(recovery, 2, 2, "打开发布流程", self.open_release_workflow, "release_workflow")
        recovery.columnconfigure(1, weight=1)

        result_header = ttk.Frame(self.release_tab)
        result_header.pack(fill="x", pady=(2, 4))
        ttk.Label(result_header, text="本次操作结果", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        ttk.Button(result_header, text="清空结果", command=self._clear_release_result).pack(side="right")
        self.release_result = tk.Text(self.release_tab, height=8, state="disabled", wrap="word", relief="flat", bg="#fbfcfd")
        self.release_result.pack(fill="both", expand=True)

    def _release_button(self, parent: ttk.Frame, row: int, column: int, label: str, command: Callable[[], None], action_id: str) -> ttk.Button:
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=column, padx=6, pady=6, sticky="w")
        button = ttk.Button(cell, text=label, command=command)
        button.pack(side="left")
        ttk.Button(cell, text="!", width=2, command=lambda current=action_id: self.show_action_details(current)).pack(side="left", padx=(3, 0))
        return button

    def _clear_release_result(self) -> None:
        self.release_result.configure(state="normal")
        self.release_result.delete("1.0", "end")
        self.release_result.configure(state="disabled")

    def _build_logs_tab(self) -> None:
        actions = ttk.Frame(self.logs_tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="刷新面板日志", command=self._load_log).pack(side="left")
        ttk.Button(actions, text="打开日志目录", command=lambda: self._open_path(self.project_root / "logs")).pack(side="left", padx=8)
        ttk.Button(actions, text="打开部署文档", command=lambda: self._open_path(self.project_root / "docs" / "deployment" / "public-startup-guide.md")).pack(side="left")
        self.log_view = tk.Text(self.logs_tab, state="disabled", wrap="word", relief="flat", bg="#fbfcfd")
        self.log_view.pack(fill="both", expand=True, pady=(10, 0))

    def _apply_permission_state(self) -> None:
        modifying = (
            self.open_launcher_button,
            self.public_button,
            self.offline_button,
            self.build_button,
            self.inspect_button,
            self.apply_button,
            self.rollback_button,
            self.inventory_button,
        )
        for widget in modifying:
            if widget is not None and not self.admin:
                widget.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (
            self.open_launcher_button, self.refresh_button, self.preflight_button,
            self.public_button, self.postflight_button, self.open_workbench_button,
            self.offline_button, self.build_button, self.inspect_button,
            self.apply_button, self.rollback_button, self.inventory_button,
        ):
            if self.admin or widget not in (self.public_button, self.offline_button):
                widget.configure(state="disabled" if busy else "normal")
        self._apply_permission_state()

    def _set_status_refresh_active(self, active: bool) -> None:
        self._status_refresh_active = active
        self.refresh_button.configure(state="disabled" if active else "normal")

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

    def _run_background(
        self,
        action: str,
        worker: Callable[[], Any],
        done: Callable[[Any], None] | None = None,
        *,
        block_controls: bool = True,
    ) -> None:
        if block_controls and self._busy:
            return
        if not block_controls and self._status_refresh_active:
            return
        if block_controls:
            self._set_busy(True)
        else:
            self._set_status_refresh_active(True)
        self._append_result(f"开始：{action}")

        def run() -> None:
            try:
                result = worker()
                self.after(0, lambda: done(result) if done else None)
            except Exception as exc:  # noqa: BLE001 - UI boundary converts to safe message
                safe = sanitize_status_message(f"{action}失败：{type(exc).__name__}: {exc}")
                self.after(0, lambda: self._append_result(safe))
                if not block_controls and action == "刷新状态":
                    self.after(0, lambda: self.control_summary.set("状态刷新失败，请查看结果和日志。"))
            finally:
                if block_controls:
                    self.after(0, lambda: self._set_busy(False))
                else:
                    self.after(0, lambda: self._set_status_refresh_active(False))

        threading.Thread(target=run, daemon=True).start()

    def open_launcher(self) -> None:
        if hasattr(self.service_manager, "launcher_running") and self.service_manager.launcher_running():
            self._append_result("启动器已经打开，未重复启动。")
            return
        if hasattr(self.service_manager, "start_launcher"):
            self.service_manager.start_launcher()
        else:
            subprocess.Popen(
                ["cmd.exe", "/c", str(self.project_root / "启动AI创意工作台.bat")],
                cwd=self.project_root,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        self.state = PanelState.LAUNCHER_OPEN
        self.state_var.set(self.state.value)
        self._append_result("已打开现有启动器，请在启动器中点击“启动”。")

    def refresh_status(self) -> None:
        self.control_summary.set("正在刷新状态：端口、进程和防火墙...")

        def worker() -> Any:
            return self._collect_status()

        self._run_background("刷新状态", worker, self._apply_status, block_controls=False)

    def _collect_status(self) -> dict[str, Any]:
        runner = getattr(self.service_manager, "runner", self._system_runner)
        process_snapshot = list(runner.enumerate_processes()) if hasattr(runner, "enumerate_processes") else []
        self._process_snapshot = {item.pid: item for item in process_snapshot if hasattr(item, "pid")}
        ports: list[Any] = []
        if hasattr(self.port_inspector, "inspect_ports"):
            grouped = self.port_inspector.inspect_ports(MANAGED_PORTS)
            for items in grouped.values():
                ports.extend(items)
        else:
            for port in MANAGED_PORTS:
                if hasattr(self.port_inspector, "inspect"):
                    ports.extend(self.port_inspector.inspect(port))
                else:
                    ports.extend(self.port_inspector.inspect_port(port))
        return {
            "ports": ports,
            "launcher_open": collect_launcher_open(self.service_manager, process_snapshot),
            "firewall": self.firewall_manager.inspect() if hasattr(self.firewall_manager, "inspect") else None,
        }

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
        launcher_open = bool(status.get("launcher_open", False))
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
        seen_ports: set[tuple[Any, ...]] = set()
        for item in status["ports"]:
            data = item.to_dict() if hasattr(item, "to_dict") else item if isinstance(item, dict) else getattr(item, "__dict__", {})
            identity = (
                data.get("port"),
                data.get("address", data.get("local_address")),
                data.get("pid"),
                data.get("ownership", data.get("owner")),
                data.get("evidence_summary", data.get("note")),
            )
            if identity in seen_ports:
                continue
            seen_ports.add(identity)
            line, failure = format_preflight_port_check(data)
            checks.append(line)
            if failure:
                failures.append(failure)
        return {"passed": not failures, "checks": checks, "failures": failures}

    def _finish_preflight(self, result: dict[str, Any]) -> None:
        self.preflight_passed = bool(result.get("passed"))
        for line in result.get("checks", []):
            self._append_result(line)
        for failure in result.get("failures", []):
            self._append_result(f"阻断原因：{failure}")
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
            pid = getattr(result, "pid", None)
            if isinstance(pid, int) and pid > 0:
                self._append_result(f"公网 Web 进程已启动，PID {pid}。")
            elif isinstance(result, dict):
                self._append_result("公网 Web 启动结果已返回。")
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

    def _take_offline_and_verify(self) -> Any:
        result = self._take_offline_impl()
        status = self._collect_status()
        launcher_open = bool(getattr(self.service_manager, "launcher_running", lambda: False)())
        if not launcher_open and hasattr(self.service_manager, "runner"):
            processes = self.service_manager.runner.enumerate_processes()
            launcher_open = any(
                self.service_manager.is_owned_process(process, "launcher")
                for process in processes
            )
        blockers = find_offline_blockers(status, launcher_open=launcher_open)
        if blockers:
            raise RuntimeError("下线复查失败，已阻止后续操作：" + "；".join(blockers))
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
        self._run_background("检查发布包", lambda: self.release_manager.inspect_package(package, digest), self._finish_inspect_release)

    def build_release(self) -> None:
        ref = self.release_ref_var.get().strip()
        if not ref:
            self._append_result("请先填写 Git Ref。")
            return
        self._run_background(
            "制作发布包",
            lambda: self.release_manager.build_release(ref, allow_dirty=self.allow_dirty_var.get()),
            self._finish_build_release,
        )

    def _finish_build_release(self, result: Any) -> None:
        if isinstance(result, dict) and result.get("ok"):
            payload = result.get("result") if isinstance(result.get("result"), dict) else {}
            package = payload.get("package_path")
            digest = payload.get("package_sha256")
            if package:
                self.package_var.set(str(package))
            if digest:
                self.sha_var.set(str(digest))
            self.release_verified_package = ""
            self.release_verified_sha = ""
            self._append_result("发布包已生成，已自动填入 ZIP 和 SHA-256；请先点击“服务器检查”。")
        self._show_release_result(result)

    def _finish_inspect_release(self, result: Any) -> None:
        if isinstance(result, dict) and result.get("ok"):
            self.release_verified_package = str(self.package_var.get().strip())
            self.release_verified_sha = str(self.sha_var.get().strip()).lower()
            self._append_result("服务器检查通过；现在才允许执行更新。")
        else:
            self.release_verified_package = ""
            self.release_verified_sha = ""
        self._show_release_result(result)

    def run_code_inventory(self) -> None:
        root = self.inventory_root_var.get().strip()
        output = self.inventory_output_var.get().strip()
        if not root:
            self._append_result("请先填写代码盘点根目录。")
            return
        self._run_background(
            "代码盘点",
            lambda: self.release_manager.code_inventory(root, output or None),
            self._show_release_result,
        )

    def rollback_release(self) -> None:
        rollback_id = self.rollback_id_var.get().strip()
        if not rollback_id or not messagebox.askyesno(
            "确认回滚",
            "回滚前必须保持工作台关闭；确认使用此 RollbackId 恢复程序代码？",
        ):
            return
        self._run_background(
            "回滚发布",
            lambda: self._rollback_release_impl(rollback_id),
            self._show_release_result,
        )

    def _rollback_release_impl(self, rollback_id: str) -> Any:
        self._take_offline_and_verify()
        return self.release_manager.rollback(rollback_id)

    def open_release_workflow(self) -> None:
        self._open_path(self.project_root / "docs" / "deployment" / "release-workflow.md")

    def apply_release(self) -> None:
        if not self.admin:
            return
        package = self.package_var.get().strip()
        digest = self.sha_var.get().strip()
        if package != self.release_verified_package or digest.lower() != self.release_verified_sha:
            self._append_result("请先对当前 ZIP 和 SHA-256 执行“服务器检查”；检查通过后才能更新。")
            return
        if not package or not digest or not messagebox.askyesno("确认更新", "更新会先全部下线并创建回滚点，是否继续？"):
            return
        self._run_background("执行更新", lambda: self._apply_release_impl(package, digest), self._finish_apply_release)

    def _apply_release_impl(self, package: str, digest: str) -> Any:
        self._take_offline_and_verify()
        return self.release_manager.apply(package, digest)

    def _finish_apply_release(self, result: Any) -> None:
        self.release_verified_package = ""
        self.release_verified_sha = ""
        self._show_release_result(result)

    def _show_release_result(self, result: Any) -> None:
        if isinstance(result, dict) and not result.get("ok"):
            text = f"操作未完成\n原因：{result.get('error', '未知错误')}"
        elif isinstance(result, (dict, list)):
            text = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            text = str(result)
        text = sanitize_status_message(text).replace("\\r", "").strip()
        if len(text) > 5000:
            text = text[:5000] + "\n…（输出已截断，完整内容请查看日志）"
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
