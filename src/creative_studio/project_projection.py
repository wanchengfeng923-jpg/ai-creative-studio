"""Deny-by-default projections for browser-visible project data."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


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
    "visual_target_audiences",
    "visual_player_desires",
    "visual_product_selling_points",
    "visual_display_contents",
    "visual_motif",
    "visual_dynamics",
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


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _public_file_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    name = Path(value.replace("\\", "/")).name
    return " ".join(name.replace("\x00", "").split())[:255]


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


class ProjectProjection:
    """Build public project DTOs without copying internal dictionaries."""

    def project(self, value: Any) -> dict[str, Any]:
        """Project a repository record into a browser-visible project DTO."""

        source = _mapping(value)
        public: dict[str, Any] = {}
        for key in ("id", "owner_user_id"):
            if key in source:
                public[key] = _optional_int(source.get(key))
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
                "original_name": _public_file_name(item.get("original_name")),
                "size_bytes": _optional_int(item.get("size_bytes")) or 0,
                "sha256": _text(item.get("sha256")),
                "mime_type": _text(item.get("mime_type")),
                "extraction_status": _text(item.get("extraction_status") or "pending"),
                "created_at": _text(item.get("created_at")),
            }
            for item in (_mapping(raw) for raw in _list(source.get("reference_files")))
        ]
        public["adoption"] = None
        return public

    def summary(self, value: Any) -> dict[str, Any]:
        """Project a repository record into a browser-visible list item."""

        source = _mapping(value)
        public: dict[str, Any] = {}
        for key in ("id", "owner_user_id"):
            if key in source:
                public[key] = _optional_int(source.get(key))
        for key in ("name", "script_type", "updated_at", "adopted_kind", "adopted_title"):
            if key in source:
                public[key] = _text(source.get(key))
        return public


__all__ = ["ProjectProjection"]
