from __future__ import annotations

import copy
import unittest

from creative_studio.ai_v2.schema import SchemaViolation, load_schema, validate_json


def _narrative_value() -> dict[str, object]:
    return {
        "schema_version": "narrative-text-v1",
        "items": [
            {
                "story": f"故事 {index}",
                "hooks": [
                    {"text": "钩子一", "scenes": ["场景一", "场景二", "场景三"]},
                    {"text": "钩子二", "scenes": ["场景四", "场景五", "场景六"]},
                ],
            }
            for index in range(5)
        ],
    }


def _static_value() -> dict[str, object]:
    return {
        "schema_version": "static-text-v1",
        "items": [
            {
                "title": f"方案 {index}",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "image_description": "画面描述",
                "execution": {"image_prompt": "私有图片提示词"},
            }
            for index in range(3)
        ],
    }


def _carousel_value(frame_count: int = 3) -> dict[str, object]:
    frames = [{"index": index, "description": f"画面 {index}"} for index in range(1, frame_count + 1)]
    prompts = [{"index": index, "prompt": f"提示词 {index}"} for index in range(1, frame_count + 1)]
    return {
        "schema_version": "carousel-text-v1",
        "items": [
            {
                "title": f"方案 {index}",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "frames": copy.deepcopy(frames),
                "execution": {
                    "continuity_rules": ["主体一致"],
                    "image_prompts": copy.deepcopy(prompts),
                },
            }
            for index in range(3)
        ],
    }


class AiV2SchemaTests(unittest.TestCase):
    def test_loads_all_versioned_schemas(self) -> None:
        for schema_id in ("narrative-text", "static-text", "carousel-text"):
            schema = load_schema(schema_id, "v1")
            self.assertEqual(schema["type"], "object")

    def test_narrative_requires_five_items_two_hooks_and_three_scenes(self) -> None:
        schema = load_schema("narrative-text", "v1")
        value = _narrative_value()
        validate_json(value, schema)

        value["items"] = value["items"][:4]  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "min_items")
        self.assertEqual(context.exception.field_path, "$.items")

        value = _narrative_value()
        value["items"][0]["hooks"] = value["items"][0]["hooks"][:1]  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertIn("hooks", context.exception.field_path)

        value = _narrative_value()
        value["items"][0]["hooks"][0]["scenes"] = ["只一幕"]  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertIn("scenes", context.exception.field_path)

    def test_static_requires_exactly_three_items_and_one_image_prompt(self) -> None:
        schema = load_schema("static-text", "v1")
        validate_json(_static_value(), schema)

        value = _static_value()
        value["items"][0]["execution"] = {}  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertIn("image_prompt", context.exception.field_path)

        value = _static_value()
        value["items"][0]["execution"]["extra"] = "第二条"  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "additional_property")

        value = _static_value()
        value["items"].append(copy.deepcopy(value["items"][0]))  # type: ignore[index]
        with self.assertRaises(SchemaViolation):
            validate_json(value, schema)

    def test_carousel_requires_two_to_five_contiguous_matching_frames_and_prompts(self) -> None:
        schema = load_schema("carousel-text", "v1")
        for frame_count in (2, 3, 4, 5):
            validate_json(_carousel_value(frame_count), schema)

        value = _carousel_value()
        value["items"][0]["frames"][1]["index"] = 4  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "non_contiguous_index")

        value = _carousel_value()
        value["items"][0]["execution"]["image_prompts"] = value["items"][0]["execution"]["image_prompts"][:2]  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "array_length_mismatch")

        value = _carousel_value()
        value["items"][0]["execution"]["image_prompts"][1]["index"] = 5  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "index_mismatch")

    def test_rejects_missing_fields_wrong_types_and_extra_fields(self) -> None:
        schema = load_schema("narrative-text", "v1")
        value = _narrative_value()
        del value["items"][0]["story"]  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "required")

        value = _narrative_value()
        value["items"][0]["story"] = 1  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "type")

        value = _narrative_value()
        value["items"][0]["unknown"] = "不在契约内"  # type: ignore[index]
        with self.assertRaises(SchemaViolation) as context:
            validate_json(value, schema)
        self.assertEqual(context.exception.reason_code, "additional_property")


if __name__ == "__main__":
    unittest.main()
