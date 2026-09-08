from __future__ import annotations

import unittest
from pathlib import Path

from creative_studio.ai_v2 import release_gate


ROOT = Path(__file__).resolve().parents[1]


class AiV2ReleaseGateTests(unittest.TestCase):
    def test_candidate_contract_evidence_covers_all_cases_without_quality_claim(self) -> None:
        self.assertTrue(
            hasattr(release_gate, "build_candidate_contract_evidence"),
            "release gate must expose reproducible candidate contract evidence",
        )
        evidence = release_gate.build_candidate_contract_evidence(ROOT)

        self.assertEqual(evidence["evidence_type"], "deterministic_fake")
        self.assertEqual(evidence["quality_claim"], "contract_only")
        self.assertEqual(evidence["real_model_quality"], "not-run")
        self.assertEqual(evidence["cases"]["total"], 30)
        self.assertEqual(evidence["cases"]["by_use_case"], {
            "carousel": 10,
            "narrative": 10,
            "static": 10,
        })
        self.assertEqual(evidence["cases"]["definition_complete"], 30)
        self.assertEqual(evidence["cases"]["contract_outcomes_evaluated"], 29)
        self.assertEqual(evidence["cases"]["contract_outcomes_passed"], 29)
        self.assertEqual(evidence["cases"]["quality_cases_not_run"], ["narrative-07"])
        self.assertEqual(evidence["privacy"]["leak_count"], 0)
        self.assertEqual(evidence["privacy"]["public_payloads_scanned"], 25)
        self.assertEqual(evidence.get("schema_validation"), {
            "expected_outcome_pass_rate": 1.0,
            "invalid_payloads_rejected": 5,
            "valid_payloads_accepted": 25,
        })
        self.assertEqual(evidence["model_calls"], {
            "text_model_calls": 30,
            "image_model_calls": 0,
            "declared_max_per_case": 1,
            "declared_total_budget": 30,
        })
        self.assertEqual(evidence.get("retry_count"), {
            "hidden_format_repairs": 0,
            "image_retries": 0,
            "text_retries": 0,
        })
        self.assertEqual(evidence["failure_classification"], {
            "carousel_operation_failed": 0,
            "image_generation_failed": 0,
            "model_output_invalid": 5,
            "provider_protocol_invalid": 0,
        })
        self.assertEqual(
            [item["output_schema"] for item in evidence["prompt_registry"]],
            ["carousel-text-v1", "narrative-text-v1", "static-text-v1"],
        )
        self.assertTrue(all(item["hash_matches"] for item in evidence["prompt_registry"]))
        self.assertTrue(all(item["schema_matches"] for item in evidence["prompt_registry"]))
        self.assertTrue(all(item["lifecycle"] == "candidate" for item in evidence["prompt_registry"]))
        self.assertTrue(all(item["caller"] is None for item in evidence["prompt_registry"]))


if __name__ == "__main__":
    unittest.main()
