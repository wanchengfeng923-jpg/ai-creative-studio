from __future__ import annotations

from dataclasses import is_dataclass
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from creative_studio.generation_models import (
    CreativeGenerationRequest,
    CreativeInputSnapshot,
    GenerationContext,
    GenerationOutcome,
)
from creative_studio.generation_service import CreativeGenerationService
from creative_studio.repository import StudioRepository


class FakeGenerationAdapter:
    def __init__(self, results_by_kind: dict[str, object]) -> None:
        self.results_by_kind = results_by_kind
        self.calls: list[CreativeInputSnapshot] = []

    def generate(self, snapshot: CreativeInputSnapshot, context: GenerationContext) -> object:
        self.calls.append(snapshot)
        return self.results_by_kind[snapshot.kind]


class FakeImageRunner:
    def __init__(self) -> None:
        self.enqueued: list[list[int]] = []

    def enqueue(self, item_ids: list[int]) -> None:
        self.enqueued.append(list(item_ids))


class GenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.repo = StudioRepository(Path(self.tempdir.name) / "studio.db")
        self.narrative_project = self.repo.create_project("叙事项目", "叙事类")
        self.visual_project = self.repo.create_project("展示项目", "展示类")
        self.repo.update_project(self.narrative_project["id"], {"task_description": "叙事说明"})
        narrative_result = SimpleNamespace(
            items=[
                {
                    "story": "故事1",
                    "hooks": [{"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]}, {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]}],
                },
                {
                    "story": "故事2",
                    "hooks": [{"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]}, {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]}],
                },
                {
                    "story": "故事3",
                    "hooks": [{"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]}, {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]}],
                },
                {
                    "story": "故事4",
                    "hooks": [{"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]}, {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]}],
                },
                {
                    "story": "故事5",
                    "hooks": [{"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]}, {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]}],
                },
            ],
            input_tokens=1,
            output_tokens=2,
            total_tokens=3,
            usage_source="exact",
            latency_ms=4,
            conversation_id="conversation",
            assistant_message_id="message",
        )
        visual_result = SimpleNamespace(
            items=[
                {
                    "title": "视觉1",
                    "subtitle": "副标题1",
                    "creative_description": "描述1",
                    "core_subject": "主体1",
                    "layout": "布局1",
                    "visual_style": "风格1",
                    "content_extensions": ["扩展1"],
                    "reference_sources": [{"name": "来源1", "note": "借用1"}],
                    "keywords": ["关键词1"],
                    "image_prompt": "提示词1",
                },
                {
                    "title": "视觉2",
                    "subtitle": "副标题2",
                    "creative_description": "描述2",
                    "core_subject": "主体2",
                    "layout": "布局2",
                    "visual_style": "风格2",
                    "content_extensions": ["扩展2"],
                    "reference_sources": [{"name": "来源2", "note": "借用2"}],
                    "keywords": ["关键词2"],
                    "image_prompt": "提示词2",
                },
                {
                    "title": "视觉3",
                    "subtitle": "副标题3",
                    "creative_description": "描述3",
                    "core_subject": "主体3",
                    "layout": "布局3",
                    "visual_style": "风格3",
                    "content_extensions": ["扩展3"],
                    "reference_sources": [{"name": "来源3", "note": "借用3"}],
                    "keywords": ["关键词3"],
                    "image_prompt": "提示词3",
                },
            ],
            input_tokens=5,
            output_tokens=6,
            total_tokens=7,
            usage_source="exact",
            latency_ms=8,
            conversation_id="conversation",
            assistant_message_id="message",
        )
        self.service = CreativeGenerationService(
            repository=self.repo,
            adapter=FakeGenerationAdapter({"narrative": narrative_result, "visual": visual_result}),
            image_runner=FakeImageRunner(),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_generation_models_are_frozen_dataclasses(self) -> None:
        for model in (
            CreativeGenerationRequest,
            CreativeInputSnapshot,
            GenerationContext,
            GenerationOutcome,
        ):
            self.assertTrue(is_dataclass(model))
            self.assertTrue(model.__dataclass_params__.frozen)

    def test_generate_narrative_calls_model_once_and_creates_no_image_jobs(self) -> None:
        result = self.service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))
        self.assertEqual(len(self.service.adapter.calls), 1)
        self.assertEqual(self.service.image_runner.enqueued, [])
        self.assertEqual(result.snapshot.kind, "narrative")

    def test_generate_visual_accepts_blank_carousel_hints_and_queues_three_images(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {
                "task_description": "展示说明",
                "creative_tags": {
                    "visual_carousel": [""],
                    "visual_carousel_count": [""],
                    "visual_carousel_form": [""],
                },
            },
        )
        result = self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))
        self.assertEqual(len(self.service.adapter.calls), 1)
        self.assertEqual(result.snapshot.schema_version, "visual.v1")
        self.assertEqual(self.service.image_runner.enqueued, [[1, 2, 3]])

    def test_generate_visual_calls_model_once(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {"task_description": "展示说明"},
        )
        self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))
        self.assertEqual(len(self.service.adapter.calls), 1)

    def test_generate_failure_calls_fail_generation(self) -> None:
        class FailingAdapter:
            def __init__(self) -> None:
                self.calls = 0

            def generate(self, snapshot: CreativeInputSnapshot, context: GenerationContext) -> object:
                self.calls += 1
                raise RuntimeError("boom")

        service = CreativeGenerationService(
            repository=self.repo,
            adapter=FailingAdapter(),
            image_runner=FakeImageRunner(),
        )
        self.repo.update_project(self.visual_project["id"], {"task_description": "展示说明"})
        with self.assertRaisesRegex(RuntimeError, "boom"):
            service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))
        self.assertEqual(service.adapter.calls, 1)
        with closing(self.repo._connect()) as connection:
            row = connection.execute(
                "SELECT status, error FROM generations ORDER BY id DESC LIMIT 1",
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error"], "boom")


if __name__ == "__main__":
    unittest.main()
