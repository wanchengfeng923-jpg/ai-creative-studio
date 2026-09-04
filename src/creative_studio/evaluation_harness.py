"""离线评测资产与报告契约检查。

默认只检查脱敏 fixture 和报告结构，不发起任何模型或图片请求。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .ai_creative import validate_visual_creative_recommendations
from .narrative import validate_narrative_result
from .phase5_governance import load_evaluation_report
from .static_visual import validate_static_visual_result


FIXTURE_NAMES = ("narrative.v1.json", "static.v1.json", "carousel.v1.json")
FAILURE_CLASSES = frozenset(
    {"model_output_invalid", "provider_protocol_invalid", "image_generation_failed", "carousel_operation_failed"}
)
EVIDENCE_TYPES = frozenset({"real_provider", "deterministic_fake", "manual_review"})
PRIVATE_OUTPUT_KEYS = frozenset(
    {
        "prompt", "content", "path", "body", "secret", "image_prompt", "image_generation_instruction", "conversation_id", "parent_message_id",
        "assistant_message_id", "image_path", "stored_name", "gateway_job_id", "raw_response",
        "private_context", "stack_trace", "error_detail", "lease_token",
    }
)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def lint_evaluation_result(value: Mapping[str, Any]) -> dict[str, Any]:
    """Lint one report result and fail closed on incomplete quality evidence."""

    if not isinstance(value, Mapping):
        raise ValueError("evaluation result must be an object")
    private_paths = _private_output_keys(value)
    if private_paths:
        raise ValueError(f"private fields are forbidden in evaluation result: {private_paths[0]}")
    status = str(value.get("status") or "")
    if status not in {"not_run", "complete", "failed"}:
        raise ValueError("invalid evaluation result status")
    if status == "not_run":
        return {"status": "not_run"}

    failure_classification = value.get("failure_classification")
    if not isinstance(failure_classification, Mapping):
        raise ValueError("failure_classification must be an object")
    normalized_failures: dict[str, int] = {}
    for raw_class, raw_count in failure_classification.items():
        failure_class = str(raw_class)
        if failure_class not in FAILURE_CLASSES:
            raise ValueError(f"unknown failure class: {failure_class}")
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            raise ValueError(f"failure class count is invalid: {failure_class}")
        normalized_failures[failure_class] = raw_count

    rate = value.get("hard_constraint_pass_rate")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= float(rate) <= 1:
        raise ValueError("hard_constraint_pass_rate must be between 0 and 1")
    calls = value.get("calls")
    if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
        raise ValueError("calls must be a non-negative integer")
    latency = value.get("latency_ms")
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or float(latency) < 0:
        raise ValueError("latency_ms must be non-negative")
    evidence_type = str(value.get("evidence_type") or "")
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError("evaluation result requires a valid evidence_type")
    if evidence_type == "deterministic_fake" and value.get("quality_claim") != "contract_only":
        raise ValueError("deterministic_fake evidence must be marked contract_only")
    return {
        "status": status,
        "hard_constraint_pass_rate": float(rate),
        "calls": calls,
        "latency_ms": float(latency),
        "failure_classification": normalized_failures,
        "evidence_type": evidence_type,
        **({"quality_claim": "contract_only"} if evidence_type == "deterministic_fake" else {}),
    }


def aggregate_failure_classifications(results: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Aggregate only registered failure classes from report result objects."""

    totals = {failure_class: 0 for failure_class in sorted(FAILURE_CLASSES)}
    for result in results:
        if not isinstance(result, Mapping):
            raise ValueError("evaluation result must be an object")
        classification = result.get("failure_classification")
        if classification is None:
            continue
        if not isinstance(classification, Mapping):
            raise ValueError("failure_classification must be an object")
        for failure_class, count in classification.items():
            key = str(failure_class)
            if key not in FAILURE_CLASSES:
                raise ValueError(f"unknown failure class: {key}")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"failure class count is invalid: {key}")
            totals[key] += count
    return totals


def _private_output_keys(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}"
            if key_text in PRIVATE_OUTPUT_KEYS:
                found.append(nested_path)
            found.extend(_private_output_keys(nested, nested_path))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_private_output_keys(nested, f"{path}[{index}]"))
    return found


