from __future__ import annotations

from http import HTTPStatus
import io
import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from creative_studio.ai_creative import (
    AiCreativeConfigurationError,
    AiCreativeQueueTimeoutError,
    AiCreativeRequestError,
)
from creative_studio.app import StudioApplication, StudioHandler
from creative_studio.generation_models import (
    GenerationConflictError,
    GenerationInputError,
    GenerationNotFoundError,
    GenerationQueueTimeoutError,
)
from creative_studio.model_client import ModelResponse
from creative_studio.repository import StudioDataError


class FakeImageRunner:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def enqueue(self, item_ids) -> None:
        return None


class FakeModelClient:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        stories = [
            {
                "story": f"故事{index}",
                "hooks": [
                    {"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]},
                    {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]},
                ],
            }
            for index in range(1, 6)
        ]
        return ModelResponse(content=json.dumps({"items": stories,}, ensure_ascii=False))


class DummyHandler:
    def __init__(self) -> None:
        self.responses: list[tuple[dict[str, object], HTTPStatus]] = []

    def _json(self, payload, status=HTTPStatus.OK):
        self.responses.append((payload, HTTPStatus(status)))


class AppApiTests(unittest.TestCase):
    @staticmethod
    def _private_fields_in(value):
        private = {
            "image_prompt",
            "image_generation_instruction",
            "conversation_id",
            "parent_message_id",
            "assistant_message_id",
            "image_path",
            "stored_name",
            "gateway_job_id",
            "raw_response",
            "private_context",
            "stack_trace",
            "error_detail",
        }
        found = set()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in private:
                    found.add(key)
                found.update(AppApiTests._private_fields_in(child))
        elif isinstance(value, (list, tuple)):
            for child in value:
                found.update(AppApiTests._private_fields_in(child))
        return found

    @staticmethod
    def _call_route(application, method: str, path: str, payload=None, *, headers=None, body=b""):
        handler = object.__new__(StudioHandler)
        handler.server = SimpleNamespace(application=application)
        handler.path = path
        handler.headers = dict(headers or {})
        handler.rfile = io.BytesIO(body)
        handler.client_address = ("127.0.0.1", 1)
        responses = []
        handler._json = lambda value, status=HTTPStatus.OK: responses.append((value, HTTPStatus(status)))
        handler._read_json = lambda: dict(payload or {})
        getattr(StudioHandler, method)(handler)
        return responses[-1]

    def test_import_does_not_construct_runtime_dependencies(self) -> None:
        import creative_studio.app as app_module

        with patch("creative_studio.repository.StudioRepository.__init__", side_effect=AssertionError("database opened")), patch(
            "creative_studio.image_jobs.ImageJobRunner.__init__",
            side_effect=AssertionError("executor created"),
        ), patch(
            "creative_studio.model_client.HttpModelClient.__init__",
            side_effect=AssertionError("model client created"),
        ):
            reloaded = importlib.reload(app_module)

        self.assertFalse(hasattr(reloaded, "APP"))

    def test_composition_root_crosses_http_generate_route_with_fake_ports_and_fixed_clock(self) -> None:
        from creative_studio.app import create_application

        class Auth:
            cookie_secure = False

            def authenticate_session(self, *args):
                return SimpleNamespace(
                    user={"id": 1, "role": "admin", "must_change_password": False}
                )

        fixed_time = "2026-09-03 12:34:56"
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            runner = FakeImageRunner()
            model = FakeModelClient()
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                model_client=model,
                image_runner=runner,
                clock=lambda: fixed_time,
                environment={},
            )
            project = application.repository.create_project("测试项目", "叙事类")
            application.repository.update_project(project["id"], {"task_description": "叙事说明"})
            application.auth = Auth()
            response, status = self._call_route(
                application,
                "_post",
                f"/api/projects/{project['id']}/generate",
            )

        self.assertIs(application.image_runner, runner)
        self.assertEqual(project["created_at"], fixed_time)
        self.assertEqual(len(model.requests), 1)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(response["success"])
        self.assertEqual(response["batches"][0]["created_at"], fixed_time)
        self.assertEqual(self._private_fields_in(response), set())

    def test_select_scheme_public_result_does_not_include_conversation_cursor(self) -> None:
        class Service:
            def select_scheme(self, item_id):
                return {
                    "scheme_id": item_id,
                    "title": "方案",
                    "conversation_id": "private-conversation",
                    "parent_message_id": "private-message",
                }

        application = object.__new__(StudioApplication)
        application.generation_service = Service()

        result = application.select_visual_scheme(9)

        self.assertEqual(result, {"scheme_id": 9, "title": "方案"})

    def test_continue_route_returns_accepted_operation_and_public_scheme(self) -> None:
        operation = {
            "operation_id": 12,
            "scheme_id": 9,
            "status": "queued",
            "total_frame_count": 3,
        }
        application = object.__new__(StudioApplication)
        application.repository = SimpleNamespace(get_visual_item_owner_id=lambda item_id: 7)
        application.continue_visual_scheme = lambda item_id: {
            "operation": operation,
            "scheme": {"scheme_id": item_id, "title": "方案", "image_status": "success"},
        }
        handler = object.__new__(StudioHandler)
        handler.server = SimpleNamespace(application=application)
        handler.path = "/api/visual-items/9/continue"
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 1)
        handler._require_auth = lambda **kwargs: SimpleNamespace(user={"id": 7, "role": "user"})
        handler._context = lambda: SimpleNamespace(user={"id": 7, "role": "user"})
        responses = []
        handler._json = lambda value, status=HTTPStatus.OK: responses.append((value, HTTPStatus(status)))

        StudioHandler._post(handler)

        payload, status = responses[-1]
        self.assertEqual(status, HTTPStatus.ACCEPTED)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["operation"]["operation_id"], 12)

    def test_operation_route_enforces_scheme_ownership(self) -> None:
        # The import-isolation test reloads the app module; use its current
        # class identity so the handler property accepts this fixture.
        current_application_type = importlib.import_module("creative_studio.app").StudioApplication
        application = object.__new__(current_application_type)
        application.repository = SimpleNamespace(get_visual_item_owner_id=lambda item_id: 99)
        application.carousel_operation_status = lambda item_id, operation_id: self.fail(
            "must not read operation"
        )
        handler = object.__new__(StudioHandler)
        handler.server = SimpleNamespace(application=application)
        handler.path = "/api/visual-items/9/operation/12"
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 1)
        handler._require_auth = lambda **kwargs: SimpleNamespace(user={"id": 7, "role": "user"})
        handler._context = lambda: SimpleNamespace(user={"id": 7, "role": "user"})
        responses = []
        handler._json = lambda value, status=HTTPStatus.OK: responses.append((value, HTTPStatus(status)))

        StudioHandler._get(handler)

        payload, status = responses[-1]
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertFalse(payload["success"])

    def test_model_client_defaults_to_local_gateway_when_launcher_env_is_absent(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "WEB_ERP_AI_API_URL": "",
                "WEB_ERP_AI_API_KEY": "",
                "WEB_ERP_AI_MODEL": "",
            },
            clear=False,
        ):
            client = StudioApplication._load_model_client()
        self.assertIsNotNone(client)
        self.assertEqual(client.api_url, "http://127.0.0.1:8780/v1/chat/completions")
        self.assertEqual(client.api_key, "local-chatgpt-gateway")

    def test_public_result_routes_recursively_drop_private_fields(self) -> None:
        from creative_studio.app import create_application

        class Auth:
            cookie_secure = False

            def authenticate_session(self, *args):
                return SimpleNamespace(
                    user={"id": 1, "role": "admin", "must_change_password": False}
                )

        private_visual = {
            "title": "方案",
            "subtitle": "副标题",
            "creative_description": "描述",
            "core_subject": "主体",
            "layout": "布局",
            "visual_style": "风格",
            "content_extensions": ["扩展"],
            "reference_sources": [{"name": "来源", "note": "说明"}],
            "keywords": ["关键词"],
            "image_prompt": "private prompt",
            "conversation_id": "private conversation",
            "first_frame": {
                "index": 1,
                "content": "首帧",
                "image_generation_instruction": "private instruction",
            },
        }
        generation_result = SimpleNamespace(
            items=[private_visual],
            input_tokens=1,
            output_tokens=2,
            total_tokens=3,
            usage_source="estimated",
            latency_ms=4,
            conversation_id="private conversation",
            assistant_message_id="private message",
        )
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                model_client=FakeModelClient(),
                image_runner=FakeImageRunner(),
                environment={},
            )
            application.auth.init_admin("admin", "correct horse battery staple")
            application.auth = Auth()
            project = application.repository.create_project("项目", "展示类", 1)
            project = application.repository.update_project(
                project["id"], {"task_description": "展示说明"}
            )
            narrative_project = application.repository.create_project("叙事项目", "叙事类", 1)
            narrative_project = application.repository.update_project(
                narrative_project["id"], {"task_description": "叙事说明"}
            )
            reservation = application.repository.reserve_generation(
                project["id"], "visual", "visual.v1", "fingerprint"
            )
            item_id = application.repository.complete_visual_generation(
                reservation["id"], generation_result, "16:9"
            )[0]
            application.repository.fail_visual_item(item_id, 0, "token=secret D:/private")
            application.generation_service.continue_scheme = lambda scheme_id: {
                **private_visual,
                "scheme_id": scheme_id,
                "scheme_status": "completed",
                "frames": [
                    {
                        "scheme_id": scheme_id,
                        "frame_index": 1,
                        "actual_content": "首帧",
                        "image_status": "success",
                        "image_path": "D:/private/frame.webp",
                        "image_generation_instruction": "private frame prompt",
                    }
                ],
            }

            responses = [
                self._call_route(
                    application,
                    "_post",
                    "/api/projects",
                    {"name": "新项目", "script_type": "展示类", "private_context": "secret"},
                )[0],
                self._call_route(application, "_get", "/api/projects")[0],
                self._call_route(application, "_get", f"/api/projects/{project['id']}")[0],
                self._call_route(application, "_get", f"/api/projects/{project['id']}/history")[0],
                self._call_route(application, "_get", f"/api/visual-items/{item_id}/status")[0],
                self._call_route(application, "_get", f"/api/visual-items/{item_id}/frames/status")[0],
                self._call_route(application, "_post", f"/api/visual-items/{item_id}/select")[0],
                self._call_route(application, "_post", f"/api/visual-items/{item_id}/continue")[0],
                self._call_route(
                    application,
                    "_post",
                    f"/api/projects/{narrative_project['id']}/generate",
                )[0],
                self._call_route(
                    application,
                    "_post",
                    f"/api/projects/{project['id']}/files",
                    headers={"Content-Length": "4", "X-File-Name": "brief.txt"},
                    body=b"safe",
                )[0],
                self._call_route(
                    application,
                    "_post",
                    f"/api/projects/{project['id']}/adopt",
                    {"recommendation_kind": "visual", "item_id": item_id},
                )[0],
                self._call_route(
                    application,
                    "_put",
                    f"/api/projects/{project['id']}",
                    {"name": "已更新", "private_context": {"raw_response": "secret"}},
                )[0],
            ]

        for response in responses:
            self.assertEqual(self._private_fields_in(response), set(), response)

    def test_require_auth_blocks_password_reset_user_for_business_requests(self) -> None:
        class Auth:
            def authenticate_session(self, session, csrf=None):
                return type("Context", (), {"user": {"id": 7, "must_change_password": True}})()

        class Handler:
            def __init__(self):
                self.responses = []
            _session_cookie = lambda self: "session"
            _csrf_cookie = lambda self: "csrf"
            _json = DummyHandler._json

        handler = Handler()
        import creative_studio.app as app_module
        handler.application = type("Application", (), {"auth": Auth()})()
        with self.assertRaises(Exception):
            StudioHandler._require_auth(handler)
        self.assertEqual(handler.responses[0][1], HTTPStatus.FORBIDDEN)

    def test_generation_errors_map_to_expected_http_statuses(self) -> None:
        cases = [
            (GenerationInputError("输入不合法"), HTTPStatus.UNPROCESSABLE_ENTITY),
            (GenerationNotFoundError("项目不存在"), HTTPStatus.NOT_FOUND),
            (GenerationConflictError("状态冲突"), HTTPStatus.CONFLICT),
            (GenerationQueueTimeoutError("队列超时"), HTTPStatus.SERVICE_UNAVAILABLE),
            (AiCreativeQueueTimeoutError("AI排队超时"), HTTPStatus.SERVICE_UNAVAILABLE),
            (AiCreativeConfigurationError("配置错误"), HTTPStatus.INTERNAL_SERVER_ERROR),
            (AiCreativeRequestError("上游失败"), HTTPStatus.BAD_GATEWAY),
        ]
        for exc, expected_status in cases:
            handler = DummyHandler()
            StudioHandler._error(handler, exc)
            payload, status = handler.responses[0]
            self.assertEqual(status, expected_status)
            self.assertEqual(payload["success"], False)
            self.assertEqual(payload["error"], str(exc))
            self.assertTrue(payload["error_code"])
            self.assertTrue(payload["phase"])
            self.assertIsInstance(payload["retryable"], bool)
            self.assertRegex(payload["trace_id"], r"^[0-9a-f]{32}$")

    def test_generic_studio_data_error_still_maps_to_bad_request(self) -> None:
        handler = DummyHandler()
        StudioHandler._error(handler, StudioDataError("普通数据错误"))
        self.assertEqual(handler.responses, [({"success": False, "error": "普通数据错误"}, HTTPStatus.BAD_REQUEST)])


if __name__ == "__main__":
    unittest.main()
