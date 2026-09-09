import unittest
from pathlib import Path

from deployment_panel import (
    PanelState,
    determine_panel_state,
    public_action_allowed,
    sanitize_status_message,
)


class DeploymentPanelStateTests(unittest.TestCase):
    def test_admin_batch_passes_script_path_without_nested_quotes(self):
        batch = (Path(__file__).resolve().parents[1] / "启动部署控制面板.bat").read_text(encoding="utf-8")
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
