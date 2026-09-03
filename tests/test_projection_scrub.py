from __future__ import annotations

import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from creative_studio.projection_scrub import scrub_public_projections
from creative_studio.repository import StudioRepository


class ProjectionScrubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "studio.db"
        self.backup_path = Path(self.temp.name) / "studio-before-scrub.db"
        self.repo = StudioRepository(self.database_path)
        project = self.repo.create_project("旧数据", "展示类")
        reservation = self.repo.reserve_generation(
            project["id"], "visual", "visual.v1", "legacy-fingerprint"
        )
        raw_item = {
            "title": "方案",
            "subtitle": "副标题",
            "creative_description": "描述",
            "image_prompt": "private prompt",
            "first_frame": {
                "index": 1,
                "content": "首帧",
                "image_generation_instruction": "private instruction",
            },
            "conversation_id": "private conversation",
            "assistant_message_id": "private assistant message",
            "error_detail": "private diagnostic detail",
            "private_context": {"parent_message_id": "private message"},
        }
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE generations SET status='success',items_json=? WHERE id=?",
                (json.dumps([raw_item], ensure_ascii=False), reservation["id"]),
            )
            connection.execute(
                "INSERT INTO adoptions(project_id,recommendation_kind,reference_id,snapshot_json,updated_at) "
                "VALUES(?,?,?,?,?)",
                (
                    project["id"],
                    "visual",
                    "legacy",
                    json.dumps(raw_item, ensure_ascii=False),
                    "2026-09-03 10:00:00",
                ),
            )
            connection.commit()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _stored_json(self) -> tuple[str, str]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            generation = connection.execute(
                "SELECT items_json FROM generations ORDER BY id LIMIT 1"
            ).fetchone()[0]
            adoption = connection.execute(
                "SELECT snapshot_json FROM adoptions ORDER BY project_id LIMIT 1"
            ).fetchone()[0]
        return generation, adoption

    def test_dry_run_reports_changes_without_writing(self) -> None:
        before = self._stored_json()

        with patch(
            "creative_studio.projection_scrub.sqlite3.connect",
            wraps=sqlite3.connect,
        ) as connect:
            stats = scrub_public_projections(self.database_path)

        self.assertFalse(stats.applied)
        self.assertEqual(stats.scanned_rows, 2)
        self.assertEqual(stats.changed_rows, 2)
        self.assertEqual(stats.private_field_occurrences, 14)
        self.assertEqual(stats.invalid_json_rows, 0)
        self.assertEqual(self._stored_json(), before)
        self.assertFalse(self.backup_path.exists())
        connection_target = str(connect.call_args_list[0].args[0])
        self.assertIn("mode=ro", connection_target)
        self.assertTrue(connect.call_args_list[0].kwargs.get("uri"))

    def test_apply_requires_backup_and_rebuilds_rows_transactionally(self) -> None:
        with self.assertRaisesRegex(ValueError, "backup"):
            scrub_public_projections(self.database_path, apply=True)

        stats = scrub_public_projections(
            self.database_path,
            apply=True,
            backup_path=self.backup_path,
        )

        self.assertTrue(stats.applied)
        self.assertEqual(stats.changed_rows, 2)
        self.assertTrue(self.backup_path.is_file())
        current = " ".join(self._stored_json())
        self.assertNotIn("image_prompt", current)
        self.assertNotIn("image_generation_instruction", current)
        self.assertNotIn("conversation_id", current)
        with closing(sqlite3.connect(self.backup_path)) as backup:
            original = backup.execute(
                "SELECT items_json FROM generations ORDER BY id LIMIT 1"
            ).fetchone()[0]
        self.assertIn("image_prompt", original)

        with closing(sqlite3.connect(self.backup_path)) as backup, closing(
            sqlite3.connect(self.database_path)
        ) as restored:
            backup.backup(restored)
        self.assertIn("image_prompt", " ".join(self._stored_json()))

    def test_apply_refuses_invalid_json_without_writing_valid_rows(self) -> None:
        before = self._stored_json()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("UPDATE generations SET items_json='not-json'")
            connection.commit()
        invalid_before = self._stored_json()

        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            scrub_public_projections(
                self.database_path,
                apply=True,
                backup_path=self.backup_path,
            )

        self.assertNotEqual(invalid_before, before)
        self.assertEqual(self._stored_json(), invalid_before)
        self.assertFalse(self.backup_path.exists())

    def test_apply_refuses_unknown_recommendation_kind(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("UPDATE generations SET recommendation_kind='unknown'")
            connection.commit()
        unknown_before = self._stored_json()

        with self.assertRaisesRegex(ValueError, "recommendation kind"):
            scrub_public_projections(
                self.database_path,
                apply=True,
                backup_path=self.backup_path,
            )
        self.assertEqual(self._stored_json(), unknown_before)
        self.assertFalse(self.backup_path.exists())

    def test_non_idempotent_projection_rolls_back_apply(self) -> None:
        class NonIdempotentMapper:
            def __init__(self) -> None:
                self.calls = 0

            def result_item(self, value, *, recommendation_kind):
                self.calls += 1
                return {"title": f"projection-{self.calls}"}

        before = self._stored_json()

        with self.assertRaisesRegex(RuntimeError, "fixed-point"):
            scrub_public_projections(
                self.database_path,
                apply=True,
                backup_path=self.backup_path,
                mapper=NonIdempotentMapper(),
            )

        self.assertEqual(self._stored_json(), before)
        self.assertTrue(self.backup_path.is_file())


if __name__ == "__main__":
    unittest.main()
