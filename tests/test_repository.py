from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from creative_studio.app import StudioApplication
from creative_studio.ai_creative import validate_visual_creative_recommendations
from creative_studio.auth import hash_password, token_digest
from creative_studio.repository import StudioDataError, StudioRepository


VISUAL_ITEM = {
    "title": "界面冲破现实",
    "subtitle": "操作直接改变现实",
    "creative_description": "现实场景与游戏界面形成直接因果。",
    "core_subject": "玩家手指与游戏界面",
    "layout": "左侧操作，右侧结果",
    "visual_style": "真实材质叠加明亮UI",
    "content_extensions": ["替换不同关卡结果"],
    "reference_sources": [{"name": "互动广告", "note": "借鉴即时反馈机制"}],
    "keywords": ["界面穿透", "即时反馈"],
    "image_prompt": "一张横版静态广告首帧",
    "carousel_frames": [1, 2, 3],
}


def result(items):
    return SimpleNamespace(
        items=items,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        usage_source="exact",
        latency_ms=50,
        conversation_id="conversation",
        assistant_message_id="message",
    )


def _create_legacy_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode = DELETE")
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
                '旧项目', '展示类', '', '', '{}', '16:9', '', '2026-08-31 00:00:00', '2026-08-31 00:00:00'
            );
            """
        )
        connection.commit()


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = StudioRepository(Path(self.temp.name) / "studio.db")
        self.project = self.repo.create_project("测试项目", "展示类")

    def tearDown(self):
        self.temp.cleanup()

    def test_project_round_trip_and_search(self):
        updated = self.repo.update_project(self.project["id"], {
            "task_description": "测试说明",
            "creative_tags": {
                "target_audiences": ["武侠玩家"],
                "visual_carousel": ["是"],
                "visual_carousel_count": ["3屏"],
                "visual_carousel_form": ["左右滑动"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {"visual_product_selling_points": ["卖点A"]},
                    }
                ],
            },
            "aspect_ratio": "9:16",
        })
        self.assertEqual(updated["aspect_ratio"], "9:16")
        self.assertEqual(updated["creative_tags"]["target_audiences"], ["武侠玩家"])
        self.assertEqual(updated["creative_tags"]["visual_carousel_rounds"][0]["overrides"]["visual_product_selling_points"], ["卖点A"])
        self.assertEqual(len(self.repo.list_projects("测试")), 1)

    def test_visual_history_hides_image_prompt_and_exposes_carousel_frames(self):
        for expected_batch in (1, 2):
            reservation = self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")
            self.assertEqual(reservation["batch_index"], expected_batch)
            self.repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")
        history = self.repo.generation_history(self.project["id"], "visual", "fingerprint")
        self.assertEqual(len(history["batches"]), 2)
        self.assertEqual(len(history["batches"][0]["items"]), 3)
        self.assertEqual(history["batches"][0]["items"][0]["carousel_frames"], [1, 2, 3])
        self.assertNotIn("image_prompt", history["batches"][0]["items"][0])
        with self.assertRaises(StudioDataError):
            self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")

    def test_new_visual_generation_remains_renderable_through_history_path(self):
        payload = {
            "items": [
                {
                    "title": "方案1",
                    "subtitle": "副标题1",
                    "creative_description": "描述1",
                    "core_subject": "主体1",
                    "layout": "布局1",
                    "visual_style": "风格1",
                    "content_extensions": ["扩展1"],
                    "reference_sources": [{"name": "来源1", "note": "借用机制1"}],
                    "keywords": ["关键词1"],
                    "image_prompt": "提示词1",
                    "carousel": {
                        "count": 3,
                        "form": ["左右滑动"],
                        "frames": [
                            {"index": 1, "display_description": "第1屏"},
                            {"index": 2, "display_description": "第2屏"},
                            {"index": 3, "display_description": "第3屏"},
                        ],
                    },
                },
                {
                    "title": "方案2",
                    "subtitle": "副标题2",
                    "creative_description": "描述2",
                    "core_subject": "主体2",
                    "layout": "布局2",
                    "visual_style": "风格2",
                    "content_extensions": ["扩展2"],
                    "reference_sources": [{"name": "来源2", "note": "借用机制2"}],
                    "keywords": ["关键词2"],
                    "image_prompt": "提示词2",
                    "carousel": {
                        "count": 3,
                        "form": ["左右滑动"],
                        "frames": [
                            {"index": 1, "display_description": "第1屏"},
                            {"index": 2, "display_description": "第2屏"},
                            {"index": 3, "display_description": "第3屏"},
                        ],
                    },
                },
                {
                    "title": "方案3",
                    "subtitle": "副标题3",
                    "creative_description": "描述3",
                    "core_subject": "主体3",
                    "layout": "布局3",
                    "visual_style": "风格3",
                    "content_extensions": ["扩展3"],
                    "reference_sources": [{"name": "来源3", "note": "借用机制3"}],
                    "keywords": ["关键词3"],
                    "image_prompt": "提示词3",
                    "carousel": {
                        "count": 3,
                        "form": ["左右滑动"],
                        "frames": [
                            {"index": 1, "display_description": "第1屏"},
                            {"index": 2, "display_description": "第2屏"},
                            {"index": 3, "display_description": "第3屏"},
                        ],
                    },
                },
            ]
        }
        validated = validate_visual_creative_recommendations(
            payload,
            carousel_config={
                "enabled": "是",
                "count_mode": "fixed",
                "count": 3,
                "rounds": [],
            },
            tag_catalog={"visual_product_selling_points": ["A"], "visual_display_contents": ["门派"]},
        )
        reservation = self.repo.reserve_generation(self.project["id"], "visual", "visual.carousel.v1", "fingerprint")
        self.repo.complete_visual_generation(
            reservation["id"],
            result(validated),
            "16:9",
        )
        history = self.repo.generation_history(self.project["id"], "visual", "fingerprint")
        self.assertEqual(history["batches"][0]["items"][0]["carousel_frames"], [1, 2, 3])
        self.assertEqual(history["batches"][0]["items"][0]["carousel"]["count"], 3)
        self.assertNotIn("resolved_tags", history["batches"][0]["items"][0])

    def test_adoption_can_be_replaced(self):
        reservation = self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")
        ids = self.repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")
        self.repo.adopt_visual(self.project["id"], ids[0])
        self.repo.adopt_visual(self.project["id"], ids[1])
        project = self.repo.get_project(self.project["id"])
        self.assertEqual(project["adoption"]["reference_id"], str(ids[1]))

    def test_fingerprint_changes_when_visual_carousel_round_override_changes(self):
        base_project = self.repo.update_project(self.project["id"], {
            "creative_tags": {
                "visual_carousel": ["是"],
                "visual_carousel_count": ["3屏"],
                "visual_carousel_form": ["左右滑动"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {"visual_product_selling_points": ["卖点A"]},
                    }
                ],
            }
        })
        changed_project = copy.deepcopy(base_project)
        changed_project["creative_tags"]["visual_carousel_rounds"][0]["overrides"]["visual_product_selling_points"] = ["卖点B"]
        self.assertNotEqual(
            StudioApplication._fingerprint(base_project),
            StudioApplication._fingerprint(changed_project),
        )

    def test_legacy_projects_schema_migrates_without_losing_rows(self):
        legacy_path = Path(self.temp.name) / "legacy.db"
        _create_legacy_database(legacy_path)

        repo = StudioRepository(legacy_path)

        with closing(sqlite3.connect(legacy_path)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(projects)")]
            self.assertIn("owner_user_id", columns)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            row = connection.execute("SELECT name, owner_user_id FROM projects WHERE id=1").fetchone()
        self.assertEqual(row[0], "旧项目")
        self.assertIsNone(row[1])
        self.assertEqual(repo.list_projects()[0]["name"], "旧项目")

    def test_bootstrap_admin_is_idempotent_and_backfills_unowned_projects(self):
        admin = self.repo.create_bootstrap_admin("Admin.User", "0123456789ab")
        project_owner = self.repo.get_project_owner_id(self.project["id"])
        self.assertEqual(project_owner, admin["id"])
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            first_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id=?", (admin["id"],)
            ).fetchone()[0]

        reservation = self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")
        item_ids = self.repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")
        self.assertEqual(self.repo.get_visual_item_owner_id(item_ids[0]), admin["id"])

        again = self.repo.create_bootstrap_admin("different", "abcdefghijkl")
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            second_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id=?", (admin["id"],)
            ).fetchone()[0]
        users = self.repo.list_users()

        self.assertEqual(admin["id"], again["id"])
        self.assertEqual(first_hash, second_hash)
        self.assertEqual(len(users), 1)
        self.assertNotIn("password_hash", users[0])

    def test_session_login_attempt_and_audit_rows_are_persisted(self):
        admin = self.repo.create_bootstrap_admin("admin", "0123456789ab")
        user = self.repo.create_user("alice", "abcdefghijklm")

        self.assertIsNone(self.repo.get_login_attempt("alice", "127.0.0.1"))
        first = self.repo.record_login_failure("alice", "127.0.0.1")
        second = self.repo.record_login_failure("alice", "127.0.0.1")
        self.assertEqual(first["failure_count"], 1)
        self.assertEqual(second["failure_count"], 2)
        self.repo.clear_login_attempt_window("alice", "127.0.0.1")
        self.assertIsNone(self.repo.get_login_attempt("alice", "127.0.0.1"))

        self.repo.record_audit(admin["id"], "create_user", "user", str(user["id"]), "success", {"ip": "127.0.0.1"})
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            row = connection.execute(
                "SELECT actor_user_id, action, target_type, target_id, result, metadata_json FROM audit_logs"
            ).fetchone()
        self.assertEqual(row[0], admin["id"])
        self.assertEqual(row[1], "create_user")
        self.assertEqual(row[2], "user")
        self.assertEqual(row[3], str(user["id"]))
        self.assertEqual(row[4], "success")
        self.assertEqual(row[5], '{"ip":"127.0.0.1"}')

        session_a = self.repo.create_session(user["id"], "token-a", "csrf-a", "127.0.0.1", "pytest")
        session_b = self.repo.create_session(user["id"], "token-b", "csrf-b", "127.0.0.1", "pytest")
        self.assertEqual(self.repo.get_session("token-a")["user_id"], user["id"])

        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            before = connection.execute(
                "SELECT idle_expires_at FROM sessions WHERE token_digest=?",
                (token_digest("token-a"),),
            ).fetchone()[0]
        self.assertTrue(self.repo.touch_session("token-a"))
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            after = connection.execute(
                "SELECT idle_expires_at FROM sessions WHERE token_digest=?",
                (token_digest("token-a"),),
            ).fetchone()[0]
        self.assertGreaterEqual(after, before)

        self.assertTrue(self.repo.revoke_session("token-a"))
        self.assertIsNone(self.repo.get_session("token-a"))
        self.assertTrue(self.repo.revoke_sessions_for_user(user["id"]))
        self.assertIsNone(self.repo.get_session("token-b"))

    def test_session_expiry_and_inactive_user_invalidate_context(self):
        user = self.repo.create_user("alice", "abcdefghijklm")
        self.repo.create_session(user["id"], "expired-token", "expired-csrf", "127.0.0.1", "pytest", idle_seconds=0)
        self.assertIsNone(self.repo.get_session("expired-token"))

        self.repo.create_session(user["id"], "active-token", "active-csrf", "127.0.0.1", "pytest")
        self.assertIsNotNone(self.repo.get_session("active-token"))
        self.repo.set_user_active(user["id"], False)
        self.assertIsNone(self.repo.get_session("active-token"))
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            revoked = connection.execute(
                "SELECT revoked_at FROM sessions WHERE token_digest=?", (token_digest("active-token"),)
            ).fetchone()[0]
        self.assertIsNotNone(revoked)

    def test_login_failure_window_resets_after_window_and_audit_omits_secrets(self):
        for expected in range(1, 6):
            attempt = self.repo.record_login_failure("alice", "127.0.0.1")
            self.assertEqual(attempt["failure_count"], expected)
        self.assertTrue(self.repo.get_login_attempt("alice", "127.0.0.1")["is_locked"])

        with closing(sqlite3.connect(self.repo.database_path)) as connection:
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
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            metadata = connection.execute("SELECT metadata_json FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertIn('"ip":"127.0.0.1"', metadata)
        self.assertNotIn("do-not-store", metadata)

    def test_last_active_admin_cannot_be_disabled(self):
        admin = self.repo.create_bootstrap_admin("admin", "0123456789ab")
        with self.assertRaises(StudioDataError):
            self.repo.set_user_active(admin["id"], False)

        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            connection.execute(
                "INSERT INTO users(username,password_hash,role,is_active,must_change_password,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("second-admin", hash_password("abcdefghijkl"), "admin", 1, 0, "2026-09-01 00:00:00", "2026-09-01 00:00:00"),
            )
            connection.commit()
            second_id = connection.execute("SELECT id FROM users WHERE username=?", ("second-admin",)).fetchone()[0]
        self.repo.set_user_active(admin["id"], False)
        with self.assertRaises(StudioDataError):
            self.repo.set_user_active(second_id, False)

    def test_schema_migration_rolls_back_when_a_hook_raises(self):
        legacy_path = Path(self.temp.name) / "rollback.db"
        _create_legacy_database(legacy_path)

        class BrokenRepository(StudioRepository):
            def _migrate_schema(self, connection):  # type: ignore[override]
                super()._migrate_schema(connection)
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            BrokenRepository(legacy_path)

        with closing(sqlite3.connect(legacy_path)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(projects)")]
            self.assertNotIn("owner_user_id", columns)
            row = connection.execute("SELECT name FROM projects WHERE id=1").fetchone()
        self.assertEqual(row[0], "旧项目")


if __name__ == "__main__":
    unittest.main()
