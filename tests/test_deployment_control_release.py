import json
import hashlib
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess


from deployment_control.release_manager import ReleaseManager


class FakeRunner:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((list(command), kwargs))
        return CompletedProcess(command, self.returncode, self.stdout, self.stderr)


class ReleaseManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.script_path = self.root / "scripts" / "server_release.ps1"
        self.script_path.parent.mkdir()
        self.script_path.write_text("# test script", encoding="utf-8")
        self.install_root = self.root / "install"
        self.install_root.mkdir()
        self.package = self.root / "release.zip"
        self.package.write_bytes(b"safe test package")
        self.sha256 = "a" * 64

    def tearDown(self):
        self.temp_dir.cleanup()

    def manager(self, runner):
        return ReleaseManager(
            script_path=self.script_path,
            build_script_path=self.root / "scripts" / "build_release.ps1",
            inventory_script_path=self.root / "scripts" / "code_inventory.ps1",
            project_root=self.root,
            install_root=self.install_root,
            runner=runner,
        )

    def test_build_release_uses_requested_ref_and_returns_script_output(self):
        runner = FakeRunner(json.dumps({"ReleaseId": "release-1", "PackageSHA256": "a" * 64}))

        result = self.manager(runner).build_release("master")

        self.assertTrue(result["ok"])
        self.assertEqual("build", result["operation"])
        command = " ".join(runner.calls[0][0])
        self.assertIn("build_release.ps1", command)
        self.assertIn("-Ref 'master'", command)
        self.assertEqual(
            getattr(__import__('subprocess'), 'CREATE_NO_WINDOW', 0),
            runner.calls[0][1]["creationflags"],
        )

    def test_build_release_can_explicitly_ignore_uncommitted_files(self):
        runner = FakeRunner("{}")

        result = self.manager(runner).build_release("master", allow_dirty=True)

        self.assertTrue(result["ok"])
        self.assertIn("-AllowDirty", " ".join(runner.calls[0][0]))

    def test_release_scripts_hash_without_powershell_module_autoloading(self):
        expected = hashlib.sha256(self.package.read_bytes()).hexdigest()
        repository_root = Path(__file__).resolve().parents[1]

        for script_name in ("build_release.ps1", "server_release.ps1"):
            script = repository_root / "scripts" / script_name
            script_text = script.read_text(encoding="utf-8")
            function_text = re.search(
                r"function Get-FileDigest\(\[string\]\$Path\) \{.*?\n\}",
                script_text,
                re.DOTALL,
            ).group(0)
            package_path = str(self.package).replace("'", "''")
            command = (
                "$PSModuleAutoLoadingPreference = 'None'; "
                + function_text
                + f"; Get-FileDigest '{package_path}'"
            )
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(expected, completed.stdout.strip())

    def test_code_inventory_rejects_unsafe_output_path(self):
        runner = FakeRunner("{}")

        result = self.manager(runner).code_inventory(self.root, self.root / ".." / "inventory.json")

        self.assertFalse(result["ok"])
        self.assertEqual([], runner.calls)

    def test_server_release_script_runs_without_creating_a_console_window(self):
        runner = FakeRunner(json.dumps({"Status": "verified"}))

        result = self.manager(runner).inspect_package(self.package, self.sha256)

        self.assertTrue(result["ok"])
        self.assertEqual(
            getattr(__import__('subprocess'), 'CREATE_NO_WINDOW', 0),
            runner.calls[0][1]["creationflags"],
        )

    def test_inspect_package_calls_existing_script_and_returns_structured_result(self):
        runner = FakeRunner(
            json.dumps(
                {
                    "Status": "verified",
                    "ReleaseId": "release-20260909",
                    "GitCommit": "a" * 40,
                    "PackageSHA256": self.sha256,
                    "CodeFileCount": 12,
                    "CodeSHA256": "b" * 64,
                    "ApplyCommandRequired": True,
                }
            )
        )

        result = self.manager(runner).inspect_package(self.package, self.sha256)

        self.assertTrue(result["ok"])
        self.assertEqual("inspect", result["operation"])
        self.assertEqual("release-20260909", result["result"]["release_id"])
        command = " ".join(runner.calls[0][0])
        self.assertIn("-Mode 'Inspect'", command)
        self.assertIn("-PackagePath", command)
        self.assertIn(str(self.package), command)
        self.assertIn("-ExpectedSHA256", command)
        self.assertIn(self.sha256, command)
        self.assertIn("-InstallRoot", command)

    def test_apply_rejects_package_inside_protected_directory_without_running_script(self):
        protected_package = self.root / "logs" / "release.zip"
        protected_package.parent.mkdir()
        protected_package.write_bytes(b"package")
        runner = FakeRunner("{}")

        result = self.manager(runner).apply(protected_package, self.sha256)

        self.assertFalse(result["ok"])
        self.assertIn("protected", result["error"].lower())
        self.assertEqual([], runner.calls)

    def test_apply_calls_existing_script_in_apply_mode(self):
        runner = FakeRunner(
            json.dumps(
                {
                    "Status": "applied",
                    "ReleaseId": "release-20260909",
                    "RollbackId": "20260909-before-release",
                    "ProtectedDataUntouched": True,
                    "RestartRequired": True,
                }
            )
        )

        result = self.manager(runner).apply(self.package, self.sha256)

        self.assertTrue(result["ok"])
        self.assertEqual("apply", result["operation"])
        self.assertEqual("applied", result["result"]["status"])
        command = " ".join(runner.calls[0][0])
        self.assertIn("-Mode 'Apply'", command)

    def test_runner_output_is_redacted_before_becoming_result(self):
        runner = FakeRunner(
            json.dumps(
                {
                    "Status": "verified",
                    "Message": "token=secret-token cookie=secret-cookie",
                    "Proxy": "http://user:password@example.test:7896",
                }
            )
        )

        result = self.manager(runner).inspect_package(self.package, self.sha256)
        rendered = json.dumps(result, ensure_ascii=False)

        self.assertNotIn("secret-token", rendered)
        self.assertNotIn("secret-cookie", rendered)
        self.assertNotIn("user:password@", rendered)
        self.assertEqual("[REDACTED]", result["result"]["message"].split("token=")[1].split()[0])

    def test_list_valid_rollbacks_ignores_invalid_and_protected_entries(self):
        rollback_root = self.install_root / "staging" / "rollbacks"
        rollback_root.mkdir(parents=True)
        valid = rollback_root / "20260909-before-release"
        valid.mkdir()
        (valid / "rollback-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "creative-studio-rollback.v1",
                    "rollback_id": valid.name,
                    "target_release_id": "release-1",
                    "created_at": "2026-09-09T00:00:00Z",
                    "backed_up_files": ["app.py"],
                    "created_files": ["new.py"],
                }
            ),
            encoding="utf-8",
        )
        invalid = rollback_root / "invalid"
        invalid.mkdir()
        (invalid / "rollback-manifest.json").write_text("not json", encoding="utf-8")
        protected = rollback_root / "private"
        protected.mkdir()
        (protected / "rollback-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "creative-studio-rollback.v1",
                    "rollback_id": "private",
                }
            ),
            encoding="utf-8",
        )

        result = self.manager(FakeRunner("{}")).list_valid_rollbacks()

        self.assertTrue(result["ok"])
        self.assertEqual(["20260909-before-release"], [item["rollback_id"] for item in result["rollbacks"]])
        self.assertEqual(1, result["rollbacks"][0]["backed_up_file_count"])

    def test_rollback_calls_script_with_validated_id(self):
        runner = FakeRunner(
            json.dumps(
                {
                    "Status": "rolled_back",
                    "RollbackId": "20260909-before-release",
                    "RestartRequired": True,
                }
            )
        )

        result = self.manager(runner).rollback("20260909-before-release")

        self.assertTrue(result["ok"])
        self.assertEqual("20260909-before-release", result["result"]["rollback_id"])
        command = " ".join(runner.calls[0][0])
        self.assertIn("-Mode 'Rollback'", command)
        self.assertIn("-RollbackId", command)
        self.assertIn("20260909-before-release", command)

    def test_rollback_rejects_path_traversal_without_running_script(self):
        runner = FakeRunner("{}")

        result = self.manager(runner).rollback("../other")

        self.assertFalse(result["ok"])
        self.assertEqual([], runner.calls)


if __name__ == "__main__":
    unittest.main()
