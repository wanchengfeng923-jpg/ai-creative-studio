"""创意生成服务的请求、快照、上下文和结果模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


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


class ReferenceAssetError(GenerationError):
    """参考资料无法安全读取或已与登记摘要不一致。"""

    error_code = "reference_asset_invalid"
    phase = "reference_asset"


@dataclass(frozen=True)
class ReferenceAsset:
    """项目参考资料的非敏感 metadata；绝不包含本地绝对路径。"""

    asset_id: int
    project_id: int
    original_name: str
    sha256: str
    mime_type: str
    size_bytes: int
    extraction_status: str = "pending"
    safe_summary: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class ReferenceAssetContent:
    """供 prompt compiler 使用的受控资料内容。"""

    asset: ReferenceAsset
    text: str = ""
    truncated: bool = False


class ReferenceAssetPort(Protocol):
    """参考资料读取 seam；实现必须检查项目归属和文件路径。"""

    def list_for_project(self, project_id: int) -> tuple[ReferenceAsset, ...]: ...

    def read(self, project_id: int, asset_id: int, *, max_bytes: int = 64_000) -> ReferenceAssetContent: ...


@dataclass(frozen=True)
class GenerationRun:
    """一次生成请求的权威、可追溯运行记录。"""

    run_id: int
    project_id: int
    kind: str
    batch_index: int
    status: str
    schema_version: str
    input_fingerprint: str
    request_id: str
    context: Mapping[str, Any]
    conversation_id: str = ""
    assistant_message_id: str = ""
    usage: Mapping[str, Any] = field(default_factory=dict)
    error: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    prompt_id: str = ""
    prompt_version: str = ""
    prompt_hash: str = ""
    input_schema_version: str = ""
    output_schema_version: str = ""
    model: str = ""
    provider: str = ""
    tag_catalog_version: str = ""
    reference_version: str = ""


class RunStorePort(Protocol):
    """生成运行的业务持久化 seam。"""

    def reserve_run(
        self,
        project_id: int,
        kind: str,
        schema_version: str,
        fingerprint: str,
        *,
        context: Mapping[str, Any] | None = None,
        request_id: str = "",
    ) -> GenerationRun: ...

    def get_run(self, run_id: int) -> GenerationRun | None: ...

    def complete_run(self, run_id: int, result: Any, *, aspect_ratio: str = "16:9") -> Sequence[int]: ...

    def complete_static_run(self, run_id: int, result: Any, *, aspect_ratio: str = "16:9") -> Sequence[int]: ...

    def fail_run(self, run_id: int, failure: Mapping[str, Any]) -> None: ...


class ObservabilityPort(Protocol):
    """只记录脱敏 trace/metrics 的可替换接口。"""

    def record(self, event: Mapping[str, Any]) -> None: ...


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
    reference_assets: tuple[ReferenceAsset, ...] = ()


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
