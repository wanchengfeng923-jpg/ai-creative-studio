from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.fakes import image_artifact
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ReconcileResult, TextSession
from creative_studio.ai_v2.store import AiV2StoreConflict, SqliteAiV2Store


def _static_result() -> dict[str, object]:
    return {
        "schema_version": "static-text-v1",
        "items": [
            {
                "title": f"方案 {index}",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "image_description": "画面描述",
                "execution": {"image_prompt": "图片提示词"},
            }
            for index in range(3)
        ],
    }


def _carousel_result() -> dict[str, object]:
    return {
        "schema_version": "carousel-text-v1",
        "items": [
            {
                "title": "方案",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "frames": [
                    {"index": 1, "description": "首帧"},
                    {"index": 2, "description": "第二帧"},
                ],
                "execution": {
                    "continuity_rules": ["主体一致"],
                    "image_prompts": [
                        {"index": 1, "prompt": "首帧图"},
                        {"index": 2, "prompt": "第二帧图"},
                    ],
                },
            }
            for _ in range(3)
        ],
    }


class AiV2StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "ai-v2.db"
        self.store = SqliteAiV2Store(self.database)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_additive_migration_is_idempotent_and_creates_only_v2_tables(self) -> None:
        self.store.migrate()
        self.store.migrate()
        connection = sqlite3.connect(self.database)
        try:
            names = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            connection.close()
        self.assertTrue({"ai_v2_runs", "ai_v2_schemes", "ai_v2_frames", "ai_v2_image_sessions", "ai_v2_image_attempts", "ai_v2_artifacts"} <= names)
        self.assertFalse({"generations", "visual_items", "display_frames", "carousel_operations"} & names)

    def test_reserves_at_most_two_batches_and_keeps_failed_runs(self) -> None:
        first = self.store.reserve_run(1, "static", "same", 1)
        self.store.fail_run(first.run_id, "model_output_invalid")
        second = self.store.reserve_run(1, "static", "same", 2)
        self.store.fail_run(second.run_id, "provider_unavailable")
        with self.assertRaises(AiV2StoreConflict):
            self.store.reserve_run(1, "static", "same", 3)
        self.assertEqual(self.store.count_runs(1, "same"), 2)

    def test_rejects_repeating_an_existing_batch_index(self) -> None:
        self.store.reserve_run(1, "static", "same", 1)
        with self.assertRaises(AiV2StoreConflict):
            self.store.reserve_run(1, "static", "same", 1)

    def test_persists_aspect_ratio_for_image_requests(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1, aspect_ratio="9:16")
        self.assertEqual(self.store.read_public_run(1, run.run_id)["aspect_ratio"], "9:16")

    def test_saves_static_schemes_and_single_pending_frame_each(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, _static_result(), TextSession("s", "c", "m"))
        schemes = self.store.list_schemes(run.run_id)
        self.assertEqual(len(schemes), 3)
        self.assertEqual([frame["status"] for frame in self.store.list_frames(schemes[0]["scheme_id"])], ["pending"])
        self.assertEqual(self.store.read_public_run(1, run.run_id)["status"], "success")

    def test_image_attempt_request_key_is_idempotent_and_failed_retry_keeps_session(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, _static_result(), TextSession("s", "c", "m"))
        scheme_id = self.store.list_schemes(run.run_id)[0]["scheme_id"]
        session = self.store.ensure_image_session(scheme_id, "run:scheme", ImageSessionCursor("p", "c", "m", 0))
        attempt = self.store.reserve_image_attempt(scheme_id, 1, "scheme:frame:1")
        self.assertEqual(attempt.image_session_id, session.session_id)
        self.assertEqual(self.store.find_image_attempt(scheme_id, 1, "scheme:frame:1").attempt_id, attempt.attempt_id)  # type: ignore[union-attr]
        with self.assertRaises(AiV2StoreConflict):
            self.store.reserve_image_attempt(scheme_id, 1, "scheme:frame:1")
        self.store.fail_image_attempt(attempt.attempt_id, "image_generation_failed", True)
        retry = self.store.reserve_image_attempt(scheme_id, 1, "scheme:frame:1")
        self.assertEqual(retry.attempt_no, 2)
        self.assertEqual(retry.image_session_id, session.session_id)

    def test_carousel_cannot_reserve_frame_two_before_frame_one_success(self) -> None:
        run = self.store.reserve_run(1, "carousel", "fp", 1)
        self.store.save_text_result(run.run_id, _carousel_result(), TextSession("s", "c", "m"))
        scheme_id = self.store.list_schemes(run.run_id)[0]["scheme_id"]
        self.store.ensure_image_session(scheme_id, "run:scheme", ImageSessionCursor("p", "c", "m", 0))
        with self.assertRaises(AiV2StoreConflict):
            self.store.reserve_image_attempt(scheme_id, 2, "scheme:frame:2")
        first = self.store.reserve_image_attempt(scheme_id, 1, "scheme:frame:1")
        artifact = image_artifact(b"png", "image/png")
        self.store.complete_image_attempt_atomic(first.attempt_id, artifact, ImageSessionCursor("p", "c", "m2", 1))
        second = self.store.reserve_image_attempt(scheme_id, 2, "scheme:frame:2")
        self.assertEqual(second.frame_index, 2)

    def test_atomic_completion_rejects_stale_attempt_and_persists_artifact_cursor(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, _static_result(), TextSession("s", "c", "m"))
        scheme_id = self.store.list_schemes(run.run_id)[0]["scheme_id"]
        session = self.store.ensure_image_session(scheme_id, "run:scheme", ImageSessionCursor("p", "c", "m", 0))
        attempt = self.store.reserve_image_attempt(scheme_id, 1, "scheme:frame:1")
        artifact = image_artifact(b"jpeg", "image/jpeg")
        self.store.complete_image_attempt_atomic(attempt.attempt_id, artifact, ImageSessionCursor("p", "c", "m2", 1))
        with self.assertRaises(AiV2StoreConflict):
            self.store.complete_image_attempt_atomic(attempt.attempt_id, artifact, ImageSessionCursor("p", "c", "m3", 2))
        self.assertEqual(self.store.find_image_session(scheme_id, "run:scheme").cursor.parent_message_id, "m2")  # type: ignore[union-attr]
        self.assertEqual(self.store.find_image_attempt(scheme_id, 1, "scheme:frame:1").status, "success")  # type: ignore[union-attr]

    def test_existing_image_session_can_recover_missing_local_attempt(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, _static_result(), TextSession("s", "c", "m"))
        scheme_id = self.store.list_schemes(run.run_id)[0]["scheme_id"]
        session = self.store.ensure_image_session(scheme_id, "run:scheme", ImageSessionCursor("p", "c", "m", 0))
        recovered = self.store.reserve_image_attempt(scheme_id, 1, "scheme:frame:1")
        self.assertEqual(recovered.image_session_id, session.session_id)
        self.assertEqual(recovered.attempt_no, 1)


if __name__ == "__main__":
    unittest.main()
