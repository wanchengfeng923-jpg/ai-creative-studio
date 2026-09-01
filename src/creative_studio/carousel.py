"""轮播配置规范化与轮次展开的纯函数。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CarouselValidationError(ValueError):
    """轮播配置不完整或不合法。"""


_ROUND_FIELDS = (
    "visual_product_selling_points",
    "visual_display_contents",
    "visual_motif",
)


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _normalize_round_overrides(value: Any) -> dict[str, list[str]]:
    source = value if isinstance(value, Mapping) else {}
    return {key: _clean_list(source.get(key)) for key in _ROUND_FIELDS}


def normalize_visual_carousel_config(
    tags: Mapping[str, Any], *, require_enabled: bool = False
) -> dict[str, Any]:
    source = tags if isinstance(tags, Mapping) else {}
    enabled_values = _clean_list(source.get("visual_carousel"))
    enabled = enabled_values[0] if enabled_values else ""
    if require_enabled and enabled not in {"是", "否"}:
        raise CarouselValidationError("展示类轮播配置缺少是否启用选择")

    count_values = _clean_list(source.get("visual_carousel_count"))
    count_value = count_values[0] if count_values else ""
    if count_value == "AI决定":
        count_mode = "ai"
        count = None
    elif count_value in {"2屏", "3屏", "4屏", "5屏"}:
        count_mode = "fixed"
        count = int(count_value[0])
    else:
        count_mode = ""
        count = None

    rounds = []
    for item in source.get("visual_carousel_rounds") or []:
        if not isinstance(item, Mapping):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        mode = str(item.get("mode") or "").strip()
        if mode not in {"base", "inherit", "custom"}:
            continue
        rounds.append(
            {
                "index": index,
                "mode": mode,
                "overrides": _normalize_round_overrides(item.get("overrides")),
            }
        )

    normalized = {
        "enabled": enabled,
        "count_mode": count_mode,
        "count": count,
        "form": _clean_list(source.get("visual_carousel_form")),
        "rounds": rounds,
    }
    if enabled == "否":
        normalized["hidden"] = True
    return normalized


def expand_visual_carousel_rounds(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    if str(config.get("count_mode") or "").strip() == "ai":
        return []
    count = config.get("count")
    if not isinstance(count, int) or count < 2:
        raise CarouselValidationError("固定轮播数量无效")
    rounds = config.get("rounds")
    if not isinstance(rounds, list):
        raise CarouselValidationError("轮播轮次无效")

    normalized_rounds: dict[int, dict[str, Any]] = {}
    for item in rounds:
        if not isinstance(item, Mapping):
            continue
        index = item.get("index")
        if not isinstance(index, int) or not 1 <= index <= count:
            raise CarouselValidationError("轮播轮次序号无效")
        mode = str(item.get("mode") or "").strip()
        if mode not in {"base", "inherit", "custom"}:
            raise CarouselValidationError("轮播轮次模式无效")
        overrides = item.get("overrides")
        if not isinstance(overrides, Mapping):
            raise CarouselValidationError("轮播轮次覆盖值无效")
        normalized_rounds[index] = {
            "index": index,
            "mode": mode,
            "overrides": {key: _clean_list(overrides.get(key)) for key in _ROUND_FIELDS},
        }

    if 1 not in normalized_rounds:
        raise CarouselValidationError("轮播第1轮缺失")

    expanded: list[dict[str, Any]] = []
    previous: dict[str, list[str]] = {key: [] for key in _ROUND_FIELDS}
    for index in range(1, count + 1):
        round_item = normalized_rounds.get(index)
        if round_item is None:
            raise CarouselValidationError("轮播轮次缺失")
        current = {"index": index}
        for key in _ROUND_FIELDS:
            override_values = round_item["overrides"].get(key, [])
            if index == 1 or round_item["mode"] == "custom":
                values = override_values
            elif round_item["mode"] == "inherit":
                values = override_values or previous[key]
            else:
                values = override_values
            current[key] = list(values) if values else None
            if current[key] is not None:
                previous[key] = list(current[key])
        expanded.append(current)
    return expanded
