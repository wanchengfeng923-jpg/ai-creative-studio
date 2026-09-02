"""Reusable validation schemas for creative model outputs."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .carousel import CarouselValidationError, normalize_visual_carousel_frames


class SchemaValidationError(ValueError):
    pass


_URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)


def _as_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(f"{label} must be a mapping")
    return value


def _text(value: Any, *, label: str, reject_urls: bool = False) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{label} must be a string")
    text = value.strip()
    if not text:
        raise SchemaValidationError(f"{label} cannot be blank")
    if reject_urls and _URL_PATTERN.search(text):
        raise SchemaValidationError(f"{label} cannot contain URLs")
    return text


def _text_list(
    value: Any,
    *,
    label: str,
    size: int | None = None,
    reject_urls: bool = False,
    non_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{label} must be a list")
    if non_empty and not value:
        raise SchemaValidationError(f"{label} cannot be empty")
    if size is not None and len(value) != size:
        raise SchemaValidationError(f"{label} must contain exactly {size} items")
    return tuple(
        _text(item, label=f"{label}[{index}]", reject_urls=reject_urls)
        for index, item in enumerate(value)
    )


@dataclass(frozen=True)
class NarrativeHook:
    text: str
    scenes: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeStory:
    story: str
    hooks: tuple[NarrativeHook, ...]


@dataclass(frozen=True)
class NarrativeRecommendation:
    items: tuple[NarrativeStory, ...]


class NarrativeRecommendationSchema:
    story_count = 5
    hook_count = 2
    scene_count = 3

    @classmethod
    def validate(cls, value: Any) -> NarrativeRecommendation:
        items = value
        if isinstance(value, Mapping):
            items = value.get("items", value)
        if not isinstance(items, list):
            raise SchemaValidationError("narrative recommendation must be a list of stories")
        if len(items) != cls.story_count:
            raise SchemaValidationError(f"narrative recommendation must contain exactly {cls.story_count} stories")

        stories: list[NarrativeStory] = []
        for index, item in enumerate(items):
            story_data = _as_mapping(item, label=f"items[{index}]")
            story = _text(story_data.get("story"), label=f"items[{index}].story")
            hooks_value = story_data.get("hooks")
            if not isinstance(hooks_value, list) or len(hooks_value) != cls.hook_count:
                raise SchemaValidationError(f"items[{index}].hooks must contain exactly {cls.hook_count} hooks")
            hooks: list[NarrativeHook] = []
            for hook_index, hook in enumerate(hooks_value):
                hook_data = _as_mapping(hook, label=f"items[{index}].hooks[{hook_index}]")
                text = _text(hook_data.get("text"), label=f"items[{index}].hooks[{hook_index}].text")
                scenes = _text_list(
                    hook_data.get("scenes"),
                    label=f"items[{index}].hooks[{hook_index}].scenes",
                    size=cls.scene_count,
                )
                hooks.append(NarrativeHook(text=text, scenes=scenes))
            stories.append(NarrativeStory(story=story, hooks=tuple(hooks)))
        return NarrativeRecommendation(items=tuple(stories))


@dataclass(frozen=True)
class CarouselFrame:
    index: int
    display_description: str


@dataclass(frozen=True)
class CarouselRecommendation:
    count: int
    form: tuple[str, ...]
    frames: tuple[CarouselFrame, ...]


class CarouselRecommendationSchema:
    @classmethod
    def validate(cls, value: Any) -> CarouselRecommendation:
        data = _as_mapping(value, label="carousel recommendation")
        try:
            normalized = normalize_visual_carousel_frames(data)
        except CarouselValidationError as exc:
            raise SchemaValidationError(str(exc)) from exc

        form = tuple(str(item).strip() for item in normalized.get("form", []) if str(item).strip())
        frames = tuple(
            CarouselFrame(
                index=int(frame["index"]),
                display_description=_text(frame["display_description"], label=f"frames[{index}].display_description"),
            )
            for index, frame in enumerate(normalized.get("frames", []))
        )
        return CarouselRecommendation(count=int(normalized["count"]), form=form, frames=frames)


@dataclass(frozen=True)
class VisualCreativeItem:
    title: str
    subtitle: str
    creative_description: str
    core_subject: str
    layout: str
    visual_style: str
    content_extensions: tuple[str, ...]
    reference_sources: tuple[tuple[str, str], ...]
    keywords: tuple[str, ...]
    image_prompt: str
    carousel: CarouselRecommendation | None = None


@dataclass(frozen=True)
class VisualRecommendation:
    items: tuple[VisualCreativeItem, ...]


class VisualRecommendationSchema:
    item_count = 3

    @classmethod
    def validate(cls, value: Any) -> VisualRecommendation:
        data = _as_mapping(value, label="visual recommendation")
        items = data.get("items")
        if not isinstance(items, list) or len(items) != cls.item_count:
            raise SchemaValidationError(f"visual recommendation must contain exactly {cls.item_count} items")

        normalized_items: list[VisualCreativeItem] = []
        for index, item in enumerate(items):
            item_data = _as_mapping(item, label=f"items[{index}]")
            title = _text(item_data.get("title"), label=f"items[{index}].title", reject_urls=True)
            subtitle = _text(item_data.get("subtitle"), label=f"items[{index}].subtitle", reject_urls=True)
            creative_description = _text(
                item_data.get("creative_description"),
                label=f"items[{index}].creative_description",
                reject_urls=True,
            )
            core_subject = _text(
                item_data.get("core_subject"),
                label=f"items[{index}].core_subject",
                reject_urls=True,
            )
            layout = _text(item_data.get("layout"), label=f"items[{index}].layout", reject_urls=True)
            visual_style = _text(
                item_data.get("visual_style"),
                label=f"items[{index}].visual_style",
                reject_urls=True,
            )
            content_extensions = _text_list(
                item_data.get("content_extensions"),
                label=f"items[{index}].content_extensions",
                reject_urls=True,
                non_empty=True,
            )
            reference_sources = item_data.get("reference_sources")
            if not isinstance(reference_sources, list) or not reference_sources:
                raise SchemaValidationError(f"items[{index}].reference_sources must be a non-empty list")
            cleaned_sources: list[tuple[str, str]] = []
            for source_index, source in enumerate(reference_sources):
                source_data = _as_mapping(source, label=f"items[{index}].reference_sources[{source_index}]")
                if set(source_data) != {"name", "note"}:
                    raise SchemaValidationError(
                        f"items[{index}].reference_sources[{source_index}] must contain only name and note"
                    )
                cleaned_sources.append(
                    (
                        _text(
                            source_data.get("name"),
                            label=f"items[{index}].reference_sources[{source_index}].name",
                            reject_urls=True,
                        ),
                        _text(
                            source_data.get("note"),
                            label=f"items[{index}].reference_sources[{source_index}].note",
                            reject_urls=True,
                        ),
                    )
                )
            keywords = _text_list(
                item_data.get("keywords"),
                label=f"items[{index}].keywords",
                reject_urls=True,
                non_empty=True,
            )
            image_prompt = _text(
                item_data.get("image_prompt"),
                label=f"items[{index}].image_prompt",
                reject_urls=True,
            )
            carousel_value = item_data.get("carousel")
            if carousel_value is None:
                raise SchemaValidationError(f"items[{index}].carousel must be provided")
            carousel = CarouselRecommendationSchema.validate(carousel_value)
            normalized_items.append(
                VisualCreativeItem(
                    title=title,
                    subtitle=subtitle,
                    creative_description=creative_description,
                    core_subject=core_subject,
                    layout=layout,
                    visual_style=visual_style,
                    content_extensions=content_extensions,
                    reference_sources=tuple(cleaned_sources),
                    keywords=keywords,
                    image_prompt=image_prompt,
                    carousel=carousel,
                )
            )
        return VisualRecommendation(items=tuple(normalized_items))


__all__ = [
    "CarouselFrame",
    "CarouselRecommendation",
    "CarouselRecommendationSchema",
    "NarrativeHook",
    "NarrativeRecommendation",
    "NarrativeRecommendationSchema",
    "SchemaValidationError",
    "VisualCreativeItem",
    "VisualRecommendation",
    "VisualRecommendationSchema",
]
