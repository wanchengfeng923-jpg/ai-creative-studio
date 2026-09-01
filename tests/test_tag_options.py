import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creative_studio.ai_creative import (
    AiCreativeRequestError,
    build_visual_creative_prompt,
    format_creative_tags_for_prompt,
    load_ai_visual_creative_config,
    normalize_creative_tags,
    validate_visual_creative_recommendations,
)
from creative_studio.app import load_tag_options


class TagOptionsTests(unittest.TestCase):
    def test_config_contains_complete_narrative_and_visual_groups(self):
        config = load_tag_options()
        self.assertEqual(config["version"], "tags-2026-08-31-v1")
        self.assertEqual(len(config["narrative"]["groups"]), 5)
        self.assertEqual(sum(len(group["options"]) for group in config["narrative"]["groups"]), 125)
        self.assertEqual(len(config["visual"]["groups"]), 11)
        self.assertIn("product_display", config["visual"]["relations"])

    def test_normalization_and_prompt_include_visual_selection(self):
        tags = normalize_creative_tags({
            "visual_art_style_relevance": ["强相关"],
            "visual_product_selling_points": ["自立门派，当一派掌门"],
            "visual_display_contents": ["门派"],
            "unknown": ["不要进入提示词"],
        })
        self.assertEqual(tags["visual_product_selling_points"], ["自立门派，当一派掌门"])
        self.assertEqual(tags["visual_art_style_relevance"], ["强相关"])
        self.assertNotIn("unknown", tags)
        prompt_tags = format_creative_tags_for_prompt(tags, mode="visual")
        self.assertIn("展示类产品卖点主选：自立门派，当一派掌门", prompt_tags)
        self.assertIn("展示类主展示内容：门派", prompt_tags)
        self.assertNotIn("主目标人群：", prompt_tags)

    def test_build_visual_prompt_includes_carousel_context(self):
        prompt = build_visual_creative_prompt(
            {
                "visual_product_selling_points": ["自立门派，当一派掌门"],
                "visual_display_contents": ["门派"],
                "visual_carousel": ["是"],
                "visual_carousel_count": ["3屏"],
            },
            "{{creative_tags}}\n{{carousel_context}}",
            carousel_config={
                "enabled": "是",
                "count_mode": "fixed",
                "count": 3,
                "rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {
                            "visual_product_selling_points": ["A"],
                            "visual_display_contents": [],
                            "visual_motif": ["M1"],
                        },
                    },
                    {
                        "index": 2,
                        "mode": "inherit",
                        "overrides": {
                            "visual_product_selling_points": [],
                            "visual_display_contents": ["B"],
                            "visual_motif": [],
                        },
                    },
                    {
                        "index": 3,
                        "mode": "custom",
                        "overrides": {
                            "visual_product_selling_points": [],
                            "visual_display_contents": [],
                            "visual_motif": ["M3"],
                        },
                    },
                ],
            },
            tag_catalog={
                "visual_product_selling_points": ["A", "B"],
                "visual_display_contents": ["门派", "场景"],
            },
        )
        self.assertIn("count_mode", prompt)
        self.assertIn("round_index", prompt)
        self.assertIn("空白可适用标签由 AI 补全", prompt)

    def test_validate_visual_recommendations_accepts_nested_carousel_without_resolved_tags(self):
        def make_item(title: str, display_prefix: str) -> dict[str, object]:
            return {
                "title": title,
                "subtitle": f"副标题{display_prefix}",
                "creative_description": f"描述{display_prefix}",
                "core_subject": f"主体{display_prefix}",
                "layout": f"布局{display_prefix}",
                "visual_style": f"风格{display_prefix}",
                "content_extensions": [f"扩展{display_prefix}"],
                "reference_sources": [{"name": f"来源{display_prefix}", "note": f"借用机制{display_prefix}"}],
                "keywords": [f"关键词{display_prefix}"],
                "image_prompt": f"提示词{display_prefix}",
                "carousel": {
                    "count": 3,
                    "form": ["左右滑动"],
                    "frames": [
                        {"index": 1, "display_description": f"第1屏{display_prefix}"},
                        {"index": 2, "display_description": f"第2屏{display_prefix}"},
                        {"index": 3, "display_description": f"第3屏{display_prefix}"},
                    ],
                },
            }

        value = {
            "items": [
                make_item("方案1", "1"),
                make_item("方案2", "2"),
                make_item("方案3", "3"),
            ]
        }
        items = validate_visual_creative_recommendations(
            value,
            carousel_config={
                "enabled": "是",
                "count_mode": "fixed",
                "count": 3,
                "rounds": [],
            },
            tag_catalog={
                "visual_product_selling_points": ["A", "B"],
                "visual_display_contents": ["门派"],
            },
        )
        self.assertEqual(len(items), 3)
        self.assertTrue(all("carousel" in item for item in items))
        self.assertTrue(all("resolved_tags" not in item for item in items))
        self.assertEqual(items[0]["carousel"]["count"], 3)
        self.assertEqual(items[0]["carousel"]["frames"][0]["display_description"], "第1屏1")

    def test_validate_visual_recommendations_rejects_fixed_carousel_length_mismatch(self):
        value = {
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
                        ],
                    },
                },
            ]
        }
        with self.assertRaisesRegex(AiCreativeRequestError, "carousel"):
            validate_visual_creative_recommendations(
                value,
                carousel_config={
                    "enabled": "是",
                    "count_mode": "fixed",
                    "count": 3,
                    "rounds": [],
                },
                tag_catalog={
                    "visual_product_selling_points": ["A", "B"],
                    "visual_display_contents": ["门派"],
                },
            )

    def test_validate_visual_recommendations_rejects_ai_carousel_count_mismatch(self):
        value = {
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
                        "count": 2,
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
                            {"index": 3, "display_description": "第三屏"},
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
                        "count": 2,
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
                        ],
                    },
                },
            ]
        }
        with self.assertRaisesRegex(AiCreativeRequestError, "统一轮播屏数"):
            validate_visual_creative_recommendations(
                value,
                carousel_config={
                    "enabled": "是",
                    "count_mode": "ai",
                    "count": None,
                    "rounds": [],
                },
                tag_catalog={
                    "visual_product_selling_points": ["A", "B"],
                    "visual_display_contents": ["门派"],
                },
            )

    def test_validate_visual_recommendations_rejects_fixed_carousel_index_gap(self):
        value = {
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 3, "display_description": "第三屏"},
                            {"index": 4, "display_description": "第四屏"},
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
                            {"index": 3, "display_description": "第三屏"},
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
                        "frames": [
                            {"index": 1, "display_description": "第一屏"},
                            {"index": 2, "display_description": "第二屏"},
                            {"index": 3, "display_description": "第三屏"},
                        ],
                    },
                },
            ]
        }
        with self.assertRaisesRegex(AiCreativeRequestError, "carousel"):
            validate_visual_creative_recommendations(
                value,
                carousel_config={
                    "enabled": "是",
                    "count_mode": "fixed",
                    "count": 3,
                    "rounds": [],
                },
                tag_catalog={
                    "visual_product_selling_points": ["A", "B"],
                    "visual_display_contents": ["门派"],
                },
            )

    def test_load_ai_visual_config_uses_carousel_prompt_version(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prompt_path = Path(tmp_dir) / "carousel_prompt.txt"
            prompt_path.write_text("carousel {{carousel_context}}", encoding="utf-8")
            with patch.dict(
                "os.environ",
                {
                    "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                    "WEB_ERP_AI_API_KEY": "secret",
                    "WEB_ERP_AI_MODEL": "test-model",
                    "WEB_ERP_AI_VISUAL_CAROUSEL_PROMPT_PATH": str(prompt_path),
                },
                clear=True,
            ):
                config = load_ai_visual_creative_config(carousel=True)
        self.assertEqual(config.prompt_version, "visual-carousel-v1")
        self.assertEqual(config.prompt_template, "carousel {{carousel_context}}")


if __name__ == "__main__":
    unittest.main()