def lint_case_output(use_case: str, case: Mapping[str, Any], output: Any) -> dict[str, Any]:
    """Validate a fixture output against its canonical contract and privacy rules."""

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {"passed": False, "failure_classification": {"model_output_invalid": 1}, "failures": ["$"]}
    failures = _private_output_keys(output)
    try:
        if use_case == "narrative.v1":
            validate_narrative_result(output)
        elif use_case == "static.v1":
            validate_static_visual_result(output)
        elif use_case == "carousel.v1":
            raw_input = case.get("input") if isinstance(case, Mapping) else {}
            carousel = raw_input.get("carousel") if isinstance(raw_input, Mapping) else {}
            config = carousel if isinstance(carousel, Mapping) else {}
            validate_visual_creative_recommendations(output, carousel_config=config, tag_catalog={})
        else:
            raise ValueError(f"unknown evaluation use case: {use_case}")
    except Exception as exc:
        failures.append(str(getattr(exc, "field_path", "$") or "$"))
    if failures:
        return {
            "passed": False,
            "failure_classification": {"model_output_invalid": 1},
            "failures": sorted(set(failures)),
        }
    return {"passed": True, "failure_classification": {}, "failures": []}


def evaluate_case_outputs(use_case: str, cases: Sequence[Mapping[str, Any]], outputs: Sequence[Any]) -> dict[str, Any]:
    """Return hard-constraint pass rate and aggregatable failure evidence."""

    if len(cases) != len(outputs):
        raise ValueError("evaluation cases and outputs must have equal lengths")
    case_results = [lint_case_output(use_case, case, output) for case, output in zip(cases, outputs)]
    passed = sum(1 for result in case_results if result["passed"])
    return {
        "use_case": use_case,
        "case_count": len(case_results),
        "hard_constraint_pass_rate": (passed / len(case_results)) if case_results else 0.0,
        "failure_classification": aggregate_failure_classifications(case_results),
        "cases": case_results,
    }


def build_deterministic_fake_evidence(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Mark fixture-only evidence separately from real-provider quality reports."""

    return {
        "schema_version": "deterministic-contract-evidence.v1",
        "evidence_type": "deterministic_fake",
        "quality_claim": "contract_only",
        "fixture_summary": {
            key: int(summary.get(key) or 0)
            for key in ("use_cases", "cases", "reports")
        },
        "notes": "Deterministic fake validates contracts and privacy only; it is not a model quality result.",
    }


def validate_evaluation_assets(root: Path) -> dict[str, int]:
    """验证固定评测集、报告模板和三份版本化报告。"""
    root = Path(root)
    use_cases = cases = 0
    for name in FIXTURE_NAMES:
        path = root / name
        payload = _load_object(path)
        listed = payload.get("cases")
        if not isinstance(listed, list) or len(listed) != 10:
            raise ValueError(f"{name} must contain exactly 10 cases")
        ids = [case.get("id") for case in listed if isinstance(case, dict)]
        if len(ids) != 10 or any(not isinstance(case_id, str) or not case_id for case_id in ids):
            raise ValueError(f"{name} contains invalid case ids")
        if len(set(ids)) != 10:
            raise ValueError(f"{name} contains duplicate case ids")
        use_cases += 1
        cases += len(listed)
    load_evaluation_report(root / "report-template.v1.json")
    reports_dir = root / "reports"
    reports = sorted(reports_dir.glob("*.not-run.json"))
    expected = {name.removesuffix(".v1.json") + ".v1" for name in FIXTURE_NAMES}
    actual = {path.name.removesuffix(".not-run.json") for path in reports}
    if actual != expected:
        raise ValueError(f"reports mismatch: expected {sorted(expected)}, got {sorted(actual)}")
    for path in reports:
        report = load_evaluation_report(path)
        results = report.get("results")
        if isinstance(results, Mapping):
            for result in results.values():
                lint_evaluation_result(result)
    return {"use_cases": use_cases, "cases": cases, "reports": len(reports)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate offline AI evaluation assets")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2] / "config" / "evals")
    parser.add_argument("--validate-only", action="store_true", help="validate fixtures and report schemas")
    parser.add_argument(
        "--deterministic-fake-summary",
        action="store_true",
        help="print fixture-only evidence with an explicit non-quality marker",
    )
    args = parser.parse_args(argv)
    summary = validate_evaluation_assets(args.root)
    payload: Mapping[str, Any] = (
        build_deterministic_fake_evidence(summary) if args.deterministic_fake_summary else summary
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
