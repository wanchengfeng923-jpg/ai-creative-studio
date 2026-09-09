"""Shared data models for the deployment control panel."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class CheckLevel(str, Enum):
    """Severity of a diagnostic result."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    """One structured diagnostic result safe to show in the panel."""

    check_id: str
    level: CheckLevel
    summary: str
    evidence: dict[str, Any]
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        value = asdict(self)
        value["level"] = self.level.value
        return value


@dataclass(frozen=True)
class PortListener:
    """A point-in-time listener record obtained from the operating system."""

    port: int
    address: str
    pid: int
    process_name: str = ""
    executable: str = ""
    command_line: str = ""
    working_directory: str = ""
    create_time: float | None = None


@dataclass(frozen=True)
class ProcessInfo:
    """Process evidence queried again immediately before management actions."""

    pid: int
    process_name: str
    executable: str = ""
    command_line: str = ""
    working_directory: str = ""
    create_time: float | None = None


@dataclass(frozen=True)
class PortInspection:
    """Listener plus the project-ownership decision derived from its evidence."""

    listener: PortListener
    ownership: str
    evidence_summary: str
    is_manageable: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {
            "port": self.listener.port,
            "address": self.listener.address,
            "pid": self.listener.pid,
            "process_name": self.listener.process_name,
            "executable": self.listener.executable,
            "ownership": self.ownership,
            "evidence_summary": self.evidence_summary,
            "is_manageable": self.is_manageable,
        }
