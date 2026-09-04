"""可重复的 Phase 5 caller 审计与评测报告契约检查。"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


RETIRED_SYMBOLS = (
    "LegacyCreativeGenerationAdapter",
    "VisualRecommendationSchema",
    "load_ai_visual_first_frame_prompt",
    "load_ai_visual_follow_up_prompt",
    "complete_visual_generation",
)
FAILURE_CLASSES = frozenset(
    {"model_output_invalid", "provider_protocol_invalid", "image_generation_failed", "carousel_operation_failed"}
)


def production_symbol_references(source_root: Path, symbol: str) -> list[str]:
    """返回源码中调用/实例化 symbol 的文件:行号，忽略定义、导入和 docstring。"""
    references: list[str] = []
    for path in sorted(Path(source_root).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions = {
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == symbol
        }
        imports = {
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.alias) and node.name == symbol
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id != symbol:
                continue
            if node.lineno in definitions or node.lineno in imports:
                continue
            parent_call = any(
                isinstance(parent, ast.Call) and parent.func is node
                for parent in ast.walk(tree)
            )
            if parent_call:
                references.append(f"{path.name}:{node.lineno}")
    return references


def load_evaluation_report(path: Path) -> dict[str, Any]:
    """读取并检查版本化评测报告的最小结构。"""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "evaluation-report.v1":
        raise ValueError("invalid evaluation report schema_version")
    if value.get("status") not in {"not_run", "complete", "failed"}:
        raise ValueError("invalid evaluation report status")
    failure_classes = value.get("failure_classes")
    if not isinstance(failure_classes, list) or any(str(item) not in FAILURE_CLASSES for item in failure_classes):
        raise ValueError("invalid evaluation failure class")
    results = value.get("results")
    if not isinstance(results, dict) or set(results) != {"baseline", "candidate", "repair_failure"}:
        raise ValueError("evaluation report requires baseline/candidate/repair_failure")
    for label, result in results.items():
        if not isinstance(result, dict) or result.get("status") not in {"not_run", "complete", "failed"}:
            raise ValueError(f"invalid evaluation result: {label}")
        if result.get("status") != "not_run":
            for key in ("hard_constraint_pass_rate", "calls", "latency_ms", "failure_classification"):
                if key not in result:
                    raise ValueError(f"missing {key}: {label}")
    return value


def governance_summary(root: Path) -> dict[str, Any]:
    """返回 registry 与 retired symbol 的机器可读审计摘要。"""
    root = Path(root)
    registry_path = root / "config" / "prompts" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    production = [item for item in registry.get("prompts", []) if item.get("lifecycle") == "production"]
    source_root = root / "src"
    return {
        "production_prompts": len(production),
        "production_callers": sorted({str(item.get("caller") or "") for item in production}),
        "retired_references": {
            symbol: production_symbol_references(source_root, symbol)
            for symbol in RETIRED_SYMBOLS
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    summary = governance_summary(root)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    references = summary["retired_references"]
    if any(references.values()):
        return 1
    callers = summary["production_callers"]
    return 0 if callers == ["carousel", "narrative", "static"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
