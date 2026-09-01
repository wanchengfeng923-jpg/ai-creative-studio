"""创意生成编排服务。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Protocol

from .ai_creative import (
    AiCreativeGenerationResult,
    generate_creative_recommendations,
    generate_visual_creative_recommendations,
    load_ai_creative_config,
    load_ai_creative_game_info,
    load_ai_visual_creative_config,
    normalize_creative_tags,
    recommendation_kind_for_script_type,
)
from .carousel import CarouselValidationError, normalize_visual_carousel_config
from .generation_models import (
    CreativeGenerationRequest,
    CreativeInputSnapshot,
    GenerationContext,
    GenerationOutcome,
)
from .repository import StudioDataError, StudioRepository


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
        raise StudioDataError("标签配置不存在或无法解析") from exc
    if not isinstance(payload, dict) or not payload.get("narrative") or not payload.get("visual"):
        raise StudioDataError("标签配置格式无效")
    return payload


def _fingerprint(snapshot: CreativeInputSnapshot) -> str:
    value: dict[str, Any] = {
        "script_type": snapshot.script_type,
        "creative_tags": {
            key: sorted(values)
            for key, values in snapshot.creative_tags.items()
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
        image_runner: Any | None = None,
    ) -> None:
        self.repository = repository
        self.adapter = adapter or LegacyCreativeGenerationAdapter()
        self.image_runner = image_runner

    def generate(self, request: CreativeGenerationRequest) -> GenerationOutcome:
        project = self.repository.get_project(int(request.project_id))
        if project is None:
            raise StudioDataError("项目不存在")
        if not str(project.get("task_description") or "").strip():
            raise StudioDataError("请先填写创意说明")
        snapshot = self._build_snapshot(project)
        reservation = self.repository.reserve_generation(
            snapshot.project_id,
            snapshot.kind,
            snapshot.schema_version,
            snapshot.fingerprint,
        )
        context = GenerationContext(
            reservation_id=int(reservation["id"]),
            batch_index=int(reservation["batch_index"]),
            schema_version=snapshot.schema_version,
            conversation_id=str(reservation.get("conversation_id") or ""),
            parent_message_id=str(reservation.get("parent_message_id") or ""),
        )
        try:
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
                if self.image_runner is not None:
                    self.image_runner.enqueue(list(item_ids))
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
                raise StudioDataError(str(exc)) from exc
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
