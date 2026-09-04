from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.phase5_governance import load_evaluation_report, production_symbol_references
from creative_studio.evaluation_harness import validate_evaluation_assets
from creative_studio.prompt_registry import PromptRegistry


ROOT = Path(__file__).resolve().parents[1]


class Phase5GovernanceTests(unittest.TestCase):
    def test_retired_loaders_have_no_runtime_callers(self) -> None:
        self.assertEqual(production_symbol_references(ROOT / "src", "load_ai_visual_first_frame_prompt"), [])
        self.assertEqual(production_symbol_references(ROOT / "src", "load_ai_visual_follow_up_prompt"), [])
        self.assertEqual(production_symbol_references(ROOT / "src", "complete_visual_generation"), [])
        self.assertEqual(production_symbol_references(ROOT / "src", "LegacyCreativeGenerationAdapter"), [])

    def test_report_template_is_versioned_and_explicitly_not_run(self) -> None:
        path = ROOT / "config" / "evals" / "report-template.v1.json"
        report = load_evaluation_report(path)
        self.assertEqual(report["status"], "not_run")
        self.assertEqual(set(report["results"]), {"baseline", "candidate", "repair_failure"})
        self.assertIn("provider_protocol_invalid", report["failure_classes"])

    def test_production_registry_callers_are_unique(self) -> None:
        registry = PromptRegistry.load(ROOT / "config" / "prompts" / "registry.json")
        production = [spec for spec in registry.inventory() if spec.lifecycle == "production"]
        self.assertEqual({spec.caller for spec in production}, {"narrative", "static", "carousel"})
        self.assertEqual(len({spec.caller for spec in production}), len(production))

    def test_eval_fixtures_have_ten_unique_cases(self) -> None:
        for path in sorted((ROOT / "config" / "evals").glob("*.v1.json")):
            if path.name == "report-template.v1.json":
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            case_ids = [case["id"] for case in payload["cases"]]
            self.assertEqual(len(case_ids), 10, path.name)
            self.assertEqual(len(set(case_ids)), 10, path.name)

    def test_versioned_reports_exist_for_each_use_case(self) -> None:
        reports = sorted((ROOT / "config" / "evals" / "reports").glob("*.not-run.json"))
        self.assertEqual({path.stem.removesuffix(".not-run") for path in reports}, {"narrative.v1", "static.v1", "carousel.v1"})
        for path in reports:
            report = load_evaluation_report(path)
            self.assertEqual(report["status"], "not_run")

    def test_evaluation_harness_validates_fixtures_and_reports(self) -> None:
        summary = validate_evaluation_assets(ROOT / "config" / "evals")
        self.assertEqual(summary["use_cases"], 3)
        self.assertEqual(summary["cases"], 30)
        self.assertEqual(summary["reports"], 3)

    def test_report_rejects_unknown_failure_class(self) -> None:
        template = ROOT / "config" / "evals" / "report-template.v1.json"
        payload = json.loads(template.read_text(encoding="utf-8"))
        payload["failure_classes"] = ["unknown_internal_error"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "failure class"):
                load_evaluation_report(path)


if __name__ == "__main__":
    unittest.main()
