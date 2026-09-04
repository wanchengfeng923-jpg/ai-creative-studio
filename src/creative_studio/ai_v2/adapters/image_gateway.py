"""Typed AI v2 adapter for the existing asynchronous image job gateway."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from ..model_ports import (
    ImageArtifact,
    ImageContinuation,
    ImageModelPort,
    ImageRequest,
    ImageSessionCursor,
    ImageSubmission,
    ReconcileRequest,
    ReconcileResult,
)


_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class ImageGatewayTransport(Protocol):
    def post_json(self, path: str, payload: Mapping[str, object]) -> Mapping[str, object]: ...
    def get_json(self, path: str, params: Mapping[str, object]) -> Mapping[str, object]: ...
    def get_bytes(self, path: str) -> tuple[bytes, str]: ...


class ImageGatewayAdapter(ImageModelPort):
    """Translate v2 image operations to `/v1/images/jobs`."""

    def __init__(self, transport: ImageGatewayTransport, *, base_url: str) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/") + "/"

    def _path(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    @staticmethod
    def _request_payload(request: ImageRequest) -> dict[str, object]:
        return {
            "request_id": request.request_key,
            "image_session_key": request.image_session_key,
            "request_key": request.request_key,
            "scheme_version": request.scheme_version,
            "frame_index": request.frame_index,
            "prompt": request.prompt,
            "aspect_ratio": request.aspect_ratio,
        }

    @staticmethod
    def _state(payload: Mapping[str, object]) -> str:
        status = str(payload.get("status") or payload.get("state") or "").lower()
        if status in {"queued", "generating", "working"}:
            return "working"
        if status == "success":
            return "success"
        if status in {"failed", "terminal_failure"}:
            return "terminal_failure"
        return "unknown"

    def _safe_image_url(self, value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = self._path(value)
        base = urlsplit(self.base_url)
        target = urlsplit(candidate)
        exact = (target.scheme, target.hostname, target.port) == (base.scheme, base.hostname, base.port)
        loopback = (target.scheme == base.scheme and target.port == base.port
                    and target.hostname in _LOOPBACK_HOSTS and base.hostname in _LOOPBACK_HOSTS)
        if target.username or target.password or not (exact or loopback):
            return None
        return candidate

    def _artifact(self, payload: Mapping[str, object]) -> ImageArtifact | None:
        image_url = self._safe_image_url(payload.get("image_url"))
        if image_url is None:
            return None
        downloaded = self.transport.get_bytes(image_url)
        if not isinstance(downloaded, tuple) or len(downloaded) != 2:
            return None
        content, mime_type = downloaded
        normalized = str(mime_type).split(";", 1)[0].strip().lower()
        if not isinstance(content, bytes) or not content or normalized not in _IMAGE_MIME_TYPES:
            return None
        return ImageArtifact(content, normalized, hashlib.sha256(content).hexdigest())  # type: ignore[arg-type]

    @staticmethod
    def _cursor(payload: Mapping[str, object], previous: ImageSessionCursor | None) -> ImageSessionCursor | None:
        conversation_id = str(payload.get("conversation_id") or "")
        parent_message_id = str(payload.get("parent_message_id") or "")
        if not conversation_id or not parent_message_id:
            return previous
        revision = previous.revision + 1 if previous is not None else 1
        return ImageSessionCursor("chat2api", conversation_id, parent_message_id, revision)

    def _submit(self, payload: dict[str, object]) -> ImageSubmission:
        try:
            response = self.transport.post_json(self._path("v1/images/jobs"), payload)
        except Exception:
            return ImageSubmission("unknown", None, None, None, "provider_unavailable")
        state = self._state(response)
        job_id = str(response.get("job_id") or "") or None
        if state == "success":
            try:
                artifact = self._artifact(response)
            except Exception:
                artifact = None
            cursor = self._cursor(response, None)
            if artifact is None or cursor is None:
                return ImageSubmission("unknown", job_id, None, None, "provider_protocol_invalid")
            return ImageSubmission("success", job_id, cursor, artifact, None)
        return ImageSubmission(state, job_id, None, None, None)  # type: ignore[arg-type]

    def start_image_session(self, request: ImageRequest) -> ImageSubmission:
        return self._submit(self._request_payload(request))

    def continue_image_session(self, request: ImageContinuation) -> ImageSubmission:
        payload = self._request_payload(request.request)
        payload.update({
            "conversation_id": request.cursor.conversation_id,
            "parent_message_id": request.cursor.parent_message_id,
            "cursor": {
                "provider": request.cursor.provider,
                "conversation_id": request.cursor.conversation_id,
                "parent_message_id": request.cursor.parent_message_id,
                "revision": request.cursor.revision,
            },
        })
        reference = request.request.reference_artifact
        if reference is not None:
            payload["image"] = (
                f"data:{reference.mime_type};base64,"
                f"{base64.b64encode(reference.content).decode('ascii')}"
            )
        return self._submit(payload)

    def reconcile(self, request: ReconcileRequest) -> ReconcileResult:
        if not request.provider_job_id:
            return ReconcileResult("unknown", None, request.cursor, None, "provider_state_unknown")
        try:
            payload = self.transport.get_json(
                self._path(f"v1/images/jobs/{request.provider_job_id}"),
                {"image_session_key": request.image_session_key, "request_key": request.request_key},
            )
            state = self._state(payload)
            cursor = self._cursor(payload, request.cursor)
            job_id = str(payload.get("job_id") or request.provider_job_id)
            if state == "success":
                artifact = self._artifact(payload)
                if artifact is None or cursor is None:
                    return ReconcileResult("unknown", job_id, request.cursor, None, "provider_protocol_invalid")
                return ReconcileResult("success", job_id, cursor, artifact, None)
            if state == "working":
                return ReconcileResult("working", job_id, cursor, None, None)
            if state == "terminal_failure":
                return ReconcileResult("terminal_failure", job_id, cursor, None, "image_generation_failed")
            return ReconcileResult("unknown", job_id, cursor, None, "provider_state_unknown")
        except Exception:
            return ReconcileResult("unknown", request.provider_job_id, request.cursor, None, "provider_unavailable")


__all__ = ["ImageGatewayAdapter", "ImageGatewayTransport"]
