"""Safe adapter around the project's PowerShell release script."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

_PROTECTED_COMPONENTS = {
    ".env",
    ".venv",
    ".scratch",
    "data",
    "images",
    "uploads",
    "logs",
    "staging",
    "private",
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_SENSITIVE_FIELD = re.compile(
    r"(?i)\b(token|access_token|refresh_token|cookie|password|authorization|proxy_password)"
    r"\s*([:=])\s*(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_URL = re.compile(r"(?i)\b(?:https?|socks5?)://[^\s\"'<>]+")


class ReleaseManager:
    """Expose release inspection, application, and rollback as safe operations."""

    def __init__(
        self,
        *,
        script_path: str | Path | None = None,
        build_script_path: str | Path | None = None,
        inventory_script_path: str | Path | None = None,
        project_root: str | Path | None = None,
        install_root: str | Path = r"E:\AI-Creative-Studio",
        runner: CommandRunner | None = None,
        powershell: str = "powershell.exe",
    ) -> None:
        resolved_project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
        self.project_root = resolved_project_root.resolve()
        self.script_path = Path(script_path) if script_path else self.project_root / "scripts" / "server_release.ps1"
        self.build_script_path = Path(build_script_path) if build_script_path else self.project_root / "scripts" / "build_release.ps1"
        self.inventory_script_path = Path(inventory_script_path) if inventory_script_path else self.project_root / "scripts" / "code_inventory.ps1"
        self.install_root = Path(install_root)
        self._runner = runner or subprocess.run
        self._powershell = powershell

    def inspect_package(self, package_path: str | Path, sha256: str) -> dict[str, Any]:
        """Validate a package through ``server_release.ps1 -Mode Inspect``."""
        return self._run_release("inspect", package_path, sha256)

    def apply(self, package_path: str | Path, sha256: str) -> dict[str, Any]:
        """Apply a validated package through ``server_release.ps1 -Mode Apply``."""
        return self._run_release("apply", package_path, sha256)

    def build_release(self, ref: str = "HEAD", output_directory: str = ".release", allow_dirty: bool = False) -> dict[str, Any]:
        """Run the developer-side isolated release builder."""
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", ref or "") or any(part == ".." for part in Path(ref).parts):
            return {"ok": False, "operation": "build", "error": "Invalid Git ref."}
        if not output_directory or any(part == ".." for part in Path(output_directory).parts):
            return {"ok": False, "operation": "build", "error": "Invalid output directory."}
        arguments = ["-Ref", ref, "-OutputDirectory", output_directory]
        if allow_dirty:
            arguments.append("-AllowDirty")
        return self._run_local_script("build", self.build_script_path, arguments)

    def code_inventory(self, root: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
        """Run the canonical code inventory script for a local/server path."""
        root_path = Path(root)
        if any(part == ".." for part in root_path.parts):
            return {"ok": False, "operation": "inventory", "error": "Invalid inventory root."}
        arguments = ["-Root", str(root_path)]
        if output_path is not None:
            output = Path(output_path)
            if any(part == ".." for part in output.parts):
                return {"ok": False, "operation": "inventory", "error": "Invalid inventory output path."}
            arguments.extend(["-OutputPath", str(output)])
        return self._run_local_script("inventory", self.inventory_script_path, arguments)

    def list_valid_rollbacks(self) -> dict[str, Any]:
        """Return only rollback directories with valid, safe manifests."""
        rollback_root = self.install_root / "staging" / "rollbacks"
        rollbacks: list[dict[str, Any]] = []
        if not rollback_root.is_dir():
            return {"ok": True, "rollbacks": []}

        for entry in sorted(rollback_root.iterdir(), key=lambda item: item.name):
            if (
                not entry.is_dir()
                or not _SAFE_ID.fullmatch(entry.name)
                or entry.name.lower() in _PROTECTED_COMPONENTS
            ):
                continue
            try:
                manifest = self._read_rollback_manifest(entry)
            except (OSError, ValueError, TypeError):
                continue
            rollbacks.append(
                {
                    "rollback_id": entry.name,
                    "target_release_id": manifest["target_release_id"],
                    "created_at": manifest["created_at"],
                    "backed_up_file_count": len(manifest["backed_up_files"]),
                    "created_file_count": len(manifest["created_files"]),
                }
            )
        return {"ok": True, "rollbacks": rollbacks}

    def rollback(self, rollback_id: str) -> dict[str, Any]:
        """Restore a previously recorded rollback point."""
        if not isinstance(rollback_id, str) or not _SAFE_ID.fullmatch(rollback_id):
            return {"ok": False, "operation": "rollback", "error": "Invalid rollback id."}
        if any(part.lower() in _PROTECTED_COMPONENTS for part in Path(rollback_id).parts):
            return {"ok": False, "operation": "rollback", "error": "Protected rollback id."}
        return self._run_script(
            "rollback",
            [
                "-Mode",
                "Rollback",
                "-RollbackId",
                rollback_id,
            ],
        )

    def _run_release(
        self,
        operation: str,
        package_path: str | Path,
        sha256: str,
    ) -> dict[str, Any]:
        try:
            package = self._validate_package(package_path)
        except ValueError as exc:
            return {"ok": False, "operation": operation, "error": str(exc)}
        if not _SHA256.fullmatch(sha256 or ""):
            return {
                "ok": False,
                "operation": operation,
                "error": "Expected SHA-256 must contain exactly 64 hexadecimal characters.",
            }
        mode = "Inspect" if operation == "inspect" else "Apply"
        return self._run_script(
            operation,
            [
                "-Mode",
                mode,
                "-PackagePath",
                str(package),
                "-ExpectedSHA256",
                sha256.lower(),
            ],
        )

    def _run_script(self, operation: str, arguments: Sequence[str]) -> dict[str, Any]:
        command_text = (
            "$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
            f"& {_quote_ps(str(self.script_path))} "
            f"{' '.join(argument if argument.startswith('-') else _quote_ps(argument) for argument in arguments)} "
            f"-InstallRoot {_quote_ps(str(self.install_root))} | ConvertTo-Json -Depth 8"
        )
        command = [
            self._powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command_text,
        ]
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return {
                "ok": False,
                "operation": operation,
                "error": "Unable to start the PowerShell release script.",
            }

        raw_stdout = completed.stdout or ""
        stdout = _sanitize(raw_stdout)
        stderr = _sanitize(completed.stderr or "")
        if completed.returncode != 0:
            return {
                "ok": False,
                "operation": operation,
                "error": stderr or stdout or "Release script failed.",
            }
        return {
            "ok": True,
            "operation": operation,
            "result": _parse_output(raw_stdout),
        }

    def _run_local_script(self, operation: str, script_path: Path, arguments: Sequence[str]) -> dict[str, Any]:
        command_text = (
            "$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
            f"& {_quote_ps(str(script_path))} "
            f"{' '.join(_quote_ps(argument) if not argument.startswith('-') else argument for argument in arguments)} "
            "| ConvertTo-Json -Depth 8"
        )
        command = [self._powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command_text]
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.project_root),
            )
        except OSError:
            return {"ok": False, "operation": operation, "error": "Unable to start the PowerShell script."}
        stdout = _sanitize(completed.stdout or "")
        stderr = _sanitize(completed.stderr or "")
        if completed.returncode != 0:
            return {"ok": False, "operation": operation, "error": stderr or stdout or "PowerShell script failed."}
        return {"ok": True, "operation": operation, "result": _parse_output(completed.stdout or "")}

    def _validate_package(self, package_path: str | Path) -> Path:
        package = Path(package_path)
        if any(part.lower() in _PROTECTED_COMPONENTS for part in package.parts):
            raise ValueError("Package path is inside a protected directory.")
        if not package.is_file():
            raise ValueError("Release package was not found.")
        return package.resolve()

    @staticmethod
    def _read_rollback_manifest(entry: Path) -> Mapping[str, Any]:
        manifest_path = entry / "rollback-manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Rollback manifest must be an object.")
        if payload.get("schema_version") != "creative-studio-rollback.v1":
            raise ValueError("Unsupported rollback manifest.")
        if payload.get("rollback_id") != entry.name:
            raise ValueError("Rollback id mismatch.")
        for field in ("target_release_id", "created_at"):
            if not isinstance(payload.get(field), str) or not payload[field]:
                raise ValueError("Rollback manifest identity is invalid.")
        for field in ("backed_up_files", "created_files"):
            values = payload.get(field)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and _safe_relative_path(value) for value in values
            ):
                raise ValueError("Rollback manifest contains an unsafe path.")
        return payload


def _safe_relative_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    if (
        not normalized
        or normalized != value.replace("\\", "/")
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or re.search(r"(^|/)\.\.(/|$)", normalized)
    ):
        return False
    return not any(
        component.lower() in _PROTECTED_COMPONENTS for component in normalized.split("/")
    )


def _parse_output(stdout: str) -> Any:
    if not stdout.strip():
        return {}
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {"output": stdout}
    return _normalise_keys(_redact_value(parsed))


def _normalise_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {_snake_case(str(key)): _normalise_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalise_keys(item) for item in value]
    return value


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize(value)
    return value


def _sanitize(value: str) -> str:
    value = _URL.sub("[REDACTED_URL]", value)
    return _SENSITIVE_FIELD.sub(r"\1\2[REDACTED]", value)


def _snake_case(value: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()


def _quote_ps(value: str) -> str:
    """Quote a literal for PowerShell without interpreting path characters."""
    return "'" + value.replace("'", "''") + "'"
