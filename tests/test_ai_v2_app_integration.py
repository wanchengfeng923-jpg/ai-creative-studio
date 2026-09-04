from __future__ import annotations

import io
import json
import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ImageSubmission
from creative_studio.app import StudioHandler, create_application


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
            generated, generated_status = self._call(application, "do_POST", f"/api/v2/projects/{project['id']}/generate", request, user=admin)
            scheme_id = generated["items"][0]["scheme_id"]
            history, history_status = self._call(application, "do_GET", f"/api/v2/projects/{project['id']}/history", {}, user=admin)
            forbidden, forbidden_status = self._call(application, "do_GET", f"/api/v2/projects/{project['id']}/history", {}, user=stranger)
            run, run_status = self._call(application, "do_GET", f"/api/v2/runs/{generated['run_id']}", {}, user=admin)
            forbidden_run, forbidden_run_status = self._call(application, "do_GET", f"/api/v2/runs/{generated['run_id']}", {}, user=stranger)
            image_state, image_status = self._call(application, "do_POST", f"/api/v2/schemes/{scheme_id}/image", {}, user=admin)
            image_response = self._image(application, image_state["image_url"], user=admin)

            carousel_request = {"task_description": "说明", "aspect_ratio": "16:9", "creative_tags": {"visual_carousel": ["是"], "visual_carousel_count": ["2"]}}
            carousel, carousel_status = self._call(application, "do_POST", f"/api/v2/projects/{project['id']}/generate", carousel_request, user=admin)
            carousel_scheme_id = carousel["items"][0]["scheme_id"]
            skipped, skipped_status = self._call(application, "do_POST", f"/api/v2/schemes/{carousel_scheme_id}/frames/2/image", {}, user=admin)
            first_frame, first_frame_status = self._call(application, "do_POST", f"/api/v2/schemes/{carousel_scheme_id}/frames/1/image", {}, user=admin)
            second_frame, second_frame_status = self._call(application, "do_POST", f"/api/v2/schemes/{carousel_scheme_id}/frames/2/image", {}, user=admin)
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
        self.assertEqual(carousel_status, HTTPStatus.OK)
        self.assertEqual(skipped_status, HTTPStatus.CONFLICT)
        self.assertEqual(skipped["error_code"], "frame_order_conflict")
        self.assertEqual(first_frame_status, HTTPStatus.OK)
        self.assertEqual(second_frame_status, HTTPStatus.OK)
        self.assertEqual(first_frame["status"], "success")
        self.assertEqual(second_frame["status"], "success")


if __name__ == "__main__":
    unittest.main()
