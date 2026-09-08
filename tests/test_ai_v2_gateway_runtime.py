from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creative_studio.ai_v2.adapters.image_gateway import ImageGatewayAdapter
from creative_studio.ai_v2.adapters.text_gateway import TextGatewayAdapter
from creative_studio.ai_v2.adapters.text_gateway import TextGatewayError
from creative_studio.ai_v2.application import AiV2Application, AiV2ApplicationError
from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.http_api import AiV2HttpApi
from creative_studio.ai_v2.model_ports import (
    ImageContinuation,
    ImageRequest,
    ImageSessionCursor,
    ImageSubmission,
    ReconcileRequest,
    ReconcileResult,
    TextRequest,
)
from creative_studio.ai_v2.store import SqliteAiV2Store
from creative_studio.app import StudioHandler, create_application
from launcher import Launcher, WEB_BIND_HOST


class _Transport:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, object]]] = []
        self.gets: list[tuple[str, dict[str, object]]] = []
        self.post_response: dict[str, object] = {}
        self.get_response: dict[str, object] = {}
        self.download = (b"image", "image/png")

    def post_json(self, path, payload):
        self.posts.append((path, dict(payload)))
        return self.post_response

    def get_json(self, path, params):
        self.gets.append((path, dict(params)))
        return self.get_response

    def get_bytes(self, path):
        return self.download


class _FailingTransport(_Transport):
    def post_json(self, path, payload):
        self.posts.append((path, dict(payload)))
        raise TimeoutError("response was lost")


def _static_text() -> str:
    return json.dumps({
        "schema_version": "static-text-v1",
        "items": [
            {"title": str(index), "core_idea": "c", "ad_copy": "a", "image_description": "d", "content_extensions": ["e"], "reference_sources": [{"name": "r", "note": "n"}], "execution": {"image_prompt": "p"}}
            for index in range(3)
        ],
    })


