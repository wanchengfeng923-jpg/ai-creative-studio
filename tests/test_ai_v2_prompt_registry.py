from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.prompt_registry import (
    AiV2PromptRegistry,
    AiV2PromptRegistryError,
    compile_prompt,
)


class AiV2PromptRegistryTests(unittest.TestCase):
    def test_candidate_prompts_spell_out_their_exact_output_contracts(self) -> None:
        registry = AiV2PromptRegistry()
        required_markers = {
            "creative.ai_v2.narrative": (
                '"schema_version": "narrative-text-v1"',
                '"items"',
                '"story"',
                '"hooks"',
                '"scenes"',
            ),
            "creative.ai_v2.static": (
                '"schema_version": "static-text-v1"',
                '"items"',
                '"title"',
                '"core_idea"',
                '"ad_copy"',
                '"image_description"',
                '"execution"',
                '"image_prompt"',
            ),
            "creative.ai_v2.carousel": (
                '"schema_version": "carousel-text-v1"',
                '"items"',
                '"title"',
                '"core_idea"',
                '"ad_copy"',
                '"frames"',
                '"continuity_rules"',
                '"image_prompts"',
            ),
        }
        for prompt_id, markers in required_markers.items():
            prompt = registry.get(prompt_id, "v1").template_text
            for marker in markers:
                self.assertIn(marker, prompt, prompt_id)

    def test_default_registry_keeps_prompts_candidate_until_explicit_approval(self) -> None:
        registry = AiV2PromptRegistry()
        prompt_ids = (
            "creative.ai_v2.narrative",
            "creative.ai_v2.static",
            "creative.ai_v2.carousel",
        )
        callers = []
        for prompt_id in prompt_ids:
            spec = registry.get(prompt_id, "v1")
            self.assertEqual(spec.lifecycle, "candidate")
            self.assertEqual(spec.max_model_calls, 1)
            self.assertIsNone(spec.caller)

    def test_missing_file_and_hash_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt_dir = root / "prompts"
            prompt_dir.mkdir()
            prompt = prompt_dir / "candidate.txt"
            prompt.write_text("TASK={{task_description}}", encoding="utf-8")
            digest = hashlib.sha256(prompt.read_bytes()).hexdigest()
            registry_file = prompt_dir / "registry.json"

            def write_registry(path: str, prompt_hash: str) -> None:
                registry_file.write_text(json.dumps({"prompts": [{
                    "id": "test", "version": "v1", "path": path,
                    "template_sha256": prompt_hash,
                    "input_schema": "AiV2Input.v1", "output_schema": "Test.v1",
                    "max_model_calls": 1, "lifecycle": "candidate", "caller": None,
                }]}), encoding="utf-8")

            write_registry("missing.txt", digest)
            with self.assertRaises(AiV2PromptRegistryError):
                AiV2PromptRegistry(registry_file)
            write_registry("candidate.txt", "0" * 64)
            with self.assertRaises(AiV2PromptRegistryError):
                AiV2PromptRegistry(registry_file)

    def test_compiler_is_single_literal_pass_and_rejects_unknown_or_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.txt"
            prompt.write_text("A={{task_description}}\nB={{aspect_ratio}}\nC={{creative_tags}}", encoding="utf-8")
            digest = hashlib.sha256(prompt.read_bytes()).hexdigest()
            registry_file = root / "registry.json"
            registry_file.write_text(json.dumps({"prompts": [{
                "id": "test", "version": "v1", "path": "prompt.txt",
                "template_sha256": digest,
                "input_schema": "AiV2Input.v1", "output_schema": "Test.v1",
                "max_model_calls": 1, "lifecycle": "candidate", "caller": None,
            }]}), encoding="utf-8")
            spec = AiV2PromptRegistry(registry_file).get("test", "v1")

            compiled = compile_prompt(spec, {
                "task_description": "$unknown ${task_type} {{x}}\n下一行",
                "aspect_ratio": "16:9",
                "creative_tags": "{}",
            })
            self.assertIn("$unknown ${task_type} {{x}}\n下一行", compiled)
            with self.assertRaises(AiV2PromptRegistryError):
                compile_prompt(spec, {"task_description": "x", "aspect_ratio": "16:9"})
            with self.assertRaises(AiV2PromptRegistryError):
                compile_prompt(spec, {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": "{}", "extra": "x"})


if __name__ == "__main__":
    unittest.main()
