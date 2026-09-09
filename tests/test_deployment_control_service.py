import unittest
from pathlib import Path

from deployment_control.firewall_manager import (
    FIREWALL_RULE_NAME,
    FirewallManager,
    FirewallRule,
)
from deployment_control.service_manager import (
    ProcessRecord,
    PortBinding,
    ServiceConflictError,
    ServiceManager,
)


class FakeProcessRunner:
    def __init__(self, processes=None):
        self.processes = list(processes or [])
        self.calls = []
        self.launched = []

    def enumerate_processes(self):
        return list(self.processes)

    def launch(self, command, cwd, env):
        self.calls.append(("launch", tuple(command), Path(cwd), dict(env)))
        self.launched.append((tuple(command), Path(cwd), dict(env)))
        return 9001

    def terminate(self, pid):
        self.calls.append(("terminate", pid))

    def send_launcher_close(self, pid):
        self.calls.append(("launcher_close", pid))

    def wait_for_exit(self, pid, timeout):
        self.calls.append(("wait", pid, timeout))
        return True


class FakePortInspector:
    def __init__(self, bindings=None):
        self.bindings = {port: list(items) for port, items in (bindings or {}).items()}

    def inspect(self, port):
        return list(self.bindings.get(port, []))


class FakeFirewallRunner:
    def __init__(self, rules=None):
        self.rules = list(rules or [])
        self.calls = []

    def inspect_rule(self, name):
        self.calls.append(("inspect", name))
        return [rule for rule in self.rules if rule.name == name]

    def create_rule(self, name, local_port, protocol, direction, action):
        self.calls.append(("create", name, local_port, protocol, direction, action))
        self.rules.append(
            FirewallRule(name, local_port, protocol, direction, action, True)
        )

    def enable_rule(self, name):
        self.calls.append(("enable", name))

    def disable_rule(self, name):
        self.calls.append(("disable", name))

    def remove_rule(self, name):
        self.calls.append(("remove", name))


class ServiceManagerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(r"C:\AI-Creative-Studio")
        self.python = self.root / ".venv" / "Scripts" / "python.exe"

    def test_owned_web_process_requires_project_evidence(self):
        owned = ProcessRecord(
            11,
            str(self.python),
            f'"{self.python}" -m creative_studio.app',
            str(self.root),
        )
        unknown = ProcessRecord(
            12,
            r"C:\Python311\python.exe",
            r"C:\Python311\python.exe -m creative_studio.app",
            r"C:\other",
        )
        manager = ServiceManager(
            self.root,
            FakeProcessRunner([owned, unknown]),
            FakePortInspector(),
        )

        self.assertTrue(manager.is_owned_process(owned, "web"))
        self.assertFalse(manager.is_owned_process(unknown, "web"))

    def test_owned_web_process_can_use_project_cwd_as_path_evidence(self):
        owned = ProcessRecord(
            11,
            str(self.python),
            '"python.exe" -m creative_studio.app',
            str(self.root),
        )
        manager = ServiceManager(
            self.root,
            FakeProcessRunner([owned]),
            FakePortInspector(),
        )

        self.assertTrue(manager.is_owned_process(owned, "web"))

    def test_public_switch_refuses_unknown_web_occupant(self):
        runner = FakeProcessRunner()
        inspector = FakePortInspector(
            {8775: [PortBinding(8775, "127.0.0.1", 22)]}
        )
        manager = ServiceManager(self.root, runner, inspector)

        with self.assertRaises(ServiceConflictError):
            manager.switch_web_to_public({"SECRET": "do-not-log"})

        self.assertEqual(runner.calls, [])

    def test_public_switch_restarts_owned_web_with_only_host_difference(self):
        owned = ProcessRecord(
            11,
            str(self.python),
            f'"{self.python}" -m creative_studio.app',
            str(self.root),
        )
        runner = FakeProcessRunner([owned])
        inspector = FakePortInspector(
            {8775: [PortBinding(8775, "127.0.0.1", 11)]}
        )
        manager = ServiceManager(self.root, runner, inspector)

        manager.switch_web_to_public(
            {
                "CREATIVE_STUDIO_HOST": "127.0.0.1",
                "CREATIVE_STUDIO_PORT": "8775",
                "SECRET": "sensitive",
            }
        )

        self.assertEqual(
            [call[0] for call in runner.calls],
            ["terminate", "wait", "launch"],
        )
        launch = runner.launched[0]
        self.assertEqual(launch[1], self.root)
        self.assertEqual(launch[2]["CREATIVE_STUDIO_HOST"], "0.0.0.0")
        self.assertEqual(launch[2]["SECRET"], "sensitive")
        self.assertNotIn("sensitive", " ".join(launch[0]))

    def test_shutdown_obeys_order_and_never_terminates_unknown_processes(self):
        web = ProcessRecord(
            11,
            str(self.python),
            f'"{self.python}" -m creative_studio.app',
            str(self.root),
        )
        launcher = ProcessRecord(
            21,
            str(self.root / ".venv" / "Scripts" / "pythonw.exe"),
            f'"{self.root / ".venv" / "Scripts" / "pythonw.exe"}" launcher.py',
            str(self.root),
        )
        gateway = ProcessRecord(
            31,
            str(self.python),
            f'"{self.python}" main.py',
            str(self.root / "chat2api"),
        )
        bridge = ProcessRecord(
            41,
            r"C:\tools\mihomo.exe",
            f'mihomo.exe -f "{self.root / ".runtime" / "proxy-bridge.yaml"}"',
            str(self.root / ".runtime"),
        )
        unknown = ProcessRecord(51, r"C:\other\python.exe", "python.exe", r"C:\other")
        runner = FakeProcessRunner([web, launcher, gateway, bridge, unknown])
        inspector = FakePortInspector(
            {
                8775: [PortBinding(8775, "0.0.0.0", 11)],
                8780: [PortBinding(8780, "127.0.0.1", 31)],
                7896: [PortBinding(7896, "127.0.0.1", 41)],
            }
        )
        firewall = FirewallManager(
            FakeFirewallRunner(
                [FirewallRule(FIREWALL_RULE_NAME, 8775, "TCP", "Inbound", "Allow", True)]
            )
        )
        manager = ServiceManager(self.root, runner, inspector)

        manager.shutdown(firewall)

        self.assertEqual(
            runner.calls,
            [
                ("terminate", 11),
                ("wait", 11, 5.0),
                ("launcher_close", 21),
                ("wait", 21, 5.0),
                ("terminate", 31),
                ("wait", 31, 5.0),
                ("terminate", 41),
                ("wait", 41, 5.0),
            ],
        )
        self.assertNotIn(("terminate", 51), runner.calls)
        self.assertEqual(firewall.runner.calls[-1], ("disable", FIREWALL_RULE_NAME))


class FirewallManagerTests(unittest.TestCase):
    def test_enable_uses_only_fixed_rule_parameters(self):
        runner = FakeFirewallRunner()
        manager = FirewallManager(runner)

        manager.enable()

        self.assertEqual(
            runner.calls,
            [
                ("inspect", FIREWALL_RULE_NAME),
                (
                    "create",
                    FIREWALL_RULE_NAME,
                    8775,
                    "TCP",
                    "Inbound",
                    "Allow",
                ),
                ("enable", FIREWALL_RULE_NAME),
            ],
        )

    def test_invalid_or_duplicate_rule_is_not_modified(self):
        invalid = FirewallRule(FIREWALL_RULE_NAME, 8780, "TCP", "Inbound", "Allow", True)
        duplicate = FirewallRule(FIREWALL_RULE_NAME, 8775, "TCP", "Inbound", "Allow", True)
        runner = FakeFirewallRunner([invalid, duplicate])
        manager = FirewallManager(runner)

        with self.assertRaises(ValueError):
            manager.enable()

        self.assertEqual(runner.calls, [("inspect", FIREWALL_RULE_NAME)])

    def test_disable_and_remove_target_only_fixed_rule(self):
        rule = FirewallRule(FIREWALL_RULE_NAME, 8775, "TCP", "Inbound", "Allow", True)
        runner = FakeFirewallRunner([rule])
        manager = FirewallManager(runner)

        manager.disable()
        manager.remove()

        self.assertEqual(
            runner.calls,
            [
                ("inspect", FIREWALL_RULE_NAME),
                ("disable", FIREWALL_RULE_NAME),
                ("inspect", FIREWALL_RULE_NAME),
                ("remove", FIREWALL_RULE_NAME),
            ],
        )


if __name__ == "__main__":
    unittest.main()
