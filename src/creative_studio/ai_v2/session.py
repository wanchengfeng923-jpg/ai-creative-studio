"""AI v2 会话键、图片 attempt 对账辅助类型。"""

from __future__ import annotations

from dataclasses import dataclass

from .model_ports import ImageSessionCursor


@dataclass(frozen=True)
class ImageSessionKey:
    """一个展示方案唯一的供应商图片会话键。"""

    run_id: int | str
    scheme_id: int | str

    @property
    def value(self) -> str:
        return f"{self.run_id}:{self.scheme_id}"


def image_session_key(run_id: int | str, scheme_id: int | str) -> str:
    """生成稳定的方案图片会话键。"""

    return ImageSessionKey(run_id, scheme_id).value


def image_request_key(scheme_version: str, frame_index: int) -> str:
    """生成跨同一逻辑帧重试复用的请求键。"""

    return f"{scheme_version}:frame:{frame_index}"


__all__ = ["ImageSessionCursor", "ImageSessionKey", "image_request_key", "image_session_key"]

