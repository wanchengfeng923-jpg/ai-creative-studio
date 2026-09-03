from __future__ import annotations

import copy
import os
import json
from dataclasses import is_dataclass
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import requests

from creative_studio.generation_models import (
    CreativeGenerationRequest,
    CreativeInputSnapshot,
    GenerationConflictError,
    GenerationInputError,
    GenerationNotFoundError,
    GenerationQueueTimeoutError,
    GenerationContext,
    GenerationOutcome,
)
from creative_studio.ai_creative import (
    AiCreativeConfig,
    AiCreativeRequestError,
    AiCreativeQueueTimeoutError,
    generate_creative_recommendations,
    generate_visual_creative_recommendations,
    load_ai_creative_config,
    load_ai_creative_game_info,
    validate_creative_recommendations,
    validate_visual_creative_recommendations,
)
from creative_studio.generation_service import (
    CreativeGenerationService,
    LegacyCreativeGenerationAdapter,
)
from creative_studio.model_client import HttpModelClient, ModelResponse
from creative_studio.prompt_registry import PromptRegistry
from creative_studio.repository import StudioRepository
from creative_studio.app import StudioApplication


NARRATIVE_PROMPT_TEMPLATE = "{{task_type}}\n{{task_description}}\n{{creative_tags}}"
PROMPT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "prompts" / "registry.json"


def valid_narrative_payload() -> dict[str, object]:
    story = {
        "story": "故事",
        "hooks": [
            {"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]},
            {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]},
        ],
    }
    return {"items": [copy.deepcopy(story) for _ in range(5)]}


class LegacyResponse:
    def __init__(self, payload: object = None, *, json_error: Exception | None = None) -> None:
        self.payload = payload
        self.json_error = json_error

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        if self.json_error is not None:
            raise self.json_error
        return copy.deepcopy(self.payload)


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
        self.waited_for: list[list[int]] = []

    def enqueue(self, item_ids: list[int]) -> None:
        self.enqueued.append(list(item_ids))

    def wait_for_items(self, item_ids: list[int]) -> list[dict[str, object]]:
        self.waited_for.append(list(item_ids))
        return []


class FakeModelClient:
    def __init__(self, response: ModelResponse) -> None:
        self.response = response
        self.requests: list[object] = []

    def generate(self, request: object) -> ModelResponse:
        self.requests.append(request)
        return self.response


