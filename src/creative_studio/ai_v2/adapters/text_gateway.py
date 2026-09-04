"""Production HTTP transport and typed text adapter for the AI v2 gateway."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from ..model_ports import TextModelPort, TextRequest, TextResponse, TextSession


class TextGatewayError(RuntimeError):
    """The text gateway failed or returned an invalid completion envelope."""


class GatewayHttpTransport:
    """Small authenticated JSON/bytes transport shared by v2 gateway adapters."""

    def __init__(self, *, api_key: str, control_token: str, timeout_seconds: float,
                 request: Callable[..., Any] = requests.request) -> None:
        self.api_key = api_key
        self.control_token = control_token
        self.timeout_seconds = timeout_seconds
        self.request = request

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.api_key}"}
        if self.control_token:
            headers["X-Control-Token"] = self.control_token
        return headers

    @staticmethod
    def _json(response: Any) -> Mapping[str, object]:
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, Mapping):
            raise TextGatewayError("gateway JSON response must be an object")
        return value

    def post_json(self, path: str, payload: Mapping[str, object]) -> Mapping[str, object]:
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        return self._json(self.request("POST", path, headers=headers, json=dict(payload),
                                       timeout=self.timeout_seconds))

    def get_json(self, path: str, params: Mapping[str, object]) -> Mapping[str, object]:
        return self._json(self.request("GET", path, headers=self._headers(), params=dict(params),
                                       timeout=self.timeout_seconds))

    def get_bytes(self, path: str) -> tuple[bytes, str]:
        response = self.request("GET", path, headers=self._headers(), timeout=self.timeout_seconds)
        response.raise_for_status()
        mime_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        return bytes(response.content), mime_type


class TextGatewayAdapter(TextModelPort):
    """Send one typed v2 batch to one Chat Completions request."""

    def __init__(self, transport: Any, *, base_url: str, model: str) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/") + "/"
        self.model = model

    def start_text(self, request: TextRequest) -> TextResponse:
        payload = self.transport.post_json(urljoin(self.base_url, "v1/chat/completions"), {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "response_format": {"type": "json_object"},
            "request_id": request.idempotency_key,
        })
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str) or not content.strip():
            raise TextGatewayError("gateway completion content is missing")
        conversation_id = str(payload.get("conversation_id") or "")
        parent_message_id = str(payload.get("assistant_message_id") or "")
        if not conversation_id or not parent_message_id:
            raise TextGatewayError("gateway completion session is missing")
        usage_source = "exact" if isinstance(payload.get("usage"), Mapping) else "unavailable"
        return TextResponse(content, TextSession(conversation_id, conversation_id, parent_message_id), usage_source)


__all__ = ["GatewayHttpTransport", "TextGatewayAdapter", "TextGatewayError"]
