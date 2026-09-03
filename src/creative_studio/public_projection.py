"""Deny-by-default projections for every browser-visible creative result."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SAFE_IMAGE_ERROR = "图片生成失败，请重试"
SAFE_GENERATION_ERROR = "生成失败，请重试"
PRIVATE_RESULT_FIELDS = frozenset(
    {
        "image_prompt",
        "image_generation_instruction",
        "conversation_id",
        "parent_message_id",
        "assistant_message_id",
        "image_path",
        "stored_name",
        "gateway_job_id",
        "raw_response",
        "private_context",
        "stack_trace",
        "error_detail",
    }
)
PUBLIC_CREATIVE_TAG_KEYS = (
    "target_audiences",
    "secondary_target_audiences",
    "art_style",
    "player_desires",
    "secondary_player_desires",
    "content_forms",
    "secondary_content_forms",
    "opening_hooks",
    "secondary_opening_hooks",
    "product_evidences",
    "secondary_product_evidences",
    "visual_target_audiences",
    "visual_secondary_target_audiences",
    "visual_player_desires",
    "visual_secondary_player_desires",
    "visual_product_selling_points",
    "visual_secondary_product_selling_points",
    "visual_display_contents",
    "visual_secondary_display_contents",
    "visual_art_style_relevance",
    "visual_art_style",
    "visual_art_style_references",
    "visual_motif",
    "visual_dynamics",
    "visual_voice_hook",
    "visual_carousel",
    "visual_carousel_count",
    "visual_carousel_form",
)
PUBLIC_CAROUSEL_ROUND_OVERRIDE_KEYS = (
    "visual_product_selling_points",
    "visual_display_contents",
    "visual_motif",
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _text_list(value: Any) -> list[str]:
    return [item for item in _list(value) if isinstance(item, str)]


def _legacy_carousel_frame_list(value: Any) -> list[str | int]:
    return [
        item
        for item in _list(value)
        if isinstance(item, str) or (isinstance(item, int) and not isinstance(item, bool))
    ]


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_image_error(value: Any) -> str:
    return SAFE_IMAGE_ERROR if _text(value).strip() else ""


def _public_carousel_rounds(value: Any) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    for raw_round in _list(value):
        source = _mapping(raw_round)
        index = _optional_int(source.get("index"))
        mode = _text(source.get("mode"))
        if index is None or index < 1 or mode not in {"base", "inherit", "custom"}:
            continue
        raw_overrides = _mapping(source.get("overrides"))
        overrides = {
            key: _text_list(raw_overrides.get(key))
            for key in PUBLIC_CAROUSEL_ROUND_OVERRIDE_KEYS
            if key in raw_overrides
        }
        rounds.append({"index": index, "mode": mode, "overrides": overrides})
    return rounds


class PublicResultMapper:
    """Build public DTOs without copying untrusted internal dictionaries."""

    def result_item(
        self,
        value: Any,
        *,
        recommendation_kind: str,
    ) -> dict[str, Any]:
        """Project one narrative or visual result according to its kind."""

        if recommendation_kind == "narrative":
            return self.narrative_item(value)
        return self.visual_item(value)

    def narrative_item(self, value: Any) -> dict[str, Any]:
        """Build the public narrative item shape from an internal value."""

        source = _mapping(value)
        hooks: list[dict[str, Any]] = []
        for raw_hook in _list(source.get("hooks")):
            hook = _mapping(raw_hook)
            hooks.append(
                {
                    "text": _text(hook.get("text")),
                    "scenes": _text_list(hook.get("scenes")),
                }
            )
        public = {"story": _text(source.get("story")), "hooks": hooks}
        for key in ("concept_id", "audience_tension", "product_value"):
            if key in source:
                public[key] = _text(source.get(key))
        evidence = _mapping(source.get("evidence"))
        if evidence:
            public["evidence"] = {
                key: _text_list(evidence.get(key))
                for key in ("confirmed", "inferred", "to_confirm")
                if key in evidence
            }
        if "risks" in source:
            public["risks"] = _text_list(source.get("risks"))
        return public

    def visual_item(self, value: Any) -> dict[str, Any]:
        """Build a public visual item while omitting execution-only fields."""

        source = _mapping(value)
        public: dict[str, Any] = {}
        for key in (
            "title",
            "subtitle",
            "creative_description",
            "core_subject",
            "layout",
            "visual_style",
            "creative_summary",
        ):
            if key in source:
                public[key] = _text(source.get(key))
        for key in (
            "content_extensions",
            "keywords",
            "creative_sources",
            "visual_continuity_rules",
        ):
            if key in source:
                public[key] = _text_list(source.get(key))
        if "carousel_frames" in source:
            public["carousel_frames"] = _legacy_carousel_frame_list(
                source.get("carousel_frames")
            )
        if "reference_sources" in source:
            public["reference_sources"] = [
                {"name": _text(item.get("name")), "note": _text(item.get("note"))}
                for item in (_mapping(raw) for raw in _list(source.get("reference_sources")))
            ]
        if "frame_count" in source:
            frame_count = _optional_int(source.get("frame_count"))
            if frame_count is not None:
                public["frame_count"] = frame_count
        if "frame_plan" in source:
            public["frame_plan"] = [
                {
                    "index": _optional_int(item.get("index")) or 0,
                    "description": _text(item.get("description")),
                }
                for item in (_mapping(raw) for raw in _list(source.get("frame_plan")))
            ]
        if "first_frame" in source:
            first = _mapping(source.get("first_frame"))
            public["first_frame"] = {
                "index": _optional_int(first.get("index")) or 0,
                "content": _text(first.get("content")),
            }
        if "carousel" in source:
            carousel = _mapping(source.get("carousel"))
            public["carousel"] = {
                "count": _optional_int(carousel.get("count")) or 0,
                "form": _text_list(carousel.get("form")),
                "frames": [
                    {
                        "index": _optional_int(frame.get("index")) or 0,
                        "display_description": _text(frame.get("display_description")),
                    }
                    for frame in (_mapping(raw) for raw in _list(carousel.get("frames")))
                ],
            }
        for key in ("id", "item_index", "scheme_id", "generation_id"):
            if key in source:
                number = _optional_int(source.get(key))
                if number is not None:
                    public[key] = number
        for key in ("aspect_ratio", "image_status", "scheme_status"):
            if key in source:
                public[key] = _text(source.get(key))
        if "image_status" in public:
            item_id = public.get("id")
            public["image_url"] = (
                f"/api/visual-items/{item_id}/image"
                if public["image_status"] == "success" and item_id is not None
                else ""
            )
        if "image_error" in source:
            public["image_error"] = _safe_image_error(source.get("image_error"))
        if "frames" in source:
            public["frames"] = [self.display_frame(frame) for frame in _list(source.get("frames"))]
        return public

    def display_frame(self, value: Any) -> dict[str, Any]:
        """Build one public display frame and its application-owned image URL."""

        source = _mapping(value)
        frame_index = _optional_int(source.get("frame_index"))
        if frame_index is None:
            frame_index = _optional_int(source.get("index")) or 0
        image_status = _text(source.get("image_status") or "pending")
        scheme_id = _optional_int(source.get("scheme_id"))
        image_url = (
            f"/api/visual-items/{scheme_id}/frames/{frame_index}/image"
            if image_status == "success" and scheme_id is not None
            else ""
        )
        public = {
            "frame_index": frame_index,
            "planned_content": _text(source.get("planned_content")),
            "actual_content": _text(source.get("actual_content")),
            "transition_from_previous": _text(source.get("transition_from_previous")),
            "transition_to_next": source.get("transition_to_next")
            if isinstance(source.get("transition_to_next"), str) or source.get("transition_to_next") is None
            else None,
            "ending_note": source.get("ending_note")
            if isinstance(source.get("ending_note"), str) or source.get("ending_note") is None
            else None,
            "image_status": image_status,
            "image_url": image_url,
            "image_error": _safe_image_error(source.get("image_error")),
        }
        return public

    def display_scheme(self, value: Any) -> dict[str, Any]:
        """Build the public shape for a selected or continued display scheme."""

        source = _mapping(value)
        projected = self.visual_item(source)
        scheme_id = _optional_int(source.get("scheme_id"))
        if scheme_id is not None:
            projected["scheme_id"] = scheme_id
        return projected

    def visual_status(self, value: Any) -> dict[str, Any]:
        """Build a visual item's public image status response."""

        source = _mapping(value)
        item_id = _optional_int(source.get("id")) or 0
        status = _text(source.get("image_status") or "queued")
        return {
            "id": item_id,
            "image_status": status,
            "image_url": f"/api/visual-items/{item_id}/image" if status == "success" else "",
            "image_error": _safe_image_error(source.get("image_error")),
        }

    def adoption(self, value: Any) -> dict[str, Any] | None:
        """Build a public adoption record and project its stored snapshot."""

        if not isinstance(value, Mapping):
            return None
        kind = _text(value.get("recommendation_kind"))
        if kind not in {"narrative", "visual"}:
            return None
        return {
            "recommendation_kind": kind,
            "reference_id": _text(value.get("reference_id")),
            "snapshot": self.result_item(value.get("snapshot"), recommendation_kind=kind),
            "updated_at": _text(value.get("updated_at")),
        }

    def project(self, value: Any) -> dict[str, Any]:
        """Build the full browser-visible project representation."""

        source = _mapping(value)
        public: dict[str, Any] = {}
        for key in ("id", "owner_user_id"):
            if key in source:
                number = _optional_int(source.get(key))
                public[key] = number
        for key in (
            "name",
            "script_type",
            "task_type",
            "task_description",
            "aspect_ratio",
            "product_evidence_summary",
            "created_at",
            "updated_at",
        ):
            if key in source:
                public[key] = _text(source.get(key))
        tags = _mapping(source.get("creative_tags"))
        public["creative_tags"] = {
            key: _text_list(tags.get(key))
            for key in PUBLIC_CREATIVE_TAG_KEYS
            if key in tags
        }
        if "visual_carousel_rounds" in tags:
            public["creative_tags"]["visual_carousel_rounds"] = _public_carousel_rounds(
                tags.get("visual_carousel_rounds")
            )
        public["reference_files"] = [
            {
                "id": _optional_int(item.get("id")) or 0,
                "original_name": _text(item.get("original_name")),
                "size_bytes": _optional_int(item.get("size_bytes")) or 0,
                "created_at": _text(item.get("created_at")),
            }
            for item in (_mapping(raw) for raw in _list(source.get("reference_files")))
        ]
        public["adoption"] = self.adoption(source.get("adoption"))
        return public

    def project_summary(self, value: Any) -> dict[str, Any]:
        """Build the compact project-list representation."""

        source = _mapping(value)
        public: dict[str, Any] = {}
        for key in ("id", "owner_user_id"):
            if key in source:
                public[key] = _optional_int(source.get(key))
        for key in (
            "name",
            "script_type",
            "updated_at",
            "adopted_kind",
            "adopted_title",
        ):
            if key in source:
                public[key] = _text(source.get(key))
        return public

    def history(
        self,
        value: Any,
        *,
        recommendation_kind: str,
    ) -> dict[str, Any]:
        """Project current, stale, and failed generation history."""

        source = _mapping(value)
        return {
            "batches": [self._batch(batch, recommendation_kind) for batch in _list(source.get("batches"))],
            "stale_batches": [
                self._batch(batch, recommendation_kind) for batch in _list(source.get("stale_batches"))
            ],
            "failed_generations": [
                self.failure(item) for item in _list(source.get("failed_generations"))
            ],
            "remaining_generations": max(0, _optional_int(source.get("remaining_generations")) or 0),
        }

    def failure(self, value: Any) -> dict[str, Any]:
        """Build a safe public failure record without internal diagnostics."""

        source = _mapping(value)
        error_code = _text(source.get("error_code")) or "generation_failed"
        if error_code == "model_output_invalid":
            public_error = "AI返回结果格式无效"
        elif error_code in {"ai_queue_timeout", "generation_queue_timeout"}:
            public_error = "AI服务暂时不可用，请重试"
        elif error_code == "ai_configuration_error":
            public_error = "AI服务配置错误"
        elif error_code == "ai_request_failed":
            public_error = "AI接口请求失败，请重试"
        else:
            public_error = SAFE_GENERATION_ERROR
        return {
            "id": _optional_int(source.get("id")) or 0,
            "batch_index": _optional_int(source.get("batch_index")) or 0,
            "input_fingerprint": _text(source.get("input_fingerprint")),
            "error": public_error,
            "error_code": error_code,
            "phase": _text(source.get("error_phase") or source.get("phase")) or "generation",
            "field_path": _text(source.get("error_field_path") or source.get("field_path")),
            "retryable": bool(source.get("error_retryable", source.get("retryable"))),
            "trace_id": _text(source.get("error_trace_id") or source.get("trace_id")),
            "created_at": _text(source.get("created_at")),
        }

    def _batch(self, value: Any, recommendation_kind: str) -> dict[str, Any]:
        source = _mapping(value)
        usage = _mapping(source.get("usage"))
        public_usage: dict[str, Any] = {}
        for key in ("input_tokens", "output_tokens", "total_tokens", "cost_amount", "latency_ms"):
            item = usage.get(key)
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                public_usage[key] = item
        for key in ("usage_source", "cost_currency"):
            item = usage.get(key)
            if isinstance(item, str):
                public_usage[key] = item
        return {
            "id": _optional_int(source.get("id")) or 0,
            "batch_index": _optional_int(source.get("batch_index")) or 0,
            "input_fingerprint": _text(source.get("input_fingerprint")),
            "items": [
                self.result_item(item, recommendation_kind=recommendation_kind)
                for item in _list(source.get("items"))
            ],
            "usage": public_usage,
            "created_at": _text(source.get("created_at")),
        }


__all__ = ["PRIVATE_RESULT_FIELDS", "PublicResultMapper", "SAFE_IMAGE_ERROR"]
