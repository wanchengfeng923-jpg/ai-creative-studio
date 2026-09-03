import json
import unittest
from pathlib import Path

from creative_studio.contracts import contract_binding
from creative_studio.prompt_registry import PromptRegistry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "prompts" / "registry.json"
EVALS = ROOT / "config" / "evals" / "static.v1.json"


class StaticRegistryAndEvaluationTests(unittest.TestCase):
    def test_static_v1_is_the_only_production_static_prompt(self) -> None:
        registry = PromptRegistry.load(REGISTRY)
        static_specs = [
            spec for spec in registry.inventory()
            if spec.id == "creative.visual.static.generate"
        ]
        production = [spec for spec in static_specs if spec.lifecycle == "production"]
        self.assertEqual([(spec.version, spec.caller) for spec in production], [("static-v1", "static")])
        retired = next(spec for spec in static_specs if spec.version == "visual-v2.3")
        self.assertEqual(retired.lifecycle, "retired")
        binding = contract_binding("creative.visual.static.generate")
        self.assertEqual(binding.output_schema, "StaticVisualResult.v1")
        self.assertEqual(binding.validator, "StaticVisualResultValidator.v1")

    def test_static_evaluation_fixture_has_ten_sanitized_cases(self) -> None:
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        cases = payload.get("cases") if isinstance(payload, dict) else None
        self.assertIsInstance(cases, list)
        self.assertGreaterEqual(len(cases), 10)
        required = {"id", "input", "hard_constraints", "fact_boundary", "quality_checks", "failure_examples"}
        for case in cases:
            self.assertEqual(set(case), required)
            self.assertTrue(case["id"])
            self.assertIsInstance(case["input"], dict)
            self.assertTrue(str(case["input"].get("task_description") or "").strip())
            self.assertIn(case["input"].get("aspect_ratio"), {"16:9", "9:16"})
            self.assertIsInstance(case["hard_constraints"], list)
            self.assertIsInstance(case["fact_boundary"], list)
            self.assertIsInstance(case["quality_checks"], list)
            self.assertIsInstance(case["failure_examples"], list)


if __name__ == "__main__":
    unittest.main()
