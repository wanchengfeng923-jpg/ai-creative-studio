from __future__ import annotations

import unittest

from creative_studio.app import load_tag_options


class TagOptionsTests(unittest.TestCase):
    def test_config_contains_complete_narrative_and_visual_groups(self) -> None:
        config = load_tag_options()

        self.assertEqual(config["version"], "tags-2026-09-04-v3")
        self.assertEqual(
            [group["key"] for group in config["narrative"]["groups"]],
            [
                "target_audiences",
                "art_style",
                "player_desires",
                "content_forms",
                "opening_hooks",
                "product_evidences",
            ],
        )
        self.assertEqual(len(config["narrative"]["groups"]), 6)
        self.assertEqual(
            sum(len(group["options"]) for group in config["narrative"]["groups"]),
            139,
        )
        self.assertEqual(len(config["visual"]["groups"]), 11)
        self.assertIn("product_display", config["visual"]["relations"])

    def test_only_target_audience_and_carousel_controls_are_required(self) -> None:
        config = load_tag_options()
        narrative_required = {
            group["key"] for group in config["narrative"]["groups"] if group.get("required")
        }
        visual_required = {
            group["key"] for group in config["visual"]["groups"] if group.get("required")
        }

        self.assertEqual(narrative_required, {"target_audiences"})
        self.assertEqual(
            visual_required,
            {
                "visual_target_audiences",
                "visual_carousel",
                "visual_carousel_count",
                "visual_carousel_form",
            },
        )


if __name__ == "__main__":
    unittest.main()