class SequenceModelClient:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []

    def generate(self, request: object) -> ModelResponse:
        self.requests.append(request)
        return self.responses.pop(0)


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

    def test_legacy_adapter_has_explicit_removal_metadata(self) -> None:
        self.assertEqual(LegacyCreativeGenerationAdapter.deprecated_since, "phase-0")
        self.assertEqual(
            LegacyCreativeGenerationAdapter.replacement,
            "CreativeGenerationService with ModelClient",
        )
        self.assertTrue(LegacyCreativeGenerationAdapter.new_callers_forbidden)
        self.assertIn("zero production callers", LegacyCreativeGenerationAdapter.removal_condition)

    def test_legacy_static_adapter_keeps_legacy_persistence_with_registry_loaded(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {"task_description": "兼容旧展示生成"},
        )
        image_runner = FakeImageRunner()
        service = CreativeGenerationService(
            repository=self.repo,
            adapter=self.service.adapter,
            model_client=None,
            image_runner=image_runner,
            prompt_registry=PromptRegistry.load(PROMPT_REGISTRY_PATH),
        )

        result = service.generate(
            CreativeGenerationRequest(project_id=self.visual_project["id"]),
        )

        self.assertEqual(result.snapshot.kind, "visual")
        self.assertEqual(len(image_runner.enqueued), 1)
        self.assertIn("subtitle", result.history["batches"][0]["items"][0])

    def test_generate_narrative_calls_model_once_and_creates_no_image_jobs(self) -> None:
        result = self.service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))
        self.assertEqual(len(self.service.adapter.calls), 1)
        self.assertEqual(self.service.image_runner.enqueued, [])
        self.assertEqual(result.snapshot.kind, "narrative")

    def test_model_client_path_repairs_one_malformed_response(self) -> None:
        payload = {"items": [{"story": f"故事{i}", "hooks": [{"text": "钩子", "scenes": ["画面1", "画面2", "画面3"]}, {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]}]} for i in range(1, 6)]}
        client = SequenceModelClient([
            ModelResponse(content="not-json"),
            ModelResponse(content=json.dumps(payload, ensure_ascii=False), conversation_id="c", assistant_message_id="m"),
        ])
        with patch.dict(os.environ, {
            "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
            "WEB_ERP_AI_API_KEY": "secret",
            "WEB_ERP_AI_MODEL": "gpt-test",
            "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
            "WEB_ERP_AI_GAME_INFO_PATH": "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json",
        }, clear=False):
            service = CreativeGenerationService(repository=self.repo, model_client=client, image_runner=FakeImageRunner())
            result = service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))
        self.assertEqual(len(client.requests), 2)
        self.assertEqual(result.snapshot.kind, "narrative")

    def test_json_text_parse_failures_use_root_field_path(self) -> None:
        for value in ("", "not-json", "[]"):
            with self.subTest(value=value):
                with self.assertRaises(AiCreativeRequestError) as raised:
                    validate_creative_recommendations(value)

                self.assertEqual(raised.exception.field_path, "$")

    def test_narrative_validator_assigns_exact_path_to_each_rejection(self) -> None:
        invalid_item = valid_narrative_payload()
        invalid_item["items"][0] = None
        invalid_story = valid_narrative_payload()
        invalid_story["items"][0]["story"] = ""
        invalid_hooks = valid_narrative_payload()
        invalid_hooks["items"][0]["hooks"] = []
        invalid_hook = valid_narrative_payload()
        invalid_hook["items"][0]["hooks"][0] = None
        invalid_hook_text = valid_narrative_payload()
        invalid_hook_text["items"][0]["hooks"][0]["text"] = "\n"
        invalid_scenes = valid_narrative_payload()
        invalid_scenes["items"][0]["hooks"][0]["scenes"] = []
        invalid_scene = valid_narrative_payload()
        invalid_scene["items"][0]["hooks"][0]["scenes"][1] = "x" * 81
        cases = (
            ({"items": []}, "items"),
            (invalid_item, "items[0]"),
            (invalid_story, "items[0].story"),
            (invalid_hooks, "items[0].hooks"),
            (invalid_hook, "items[0].hooks[0]"),
            (invalid_hook_text, "items[0].hooks[0].text"),
            (invalid_scenes, "items[0].hooks[0].scenes"),
            (invalid_scene, "items[0].hooks[0].scenes[1]"),
        )

        for value, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                with self.assertRaises(AiCreativeRequestError) as raised:
                    validate_creative_recommendations(value)

                self.assertEqual(raised.exception.field_path, expected_path)

    def test_visual_choices_wrapper_failures_use_exact_field_paths(self) -> None:
        cases = (
            ({"choices": []}, "choices"),
            ({"choices": [{}]}, "choices[0].message.content"),
        )

        for value, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                with self.assertRaises(AiCreativeRequestError) as raised:
                    validate_visual_creative_recommendations(value)

                self.assertEqual(raised.exception.field_path, expected_path)

    def test_malformed_model_json_persists_root_field_path(self) -> None:
        client = SequenceModelClient(
            [ModelResponse(content="not-json"), ModelResponse(content="not-json")]
        )
        service = CreativeGenerationService(
            repository=self.repo,
            model_client=client,
            image_runner=FakeImageRunner(),
            environment={
                "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "fake-test-key",
                "WEB_ERP_AI_MODEL": "fake-test-model",
                "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
                "WEB_ERP_AI_GAME_INFO_PATH": (
                    "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json"
                ),
            },
        )

        with self.assertRaises(AiCreativeRequestError) as raised:
            service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))

        self.assertEqual(raised.exception.error_code, "model_output_invalid")
        self.assertEqual(raised.exception.field_path, "$")
        snapshot = service._build_snapshot(self.repo.get_project(self.narrative_project["id"]))
        history = self.repo.generation_history(
            self.narrative_project["id"],
            "narrative",
            snapshot.fingerprint,
        )
        self.assertEqual(history["failed_generations"][0]["field_path"], "$")

    def test_http_model_client_choices_failure_persists_wrapper_field_path(self) -> None:
        client = HttpModelClient(
            api_url="https://example.invalid/v1/chat/completions",
            api_key="fake-test-key",
            transport=lambda *args, **kwargs: LegacyResponse({"choices": []}),
        )
        service = CreativeGenerationService(
            repository=self.repo,
            model_client=client,
            image_runner=FakeImageRunner(),
            environment={
                "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "fake-test-key",
                "WEB_ERP_AI_MODEL": "fake-test-model",
                "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
                "WEB_ERP_AI_GAME_INFO_PATH": (
                    "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json"
                ),
            },
        )

        with self.assertRaises(AiCreativeRequestError) as raised:
            service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))

        self.assertEqual(raised.exception.error_code, "model_output_invalid")
        self.assertEqual(raised.exception.field_path, "choices")
        snapshot = service._build_snapshot(self.repo.get_project(self.narrative_project["id"]))
        history = self.repo.generation_history(
            self.narrative_project["id"],
            "narrative",
            snapshot.fingerprint,
        )
        self.assertEqual(history["failed_generations"][0]["field_path"], "choices")

    def test_model_validation_failure_preserves_field_path_and_error_contract(self) -> None:
        valid_story = {
            "story": "故事",
            "hooks": [
                {"text": "钩子1", "scenes": ["画面1", "画面2", "画面3"]},
                {"text": "钩子2", "scenes": ["画面4", "画面5", "画面6"]},
            ],
        }
        payload = {"items": [dict(valid_story) for _ in range(5)]}
        payload["items"][0]["story"] = ""
        client = SequenceModelClient(
            [ModelResponse(content=json.dumps(payload, ensure_ascii=False)) for _ in range(2)]
        )
        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "secret",
                "WEB_ERP_AI_MODEL": "gpt-test",
                "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
                "WEB_ERP_AI_GAME_INFO_PATH": "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json",
            },
            clear=False,
        ):
            service = CreativeGenerationService(
                repository=self.repo,
                model_client=client,
                image_runner=FakeImageRunner(),
            )
            with self.assertRaises(AiCreativeRequestError) as raised:
                service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))

        error = raised.exception
        self.assertEqual(len(client.requests), 2)
        self.assertEqual(getattr(error, "error_code", ""), "model_output_invalid")
        self.assertEqual(getattr(error, "phase", ""), "validation")
        self.assertEqual(getattr(error, "field_path", ""), "items[0].story")
        self.assertFalse(getattr(error, "retryable", True))
        self.assertIn("items[0].story", str(error))
        snapshot = service._build_snapshot(self.repo.get_project(self.narrative_project["id"]))
        history = self.repo.generation_history(
            self.narrative_project["id"],
            "narrative",
            snapshot.fingerprint,
        )
        self.assertEqual(history["failed_generations"][0]["field_path"], "items[0].story")
        self.assertRegex(history["failed_generations"][0]["trace_id"], r"^[0-9a-f]{32}$")

    def test_static_visual_validation_failure_preserves_exact_field_path(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {"task_description": "展示说明"},
        )
        items = copy.deepcopy(self.service.adapter.results_by_kind["visual"].items)
        items[0]["title"] = ""
        response = ModelResponse(content=json.dumps({"items": items}, ensure_ascii=False))
        client = SequenceModelClient([response, response])
        service = CreativeGenerationService(
            repository=self.repo,
            model_client=client,
            image_runner=FakeImageRunner(),
            environment={
                "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "fake-test-key",
                "WEB_ERP_AI_MODEL": "fake-test-model",
            },
        )

        with self.assertRaises(AiCreativeRequestError) as raised:
            service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

        self.assertEqual(raised.exception.error_code, "model_output_invalid")
        self.assertEqual(raised.exception.field_path, "items[0].title")
        snapshot = service._build_snapshot(self.repo.get_project(self.visual_project["id"]))
        history = self.repo.generation_history(
            self.visual_project["id"],
            "visual",
            snapshot.fingerprint,
        )
        self.assertEqual(history["failed_generations"][0]["field_path"], "items[0].title")

    def test_carousel_validation_failure_preserves_deep_field_path(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {
                "task_description": "展示说明",
                "creative_tags": {
                    "visual_carousel": ["是"],
                    "visual_carousel_count": ["3屏"],
                },
            },
        )

        def scheme(index: int) -> dict[str, object]:
            return {
                "title": f"方案{index}",
                "creative_summary": f"说明{index}",
                "creative_sources": [f"来源{index}"],
                "frame_count": 3,
                "visual_continuity_rules": ["保持主体一致"],
                "frame_plan": [
                    {"index": frame, "description": f"画面{frame}"}
                    for frame in range(1, 4)
                ],
                "first_frame": {
                    "index": 1,
                    "content": "首帧",
                    "image_generation_instruction": "图片指令",
                },
            }

        items = [scheme(index) for index in range(1, 4)]
        items[0]["frame_plan"][1]["description"] = ""
        response = ModelResponse(content=json.dumps({"items": items}, ensure_ascii=False))
        client = SequenceModelClient([response, response])
        service = CreativeGenerationService(
            repository=self.repo,
            model_client=client,
            image_runner=FakeImageRunner(),
            environment={
                "WEB_ERP_AI_API_URL": "https://example.invalid/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "fake-test-key",
                "WEB_ERP_AI_MODEL": "fake-test-model",
            },
        )

        with self.assertRaises(AiCreativeRequestError) as raised:
            service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

        self.assertEqual(raised.exception.error_code, "model_output_invalid")
        self.assertEqual(
            raised.exception.field_path,
            "items[0].frame_plan[1].description",
        )

    def test_generate_blank_task_description_raises_input_error(self) -> None:
        self.repo.update_project(self.narrative_project["id"], {"task_description": "   "})
        with self.assertRaises(GenerationInputError):
            self.service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))

    def test_generate_missing_project_raises_not_found_error(self) -> None:
        with self.assertRaises(GenerationNotFoundError):
            self.service.generate(CreativeGenerationRequest(project_id=999999))

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
        self.assertEqual(self.service.image_runner.waited_for, [])

    def test_enabled_carousel_without_count_is_rejected_before_adapter_call(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {
                "task_description": "展示说明",
                "creative_tags": {
                    "visual_carousel": ["是"],
                    "visual_carousel_count": [""],
                },
            },
        )

        with self.assertRaises(GenerationInputError) as raised:
            self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

        self.assertIn("轮播数量", str(raised.exception))
        self.assertEqual(getattr(raised.exception, "error_code", ""), "carousel_count_required")
        self.assertEqual(
            getattr(raised.exception, "field_path", ""),
            "creative_tags.visual_carousel_count",
        )
        self.assertEqual(self.service.adapter.calls, [])
        with closing(self.repo._connect()) as connection:
            count = connection.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        self.assertEqual(count, 0)

    def test_enabled_carousel_with_invalid_count_is_rejected_before_model_call(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {
                "task_description": "展示说明",
                "creative_tags": {
                    "visual_carousel": ["是"],
                    "visual_carousel_count": ["6屏"],
                },
            },
        )
        client = FakeModelClient(ModelResponse(content="{}"))
        service = CreativeGenerationService(
            repository=self.repo,
            model_client=client,
            image_runner=FakeImageRunner(),
        )

        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "secret",
                "WEB_ERP_AI_MODEL": "gpt-test",
            },
            clear=False,
        ):
            with self.assertRaises(GenerationInputError) as raised:
                service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

        self.assertEqual(client.requests, [])
        self.assertEqual(getattr(raised.exception, "error_code", ""), "carousel_count_invalid")
        self.assertEqual(
            getattr(raised.exception, "field_path", ""),
            "creative_tags.visual_carousel_count",
        )
        with closing(self.repo._connect()) as connection:
            count = connection.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        self.assertEqual(count, 0)

    def test_generate_visual_calls_model_once(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {"task_description": "展示说明"},
        )
        self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))
        self.assertEqual(len(self.service.adapter.calls), 1)

    def test_carousel_batch_uses_shared_plan_then_one_new_session_per_scheme_for_first_frames(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {
                "task_description": "展示说明",
                "creative_tags": {
                    "visual_carousel": ["是"],
                    "visual_carousel_count": ["3屏"],
                    "visual_carousel_form": ["产品演示"],
                },
            },
        )

        def scheme_payload(index: int) -> dict[str, object]:
            return {
                "title": f"方案{index}",
                "creative_summary": f"说明{index}",
                "creative_sources": [f"来源{index}"],
                "frame_count": 3,
                "visual_continuity_rules": ["保持主体一致"],
                "frame_plan": [
                    {"index": frame, "description": f"方案{index}画面{frame}"}
                    for frame in range(1, 4)
                ],
                "first_frame": {
                    "index": 1,
                    "content": f"共享草稿首帧{index}",
                    "image_generation_instruction": f"共享草稿图片{index}",
                },
            }

        shared = ModelResponse(
            content=json.dumps({"items": [scheme_payload(index) for index in range(1, 4)]}, ensure_ascii=False),
            conversation_id="shared-conversation",
            assistant_message_id="shared-message",
        )
        client = SequenceModelClient([shared])
        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "secret",
                "WEB_ERP_AI_MODEL": "gpt-test",
            },
            clear=False,
        ):
            service = CreativeGenerationService(
                repository=self.repo,
                model_client=client,
                image_runner=FakeImageRunner(),
            )
            outcome = service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

        self.assertEqual(len(client.requests), 1)
        self.assertEqual(client.requests[0].conversation_id, "")
        self.assertEqual(client.requests[0].parent_message_id, "")
        with closing(self.repo._connect()) as connection:
            rows = connection.execute(
                "SELECT content_json FROM visual_items ORDER BY item_index",
            ).fetchall()
        schemes = [json.loads(row[0]) for row in rows]
        self.assertEqual(
            [scheme["first_frame"]["content"] for scheme in schemes],
            ["共享草稿首帧1", "共享草稿首帧2", "共享草稿首帧3"],
        )
        self.assertEqual(service.image_runner.enqueued, [[1, 2, 3]])
        public_history = json.dumps(outcome.history, ensure_ascii=False)
        self.assertNotIn("shared-conversation", public_history)

    def test_generate_expires_stale_pending_generation_and_persists_request_context(self) -> None:
        with closing(self.repo._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO generations(
                    project_id, recommendation_kind, schema_version, input_fingerprint, batch_index,
                    status, items_json, usage_json, conversation_id, assistant_message_id, error,
                    created_at, updated_at
                ) VALUES(?,?,?,?,?,'pending','[]','{}','','','',?,?)
                """,
                (
                    self.visual_project["id"],
                    "visual",
                    "visual.v1",
                    "stale-fingerprint",
                    1,
                    "2026-08-31 00:00:00",
                    "2026-08-31 00:00:00",
                ),
            )
            stale_id = int(cursor.lastrowid)
            connection.commit()

        self.repo.update_project(self.visual_project["id"], {"task_description": "展示说明"})
        outcome = self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

        self.assertEqual(len(self.service.adapter.calls), 1)
        self.assertRegex(outcome.context.request_id, r"^[0-9a-f]{32}$")
        self.assertEqual(outcome.context.context_json["request_id"], outcome.context.request_id)
        self.assertEqual(outcome.context.context_json["project_id"], self.visual_project["id"])
        with closing(self.repo._connect()) as connection:
            stale_status = connection.execute(
                "SELECT status FROM generations WHERE id=?", (stale_id,)
            ).fetchone()[0]
            current_row = connection.execute(
                "SELECT request_id, context_json FROM generations WHERE request_id=? ORDER BY id DESC LIMIT 1",
                (outcome.context.request_id,),
            ).fetchone()
        self.assertEqual(stale_status, "expired")
        self.assertIsNotNone(current_row)
        self.assertEqual(current_row[0], outcome.context.request_id)
        self.assertNotIn("prompt", current_row[1])
        self.assertNotIn("response", current_row[1])
        self.assertNotIn("secret", current_row[1])

    def test_generate_active_pending_generation_raises_conflict(self) -> None:
        self.repo.update_project(self.visual_project["id"], {"task_description": "展示说明"})
        snapshot = self.service._build_snapshot(self.repo.get_project(self.visual_project["id"]))
        with closing(self.repo._connect()) as connection:
            connection.execute(
                """
                INSERT INTO generations(
                    project_id, recommendation_kind, schema_version, input_fingerprint, batch_index,
                    status, items_json, usage_json, conversation_id, assistant_message_id, error,
                    created_at, updated_at
                ) VALUES(?,?,?,?,?,'pending','[]','{}','','','',?,?)
                """,
                (
                    self.visual_project["id"],
                    "visual",
                    "visual.v1",
                    snapshot.fingerprint,
                    1,
                    "2999-01-01 00:00:00",
                    "2999-01-01 00:00:00",
                ),
            )
            connection.commit()

        with self.assertRaises(GenerationConflictError):
            self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

    def test_generate_narrative_can_use_a_generic_model_client(self) -> None:
        response = ModelResponse(
            content=(
                '{"items":['
                '{"story":"故事1","hooks":[{"text":"钩子1","scenes":["画面1","画面2","画面3"]},{"text":"钩子2","scenes":["画面4","画面5","画面6"]}]},'
                '{"story":"故事2","hooks":[{"text":"钩子1","scenes":["画面1","画面2","画面3"]},{"text":"钩子2","scenes":["画面4","画面5","画面6"]}]},'
                '{"story":"故事3","hooks":[{"text":"钩子1","scenes":["画面1","画面2","画面3"]},{"text":"钩子2","scenes":["画面4","画面5","画面6"]}]},'
                '{"story":"故事4","hooks":[{"text":"钩子1","scenes":["画面1","画面2","画面3"]},{"text":"钩子2","scenes":["画面4","画面5","画面6"]}]},'
                '{"story":"故事5","hooks":[{"text":"钩子1","scenes":["画面1","画面2","画面3"]},{"text":"钩子2","scenes":["画面4","画面5","画面6"]}]}'
                ']}'
            ),
            input_tokens=11,
            output_tokens=22,
            total_tokens=33,
            latency_ms=4,
            conversation_id="conversation",
            assistant_message_id="message",
        )
        client = FakeModelClient(response)
        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "secret",
                "WEB_ERP_AI_MODEL": "gpt-test",
                "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
                "WEB_ERP_AI_GAME_INFO_PATH": "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json",
            },
            clear=False,
        ):
            service = CreativeGenerationService(
                repository=self.repo,
                model_client=client,
                image_runner=FakeImageRunner(),
            )
            self.repo.update_project(self.narrative_project["id"], {"task_description": "叙事说明"})

            result = service.generate(CreativeGenerationRequest(project_id=self.narrative_project["id"]))

        self.assertEqual(len(client.requests), 1)
        request = client.requests[0]
        self.assertIn("叙事说明", request.messages[0]["content"])
        self.assertEqual(result.snapshot.kind, "narrative")
        with closing(self.repo._connect()) as connection:
            row = connection.execute(
                "SELECT conversation_id, assistant_message_id FROM generations ORDER BY id DESC LIMIT 1",
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["conversation_id"], "conversation")
        self.assertEqual(row["assistant_message_id"], "message")
        self.assertEqual(result.history["batches"][0]["usage"]["usage_source"], "estimated")

    def test_default_game_info_path_points_to_existing_v2_file(self) -> None:
        game_info = load_ai_creative_game_info({})

        self.assertEqual(game_info.version, "v2")
        self.assertIn("《剑侠传奇》", game_info.content)

    def test_generate_model_timeout_raises_queue_timeout_error(self) -> None:
        class TimeoutModelClient:
            def generate(self, request: object) -> object:
                raise requests.Timeout("timeout")

        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "secret",
                "WEB_ERP_AI_MODEL": "gpt-test",
                "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
                "WEB_ERP_AI_GAME_INFO_PATH": "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json",
            },
            clear=False,
        ):
            service = CreativeGenerationService(
                repository=self.repo,
                model_client=TimeoutModelClient(),
                image_runner=FakeImageRunner(),
            )
            self.repo.update_project(self.visual_project["id"], {"task_description": "展示说明"})
            with self.assertRaises(GenerationQueueTimeoutError):
                service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))

    def test_generate_legacy_adapter_timeout_raises_queue_timeout_error(self) -> None:
        def timeout_transport(*args, **kwargs):
            raise requests.Timeout("timeout")

        with patch.dict(
            os.environ,
            {
                "WEB_ERP_AI_API_URL": "https://example.com/v1/chat/completions",
                "WEB_ERP_AI_API_KEY": "secret",
                "WEB_ERP_AI_MODEL": "gpt-test",
                "WEB_ERP_AI_PROMPT_TEMPLATE": NARRATIVE_PROMPT_TEMPLATE,
                "WEB_ERP_AI_GAME_INFO_PATH": "D:\\code\\ai_creative_studio\\config\\ai_creative_game_info_v2.json",
            },
            clear=False,
        ):
            config = load_ai_creative_config()
            game_info = load_ai_creative_game_info().content
            with self.assertRaises(AiCreativeQueueTimeoutError):
                generate_creative_recommendations(
                    {},
                    config=config,
                    game_info=game_info,
                    task_type="",
                    task_description="叙事说明",
                    script_type="叙事类",
                    transport=timeout_transport,
                )

    def test_legacy_generation_json_failures_use_root_field_path(self) -> None:
        narrative_config = AiCreativeConfig(
            provider="chatgpt-web",
            api_url="https://example.invalid/v1/chat/completions",
            api_key="fake-test-key",
            model="fake-test-model",
            timeout_seconds=1,
            prompt_version="test",
            prompt_template=NARRATIVE_PROMPT_TEMPLATE,
        )
        visual_config = AiCreativeConfig(
            provider="chatgpt-web",
            api_url="https://example.invalid/v1/chat/completions",
            api_key="fake-test-key",
            model="fake-test-model",
            timeout_seconds=1,
            prompt_version="test",
            prompt_template="\n".join(
                (
                    "{{task_type}}",
                    "{{task_description}}",
                    "{{creative_tags}}",
                    "{{aspect_ratio}}",
                    "{{product_evidence_summary}}",
                    "{{reference_file_names}}",
                    "{{carousel_context}}",
                )
            ),
        )

        def malformed_transport(*args, **kwargs):
            return LegacyResponse(json_error=ValueError("malformed"))

        calls = (
            lambda: generate_creative_recommendations(
                {},
                config=narrative_config,
                task_description="叙事说明",
                script_type="叙事类",
                transport=malformed_transport,
            ),
            lambda: generate_visual_creative_recommendations(
                {},
                config=visual_config,
                task_description="展示说明",
                carousel_config={
                    "enabled": "否",
                    "count_mode": "none",
                    "count": 1,
                    "rounds": [],
                },
                transport=malformed_transport,
            ),
        )

        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(AiCreativeRequestError) as raised:
                    call()

                self.assertEqual(raised.exception.field_path, "$")

    def test_legacy_generation_cursor_failures_use_exact_field_paths(self) -> None:
        narrative_payload = valid_narrative_payload()
        narrative_payload["assistant_message_id"] = "assistant"
        visual_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": copy.deepcopy(
                                    self.service.adapter.results_by_kind["visual"].items
                                )
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "conversation_id": "conversation",
        }
        narrative_config = AiCreativeConfig(
            provider="chatgpt-web",
            api_url="https://example.invalid/v1/chat/completions",
            api_key="fake-test-key",
            model="fake-test-model",
            timeout_seconds=1,
            prompt_version="test",
            prompt_template=NARRATIVE_PROMPT_TEMPLATE,
        )
        visual_config = AiCreativeConfig(
            provider="chatgpt-web",
            api_url="https://example.invalid/v1/chat/completions",
            api_key="fake-test-key",
            model="fake-test-model",
            timeout_seconds=1,
            prompt_version="test",
            prompt_template="\n".join(
                (
                    "{{task_type}}",
                    "{{task_description}}",
                    "{{creative_tags}}",
                    "{{aspect_ratio}}",
                    "{{product_evidence_summary}}",
                    "{{reference_file_names}}",
                    "{{carousel_context}}",
                )
            ),
        )
        cases = (
            (
                lambda: generate_creative_recommendations(
                    {},
                    config=narrative_config,
                    task_description="叙事说明",
                    script_type="叙事类",
                    transport=lambda *args, **kwargs: LegacyResponse(narrative_payload),
                ),
                "conversation_id",
            ),
            (
                lambda: generate_visual_creative_recommendations(
                    {},
                    config=visual_config,
                    task_description="展示说明",
                    transport=lambda *args, **kwargs: LegacyResponse(visual_payload),
                ),
                "assistant_message_id",
            ),
        )

        for call, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                with self.assertRaises(AiCreativeRequestError) as raised:
                    call()

                self.assertEqual(raised.exception.field_path, expected_path)

    def test_inactive_tags_do_not_change_fingerprint_or_batch_identity(self) -> None:
        self.repo.update_project(
            self.visual_project["id"],
            {
                "task_description": "展示说明",
                "creative_tags": {
                    "visual_carousel": ["是"],
                    "visual_carousel_count": ["3屏"],
                    "visual_carousel_form": ["左右滑动"],
                    "target_audiences": ["武侠玩家"],
                },
            },
        )
        first_snapshot = self.service._build_snapshot(self.repo.get_project(self.visual_project["id"]))
        first_app_fingerprint = StudioApplication._fingerprint(self.repo.get_project(self.visual_project["id"]))
        self.assertEqual(first_snapshot.fingerprint, first_app_fingerprint)
        self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))
        self.repo.update_project(
            self.visual_project["id"],
            {
                "creative_tags": {
                    "visual_carousel": ["是"],
                    "visual_carousel_count": ["3屏"],
                    "visual_carousel_form": ["左右滑动"],
                    "target_audiences": ["武侠玩家", "仙侠玩家"],
                }
            },
        )
        second_snapshot = self.service._build_snapshot(self.repo.get_project(self.visual_project["id"]))
        second_app_fingerprint = StudioApplication._fingerprint(self.repo.get_project(self.visual_project["id"]))
        self.assertEqual(second_snapshot.fingerprint, first_snapshot.fingerprint)
        self.assertEqual(second_app_fingerprint, first_app_fingerprint)
        outcome = self.service.generate(CreativeGenerationRequest(project_id=self.visual_project["id"]))
        self.assertEqual([batch["batch_index"] for batch in outcome.history["batches"]], [1, 2])
        self.assertEqual(
            [batch["input_fingerprint"] for batch in outcome.history["batches"]],
            [first_snapshot.fingerprint, first_snapshot.fingerprint],
        )

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
                "SELECT status, error, error_detail FROM generations ORDER BY id DESC LIMIT 1",
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error"], "生成失败，请重试")
        self.assertIn("RuntimeError: boom", row["error_detail"])


if __name__ == "__main__":
    unittest.main()
