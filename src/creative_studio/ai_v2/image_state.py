"""AI v2 图片状态机纯函数。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal


ImageStatus = Literal["pending", "generating", "success", "failed"]
ImageEvent = Literal["start", "success", "failure", "retry"]


class ImageStateConflict(ValueError):
    """图片状态不允许当前操作。"""

    def __init__(self, error_code: str, message: str | None = None) -> None:
        self.error_code = error_code
        super().__init__(message or error_code)


def can_start_static(status: str) -> bool:
    """静态图片只可从 pending 或 failed 开始一次尝试。"""

    return status in {"pending", "failed"}


def can_start_frame(states: Sequence[str], frame_index: int) -> bool:
    """轮播仅在当前帧可重试且此前所有帧成功时允许开始。"""

    if frame_index < 1 or frame_index > len(states):
        return False
    current = states[frame_index - 1]
    if current not in {"pending", "failed"}:
        return False
    return all(status == "success" for status in states[: frame_index - 1])


def transition(status: str, event: ImageEvent) -> ImageStatus:
    """执行一个显式图片状态迁移，拒绝隐式或越序转换。"""

    transitions: dict[tuple[str, str], ImageStatus] = {
        ("pending", "start"): "generating",
        ("generating", "success"): "success",
        ("generating", "failure"): "failed",
        ("failed", "retry"): "generating",
    }
    if status == "success" and event == "start":
        raise ImageStateConflict("image_already_successful", "successful image is locked")
    try:
        return transitions[(status, event)]
    except KeyError as exc:
        raise ImageStateConflict("invalid_image_transition", "image state transition is not allowed") from exc


def stable_image_key(scheme_version: str, frame_index: int) -> str:
    """生成同一逻辑帧跨 attempt 重试复用的稳定键。"""

    if not isinstance(scheme_version, str) or not scheme_version.strip() or frame_index < 1:
        raise ImageStateConflict("invalid_image_key", "scheme version and frame index are required")
    return f"{scheme_version}:frame:{frame_index}"


__all__ = ["ImageStateConflict", "can_start_frame", "can_start_static", "stable_image_key", "transition"]
