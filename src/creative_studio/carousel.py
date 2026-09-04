"""轮播配置规范化与轮次展开的纯函数。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CarouselValidationError(ValueError):
    """轮播配置不完整或不合法。"""

    def __init__(self, message: str, *, field_path: str = "") -> None:
        super().__init__(message)
        self.field_path = str(field_path or "")


_ROUND_FIELDS = (
    "visual_target_audiences",
    "visual_player_desires",
    "visual_product_selling_points",
    "visual_display_contents",
    "visual_motif",
    "visual_dynamics",
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


def normalize_visual_carousel_frames(carousel: Mapping[str, Any]) -> dict[str, Any]:
    source = carousel if isinstance(carousel, Mapping) else {}
    keys = set(source)
    if not {"count", "frames"} <= keys or not keys <= {"count", "form", "frames"}:
        raise CarouselValidationError(
            "AI视觉返回的carousel必须只包含count、form和frames",
            field_path="carousel",
        )

    count = source.get("count")
    if isinstance(count, bool) or not isinstance(count, int):
        raise CarouselValidationError(
            "AI视觉返回的carousel.count必须是有效整数",
            field_path="carousel.count",
        )
    if not 2 <= count <= 5:
        raise CarouselValidationError(
            "AI视觉返回的carousel.count必须在2到5之间",
            field_path="carousel.count",
        )

    form = _clean_list(source.get("form"))
    raw_frames = source.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise CarouselValidationError(
            "AI视觉返回的carousel.frames必须是非空列表",
            field_path="carousel.frames",
        )
    if len(raw_frames) != count:
        raise CarouselValidationError(
            "AI视觉返回的carousel.frames数量必须与count一致",
            field_path="carousel.frames",
        )

    frames: list[dict[str, Any]] = []
    for frame_offset, frame in enumerate(raw_frames):
        expected_index = frame_offset + 1
        frame_path = f"carousel.frames[{frame_offset}]"
        if not isinstance(frame, Mapping):
            raise CarouselValidationError(
                "AI视觉返回的carousel.frames必须是对象列表",
                field_path=frame_path,
            )
        if set(frame) != {"index", "display_description"}:
            raise CarouselValidationError(
                "AI视觉返回的carousel.frames只能包含index和display_description",
                field_path=frame_path,
            )
        index = frame.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise CarouselValidationError(
                "AI视觉返回的carousel.frames.index必须是有效整数",
                field_path=f"{frame_path}.index",
            )
        if index != expected_index:
            raise CarouselValidationError(
                "AI视觉返回的carousel.frames必须是连续的1-based编号",
                field_path=f"{frame_path}.index",
            )
        display_description = str(frame.get("display_description") or "").strip()
        if not display_description:
            raise CarouselValidationError(
                "AI视觉返回的carousel.frames.display_description不能为空",
                field_path=f"{frame_path}.display_description",
            )
        frames.append({"index": index, "display_description": display_description})

    normalized = {"count": count, "frames": frames}
    if form:
        normalized["form"] = form
    return normalized


def normalize_visual_carousel_config(
    tags: Mapping[str, Any], *, require_enabled: bool = False
) -> dict[str, Any]:
    source = tags if isinstance(tags, Mapping) else {}
    enabled_values = _clean_list(source.get("visual_carousel"))
    enabled = enabled_values[0] if enabled_values else ""
    if require_enabled and enabled not in {"是", "否"}:
        raise CarouselValidationError(
            "展示类轮播配置缺少是否启用选择",
            field_path="creative_tags.visual_carousel",
        )

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
        raise CarouselValidationError(
            "固定轮播数量无效",
            field_path="carousel_config.count",
        )
    rounds = config.get("rounds")
    if not isinstance(rounds, list):
        raise CarouselValidationError(
            "轮播轮次无效",
            field_path="carousel_config.rounds",
        )

    normalized_rounds: dict[int, dict[str, Any]] = {}
    for round_offset, item in enumerate(rounds):
        round_path = f"carousel_config.rounds[{round_offset}]"
        if not isinstance(item, Mapping):
            continue
        index = item.get("index")
        if not isinstance(index, int) or not 1 <= index <= count:
            raise CarouselValidationError("轮播轮次序号无效", field_path=f"{round_path}.index")
        mode = str(item.get("mode") or "").strip()
        if mode not in {"base", "inherit", "custom"}:
            raise CarouselValidationError("轮播轮次模式无效", field_path=f"{round_path}.mode")
        overrides = item.get("overrides")
        if not isinstance(overrides, Mapping):
            raise CarouselValidationError(
                "轮播轮次覆盖值无效",
                field_path=f"{round_path}.overrides",
            )
        normalized_rounds[index] = {
            "index": index,
            "mode": mode,
            "overrides": {key: _clean_list(overrides.get(key)) for key in _ROUND_FIELDS},
        }

    if 1 not in normalized_rounds:
        raise CarouselValidationError(
            "轮播第1轮缺失",
            field_path="carousel_config.rounds[0]",
        )

    expanded: list[dict[str, Any]] = []
    base_round = normalized_rounds[1]
    base_values = {
        key: list(base_round["overrides"].get(key, [])) or None
        for key in _ROUND_FIELDS
    }
    for index in range(1, count + 1):
        round_item = normalized_rounds.get(index)
        if round_item is None:
            round_item = {
                "index": index,
                "mode": "inherit",
                "overrides": {key: [] for key in _ROUND_FIELDS},
            }
        current = {"index": index}
        for key in _ROUND_FIELDS:
            override_values = round_item["overrides"].get(key, [])
            if index == 1:
                values = override_values
            elif round_item["mode"] == "custom":
                values = override_values
            elif round_item["mode"] == "inherit":
                values = override_values or base_values[key]
            else:
                values = override_values
            current[key] = list(values) if values else None
        current["mode"] = round_item["mode"] if index in normalized_rounds else "inherit"
        expanded.append(current)
    return expanded
