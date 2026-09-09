import unittest
from pathlib import Path

from deployment_panel import (
    ACTION_DETAILS,
    PanelState,
    determine_panel_state,
    get_action_details,
    public_action_allowed,
    sanitize_status_message,
)


class DeploymentPanelStateTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
