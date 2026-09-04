from __future__ import annotations

import io
import json
import sqlite3
import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ImageSubmission
from creative_studio.app import STATIC_DIR, StudioHandler, create_application


def _static_text() -> str:
    return json.dumps({
        "schema_version": "static-text-v1",
        "items": [
            {
                "title": f"方案 {index}",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "image_description": "画面描述",
                "execution": {"image_prompt": "private prompt"},
            }
            for index in range(1, 4)
        ],
    })


def _carousel_text() -> str:
    return json.dumps({
        "schema_version": "carousel-text-v1",
        "items": [
            {
                "title": f"轮播方案 {item}",
                "core_idea": "核心创意",
                "ad_copy": "广告文案",
                "frames": [
                    {"index": 1, "description": "首帧"},
                    {"index": 2, "description": "第二帧"},
                ],
                "execution": {
                    "continuity_rules": ["保持连续"],
                    "image_prompts": [
                        {"index": 1, "prompt": "private first prompt"},
                        {"index": 2, "prompt": "private second prompt"},
                    ],
                },
            }
            for item in range(1, 4)
        ],
    })


class AiV2AppIntegrationTests(unittest.TestCase):
    @staticmethod
    def _legacy_counts(application) -> dict[str, int]:
        connection = sqlite3.connect(application.repository.database_path)
        try:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("generations", "visual_items", "adoptions")
            }
        finally:
            connection.close()

    def _call(self, application, method: str, path: str, payload: dict[str, object], *, user: dict[str, object] | None):
        handler = object.__new__(StudioHandler)
        handler.server = SimpleNamespace(application=application)
        handler.path = path
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.client_address = ("127.0.0.1", 1)
        responses: list[tuple[dict[str, object], HTTPStatus]] = []
        handler._json = lambda value, status=HTTPStatus.OK: responses.append((value, HTTPStatus(status)))
        handler._read_json = lambda: payload
        if user is not None:
            context = SimpleNamespace(user=user)
            handler._require_auth = lambda **kwargs: context
            handler._require_v2_auth = lambda **kwargs: context
            handler._context = lambda: context
        getattr(StudioHandler, method)(handler)
        return responses[-1]

    def _image(self, application, path: str, *, user: dict[str, object]):
        handler = object.__new__(StudioHandler)
        handler.server = SimpleNamespace(application=application)
        handler.path = path
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.client_address = ("127.0.0.1", 1)
        context = SimpleNamespace(user=user)
        handler._require_auth = lambda **kwargs: context
        handler._require_v2_auth = lambda **kwargs: context
        handler._context = lambda: context
        response: dict[str, object] = {"headers": {}}
        handler.send_response = lambda status: response.update(status=HTTPStatus(status))
        handler.send_header = lambda name, value: response["headers"].__setitem__(name, value)
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()
        StudioHandler.do_GET(handler)
        response["body"] = handler.wfile.getvalue()
        return response

    def _real_post(self, application, path: str, payload: dict[str, object], headers: dict[str, str]):
        handler = object.__new__(StudioHandler)
        handler.server = SimpleNamespace(application=application)
        handler.path = path
        handler.headers = headers
        handler.rfile = io.BytesIO()
        handler.client_address = ("127.0.0.1", 1)
        responses: list[tuple[dict[str, object], HTTPStatus]] = []
        handler._json = lambda value, status=HTTPStatus.OK: responses.append((value, HTTPStatus(status)))
        handler._read_json = lambda: payload
        StudioHandler.do_POST(handler)
        return responses[-1]

    def test_v2_static_page_does_not_fall_back_to_legacy_index(self) -> None:
        handler = object.__new__(StudioHandler)
        served: list[Path] = []
        handler._file = lambda path, cache: served.append(path)
        handler.send_error = lambda status: self.fail(f"unexpected static error: {status}")

        StudioHandler._static(handler, "/ai-v2/")

        self.assertEqual(served, [STATIC_DIR / "ai-v2" / "index.html"])
        js = (STATIC_DIR / "ai-v2" / "app.js").read_text(encoding="utf-8")
        self.assertIn("X-CSRF-Token", js)

    def test_v2_writes_require_real_matching_csrf_header(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                ai_v2_text_model=DeterministicTextModel([_static_text()]),
                ai_v2_image_model=DeterministicImageModel(),
                environment={},
            )
            application.auth.init_admin("admin", "correct horse battery staple")
            project = application.repository.create_project("v2", "展示类", 1)
            login = application.auth.login("admin", "correct horse battery staple")
            cookie_handler = object.__new__(StudioHandler)
            cookie_handler.server = SimpleNamespace(application=application)
            StudioHandler._set_auth_cookies(cookie_handler, login.session_token, login.csrf_token)
            cookie = f"studio_session={login.session_token}; studio_csrf={login.csrf_token}"
            body = {"task_description": "说明", "aspect_ratio": "16:9", "creative_tags": {}}
            missing, missing_status = self._real_post(
                application, f"/api/v2/projects/{project['id']}/generate", body, {"Cookie": cookie}
            )
            forged, forged_status = self._real_post(
                application,
                f"/api/v2/projects/{project['id']}/generate",
                body,
                {"Cookie": cookie, "X-CSRF-Token": "forged"},
            )
            accepted, accepted_status = self._real_post(
                application,
                f"/api/v2/projects/{project['id']}/generate",
                body,
                {"Cookie": cookie, "X-CSRF-Token": login.csrf_token},
            )
            application.ai_v2_application.store.close()

        self.assertEqual(missing_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(missing["error_code"], "csrf_invalid")
        self.assertEqual(forged_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(forged["error_code"], "csrf_invalid")
        self.assertEqual(accepted_status, HTTPStatus.OK)
        self.assertEqual(accepted["use_case"], "static")
        self.assertIn("studio_csrf=", cookie_handler._pending_cookies[1])
        self.assertIn("SameSite=Strict", cookie_handler._pending_cookies[1])

    def test_v2_generate_requires_existing_auth_and_uses_owned_project(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = DeterministicImageModel()
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                ai_v2_text_model=DeterministicTextModel([_static_text()]),
                ai_v2_image_model=image,
                environment={},
            )
            application.auth.init_admin("admin", "correct horse battery staple")
            project = application.repository.create_project("v2", "展示类", 1)
            request = {"task_description": "说明", "aspect_ratio": "16:9", "creative_tags": {}}

            anonymous, anonymous_status = self._call(
                application, "do_POST", f"/api/v2/projects/{project['id']}/generate", request, user=None
            )
            response, status = self._call(
                application,
                "do_POST",
                f"/api/v2/projects/{project['id']}/generate",
                request,
                user={"id": 1, "role": "admin", "must_change_password": False},
            )
            application.ai_v2_application.store.close()

        self.assertEqual(anonymous_status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(anonymous["error_code"], "unauthorized")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(response["use_case"], "static")
        self.assertEqual(len(response["items"]), 3)
        self.assertEqual(len(image.start_calls), 0)

    def test_v2_resource_routes_enforce_project_ownership_and_preserve_image_mime(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cursor = ImageSessionCursor("fake", "conversation", "message", 1)
            artifact = image_artifact(b"png-bytes", "image/png")
            image = DeterministicImageModel(
                start_submissions={
                    "v2-run-1-scheme-1:frame:1": ImageSubmission("success", None, cursor, artifact, None),
                    "v2-run-2-scheme-1:frame:1": ImageSubmission("success", None, cursor, artifact, None),
                },
                continue_submissions={
                    "v2-run-2-scheme-1:frame:2": ImageSubmission("success", None, cursor, artifact, None),
                },
            )
            application = create_application(
                database_path=root / "studio.db",
                images_dir=root / "images",
                uploads_dir=root / "uploads",
                ai_v2_text_model=DeterministicTextModel([_static_text(), _carousel_text()]),
                ai_v2_image_model=image,
                environment={},
            )
            application.auth.init_admin("admin", "correct horse battery staple")
            project = application.repository.create_project("v2", "展示类", 1)
            admin = {"id": 1, "role": "admin", "must_change_password": False}
            stranger = {"id": 2, "role": "user", "must_change_password": False}
            request = {"task_description": "说明", "aspect_ratio": "16:9", "creative_tags": {}}
            legacy_before = self._legacy_counts(application)
            generated, generated_status = self._call(application, "do_POST", f"/api/v2/projects/{project['id']}/generate", request, user=admin)
            scheme_id = generated["items"][0]["scheme_id"]
            history, history_status = self._call(application, "do_GET", f"/api/v2/projects/{project['id']}/history", {}, user=admin)
            forbidden, forbidden_status = self._call(application, "do_GET", f"/api/v2/projects/{project['id']}/history", {}, user=stranger)
            run, run_status = self._call(application, "do_GET", f"/api/v2/runs/{generated['run_id']}", {}, user=admin)
            forbidden_run, forbidden_run_status = self._call(application, "do_GET", f"/api/v2/runs/{generated['run_id']}", {}, user=stranger)
            image_state, image_status = self._call(application, "do_POST", f"/api/v2/schemes/{scheme_id}/image", {}, user=admin)
            image_response = self._image(application, image_state["image_url"], user=admin)
            foreign_scheme, foreign_scheme_status = self._call(application, "do_POST", f"/api/v2/schemes/{scheme_id}/image", {}, user=stranger)
            foreign_attempt, foreign_attempt_status = self._call(application, "do_GET", f"/api/v2/image-attempts/{image_state['attempt_id']}", {}, user=stranger)
            foreign_image, foreign_image_status = self._call(application, "do_GET", image_state["image_url"], {}, user=stranger)

            carousel_request = {"task_description": "说明", "aspect_ratio": "16:9", "creative_tags": {"visual_carousel": ["是"], "visual_carousel_count": ["2"]}}
            carousel, carousel_status = self._call(application, "do_POST", f"/api/v2/projects/{project['id']}/generate", carousel_request, user=admin)
            carousel_scheme_id = carousel["items"][0]["scheme_id"]
            skipped, skipped_status = self._call(application, "do_POST", f"/api/v2/schemes/{carousel_scheme_id}/frames/2/image", {}, user=admin)
            first_frame, first_frame_status = self._call(application, "do_POST", f"/api/v2/schemes/{carousel_scheme_id}/frames/1/image", {}, user=admin)
            second_frame, second_frame_status = self._call(application, "do_POST", f"/api/v2/schemes/{carousel_scheme_id}/frames/2/image", {}, user=admin)
            legacy_after = self._legacy_counts(application)
            application.ai_v2_application.store.close()

        self.assertEqual(generated_status, HTTPStatus.OK)
        self.assertEqual(history_status, HTTPStatus.OK)
        self.assertEqual(history["runs"][0]["run_id"], generated["run_id"])
        self.assertEqual(forbidden_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(forbidden["error_code"], "forbidden")
        self.assertEqual(run_status, HTTPStatus.OK)
        self.assertEqual(run["run_id"], generated["run_id"])
        self.assertEqual(forbidden_run_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(forbidden_run["error_code"], "forbidden")
        self.assertEqual(image_status, HTTPStatus.OK)
        self.assertEqual(image_response["status"], HTTPStatus.OK)
        self.assertEqual(image_response["headers"]["Content-Type"], "image/png")
        self.assertEqual(image_response["body"], b"png-bytes")
        self.assertEqual(foreign_scheme_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(foreign_scheme["error_code"], "forbidden")
        self.assertEqual(foreign_attempt_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(foreign_attempt["error_code"], "forbidden")
        self.assertEqual(foreign_image_status, HTTPStatus.FORBIDDEN)
        self.assertEqual(foreign_image["error_code"], "forbidden")
        self.assertEqual(carousel_status, HTTPStatus.OK)
        self.assertEqual(skipped_status, HTTPStatus.CONFLICT)
        self.assertEqual(skipped["error_code"], "frame_order_conflict")
        self.assertEqual(first_frame_status, HTTPStatus.OK)
        self.assertEqual(second_frame_status, HTTPStatus.OK)
        self.assertEqual(first_frame["status"], "success")
        self.assertEqual(second_frame["status"], "success")
        self.assertEqual(legacy_after, legacy_before)


if __name__ == "__main__":
    unittest.main()
