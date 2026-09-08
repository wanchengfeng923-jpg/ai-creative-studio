"""Deterministic AI v2 contract/privacy release gate."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .boundary import assert_ai_v2_boundary
from .carousel_visual import CarouselTextUseCase, CarouselTextUseCaseError
from .fakes import DeterministicTextModel
from .input_contract import normalize_input
from .narrative import NarrativeTextUseCase, NarrativeTextUseCaseError
from .prompt_registry import AiV2PromptRegistry
from .static_visual import StaticTextUseCase, StaticTextUseCaseError
from .store import SqliteAiV2Store

ROOT = Path(__file__).resolve().parents[3]

_PROMPTS = {
    "narrative": "creative.ai_v2.narrative",
    "static": "creative.ai_v2.static",
    "carousel": "creative.ai_v2.carousel",
}
_OUTPUT_SCHEMAS = {
    "narrative": "narrative-text-v1",
    "static": "static-text-v1",
    "carousel": "carousel-text-v1",
}
_FAILURE_CLASSES = (
    "carousel_operation_failed",
    "image_generation_failed",
    "model_output_invalid",
    "provider_protocol_invalid",
)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid v2 evaluation case at line {line_number}") from exc
        if not isinstance(value, dict) or set(value) != {"case_id", "use_case", "input", "expected"}:
            raise ValueError(f"incomplete v2 evaluation case at line {line_number}")
        cases.append(value)
    return cases


def _frame_count(case: Mapping[str, Any]) -> int:
    body = case["input"]
    tags = body["creative_tags"]
    values = tags.get("visual_carousel_count", [])
    return int(values[0])


def _candidate_output(case: Mapping[str, Any]) -> str:
    use_case = str(case["use_case"])
    expected = case["expected"]
    failure = str(expected.get("schema_error") or expected.get("failure") or "")

    if use_case == "narrative":
        value: dict[str, Any] = {
            "schema_version": "narrative-text-v1",
            "items": [
                {
                    "story": f"deterministic story {index}",
                    "hooks": [
                        {"text": "hook one", "scenes": ["scene one", "scene two", "scene three"]},
                        {"text": "hook two", "scenes": ["scene four", "scene five", "scene six"]},
                    ],
                }
                for index in range(1, 6)
            ],
        }
        if failure == "format":
            return "```json\n" + json.dumps(value) + "\n```"
        if failure == "additional_property":
            value["items"][0]["rationale"] = "not allowed"
        elif failure == "min_length":
            value["items"][0]["hooks"][0]["scenes"][0] = ""
    elif use_case == "static":
        value = {
            "schema_version": "static-text-v1",
            "items": [
                {
                    "title": f"deterministic concept {index}",
                    "core_idea": "core idea",
                    "ad_copy": "ad copy",
                    "image_description": "image description",
                    "content_extensions": ["follow-up content"],
                    "reference_sources": [{"name": "reference", "note": "reference note"}],
                    "execution": {"image_prompt": "private image instruction"},
                }
                for index in range(1, 4)
            ],
        }
        if failure == "additional_property":
            value["items"][0]["rationale"] = "not allowed"
        elif failure == "required":
            del value["items"][0]["execution"]["image_prompt"]
    elif use_case == "carousel":
        count = _frame_count(case)
        value = {
            "schema_version": "carousel-text-v1",
            "items": [
                {
                    "title": f"deterministic route {index}",
                    "core_idea": "core idea",
                    "core_subject": "fixed subject",
                    "ad_copy": "ad copy",
                    "content_extensions": ["follow-up content"],
                    "reference_sources": [{"name": "reference", "note": "reference note"}],
                    "frames": [
                        {"index": frame, "description": f"frame {frame}"}
                        for frame in range(1, count + 1)
                    ],
                    "execution": {
                        "continuity_rules": ["subject remains consistent"],
                        "image_prompts": [
                            {"index": frame, "prompt": f"private frame instruction {frame}"}
                            for frame in range(1, count + 1)
                        ],
                    },
                }
                for index in range(1, 4)
            ],
        }
        if failure == "non_contiguous_index":
            value["items"][0]["frames"][1]["index"] = count + 1
        elif failure == "array_length_mismatch":
            value["items"][0]["execution"]["image_prompts"].pop()
    else:
        raise ValueError(f"unknown v2 evaluation use case: {use_case}")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _private_paths(value: Any, prohibited: set[str], path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key)
            nested_path = f"{path}.{key}"
            if key in prohibited:
                found.append(nested_path)
            found.extend(_private_paths(nested, prohibited, nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_private_paths(nested, prohibited, f"{path}[{index}]"))
    return found


def _registry_evidence(root: Path, registry: AiV2PromptRegistry) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for use_case, prompt_id in _PROMPTS.items():
        spec = registry.get(prompt_id, "v1")
        schema_path = root / "config" / "ai_v2" / "schemas" / f"{spec.output_schema}.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_matches = (
            spec.input_schema == "AiV2Input.v1"
            and spec.output_schema == _OUTPUT_SCHEMAS[use_case]
            and schema.get("properties", {}).get("schema_version", {}).get("enum") == [spec.output_schema]
            and set(schema.get("required", [])) == {"schema_version", "items"}
        )
        hash_matches = hashlib.sha256(Path(spec.prompt_path).read_bytes()).hexdigest() == spec.template_sha256
        if not schema_matches or not hash_matches:
            raise ValueError(f"candidate prompt registry is not aligned: {prompt_id}")
        evidence.append({
            "prompt_id": prompt_id,
            "version": spec.version,
            "output_schema": spec.output_schema,
            "template_sha256": spec.template_sha256,
            "hash_matches": hash_matches,
            "schema_matches": schema_matches,
            "max_model_calls": spec.max_model_calls,
            "lifecycle": spec.lifecycle,
            "caller": spec.caller,
        })
    return sorted(evidence, key=lambda item: item["output_schema"])


def build_candidate_contract_evidence(root: Path = ROOT) -> dict[str, Any]:
    """Execute the 30-case candidate contract suite without network or real data."""

    root = Path(root)
    eval_root = root / "config" / "evals" / "ai_v2"
    cases = _load_cases(eval_root / "prompt-cases.jsonl")
    constraints = json.loads((eval_root / "expected-hard-constraints.json").read_text(encoding="utf-8"))
    if len(cases) != 30 or len({str(case["case_id"]) for case in cases}) != 30:
        raise ValueError("v2 evaluation set must contain 30 unique cases")
    counts = Counter(str(case["use_case"]) for case in cases)
    if counts != Counter({"narrative": 10, "static": 10, "carousel": 10}):
        raise ValueError("v2 evaluation set must contain 10 cases per use case")

    # Candidate evidence remains reproducible after the production registry is promoted.
    # The fixture is derived in a disposable directory and never changes the checked-in registry.
    source_registry_path = root / "config" / "ai_v2" / "prompts" / "registry.json"
    candidate_directory = Path(tempfile.mkdtemp(prefix="ai-v2-candidate-registry-"))
    source_payload = json.loads(source_registry_path.read_text(encoding="utf-8"))
    for entry in source_payload["prompts"]:
        entry["lifecycle"] = "candidate"
        entry["caller"] = None
        shutil.copyfile(source_registry_path.parent / entry["path"], candidate_directory / entry["path"])
    candidate_registry_path = candidate_directory / "registry.json"
    candidate_registry_path.write_text(json.dumps(source_payload), encoding="utf-8")
    registry = AiV2PromptRegistry(candidate_registry_path)
    registry_evidence = _registry_evidence(root, registry)
    if any(item["lifecycle"] != "candidate" or item["caller"] is not None for item in registry_evidence):
        raise ValueError("v2 evaluation only accepts unapproved candidate prompts")
    if any(item["max_model_calls"] != 1 for item in registry_evidence):
        raise ValueError("v2 candidate prompts must allow one model call per case")

    prohibited = set(constraints["prohibited_public_fields"])
    prohibited.update({"prompt", "cursor", "job_id", "local_path", "stack", "stack_trace", "error_detail"})
    definition_complete = 0
    contract_evaluated = 0
    contract_passed = 0
    public_payloads_scanned = 0
    text_model_calls = 0
    failures = {failure_class: 0 for failure_class in _FAILURE_CLASSES}
    quality_cases_not_run: list[str] = []

    with tempfile.TemporaryDirectory(prefix="ai-v2-eval-") as directory:
        store = SqliteAiV2Store(Path(directory) / "evaluation.sqlite")
        try:
            for project_id, case in enumerate(cases, start=1):
                case_id = str(case["case_id"])
                use_case = str(case["use_case"])
                body = case["input"]
                expected = case["expected"]
                if not isinstance(body, Mapping) or set(body) != {
                    "task_description", "aspect_ratio", "creative_tags"
                }:
                    raise ValueError(f"incomplete v2 evaluation input: {case_id}")
                if not isinstance(expected, Mapping) or expected.get("status") not in {"valid", "invalid"}:
                    raise ValueError(f"incomplete v2 evaluation expectation: {case_id}")
                if not case_id.startswith(f"{use_case}-") or use_case not in _PROMPTS:
                    raise ValueError(f"misclassified v2 evaluation case: {case_id}")
                input_value = normalize_input(body)
                definition_complete += 1

                model = DeterministicTextModel([_candidate_output(case)])
                if use_case == "narrative":
                    use_case_runner = NarrativeTextUseCase(registry, model, store)
                    error_types = (NarrativeTextUseCaseError,)
                elif use_case == "static":
                    use_case_runner = StaticTextUseCase(registry, model, store)
                    error_types = (StaticTextUseCaseError,)
                else:
                    use_case_runner = CarouselTextUseCase(registry, model, store)
                    error_types = (CarouselTextUseCaseError,)

                failure = str(expected.get("failure") or "")
                is_quality_only = failure == "duplicate_mechanism"
                if is_quality_only:
                    quality_cases_not_run.append(case_id)
                else:
                    contract_evaluated += 1
                try:
                    public = use_case_runner.generate(
                        project_id,
                        input_value,
                        int(expected.get("batch_index") or 1),
                    )
                except error_types as exc:
                    if expected["status"] != "invalid" or is_quality_only or exc.error_code != "model_output_invalid":
                        raise ValueError(f"unexpected v2 contract failure: {case_id}") from exc
                    failures["model_output_invalid"] += 1
                    contract_passed += 1
                else:
                    if expected["status"] == "invalid" and not is_quality_only:
                        raise ValueError(f"v2 contract accepted an invalid case: {case_id}")
                    leaks = _private_paths(public, prohibited)
                    if leaks:
                        raise ValueError(f"v2 public projection leaked a private field: {case_id}:{leaks[0]}")
                    public_payloads_scanned += 1
                    if not is_quality_only:
                        contract_passed += 1
                if len(model.start_calls) != 1:
                    raise ValueError(f"v2 case did not use exactly one text model call: {case_id}")
                text_model_calls += len(model.start_calls)
        finally:
            store.close()

    return {
        "schema_version": "ai-v2-candidate-contract-evidence.v1",
        "evidence_type": "deterministic_fake",
        "quality_claim": "contract_only",
        "real_model_quality": "not-run",
        "cases": {
            "total": len(cases),
            "by_use_case": dict(sorted(counts.items())),
            "definition_complete": definition_complete,
            "contract_outcomes_evaluated": contract_evaluated,
            "contract_outcomes_passed": contract_passed,
            "quality_cases_not_run": quality_cases_not_run,
        },
        "privacy": {
            "public_payloads_scanned": public_payloads_scanned,
            "leak_count": 0,
        },
        "schema_validation": {
            "valid_payloads_accepted": public_payloads_scanned,
            "invalid_payloads_rejected": failures["model_output_invalid"],
            "expected_outcome_pass_rate": (
                public_payloads_scanned + failures["model_output_invalid"]
            ) / len(cases),
        },
        "model_calls": {
            "text_model_calls": text_model_calls,
            "image_model_calls": 0,
            "declared_max_per_case": 1,
            "declared_total_budget": len(cases),
        },
        "retry_count": {
            "hidden_format_repairs": 0,
            "text_retries": 0,
            "image_retries": 0,
        },
        "failure_classification": failures,
        "prompt_registry": registry_evidence,
    }


def run_gate() -> list[tuple[str, int]]:
    commands = [
        ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_ai_v2_*.py", "-q"], "v2-contract"),
        ([sys.executable, "-m", "compileall", "-q", "src/creative_studio/ai_v2"], "compileall"),
        (["node", "--check", "static/ai-v2/app.js"], "node"),
        (["git", "diff", "--check"], "diff-check"),
    ]
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    results: list[tuple[str, int]] = []
    for command, name in commands:
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        results.append((name, completed.returncode))
        if completed.returncode:
            break
    try:
        assert_ai_v2_boundary(ROOT)
        results.append(("boundary", 0))
    except Exception:
        results.append(("boundary", 1))
    return results


def main() -> int:
    results = run_gate()
    for name, code in results:
        print(f"{name}: {'ok' if code == 0 else 'failed'}")
    passed = all(code == 0 for _, code in results)
    evidence = (
        build_candidate_contract_evidence(ROOT)
        if passed
        else {
            "evidence_type": "deterministic_fake",
            "quality_claim": "contract_only",
            "real_model_quality": "not-run",
            "status": "gate-failed",
        }
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
