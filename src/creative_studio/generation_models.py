"""创意生成服务的请求、快照、上下文和结果模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Mapping


class GenerationError(RuntimeError):
    """Base class for generation-specific domain errors."""

    error_code = "generation_failed"
    phase = "generation"
    field_path = ""
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        phase: str | None = None,
        field_path: str = "",
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = str(error_code or self.__class__.error_code)
        self.phase = str(phase or self.__class__.phase)
        self.field_path = str(field_path or self.__class__.field_path)
        self.retryable = self.__class__.retryable if retryable is None else bool(retryable)


class GenerationInputError(GenerationError):
    """The user must change the submitted input."""

    error_code = "generation_input_invalid"
    phase = "input_validation"


class GenerationNotFoundError(GenerationError):
    """The requested project or generation resource does not exist."""

    error_code = "generation_not_found"
    phase = "lookup"


class GenerationConflictError(GenerationError):
    """The generation request conflicts with an active state."""

    error_code = "generation_conflict"
    phase = "reservation"


class GenerationQueueTimeoutError(GenerationError):
    """The upstream queue did not accept the request in time."""

    error_code = "generation_queue_timeout"
    phase = "model_request"
    retryable = True


@dataclass(frozen=True)
class ErrorDetails:
    error_code: str
    phase: str
    field_path: str
    retryable: bool
    trace_id: str

    def public_fields(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "phase": self.phase,
            "field_path": self.field_path,
            "retryable": self.retryable,
            "trace_id": self.trace_id,
        }


def error_details(exc: BaseException, *, trace_id: str = "") -> ErrorDetails:
    """Normalize an exception into stable public and persisted error metadata."""

    return ErrorDetails(
        error_code=str(getattr(exc, "error_code", "generation_failed") or "generation_failed"),
        phase=str(getattr(exc, "phase", "generation") or "generation"),
        field_path=str(getattr(exc, "field_path", "") or ""),
        retryable=bool(getattr(exc, "retryable", False)),
        trace_id=str(trace_id or getattr(exc, "trace_id", "") or uuid.uuid4().hex),
    )


@dataclass(frozen=True)
class CreativeGenerationRequest:
    """一次创意生成所需的 HTTP 级请求。"""

    project_id: int


@dataclass(frozen=True)
class CreativeInputSnapshot:
    """归一化后的生成输入快照。"""

    project_id: int
    kind: str
    schema_version: str
    fingerprint: str
    script_type: str
    task_type: str
    task_description: str
    product_evidence_summary: str
    aspect_ratio: str
    creative_tags: Mapping[str, tuple[str, ...]]
    carousel_config: Mapping[str, Any] | None
    carousel_enabled: bool
    reference_file_names: tuple[str, ...]


@dataclass(frozen=True)
class GenerationContext:
    """生成过程中的持久化上下文。"""

    reservation_id: int
    batch_index: int
    schema_version: str
    request_id: str
    context_json: Mapping[str, Any]
    conversation_id: str
    parent_message_id: str


@dataclass(frozen=True)
class GenerationOutcome:
    """一次生成结束后的公开结果。"""

    history: dict[str, Any]
    snapshot: CreativeInputSnapshot
    context: GenerationContext
    item_ids: tuple[int, ...] = ()
