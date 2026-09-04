from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.generation_models import CreativeGenerationRequest
from creative_studio.generation_service import CreativeGenerationService
from creative_studio.model_client import ModelResponse
from creative_studio.prompt_registry import PromptRegistry
from creative_studio.public_projection import PublicResultMapper
from creative_studio.reference_assets import FileReferenceAssetStore
from creative_studio.repository import StudioRepository


ROOT = Path(__file__).resolve().parents[1]


class RecordingModelClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[object] = []

    def generate(self, request: object) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(content=json.dumps(self.payload, ensure_ascii=False))


def _narrative_payload() -> dict[str, object]:
    items = []
    for index in range(5):
        items.append(
            {
                "concept_id": chr(65 + index),
                "story": f"故事{index}",
                "audience_tension": "新手不知道从何开始",
                "product_value": "明确展示已确认玩法",
                "hooks": [
                    {"text": f"钩子{index}A", "scenes": ["场景一", "场景二", "场景三"]},
                    {"text": f"钩子{index}B", "scenes": ["场景四", "场景五", "场景六"]},
                ],
                "evidence": {"confirmed": ["已确认玩法"], "inferred": [], "to_confirm": []},
                "risks": ["需要确认素材"],
            }
        )
    return {"items": items}


class ReferencePromptIntegrationTests(unittest.TestCase):
    def test_generation_prompt_uses_bounded_reference_context_without_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = StudioRepository(root / "studio.db")
            project = repo.create_project("叙事项目", "叙事类")
            repo.update_project(project["id"], {"task_description": "说明已确认玩法"})
            uploads = root / "uploads" / str(project["id"])
            uploads.mkdir(parents=True)
            body = "PRIVATE_BINARY_MARKER".encode("utf-8")
            stored = uploads / "asset.txt"
            stored.write_bytes(body)
            repo.add_project_file(
                project["id"],
                "C:\\private\\brief.txt",
                "asset.txt",
                len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                mime_type="text/plain",
                extraction_status="complete",
                safe_summary=(
                    "产品证据；C:\\private\\source.pdf；https://private.invalid/secret；"
                    "image_prompt=DO_NOT_LEAK；受控结论"
                ),
            )
            client = RecordingModelClient(_narrative_payload())
            service = CreativeGenerationService(
                repository=repo,
                model_client=client,
                reference_asset_port=FileReferenceAssetStore(repo, root / "uploads"),
                prompt_registry=PromptRegistry.load(ROOT / "config" / "prompts" / "registry.json"),
                environment={
                    "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                    "WEB_ERP_AI_API_KEY": "fake-test-key",
                    "WEB_ERP_AI_MODEL": "fake-test-model",
                    "WEB_ERP_AI_PROMPT_TEMPLATE": "{{task_type}} {{task_description}} {{creative_tags}}",
                },
            )

            service.generate(CreativeGenerationRequest(project_id=project["id"]))

            prompt = client.requests[0].messages[0]["content"]
            self.assertIn("brief.txt", prompt)
            self.assertIn("产品证据", prompt)
            self.assertIn("受控结论", prompt)
            self.assertNotIn("C:\\private\\", prompt)
            self.assertNotIn("https://private.invalid", prompt)
            self.assertNotIn("PRIVATE_BINARY_MARKER", prompt)
            self.assertNotIn("image_prompt=DO_NOT_LEAK", prompt)

            public = PublicResultMapper().project(repo.get_project(project["id"]))
            self.assertNotIn("safe_summary", json.dumps(public, ensure_ascii=False))
            self.assertNotIn("stored_name", json.dumps(public, ensure_ascii=False))
            self.assertEqual(public["reference_files"][0]["original_name"], "brief.txt")
            self.assertNotIn("C:\\private\\", json.dumps(public, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
