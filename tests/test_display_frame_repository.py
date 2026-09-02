import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.display_frame_models import DisplayScheme
from creative_studio.repository import StudioRepository


class DisplayFrameRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = StudioRepository(Path(self.temp.name) / "studio.db")
        self.project = self.repo.create_project("展示测试", "展示类")
        reservation = self.repo.reserve_generation(
            self.project["id"], "visual", "visual.carousel.v2", "fp"
        )
        self.generation_id = reservation["id"]
        self.project_id = self.project["id"]
        self.scheme = DisplayScheme.from_payload(
            {
                "title": "方案",
                "creative_summary": "整体说明",
                "creative_sources": ["产品卖点"],
                "frame_count": 2,
                "visual_continuity_rules": ["主体保持一致"],
                "frame_plan": [
                    {"index": 1, "description": "首画面"},
                    {"index": 2, "description": "后续画面"},
                ],
            }
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_frame_state_and_hidden_instruction_survive_restart_without_public_leak(self) -> None:
        scheme_id = self.repo.save_display_schemes(self.generation_id, [self.scheme])[0]
        restored = self.repo.get_display_scheme(scheme_id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored["frames"][0]["planned_content"], "首画面")
        self.assertNotIn("image_generation_instruction", json.dumps(self.repo.public_display_history(self.project_id, "fp")))

    def test_scheme_continuation_lease_rejects_duplicate_owner(self) -> None:
        scheme_id = self.repo.save_display_schemes(self.generation_id, [self.scheme])[0]
        self.repo.reserve_scheme_continuation(scheme_id, "first")
        with self.assertRaisesRegex(Exception, "已有继续生成任务"):
            self.repo.reserve_scheme_continuation(scheme_id, "second")


if __name__ == "__main__":
    unittest.main()
