"""AI v2 版本化 JSON Schema 加载和最小无依赖校验器。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class SchemaViolation(ValueError):
    """模型 JSON 不满足 v2 schema。"""

    def __init__(self, field_path: str, reason_code: str, message: str | None = None) -> None:
        self.field_path = field_path
        self.reason_code = reason_code
        super().__init__(message or f"{field_path}: {reason_code}")


_SCHEMA_IDS = frozenset({"narrative-text", "static-text", "carousel-text"})


def load_schema(schema_id: str, version: str) -> Mapping[str, Any]:
    """加载仓库内已知的 v2 schema，不执行 schema 文件中的内容。"""

    if schema_id not in _SCHEMA_IDS or version != "v1":
        raise SchemaViolation("$", "unknown_schema", "unknown AI v2 schema")
    path = Path(__file__).resolve().parents[3] / "config" / "ai_v2" / "schemas" / f"{schema_id}-{version}.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaViolation("$", "schema_unavailable", "AI v2 schema is unavailable") from exc
    if not isinstance(schema, Mapping):
        raise SchemaViolation("$", "schema_invalid", "AI v2 schema must be an object")
    return schema


def _path_property(path: str, name: str) -> str:
    return f"{path}.{name}" if name.replace("_", "").isalnum() else f"{path}[{name!r}]"


def _violate(path: str, reason: str, message: str) -> None:
    raise SchemaViolation(path, reason, message)


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _validate(value: Any, schema: Mapping[str, Any], path: str) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(isinstance(item, str) and _matches_type(value, item) for item in allowed_types):
            _violate(path, "type", f"expected {expected_type}")

    if "enum" in schema and value not in schema["enum"]:
        _violate(path, "enum", "value is not allowed")

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            _violate(path, "min_length", "string is too short")
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            _violate(path, "max_length", "string is too long")

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            _violate(path, "min_items", "array has too few items")
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            _violate(path, "max_items", "array has too many items")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{index}]")

    if isinstance(value, Mapping):
        required = schema.get("required", ())
        if isinstance(required, Sequence) and not isinstance(required, (str, bytes, bytearray)):
            for name in required:
                if name not in value:
                    _violate(_path_property(path, str(name)), "required", "required property is missing")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            properties = {}
        additional_properties = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name not in properties:
                if additional_properties is False:
                    _violate(_path_property(path, str(name)), "additional_property", "property is not allowed")
                continue
            item_schema = properties[name]
            if isinstance(item_schema, Mapping):
                _validate(item, item_schema, _path_property(path, str(name)))


def _validate_carousel_constraints(value: Mapping[str, Any]) -> None:
    items = value.get("items")
    if not isinstance(items, Sequence):
        return
    for item_index, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        frames = item.get("frames")
        execution = item.get("execution")
        prompts = execution.get("image_prompts") if isinstance(execution, Mapping) else None
        if not isinstance(frames, Sequence) or not isinstance(prompts, Sequence):
            continue
        item_path = f"$.items[{item_index}]"
        if len(frames) != len(prompts):
            _violate(
                f"{item_path}.execution.image_prompts",
                "array_length_mismatch",
                "frames and image_prompts must have the same length",
            )
        frame_indexes = [frame.get("index") for frame in frames if isinstance(frame, Mapping)]
        expected_indexes = list(range(1, len(frames) + 1))
        if frame_indexes != expected_indexes:
            for index, (actual, expected) in enumerate(zip(frame_indexes, expected_indexes)):
                if actual != expected:
                    _violate(
                        f"{item_path}.frames[{index}].index",
                        "non_contiguous_index",
                        "frame indexes must be contiguous from 1",
                    )
            _violate(f"{item_path}.frames", "non_contiguous_index", "frame indexes must be contiguous from 1")
        prompt_indexes = [prompt.get("index") for prompt in prompts if isinstance(prompt, Mapping)]
        if prompt_indexes != frame_indexes:
            for index, (actual, expected) in enumerate(zip(prompt_indexes, frame_indexes)):
                if actual != expected:
                    _violate(
                        f"{item_path}.execution.image_prompts[{index}].index",
                        "index_mismatch",
                        "image prompt indexes must match frame indexes",
                    )
            _violate(
                f"{item_path}.execution.image_prompts",
                "index_mismatch",
                "image prompt indexes must match frame indexes",
            )


def validate_json(value: Any, schema: Mapping[str, Any]) -> None:
    """按 v2 schema 子集校验 JSON 值，失败时提供稳定路径和原因。"""

    if not isinstance(schema, Mapping):
        raise SchemaViolation("$", "schema_invalid", "schema must be an object")
    _validate(value, schema, "$")
    if schema.get("x-ai-v2") == "carousel" and isinstance(value, Mapping):
        _validate_carousel_constraints(value)


__all__ = ["SchemaViolation", "load_schema", "validate_json"]

