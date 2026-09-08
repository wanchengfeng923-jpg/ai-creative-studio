"""独立的 AI v2 production readiness contract gate。"""

from __future__ import annotations

import ast
import json
import argparse
from pathlib import Path
from typing import Any

from .prompt_registry import AiV2PromptRegistry, AiV2PromptRegistryError


class ProductionGateError(ValueError):
    """生产 registry 或正式 caller 不满足 readiness contract。"""


_PROMPT_USE_CASES = {
    "creative.ai_v2.narrative": "narrative",
    "creative.ai_v2.static": "static",
    "creative.ai_v2.carousel": "carousel",
}
_CALLER_TYPES = {
    "narrative": "creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate",
    "static": "creative_studio.ai_v2.static_visual.StaticTextUseCase.generate",
    "carousel": "creative_studio.ai_v2.carousel_visual.CarouselTextUseCase.generate",
}
_OUTPUT_SCHEMAS = {
    "narrative": "narrative-text-v1",
    "static": "static-text-v1",
    "carousel": "carousel-text-v1",
}


def _composition_root_exists(root: Path) -> bool:
    module_path = root / "src" / "creative_studio" / "app.py"
    if not module_path.is_file():
        return False
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    has_application_import = any(
        isinstance(node, ast.ImportFrom)
        and node.module in {"creative_studio.ai_v2.application", "ai_v2.application"}
        and any(alias.name == "AiV2Application" for alias in node.names)
        for node in tree.body
    )
    has_factory = any(
        isinstance(node, ast.FunctionDef)
        and node.name == "create_application"
        and any(isinstance(child, ast.FunctionDef) and child.name == "create_ai_v2_application" for child in node.body)
        for node in tree.body
    )
    return has_application_import and has_factory


def _caller_exists(root: Path, caller: str) -> bool:
    parts = caller.split(".")
    if len(parts) != 5 or parts[:3] != ["creative_studio", "ai_v2", parts[2]]:
        return False
    module_path = root / "src" / Path(*parts[:3]).with_suffix(".py")
    if not module_path.is_file():
        return False
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == parts[3]:
            return any(isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == parts[4] for child in node.body)
    return False


def _registry_path(path: Path) -> Path:
    return path.resolve()


def build_production_readiness_evidence(root: Path, registry_path: Path | str) -> dict[str, Any]:
    """Validate a production registry without contacting models or writing runtime data."""

    root = Path(root).resolve()
    if not _composition_root_exists(root):
        raise ProductionGateError("composition root does not expose create_ai_v2_application")
    try:
        registry = AiV2PromptRegistry(_registry_path(Path(registry_path)))
    except AiV2PromptRegistryError as exc:
        raise ProductionGateError(str(exc)) from exc

    entries = []
    for prompt_id, use_case in _PROMPT_USE_CASES.items():
        try:
            spec = registry.get(prompt_id, "v1")
        except AiV2PromptRegistryError as exc:
            raise ProductionGateError(f"missing production prompt: {prompt_id}") from exc
        if spec.lifecycle != "production":
            raise ProductionGateError(f"lifecycle for {prompt_id} must be production")
        if spec.caller != _CALLER_TYPES[use_case]:
            raise ProductionGateError(f"caller for {prompt_id} is not the canonical caller")
        if spec.output_schema != _OUTPUT_SCHEMAS[use_case]:
            raise ProductionGateError(f"output schema for {prompt_id} does not match its use case")
        if spec.max_model_calls != 1:
            raise ProductionGateError(f"production prompt {prompt_id} must allow exactly one call")
        if not _caller_exists(root, spec.caller):
            raise ProductionGateError(f"caller for {prompt_id} is not reachable")
        entries.append({
            "prompt_id": spec.prompt_id,
            "version": spec.version,
            "output_schema": spec.output_schema,
            "template_sha256": spec.template_sha256,
            "caller": spec.caller,
            "max_model_calls": spec.max_model_calls,
        })

    callers = [str(item["caller"]) for item in entries]
    if len(callers) != len(set(callers)) or len(callers) != 3:
        raise ProductionGateError("each production prompt must have exactly one unique caller")
    return {
        "schema_version": "ai-v2-production-readiness-evidence.v1",
        "evidence_type": "deterministic_fake",
        "quality_claim": "contract_only",
        "real_model_quality": "not-run",
        "composition_root": "creative_studio.app.create_application",
        "prompt_registry": {"production_prompts": len(entries), "entries": entries},
        "callers": callers,
        "reachable_use_cases": sorted(_PROMPT_USE_CASES.values()),
        "model_calls": {"declared_max_per_case": 1, "image_model_calls": 0},
    }


__all__ = ["ProductionGateError", "build_production_readiness_evidence"]


def main() -> int:
    parser = argparse.ArgumentParser(description="AI v2 production readiness contract gate")
    parser.add_argument("--registry", type=Path, help="registry to validate; defaults to the repository registry")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    registry = args.registry or root / "config" / "ai_v2" / "prompts" / "registry.json"
    try:
        evidence = build_production_readiness_evidence(root, registry)
    except ProductionGateError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
