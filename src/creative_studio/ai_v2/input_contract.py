"""AI v2 三字段输入契约、用例判定和批次 fingerprint。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal


MAX_TASK_DESCRIPTION_LENGTH = 500
ALLOWED_ASPECT_RATIOS = frozenset({"16:9", "9:16"})
_ALLOWED_FIELDS = frozenset({"task_description", "aspect_ratio", "creative_tags"})
_EDITOR_ONLY_TAGS = frozenset({"visual_carousel_rounds"})


class InputContractError(ValueError):
    """输入未满足 AI v2 三字段契约。"""

    def __init__(self, message: str, *, field_path: str = "$", reason_code: str = "invalid_input") -> None:
        super().__init__(message)
        self.field_path = field_path
        self.reason_code = reason_code


@dataclass(frozen=True)
class AiV2Input:
    """经过边界归一化、可安全进入 v2 prompt 的业务输入。"""

    task_description: str
    aspect_ratio: str
    creative_tags: Mapping[str, tuple[str, ...]]


def _raise(message: str, field_path: str, reason_code: str) -> None:
    raise InputContractError(message, field_path=field_path, reason_code=reason_code)


def _normalize_tags(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        _raise("creative_tags must be an object", "$.creative_tags", "invalid_type")

    normalized: dict[str, tuple[str, ...]] = {}
    for raw_key, raw_values in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            _raise("tag group names must be non-empty strings", "$.creative_tags", "invalid_tag_group")
        if raw_key.strip() in _EDITOR_ONLY_TAGS:
            continue
        if isinstance(raw_values, (str, bytes)) or not isinstance(raw_values, Sequence):
            _raise("tag values must be a string sequence", f"$.creative_tags.{raw_key}", "invalid_type")

        seen: set[str] = set()
        values: list[str] = []
        for index, raw_item in enumerate(raw_values):
            if not isinstance(raw_item, str):
                _raise(
                    "tag values must be strings",
                    f"$.creative_tags.{raw_key}[{index}]",
                    "invalid_type",
                )
            item = raw_item.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            values.append(item)
        if values:
            normalized[raw_key.strip()] = tuple(values)
    return normalized


def normalize_input(body: Mapping[str, Any]) -> AiV2Input:
    """校验并归一化 v2 请求，只接受三个业务字段。"""

    if not isinstance(body, Mapping):
        _raise("request body must be an object", "$", "invalid_type")
    unknown = sorted(set(body) - _ALLOWED_FIELDS)
    if unknown:
        _raise(f"unknown v2 input field: {unknown[0]}", f"$.{unknown[0]}", "unknown_field")
    missing = sorted(_ALLOWED_FIELDS - set(body))
    if missing:
        _raise(f"missing v2 input field: {missing[0]}", f"$.{missing[0]}", "missing_field")

    task_description = body["task_description"]
    if not isinstance(task_description, str):
        _raise("task_description must be a string", "$.task_description", "invalid_type")
    task_description = task_description.strip()
    if len(task_description) > MAX_TASK_DESCRIPTION_LENGTH:
        _raise("task_description is too long", "$.task_description", "max_length")

    aspect_ratio = body["aspect_ratio"]
    if not isinstance(aspect_ratio, str):
        _raise("aspect_ratio must be a string", "$.aspect_ratio", "invalid_type")
    aspect_ratio = aspect_ratio.strip()
    if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
        _raise("aspect_ratio must be 16:9 or 9:16", "$.aspect_ratio", "invalid_enum")

    return AiV2Input(task_description, aspect_ratio, _normalize_tags(body["creative_tags"]))


def resolve_use_case(
    project_kind: str,
    tags: Mapping[str, Sequence[str]],
) -> Literal["narrative", "static", "carousel"]:
    """根据已授权项目类型和轮播标签选择唯一 v2 用例。"""

    normalized_kind = str(project_kind or "").strip().lower()
    if normalized_kind in {"narrative", "叙事类", "narrative_text"}:
        return "narrative"
    if normalized_kind not in {"visual", "展示类", "static", "carousel"}:
        _raise("unsupported project kind", "$.project_kind", "unsupported_use_case")

    carousel_values = tags.get("visual_carousel", ())
    if any(str(value).strip() == "是" for value in carousel_values):
        return "carousel"
    return "static"


def fingerprint(value: AiV2Input, use_case: str, *, prompt_version: str) -> str:
    """对归一化输入、用例和 prompt 版本生成稳定 SHA-256 指纹。"""

    canonical = {
        "aspect_ratio": value.aspect_ratio,
        "creative_tags": {
            key: sorted(values) for key, values in sorted(value.creative_tags.items())
        },
        "prompt_version": prompt_version,
        "task_description": value.task_description,
        "use_case": use_case,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ALLOWED_ASPECT_RATIOS",
    "AiV2Input",
    "InputContractError",
    "MAX_TASK_DESCRIPTION_LENGTH",
    "fingerprint",
    "normalize_input",
    "resolve_use_case",
]
