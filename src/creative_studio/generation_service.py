"""创意生成编排服务。"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Protocol

import requests

from .ai_creative import (
    AiCreativeConfigurationError,
    AiCreativeRequestError,
    AiCreativeGenerationResult,
    NARRATIVE_TAG_KEYS,
    VISUAL_TAG_KEYS,
    build_creative_prompt,
    build_visual_creative_prompt,
    generate_creative_recommendations,
    generate_visual_creative_recommendations,
    load_ai_creative_config,
    load_ai_creative_game_info,
    load_ai_visual_creative_config,
    normalize_creative_tags,
    recommendation_kind_for_script_type,
    validate_creative_recommendations,
    validate_visual_creative_recommendations,
)
from .carousel import CarouselValidationError, normalize_visual_carousel_config
from .generation_models import (
    CreativeGenerationRequest,
    CreativeInputSnapshot,
    GenerationContext,
    GenerationConflictError,
    GenerationInputError,
    GenerationNotFoundError,
    GenerationQueueTimeoutError,
    GenerationOutcome,
)
from .model_client import ModelClient, ModelRequest
from .prompting import CompiledPrompt
from .repository import StudioRepository


ROOT_DIR = Path(__file__).resolve().parents[2]
TAG_OPTIONS_PATH = ROOT_DIR / "config" / "creative_tag_options.json"


class CreativeGenerationAdapter(Protocol):
    """桥接旧 AI 生成函数的临时适配器。"""

    def generate(
        self,
        snapshot: CreativeInputSnapshot,
        context: GenerationContext,
    ) -> AiCreativeGenerationResult:
        """返回一批创意结果。"""


def _load_tag_options() -> dict[str, Any]:
    try:
        payload = json.loads(TAG_OPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise AiCreativeConfigurationError("标签配置不存在或无法解析") from exc
    if not isinstance(payload, dict) or not payload.get("narrative") or not payload.get("visual"):
        raise AiCreativeConfigurationError("标签配置格式无效")
    return payload


def _fingerprint(snapshot: CreativeInputSnapshot) -> str:
    active_keys = VISUAL_TAG_KEYS if snapshot.script_type == "展示类" else NARRATIVE_TAG_KEYS
    value: dict[str, Any] = {
        "script_type": snapshot.script_type,
        "creative_tags": {
            key: sorted(snapshot.creative_tags[key])
            for key in active_keys
        },
        "task_type": snapshot.task_type,
        "task_description": snapshot.task_description,
        "product_evidence_summary": snapshot.product_evidence_summary,
        "aspect_ratio": snapshot.aspect_ratio,
    }
    if snapshot.kind == "visual":
        value["visual_carousel"] = snapshot.carousel_config
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LegacyCreativeGenerationAdapter:
    """用现有 AI 函数实现的一次性生成适配器。"""

    def generate(
        self,
        snapshot: CreativeInputSnapshot,
        context: GenerationContext,
    ) -> AiCreativeGenerationResult:
        tags = {key: list(values) for key, values in snapshot.creative_tags.items()}
        if snapshot.kind == "visual":
            tag_catalog = _load_tag_options()
            return generate_visual_creative_recommendations(
                tags,
                config=load_ai_visual_creative_config(carousel=snapshot.carousel_enabled),
                task_type=snapshot.task_type,
                task_description=snapshot.task_description,
                aspect_ratio=snapshot.aspect_ratio,
                product_evidence_summary=snapshot.product_evidence_summary,
                reference_file_names=snapshot.reference_file_names,
                carousel_config=snapshot.carousel_config if snapshot.carousel_enabled else None,
                tag_catalog=tag_catalog,
                conversation_id=context.conversation_id,
                parent_message_id=context.parent_message_id,
            )
        return generate_creative_recommendations(
            tags,
            config=load_ai_creative_config(),
            game_info=load_ai_creative_game_info().content,
            task_type=snapshot.task_type,
            task_description=snapshot.task_description,
            script_type=snapshot.script_type,
            conversation_id=context.conversation_id,
            parent_message_id=context.parent_message_id,
        )


class CreativeGenerationService:
    """把生成所需的编排从 HTTP 处理器中移出来。"""

    def __init__(
        self,
        repository: StudioRepository,
        adapter: CreativeGenerationAdapter | None = None,
        model_client: ModelClient | None = None,
        image_runner: Any | None = None,
        pending_timeout_seconds: int = 15 * 60,
    ) -> None:
        self.repository = repository
        self.adapter = adapter or LegacyCreativeGenerationAdapter()
        self.model_client = model_client
        self.image_runner = image_runner
        self.pending_timeout_seconds = max(1, int(pending_timeout_seconds))
        self._recover_pending_generations()

    def generate(self, request: CreativeGenerationRequest) -> GenerationOutcome:
        project = self.repository.get_project(int(request.project_id))
        if project is None:
            raise GenerationNotFoundError("项目不存在")
        if not str(project.get("task_description") or "").strip():
            raise GenerationInputError("请先填写创意说明")
        snapshot = self._build_snapshot(project)
        self._recover_pending_generations()
        request_id = uuid.uuid4().hex
        context_json = self._build_context_json(snapshot, request_id)
        reservation = self.repository.reserve_generation(
            snapshot.project_id,
            snapshot.kind,
            snapshot.schema_version,
            snapshot.fingerprint,
            context_json=context_json,
            request_id=request_id,
        )
        context = GenerationContext(
            reservation_id=int(reservation["id"]),
            batch_index=int(reservation["batch_index"]),
            schema_version=snapshot.schema_version,
            request_id=request_id,
            context_json=context_json,
            conversation_id=str(reservation.get("conversation_id") or ""),
            parent_message_id=str(reservation.get("parent_message_id") or ""),
        )
        try:
            if self.model_client is not None:
                result = self._generate_with_model_client(snapshot, context)
            else:
                result = self.adapter.generate(snapshot, context)
            item_ids: tuple[int, ...] = ()
            if snapshot.kind == "visual":
                item_ids = tuple(
                    self.repository.complete_visual_generation(
                        context.reservation_id,
                        result,
                        snapshot.aspect_ratio,
                    )
                )
                self._enqueue_visual_image_jobs(item_ids)
            else:
                self.repository.complete_narrative_generation(context.reservation_id, result)
            history = self.repository.generation_history(
                snapshot.project_id,
                snapshot.kind,
                snapshot.fingerprint,
            )
            return GenerationOutcome(
                history=history,
                snapshot=snapshot,
                context=context,
                item_ids=item_ids,
            )
        except Exception as exc:
            self.repository.fail_generation(context.reservation_id, str(exc))
            raise

    def _recover_pending_generations(self) -> int:
        return self.repository.recover_pending_generations(self.pending_timeout_seconds)

    def _generate_with_model_client(
        self,
        snapshot: CreativeInputSnapshot,
        context: GenerationContext,
    ) -> AiCreativeGenerationResult:
        if snapshot.kind == "visual":
            config = load_ai_visual_creative_config(carousel=snapshot.carousel_enabled)
            prompt = build_visual_creative_prompt(
                {key: list(values) for key, values in snapshot.creative_tags.items()},
                config.prompt_template,
                task_type=snapshot.task_type,
                task_description=snapshot.task_description,
                aspect_ratio=snapshot.aspect_ratio,
                product_evidence_summary=snapshot.product_evidence_summary,
                reference_file_names=snapshot.reference_file_names,
                carousel_config=snapshot.carousel_config if snapshot.carousel_enabled else None,
                tag_catalog=_load_tag_options(),
            )
            request = ModelRequest(
                model=config.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=5000,
                conversation_id=context.conversation_id,
                parent_message_id=context.parent_message_id,
            )
            response, items = self._request_and_validate(
                request,
                lambda payload: validate_visual_creative_recommendations(
                    payload,
                    carousel_config=snapshot.carousel_config if snapshot.carousel_enabled else None,
                    tag_catalog=_load_tag_options(),
                ),
            )
            return AiCreativeGenerationResult(
                items=items,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                usage_source="exact",
                cost_amount=None,
                cost_currency="",
                latency_ms=response.latency_ms,
                conversation_id=response.conversation_id,
                assistant_message_id=response.assistant_message_id,
            )

        config = load_ai_creative_config()
        prompt = build_creative_prompt(
            {key: list(values) for key, values in snapshot.creative_tags.items()},
            config.prompt_template,
            game_info=load_ai_creative_game_info().content,
            task_type=snapshot.task_type,
            task_description=snapshot.task_description,
            script_type=snapshot.script_type,
        )
        request = ModelRequest(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=10000,
            conversation_id=context.conversation_id,
            parent_message_id=context.parent_message_id,
        )
        response, items = self._request_and_validate(request, validate_creative_recommendations)
        return AiCreativeGenerationResult(
            items=items,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            usage_source="exact",
            cost_amount=None,
            cost_currency="",
            latency_ms=response.latency_ms,
            conversation_id=response.conversation_id,
            assistant_message_id=response.assistant_message_id,
        )

    def _request_and_validate(self, request: ModelRequest, validator):
        """调用模型并对格式错误执行一次有限修复重试。"""
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.model_client.generate(request)
            except requests.Timeout as exc:
                raise GenerationQueueTimeoutError("AI排队超时") from exc
            except Exception as exc:
                raise AiCreativeRequestError("AI接口请求失败") from exc
            try:
                payload = json.loads(response.content or "{}")
                return response, validator(payload)
            except (TypeError, ValueError, json.JSONDecodeError, AiCreativeRequestError) as exc:
                last_error = exc
                if attempt == 0:
                    continue
        raise AiCreativeRequestError("AI返回结果无法解析") from last_error

    def _build_snapshot(self, project: Mapping[str, Any]) -> CreativeInputSnapshot:
        script_type = str(project.get("script_type") or "").strip()
        kind = recommendation_kind_for_script_type(script_type)
        normalized_tags = normalize_creative_tags(project.get("creative_tags"))
        normalized_tags_by_kind = {
            key: tuple(normalized_tags[key])
            for key in normalized_tags
        }
        carousel_config: Mapping[str, Any] | None = None
        carousel_enabled = False
        if kind == "visual":
            try:
                carousel_config = normalize_visual_carousel_config(project.get("creative_tags"))
            except CarouselValidationError as exc:
                raise GenerationInputError(str(exc)) from exc
            carousel_enabled = bool(str(carousel_config.get("enabled") or "").strip() == "是")
        reference_file_names = tuple(self.repository.reference_file_names(int(project["id"])))
        snapshot = CreativeInputSnapshot(
            project_id=int(project["id"]),
            kind=kind,
            schema_version=(
                "visual.carousel.v1"
                if kind == "visual" and carousel_enabled
                else ("visual.v1" if kind == "visual" else "narrative.v1")
            ),
            fingerprint="",
            script_type=script_type,
            task_type=str(project.get("task_type") or "").strip(),
            task_description=str(project.get("task_description") or "").strip(),
            product_evidence_summary=str(project.get("product_evidence_summary") or "").strip(),
            aspect_ratio=str(project.get("aspect_ratio") or "").strip(),
            creative_tags=normalized_tags_by_kind,
            carousel_config=carousel_config,
            carousel_enabled=carousel_enabled,
            reference_file_names=reference_file_names,
        )
        return replace(snapshot, fingerprint=_fingerprint(snapshot))

    def _build_context_json(self, snapshot: CreativeInputSnapshot, request_id: str) -> dict[str, Any]:
        return {
            "project_id": snapshot.project_id,
            "kind": snapshot.kind,
            "schema_version": snapshot.schema_version,
            "fingerprint": snapshot.fingerprint,
            "script_type": snapshot.script_type,
            "task_type": snapshot.task_type,
            "task_description": snapshot.task_description,
            "product_evidence_summary": snapshot.product_evidence_summary,
            "aspect_ratio": snapshot.aspect_ratio,
            "creative_tags": {key: list(values) for key, values in snapshot.creative_tags.items()},
            "carousel_config": (
                json.loads(json.dumps(snapshot.carousel_config, ensure_ascii=False))
                if snapshot.carousel_config is not None
                else None
            ),
            "carousel_enabled": snapshot.carousel_enabled,
            "reference_file_names": list(snapshot.reference_file_names),
            "request_id": request_id,
        }

    def _enqueue_visual_image_jobs(self, item_ids: tuple[int, ...]) -> None:
        if self.image_runner is not None and item_ids:
            self.image_runner.enqueue(list(item_ids))
