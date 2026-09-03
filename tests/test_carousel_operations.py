import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from creative_studio.display_frame_models import DisplayScheme
from creative_studio.carousel_operations import CarouselOperationCoordinator
from creative_studio.public_projection import PRIVATE_RESULT_FIELDS, PublicResultMapper
from creative_studio.repository import StudioRepository


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> str:
        return self.value.isoformat()

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class CarouselOperationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.clock = MutableClock()
        self.repo = StudioRepository(Path(self.temp.name) / "studio.db", clock=self.clock)
        project = self.repo.create_project("轮播项目", "展示类")
        self.project_id = int(project["id"])
        reservation = self.repo.reserve_generation(
            project["id"], "visual", "CarouselResult.v1", "carousel-fingerprint"
        )
        scheme = DisplayScheme.from_payload(
            {
                "title": "方案",
                "creative_summary": "说明",
                "creative_sources": ["原创"],
                "frame_count": 3,
                "visual_continuity_rules": ["主体一致"],
                "frame_plan": [
                    {"index": 1, "description": "首帧"},
                    {"index": 2, "description": "推进"},
                    {"index": 3, "description": "收束"},
                ],
            }
        )
        self.scheme_id = self.repo.save_display_schemes(reservation["id"], [scheme])[0]
        first = self.repo.claim_display_frame(self.scheme_id, 1)
        self.repo.complete_display_frame(
            self.scheme_id, 1, int(first["image_attempt"]), "first.png", "image/png"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_is_idempotent_while_operation_is_active(self) -> None:
        first = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "request-one", lease_seconds=30
        )
        duplicate = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "request-two", lease_seconds=30
        )

        self.assertEqual(duplicate["id"], first["id"])
        self.assertEqual(duplicate["status"], "queued")
        self.assertNotEqual(first["lease_token"], "")

    def test_heartbeat_prevents_recovery_until_lease_expires(self) -> None:
        operation = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "request-one", lease_seconds=30
        )
        self.assertTrue(
            self.repo.start_carousel_operation(
                operation["id"], operation["lease_token"], lease_seconds=30
            )
        )
        self.clock.advance(20)
        self.assertTrue(
            self.repo.heartbeat_carousel_operation(
                operation["id"], operation["lease_token"], lease_seconds=30
            )
        )
        self.clock.advance(20)
        self.assertEqual(self.repo.recover_stale_carousel_operations(), [])
        self.clock.advance(11)

        recovered = self.repo.recover_stale_carousel_operations()

        self.assertEqual(recovered, [operation["id"]])
        refreshed = self.repo.get_carousel_operation(operation["id"])
        self.assertEqual(refreshed["status"], "queued")
        self.assertNotEqual(refreshed["lease_token"], operation["lease_token"])

    def test_atomic_completion_rejects_stale_lease_and_updates_cursor(self) -> None:
        operation = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "request-one", lease_seconds=30
        )
        self.repo.start_carousel_operation(
            operation["id"], operation["lease_token"], lease_seconds=30
        )
        frame = self.repo.claim_carousel_operation_frame(
            operation["id"], operation["lease_token"], 2
        )
        self.assertIsNotNone(frame)

        stale = self.repo.complete_carousel_frame_atomic(
            operation["id"],
            "stale-token",
            2,
            int(frame["image_attempt"]),
            "second.png",
            "image/png",
            "conversation-new",
            "message-new",
        )
        committed = self.repo.complete_carousel_frame_atomic(
            operation["id"],
            operation["lease_token"],
            2,
            int(frame["image_attempt"]),
            "second.png",
            "image/png",
            "conversation-new",
            "message-new",
        )

        self.assertFalse(stale)
        self.assertTrue(committed)
        scheme = self.repo.get_display_scheme(self.scheme_id)
        self.assertEqual(scheme["frames"][1]["image_status"], "success")
        self.assertEqual(scheme["conversation_id"], "conversation-new")
        self.assertEqual(scheme["parent_message_id"], "message-new")
        refreshed = self.repo.get_carousel_operation(operation["id"])
        self.assertEqual(refreshed["completed_frame_count"], 2)
        self.assertEqual(refreshed["current_frame_index"], 3)

    def test_recovery_requeues_frame_left_generating_by_crashed_worker(self) -> None:
        operation = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "crash-request", lease_seconds=30
        )
        self.assertTrue(
            self.repo.start_carousel_operation(
                operation["id"], operation["lease_token"], lease_seconds=30
            )
        )
        frame = self.repo.claim_carousel_operation_frame(
            operation["id"], operation["lease_token"], 2
        )
        self.assertEqual(frame["image_status"], "generating")
        self.clock.advance(31)

        recovered = self.repo.recover_stale_carousel_operations()

        self.assertEqual(recovered, [operation["id"]])
        refreshed = self.repo.get_carousel_operation(operation["id"])
        self.assertEqual(refreshed["status"], "queued")
        scheme = self.repo.get_display_scheme(self.scheme_id)
        self.assertEqual(scheme["frames"][1]["image_status"], "pending")

    def test_public_operation_excludes_private_execution_fields(self) -> None:
        operation = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "request-one", lease_seconds=30
        )
        public = PublicResultMapper().carousel_operation(operation)
        encoded = json.dumps(public, ensure_ascii=False)

        self.assertEqual(public["operation_id"], operation["id"])
        self.assertNotIn("lease_token", encoded)
        self.assertNotIn("request_key", encoded)
        self.assertNotIn("revision", encoded)
        self.assertTrue(PRIVATE_RESULT_FIELDS.isdisjoint(public))

    def test_public_scheme_projection_includes_operation_without_private_lease(self) -> None:
        operation = self.repo.get_or_create_carousel_operation(
            self.scheme_id, "history-request", lease_seconds=30
        )

        public = PublicResultMapper().visual_item(
            {"id": self.scheme_id, "operation": operation}
        )
        public_operation = public["operation"]
        encoded = json.dumps(public_operation, ensure_ascii=False)

        self.assertEqual(public_operation["operation_id"], operation["id"])
        self.assertNotIn("lease_token", encoded)
        self.assertNotIn("request_key", encoded)

    def test_coordinator_starts_once_and_processes_frames_in_order(self) -> None:
        runner = ImmediateFrameRunner(self.repo)
        coordinator = CarouselOperationCoordinator(
            self.repo,
            runner,
            prompt_builder=lambda scheme, frames, index: f"frame-{index}",
            wait_timeout_seconds=2,
        )
        try:
            first = coordinator.start(self.scheme_id, "continue-request")
            duplicate = coordinator.start(self.scheme_id, "continue-request")
            self.assertEqual(first["id"], duplicate["id"])
            self.assertEqual(
                _wait_for_operation(self.repo, first["id"])["status"], "completed"
            )
            self.assertEqual([call[1] for call in runner.calls], [2, 3])
        finally:
            coordinator.stop()

    def test_coordinator_blocks_after_two_failed_attempts(self) -> None:
        runner = FailingFrameRunner(self.repo)
        coordinator = CarouselOperationCoordinator(
            self.repo,
            runner,
            prompt_builder=lambda scheme, frames, index: f"frame-{index}",
            wait_timeout_seconds=1,
        )
        try:
            operation = coordinator.start(self.scheme_id, "failure-request")
            finished = _wait_for_operation(self.repo, operation["id"])
        finally:
            coordinator.stop()

        self.assertEqual(finished["status"], "blocked")
        self.assertEqual([call[1] for call in runner.calls], [2, 2])
        self.assertEqual(self.repo.get_display_scheme(self.scheme_id)["frames"][1]["image_status"], "failed")


