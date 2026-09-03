"""Generic model client boundary used by creative generation."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

import requests


class ModelResponseFormatError(ValueError):
    """The provider response does not match the chat completion envelope."""

    error_code = "model_output_invalid"
    phase = "validation"
    retryable = False

    def __init__(self, message: str, *, field_path: str) -> None:
        super().__init__(message)
        self.field_path = field_path


@dataclass(frozen=True)
class ModelRequest:
    model: str
    messages: list[Mapping[str, str]]
    response_format: Mapping[str, Any] | None
    max_tokens: int
    conversation_id: str = ""
    parent_message_id: str = ""


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    conversation_id: str = ""
    assistant_message_id: str = ""
    latency_ms: int = 0


@runtime_checkable
class ModelClient(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse:
        ...


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _extract_usage(payload: Mapping[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return None, None, None
    input_tokens = _optional_nonnegative_int(usage.get("prompt_tokens", usage.get("input_tokens")))
    output_tokens = _optional_nonnegative_int(usage.get("completion_tokens", usage.get("output_tokens")))
    total_tokens = _optional_nonnegative_int(usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _first_message_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelResponseFormatError(
            "AI返回结果缺少choices",
            field_path="choices",
        )
    first = choices[0]
    if not isinstance(first, Mapping):
        raise ModelResponseFormatError(
            "AI返回结果缺少正文",
            field_path="choices[0].message.content",
        )
    message = first.get("message")
    if not isinstance(message, Mapping):
        raise ModelResponseFormatError(
            "AI返回结果缺少正文",
            field_path="choices[0].message.content",
        )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ModelResponseFormatError(
            "AI返回结果缺少正文",
            field_path="choices[0].message.content",
        )
    return content


@dataclass
class HttpModelClient:
    api_url: str
    api_key: str
    transport: Callable[..., Any] = requests.post
    timeout_seconds: float = 60.0

    def generate(self, request: ModelRequest) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": list(request.messages),
            "response_format": request.response_format,
            "max_tokens": request.max_tokens,
            "conversation_id": request.conversation_id,
            "parent_message_id": request.parent_message_id,
        }
        started_at = perf_counter()
        response = self.transport(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        try:
            response_payload = response.json()
        except (TypeError, ValueError) as exc:
            raise ModelResponseFormatError(
                "AI返回结果无法解析",
                field_path="$",
            ) from exc
        if not isinstance(response_payload, Mapping):
            raise ModelResponseFormatError(
                "AI返回结果必须是对象",
                field_path="$",
            )
        input_tokens, output_tokens, total_tokens = _extract_usage(response_payload)
        return ModelResponse(
            content=_first_message_content(response_payload),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            conversation_id=str(response_payload.get("conversation_id") or ""),
            assistant_message_id=str(response_payload.get("assistant_message_id") or ""),
            latency_ms=max(0, round((perf_counter() - started_at) * 1000)),
        )


__all__ = [
    "HttpModelClient",
    "ModelClient",
    "ModelRequest",
    "ModelResponse",
    "ModelResponseFormatError",
]
