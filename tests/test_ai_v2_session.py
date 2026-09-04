from __future__ import annotations

import unittest

from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.model_ports import (
    ImageContinuation,
    ImageRequest,
    ReconcileRequest,
    ReconcileResult,
    TextRequest,
)


class AiV2SessionTests(unittest.TestCase):
    def test_each_text_batch_creates_one_new_text_session(self) -> None:
        fake = DeterministicTextModel(["{\"batch\": 1}", "{\"batch\": 2}"])
        request = TextRequest("prompt", "narrative-text", "narrative-text-v1", "model", "run-1")

        first = fake.start_text(request)
        second = fake.start_text(request)

        self.assertNotEqual(first.session.session_id, second.session.session_id)
        self.assertEqual(len(fake.start_calls), 2)

    def test_three_schemes_create_three_image_sessions(self) -> None:
        fake = DeterministicImageModel()
        for scheme_id in ("scheme-a", "scheme-b", "scheme-c"):
            request = ImageRequest("run-1-" + scheme_id, 1, "prompt", "run-1-" + scheme_id, scheme_id + "-frame-1", "16:9", None)
            fake.start_image_session(request)

        self.assertEqual(len(fake.created_image_sessions), 3)
        self.assertEqual({call.image_session_key for call in fake.start_calls}, {"run-1-scheme-a", "run-1-scheme-b", "run-1-scheme-c"})

    def test_carousel_frames_continue_with_one_image_session(self) -> None:
        fake = DeterministicImageModel()
        first_request = ImageRequest("run-1-scheme-a", 1, "first", "run-1-scheme-a", "scheme-a-frame-1", "16:9", None)
        first = fake.start_image_session(first_request)
        self.assertIsNotNone(first.cursor)

        second_request = ImageRequest("run-1-scheme-a", 2, "second", "run-1-scheme-a", "scheme-a-frame-2", "16:9", image_artifact(b"one", "image/png"))
        second = fake.continue_image_session(ImageContinuation(second_request, first.cursor))  # type: ignore[arg-type]
        third_request = ImageRequest("run-1-scheme-a", 3, "third", "run-1-scheme-a", "scheme-a-frame-3", "16:9", image_artifact(b"two", "image/png"))
        fake.continue_image_session(ImageContinuation(third_request, second.cursor))  # type: ignore[arg-type]

        self.assertEqual(len(fake.created_image_sessions), 1)
        self.assertEqual(len(fake.continue_calls), 2)
        self.assertEqual(fake.continue_calls[0].request.image_session_key, "run-1-scheme-a")

    def test_unknown_reconcile_does_not_create_new_session_or_attempt(self) -> None:
        fake = DeterministicImageModel(
            reconcile_results={
                "scheme-a-frame-1": ReconcileResult("unknown", None, None, None, "provider_unavailable")
            }
        )
        request = ImageRequest("run-1-scheme-a", 1, "prompt", "run-1-scheme-a", "scheme-a-frame-1", "16:9", None)
        fake.start_image_session(request)
        result = fake.reconcile(ReconcileRequest("run-1-scheme-a", "scheme-a-frame-1", None, "job-1"))

        self.assertEqual(result.state, "unknown")
        self.assertEqual(len(fake.created_image_sessions), 1)
        self.assertEqual(len(fake.start_calls), 1)
        self.assertEqual(len(fake.reconcile_calls), 1)


if __name__ == "__main__":
    unittest.main()
