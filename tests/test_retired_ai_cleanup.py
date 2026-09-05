from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RETIRED_PATHS = (
    "src/creative_studio/ai_creative.py",
    "src/creative_studio/ai_provider.py",
    "src/creative_studio/ai_service_settings.py",
    "src/creative_studio/carousel.py",
    "src/creative_studio/carousel_operations.py",
    "src/creative_studio/carousel_visual.py",
    "src/creative_studio/contracts.py",
    "src/creative_studio/display_frame_models.py",
    "src/creative_studio/evaluation_harness.py",
    "src/creative_studio/generation_models.py",
    "src/creative_studio/generation_service.py",
    "src/creative_studio/image_jobs.py",
    "src/creative_studio/model_client.py",
    "src/creative_studio/model_ports.py",
    "src/creative_studio/narrative.py",
    "src/creative_studio/observability.py",
    "src/creative_studio/phase5_governance.py",
    "src/creative_studio/ports.py",
    "src/creative_studio/projection_scrub.py",
    "src/creative_studio/prompt_registry.py",
    "src/creative_studio/prompting.py",
    "src/creative_studio/provider_capabilities.py",
    "src/creative_studio/public_projection.py",
    "src/creative_studio/reference_assets.py",
    "src/creative_studio/release_gate.py",
    "src/creative_studio/schemas.py",
    "src/creative_studio/static_visual.py",
    "config/ai_creative_game_info_v2.json",
    "config/ai_creative_prompt_v5.txt",
    "config/ai_visual_carousel_prompt_v1.txt",
    "config/ai_visual_creative_prompt_v2.txt",
    "config/ai_visual_first_frame_prompt_v1.txt",
    "config/ai_visual_follow_up_prompt_v1.txt",
    "config/ai_visual_static_creative_prompt_v1.txt",
    "config/prompts/registry.json",
    "config/prompts/narrative/v6.txt",
    "config/evals/carousel.v1.json",
    "config/evals/narrative.v1.json",
    "config/evals/report-template.v1.json",
    "config/evals/static.v1.json",
    "config/evals/reports/carousel.v1.not-run.json",
    "config/evals/reports/narrative.v1.not-run.json",
    "config/evals/reports/static.v1.not-run.json",
    "tests/test_evaluation_harness.py",
    "tests/test_generation_models.py",
    "tests/test_model_ports.py",
    "tests/test_observability.py",
    "tests/test_phase5_governance.py",
    "tests/test_projection_scrub.py",
    "tests/test_public_projection.py",
)


class RetiredAiCleanupTests(unittest.TestCase):
    def test_retired_python_modules_configuration_and_tests_are_absent(self) -> None:
        for relative_path in RETIRED_PATHS:
            with self.subTest(path=relative_path):
                self.assertFalse((ROOT / relative_path).exists(), relative_path)

    def test_v2_and_neutral_runtime_assets_remain(self) -> None:
        retained_paths = (
            "src/creative_studio/ai_v2/application.py",
            "src/creative_studio/project_projection.py",
            "src/creative_studio/repository.py",
            "src/creative_studio/backup.py",
            "config/ai_v2/prompts/registry.json",
            "config/evals/ai_v2/prompt-cases.jsonl",
            "config/creative_tag_options.json",
            "chat2api/main.py",
        )
        for relative_path in retained_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
