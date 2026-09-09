"""Read-only port and process evidence inspection."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterable
from enum import Enum
from pathlib import Path

from .models import PortInspection, PortListener, ProcessInfo


class ProcessOwnership(str, Enum):
    """Conservative ownership states used before a process can be managed."""

    PROJECT = "project"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"


ListenersProvider = Callable[[], Iterable[PortListener]]
ProcessProvider = Callable[[int], ProcessInfo | None]


class PortInspector:
    """Inspect listeners without stopping processes or changing firewall state."""

    def __init__(
        self,
        *,
        listeners_provider: ListenersProvider | None = None,
        process_provider: ProcessProvider | None = None,
        project_root: str | Path,
    ) -> None:
        self._listeners_provider = listeners_provider or _read_netstat_listeners
        self._process_provider = process_provider or (lambda _pid: None)
        self.project_root = Path(project_root).resolve()

    def inspect(self, port: int) -> list[PortInspection]:
        """Return all current listeners for ``port`` and their ownership evidence."""
        return [
            self._inspect_listener(listener)
            for listener in self._listeners_provider()
            if listener.port == port
        ]

    def inspect_ports(self, ports: Iterable[int]) -> dict[int, list[PortInspection]]:
        """Inspect several ports from one provider snapshot."""
        listeners = list(self._listeners_provider())
        return {
            port: [
                self._inspect_listener(listener)
                for listener in listeners
                if listener.port == port
            ]
            for port in ports
        }

    def _inspect_listener(self, listener: PortListener) -> PortInspection:
        process = self._process_provider(listener.pid)
        ownership, evidence = self._classify(listener, process)
        return PortInspection(
            listener=listener,
            ownership=ownership.value,
            evidence_summary=evidence,
            is_manageable=ownership is ProcessOwnership.PROJECT,
        )

    def _classify(
        self,
        listener: PortListener,
        process: ProcessInfo | None,
    ) -> tuple[ProcessOwnership, str]:
        if process is None:
            return ProcessOwnership.UNKNOWN, "未能重新取得 PID 进程证据"
        if process.pid != listener.pid:
            return ProcessOwnership.UNKNOWN, "PID 证据不一致"
        if (
            listener.create_time is not None
            and process.create_time is not None
            and abs(listener.create_time - process.create_time) > 0.001
        ):
            return ProcessOwnership.UNKNOWN, "PID 创建时间不一致，可能已被复用"

        executable = _resolve_optional_path(process.executable)
        project_python = self.project_root / ".venv" / "Scripts" / "python.exe"
        executable_matches = executable == project_python
        working_directory_matches = _is_within(
            _resolve_optional_path(process.working_directory),
            self.project_root,
        )
        expected_entry = _expected_entry(listener.port)
        command_line = process.command_line.lower().replace("\\", "/")
        command_line_matches = expected_entry in command_line
        if executable_matches and working_directory_matches and command_line_matches:
            return ProcessOwnership.PROJECT, "虚拟环境、工作目录和入口命令均匹配"

        evidence = []
        if not executable_matches:
            evidence.append("可执行文件不匹配")
        if not working_directory_matches:
            evidence.append("工作目录不匹配")
        if not command_line_matches:
            evidence.append("入口命令不匹配")
        return ProcessOwnership.UNKNOWN, "；".join(evidence) or "证据不足"


def _expected_entry(port: int) -> str:
    if port == 8775:
        return "creative_studio.app"
    if port == 8780:
        return "chat2api/main.py"
    if port == 7896:
        return "proxy"
    return ""


def _resolve_optional_path(value: str) -> Path:
    return Path(value).resolve() if value else Path()


def _is_within(path: Path, root: Path) -> bool:
    if not path:
        return False
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_netstat_listeners() -> list[PortListener]:
    """Read TCP listeners without adding a dependency on a process library."""
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
        encoding="oem",
        errors="replace",
    )
    listeners: list[PortListener] = []
    pattern = re.compile(
        r"^\s*TCP\s+(?P<address>[^ ]+):(?P<port>\d+)\s+"
        r"[^ ]+\s+LISTENING\s+(?P<pid>\d+)\s*$",
        re.IGNORECASE,
    )
    for line in completed.stdout.splitlines():
        match = pattern.match(line)
        if match:
            listeners.append(
                PortListener(
                    port=int(match.group("port")),
                    address=match.group("address"),
                    pid=int(match.group("pid")),
                )
            )
    return listeners