class AiV2GatewayRuntimeTests(unittest.TestCase):
    def test_text_adapter_posts_one_chat_completion_and_returns_typed_session(self) -> None:
        transport = _Transport()
        transport.post_response = {
            "choices": [{"message": {"content": "{\"ok\":true}"}}],
            "conversation_id": "conversation-1",
            "assistant_message_id": "message-1",
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        adapter = TextGatewayAdapter(transport, base_url="http://127.0.0.1:8780", model="gpt-v2")

        response = adapter.start_text(TextRequest("prompt", "prompt-id", "schema-v1", "ignored", "stable-key"))

        self.assertEqual(len(transport.posts), 1)
        self.assertEqual(transport.posts[0][0], "http://127.0.0.1:8780/v1/chat/completions")
        self.assertEqual(transport.posts[0][1]["model"], "gpt-v2")
        self.assertEqual(transport.posts[0][1]["messages"], [{"role": "user", "content": "prompt"}])
        self.assertEqual(transport.posts[0][1]["request_id"], "stable-key")
        self.assertEqual(response.raw_text, '{"ok":true}')
        self.assertEqual(response.session.conversation_id, "conversation-1")
        self.assertEqual(response.session.parent_message_id, "message-1")
        self.assertEqual(response.usage_source, "exact")

    def test_text_adapter_does_not_retry_invalid_gateway_output(self) -> None:
        transport = _Transport()
        transport.post_response = {"choices": []}
        adapter = TextGatewayAdapter(transport, base_url="http://127.0.0.1:8780", model="gpt-v2")

        with self.assertRaises(TextGatewayError):
            adapter.start_text(TextRequest("prompt", "prompt-id", "schema-v1", "ignored", "stable-key"))

        self.assertEqual(len(transport.posts), 1)

    def test_image_adapter_uses_job_protocol_and_continuation_data_url(self) -> None:
        transport = _Transport()
        transport.post_response = {"job_id": "job-1", "status": "queued"}
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")
        reference = image_artifact(b"jpeg", "image/jpeg")
        request = ImageRequest(
            "scheme", 2, "prompt", "session-key", "request-key", "16:9", reference,
            provider_request_id="request-key:attempt:2",
        )

        result = adapter.continue_image_session(ImageContinuation(
            request,
            ImageSessionCursor("chat2api", "conversation", "parent", 1),
        ))

        path, payload = transport.posts[0]
        self.assertEqual(path, "http://127.0.0.1:8780/v1/images/jobs")
        self.assertEqual(payload["request_id"], "request-key:attempt:2")
        self.assertEqual(payload["image_session_key"], "session-key")
        self.assertEqual(payload["request_key"], "request-key")
        self.assertEqual(payload["conversation_id"], "conversation")
        self.assertEqual(payload["parent_message_id"], "parent")
        self.assertEqual(payload["image"], "data:image/jpeg;base64," + base64.b64encode(b"jpeg").decode("ascii"))
        self.assertEqual(result.state, "working")

    def test_actual_failed_job_envelope_requires_explicit_terminal_marker(self) -> None:
        request = ReconcileRequest("session", "logical-key", None, "job-1")
        for error in ("gateway_restarted", "upstream page closed unexpectedly"):
            with self.subTest(error=error):
                transport = _Transport()
                transport.get_response = {
                    "job_id": "job-1",
                    "request_id": "logical-key:attempt:1",
                    "status": "failed",
                    "image_url": "",
                    "error": error,
                    "conversation_id": "",
                    "parent_message_id": "",
                }
                adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")
                self.assertEqual(adapter.reconcile(request).state, "unknown")

        transport = _Transport()
        transport.get_response = {
            "job_id": "job-1",
            "request_id": "logical-key:attempt:1",
            "status": "failed",
            "error": "provider_rejected",
            "terminal_failure": True,
        }
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")
        self.assertEqual(adapter.reconcile(request).state, "terminal_failure")

    def test_image_reconcile_gets_job_and_downloads_declared_mime(self) -> None:
        transport = _Transport()
        transport.get_response = {
            "job_id": "job-1",
            "status": "success",
            "image_url": "http://127.0.0.1:8780/images/result.webp",
            "conversation_id": "conversation",
            "parent_message_id": "parent-2",
        }
        transport.download = (b"webp", "image/webp")
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")

        result = adapter.reconcile(ReconcileRequest(
            "session-key", "request-key", ImageSessionCursor("chat2api", "conversation", "parent-1", 1), "job-1"
        ))

        self.assertEqual(transport.gets[0][0], "http://127.0.0.1:8780/v1/images/jobs/job-1")
        self.assertEqual(result.state, "success")
        self.assertEqual(result.artifact.content, b"webp")  # type: ignore[union-attr]
        self.assertEqual(result.artifact.mime_type, "image/webp")  # type: ignore[union-attr]
        self.assertEqual(result.cursor.revision, 2)  # type: ignore[union-attr]

    def test_image_start_recovers_already_successful_idempotent_job(self) -> None:
        transport = _Transport()
        transport.post_response = {
            "job_id": "job-1",
            "status": "success",
            "image_url": "http://localhost:8780/images/result.jpg",
            "conversation_id": "conversation",
            "parent_message_id": "parent",
        }
        transport.download = (b"jpeg", "image/jpeg; charset=binary")
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")

        result = adapter.start_image_session(ImageRequest(
            "scheme", 1, "prompt", "session-key", "request-key", "16:9", None
        ))

        self.assertEqual(result.state, "success")
        self.assertEqual(result.artifact.mime_type, "image/jpeg")  # type: ignore[union-attr]
        self.assertEqual(result.cursor.revision, 1)  # type: ignore[union-attr]

    def test_continuation_immediate_success_increments_existing_cursor(self) -> None:
        transport = _Transport()
        transport.post_response = {
            "job_id": "job-2",
            "status": "success",
            "image_url": "http://127.0.0.1:8780/images/result.png",
            "conversation_id": "conversation",
            "parent_message_id": "parent-2",
        }
        transport.download = (b"png", "image/png")
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")
        previous = ImageSessionCursor("chat2api", "conversation", "parent-1", 4)
        request = ImageRequest(
            "scheme", 2, "prompt", "session", "logical-key", "16:9", None,
            provider_request_id="logical-key:attempt:1",
        )

        result = adapter.continue_image_session(ImageContinuation(request, previous))

        self.assertEqual(result.state, "success")
        self.assertEqual(result.cursor.revision, 5)  # type: ignore[union-attr]

    def test_image_reconcile_rejects_cross_origin_download(self) -> None:
        transport = _Transport()
        transport.get_response = {
            "job_id": "job-1",
            "status": "success",
            "image_url": "https://example.invalid/result.png",
            "conversation_id": "conversation",
            "parent_message_id": "parent",
        }
        adapter = ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780")

        result = adapter.reconcile(ReconcileRequest("session", "request", None, "job-1"))

        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.error_code, "provider_protocol_invalid")

    def test_attempt_get_reconciles_original_working_attempt_to_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SqliteAiV2Store(Path(directory) / "studio.db")
            cursor = ImageSessionCursor("fake", "conversation", "parent-1", 1)
            model = DeterministicImageModel(
                start_submissions={"v2-run-1-scheme-1:frame:1": ImageSubmission("working", "job-1", cursor, None, None)},
                reconcile_results={"v2-run-1-scheme-1:frame:1": ReconcileResult("success", "job-1", ImageSessionCursor("fake", "conversation", "parent-2", 2), image_artifact(b"png", "image/png"), None)},
            )
            application = AiV2Application(
                store,
                text_model=DeterministicTextModel([_static_text()]),
                image_model=model,
                project_provider=lambda project_id: {"id": project_id, "script_type": "展示类"},
            )
            generated = application.generate(1, {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}})
            view = application.image(generated["items"][0]["scheme_id"])

            state = application.image_attempt(view.attempt_id)

            self.assertEqual(state["status"], "success")
            self.assertEqual(len(model.reconcile_calls), 1)
            store.close()

    def test_attempt_get_keeps_unknown_on_original_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SqliteAiV2Store(Path(directory) / "studio.db")
            cursor = ImageSessionCursor("fake", "conversation", "parent", 1)
            model = DeterministicImageModel(
                start_submissions={"v2-run-1-scheme-1:frame:1": ImageSubmission("working", "job-1", cursor, None, None)},
                reconcile_results={"v2-run-1-scheme-1:frame:1": ReconcileResult("unknown", "job-1", cursor, None, "provider_unavailable")},
            )
            application = AiV2Application(
                store,
                text_model=DeterministicTextModel([_static_text()]),
                image_model=model,
                project_provider=lambda project_id: {"id": project_id, "script_type": "展示类"},
            )
            generated = application.generate(1, {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}})
            scheme_id = generated["items"][0]["scheme_id"]
            view = application.image(scheme_id)

            state = application.image_attempt(view.attempt_id)

            current = store.find_image_attempt(scheme_id, 1, "v2-run-1-scheme-1:frame:1")
            self.assertEqual(state["status"], "generating")
            self.assertEqual(current.attempt_no, 1)  # type: ignore[union-attr]
            self.assertEqual(store.count_image_sessions(scheme_id), 1)
            store.close()

    def test_composition_root_fails_closed_until_prompt_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                environment={"CREATIVE_STUDIO_AI_GATEWAY_URL": "http://127.0.0.1:8780"},
            )
            with self.assertRaises(AiV2ApplicationError) as context:
                _ = application.ai_v2_application
            self.assertEqual(context.exception.error_code, "ai_not_enabled")

    def test_composition_root_fails_closed_without_live_or_injected_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                environment={},
            )

            try:
                with self.assertRaises(AiV2ApplicationError) as context:
                    _ = application.ai_v2_application

                self.assertEqual(context.exception.error_code, "ai_not_enabled")
                self.assertEqual(context.exception.phase, "configuration")
                self.assertFalse(context.exception.retryable)
            finally:
                if application._ai_v2_application is not None:
                    application._ai_v2_application.store.close()

    def test_composition_root_constructs_gateway_only_with_explicit_live_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                environment={"CREATIVE_STUDIO_AI_V2_LIVE": "1"},
            )
            ai_v2 = application.ai_v2_application
            self.assertIsInstance(ai_v2.static.text_model, TextGatewayAdapter)  # type: ignore[union-attr]
            self.assertIsInstance(ai_v2.static.image_model, ImageGatewayAdapter)  # type: ignore[union-attr]
            ai_v2.store.close()  # type: ignore[union-attr]

    def test_launcher_defaults_to_loopback_web_binding(self) -> None:
        self.assertEqual(WEB_BIND_HOST, "127.0.0.1")

    def test_composition_root_exposes_only_v2_ai_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                database_path=root / "studio.db",
                uploads_dir=root / "uploads",
                environment={},
                ai_v2_text_model=DeterministicTextModel([_static_text()]),
                ai_v2_image_model=DeterministicImageModel(),
            )

            self.assertFalse(hasattr(application, "generation_service"))
            self.assertFalse(hasattr(application, "image_runner"))
            self.assertIsNotNone(application.ai_v2_application)
            application.ai_v2_application.store.close()  # type: ignore[union-attr]

    def test_legacy_generation_post_routes_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                database_path=root / "studio.db",
                uploads_dir=root / "uploads",
                environment={},
                ai_v2_text_model=DeterministicTextModel([_static_text()]),
                ai_v2_image_model=DeterministicImageModel(),
            )
            context = SimpleNamespace(user={"id": 1, "role": "admin", "must_change_password": False})

            for path in (
                "/api/projects/1/generate",
                "/api/visual-items/1/select",
                "/api/visual-items/1/continue",
                "/api/visual-items/1/retry",
                "/api/projects/1/adopt",
            ):
                with self.subTest(path=path):
                    handler = object.__new__(StudioHandler)
                    handler.server = SimpleNamespace(application=application)
                    handler.path = path
                    handler.headers = {}
                    handler.rfile = io.BytesIO()
                    handler.client_address = ("127.0.0.1", 1)
                    handler._require_auth = lambda **_kwargs: context
                    handler._context = lambda: context
                    handler._require_project_access = lambda *_args: {}
                    responses = []
                    handler._json = lambda payload, status=HTTPStatus.OK: responses.append(
                        (payload, HTTPStatus(status))
                    )

                    StudioHandler._post(handler)

                    self.assertEqual(responses[-1][1], HTTPStatus.NOT_FOUND)

    def test_initial_image_timeout_returns_503_without_local_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SqliteAiV2Store(Path(directory) / "studio.db")
            transport = _FailingTransport()
            application = AiV2Application(
                store,
                text_model=DeterministicTextModel([_static_text()]),
                image_model=ImageGatewayAdapter(transport, base_url="http://127.0.0.1:8780"),
                project_provider=lambda project_id: {"id": project_id, "script_type": "展示类"},
            )
            api = AiV2HttpApi(application)
            _, generated = api.dispatch("POST", "/api/v2/projects/1/generate", {
                "task_description": "x", "aspect_ratio": "16:9", "creative_tags": {},
            })
            scheme_id = generated["items"][0]["scheme_id"]

            first = api.dispatch("POST", f"/api/v2/schemes/{scheme_id}/image", {})
            second = api.dispatch("POST", f"/api/v2/schemes/{scheme_id}/image", {})

            self.assertEqual(first[0], 503)
            self.assertTrue(first[1]["retryable"])
            self.assertEqual(second[0], 503)
            self.assertEqual(store.count_image_sessions(scheme_id), 0)
            self.assertIsNone(store.find_image_attempt(scheme_id, 1, "v2-run-1-scheme-1:frame:1"))
            self.assertEqual(transport.posts[0][1]["request_id"], transport.posts[1][1]["request_id"])
            store.close()

    def test_launcher_injects_only_v2_ai_runtime_names(self) -> None:
        with patch.dict("os.environ", {"WEB_ERP_AI_API_URL": "legacy"}, clear=False):
            with patch("launcher.read_env", return_value={"CHATGPT_CONTROL_TOKEN": "control"}):
                environment = Launcher._environment(object.__new__(Launcher))

        self.assertEqual(environment["CREATIVE_STUDIO_AI_GATEWAY_URL"], "http://127.0.0.1:8780")
        self.assertEqual(environment["CREATIVE_STUDIO_AI_CONTROL_TOKEN"], "control")
        self.assertFalse(any(key.startswith("WEB_ERP_AI_") for key in environment))


if __name__ == "__main__":
    unittest.main()
