from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.input_contract import normalize_input
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ImageSubmission, ReconcileResult
from creative_studio.ai_v2.prompt_registry import AiV2PromptRegistry
from creative_studio.ai_v2.store import SqliteAiV2Store
from creative_studio.ai_v2.image_worker import ImageWorker
from creative_studio.ai_v2.adapters.image_gateway import ImageGatewayAdapter


class _Transport:
    def __init__(self, post=None, get=None, bytes_value=b"png"):
        self.post_payloads = []
        self.get_paths = []
        self.post_response = post or {}
        self.get_response = get or {}
        self.bytes_value = bytes_value

    def post_json(self, path, payload):
        self.post_payloads.append((path, payload))
        return self.post_response

    def get_json(self, path, params):
        self.get_paths.append((path, params))
        return self.get_response

    def get_bytes(self, path):
        return self.bytes_value


def _static_json() -> str:
    return json.dumps({
        "schema_version": "static-text-v1",
        "items": [
            {"title": str(i), "core_idea": "c", "ad_copy": "a", "image_description": "d", "execution": {"image_prompt": "p"}}
            for i in range(3)
        ]
    })


class AiV2ImageWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteAiV2Store(Path(self.temp_dir.name) / "db.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_gateway_adapter_transmits_stable_keys_and_maps_unknown_reconcile(self) -> None:
        transport = _Transport(
            post={"state": "working", "job_id": "job-1", "cursor": {"provider": "fake", "conversation_id": "c", "parent_message_id": "m", "revision": 1}},
            get={},
        )
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")
        from creative_studio.ai_v2.model_ports import ImageRequest, ReconcileRequest
        request = ImageRequest("scheme-v1", 1, "PRIVATE_PROMPT", "session-key", "request-key", "16:9", None)
        submission = adapter.start_image_session(request)
        result = adapter.reconcile(ReconcileRequest("session-key", "request-key", submission.cursor, submission.provider_job_id))

        self.assertEqual(transport.post_payloads[0][1]["image_session_key"], "session-key")
        self.assertEqual(transport.post_payloads[0][1]["request_key"], "request-key")
        self.assertEqual(submission.state, "working")
        self.assertEqual(result.state, "unknown")

    def test_worker_completes_success_with_real_mime_and_reference_artifact(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, json.loads(_static_json()), __import__("creative_studio.ai_v2.model_ports", fromlist=["TextSession"]).TextSession("t", "c", "m"))
        scheme = self.store.list_schemes(run.run_id)[0]
        session = self.store.ensure_image_session(scheme["scheme_id"], "session", ImageSessionCursor("fake", "c", "m", 0))
        attempt = self.store.reserve_image_attempt(scheme["scheme_id"], 1, scheme["scheme_version"] + ":frame:1")
        image_model = DeterministicImageModel(continue_submissions={scheme["scheme_version"] + ":frame:1": ImageSubmission("success", "job", ImageSessionCursor("fake", "c", "m2", 1), image_artifact(b"webp", "image/webp"), None)})
        worker = ImageWorker(self.store, image_model)

        worker.submit(attempt.attempt_id)

        state = self.store.read_image_attempt_state(attempt.attempt_id)
        self.assertEqual(state["status"], "success")
        self.assertEqual(self.store.read_artifact_for_frame(scheme["scheme_id"], 1).mime_type, "image/webp")
        self.assertEqual(image_model.continue_calls[0].request.image_session_key, "session")

    def test_worker_unknown_reconcile_does_not_create_new_attempt_or_session(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, json.loads(_static_json()), __import__("creative_studio.ai_v2.model_ports", fromlist=["TextSession"]).TextSession("t", "c", "m"))
        scheme = self.store.list_schemes(run.run_id)[0]
        self.store.ensure_image_session(scheme["scheme_id"], "session", ImageSessionCursor("fake", "c", "m", 0))
        attempt = self.store.reserve_image_attempt(scheme["scheme_id"], 1, scheme["scheme_version"] + ":frame:1")
        self.store.fail_image_attempt(attempt.attempt_id, "timeout_unknown", True)
        image_model = DeterministicImageModel(reconcile_results={scheme["scheme_version"] + ":frame:1": ReconcileResult("unknown", "job", None, None, "provider_unknown")})
        worker = ImageWorker(self.store, image_model)

        worker.submit(attempt.attempt_id)

        self.assertEqual(len(image_model.reconcile_calls), 1)
        self.assertEqual(self.store.find_image_attempt(scheme["scheme_id"], 1, scheme["scheme_version"] + ":frame:1").attempt_no, 1)  # type: ignore[union-attr]
        self.assertEqual(self.store.count_image_sessions(scheme["scheme_id"]), 1)

    def test_concurrent_worker_poll_claims_pending_attempt_once(self) -> None:
        run = self.store.reserve_run(1, "static", "fp", 1)
        self.store.save_text_result(run.run_id, json.loads(_static_json()), __import__("creative_studio.ai_v2.model_ports", fromlist=["TextSession"]).TextSession("t", "c", "m"))
        scheme = self.store.list_schemes(run.run_id)[0]
        self.store.ensure_image_session(scheme["scheme_id"], "session", ImageSessionCursor("fake", "c", "m", 0))
        attempt = self.store.reserve_image_attempt(scheme["scheme_id"], 1, scheme["scheme_version"] + ":frame:1")

        class BlockingImageModel(DeterministicImageModel):
            def __init__(self) -> None:
                super().__init__()
                self.started = threading.Event()
                self.release = threading.Event()

            def continue_image_session(self, request):  # type: ignore[no-untyped-def]
                self.continue_calls.append(request)
                self.started.set()
                self.release.wait(timeout=3)
                return ImageSubmission("working", "job", request.cursor, None, None)

        image_model = BlockingImageModel()
        worker_one = ImageWorker(self.store, image_model)
        other_store = SqliteAiV2Store(self.store.database)
        worker_two = ImageWorker(other_store, image_model)
        errors: list[Exception] = []

        def run_worker(worker: ImageWorker) -> None:
            try:
                worker.submit(attempt.attempt_id)
            except Exception as exc:  # noqa: BLE001 - no worker failure expected.
                errors.append(exc)

        first = threading.Thread(target=run_worker, args=(worker_one,))
        first.start()
        self.assertTrue(image_model.started.wait(timeout=2))
        second = threading.Thread(target=run_worker, args=(worker_two,))
        second.start()
        second.join(timeout=2)
        image_model.release.set()
        first.join(timeout=3)
        other_store.close()

        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(len(image_model.continue_calls), 1)
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
