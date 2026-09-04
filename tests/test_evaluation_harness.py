import unittest
import json
import tempfile
from pathlib import Path

from creative_studio.evaluation_harness import (
    aggregate_failure_classifications,
    build_deterministic_fake_evidence,
    evaluate_case_outputs,
    lint_case_output,
    lint_evaluation_result,
)


class EvaluationHarnessTests(unittest.TestCase):
    def test_lint_requires_metrics_and_valid_failure_classification(self):
        with self.assertRaisesRegex(ValueError, "hard_constraint_pass_rate"):
            lint_evaluation_result({"status": "complete", "failure_classification": {}})

        valid = lint_evaluation_result(
            {
                "status": "complete",
                "hard_constraint_pass_rate": 1.0,
                "calls": 1,
                "latency_ms": 42,
                "failure_classification": {"model_output_invalid": 0},
                "evidence_type": "real_provider",
            }
        )
        self.assertEqual(valid["status"], "complete")

    def test_lint_rejects_unknown_failure_class_and_invalid_metric(self):
        with self.assertRaisesRegex(ValueError, "failure class"):
            lint_evaluation_result(
                {
                    "status": "complete",
                    "hard_constraint_pass_rate": 1.1,
                    "calls": 1,
                    "latency_ms": 10,
                    "failure_classification": {"unknown": 1},
                    "evidence_type": "real_provider",
                }
            )

        with self.assertRaisesRegex(ValueError, "private"):
            lint_evaluation_result(
                {
                    "status": "complete",
                    "hard_constraint_pass_rate": 1.0,
                    "calls": 1,
                    "latency_ms": 10,
                    "failure_classification": {},
                    "evidence_type": "real_provider",
                    "prompt": "do not persist",
                }
            )

    def test_failure_classifications_aggregate_without_accepting_private_values(self):
        summary = aggregate_failure_classifications(
            [
                {"failure_classification": {"model_output_invalid": 2, "image_generation_failed": 1}},
                {"failure_classification": {"model_output_invalid": 3}},
            ]
        )
        self.assertEqual(summary["model_output_invalid"], 5)
        self.assertEqual(summary["image_generation_failed"], 1)
        self.assertNotIn("prompt", summary)

    def test_deterministic_fake_evidence_is_separate_from_quality_report(self):
        evidence = build_deterministic_fake_evidence({"use_cases": 3, "cases": 30, "reports": 3})
        self.assertEqual(evidence["schema_version"], "deterministic-contract-evidence.v1")
        self.assertEqual(evidence["evidence_type"], "deterministic_fake")
        self.assertEqual(evidence["quality_claim"], "contract_only")
        self.assertNotIn("candidate", evidence)

    def test_case_output_lint_validates_canonical_shape_and_private_boundary(self):
        case = {"input": {}, "assertions": {"item_count": 5}}
        valid = {
            "items": [
                {
                    "story": "故事",
                    "hooks": [
                        {"text": "钩子1", "scenes": ["场景1", "场景2", "场景3"]},
                        {"text": "钩子2", "scenes": ["场景4", "场景5", "场景6"]},
                    ],
                }
                for _ in range(5)
            ]
        }
        self.assertTrue(lint_case_output("narrative.v1", case, valid)["passed"])
        invalid = {"items": valid["items"], "image_prompt": "private"}
        self.assertFalse(lint_case_output("narrative.v1", case, invalid)["passed"])

        summary = evaluate_case_outputs("narrative.v1", [case], [valid])
        self.assertEqual(summary["hard_constraint_pass_rate"], 1.0)
        self.assertEqual(summary["failure_classification"]["model_output_invalid"], 0)

    def test_asset_validation_lints_non_not_run_reports(self):
        root = Path(__file__).resolve().parents[1] / "config" / "evals"
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory) / "evals"
            import shutil
            shutil.copytree(root, temp_root)
            report_path = temp_root / "reports" / "narrative.v1.not-run.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["status"] = "complete"
            report["results"]["candidate"] = {"status": "complete"}
            report_path.write_text(json.dumps(report), encoding="utf-8")
            from creative_studio.evaluation_harness import validate_evaluation_assets
            with self.assertRaisesRegex(ValueError, "hard_constraint_pass_rate"):
                validate_evaluation_assets(temp_root)


if __name__ == "__main__":
    unittest.main()
