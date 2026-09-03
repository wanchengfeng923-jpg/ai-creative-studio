"""Phase 1 的显式 contract、validator、projector 和 caller allowlist。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ContractBinding:
    input_schema: str
    output_schema: str
    validator: str
    public_projector: str
    production_caller: str


CONTRACT_BINDINGS: Mapping[str, ContractBinding] = {
    "creative.narrative.generate": ContractBinding(
        "NarrativePromptInput.v1", "NarrativeResult.v1", "NarrativeResultValidator.v1", "NarrativePublicDTO.v1", "narrative",
    ),
    "creative.visual.static.generate": ContractBinding(
        "StaticVisualPromptInput.v1", "LegacyStaticVisualResult.v2.3", "StaticVisualResultValidator.v2.3", "StaticVisualPublicDTO.v1", "static",
    ),
    "creative.visual.carousel.plan": ContractBinding(
        "CarouselPromptInput.v1", "LegacyCarouselPlanResult.v1", "CarouselPlanValidator.v1", "CarouselPublicDTO.v1", "carousel",
    ),
}

SCHEMA_IDS = frozenset({
    "NarrativePromptInput.v1", "NarrativeResult.v1", "StaticVisualPromptInput.v1",
    "LegacyStaticVisualResult.v2.3", "CarouselPromptInput.v1", "LegacyCarouselPlanResult.v1",
})
VALIDATOR_IDS = frozenset(binding.validator for binding in CONTRACT_BINDINGS.values()) | {"NarrativeResultValidator.v5"}
PROJECTOR_IDS = frozenset(binding.public_projector for binding in CONTRACT_BINDINGS.values())


def contract_binding(prompt_id: str) -> ContractBinding | None:
    """按稳定 prompt ID 查询显式 contract 绑定。"""

    return CONTRACT_BINDINGS.get(prompt_id)


def validate_contract_ids(binding: Mapping[str, Any]) -> None:
    """拒绝未登记的 schema、validator 或 projector ID。"""

    required = ("input_schema", "output_schema", "validator", "public_dto")
    for key in required:
        value = str(binding.get(key) or "")
        allowed = SCHEMA_IDS if "schema" in key else VALIDATOR_IDS if key == "validator" else PROJECTOR_IDS
        if value not in allowed:
            raise ValueError(f"unknown {key}: {value}")


__all__ = ["CONTRACT_BINDINGS", "ContractBinding", "contract_binding", "validate_contract_ids"]
