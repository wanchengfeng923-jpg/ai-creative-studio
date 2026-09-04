"""不联网、不读取凭据的 AI v2 deterministic fake adapters。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from .model_ports import (
    ImageArtifact,
    ImageContinuation,
    ImageModelPort,
    ImageRequest,
    ImageSessionCursor,
    ImageSubmission,
    ReconcileRequest,
    ReconcileResult,
    TextModelPort,
    TextRequest,
    TextResponse,
    TextSession,
)


def image_artifact(content: bytes, mime_type: str) -> ImageArtifact:
    """构造带真实 MIME 和摘要的 deterministic 图片 artifact。"""

    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("unsupported image MIME")
    return ImageArtifact(content, mime_type, hashlib.sha256(content).hexdigest())  # type: ignore[arg-type]


class DeterministicTextModel(TextModelPort):
    """按调用顺序返回固定文字，不执行网络或环境访问。"""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self.start_calls: list[TextRequest] = []

    def start_text(self, request: TextRequest) -> TextResponse:
        self.start_calls.append(request)
        response_index = len(self.start_calls) - 1
        raw_text = self._responses[response_index] if response_index < len(self._responses) else "{}"
        session_number = len(self.start_calls)
        return TextResponse(
            raw_text=raw_text,
            session=TextSession(
                session_id=f"text-session-{session_number}",
                conversation_id=f"text-conversation-{session_number}",
                parent_message_id=f"text-message-{session_number}",
            ),
            usage_source="unavailable",
        )


class DeterministicImageModel(ImageModelPort):
    """记录图片会话/继续/对账调用并支持按请求键编程状态。"""

    def __init__(
        self,
        *,
        start_submissions: Mapping[str, ImageSubmission] | None = None,
        continue_submissions: Mapping[str, ImageSubmission] | None = None,
        reconcile_results: Mapping[str, ReconcileResult] | None = None,
    ) -> None:
        self._start_submissions = dict(start_submissions or {})
        self._continue_submissions = dict(continue_submissions or {})
        self._reconcile_results = dict(reconcile_results or {})
        self.start_calls: list[ImageRequest] = []
        self.continue_calls: list[ImageContinuation] = []
        self.reconcile_calls: list[ReconcileRequest] = []
        self.created_image_sessions: list[str] = []

    def _default_cursor(self, request: ImageRequest, revision: int = 0) -> ImageSessionCursor:
        return ImageSessionCursor("deterministic", request.image_session_key, request.request_key, revision)

    def start_image_session(self, request: ImageRequest) -> ImageSubmission:
        if request.image_session_key in self.created_image_sessions:
            raise AssertionError("image session created twice")
        self.created_image_sessions.append(request.image_session_key)
        self.start_calls.append(request)
        configured = self._start_submissions.get(request.request_key)
        if configured is not None:
            return configured
        return ImageSubmission("working", f"job-{len(self.start_calls)}", self._default_cursor(request), None, None)

    def continue_image_session(self, request: ImageContinuation) -> ImageSubmission:
        self.continue_calls.append(request)
        configured = self._continue_submissions.get(request.request.request_key)
        if configured is not None:
            return configured
        cursor = ImageSessionCursor(
            request.cursor.provider,
            request.cursor.conversation_id,
            request.request.request_key,
            request.cursor.revision + 1,
        )
        return ImageSubmission("working", f"job-{len(self.continue_calls)}", cursor, None, None)

    def reconcile(self, request: ReconcileRequest) -> ReconcileResult:
        self.reconcile_calls.append(request)
        return self._reconcile_results.get(
            request.request_key,
            ReconcileResult("unknown", request.provider_job_id, request.cursor, None, "unknown_provider_state"),
        )


__all__ = ["DeterministicImageModel", "DeterministicTextModel", "image_artifact"]

