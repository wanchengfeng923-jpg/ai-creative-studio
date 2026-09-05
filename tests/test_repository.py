from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from creative_studio.auth import hash_password, token_digest
from creative_studio.repository import StudioDataError, StudioRepository


RETIRED_TABLES = {
    "generations",
    "visual_items",
    "display_frames",
    "adoptions",
    "carousel_operations",
}
NEUTRAL_TABLES = {
    "projects",
    "project_files",
    "users",
    "sessions",
    "login_attempts",
    "audit_logs",
}


def _create_legacy_project_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            PRAGMA user_version = 0;
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                script_type TEXT NOT NULL DEFAULT '展示类',
                task_type TEXT NOT NULL DEFAULT '',
                task_description TEXT NOT NULL DEFAULT '',
                creative_tags_json TEXT NOT NULL DEFAULT '{}',
                aspect_ratio TEXT NOT NULL DEFAULT '16:9',
                product_evidence_summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO projects(
                name, script_type, task_type, task_description, creative_tags_json,
                aspect_ratio, product_evidence_summary, created_at, updated_at
            ) VALUES(
                '旧项目', '展示类', '', '', '{}', '16:9', '',
                '2026-08-31 00:00:00', '2026-08-31 00:00:00'
            );
            """
        )
        connection.commit()


def _create_database_with_retired_tables(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for table_name in sorted(RETIRED_TABLES):
            connection.execute(
                f"CREATE TABLE {table_name}(id INTEGER PRIMARY KEY, marker TEXT NOT NULL)"
            )
            connection.execute(
                f"INSERT INTO {table_name}(id, marker) VALUES(1, ?)",
                (f"keep-{table_name}",),
            )
        connection.commit()


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "studio.db"
        self.repo = StudioRepository(self.database_path)
        self.project = self.repo.create_project("测试项目", "展示类")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _table_names(path: Path) -> set[str]:
        with closing(sqlite3.connect(path)) as connection:
            return {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }

    def test_new_database_contains_only_neutral_repository_tables(self) -> None:
        self.assertEqual(self._table_names(self.database_path), NEUTRAL_TABLES)

    def test_initialization_preserves_existing_retired_tables_and_rows(self) -> None:
        retired_path = Path(self.temp.name) / "retired.db"
        _create_database_with_retired_tables(retired_path)
        with closing(sqlite3.connect(retired_path)) as connection:
            columns_before = {
                table: tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))
                for table in RETIRED_TABLES
            }

        StudioRepository(retired_path)

        with closing(sqlite3.connect(retired_path)) as connection:
            columns_after = {
                table: tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))
                for table in RETIRED_TABLES
            }
            markers = {
                table: connection.execute(f"SELECT marker FROM {table} WHERE id=1").fetchone()[0]
                for table in RETIRED_TABLES
            }
        self.assertEqual(columns_after, columns_before)
        self.assertEqual(markers, {table: f"keep-{table}" for table in RETIRED_TABLES})

    def test_project_round_trip_search_and_file_metadata(self) -> None:
        updated = self.repo.update_project(
            self.project["id"],
            {
                "task_description": "测试说明",
                "creative_tags": {"target_audiences": ["武侠玩家"]},
                "aspect_ratio": "9:16",
            },
        )
        record = self.repo.add_project_file(
            self.project["id"],
            "brief.txt",
            "stored.txt",
            12,
            sha256="b" * 64,
            mime_type="text/plain",
            extraction_status="complete",
            safe_summary="摘要",
        )
        loaded = self.repo.get_project(self.project["id"])

        self.assertEqual(updated["aspect_ratio"], "9:16")
        self.assertEqual(updated["creative_tags"]["target_audiences"], ["武侠玩家"])
        self.assertEqual(len(self.repo.list_projects("测试")), 1)
        self.assertEqual(loaded["reference_files"][0]["id"], record["id"])
        self.assertNotIn("stored_name", loaded["reference_files"][0])
        self.assertIsNone(loaded["adoption"])

    def test_project_listing_does_not_require_retired_adoption_table(self) -> None:
        self.assertNotIn("adoptions", self._table_names(self.database_path))
        summary = self.repo.list_projects()[0]
        self.assertEqual(summary["id"], self.project["id"])
        self.assertEqual(summary["adopted_kind"], "")
        self.assertEqual(summary["adopted_title"], "")

    def test_project_file_validation_rejects_invalid_digest_and_status(self) -> None:
        with self.assertRaises(StudioDataError):
            self.repo.add_project_file(self.project["id"], "a.txt", "a.txt", 1, sha256="bad")
        with self.assertRaises(StudioDataError):
            self.repo.add_project_file(
                self.project["id"], "a.txt", "a.txt", 1, extraction_status="unknown"
            )

    def test_legacy_projects_schema_migrates_without_losing_rows(self) -> None:
        legacy_path = Path(self.temp.name) / "legacy.db"
        _create_legacy_project_database(legacy_path)

        migrated = StudioRepository(legacy_path)
        loaded = migrated.get_project(1)

        self.assertEqual(loaded["name"], "旧项目")
        self.assertIsNone(loaded["owner_user_id"])
        with closing(sqlite3.connect(legacy_path)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(projects)")]
        self.assertIn("owner_user_id", columns)

    def test_bootstrap_admin_is_idempotent_and_backfills_unowned_projects(self) -> None:
        admin = self.repo.create_bootstrap_admin("Admin.User", "0123456789ab")
        self.assertEqual(self.repo.get_project_owner_id(self.project["id"]), admin["id"])
        with closing(sqlite3.connect(self.database_path)) as connection:
            first_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id=?", (admin["id"],)
            ).fetchone()[0]

        again = self.repo.create_bootstrap_admin("different", "abcdefghijkl")
        with closing(sqlite3.connect(self.database_path)) as connection:
            second_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id=?", (admin["id"],)
            ).fetchone()[0]
        self.assertEqual(admin["id"], again["id"])
        self.assertEqual(first_hash, second_hash)
        self.assertNotIn("password_hash", self.repo.list_users()[0])

        late_project = self.repo.create_project("后来创建的项目", "展示类")
        self.assertIsNone(self.repo.get_project_owner_id(late_project["id"]))
        self.repo.create_bootstrap_admin("ignored", "abcdefghijkl")
        self.assertEqual(self.repo.get_project_owner_id(late_project["id"]), admin["id"])

    def test_session_login_attempt_and_audit_rows_are_persisted(self) -> None:
        admin = self.repo.create_bootstrap_admin("admin", "0123456789ab")
        user = self.repo.create_user("alice", "abcdefghijklm")

        self.assertEqual(self.repo.record_login_failure("alice", "127.0.0.1")["failure_count"], 1)
        self.assertEqual(self.repo.record_login_failure("alice", "127.0.0.1")["failure_count"], 2)
        self.repo.clear_login_attempt_window("alice", "127.0.0.1")
        self.assertIsNone(self.repo.get_login_attempt("alice", "127.0.0.1"))

        self.repo.record_audit(
            admin["id"], "create_user", "user", str(user["id"]), "success", {"ip": "127.0.0.1"}
        )
        self.repo.create_session(user["id"], "token-a", "csrf-a", "127.0.0.1", "unittest")
        self.repo.create_session(user["id"], "token-b", "csrf-b", "127.0.0.1", "unittest")
        session_context = self.repo.get_session("token-a")
        self.assertEqual(session_context["user_id"], user["id"])
        self.assertNotIn("csrf_token_digest", session_context)
        self.assertTrue(self.repo.verify_session_csrf("token-a", "csrf-a"))
        self.assertFalse(self.repo.verify_session_csrf("token-a", "wrong-csrf"))
        self.assertTrue(self.repo.touch_session("token-a"))
        self.assertTrue(self.repo.revoke_session("token-a"))
        self.assertTrue(self.repo.revoke_sessions_for_user(user["id"]))

    def test_session_expiry_and_inactive_user_invalidate_context(self) -> None:
        user = self.repo.create_user("alice", "abcdefghijklm")
        self.repo.create_session(
            user["id"], "expired-token", "expired-csrf", idle_seconds=0
        )
        self.assertIsNone(self.repo.get_session("expired-token"))

        self.repo.create_session(user["id"], "active-token", "active-csrf")
        self.repo.set_user_active(user["id"], False)
        self.assertIsNone(self.repo.get_session("active-token"))
        with closing(sqlite3.connect(self.database_path)) as connection:
            revoked = connection.execute(
                "SELECT revoked_at FROM sessions WHERE token_digest=?", (token_digest("active-token"),)
            ).fetchone()[0]
        self.assertIsNotNone(revoked)

    def test_login_failure_window_resets_and_audit_omits_secrets(self) -> None:
        for expected in range(1, 6):
            self.assertEqual(
                self.repo.record_login_failure("alice", "127.0.0.1")["failure_count"], expected
            )
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE login_attempts SET window_started_at=?,locked_until=NULL WHERE username=?",
                ("2000-01-01 00:00:00", "alice"),
            )
            connection.commit()
        self.assertEqual(self.repo.record_login_failure("alice", "127.0.0.1")["failure_count"], 1)

        admin = self.repo.create_bootstrap_admin("admin", "0123456789ab")
        self.repo.record_audit(
            admin["id"], "login", "user", "1", "failure",
            {"ip": "127.0.0.1", "password": "do-not-store", "token": "do-not-store"},
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            metadata = connection.execute(
                "SELECT metadata_json FROM audit_logs ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        self.assertIn('"ip":"127.0.0.1"', metadata)
        self.assertNotIn("do-not-store", metadata)

    def test_last_active_admin_cannot_be_disabled(self) -> None:
        admin = self.repo.create_bootstrap_admin("admin", "0123456789ab")
        with self.assertRaises(StudioDataError):
            self.repo.set_user_active(admin["id"], False)

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO users(username,password_hash,role,is_active,must_change_password,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("second-admin", hash_password("abcdefghijkl"), "admin", 1, 0,
                 "2026-09-01 00:00:00", "2026-09-01 00:00:00"),
            )
            connection.commit()
            second_id = connection.execute(
                "SELECT id FROM users WHERE username='second-admin'"
            ).fetchone()[0]
        self.repo.set_user_active(admin["id"], False)
        with self.assertRaises(StudioDataError):
            self.repo.set_user_active(second_id, False)

    def test_schema_migration_rolls_back_when_a_hook_raises(self) -> None:
        legacy_path = Path(self.temp.name) / "rollback.db"
        _create_legacy_project_database(legacy_path)

        class BrokenRepository(StudioRepository):
            def _migrate_schema(self, connection):  # type: ignore[override]
                super()._migrate_schema(connection)
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            BrokenRepository(legacy_path)

        with closing(sqlite3.connect(legacy_path)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(projects)")]
            row = connection.execute("SELECT name FROM projects WHERE id=1").fetchone()
        self.assertNotIn("owner_user_id", columns)
        self.assertEqual(row[0], "旧项目")


if __name__ == "__main__":
    unittest.main()
