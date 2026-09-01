from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from creative_studio.app import StudioApplication
from creative_studio.ai_creative import validate_visual_creative_recommendations
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


if __name__ == "__main__":
    unittest.main()
