from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.application import AiV2Application
from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel
from creative_studio.ai_v2.http_api import AiV2HttpApi
from creative_studio.ai_v2.store import SqliteAiV2Store


def _static_result() -> str:
    return json.dumps({
        "schema_version": "static-text-v1",
        "items": [
            {"title": str(i), "core_idea": "c", "ad_copy": "a", "image_description": "d", "execution": {"image_prompt": "p"}}
            for i in range(3)
        ],
    })


def _narrative_result() -> str:
    return json.dumps({
        "schema_version": "narrative-text-v1",
        "items": [
            {
                "story": f"故事 {i}",
                "hooks": [
                    {"text": "钩子一", "scenes": ["场景一", "场景二", "场景三"]},
                    {"text": "钩子二", "scenes": ["场景四", "场景五", "场景六"]},
                ],
            }
            for i in range(5)
        ],
    })


class AiV2ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteAiV2Store(Path(self.temp_dir.name) / "db.sqlite")
        self.application = AiV2Application(
            self.store,
            text_model=DeterministicTextModel([_static_result()]),
            image_model=DeterministicImageModel(),
            project_provider=lambda project_id: {"id": project_id, "script_type": "展示类"},
        )
        self.api = AiV2HttpApi(self.application)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_generate_requires_auth_and_accepts_only_three_fields(self) -> None:
        status, payload = self.api.dispatch("POST", "/api/v2/projects/1/generate", {}, authenticated=False)
        self.assertEqual(status, 401)
        self.assertEqual(payload["error_code"], "unauthorized")
        status, payload = self.api.dispatch("POST", "/api/v2/projects/1/generate", {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}, "legacy": True})
        self.assertEqual(status, 422)
        self.assertEqual(payload["error_code"], "unknown_field")

    def test_generate_and_history_return_public_v2_dto_only(self) -> None:
        body = {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}}
        status, payload = self.api.dispatch("POST", "/api/v2/projects/1/generate", body)
        self.assertEqual(status, 200)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("execution", encoded)
        self.assertNotIn("conversation", encoded)
        self.assertNotIn("prompt", encoded)
        status, history = self.api.dispatch("GET", "/api/v2/projects/1/history", None)
        self.assertEqual(status, 200)
        self.assertEqual(len(history["runs"]), 1)
        status, current = self.api.dispatch("GET", f"/api/v2/runs/{payload['run_id']}", None)
        self.assertEqual(status, 200)
        self.assertEqual(current["run_id"], payload["run_id"])

    def test_history_reopen_keeps_scheme_and_image_state(self) -> None:
        body = {"task_description": "x", "aspect_ratio": "9:16", "creative_tags": {}}
        _, generated = self.api.dispatch("POST", "/api/v2/projects/1/generate", body)
        scheme_id = generated["items"][0]["scheme_id"]
        self.api.dispatch("POST", f"/api/v2/schemes/{scheme_id}/image", {})
        _, history = self.api.dispatch("GET", "/api/v2/projects/1/history", None)
        reopened = history["runs"][0]
        self.assertEqual(reopened["items"][0]["scheme_id"], scheme_id)
        self.assertIn(reopened["items"][0]["image_state"]["status"], {"success", "pending", "generating", "failed"})
        self.assertEqual(reopened["aspect_ratio"], "9:16")

    def test_static_image_is_accepted_once_and_repeated_request_is_idempotent(self) -> None:
        body = {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}}
        _, generated = self.api.dispatch("POST", "/api/v2/projects/1/generate", body)
        scheme_id = generated["items"][0]["scheme_id"]
        status, first = self.api.dispatch("POST", f"/api/v2/schemes/{scheme_id}/image", {})
        status2, second = self.api.dispatch("POST", f"/api/v2/schemes/{scheme_id}/image", {})
        self.assertIn(status, {200, 202})
        self.assertEqual(status2, status)
        self.assertEqual(first["attempt_id"], second["attempt_id"])

    def test_narrative_history_does_not_assume_image_frames(self) -> None:
        application = AiV2Application(
            self.store,
            text_model=DeterministicTextModel([_narrative_result()]),
            image_model=DeterministicImageModel(),
            project_provider=lambda project_id: {"id": project_id, "script_type": "叙事类"},
        )
        api = AiV2HttpApi(application)
        body = {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}}
        status, generated = api.dispatch("POST", "/api/v2/projects/1/generate", body)
        self.assertEqual(status, 200)
        status, history = api.dispatch("GET", "/api/v2/projects/1/history", None)
        self.assertEqual(status, 200)
        self.assertEqual(len(history["runs"][0]["items"]), 5)
        status, current = api.dispatch("GET", f"/api/v2/runs/{generated['run_id']}", None)
        self.assertEqual(status, 200)
        self.assertEqual(len(current["items"]), 5)

    def test_repeated_generation_automatically_uses_second_batch(self) -> None:
        application = AiV2Application(
            self.store,
            text_model=DeterministicTextModel([_static_result(), _static_result()]),
            image_model=DeterministicImageModel(),
            project_provider=lambda project_id: {"id": project_id, "script_type": "展示类"},
        )
        api = AiV2HttpApi(application)
        body = {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}}
        first_status, first = api.dispatch("POST", "/api/v2/projects/1/generate", body)
        second_status, second = api.dispatch("POST", "/api/v2/projects/1/generate", body)
        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["batch_index"], 1)
        self.assertEqual(second["batch_index"], 2)


if __name__ == "__main__":
    unittest.main()
