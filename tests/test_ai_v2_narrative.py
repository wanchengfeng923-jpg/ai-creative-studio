from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.fakes import DeterministicTextModel
from creative_studio.ai_v2.input_contract import normalize_input
from creative_studio.ai_v2.narrative import NarrativeTextUseCase, NarrativeTextUseCaseError
from creative_studio.ai_v2.prompt_registry import AiV2PromptRegistry
from creative_studio.ai_v2.store import SqliteAiV2Store


def _input():
    return normalize_input({"task_description": "任务", "aspect_ratio": "16:9", "creative_tags": {}})


def _result() -> str:
    return json.dumps({
        "schema_version": "narrative-text-v1",
        "items": [
            {
                "story": f"故事 {index}",
                "hooks": [
                    {"text": "钩子一", "scenes": ["一", "二", "三"]},
                    {"text": "钩子二", "scenes": ["四", "五", "六"]},
                ],
            }
            for index in range(5)
        ],
    }, ensure_ascii=False)


class AiV2NarrativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteAiV2Store(Path(self.temp_dir.name) / "db.sqlite")
        self.registry = AiV2PromptRegistry()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_generates_five_stories_with_two_hooks_and_three_scenes(self) -> None:
        model = DeterministicTextModel([_result()])
        use_case = NarrativeTextUseCase(self.registry, model, self.store)

        public = use_case.generate(1, _input(), 1)

        self.assertEqual(public["schema_version"], "narrative-text-v1")
        self.assertEqual(len(public["items"]), 5)
        self.assertTrue(all(len(item["hooks"]) == 2 for item in public["items"]))
        self.assertTrue(all(len(hook["scenes"]) == 3 for item in public["items"] for hook in item["hooks"]))
        self.assertEqual(len(model.start_calls), 1)
        self.assertEqual(self.store.count_image_sessions(), 0)

    def test_empty_task_description_is_accepted(self) -> None:
        model = DeterministicTextModel([_result()])
        use_case = NarrativeTextUseCase(self.registry, model, self.store)
        value = normalize_input({"task_description": "", "aspect_ratio": "9:16", "creative_tags": {}})

        public = use_case.generate(1, value, 1)

        self.assertEqual(public["items"][0]["story"], "故事 0")
        self.assertEqual(len(model.start_calls), 1)

    def test_extra_fields_or_format_errors_fail_without_hidden_repair_call(self) -> None:
        invalid = json.loads(_result())
        invalid["items"][0]["rationale"] = "不允许"
        model = DeterministicTextModel([json.dumps(invalid)])
        use_case = NarrativeTextUseCase(self.registry, model, self.store)

        with self.assertRaises(NarrativeTextUseCaseError) as context:
            use_case.generate(1, _input(), 1)
        self.assertEqual(context.exception.error_code, "model_output_invalid")
        self.assertEqual(len(model.start_calls), 1)

    def test_user_retry_after_failure_uses_new_text_session_and_second_batch_is_new_session(self) -> None:
        model = DeterministicTextModel(["not-json", _result(), _result()])
        use_case = NarrativeTextUseCase(self.registry, model, self.store)

        with self.assertRaises(NarrativeTextUseCaseError):
            use_case.generate(1, _input(), 1)
        use_case.generate(1, _input(), 1)
        use_case.generate(1, _input(), 2)

        self.assertEqual(len(model.start_calls), 3)
        self.assertEqual(len({call.idempotency_key for call in model.start_calls}), 3)
        self.assertEqual(self.store.count_image_sessions(), 0)


if __name__ == "__main__":
    unittest.main()
