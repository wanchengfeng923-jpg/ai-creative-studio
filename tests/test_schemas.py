import unittest

from creative_studio.schemas import (
    CarouselRecommendationSchema,
    NarrativeRecommendationSchema,
    SchemaValidationError,
    VisualRecommendationSchema,
)


def _narrative_story(index: int) -> dict[str, object]:
    return {
        "story": f"故事{index}",
        "hooks": [
            {"text": f"钩子{index}-1", "scenes": [f"画面{index}-1", f"画面{index}-2", f"画面{index}-3"]},
            {"text": f"钩子{index}-2", "scenes": [f"画面{index}-4", f"画面{index}-5", f"画面{index}-6"]},
        ],
    }


def _visual_item(index: int) -> dict[str, object]:
    return {
        "title": f"方案{index}",
        "subtitle": f"副标题{index}",
        "creative_description": f"描述{index}",
        "core_subject": f"主体{index}",
        "layout": f"布局{index}",
        "visual_style": f"风格{index}",
        "content_extensions": [f"扩展{index}"],
        "reference_sources": [{"name": f"来源{index}", "note": f"借用{index}"}],
        "keywords": [f"关键词{index}"],
        "image_prompt": f"提示词{index}",
        "carousel": {
            "count": 3,
            "form": ["左右滑动"],
            "frames": [
                {"index": 1, "display_description": f"第1屏{index}"},
                {"index": 2, "display_description": f"第2屏{index}"},
                {"index": 3, "display_description": f"第3屏{index}"},
            ],
        },
    }


class SchemaTests(unittest.TestCase):
    def test_narrative_schema_requires_five_stories_two_hooks_and_three_scenes(self) -> None:
        result = NarrativeRecommendationSchema.validate([_narrative_story(index) for index in range(1, 6)])

        self.assertEqual(len(result.items), 5)
        self.assertEqual(len(result.items[0].hooks), 2)
        self.assertEqual(len(result.items[0].hooks[0].scenes), 3)

    def test_visual_schema_requires_exactly_three_items_and_keeps_carousel(self) -> None:
        result = VisualRecommendationSchema.validate({"items": [_visual_item(index) for index in range(1, 4)]})

        self.assertEqual(len(result.items), 3)
        self.assertIsNotNone(result.items[0].carousel)
        self.assertEqual(result.items[0].carousel.count, 3)
        self.assertEqual([frame.index for frame in result.items[0].carousel.frames], [1, 2, 3])
        self.assertNotIn("resolved_tags", result.items[0].__dict__)

    def test_visual_schema_rejects_urls_in_text_fields(self) -> None:
        payload = {"items": [_visual_item(index) for index in range(1, 4)]}
        payload["items"][0]["title"] = "https://example.com"

        with self.assertRaises(SchemaValidationError):
            VisualRecommendationSchema.validate(payload)

    def test_visual_schema_rejects_empty_content_extensions(self) -> None:
        payload = {"items": [_visual_item(index) for index in range(1, 4)]}
        payload["items"][0]["content_extensions"] = []

        with self.assertRaises(SchemaValidationError):
            VisualRecommendationSchema.validate(payload)

    def test_visual_schema_rejects_empty_keywords(self) -> None:
        payload = {"items": [_visual_item(index) for index in range(1, 4)]}
        payload["items"][0]["keywords"] = []

        with self.assertRaises(SchemaValidationError):
            VisualRecommendationSchema.validate(payload)

    def test_carousel_schema_requires_continuous_frames(self) -> None:
        result = CarouselRecommendationSchema.validate(
            {
                "count": 3,
                "form": ["左右滑动"],
                "frames": [
                    {"index": 1, "display_description": "第1屏"},
                    {"index": 2, "display_description": "第2屏"},
                    {"index": 3, "display_description": "第3屏"},
                ],
            }
        )

        self.assertEqual(result.count, 3)
        self.assertEqual([frame.index for frame in result.frames], [1, 2, 3])

    def test_visual_schema_rejects_mixed_ai_carousel_counts(self) -> None:
        payload = {"items": [_visual_item(index) for index in range(1, 4)]}
        payload["items"][0]["carousel"]["count"] = 2
        payload["items"][0]["carousel"]["frames"] = [
            {"index": 1, "display_description": "第1屏1"},
            {"index": 2, "display_description": "第2屏1"},
        ]
        payload["items"][1]["carousel"]["count"] = 3
        payload["items"][1]["carousel"]["frames"] = [
            {"index": 1, "display_description": "第1屏2"},
            {"index": 2, "display_description": "第2屏2"},
            {"index": 3, "display_description": "第3屏2"},
        ]
        payload["items"][2]["carousel"]["count"] = 2
        payload["items"][2]["carousel"]["frames"] = [
            {"index": 1, "display_description": "第1屏3"},
            {"index": 2, "display_description": "第2屏3"},
        ]

        with self.assertRaises(SchemaValidationError):
            VisualRecommendationSchema.validate(payload)

    def test_carousel_schema_rejects_non_continuous_frames(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CarouselRecommendationSchema.validate(
                {
                    "count": 3,
                    "frames": [
                        {"index": 1, "display_description": "第1屏"},
                        {"index": 3, "display_description": "第3屏"},
                        {"index": 4, "display_description": "第4屏"},
                    ],
                }
            )
