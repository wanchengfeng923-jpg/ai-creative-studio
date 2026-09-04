"""AI v2 文字/图片供应商端口和私有 typed 请求。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ImageMimeType = Literal["image/png", "image/jpeg", "image/webp"]
UsageSource = Literal["exact", "estimated", "unavailable"]
ReconcileState = Literal["success", "working", "terminal_failure", "unknown"]
SubmissionState = Literal["working", "success", "terminal_failure", "unknown"]


@dataclass(frozen=True)
class TextSession:
    session_id: str
    conversation_id: str
    parent_message_id: str


@dataclass(frozen=True)
class ImageSessionCursor:
    provider: str
    conversation_id: str
    parent_message_id: str
    revision: int


@dataclass(frozen=True)
class ImageArtifact:
    content: bytes
    mime_type: ImageMimeType
    sha256: str


@dataclass(frozen=True)
class ReconcileResult:
    state: ReconcileState
    provider_job_id: str | None
    cursor: ImageSessionCursor | None
    artifact: ImageArtifact | None
    error_code: str | None


@dataclass(frozen=True)
class TextRequest:
    prompt: str
    prompt_id: str
    schema_version: str
    model: str
    idempotency_key: str


@dataclass(frozen=True)
class TextResponse:
    raw_text: str
    session: TextSession
    usage_source: UsageSource


@dataclass(frozen=True)
class ImageRequest:
    scheme_version: str
    frame_index: int
    prompt: str
    image_session_key: str
    request_key: str
    aspect_ratio: str
    reference_artifact: ImageArtifact | None


@dataclass(frozen=True)
class ImageContinuation:
    request: ImageRequest
    cursor: ImageSessionCursor


@dataclass(frozen=True)
class ImageSubmission:
    state: SubmissionState
    provider_job_id: str | None
    cursor: ImageSessionCursor | None
    artifact: ImageArtifact | None
    error_code: str | None


@dataclass(frozen=True)
class ReconcileRequest:
    image_session_key: str
    request_key: str
    cursor: ImageSessionCursor | None
    provider_job_id: str | None


class TextModelPort(Protocol):
    def start_text(self, request: TextRequest) -> TextResponse:
        """创建一次 v2 文字会话并返回整批文字结果。"""


class ImageModelPort(Protocol):
    def start_image_session(self, request: ImageRequest) -> ImageSubmission:
        """为展示方案首次点击创建唯一图片会话。"""

    def continue_image_session(self, request: ImageContinuation) -> ImageSubmission:
        """在已有方案图片会话内继续当前帧。"""

    def reconcile(self, request: ReconcileRequest) -> ReconcileResult:
        """查询供应商稳定键对应的任务状态。"""


__all__ = [
    "ImageArtifact",
    "ImageContinuation",
    "ImageMimeType",
    "ImageModelPort",
    "ImageRequest",
    "ImageSessionCursor",
    "ImageSubmission",
    "ReconcileRequest",
    "ReconcileResult",
    "TextModelPort",
    "TextRequest",
    "TextResponse",
    "TextSession",
]
