import unittest

from creative_studio.carousel import (
    CarouselValidationError,
    expand_visual_carousel_rounds,
    normalize_visual_carousel_config,
)


class CarouselTests(unittest.TestCase):
    def test_fixed_count_expands_inherited_rounds(self):
        config = normalize_visual_carousel_config(
            {
                "visual_carousel": ["是"],
                "visual_carousel_count": ["3屏"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {"visual_product_selling_points": ["卖点A"]},
                    },
                ],
            },
            require_enabled=True,
        )
        rounds = expand_visual_carousel_rounds(config)
        self.assertEqual(rounds[1]["visual_product_selling_points"], ["卖点A"])
        self.assertEqual(rounds[1]["visual_display_contents"], None)
        self.assertEqual(rounds[2]["visual_product_selling_points"], ["卖点A"])
        self.assertEqual(rounds[2]["visual_motif"], None)
        self.assertEqual(rounds[2]["mode"], "inherit")
        self.assertEqual(rounds[2]["visual_product_selling_points"], ["卖点A"])
        self.assertEqual(rounds[2]["mode"], "inherit")

    def test_inherit_round_anchors_to_round_one_after_custom_round(self):
        config = normalize_visual_carousel_config(
            {
                "visual_carousel": ["是"],
                "visual_carousel_count": ["3屏"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {"visual_product_selling_points": ["卖点A"]},
                    },
                    {
                        "index": 2,
                        "mode": "custom",
                        "overrides": {"visual_product_selling_points": ["卖点B"]},
                    },
                ],
            },
            require_enabled=True,
        )
        rounds = expand_visual_carousel_rounds(config)
        self.assertEqual(rounds[1]["visual_product_selling_points"], ["卖点B"])
        self.assertEqual(rounds[2]["visual_product_selling_points"], ["卖点A"])

    def test_custom_round_missing_field_stays_none(self):
        config = normalize_visual_carousel_config(
            {
                "visual_carousel": ["是"],
                "visual_carousel_count": ["3屏"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {"visual_product_selling_points": ["卖点A"]},
                    },
                    {
                        "index": 2,
                        "mode": "custom",
                        "overrides": {"visual_motif": ["母题B"]},
                    },
                ],
            },
            require_enabled=True,
        )
        rounds = expand_visual_carousel_rounds(config)
        self.assertEqual(rounds[1]["visual_product_selling_points"], None)
        self.assertEqual(rounds[1]["visual_motif"], ["母题B"])

    def test_ai_count_has_no_predefined_rounds(self):
        config = normalize_visual_carousel_config(
            {
                "visual_carousel": ["是"],
                "visual_carousel_count": ["AI决定"],
            },
            require_enabled=True,
        )
        self.assertEqual(config["count_mode"], "ai")
        self.assertEqual(expand_visual_carousel_rounds(config), [])

    def test_missing_carousel_choice_is_rejected_only_for_generation(self):
        with self.assertRaises(CarouselValidationError):
            normalize_visual_carousel_config({}, require_enabled=True)
        saved = normalize_visual_carousel_config({})
        self.assertEqual(saved["enabled"], "")


if __name__ == "__main__":
    unittest.main()
