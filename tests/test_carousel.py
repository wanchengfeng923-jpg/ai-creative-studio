import json
import unittest
from pathlib import Path

from creative_studio.carousel import (
    CarouselValidationError,
    expand_visual_carousel_rounds,
    normalize_visual_carousel_config,
    normalize_visual_carousel_frames,
)
from creative_studio.contracts import contract_binding
from creative_studio.prompt_registry import PromptRegistry


class CarouselTests(unittest.TestCase):

    def test_carousel_evaluation_fixture_has_ten_sanitized_cases(self):
        path = Path(__file__).resolve().parents[1] / "config" / "evals" / "carousel.v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload.get("cases") if isinstance(payload, dict) else None
        self.assertIsInstance(cases, list)
        self.assertGreaterEqual(len(cases), 10)
        required = {"id", "input", "hard_constraints", "fact_boundary", "quality_checks", "failure_examples"}
        for case in cases:
            self.assertEqual(set(case), required)
            self.assertTrue(case["id"])
            self.assertIsInstance(case["input"], dict)
            self.assertTrue(str(case["input"].get("task_description") or "").strip())
            self.assertIn(case["input"].get("aspect_ratio"), {"16:9", "9:16"})
            self.assertIsInstance(case["hard_constraints"], list)
            self.assertIsInstance(case["fact_boundary"], list)
            self.assertIsInstance(case["quality_checks"], list)
            self.assertIsInstance(case["failure_examples"], list)

    def test_carousel_registry_uses_canonical_v1_contract(self):
        registry_path = Path(__file__).resolve().parents[1] / "config" / "prompts" / "registry.json"
        spec = PromptRegistry.load(registry_path).get("creative.visual.carousel.plan", "visual-carousel-v1")
        binding = contract_binding("creative.visual.carousel.plan")
        self.assertEqual(spec.lifecycle, "production")
        self.assertEqual(spec.caller, "carousel")
        self.assertEqual(spec.output_schema, "CarouselResult.v1")
        self.assertEqual(spec.validator, "CarouselResultValidator.v1")
        self.assertEqual(binding.output_schema, spec.output_schema)
        self.assertEqual(binding.validator, spec.validator)

    def test_production_prompt_matches_shared_planner_v1_policy(self):
        prompt = (Path(__file__).resolve().parents[1] / "config" / "ai_visual_carousel_prompt_v1.txt").read_text(encoding="utf-8")
        self.assertIn("直接把该私有指令交给图片模型生成首帧", prompt)
        self.assertNotIn("每套方案的新会话中重新生成实际首帧", prompt)
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

    def test_rounds_preserve_all_supported_positioning_overrides(self):
        config = normalize_visual_carousel_config(
            {
                "visual_carousel": ["是"],
                "visual_carousel_count": ["2屏"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {
                            "visual_target_audiences": ["用户A"],
                            "visual_player_desires": ["欲望A"],
                            "visual_product_selling_points": ["卖点A"],
                            "visual_display_contents": ["内容A"],
                            "visual_motif": ["母题A"],
                            "visual_dynamics": ["动态A"],
                            "visual_art_style": ["不应保留"],
                            "visual_voice_hook": ["不应保留"],
                        },
                    }
                ],
            },
            require_enabled=True,
        )

        rounds = expand_visual_carousel_rounds(config)

        self.assertEqual(
            rounds[0],
            {
                "index": 1,
                "visual_target_audiences": ["用户A"],
                "visual_player_desires": ["欲望A"],
                "visual_product_selling_points": ["卖点A"],
                "visual_display_contents": ["内容A"],
                "visual_motif": ["母题A"],
                "visual_dynamics": ["动态A"],
                "mode": "base",
            },
        )
        self.assertNotIn("visual_art_style", rounds[0])
        self.assertNotIn("visual_voice_hook", rounds[0])

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

    def test_normalize_visual_carousel_frames_accepts_nested_frame_descriptions(self):
        carousel = normalize_visual_carousel_frames(
            {
                "count": 3,
                "form": ["左右滑动"],
                "frames": [
                    {"index": 1, "display_description": "第一屏"},
                    {"index": 2, "display_description": "第二屏"},
                    {"index": 3, "display_description": "第三屏"},
                ],
            }
        )
        self.assertEqual(carousel["count"], 3)
        self.assertEqual(carousel["form"], ["左右滑动"])
        self.assertEqual(
            carousel["frames"],
            [
                {"index": 1, "display_description": "第一屏"},
                {"index": 2, "display_description": "第二屏"},
                {"index": 3, "display_description": "第三屏"},
            ],
        )

    def test_normalize_visual_carousel_frames_rejects_gaps(self):
        with self.assertRaises(CarouselValidationError) as raised:
            normalize_visual_carousel_frames(
                {
                    "count": 3,
                    "frames": [
                        {"index": 1, "display_description": "第一屏"},
                        {"index": 3, "display_description": "第三屏"},
                        {"index": 4, "display_description": "第四屏"},
                    ],
                }
            )
        self.assertEqual(
            getattr(raised.exception, "field_path", ""),
            "carousel.frames[1].index",
        )

    def test_missing_carousel_choice_is_rejected_only_for_generation(self):
        with self.assertRaises(CarouselValidationError):
            normalize_visual_carousel_config({}, require_enabled=True)
        saved = normalize_visual_carousel_config({})
        self.assertEqual(saved["enabled"], "")


if __name__ == "__main__":
    unittest.main()
