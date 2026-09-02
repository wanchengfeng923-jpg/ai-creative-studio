import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creative_studio.display_frame_models import DisplayScheme
from creative_studio.generation_service import CreativeGenerationService
from creative_studio.model_client import ModelResponse
from creative_studio.repository import StudioRepository


class FakeFollowUpModel:
    def __init__(self) -> None:
        self.requests = []
        self.responses = [
            {"frame_index": 2, "content": "第二张", "transition_from_previous": "承接一", "image_generation_instruction": "图二"},
            {"frame_index": 3, "content": "第三张", "transition_from_previous": "承接二", "ending_note": "收束", "image_generation_instruction": "图三"},
        ]

    def generate(self, request):
        self.requests.append(request)
        if not request.conversation_id:
            if not self.responses:
                return ModelResponse(
                    content=json.dumps(
                        {
                            "frame": {
                                "frame_index": 1,
                                "content": "第一张",
                                "transition_to_next": "承接首帧",
                                "image_generation_instruction": "图一",
                            }
                        },
                        ensure_ascii=False,
                    ),
                    conversation_id="created-conversation",
                    assistant_message_id="created-message",
                )
            return ModelResponse(
                content=json.dumps(
                    {
                        "frame": {
                            "frame_index": 1,
                            "content": "第一张",
                            "transition_to_next": "承接首帧",
                            "image_generation_instruction": "图一",
                        }
                    },
                    ensure_ascii=False,
                ),
                conversation_id="created-conversation",
                assistant_message_id="created-message",
            )
        payload = {"frame": self.responses.pop(0)}
        return ModelResponse(
            content=json.dumps(payload, ensure_ascii=False),
            conversation_id="conversation-1",
            assistant_message_id=f"message-{len(self.requests)}",
        )


class FakeFrameRunner:
    def __init__(self, repo: StudioRepository) -> None:
        self.repo = repo
        self.calls = []
        self.prompts = []

    def enqueue_frame(self, scheme_id, frame_index, prompt, aspect_ratio, previous_image_path, conversation_id="", parent_message_id=""):
        self.calls.append((scheme_id, frame_index, previous_image_path))
        self.prompts.append(prompt)
        self.repo.claim_display_frame(scheme_id, frame_index)
        self.repo.complete_display_frame(scheme_id, frame_index, 1, f"frame-{frame_index}-image")

    def enqueue(self, item_ids):
        for scheme_id in item_ids:
            frame = self.repo.claim_display_frame(scheme_id, 1)
            if frame is not None:
                self.repo.complete_display_frame(scheme_id, 1, int(frame["image_attempt"]), "frame-1-image")


class DisplayFrameContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = StudioRepository(Path(self.temp.name) / "studio.db")
        project = self.repo.create_project("展示项目", "展示类")
        project = self.repo.update_project(
            project["id"],
            {
                "task_type": "产品展示",
                "task_description": "突出新品卖点",
                "product_evidence_summary": "真实产品证据",
            },
        )
        reservation = self.repo.reserve_generation(
            project["id"],
            "visual",
            "visual.carousel.v2",
            "fp",
            context_json={
                "task_type": project["task_type"],
                "task_description": project["task_description"],
                "product_evidence_summary": project["product_evidence_summary"],
            },
        )
        scheme = DisplayScheme.from_payload(
            {
                "title": "方案",
                "creative_summary": "整体说明",
                "creative_sources": ["创意来源"],
                "core_subject": "核心主体",
                "layout": "画面布局",
                "visual_style": "视觉风格",
                "content_extensions": ["内容延展"],
                "reference_sources": [{"name": "参考", "note": "参考说明"}],
                "keywords": ["关键词"],
                "frame_count": 3,
                "frame_plan": [{"index": i, "description": f"计划{i}"} for i in range(1, 4)],
            }
        )
        self.scheme_id = self.repo.save_display_schemes(reservation["id"], [scheme])[0]
        self.repo.claim_display_frame(self.scheme_id, 1)
        self.repo.complete_display_frame(self.scheme_id, 1, 1, "frame-1-image")
        self.model = FakeFollowUpModel()
        self.runner = FakeFrameRunner(self.repo)
        self.service = CreativeGenerationService(self.repo, model_client=self.model, image_runner=self.runner)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_continue_is_serial_image_only_and_passes_previous_actual_image(self) -> None:
        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "test-key",
                "WEB_ERP_AI_MODEL": "test-model",
            },
            clear=False,
        ):
            self.service.select_scheme(self.scheme_id)
            result = self.service.continue_scheme(self.scheme_id)
        # Continuation is an image-only flow; it must not create a follow-up
        # text-model conversation just to produce a prompt.
        self.assertEqual(self.model.requests, [])
        image_prompt = self.runner.prompts[0]
        self.assertIn("核心主体", image_prompt)
        self.assertIn("画面布局", image_prompt)
        self.assertIn("视觉风格", image_prompt)
        self.assertIn("创意来源", image_prompt)
        self.assertIn("真实产品证据", image_prompt)
        self.assertIn("突出新品卖点", image_prompt)
        self.assertIn("直接生成一张图片", image_prompt)
        self.assertNotIn("只输出一个合法 JSON", image_prompt)
        self.assertNotIn("image_path", image_prompt)
        self.assertEqual([call[1] for call in self.runner.calls], [2, 3])
        self.assertEqual(self.runner.calls[1][2], "frame-2-image")
        self.assertEqual(self.repo.get_display_scheme(self.scheme_id)["scheme_status"], "completed")
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("image_generation_instruction", encoded)
        self.assertNotIn("image_path", encoded)


if __name__ == "__main__":
    unittest.main()
