import unittest

from creative_studio.ai_creative import format_creative_tags_for_prompt, normalize_creative_tags
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


if __name__ == "__main__":
    unittest.main()
