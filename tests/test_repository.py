from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
            "creative_tags": {"target_audiences": ["武侠玩家"]},
            "aspect_ratio": "9:16",
        })
        self.assertEqual(updated["aspect_ratio"], "9:16")
        self.assertEqual(updated["creative_tags"]["target_audiences"], ["武侠玩家"])
        self.assertEqual(len(self.repo.list_projects("测试")), 1)

    def test_visual_history_hides_image_prompt_and_enforces_two_batches(self):
        for expected_batch in (1, 2):
            reservation = self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")
            self.assertEqual(reservation["batch_index"], expected_batch)
            self.repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")
        history = self.repo.generation_history(self.project["id"], "visual", "fingerprint")
        self.assertEqual(len(history["batches"]), 2)
        self.assertEqual(len(history["batches"][0]["items"]), 3)
        self.assertNotIn("image_prompt", history["batches"][0]["items"][0])
        with self.assertRaises(StudioDataError):
            self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")

    def test_adoption_can_be_replaced(self):
        reservation = self.repo.reserve_generation(self.project["id"], "visual", "visual.v1", "fingerprint")
        ids = self.repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")
        self.repo.adopt_visual(self.project["id"], ids[0])
        self.repo.adopt_visual(self.project["id"], ids[1])
        project = self.repo.get_project(self.project["id"])
        self.assertEqual(project["adoption"]["reference_id"], str(ids[1]))


if __name__ == "__main__":
    unittest.main()
