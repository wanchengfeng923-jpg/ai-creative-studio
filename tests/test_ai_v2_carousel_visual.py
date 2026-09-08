from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.input_contract import normalize_input
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ImageSubmission, ReconcileResult
from creative_studio.ai_v2.prompt_registry import AiV2PromptRegistry
from creative_studio.ai_v2.carousel_visual import CarouselTextUseCase, CarouselTextUseCaseError
from creative_studio.ai_v2.image_worker import ImageWorker
from creative_studio.ai_v2.store import SqliteAiV2Store


def _input(count: str = "3"):
    return normalize_input({
        "task_description": "轮播任务",
        "aspect_ratio": "16:9",
        "creative_tags": {"visual_carousel": ["是"], "visual_carousel_count": [count]},
    })


def _result(frame_count: int = 3) -> str:
    return json.dumps({
        "schema_version": "carousel-text-v1",
        "items": [
            {
                "title": f"方案 {index}",
                "core_idea": "核心创意",
                "core_subject": "固定主体",
                "ad_copy": "广告文案",
                "content_extensions": ["补充内容"],
                "reference_sources": [{"name": "参考", "note": "参考说明"}],
                "frames": [{"index": frame, "description": f"画面 {frame}"} for frame in range(1, frame_count + 1)],
                "execution": {
                    "continuity_rules": ["主体一致"],
                    "image_prompts": [{"index": frame, "prompt": f"图片 {frame}"} for frame in range(1, frame_count + 1)],
                },
            }
            for index in range(3)
        ],
    }, ensure_ascii=False)


