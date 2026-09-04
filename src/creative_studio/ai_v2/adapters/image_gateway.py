"""Typed AI v2 image gateway adapter.

The adapter deliberately knows only the small transport contract below.  It
does not import the legacy image job client or expose provider internals to
the browser-facing layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urljoin

from ..fakes import image_artifact
from ..model_ports import (
    ImageContinuation,
    ImageModelPort,
    ImageRequest,
    ImageSessionCursor,
    ImageSubmission,
    ReconcileRequest,
    ReconcileResult,
)


class ImageGatewayTransport(Protocol):
    def post_json(self, path: str, payload: Mapping[str, object]) -> Mapping[str, object]: ...

    def get_json(self, path: str, params: Mapping[str, object]) -> Mapping[str, object]: ...

    def get_bytes(self, path: str) -> bytes: ...


def _cursor(value: object) -> ImageSessionCursor | None:
    if not isinstance(value, Mapping):
        return None
    provider = str(value.get("provider") or "gateway")
    conversation = str(value.get("conversation_id") or "")
    parent = str(value.get("parent_message_id") or "")
    if not conversation or not parent:
        return None
    try:
        revision = int(value.get("revision") or 0)
    except (TypeError, ValueError):
        return None
    return ImageSessionCursor(provider, conversation, parent, revision)


class ImageGatewayAdapter(ImageModelPort):
    """Translate v2 image operations to a minimal JSON gateway protocol."""

    def __init__(self, transport: ImageGatewayTransport, *, base_url: str) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/") + "/"

    def _path(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    @staticmethod
    def _payload(request: ImageRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "scheme_version": request.scheme_version,
            "frame_index": request.frame_index,
            "image_session_key": request.image_session_key,
            "request_key": request.request_key,
            "aspect_ratio": request.aspect_ratio,
            "prompt": request.prompt,
        }
        if request.reference_artifact is not None:
            payload["reference_image_sha256"] = request.reference_artifact.sha256
            payload["reference_image_mime"] = request.reference_artifact.mime_type
            payload["reference_image_bytes"] = request.reference_artifact.content
        return payload

    def _submission(self, payload: Mapping[str, object]) -> ImageSubmission:
        state = str(payload.get("state") or "unknown")
        if state not in {"working", "success", "terminal_failure", "unknown"}:
            state = "unknown"
        cursor = _cursor(payload.get("cursor"))
        artifact = None
        if state == "success":
            image_url = payload.get("image_url") or payload.get("artifact_url")
            mime = str(payload.get("mime_type") or "")
            if image_url and mime in {"image/png", "image/jpeg", "image/webp"}:
                content = self.transport.get_bytes(self._path(str(image_url)))
                artifact = image_artifact(content, mime)
            else:
                state = "unknown"
        return ImageSubmission(
            state,  # type: ignore[arg-type]
            str(payload.get("job_id") or payload.get("provider_job_id") or "") or None,
            cursor,
            artifact,
            str(payload.get("error_code") or "") or None,
        )

    def start_image_session(self, request: ImageRequest) -> ImageSubmission:
        return self._submission(self.transport.post_json(self._path("api/v2/image-sessions/start"), self._payload(request)))

    def continue_image_session(self, request: ImageContinuation) -> ImageSubmission:
        payload = self._payload(request.request)
        payload["cursor"] = {
            "provider": request.cursor.provider,
            "conversation_id": request.cursor.conversation_id,
            "parent_message_id": request.cursor.parent_message_id,
            "revision": request.cursor.revision,
        }
        return self._submission(self.transport.post_json(self._path("api/v2/image-sessions/continue"), payload))

    def reconcile(self, request: ReconcileRequest) -> ReconcileResult:
        params: dict[str, object] = {
            "image_session_key": request.image_session_key,
            "request_key": request.request_key,
        }
        if request.provider_job_id:
            params["provider_job_id"] = request.provider_job_id
        if request.cursor is not None:
            params["conversation_id"] = request.cursor.conversation_id
            params["parent_message_id"] = request.cursor.parent_message_id
            params["revision"] = request.cursor.revision
        try:
            payload = self.transport.get_json(self._path("api/v2/image-sessions/reconcile"), params)
        except Exception:
            return ReconcileResult("unknown", request.provider_job_id, request.cursor, None, "provider_unavailable")
        state = str(payload.get("state") or "unknown")
        if state not in {"success", "working", "terminal_failure", "unknown"}:
            state = "unknown"
        submission = self._submission(payload)
        if state == "success" and submission.state == "success":
            return ReconcileResult("success", submission.provider_job_id, submission.cursor, submission.artifact, submission.error_code)
        if state == "working":
            return ReconcileResult("working", submission.provider_job_id, submission.cursor or request.cursor, None, submission.error_code)
        if state == "terminal_failure":
            return ReconcileResult("terminal_failure", submission.provider_job_id, submission.cursor or request.cursor, None, submission.error_code)
        return ReconcileResult("unknown", submission.provider_job_id or request.provider_job_id, submission.cursor or request.cursor, None, submission.error_code or "provider_state_unknown")


__all__ = ["ImageGatewayAdapter", "ImageGatewayTransport"]
