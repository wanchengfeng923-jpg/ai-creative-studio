import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.prompt_registry import PromptRegistry, PromptRegistryError


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "prompts" / "registry.json"


class PromptRegistryTests(unittest.TestCase):
    def test_loads_six_entries_and_three_production_specs(self):
        registry = PromptRegistry.load(REGISTRY)
        self.assertEqual(len(registry.inventory()), 6)
        self.assertEqual(sum(spec.lifecycle == "production" for spec in registry.inventory()), 3)
        self.assertEqual(registry.get("creative.narrative.generate", "v5").template_sha256[:8], "262d97be")

    def test_candidate_cannot_resolve_as_production_without_explicit_version(self):
        registry = PromptRegistry.load(REGISTRY)
        with self.assertRaises(PromptRegistryError):
            registry.get("creative.visual.static.generate")

    def test_wrong_hash_fails_closed(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["prompts"][0]["template_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config" / "prompts").mkdir(parents=True)
            (root / "config" / "ai_creative_prompt_v5.txt").write_text("", encoding="utf-8")
            path = root / "config" / "prompts" / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(PromptRegistryError):
                PromptRegistry.load(path)


if __name__ == "__main__":
    unittest.main()
