import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlparse

from launcher import (
    ProxyBridge,
    _terminate_process,
    is_owned_bridge_process,
    build_mihomo_config,
    build_proxy_url,
    find_local_clash_port,
    find_local_clash_endpoint,
    format_connection_error,
    gateway_upstream_verified,
    build_session_update_request,
    push_session_cookie,
    token_username,
    should_refresh_from_cookie,
    should_refresh_session,
    mask_proxy_url,
    parse_proxy_url,
    select_runtime_proxy,
    select_chat2api_proxy,
)
from proxy_relay import build_socks5_auth_request, build_socks5_greeting, parse_connect_target


class _FakeProcess:
    def __init__(self, *, exits_on_terminate: bool = True) -> None:
        self.pid = 1234
        self.exits_on_terminate = exits_on_terminate
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self):
        return 0 if self.killed or (self.terminated and self.exits_on_terminate) else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        self.waited = True
        if self.poll() is None:
            raise subprocess.TimeoutExpired("fake", timeout)

    def kill(self):
        self.killed = True


class LauncherProxyTests(unittest.TestCase):

    def test_session_update_request_contains_cookie_and_control_header(self):
        request = build_session_update_request("new-cookie", "control-secret")

        self.assertEqual(request.get_header("X-control-token"), "control-secret")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"session_cookie": "new-cookie"})

    def test_push_session_cookie_reports_gateway_success(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"ok": true, "has_token": true}'

        with patch("launcher.urllib.request.urlopen", return_value=Response()):
            self.assertEqual(push_session_cookie("new-cookie", "control-secret"), (True, "网关已立即切换到新 Session Cookie"))

    def test_token_username_reads_web_profile_name_without_exposing_token(self):
        import base64

        def part(value):
            raw = base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
            return raw

        token = ".".join((part({"alg": "none"}), part({"https://api.openai.com/profile": {"name": "Alice"}}), "sig"))
        self.assertEqual(token_username(token), "Alice")
        self.assertEqual(token_username("invalid"), "未识别")

    def test_parse_connect_target_accepts_host_and_port(self):
        self.assertEqual(parse_connect_target("api.ipify.org:443"), ("api.ipify.org", 443))

    def test_build_socks5_auth_request_contains_credentials(self):
        request = build_socks5_auth_request("alice", "secret")

        self.assertEqual(request, b"\x01\x05alice\x06secret")

    def test_build_socks5_greeting_advertises_password_auth_when_configured(self):
        self.assertEqual(build_socks5_greeting("alice", "secret"), b"\x05\x02\x00\x02")

    def test_select_chat2api_proxy_preserves_configured_fixed_exit(self):
        selected, message = select_chat2api_proxy(
            "socks5://clipproxy.example:443",
            endpoint_finder=lambda: (17897, "http"),
        )

        self.assertEqual(selected, "socks5://clipproxy.example:443")
        self.assertIn("固定出口", message)

    def test_select_chat2api_proxy_falls_back_to_configured_proxy(self):
        selected, message = select_chat2api_proxy(
            "socks5://clipproxy.example:443",
            endpoint_finder=lambda: None,
        )

        self.assertEqual(selected, "socks5://clipproxy.example:443")
        self.assertIn("固定出口", message)

    def test_find_local_clash_endpoint_reads_configured_socks_port(self):
        config = Path(self._testMethodName + ".yaml")
        config.write_text("mixed-port: 17897\nsocks-port: 17898\nport: 17899\n", encoding="utf-8")
        try:
            with patch.dict("os.environ", {"CLASH_CONFIG_PATH": str(config)}, clear=False):
                with patch("launcher.socket.create_connection") as connect:
                    connect.return_value.__enter__.return_value = object()
                    endpoint = find_local_clash_endpoint()
            self.assertEqual(endpoint, (17897, "http"))
        finally:
            config.unlink(missing_ok=True)

    def test_find_local_clash_endpoint_honors_protocol_override(self):
        with patch.dict("os.environ", {"CHAT2API_CLASH_PORT": "12345", "CHAT2API_CLASH_PROTOCOL": "socks5"}):
            with patch("launcher.socket.create_connection") as connect:
                connect.return_value.__enter__.return_value = object()
                self.assertEqual(find_local_clash_endpoint(), (12345, "socks5"))

    def test_session_refresh_is_skipped_for_valid_gateway_token(self):
        self.assertFalse(should_refresh_session({"ok": True, "has_token": True, "seconds_to_expire": 3600}))

    def test_session_refresh_is_required_when_token_is_missing_or_expired(self):
        self.assertTrue(should_refresh_session({"ok": False, "has_token": False, "seconds_to_expire": None}))
        self.assertTrue(should_refresh_session({"ok": True, "has_token": True, "seconds_to_expire": 0}))
        self.assertTrue(should_refresh_session({"ok": True, "has_token": True, "seconds_to_expire": None}))

    def test_connection_requires_upstream_model_detection(self):
        self.assertTrue(gateway_upstream_verified({"detected": True, "data": [{"id": "gpt-5-6-mini"}]}))
        self.assertFalse(gateway_upstream_verified({"detected": False, "data": [{"id": "gpt-5-6-mini"}]}))
        self.assertFalse(gateway_upstream_verified({"detected": True, "data": []}))

    def test_failed_upstream_detection_uses_available_cookie(self):
        self.assertTrue(should_refresh_from_cookie({"detected": False, "data": []}, True))
        self.assertFalse(should_refresh_from_cookie({"detected": False, "data": []}, False))
        self.assertFalse(should_refresh_from_cookie({"detected": True, "data": [{"id": "gpt-5-6-mini"}]}, True))

    def test_format_connection_error_keeps_safe_runtime_reason(self):
        message = format_connection_error(
            RuntimeError("session refresh failed: 403"),
            secrets=("cookie-secret", "token-secret"),
        )

        self.assertEqual(message, "RuntimeError：session refresh failed: 403")

    def test_format_connection_error_redacts_configured_secrets(self):
        message = format_connection_error(
            RuntimeError("request failed cookie-secret token-secret"),
            secrets=("cookie-secret", "token-secret"),
        )

        self.assertNotIn("cookie-secret", message)
        self.assertNotIn("token-secret", message)

    def test_owned_bridge_process_requires_matching_runtime_config(self):
        runtime_dir = Path("D:/code/ai_creative_studio/.runtime")

        self.assertTrue(is_owned_bridge_process(
            23276,
            '"C:/Program Files/Clash Verge/verge-mihomo.exe" -f D:/code/ai_creative_studio/.runtime/proxy-bridge.yaml',
            runtime_dir,
        ))
        self.assertFalse(is_owned_bridge_process(
            38428,
            '"C:/Program Files/Clash Verge/verge-mihomo.exe" -f C:/Users/admin/AppData/Roaming/main.yaml',
            runtime_dir,
        ))

    def test_terminate_process_waits_and_escalates_when_needed(self):
        process = _FakeProcess(exits_on_terminate=False)

        _terminate_process(process)

        self.assertTrue(process.terminated)
        self.assertTrue(process.waited)
        self.assertTrue(process.killed)
    def test_build_proxy_url_encodes_credentials(self):
        value = build_proxy_url("http", "proxy.example.com", "8080", "user@example.com", "p@ss:word")
        parsed = urlparse(value)
        self.assertEqual(parsed.scheme, "http")
        self.assertEqual(parsed.hostname, "proxy.example.com")
        self.assertEqual(parsed.port, 8080)
        self.assertEqual(unquote(parsed.username), "user@example.com")
        self.assertEqual(unquote(parsed.password), "p@ss:word")

    def test_parse_proxy_url_hides_password_but_keeps_editable_fields(self):
        fields = parse_proxy_url("socks5://alice:secret@10.0.0.2:1080")
        self.assertEqual(fields, {"scheme": "socks5", "host": "10.0.0.2", "port": "1080", "username": "alice", "password": "secret"})

    def test_mask_proxy_url_never_exposes_password(self):
        self.assertEqual(mask_proxy_url("http://alice:secret@proxy.example.com:8080"), "http://alice:***@proxy.example.com:8080")

    def test_build_proxy_url_rejects_invalid_ports(self):
        self.assertEqual(build_proxy_url("http", "proxy.example.com", "not-a-port"), "")
        self.assertEqual(build_proxy_url("http", "proxy.example.com", "70000"), "")

    def test_parse_proxy_url_rejects_invalid_port_without_raising(self):
        self.assertEqual(parse_proxy_url("socks5://proxy.example.com:not-a-port"), {"scheme": "http", "host": "", "port": "", "username": "", "password": ""})

    def test_select_runtime_proxy_falls_back_to_working_local_clash(self):
        calls = []

        def probe(value):
            calls.append(value)
            if value == "http://127.0.0.1:7897":
                return "203.0.113.10"
            raise TimeoutError()

        selected, message = select_runtime_proxy("socks5://remote.example:433", probe)
        self.assertEqual(selected, "http://127.0.0.1:7897")
        self.assertIn("自动切换本机 Clash", message)
        self.assertIn("确认 Clash 节点就是 ClipProxy 固定 IP", message)
        self.assertEqual(calls[:2], ["socks5://remote.example:433", "http://127.0.0.1:7897"])

    def test_build_mihomo_config_chains_clipproxy_through_local_clash(self):
        config = build_mihomo_config(
            "socks5://alice:p%40ss@38.248.239.46:443",
            upstream_port=7897,
            listen_port=7896,
        )
        self.assertEqual(config["mixed-port"], 7896)
        self.assertEqual(config["proxies"][0], {
            "name": "clash-upstream",
            "type": "http",
            "server": "127.0.0.1",
            "port": 7897,
        })
        clipproxy = config["proxies"][1]
        self.assertEqual(clipproxy["server"], "38.248.239.46")
        self.assertEqual(clipproxy["username"], "alice")
        self.assertEqual(clipproxy["password"], "p@ss")
        self.assertEqual(clipproxy["dialer-proxy"], "clash-upstream")
        self.assertEqual(config["rules"], ["MATCH,chat2api-chain"])

    def test_build_mihomo_config_uses_http_type_for_http_proxy(self):
        config = build_mihomo_config("http://user:secret@proxy.example:8080", 7890, 7896)
        self.assertEqual(config["proxies"][1]["type"], "http")

    def test_build_mihomo_config_marks_https_proxy_as_tls(self):
        config = build_mihomo_config("https://proxy.example:8443", 7890, 7896)
        self.assertTrue(config["proxies"][1]["tls"])

    def test_proxy_bridge_writes_no_secret_to_status_message(self):
        bridge = ProxyBridge(
            "socks5://alice:secret@proxy.example:443",
            executable="C:/mihomo.exe",
            runtime_dir="C:/runtime",
        )
        self.assertNotIn("secret", bridge.describe())
        self.assertIn("alice:***@proxy.example:443", bridge.describe())

    def test_find_local_clash_port_honors_optional_port_override(self):
        with patch.dict("os.environ", {"CHAT2API_CLASH_PORT": "12345"}):
            with patch("launcher.socket.create_connection") as connect:
                connect.side_effect = OSError()
                self.assertIsNone(find_local_clash_port())
                self.assertEqual(connect.call_args_list[0].args[0], ("127.0.0.1", 12345))


if __name__ == "__main__":
    unittest.main()
