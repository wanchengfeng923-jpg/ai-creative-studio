from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.input_contract import normalize_input
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ImageSubmission, ReconcileResult
from creative_studio.ai_v2.prompt_registry import AiV2PromptRegistry
from creative_studio.ai_v2.static_visual import StaticTextUseCase
from creative_studio.ai_v2.store import SqliteAiV2Store


def _input():
    return normalize_input({"task_description": "静态任务", "aspect_ratio": "16:9", "creative_tags": {}})


def _result() -> str:
    return json.dumps({
        "schema_version": "static-text-v1",
        "items": [
            {
                "title": f"方案 {index}",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "image_description": "画面描述",
                "execution": {"image_prompt": f"图片指令 {index}"},
            }
            for index in range(3)
        ],
    }, ensure_ascii=False)


class AiV2StaticVisualTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteAiV2Store(Path(self.temp_dir.name) / "db.sqlite")
        self.registry = AiV2PromptRegistry()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def _use_case(self, text_model: DeterministicTextModel, image_model: DeterministicImageModel | None = None) -> StaticTextUseCase:
        return StaticTextUseCase(self.registry, text_model, self.store, image_model=image_model)

    def test_text_success_returns_three_pending_schemes_without_execution(self) -> None:
        public = self._use_case(DeterministicTextModel([_result()])).generate(1, _input(), 1)

        self.assertEqual(public["schema_version"], "static-text-v1")
        self.assertEqual(len(public["items"]), 3)
        self.assertTrue(all(item["image_state"]["status"] == "pending" for item in public["items"]))
        self.assertNotIn("execution", json.dumps(public, ensure_ascii=False))

    def test_first_image_click_is_idempotent_and_creates_one_attempt_and_session(self) -> None:
        text_model = DeterministicTextModel([_result()])
        image_model = DeterministicImageModel()
        use_case = self._use_case(text_model, image_model)
        use_case.generate(1, _input(), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_image(scheme_id)
        second = use_case.request_image(scheme_id)

        self.assertEqual(first.attempt_id, second.attempt_id)
        self.assertEqual(len(image_model.created_image_sessions), 1)
        self.assertEqual(len(self.store.list_frames(scheme_id)), 1)
        self.assertEqual(
            self.store.find_image_attempt(
                scheme_id, 1, self.store.list_schemes(1)[0]["scheme_version"] + ":frame:1"
            ).attempt_no,
            1,
        )  # type: ignore[union-attr]

    def test_successful_image_is_locked_and_cannot_be_regenerated(self) -> None:
        cursor = ImageSessionCursor("fake", "conversation", "message", 1)
        submission = ImageSubmission("success", "job-success", cursor, image_artifact(b"png", "image/png"), None)
        text_model = DeterministicTextModel([_result()])
        image_model = DeterministicImageModel(start_submissions={"v2-run-1-scheme-1:frame:1": submission})
        use_case = self._use_case(text_model, image_model)
        use_case.generate(1, _input(), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_image(scheme_id)
        second = use_case.request_image(scheme_id)

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "success")
        self.assertEqual(len(image_model.start_calls), 1)
        self.assertEqual(self.store.count_image_sessions(scheme_id), 1)

    def test_terminal_failure_retry_reconciles_then_reuses_session_with_new_attempt(self) -> None:
        failed = ImageSubmission("terminal_failure", "job-failed", ImageSessionCursor("fake", "conversation", "message", 0), None, "provider_rejected")
        image_model = DeterministicImageModel(
            start_submissions={"v2-run-1-scheme-1:frame:1": failed},
            reconcile_results={
                "v2-run-1-scheme-1:frame:1": ReconcileResult(
                    "terminal_failure", "job-failed", failed.cursor, None, "provider_rejected"
                )
            },
        )
        use_case = self._use_case(DeterministicTextModel([_result()]), image_model)
        use_case.generate(1, _input(), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_image(scheme_id)
        retry = use_case.request_image(scheme_id)

        self.assertEqual(first.status, "failed")
        self.assertNotEqual(retry.attempt_id, first.attempt_id)
        self.assertEqual(len(image_model.created_image_sessions), 1)
        self.assertEqual(len(image_model.start_calls), 1)
        self.assertEqual(len(image_model.continue_calls), 1)
        self.assertEqual(
            image_model.start_calls[0].provider_request_id,
            "v2-run-1-scheme-1:frame:1:attempt:1",
        )
        self.assertEqual(
            image_model.continue_calls[0].request.provider_request_id,
            "v2-run-1-scheme-1:frame:1:attempt:2",
        )
        self.assertEqual(
            image_model.start_calls[0].request_key,
            image_model.continue_calls[0].request.request_key,
        )


if __name__ == "__main__":
    unittest.main()