class AiV2CarouselVisualTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteAiV2Store(Path(self.temp_dir.name) / "db.sqlite")
        self.registry = AiV2PromptRegistry()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def _use_case(self, text_model: DeterministicTextModel, image_model: DeterministicImageModel | None = None) -> CarouselTextUseCase:
        return CarouselTextUseCase(self.registry, text_model, self.store, image_model=image_model)

    def test_fixed_two_to_five_frame_counts_are_supported(self) -> None:
        for count in (2, 3, 4, 5):
            store = SqliteAiV2Store(Path(self.temp_dir.name) / f"db-{count}.sqlite")
            use_case = CarouselTextUseCase(self.registry, DeterministicTextModel([_result(count)]), store)
            public = use_case.generate(count, _input(str(count)), 1)
            self.assertEqual([len(item["frames"]) for item in public["items"]], [count, count, count])
            store.close()

    def test_fixed_count_mismatch_is_normalized_after_one_text_call(self) -> None:
        model = DeterministicTextModel([_result(3)])
        use_case = self._use_case(model)

        public = use_case.generate(1, _input("2"), 1)
        self.assertEqual([len(item["frames"]) for item in public["items"]], [2, 2, 2])
        self.assertEqual(len(model.start_calls), 1)

    def test_builtin_screen_label_is_accepted_for_fixed_count(self) -> None:
        public = self._use_case(DeterministicTextModel([_result(3)])).generate(1, _input("3屏"), 1)
        self.assertEqual([len(item["frames"]) for item in public["items"]], [3, 3, 3])

    def test_ai_decided_count_stays_between_two_and_five(self) -> None:
        model = DeterministicTextModel([_result(4)])
        public = self._use_case(model).generate(1, _input("AI决定"), 1)
        self.assertEqual(len(public["items"][0]["frames"]), 4)

    def test_first_frame_failure_does_not_unlock_second_frame(self) -> None:
        failed = ImageSubmission("terminal_failure", "job-1", ImageSessionCursor("fake", "c", "m", 0), None, "provider_rejected")
        image_model = DeterministicImageModel(start_submissions={"v2-run-1-scheme-1:frame:1": failed})
        use_case = self._use_case(DeterministicTextModel([_result(2)]), image_model)
        use_case.generate(1, _input("2"), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_frame(scheme_id, 1)
        with self.assertRaises(CarouselTextUseCaseError) as context:
            use_case.request_frame(scheme_id, 2)

        self.assertEqual(first.status, "failed")
        self.assertEqual(context.exception.error_code, "frame_order_conflict")
        self.assertEqual(len(image_model.created_image_sessions), 1)

    def test_successful_frames_are_serial_and_share_one_session_and_reference(self) -> None:
        first_cursor = ImageSessionCursor("fake", "c", "m1", 1)
        second_cursor = ImageSessionCursor("fake", "c", "m2", 2)
        image_model = DeterministicImageModel(
            start_submissions={
                "v2-run-1-scheme-1:frame:1": ImageSubmission("success", "job-1", first_cursor, image_artifact(b"one", "image/jpeg"), None)
            },
            continue_submissions={
                "v2-run-1-scheme-1:frame:2": ImageSubmission("success", "job-2", second_cursor, image_artifact(b"two", "image/webp"), None)
            },
        )
        use_case = self._use_case(DeterministicTextModel([_result(2)]), image_model)
        use_case.generate(1, _input("2"), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_frame(scheme_id, 1)
        second = use_case.request_frame(scheme_id, 2)
        repeated = use_case.request_frame(scheme_id, 2)

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "success")
        self.assertEqual(repeated.attempt_id, second.attempt_id)
        self.assertEqual(len(image_model.created_image_sessions), 1)
        self.assertEqual(len(image_model.continue_calls), 1)
        self.assertIsNotNone(image_model.continue_calls[0].request.reference_artifact)
        self.assertEqual(image_model.continue_calls[0].request.reference_artifact.mime_type, "image/jpeg")

        refreshed = use_case._public_run(1, 1)
        self.assertEqual(refreshed["items"][0]["frames"][0]["image_state"]["status"], "success")

    def test_three_frame_continuation_stays_in_one_session(self) -> None:
        cursors = [
            ImageSessionCursor("chat2api", "conversation", "message-1", 1),
            ImageSessionCursor("chat2api", "conversation", "message-2", 2),
            ImageSessionCursor("chat2api", "conversation", "message-3", 3),
        ]
        image_model = DeterministicImageModel(
            start_submissions={
                "v2-run-1-scheme-1:frame:1": ImageSubmission("success", "job-1", cursors[0], image_artifact(b"one", "image/png"), None),
            },
            continue_submissions={
                "v2-run-1-scheme-1:frame:2": ImageSubmission("success", "job-2", cursors[1], image_artifact(b"two", "image/png"), None),
                "v2-run-1-scheme-1:frame:3": ImageSubmission("success", "job-3", cursors[2], image_artifact(b"three", "image/png"), None),
            },
        )
        use_case = self._use_case(DeterministicTextModel([_result(3)]), image_model)
        use_case.generate(1, _input("3"), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_frame(scheme_id, 1)
        second = use_case.request_frame(scheme_id, 2)
        third = use_case.request_frame(scheme_id, 3)

        self.assertEqual([first.status, second.status, third.status], ["success", "success", "success"])
        self.assertEqual(self.store.count_image_sessions(scheme_id), 1)
        self.assertEqual([call.request.request_key for call in image_model.continue_calls], [
            "v2-run-1-scheme-1:frame:2",
            "v2-run-1-scheme-1:frame:3",
        ])
        self.assertEqual(self.store.read_artifact_for_frame(scheme_id, 2).content, b"two")
        self.assertEqual(self.store.read_artifact_for_frame(scheme_id, 3).content, b"three")

    def test_async_continuation_poll_uses_attempt_job_not_first_frame_job(self) -> None:
        first_cursor = ImageSessionCursor("chat2api", "conversation", "first", 1)
        second_cursor = ImageSessionCursor("chat2api", "conversation", "second", 2)
        second_key = "v2-run-1-scheme-1:frame:2"
        image_model = DeterministicImageModel(
            start_submissions={
                "v2-run-1-scheme-1:frame:1": ImageSubmission(
                    "success", "job-1", first_cursor, image_artifact(b"one", "image/png"), None
                )
            },
            continue_submissions={
                second_key: ImageSubmission("working", "job-2", None, None, None)
            },
            reconcile_results={
                second_key: ReconcileResult(
                    "success", "job-2", second_cursor, image_artifact(b"two", "image/png"), None
                )
            },
        )
        use_case = self._use_case(DeterministicTextModel([_result(2)]), image_model)
        use_case.generate(1, _input("2"), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        use_case.request_frame(scheme_id, 1)
        second = use_case.request_frame(scheme_id, 2)
        self.assertEqual(second.status, "generating")

        ImageWorker(self.store, image_model).submit(second.attempt_id)

        state = self.store.read_image_attempt_state(second.attempt_id)
        self.assertEqual(state["status"], "success")
        self.assertEqual(image_model.reconcile_calls[-1].provider_job_id, "job-2")
        self.assertEqual(self.store.read_artifact_for_frame(scheme_id, 2).content, b"two")

    def test_terminal_failure_retry_reuses_session_and_creates_no_second_session(self) -> None:
        failed = ImageSubmission("terminal_failure", "job-1", ImageSessionCursor("fake", "c", "m1", 1), None, "provider_rejected")
        image_model = DeterministicImageModel(
            start_submissions={"v2-run-1-scheme-1:frame:1": failed},
            reconcile_results={"v2-run-1-scheme-1:frame:1": ReconcileResult("terminal_failure", "job-1", failed.cursor, None, "provider_rejected")},
            continue_submissions={"v2-run-1-scheme-1:frame:1": ImageSubmission("success", "job-2", ImageSessionCursor("fake", "c", "m2", 2), image_artifact(b"retry", "image/png"), None)},
        )
        use_case = self._use_case(DeterministicTextModel([_result(2)]), image_model)
        use_case.generate(1, _input("2"), 1)
        scheme_id = self.store.list_schemes(1)[0]["scheme_id"]

        first = use_case.request_frame(scheme_id, 1)
        retry = use_case.request_frame(scheme_id, 1)

        self.assertEqual(first.status, "failed")
        self.assertEqual(retry.status, "success")
        self.assertEqual(len(image_model.created_image_sessions), 1)
        self.assertEqual(len(image_model.start_calls), 1)
        self.assertEqual(len(image_model.continue_calls), 1)


if __name__ == "__main__":
    unittest.main()
