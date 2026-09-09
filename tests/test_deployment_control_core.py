from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from deployment_control.health_checker import HealthChecker
from deployment_control.models import CheckLevel, CheckResult, PortListener, ProcessInfo
from deployment_control.operation_log import OperationLogger, sanitize_sensitive
from deployment_control.port_inspector import PortInspector, ProcessOwnership
from deployment_control.port_inspector import _read_netstat_listeners

from unittest.mock import patch


class DeploymentControlCoreTests(unittest.TestCase):
    def test_check_result_is_structured_and_serializable(self) -> None:
        result = CheckResult(
            check_id="web_local",
            level=CheckLevel.PASS,
            summary="Web 已就绪",
            evidence={"port": 8775, "address": "127.0.0.1"},
            recommendation="可以继续",
        )

        self.assertEqual(result.to_dict()["level"], "pass")
        self.assertEqual(result.to_dict()["evidence"]["port"], 8775)

    def test_port_inspector_classifies_expected_project_process(self) -> None:
        listener = PortListener(
            port=8775,
            address="127.0.0.1",
            pid=321,
            process_name="python.exe",
            executable=r"D:\code\ai_creative_studio\.venv\Scripts\python.exe",
            command_line="python -m creative_studio.app",
            working_directory=r"D:\code\ai_creative_studio",
            create_time=10.0,
        )
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=lambda pid: ProcessInfo(
                pid=pid,
                process_name="python.exe",
                executable=listener.executable,
                command_line=listener.command_line,
                working_directory=listener.working_directory,
                create_time=10.0,
            ),
            project_root=r"D:\code\ai_creative_studio",
        )

        inspection = inspector.inspect(8775)[0]

        self.assertEqual(inspection.ownership, ProcessOwnership.PROJECT)
        self.assertTrue(inspection.is_manageable)

    def test_port_inspector_rejects_unknown_process_even_on_project_port(self) -> None:
        listener = PortListener(
            port=8775,
            address="0.0.0.0",
            pid=999,
            process_name="python.exe",
            executable=r"C:\Python311\python.exe",
            command_line="python -m unrelated_service",
            working_directory=r"C:\other",
            create_time=20.0,
        )
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=lambda pid: None,
            project_root=r"D:\code\ai_creative_studio",
        )

        inspection = inspector.inspect(8775)[0]

        self.assertEqual(inspection.ownership, ProcessOwnership.UNKNOWN)
        self.assertFalse(inspection.is_manageable)

    def test_port_inspector_detects_pid_reuse_when_process_evidence_differs(self) -> None:
        listener = PortListener(
            port=8780,
            address="127.0.0.1",
            pid=12,
            process_name="python.exe",
            executable=r"D:\code\ai_creative_studio\.venv\Scripts\python.exe",
            command_line="python chat2api/main.py",
            working_directory=r"D:\code\ai_creative_studio",
            create_time=100.0,
        )
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=lambda pid: ProcessInfo(
                pid=pid,
                process_name="python.exe",
                executable=listener.executable,
                command_line=listener.command_line,
                working_directory=listener.working_directory,
                create_time=101.0,
            ),
            project_root=r"D:\code\ai_creative_studio",
        )

        inspection = inspector.inspect(8780)[0]

        self.assertEqual(inspection.ownership, ProcessOwnership.UNKNOWN)
        self.assertIn("创建时间", inspection.evidence_summary)

    def test_port_inspector_accepts_windows_entry_path_separator(self) -> None:
        listener = PortListener(
            port=8780,
            address="127.0.0.1",
            pid=13,
            process_name="python.exe",
            executable=r"D:\code\ai_creative_studio\.venv\Scripts\python.exe",
            command_line=r"python chat2api\main.py",
            working_directory=r"D:\code\ai_creative_studio",
            create_time=10.0,
        )
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=lambda pid: ProcessInfo(
                pid=pid,
                process_name=listener.process_name,
                executable=listener.executable,
                command_line=listener.command_line,
                working_directory=listener.working_directory,
                create_time=listener.create_time,
            ),
            project_root=r"D:\code\ai_creative_studio",
        )

        self.assertTrue(inspector.inspect(8780)[0].is_manageable)

    def test_system_python_web_child_of_project_launcher_is_manageable(self) -> None:
        root = Path(r"E:\AI-Creative-Studio")
        listener = PortListener(port=8775, address="127.0.0.1", pid=20)
        processes = {
            10: ProcessInfo(10, "pythonw.exe", r"C:\Python311\pythonw.exe", f'pythonw.exe "{root / "launcher.py"}"'),
            20: ProcessInfo(20, "python.exe", r"C:\Python311\python.exe", "python.exe -m creative_studio.app", parent_pid=10),
        }
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=processes.get,
            project_root=root,
        )

        self.assertTrue(inspector.inspect(8775)[0].is_manageable)

    def test_system_python_gateway_child_of_project_launcher_is_manageable(self) -> None:
        root = Path(r"E:\AI-Creative-Studio")
        listener = PortListener(port=8780, address="127.0.0.1", pid=30)
        processes = {
            10: ProcessInfo(10, "pythonw.exe", r"C:\Python311\pythonw.exe", f'pythonw.exe "{root / "launcher.py"}"'),
            30: ProcessInfo(30, "python.exe", r"C:\Python311\python.exe", "python.exe main.py", parent_pid=10),
        }
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=processes.get,
            project_root=root,
        )

        self.assertTrue(inspector.inspect(8780)[0].is_manageable)

    def test_project_launcher_can_own_in_process_proxy_bridge(self) -> None:
        root = Path(r"E:\AI-Creative-Studio")
        listener = PortListener(port=7896, address="127.0.0.1", pid=10)
        launcher = ProcessInfo(10, "pythonw.exe", r"C:\Python311\pythonw.exe", f'pythonw.exe "{root / "launcher.py"}"')
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=lambda _pid: launcher,
            project_root=root,
        )

        self.assertTrue(inspector.inspect(7896)[0].is_manageable)

    def test_system_python_without_project_controller_remains_unknown(self) -> None:
        listener = PortListener(port=8775, address="127.0.0.1", pid=40)
        process = ProcessInfo(40, "python.exe", r"C:\Python311\python.exe", "python.exe -m creative_studio.app")
        inspector = PortInspector(
            listeners_provider=lambda: [listener],
            process_provider=lambda _pid: process,
            project_root=Path(r"E:\AI-Creative-Studio"),
        )

        self.assertFalse(inspector.inspect(8775)[0].is_manageable)

    def test_netstat_timeout_returns_without_blocking_status_refresh(self) -> None:
        with patch("deployment_control.port_inspector.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("netstat", 5)):
            self.assertEqual([], _read_netstat_listeners())

    def test_health_checker_checks_local_gateway_and_public_url_with_injected_opener(self) -> None:
        requested: list[str] = []

        class Response:
            status = 200

            def read(self) -> bytes:
                return b'{"status":"ok"}'

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *args: object) -> None:
                return None

        def opener(url: str, timeout: float) -> Response:
            requested.append(url)
            return Response()

        results = HealthChecker(
            web_url="http://127.0.0.1:8775/api/health",
            gateway_url="http://127.0.0.1:8780/health",
            public_url="http://example.test:8775/api/health",
            opener=opener,
        ).check_all()

        self.assertEqual([result.level for result in results], [CheckLevel.PASS] * 3)
        self.assertEqual(
            requested,
            [
                "http://127.0.0.1:8775/api/health",
                "http://127.0.0.1:8780/health",
                "http://example.test:8775/api/health",
            ],
        )

    def test_health_checker_reports_connection_failure_without_request_content(self) -> None:
        def opener(url: str, timeout: float) -> object:
            raise OSError("Authorization: Bearer super-secret-token")

        result = HealthChecker(
            web_url="http://127.0.0.1:8775/api/health",
            gateway_url="http://127.0.0.1:8780/health",
            public_url=None,
            opener=opener,
        ).check_local_web()

        self.assertEqual(result.level, CheckLevel.FAIL)
        self.assertNotIn("super-secret-token", result.summary)
        self.assertNotIn("Authorization", str(result.evidence))

    def test_sanitize_sensitive_removes_secret_headers_and_proxy_credentials(self) -> None:
        value = {
            "token": "abc123",
            "Cookie": "session=xyz",
            "password": "pw",
            "Authorization": "Bearer header-secret",
            "proxy": "http://user:pass@example.test:7896",
            "nested": ["safe", "api_key=key-secret"],
        }

        sanitized = sanitize_sensitive(value)
        rendered = json.dumps(sanitized, ensure_ascii=False)

        for secret in ("abc123", "session=xyz", "pw", "header-secret", "user:pass", "key-secret"):
            self.assertNotIn(secret, rendered)
        self.assertEqual(sanitized["token"], "[REDACTED]")

    def test_sanitize_sensitive_redacts_inline_authorization_and_cookie_headers(self) -> None:
        sanitized = sanitize_sensitive(
            ["Authorization: Bearer inline-secret", "Cookie: session=inline-cookie"]
        )

        rendered = json.dumps(sanitized)
        self.assertNotIn("inline-secret", rendered)
        self.assertNotIn("inline-cookie", rendered)

    def test_operation_logger_writes_json_lines_with_timestamp_and_sanitized_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment-panel.log"
            logger = OperationLogger(
                path,
                clock=lambda: datetime(2026, 9, 9, 1, 2, 3, tzinfo=timezone.utc),
            )
            logger.record(
                action="health_check",
                result="fail",
                details={"Authorization": "Bearer secret", "port": 8775},
            )

            line = path.read_text(encoding="utf-8").strip()
            entry = json.loads(line)

        self.assertEqual(entry["action"], "health_check")
        self.assertEqual(entry["result"], "fail")
        self.assertEqual(entry["timestamp"], "2026-09-09T01:02:03+00:00")
        self.assertEqual(entry["details"]["Authorization"], "[REDACTED]")
        self.assertEqual(entry["details"]["port"], 8775)


if __name__ == "__main__":
    unittest.main()