class ImmediateFrameRunner:
    def __init__(self, repo: StudioRepository) -> None:
        self.repo = repo
        self.calls = []

    def enqueue_frame(
        self,
        scheme_id,
        frame_index,
        prompt,
        aspect_ratio,
        previous_image_path,
        conversation_id="",
        parent_message_id="",
        operation_id=0,
        operation_token="",
    ):
        self.calls.append((scheme_id, frame_index, prompt))
        frame = self.repo.claim_carousel_operation_frame(operation_id, operation_token, frame_index)
        if frame is None:
            return
        self.repo.complete_carousel_frame_atomic(
            operation_id,
            operation_token,
            frame_index,
            int(frame["image_attempt"]),
            f"frame-{frame_index}.png",
            "image/png",
            "conversation",
            "message",
        )


class FailingFrameRunner(ImmediateFrameRunner):
    def enqueue_frame(
        self,
        scheme_id,
        frame_index,
        prompt,
        aspect_ratio,
        previous_image_path,
        conversation_id="",
        parent_message_id="",
        operation_id=0,
        operation_token="",
    ):
        self.calls.append((scheme_id, frame_index, prompt))
        frame = self.repo.claim_carousel_operation_frame(operation_id, operation_token, frame_index)
        if frame is not None:
            self.repo.fail_carousel_frame(operation_id, operation_token, frame_index, int(frame["image_attempt"]), "失败")


def _wait_for_operation(repo: StudioRepository, operation_id: int) -> dict:
    import time

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        operation = repo.get_carousel_operation(operation_id)
        if operation and operation["status"] in {"completed", "failed", "blocked"}:
            return operation
        time.sleep(0.01)
    raise AssertionError("operation did not finish")


if __name__ == "__main__":
    unittest.main()
