from __future__ import annotations

import unittest

from creative_studio.ai_v2.input_contract import (
    AiV2Input,
    InputContractError,
    fingerprint,
    normalize_input,
    resolve_use_case,
)


class AiV2InputContractTests(unittest.TestCase):
    def test_normalizes_three_fields_and_removes_empty_duplicate_tag_values(self) -> None:
        value = normalize_input(
            {
                "task_description": "  做一张海报  ",
                "aspect_ratio": " 16:9 ",
                "creative_tags": {
                    "目标人群": ["经典武侠用户", "", "经典武侠用户", "  高意愿用户  "],
                    "visual_carousel": ["是"],
                    "empty": [],
                },
            }
        )

        self.assertEqual(value, AiV2Input("做一张海报", "16:9", {
            "目标人群": ("经典武侠用户", "高意愿用户"),
            "visual_carousel": ("是",),
        }))

    def test_allows_empty_task_description_but_limits_length(self) -> None:
        self.assertEqual(normalize_input({
            "task_description": "   ",
            "aspect_ratio": "9:16",
            "creative_tags": {},
        }).task_description, "")
        with self.assertRaises(InputContractError):
            normalize_input({
                "task_description": "x" * 501,
                "aspect_ratio": "16:9",
                "creative_tags": {},
            })

    def test_rejects_unknown_fields_invalid_ratio_and_non_string_tags(self) -> None:
        base = {"task_description": "任务", "aspect_ratio": "16:9", "creative_tags": {}}
        with self.assertRaises(InputContractError):
            normalize_input({**base, "reference_files": []})
        with self.assertRaises(InputContractError):
            normalize_input({**base, "product_evidence": []})
        with self.assertRaises(InputContractError):
            normalize_input({**base, "aspect_ratio": "1:1"})
        with self.assertRaises(InputContractError):
            normalize_input({**base, "creative_tags": {"目标人群": "不是序列"}})

    def test_ignores_editor_only_carousel_round_objects(self) -> None:
        value = normalize_input({
            "task_description": "任务",
            "aspect_ratio": "16:9",
            "creative_tags": {
                "visual_carousel": ["是"],
                "visual_carousel_rounds": [{"index": 1, "mode": "base", "overrides": {}}],
            },
        })
        self.assertEqual(value.creative_tags, {"visual_carousel": ("是",)})

    def test_requires_all_three_top_level_fields(self) -> None:
        with self.assertRaises(InputContractError):
            normalize_input({"task_description": "任务", "aspect_ratio": "16:9"})

    def test_resolves_use_case_from_project_kind_and_carousel_tag(self) -> None:
        self.assertEqual(resolve_use_case("narrative", {}), "narrative")
        self.assertEqual(resolve_use_case("叙事类", {}), "narrative")
        self.assertEqual(resolve_use_case("visual", {}), "static")
        self.assertEqual(resolve_use_case("展示类", {"visual_carousel": ("否",)}), "static")
        self.assertEqual(resolve_use_case("展示类", {"visual_carousel": ("是",)}), "carousel")

    def test_fingerprint_is_stable_for_tag_order_and_contains_use_case_version(self) -> None:
        first = normalize_input({
            "task_description": "任务",
            "aspect_ratio": "16:9",
            "creative_tags": {"B": ["2", "1"], "A": ["x"]},
        })
        second = normalize_input({
            "task_description": "任务",
            "aspect_ratio": "16:9",
            "creative_tags": {"A": ["x"], "B": ["1", "2"]},
        })
        self.assertEqual(fingerprint(first, "static", prompt_version="v1"),
                         fingerprint(second, "static", prompt_version="v1"))
        self.assertNotEqual(fingerprint(first, "static", prompt_version="v1"),
                            fingerprint(first, "carousel", prompt_version="v1"))
        self.assertNotEqual(fingerprint(first, "static", prompt_version="v1"),
                            fingerprint(first, "static", prompt_version="v2"))


if __name__ == "__main__":
    unittest.main()
