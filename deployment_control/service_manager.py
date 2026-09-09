"""受控管理 AI 创意工作台的本地服务进程。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence


WEB_PORT = 8775
GATEWAY_PORT = 8780
BRIDGE_PORT = 7896
DEFAULT_WAIT_SECONDS = 5.0


@dataclass(frozen=True)
class ProcessRecord:
    """进程枚举所需的非敏感证据。"""

    pid: int
    executable: str
    command_line: str
    cwd: str
    create_time: float | None = None
    parent_pid: int | None = None


@dataclass(frozen=True)
class PortBinding:
    """监听端口及其 PID。"""

    port: int
    host: str
    pid: int


class ServiceConflictError(RuntimeError):
    """端口被未知进程占用，面板不得继续管理该端口。"""


class ProcessRunner(Protocol):
    """服务管理所需的可替换系统边界。"""

    def enumerate_processes(self) -> Iterable[ProcessRecord]:
        ...

    def launch(
        self, command: Sequence[str], cwd: Path, env: Mapping[str, str]
    ) -> Any:
        ...

    def terminate(self, pid: int) -> None:
        ...

    def send_launcher_close(self, pid: int) -> None:
        ...

    def wait_for_exit(self, pid: int, timeout: float) -> bool:
        ...


class PortInspector(Protocol):
    def inspect(self, port: int) -> Iterable[PortBinding]:
        ...


class ServiceManager:
    """启动、切换和停止项目服务，永不处理未知进程。"""

    def __init__(
        self,
        project_root: str | Path,
        runner: ProcessRunner,
        port_inspector: PortInspector,
        *,
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.runner = runner
        self.port_inspector = port_inspector
        self.wait_seconds = wait_seconds

    def is_owned_process(self, process: ProcessRecord, role: str) -> bool:
        """根据多项证据判断进程是否由当前项目启动。"""
        if process.pid <= 0:
            return False
        root = _normalise_path(self.project_root)
        cwd = _normalise_path(process.cwd)
        executable = _normalise_path(process.executable)
        command = _normalise_text(process.command_line)
        venv = _normalise_path(self.project_root / ".venv")
        executable_name = Path(process.executable).name.lower()
        is_python = executable_name in {"python.exe", "pythonw.exe", "python", "pythonw"}
        parent = self._process_by_pid(process.parent_pid) if process.parent_pid else None
        controlled_by_project = parent is not None and self._is_project_controller(parent)

        if role == "launcher":
            return self._is_project_controller(process, entry="launcher.py")
        if role == "web":
            return (
                is_python
                and "creative_studio.app" in command
                and ((cwd == root and _path_is_within(executable, venv)) or controlled_by_project)
            )
        if role == "gateway":
            return (
                is_python
                and "main.py" in command
                and (
                    (cwd == _normalise_path(self.project_root / "chat2api") and _path_is_within(executable, venv))
                    or controlled_by_project
                )
            )
        if role == "bridge":
            bridge_config = _normalise_path(self.project_root / ".runtime" / "proxy-bridge.yaml")
            return self._is_project_controller(process, entry="launcher.py") or (
                "mihomo" in command
                and bridge_config in command
                and (
                    cwd == _normalise_path(self.project_root / ".runtime")
                    or bridge_config in command
                )
            )
        return False

    def _is_project_controller(self, process: ProcessRecord, *, entry: str | None = None) -> bool:
        executable_name = Path(process.executable).name.lower()
        if executable_name not in {"python.exe", "pythonw.exe", "python", "pythonw"}:
            return False
        command = _normalise_text(process.command_line)
        entries = (entry,) if entry else ("launcher.py", "deployment_panel.py")
        if any(_normalise_path(self.project_root / name) in command for name in entries):
            return True
        executable = _normalise_path(process.executable)
        cwd = _normalise_path(process.cwd)
        venv = _normalise_path(self.project_root / ".venv")
        return cwd == _normalise_path(self.project_root) and _path_is_within(executable, venv) and any(name in command for name in entries)

    def switch_web_to_public(self, environment: Mapping[str, str]) -> Any:
        """重启已确认的本地 Web，并只改变其监听主机。"""
        binding = self._single_binding(WEB_PORT)
        if binding is not None:
            process = self._process_by_pid(binding.pid)
            if process is None or not self.is_owned_process(process, "web"):
                raise ServiceConflictError(
                    f"{WEB_PORT} 已被未知进程占用，拒绝切换公网监听"
                )
            self._stop_owned(process, "web")

        env = dict(environment)
        env["CREATIVE_STUDIO_HOST"] = "0.0.0.0"
        env.setdefault("CREATIVE_STUDIO_PORT", str(WEB_PORT))
        python_executable = self.project_root / ".venv" / "Scripts" / "python.exe"
        command = (str(python_executable), "-m", "creative_studio.app")
        return self.runner.launch(command, self.project_root, env)

    def start_launcher(self, batch_path: str | Path | None = None) -> Any | None:
        """打开现有启动器；已存在项目启动器时不重复打开。"""
        for process in self.runner.enumerate_processes():
            if self.is_owned_process(process, "launcher"):
                return None
        path = Path(batch_path) if batch_path else self.project_root / "启动AI创意工作台.bat"
        launch_batch = getattr(self.runner, "launch_batch", None)
        if launch_batch is None:
            raise RuntimeError("进程 runner 未提供启动器接口")
        return launch_batch(path, self.project_root)

    def shutdown(self, firewall_manager: Any | None = None) -> None:
        """按 Web、防火墙、启动器、网关、代理桥顺序完整下线。"""
        self._stop_port_if_owned(WEB_PORT, "web")
        if firewall_manager is not None:
            firewall_manager.disable()

        launcher = self._owned_process_for_role("launcher")
        if launcher is not None:
            self.runner.send_launcher_close(launcher.pid)
            self.runner.wait_for_exit(launcher.pid, self.wait_seconds)

        for port, role in ((GATEWAY_PORT, "gateway"), (BRIDGE_PORT, "bridge")):
            self._stop_port_if_owned(port, role)

    def _stop_port_if_owned(self, port: int, role: str) -> bool:
        binding = self._single_binding(port)
        if binding is None:
            return False
        process = self._process_by_pid(binding.pid)
        if process is None or not self.is_owned_process(process, role):
            return False
        self._stop_owned(process, role)
        return True

    def _stop_owned(self, process: ProcessRecord, role: str) -> None:
        # Re-enumerate immediately before termination so stale/PID-reused records
        # cannot cause an unrelated process to be ended.
        current = self._process_by_pid(process.pid)
        if current is None or not self.is_owned_process(current, role):
            raise ServiceConflictError(f"PID {process.pid} 的归属证据已失效")
        self.runner.terminate(current.pid)
        self.runner.wait_for_exit(current.pid, self.wait_seconds)

    def _single_binding(self, port: int) -> PortBinding | None:
        bindings = list(self.port_inspector.inspect(port))
        if not bindings:
            return None
        if len(bindings) > 1:
            raise ServiceConflictError(f"{port} 存在多个监听占用，拒绝管理")
        return bindings[0]

    def _process_by_pid(self, pid: int) -> ProcessRecord | None:
        return next(
            (process for process in self.runner.enumerate_processes() if process.pid == pid),
            None,
        )

    def _owned_process_for_role(self, role: str) -> ProcessRecord | None:
        return next(
            (
                process
                for process in self.runner.enumerate_processes()
                if self.is_owned_process(process, role)
            ),
            None,
        )


def _normalise_path(value: str | Path) -> str:
    if not str(value):
        return ""
    return os.path.normcase(str(Path(value).resolve())).replace("\\", "/").rstrip("/")


def _normalise_text(value: str) -> str:
    return value.replace("\\", "/").lower()


def _path_is_within(path: str, root: str) -> bool:
    """Match a path component boundary, avoiding ``.venv-evil`` collisions."""
    return path == root or path.startswith(root + "/")


def _contains_path(command: str, path: str | Path) -> bool:
    return _normalise_path(path) in command
