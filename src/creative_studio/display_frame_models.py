"""展示类连续画面的不可变领域对象。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .generation_models import GenerationInputError


def validate_frame_count(mode: str, requested: int | None, actual: int) -> int:
    """校验并返回方案锁定的画面数量。"""

    normalized_mode = str(mode or "").strip().lower()
    count = int(actual)
    if normalized_mode == "none":
        if count != 1:
            raise GenerationInputError("不轮播方案必须只有1张画面")
        return count
    if normalized_mode == "fixed":
        if requested not in range(2, 6) or count != int(requested):
            raise GenerationInputError("固定轮播数量必须为2至5张")
        return count
    if normalized_mode == "ai" and count in range(2, 6):
        return count
    raise GenerationInputError("轮播数量必须为2至5张")


@dataclass(frozen=True)
class PlannedFrame:
    index: int
    description: str


@dataclass(frozen=True)
class CompletedFrame:
    index: int
    planned_content: str
    actual_content: str = ""
    transition_from_previous: str = ""
    transition_to_next: str | None = None
    ending_note: str | None = None
    image_status: str = "pending"
    image_path: str = ""
    image_generation_instruction: str = ""
    attempt: int = 0
    failure_code: str = ""
    failure_message: str = ""


@dataclass(frozen=True)
class DisplayScheme:
    scheme_id: int
    title: str
    creative_summary: str
    creative_sources: tuple[str, ...]
    frame_count: int
    visual_continuity_rules: tuple[str, ...]
    frame_plan: tuple[PlannedFrame, ...]
    frames: tuple[CompletedFrame, ...]
    # Keep the complete visual brief available when a later frame is generated.
    core_subject: str = ""
    layout: str = ""
    visual_style: str = ""
    content_extensions: tuple[str, ...] = ()
    reference_sources: tuple[Mapping[str, Any], ...] = ()
    keywords: tuple[str, ...] = ()
    conversation_id: str = ""
    parent_message_id: str = ""
    scheme_status: str = "ready"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], scheme_id: int = 0) -> "DisplayScheme":
        """从首帧模型结果构造并锁定一套方案。"""

        frame_count = int(payload.get("frame_count") or 0)
        raw_plan = payload.get("frame_plan")
        if not isinstance(raw_plan, list) or len(raw_plan) != frame_count:
            raise GenerationInputError("画面路线数量与方案数量不一致")
        plan: list[PlannedFrame] = []
        frames: list[CompletedFrame] = []
        for expected_index, raw_frame in enumerate(raw_plan, start=1):
            if not isinstance(raw_frame, Mapping) or int(raw_frame.get("index") or 0) != expected_index:
                raise GenerationInputError("画面路线序号必须从1连续递增")
            description = str(raw_frame.get("description") or raw_frame.get("content") or "").strip()
            if not description:
                raise GenerationInputError("画面路线内容不能为空")
            plan.append(PlannedFrame(index=expected_index, description=description))
            frames.append(CompletedFrame(index=expected_index, planned_content=description))
        first_frame = payload.get("first_frame")
        if isinstance(first_frame, Mapping):
            if int(first_frame.get("index") or 0) != 1:
                raise GenerationInputError("首帧序号必须为1")
            first_content = str(first_frame.get("content") or "").strip()
            instruction = str(first_frame.get("image_generation_instruction") or "").strip()
            if not first_content or not instruction:
                raise GenerationInputError("首帧内容和图片指令不能为空")
            frames[0] = CompletedFrame(
                index=1,
                planned_content=frames[0].planned_content,
                actual_content=first_content,
                image_generation_instruction=instruction,
            )
        return cls(
            scheme_id=int(scheme_id),
            title=str(payload.get("title") or "").strip(),
            creative_summary=str(payload.get("creative_summary") or payload.get("creative_description") or "").strip(),
            creative_sources=tuple(str(item).strip() for item in payload.get("creative_sources", []) if str(item).strip()),
            frame_count=frame_count,
            visual_continuity_rules=tuple(
                str(item).strip() for item in payload.get("visual_continuity_rules", []) if str(item).strip()
            ),
            frame_plan=tuple(plan),
            frames=tuple(frames),
            core_subject=str(payload.get("core_subject") or "").strip(),
            layout=str(payload.get("layout") or "").strip(),
            visual_style=str(payload.get("visual_style") or "").strip(),
            content_extensions=tuple(
                str(item).strip() for item in payload.get("content_extensions", []) if str(item).strip()
            ),
            reference_sources=tuple(
                dict(item) for item in payload.get("reference_sources", []) if isinstance(item, Mapping)
            ),
            keywords=tuple(str(item).strip() for item in payload.get("keywords", []) if str(item).strip()),
        )


def next_frame_index(frames: Sequence[CompletedFrame]) -> int | None:
    """返回第一个尚未成功的画面序号；全部成功时返回 ``None``。"""

    for frame in sorted(frames, key=lambda item: item.index):
        if frame.image_status != "success":
            return frame.index
    return None


__all__ = [
    "CompletedFrame",
    "DisplayScheme",
    "PlannedFrame",
    "next_frame_index",
    "validate_frame_count",
]
