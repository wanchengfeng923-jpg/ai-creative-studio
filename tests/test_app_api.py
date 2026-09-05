from __future__ import annotations

import unittest
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

from creative_studio.app import StudioApplication, StudioHandler
from creative_studio.project_projection import ProjectProjection
from creative_studio.repository import StudioDataError


class DummyHandler:
    def __init__(self) -> None:
        self.responses: list[tuple[dict[str, object], HTTPStatus]] = []

    def _json(self, payload, status=HTTPStatus.OK):
        self.responses.append((payload, HTTPStatus(status)))


class AppApiTests(unittest.TestCase):
    def test_project_list_and_detail_use_public_project_projection(self) -> None:
        project = {
            "id": 7,
            "owner_user_id": 1,
            "name": "投影测试",
            "script_type": "展示类",
            "creative_tags": {
                "visual_carousel": ["否"],
                "private_tag": ["secret"],
            },
            "reference_files": [
                {
                    "id": 3,
                    "original_name": "../brief.txt",
                    "stored_name": "internal.bin",
                },
            ],
            "private": "secret",
        }

        class Repository:
            def list_projects(self, keyword: str):
                self.keyword = keyword
                return [project]

            def get_project(self, project_id: int):
                return project if project_id == 7 else None

        repository = Repository()
        application = StudioApplication(
            repository,
            SimpleNamespace(),
            project_projection=ProjectProjection(),
            uploads_dir=Path("."),
        )
        context = SimpleNamespace(
            user={"id": 1, "role": "admin", "must_change_password": False},
        )

        def call(path: str) -> tuple[dict[str, object], HTTPStatus]:
            handler = object.__new__(StudioHandler)
            handler.server = SimpleNamespace(application=application)
            handler.path = path
            responses: list[tuple[dict[str, object], HTTPStatus]] = []
            handler._json = lambda value, status=HTTPStatus.OK: responses.append(
                (value, HTTPStatus(status))
            )
            handler._require_auth = lambda: context
            handler._context = lambda: context
            StudioHandler.do_GET(handler)
            return responses[-1]

        listed, list_status = call("/api/projects?search=projection")
        detailed, detail_status = call("/api/projects/7")

        self.assertEqual(list_status, HTTPStatus.OK)
        self.assertEqual(repository.keyword, "projection")
        self.assertNotIn("private", listed["projects"][0])
        self.assertEqual(detail_status, HTTPStatus.OK)
        self.assertNotIn("private", detailed["project"])
        self.assertNotIn("private_tag", detailed["project"]["creative_tags"])
        self.assertEqual(detailed["project"]["reference_files"][0]["original_name"], "brief.txt")
        self.assertNotIn("stored_name", detailed["project"]["reference_files"][0])

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
        handler.application = type("Application", (), {"auth": Auth()})()
        with self.assertRaises(Exception):
            StudioHandler._require_auth(handler)
        self.assertEqual(handler.responses[0][1], HTTPStatus.FORBIDDEN)

    def test_generic_studio_data_error_still_maps_to_bad_request(self) -> None:
        handler = DummyHandler()
        StudioHandler._error(handler, StudioDataError("普通数据错误"))
        self.assertEqual(handler.responses, [({"success": False, "error": "普通数据错误"}, HTTPStatus.BAD_REQUEST)])


if __name__ == "__main__":
    unittest.main()
