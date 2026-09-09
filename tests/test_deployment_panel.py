import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from subprocess import CompletedProcess

import deployment_panel
from deployment_panel import (
    ACTION_DETAILS,
    DeploymentPanel,
    PanelState,
    determine_panel_state,
    get_action_details,
    public_action_allowed,
    sanitize_status_message,
    format_preflight_port_check,
    find_offline_blockers,
    collect_launcher_open,
)


class DeploymentPanelStateTests(unittest.TestCase):
    def test_status_refresh_does_not_lock_controls_for_other_actions(self):
        panel = object.__new__(DeploymentPanel)
        panel._busy = False
        panel._status_refresh_active = False
        panel._set_busy = Mock()
        panel._append_result = Mock()
        panel.after = lambda _delay, callback: callback()

        panel._run_background("刷新状态", lambda: {"ok": True}, lambda _result: None, block_controls=False)

        panel._set_busy.assert_not_called()

    def test_process_scan_limits_wmi_to_relevant_process_names(self):
        completed = __import__("subprocess").CompletedProcess([], 0, "[]", "")
        with patch("deployment_panel.subprocess.run", return_value=completed) as run:
            deployment_panel._SystemProcessRunner(Path("D:/code/ai_creative_studio")).enumerate_processes()

        query = run.call_args.args[0][-1]
        self.assertIn("-Filter", query)
        self.assertIn("python.exe", query)

    def test_firewall_powershell_runs_without_creating_a_console_window(self):
        with patch(
            "deployment_panel.subprocess.run",
            return_value=CompletedProcess([], 0, "", ""),
        ) as run:
            deployment_panel._SystemFirewallRunner()._run("Get-NetFirewallRule")

        kwargs = run.call_args.kwargs
        command = run.call_args.args[0]
        self.assertIn("-NonInteractive", command)
        self.assertEqual(getattr(__import__('subprocess'), "CREATE_NO_WINDOW", 0), kwargs["creationflags"])

    def test_firewall_status_query_is_bounded(self):
        with patch(
            "deployment_panel.subprocess.run",
            side_effect=__import__("subprocess").TimeoutExpired("powershell.exe", 5),
        ) as run:
            self.assertEqual([], deployment_panel._SystemFirewallRunner().inspect_rule("rule"))

        self.assertEqual(5, run.call_args.kwargs["timeout"])

    def test_each_control_action_has_technical_details(self):
        expected = {
            "open_launcher",
            "refresh_status",
            "preflight",
            "public",
            "postflight",
            "open_workbench",
            "offline",
            "build_release",
            "inspect_release",
            "apply_release",
            "rollback_release",
            "code_inventory",
            "release_workflow",
        }
        self.assertEqual(set(ACTION_DETAILS), expected)
        required = {"title", "purpose", "preconditions", "steps", "ports", "failure", "rollback"}
        for action_id in expected:
            details = get_action_details(action_id)
            self.assertTrue(required.issubset(details))
            self.assertTrue(details["purpose"])
            for field in ("preconditions", "steps", "ports", "failure"):
                self.assertIsInstance(details[field], tuple)
                self.assertTrue(details[field])
            self.assertTrue(details["rollback"])

    def test_action_details_are_unknown_action_safe_and_do_not_expose_secrets(self):
        self.assertIsNone(get_action_details("missing"))
        text = repr(ACTION_DETAILS)
        for secret in ("token=", "cookie=", "password=", "Bearer ", "user:pass@"):
            self.assertNotIn(secret, text)

    def test_admin_batch_passes_script_path_without_nested_quotes(self):
        batch_path = Path(__file__).resolve().parents[1] / "启动部署控制面板.bat"
        raw = batch_path.read_bytes()
        self.assertIn(b"\r\n", raw)
        batch = raw.decode("utf-8")
        self.assertNotIn("-ArgumentList '\"\"%CD%\\deployment_panel.py\"\"'", batch)

    def test_all_closed_state_when_no_project_listeners(self):
        state = determine_panel_state(
            launcher_open=False,
            web_running=False,
            web_public=False,
            gateway_running=False,
            bridge_running=False,
            has_unknown_conflict=False,
        )
        self.assertEqual(state, PanelState.ALL_CLOSED)

    def test_local_ready_requires_web_gateway_and_no_unknown_conflict(self):
        state = determine_panel_state(
            launcher_open=True,
            web_running=True,
            web_public=False,
            gateway_running=True,
            bridge_running=False,
            has_unknown_conflict=False,
        )
        self.assertEqual(state, PanelState.LOCAL_READY)

    def test_public_state_requires_public_web_and_loopback_dependencies(self):
        state = determine_panel_state(
            launcher_open=True,
            web_running=True,
            web_public=True,
            gateway_running=True,
            bridge_running=True,
            has_unknown_conflict=False,
        )
        self.assertEqual(state, PanelState.PUBLIC_RUNNING)

    def test_unknown_conflict_is_anomaly_not_all_closed(self):
        state = determine_panel_state(
            launcher_open=False,
            web_running=False,
            web_public=False,
            gateway_running=False,
            bridge_running=False,
            has_unknown_conflict=True,
        )
        self.assertEqual(state, PanelState.ANOMALY)

    def test_partial_service_runtime_is_anomaly_not_all_closed(self):
        state = determine_panel_state(
            launcher_open=False,
            web_running=True,
            web_public=False,
            gateway_running=False,
            bridge_running=False,
            has_unknown_conflict=False,
        )
        self.assertEqual(state, PanelState.ANOMALY)

    def test_public_action_needs_recent_successful_preflight(self):
        self.assertFalse(public_action_allowed(PanelState.LOCAL_READY, False, False))
        self.assertFalse(public_action_allowed(PanelState.ALL_CLOSED, True, False))
        self.assertTrue(public_action_allowed(PanelState.LOCAL_READY, True, True))
        self.assertFalse(public_action_allowed(PanelState.PUBLIC_RUNNING, True, True))

    def test_status_message_masks_sensitive_values(self):
        message = sanitize_status_message(
            "token=secret-token cookie=session-cookie password=pwd "
            "Authorization: Bearer abc proxy=http://user:pass@example.test:8080"
        )
        self.assertNotIn("secret-token", message)
        self.assertNotIn("session-cookie", message)
        self.assertNotIn("pwd", message)
        self.assertNotIn("Bearer abc", message)
        self.assertNotIn("user:pass@", message)

    def test_preflight_port_result_exposes_ownership_and_evidence(self):
        line, failure = format_preflight_port_check(
            {
                "port": 8775,
                "address": "0.0.0.0",
                "pid": 1234,
                "ownership": "unknown",
                "evidence_summary": "工作目录不匹配",
            }
        )
        self.assertIn("8775", line)
        self.assertIn("0.0.0.0", line)
        self.assertIn("PID 1234", line)
        self.assertIn("未知占用", line)
        self.assertIn("工作目录不匹配", line)
        self.assertEqual("端口 8775 未知占用（PID 1234）：工作目录不匹配", failure)

    def test_preflight_port_result_does_not_duplicate_identical_records(self):
        line, failure = format_preflight_port_check(
            {
                "port": 7896,
                "address": "127.0.0.1",
                "pid": 4321,
                "ownership": "project",
                "evidence_summary": "入口命令匹配",
            }
        )
        self.assertEqual("端口 7896 127.0.0.1（PID 4321）：本项目，可管理；入口命令匹配", line)
        self.assertIsNone(failure)

    def test_offline_verification_blocks_any_remaining_listener_or_launcher(self):
        blockers = find_offline_blockers(
            {
                "ports": [
                    {"port": 8780, "address": "127.0.0.1", "pid": 22},
                    {"port": 7896, "address": "127.0.0.1", "pid": 33},
                ]
            },
            launcher_open=True,
        )
        self.assertEqual(
            ["端口 8780 仍由 PID 22 监听", "端口 7896 仍由 PID 33 监听", "启动器仍在运行"],
            blockers,
        )

    def test_offline_verification_accepts_no_listeners_and_closed_launcher(self):
        self.assertEqual([], find_offline_blockers({"ports": []}, launcher_open=False))

    def test_launcher_state_is_collected_before_ui_callback(self):
        process = type("Process", (), {"pid": 10})()
        calls = []
        manager = type(
            "Manager",
            (),
            {
                "launcher_running": lambda _self: False,
                "runner": type("Runner", (), {"enumerate_processes": lambda _self: calls.append(True) or []})(),
                "is_owned_process": lambda _self, item, role: item is process and role == "launcher",
            },
        )()
        self.assertTrue(collect_launcher_open(manager, processes=[process]))
        self.assertEqual([], calls)

    def test_offline_verification_blocks_enabled_public_firewall_rule(self):
        rule = type("Rule", (), {"enabled": True})()
        self.assertEqual(
            ["8775 公网防火墙规则仍在启用"],
            find_offline_blockers({"ports": [], "firewall": rule}, launcher_open=False),
        )

    def test_apply_does_not_call_release_script_when_offline_verification_fails(self):
        panel = object.__new__(DeploymentPanel)
        calls = []
        panel.release_manager = type(
            "ReleaseManager",
            (),
            {"apply": lambda _self, package, digest: calls.append((package, digest))},
        )()
        panel._take_offline_and_verify = lambda: (_ for _ in ()).throw(RuntimeError("still online"))

        with self.assertRaisesRegex(RuntimeError, "still online"):
            panel._apply_release_impl("release.zip", "a" * 64)

        self.assertEqual([], calls)

    def test_rollback_does_not_call_release_script_when_offline_verification_fails(self):
        panel = object.__new__(DeploymentPanel)
        calls = []
        panel.release_manager = type(
            "ReleaseManager",
            (),
            {"rollback": lambda _self, rollback_id: calls.append(rollback_id)},
        )()
        panel._take_offline_and_verify = lambda: (_ for _ in ()).throw(RuntimeError("still online"))

        with self.assertRaisesRegex(RuntimeError, "still online"):
            panel._rollback_release_impl("rollback-1")

        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
