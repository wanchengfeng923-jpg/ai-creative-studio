import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from creative_studio.app import create_application
from creative_studio.model_client import ModelResponse
from creative_studio.static_visual import StaticVisualImageRequest
from tests.test_static_visual import valid_payload


class _SequenceModelClient:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.requests = []

    def generate(self, request: object) -> ModelResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("fake model response exhausted")
        return self.responses.pop(0)


class _FakeStaticImageRunner:
    def __init__(self) -> None:
        self.requests: list[StaticVisualImageRequest] = []
        self.fallback_item_ids: list[list[int]] = []

    def enqueue_static(self, requests: list[StaticVisualImageRequest]) -> None:
        self.requests.extend(requests)

    def enqueue(self, item_ids: list[int]) -> None:
        self.fallback_item_ids.append(list(item_ids))


class StaticGenerationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.client = _SequenceModelClient([
            ModelResponse(
                content=json.dumps(valid_payload(), ensure_ascii=False),
                input_tokens=11,
                output_tokens=22,
                total_tokens=33,
                latency_ms=4,
                conversation_id="private-conversation",
                assistant_message_id="private-message",
            )
        ])
        self.image_runner = _FakeStaticImageRunner()
        self.application = create_application(
            database_path=root / "studio.db",
            images_dir=root / "images",
            uploads_dir=root / "uploads",
            model_client=self.client,
            image_runner=self.image_runner,
            environment={
                "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "fake-key",
                "WEB_ERP_AI_MODEL": "fake-model",
            },
        )
        self.project = self.application.repository.create_project("静态生产项目", "展示类")
        self.application.repository.update_project(
            self.project["id"],
            {
                "task_description": "生成一张独立静态展示广告",
                "creative_tags": {},
                "aspect_ratio": "16:9",
            },
        )

    def tearDown(self) -> None:
        self.application.image_runner.stop() if hasattr(self.application.image_runner, "stop") else None
        self.tempdir.cleanup()

    def test_production_root_routes_static_generation_to_canonical_module(self) -> None:
        response = self.application.generate(self.project["id"])

        self.assertTrue(response["success"])
        self.assertEqual(len(self.client.requests), 1)
        self.assertIn("VISUAL_STATIC_CREATIVE_PROMPT_VERSION", self.client.requests[0].messages[0]["content"])
        self.assertEqual(len(self.image_runner.requests), 3)
        self.assertEqual({request.aspect_ratio for request in self.image_runner.requests}, {"16:9"})
        self.assertEqual(
            [request.request_id for request in self.image_runner.requests],
            [f"creative-studio-{index}-attempt-1" for index in range(1, 4)],
        )
        self.assertTrue(all(request.prompt for request in self.image_runner.requests))
        encoded = json.dumps(response, ensure_ascii=False)
        self.assertIn("audience_tension", encoded)
        self.assertIn("static_frame", encoded)
        self.assertNotIn("image_generation_instruction", encoded)
        self.assertNotIn("private-conversation", encoded)
        self.assertNotIn("private-message", encoded)
        with closing(sqlite3.connect(self.application.repository.database_path)) as connection:
            metadata = connection.execute(
                "SELECT output_schema_version,prompt_version FROM generations ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(metadata, ("StaticVisualResult.v1", "static-v1"))

    def test_format_repair_is_bounded_and_carries_validation_path(self) -> None:
        invalid = valid_payload()
        invalid["items"][0]["subtitle"] = "legacy"
        self.client.responses = [
            ModelResponse(content=json.dumps(invalid, ensure_ascii=False)),
            ModelResponse(content=json.dumps(valid_payload(), ensure_ascii=False)),
        ]

        response = self.application.generate(self.project["id"])

        self.assertTrue(response["success"])
        self.assertEqual(len(self.client.requests), 2)
        self.assertIn("items[0]", self.client.requests[1].messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
