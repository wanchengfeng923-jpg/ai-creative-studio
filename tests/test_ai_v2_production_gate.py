from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.production_gate import (
    ProductionGateError,
    build_production_readiness_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


class AiV2ProductionGateTests(unittest.TestCase):
    def _registry(self, directory: Path, *, lifecycle: str = "candidate", callers: tuple[str | None, ...] = (None, None, None)) -> Path:
        source = json.loads((ROOT / "config/ai_v2/prompts/registry.json").read_text(encoding="utf-8"))
        for entry, caller in zip(source["prompts"], callers):
            entry["lifecycle"] = lifecycle
            entry["caller"] = caller
        path = directory / "registry.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        for entry in source["prompts"]:
            (directory / entry["path"]).write_bytes(
                (ROOT / "config/ai_v2/prompts" / entry["path"]).read_bytes()
            )
        return path

    def test_candidate_registry_is_rejected_by_production_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._registry(Path(directory))
            with self.assertRaisesRegex(ProductionGateError, "lifecycle"):
                build_production_readiness_evidence(ROOT, path)

    def test_production_registry_requires_exact_callers_and_reachable_use_cases(self) -> None:
        callers = (
            "creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate",
            "creative_studio.ai_v2.static_visual.StaticTextUseCase.generate",
            "creative_studio.ai_v2.carousel_visual.CarouselTextUseCase.generate",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self._registry(Path(directory), lifecycle="production", callers=callers)
            evidence = build_production_readiness_evidence(ROOT, path)
        self.assertEqual(evidence["evidence_type"], "deterministic_fake")
        self.assertEqual(evidence["quality_claim"], "contract_only")
        self.assertEqual(evidence["prompt_registry"]["production_prompts"], 3)
        self.assertEqual(set(evidence["callers"]), set(callers))
        self.assertEqual(evidence["reachable_use_cases"], ["carousel", "narrative", "static"])
        self.assertEqual(evidence["composition_root"], "creative_studio.app.create_application")

    def test_duplicate_caller_is_rejected(self) -> None:
        caller = "creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate"
        with tempfile.TemporaryDirectory() as directory:
            path = self._registry(Path(directory), lifecycle="production", callers=(caller, caller, caller))
            with self.assertRaisesRegex(ProductionGateError, "canonical|exactly one"):
                build_production_readiness_evidence(ROOT, path)

    def test_schema_mismatch_is_rejected(self) -> None:
        callers = (
            "creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate",
            "creative_studio.ai_v2.static_visual.StaticTextUseCase.generate",
            "creative_studio.ai_v2.carousel_visual.CarouselTextUseCase.generate",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self._registry(Path(directory), lifecycle="production", callers=callers)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["prompts"][0]["output_schema"] = "static-text-v1"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ProductionGateError, "schema"):
                build_production_readiness_evidence(ROOT, path)


if __name__ == "__main__":
    unittest.main()
