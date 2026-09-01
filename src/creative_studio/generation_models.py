"""创意生成服务的请求、快照、上下文和结果模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


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
    conversation_id: str
    parent_message_id: str


@dataclass(frozen=True)
class GenerationOutcome:
    """一次生成结束后的公开结果。"""

    history: dict[str, Any]
    snapshot: CreativeInputSnapshot
    context: GenerationContext
    item_ids: tuple[int, ...] = ()
