import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from creative_studio.public_projection import PublicResultMapper
from creative_studio.repository import StudioRepository
from tests.test_static_visual import valid_payload


class StaticPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = StudioRepository(Path(self.tempdir.name) / "studio.db")
        self.project = self.repo.create_project("静态项目", "展示类")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_static_completion_persists_canonical_items_without_frames_or_aliases(self) -> None:
        reservation = self.repo.reserve_generation(
            self.project["id"], "visual", "static-v1", "static-fingerprint"
        )
        result = self.repo.complete_static_generation(
            reservation["id"],
            valid_payload(),
            "16:9",
        )

        self.assertEqual(len(result), 3)
        with closing(sqlite3.connect(self.repo.database_path)) as connection:
            rows = connection.execute(
                "SELECT content_json,image_prompt FROM visual_items ORDER BY item_index"
            ).fetchall()
            frame_count = connection.execute("SELECT COUNT(*) FROM display_frames").fetchone()[0]
        content = json.loads(rows[0][0])
        self.assertNotIn("subtitle", content)
        self.assertNotIn("core_subject", content)
        self.assertNotIn("image_generation_instruction", content)
        self.assertEqual(rows[0][1], valid_payload()["items"][0]["image_generation_instruction"])
        self.assertEqual(frame_count, 0)

    def test_static_history_and_adoption_projection_excludes_private_instruction(self) -> None:
        reservation = self.repo.reserve_generation(
            self.project["id"], "visual", "static-v1", "static-public"
        )
        item_id = self.repo.complete_static_generation(
            reservation["id"], valid_payload(), "9:16"
        )[0]
        history = self.repo.generation_history(self.project["id"], "visual", "static-public")
        item = history["batches"][0]["items"][0]
        public = PublicResultMapper().result_item(item, recommendation_kind="visual")
        self.assertIn("static_frame", public)
        self.assertNotIn("image_generation_instruction", json.dumps(public, ensure_ascii=False))

        reference_id, source = self.repo.visual_adoption_source(self.project["id"], item_id)
        adoption = PublicResultMapper().result_item(source, recommendation_kind="visual")
        self.repo.save_adoption(self.project["id"], "visual", reference_id, adoption)
        self.assertNotIn("image_prompt", json.dumps(adoption, ensure_ascii=False))
        self.assertNotIn("image_generation_instruction", json.dumps(adoption, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
