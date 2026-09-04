# -*- coding: utf-8 -*-
"""AI 创意辅助的配置、请求和返回结果校验。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests

from .model_client import HttpModelClient, ModelClient, ModelRequest, ModelResponse
from .ai_service_settings import AiServiceSettings
from .ai_provider import chat_completions_url
from .carousel import CarouselValidationError, normalize_visual_carousel_config, normalize_visual_carousel_frames
from .prompting import CompiledPrompt, PromptCompilationError, compile_prompt, prompt_variable_names
from .schemas import (
    CarouselRecommendationSchema,
    NarrativeRecommendationSchema,
    SchemaValidationError,
    VisualRecommendationSchema,
)


AI_LOGGER = logging.getLogger("web_erp.http")

CREATIVE_TAG_KEYS = (
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
    # 展示类输入标签；与叙事类标签分开，避免切换模式时互相覆盖。
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
NARRATIVE_TAG_KEYS = CREATIVE_TAG_KEYS[:11]
VISUAL_TAG_KEYS = CREATIVE_TAG_KEYS[11:]
NARRATIVE_PROMPT_VARIABLES = frozenset(
    {"task_type", "task_description", "creative_tags"}
)
VISUAL_PROMPT_VARIABLES = frozenset(
    {
        "task_type",
        "task_description",
        "creative_tags",
        "aspect_ratio",
        "product_evidence_summary",
        "reference_file_names",
    }
)
AI_TASK_TYPE_MAX_LENGTH = 100
AI_TASK_DESCRIPTION_MAX_LENGTH = 1000
AI_SCRIPT_TYPE_MAX_LENGTH = 20
CREATIVE_SCRIPT_TYPES = ("叙事类", "展示类")
AI_RECOMMENDATION_NARRATIVE = "narrative"
AI_RECOMMENDATION_VISUAL = "visual"
VISUAL_CREATIVE_ITEM_FIELDS = (
    "title",
    "subtitle",
    "creative_description",
    "core_subject",
    "layout",
    "visual_style",
    "content_extensions",
    "reference_sources",
    "keywords",
    "image_prompt",
)
VISUAL_CAROUSEL_ROUND_KEYS = (
    "visual_target_audiences",
    "visual_player_desires",
    "visual_product_selling_points",
    "visual_display_contents",
    "visual_motif",
    "visual_dynamics",
)
VISUAL_BARE_DOMAIN_URL_PATTERN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d+)?(?:[/?#][^\s]*)?",
    re.IGNORECASE,
)
AI_CREATIVE_CONTINUATION_PROMPT = (
    "请基于同一任务和上一批结果，再生成5条全新的故事创意。"
    "新内容必须与上一批故事、钩子和画面建议不重复，继续严格使用上一轮相同的JSON结构，只输出JSON。"
)
AI_CREATIVE_FORMAT_REPAIR_PROMPT = (
    "上一次返回未通过格式校验。请严格重新生成并只返回合法JSON：根对象只能有items；"
    "items必须恰好包含5个故事对象；每个故事包含story和恰好2个hooks对象；"
    "每个hooks对象包含text和恰好3条scenes。不要输出解释、Markdown或其他字段。"
)
AI_VISUAL_CREATIVE_CONTINUATION_PROMPT = (
    "请基于同一展示任务和上一批结果，再生成3个全新的视觉创意方案。"
    "新方案必须与上一批不重复，继续严格使用上一轮相同的JSON结构，只输出JSON。"
)


class AiCreativeConfigurationError(ValueError):
    """AI 创意服务配置不完整或不合法。"""

    error_code = "ai_configuration_error"
    phase = "configuration"
    field_path = ""
    retryable = False


class AiCreativeRequestError(RuntimeError):
    """AI 创意服务请求失败或返回结果不符合约定。"""

    error_code = "ai_request_failed"
    phase = "model_request"
    field_path = ""
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        phase: str | None = None,
        field_path: str = "",
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = str(error_code or self.__class__.error_code)
        self.phase = str(phase or self.__class__.phase)
        self.field_path = str(field_path or "")
        self.retryable = self.__class__.retryable if retryable is None else bool(retryable)


class AiCreativeQueueTimeoutError(AiCreativeRequestError):
    """AI 网关排队或请求超时。"""

    error_code = "ai_queue_timeout"
    phase = "model_request"
    retryable = True


@dataclass(frozen=True)
class AiCreativeConfig:
    """AI 创意服务所需的服务端配置。"""

    provider: str
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float
    prompt_version: str
    prompt_template: str


@dataclass(frozen=True)
class AiCreativeGameInfo:
    """供 AI 使用的服务端筛选游戏信息摘要。"""

    version: str
    content: str


@dataclass(frozen=True)
class AiCreativeGenerationResult:
    """一次 AI 创意生成的正文、用量和性能信息。"""

    items: List[Any]
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    usage_source: str
    cost_amount: float | None
    cost_currency: str
    latency_ms: int
    conversation_id: str = ""
    assistant_message_id: str = ""
    prompt_id: str = ""
    prompt_version: str = ""
    prompt_hash: str = ""
    input_schema_version: str = ""
    output_schema_version: str = ""
    model: str = ""
    provider: str = ""

    def __iter__(self):
        """兼容旧调用方把返回值当作十条创意列表遍历。"""
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Any:
        return self.items[index]

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, AiCreativeGenerationResult):
            return (
                self.items == other.items
                and self.input_tokens == other.input_tokens
                and self.output_tokens == other.output_tokens
                and self.total_tokens == other.total_tokens
                and self.usage_source == other.usage_source
                and self.cost_amount == other.cost_amount
                and self.cost_currency == other.cost_currency
                and self.latency_ms == other.latency_ms
                and self.conversation_id == other.conversation_id
                and self.assistant_message_id == other.assistant_message_id
            )
        if isinstance(other, list):
            return self.items == other
        return NotImplemented


def _clean_text_list(value: Any) -> List[str]:
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = []
    result: List[str] = []
    seen = set()
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def normalize_creative_tags(value: Any) -> Dict[str, List[str]]:
    """只保留当前六类叙事定位、展示定位及其兼容主副选项。"""

    source = value if isinstance(value, dict) else {}
    return {key: _clean_text_list(source.get(key)) for key in CREATIVE_TAG_KEYS}


def recommendation_kind_for_script_type(script_type: str) -> str:
    """展示类任务使用视觉方案，其余类型沿用叙事方案。"""

    return (
        AI_RECOMMENDATION_VISUAL
        if str(script_type).strip() == "展示类"
        else AI_RECOMMENDATION_NARRATIVE
    )


def visual_aspect_ratio(size_requirement: str) -> str:
    """把展示素材尺寸收敛为前端支持的固定画幅。"""

    normalized = str(size_requirement or "").replace("×", "*").replace("x", "*").replace(" ", "")
    return "9:16" if normalized == "720*1280" else "16:9"


def build_creative_input_fingerprint(
    *,
    script_type: Any,
    creative_tags: Any,
    task_type: Any,
    task_description: Any,
    product_evidence_summary: Any,
    aspect_ratio: Any,
) -> str:
    """返回与当前脚本类型相关、且与标签输入顺序无关的创意请求指纹。"""

    normalized_tags = normalize_creative_tags(creative_tags)
    active_keys = VISUAL_TAG_KEYS if str(script_type or "").strip() == "展示类" else NARRATIVE_TAG_KEYS
    value = {
        "script_type": str(script_type or "").strip(),
        "creative_tags": {
            key: sorted(normalized_tags[key])
            for key in active_keys
        },
        "task_type": str(task_type or "").strip(),
        "task_description": str(task_description or "").strip(),
        "product_evidence_summary": str(product_evidence_summary or "").strip(),
        "aspect_ratio": str(aspect_ratio or "").strip(),
    }
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def format_creative_tags_for_prompt(value: Any, mode: str = "") -> str:
    """把标签候选转换成 AI 更容易理解的中文分组文本。"""

    tags = normalize_creative_tags(value)
    groups = (
        ("主目标人群", "target_audiences"),
        ("副目标人群", "secondary_target_audiences"),
        ("叙事类美术风格", "art_style"),
        ("玩家欲望候选", "player_desires"),
        ("副玩家欲望候选", "secondary_player_desires"),
        ("内容形式候选", "content_forms"),
        ("副内容形式候选", "secondary_content_forms"),
        ("开局钩子候选", "opening_hooks"),
        ("副开局钩子候选", "secondary_opening_hooks"),
        ("产品证据候选", "product_evidences"),
        ("副产品证据候选", "secondary_product_evidences"),
        ("展示类主目标用户", "visual_target_audiences"),
        ("展示类附目标用户", "visual_secondary_target_audiences"),
        ("展示类玩家欲望主选", "visual_player_desires"),
        ("展示类玩家欲望辅选", "visual_secondary_player_desires"),
        ("展示类产品卖点主选", "visual_product_selling_points"),
        ("展示类产品卖点辅选", "visual_secondary_product_selling_points"),
        ("展示类主展示内容", "visual_display_contents"),
        ("展示类辅助展示内容", "visual_secondary_display_contents"),
        ("展示类美术相关度", "visual_art_style_relevance"),
        ("展示类美术表现风格", "visual_art_style"),
        ("展示类美术参考作品", "visual_art_style_references"),
        ("展示类视觉母题", "visual_motif"),
        ("展示类动态方案", "visual_dynamics"),
        ("展示类语音钩子", "visual_voice_hook"),
        ("展示类是否轮播", "visual_carousel"),
        ("展示类轮播数量", "visual_carousel_count"),
        ("展示类轮播形式", "visual_carousel_form"),
    )
    allowed_keys = None
    if str(mode).strip() == "visual":
        allowed_keys = set(VISUAL_TAG_KEYS)
    elif str(mode).strip() == "narrative":
        allowed_keys = set(NARRATIVE_TAG_KEYS)
    lines = [
        f"{label}：{'、'.join(tags[key])}"
        for label, key in groups
        if tags[key] and (allowed_keys is None or key in allowed_keys)
    ]
    return "\n".join(lines) or "（未选择标签）"


def _bounded_context_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _clean_mapping_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return _clean_text_list([value])
    if isinstance(value, (list, tuple)):
        return _clean_text_list(value)
    return []


def _normalize_visual_carousel_request(carousel_config: Mapping[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(carousel_config, Mapping):
        return None
    source = dict(carousel_config)
    if {"enabled", "count_mode", "rounds"} & set(source):
        rounds: List[Dict[str, Any]] = []
        for item in source.get("rounds") or []:
            if not isinstance(item, Mapping):
                continue
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            overrides_source = item.get("overrides") if isinstance(item.get("overrides"), Mapping) else {}
            rounds.append(
                {
                    "index": index,
                    "mode": str(item.get("mode") or "").strip(),
                    "overrides": {
                        key: _clean_mapping_list(overrides_source.get(key))
                        for key in VISUAL_CAROUSEL_ROUND_KEYS
                    },
                }
            )
        count_value = source.get("count")
        try:
            count = int(count_value) if count_value is not None and str(count_value).strip() else None
        except (TypeError, ValueError):
            count = None
        if isinstance(count, int) and count < 2:
            count = None
        return {
            "enabled": str(source.get("enabled") or "").strip(),
            "count_mode": str(source.get("count_mode") or "").strip(),
            "count": count,
            "form": _clean_mapping_list(source.get("form")),
            "rounds": rounds,
        }
    try:
        from .carousel import normalize_visual_carousel_config

        normalized = normalize_visual_carousel_config(source)
    except Exception:
        return None
    return {
        "enabled": str(normalized.get("enabled") or "").strip(),
        "count_mode": str(normalized.get("count_mode") or "").strip(),
        "count": normalized.get("count"),
        "form": _clean_mapping_list(normalized.get("form")),
        "rounds": [
            {
                "index": int(item.get("index")),
                "mode": str(item.get("mode") or "").strip(),
                "overrides": {
                    key: _clean_mapping_list((item.get("overrides") or {}).get(key))
                    for key in VISUAL_CAROUSEL_ROUND_KEYS
                },
            }
            for item in normalized.get("rounds") or []
            if isinstance(item, Mapping)
        ],
    }


def _visual_catalog_data(tag_catalog: Mapping[str, Any] | None) -> Dict[str, Any]:
    source = tag_catalog if isinstance(tag_catalog, Mapping) else {}
    visual = source.get("visual") if isinstance(source.get("visual"), Mapping) else source
    groups = []
    if isinstance(visual, Mapping) and isinstance(visual.get("groups"), list):
        groups = visual.get("groups") or []
    elif isinstance(source.get("groups"), list):
        groups = source.get("groups") or []
    labels_by_key: Dict[str, List[str]] = {}
    ids_by_key: Dict[str, Dict[str, str]] = {}
    if groups:
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            key = str(group.get("key") or "").strip()
            if not key:
                continue
            labels: List[str] = []
            ids: Dict[str, str] = {}
            for option in group.get("options") or []:
                if not isinstance(option, Mapping):
                    continue
                label = str(option.get("label") or "").strip()
                option_id = str(option.get("id") or "").strip()
                if label and label not in labels:
                    labels.append(label)
                if label and option_id and option_id not in ids:
                    ids[option_id] = label
            labels_by_key[key] = labels
            ids_by_key[key] = ids
    else:
        for key, value in source.items():
            if isinstance(key, str) and isinstance(value, (list, tuple, str)):
                labels_by_key[key] = _clean_mapping_list(value)
    relations = {}
    relation_source = visual.get("relations") if isinstance(visual, Mapping) else source.get("relations")
    if isinstance(relation_source, Mapping):
        product_display = relation_source.get("product_display")
        if isinstance(product_display, Mapping):
            relations = {
                str(key): [str(item or "").strip() for item in value if str(item or "").strip()]
                for key, value in product_display.items()
                if isinstance(key, str) and isinstance(value, list)
            }
    return {"labels_by_key": labels_by_key, "ids_by_key": ids_by_key, "relations": relations}


def _visual_carousel_context_text(
    carousel_config: Mapping[str, Any] | None,
    tag_catalog: Mapping[str, Any] | None,
) -> str:
    config = _normalize_visual_carousel_request(carousel_config)
    if not config:
        return ""
    catalog = _visual_catalog_data(tag_catalog)
    labels_by_key = catalog["labels_by_key"]
    lines = [
        "轮播上下文：",
        f"- count_mode: {config.get('count_mode') or 'unknown'}",
    ]
    if isinstance(config.get("count"), int):
        lines.append(f"- count: {config['count']}")
    if config.get("form"):
        lines.append(f"- form: {'、'.join(config['form'])}")
    for round_item in config.get("rounds") or []:
        overrides = round_item.get("overrides") if isinstance(round_item, Mapping) else {}
        parts = [
            f"round_index={round_item.get('index')}",
            f"mode={round_item.get('mode') or 'base'}",
        ]
        for key in VISUAL_CAROUSEL_ROUND_KEYS:
            values = _clean_mapping_list((overrides or {}).get(key))
            if values:
                parts.append(f"{key}={'、'.join(values)}")
            else:
                parts.append(f"{key}=（空白可适用标签由 AI 补全）")
        lines.append("- " + "; ".join(parts))
    if labels_by_key:
        lines.append("- 有效标签目录：")
        for key in VISUAL_CAROUSEL_ROUND_KEYS:
            labels = labels_by_key.get(key) or []
            if labels:
                lines.append(f"  - {key}: {'、'.join(labels)}")
    return "\n".join(lines)


def _visual_catalog_labels_for_key(tag_catalog: Mapping[str, Any] | None, key: str) -> List[str]:
    catalog = _visual_catalog_data(tag_catalog)
    labels = catalog["labels_by_key"].get(key) or []
    return list(labels)


def _visual_label_is_allowed(tag_catalog: Mapping[str, Any] | None, key: str, label: str) -> bool:
    allowed = _visual_catalog_labels_for_key(tag_catalog, key)
    return not allowed or label in allowed


def _visual_id_lookup(tag_catalog: Mapping[str, Any] | None, key: str) -> Dict[str, str]:
    catalog = _visual_catalog_data(tag_catalog)
    return dict(catalog["ids_by_key"].get(key) or {})


def _validate_visual_text_list(value: Any, label: str, *, field_path: str) -> List[str]:
    if not isinstance(value, list) or not value:
        raise AiCreativeRequestError(
            f"AI视觉返回的{label}必须是非空列表",
            field_path=field_path,
        )
    return [
        _visual_text(item, label, field_path=f"{field_path}[{index}]")
        for index, item in enumerate(value)
    ]


def _default_game_info_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "ai_creative_game_info_v2.json"


def load_ai_creative_game_info(
    environ: Mapping[str, str] | None = None,
) -> AiCreativeGameInfo:
    """读取服务端维护的游戏信息摘要，不读取原始攻略文档。"""

    source = environ if environ is not None else os.environ
    path_text = str(source.get("WEB_ERP_AI_GAME_INFO_PATH") or "").strip()
    path = Path(path_text) if path_text else _default_game_info_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AiCreativeConfigurationError("AI游戏信息摘要不存在或无法解析") from exc
    if not isinstance(payload, dict) or set(payload) != {"version", "content"}:
        raise AiCreativeConfigurationError("AI游戏信息摘要格式无效")
    version = str(payload.get("version") or "").strip()
    content = str(payload.get("content") or "").strip()
    if not version or not content:
        raise AiCreativeConfigurationError("AI游戏信息摘要不能为空")
    if not isinstance(payload.get("version"), str) or not isinstance(payload.get("content"), str):
        raise AiCreativeConfigurationError("AI游戏信息摘要字段类型无效")
    return AiCreativeGameInfo(version=version, content=content)


def build_creative_prompt(
    tags: Dict[str, List[str]],
    prompt_template: str,
    game_info: str = "",
    task_type: str = "",
    task_description: str = "",
    script_type: str = "",
) -> str:
    """把规范化标签放入用户提供的提示词模板。"""

    template = str(prompt_template or "").strip()
    if not template:
        raise AiCreativeConfigurationError("AI提示词尚未配置")
    tags_text = format_creative_tags_for_prompt(tags, mode="narrative")
    bounded_task_type = _bounded_context_text(task_type, AI_TASK_TYPE_MAX_LENGTH)
    bounded_task_description = _bounded_context_text(task_description, AI_TASK_DESCRIPTION_MAX_LENGTH)
    raw_script_type = script_type or (tags.get("script_type") if isinstance(tags, dict) else "")
    bounded_script_type = _bounded_context_text(raw_script_type, AI_SCRIPT_TYPE_MAX_LENGTH)
    values = {
        "game_info": str(game_info or "").strip(),
        "creative_tags": tags_text,
        "task_type": bounded_task_type,
        "task_description": bounded_task_description,
        "script_type": bounded_script_type,
    }
    return _render_known_prompt(
        template,
        values,
        required_variables=NARRATIVE_PROMPT_VARIABLES,
    )


def load_ai_creative_config(
    environ: Mapping[str, str] | None = None,
    *,
    service_settings: AiServiceSettings | None = None,
) -> AiCreativeConfig:
    """从服务端环境读取 AI 创意配置，不读取浏览器传入的密钥。"""

    source = environ if environ is not None else os.environ
    configured_api_url = (
        chat_completions_url(service_settings.base_url)
        if service_settings is not None and service_settings.base_url
        else str(source.get("WEB_ERP_AI_API_URL") or "").strip()
    )
    configured_api_key = (
        service_settings.api_key
        if service_settings is not None
        else str(source.get("WEB_ERP_AI_API_KEY") or "").strip()
    )
    configured_model = (
        service_settings.model
        if service_settings is not None
        else str(source.get("WEB_ERP_AI_MODEL") or "").strip()
    )
    configured_provider = (
        service_settings.provider
        if service_settings is not None
        else str(source.get("WEB_ERP_AI_PROVIDER") or "custom").strip()
    )
    prompt_template = str(source.get("WEB_ERP_AI_PROMPT_TEMPLATE") or "").strip()
    prompt_path = str(source.get("WEB_ERP_AI_PROMPT_PATH") or "").strip()
    if not prompt_template and prompt_path:
        try:
            prompt_template = Path(prompt_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise AiCreativeConfigurationError("AI提示词文件不存在或无法读取") from exc
    required_values = (
        (configured_api_url, "AI接口地址"),
        (configured_api_key, "AI接口密钥"),
        (configured_model, "AI模型名称"),
        (prompt_template, "AI提示词"),
    )
    missing = [label for value, label in required_values if not str(value or "").strip()]
    if missing:
        raise AiCreativeConfigurationError(f"AI配置缺失：{'、'.join(missing)}")
    try:
        timeout_seconds = float(source.get("WEB_ERP_AI_TIMEOUT_SECONDS") or 30)
    except (TypeError, ValueError) as exc:
        raise AiCreativeConfigurationError("AI请求超时时间无效") from exc
    if timeout_seconds <= 0:
        raise AiCreativeConfigurationError("AI请求超时时间必须大于0")
    return AiCreativeConfig(
        provider=str(configured_provider or "custom").strip(),
        api_url=configured_api_url,
        api_key=configured_api_key,
        model=configured_model,
        timeout_seconds=timeout_seconds,
        prompt_version=str(source.get("WEB_ERP_AI_PROMPT_VERSION") or "v1").strip() or "v1",
        prompt_template=prompt_template,
    )


def _default_ai_visual_creative_prompt_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "ai_visual_creative_prompt_v2.txt"


def _default_ai_visual_carousel_prompt_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "ai_visual_carousel_prompt_v1.txt"


def load_ai_visual_creative_config(
    environ: Mapping[str, str] | None = None,
    *,
    service_settings: AiServiceSettings | None = None,
    carousel: bool = False,
) -> AiCreativeConfig:
    """加载展示类 AI 的独立提示词配置，复用同一服务商配置。"""

    source = dict(environ if environ is not None else os.environ)
    source.pop("WEB_ERP_AI_PROMPT_TEMPLATE", None)
    if carousel:
        source["WEB_ERP_AI_PROMPT_PATH"] = (
            str(source.get("WEB_ERP_AI_VISUAL_CAROUSEL_PROMPT_PATH") or "").strip()
            or str(_default_ai_visual_carousel_prompt_path())
        )
        source["WEB_ERP_AI_PROMPT_VERSION"] = (
            str(source.get("WEB_ERP_AI_VISUAL_CAROUSEL_PROMPT_VERSION") or "").strip()
            or "visual-carousel-v1"
        )
    else:
        source["WEB_ERP_AI_PROMPT_PATH"] = (
            str(source.get("WEB_ERP_AI_VISUAL_PROMPT_PATH") or "").strip()
            or str(_default_ai_visual_creative_prompt_path())
        )
        source["WEB_ERP_AI_PROMPT_VERSION"] = (
            str(source.get("WEB_ERP_AI_VISUAL_PROMPT_VERSION") or "").strip()
            or "visual-v2.3"
        )
    return load_ai_creative_config(source, service_settings=service_settings)


def build_visual_creative_prompt(
    tags: Dict[str, List[str]],
    prompt_template: str,
    *,
    task_type: str = "",
    task_description: str = "",
    aspect_ratio: str = "16:9",
    product_evidence_summary: str = "",
    reference_file_names: Any = None,
    carousel_config: Mapping[str, Any] | None = None,
    tag_catalog: Mapping[str, Any] | None = None,
) -> str:
    """以批准的展示类上下文填充视觉创意提示词。"""

    template = str(prompt_template or "").strip()
    if not template:
        raise AiCreativeConfigurationError("AI视觉提示词尚未配置")
    reference_names = "、".join(_clean_text_list(reference_file_names)) or "（无参考文件）"
    carousel_context = _visual_carousel_context_text(carousel_config, tag_catalog)
    values = {
        "task_type": _bounded_context_text(task_type, AI_TASK_TYPE_MAX_LENGTH),
        "task_description": _bounded_context_text(task_description, AI_TASK_DESCRIPTION_MAX_LENGTH),
        "creative_tags": format_creative_tags_for_prompt(tags, mode="visual"),
        "aspect_ratio": str(aspect_ratio or "").strip() or "16:9",
        "product_evidence_summary": str(product_evidence_summary or "").strip(),
        "reference_file_names": reference_names,
        "carousel_context": carousel_context,
    }
    required_variables = set(VISUAL_PROMPT_VARIABLES)
    if carousel_context:
        required_variables.add("carousel_context")
    return _render_known_prompt(
        template,
        values,
        required_variables=required_variables,
    )


def _render_known_prompt(
    template: str,
    values: Mapping[str, Any],
    *,
    required_variables: Any,
) -> str:
    """Compile an existing prompt while rejecting undeclared placeholder names."""

    declared = prompt_variable_names(template)
    missing = sorted(set(required_variables) - declared)
    if missing:
        raise AiCreativeConfigurationError(
            f"AI提示词缺失变量：{', '.join(missing)}"
        )
    unsupported = sorted(declared - set(values))
    if unsupported:
        raise AiCreativeConfigurationError(
            f"AI提示词包含未知变量：{', '.join(unsupported)}"
        )
    try:
        return compile_prompt(
            template,
            {name: values[name] for name in declared},
        ).render()
    except PromptCompilationError as exc:
        raise AiCreativeConfigurationError(str(exc)) from exc


def _parse_json_object_text(value: str) -> Dict[str, Any]:
    """解析严格 JSON，或从模型附加说明中提取首个完整 JSON 对象。"""

    text = str(value or "").strip()
    if not text:
        raise AiCreativeRequestError("AI返回结果无法解析", field_path="$")
    try:
        payload = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        decoder = json.JSONDecoder()
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise AiCreativeRequestError("AI返回结果无法解析", field_path="$")
    if not isinstance(payload, dict):
        raise AiCreativeRequestError("AI返回结果无法解析", field_path="$")
    return payload


def _recommendation_payload(value: Any) -> Any:
    if isinstance(value, dict) and "items" in value:
        return value["items"]
    if isinstance(value, str):
        return _recommendation_payload(_parse_json_object_text(value))
    if isinstance(value, dict) and "choices" in value:
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AiCreativeRequestError("AI返回结果缺少choices", field_path="choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict) or "content" not in message:
            raise AiCreativeRequestError(
                "AI返回结果缺少正文",
                field_path="choices[0].message.content",
            )
        return _recommendation_payload(message["content"])
    return value


def validate_creative_recommendations(value: Any) -> List[Dict[str, Any]]:
    """验证 AI 返回值必须满足 5 个故事、每故事 2 个钩子、每钩子 3 个画面。"""

    items = _recommendation_payload(value)
    if not isinstance(items, list) or len(items) != 5:
        raise AiCreativeRequestError("items 必须正好包含5个故事", field_path="items")
    result: List[Dict[str, Any]] = []
    for item_index, item in enumerate(items):
        item_path = f"items[{item_index}]"
        if not isinstance(item, dict):
            raise AiCreativeRequestError(
                f"{item_path} 必须是对象",
                field_path=item_path,
            )
        story = str(item.get("story") or "").strip()
        if not story or "\n" in story or "\r" in story:
            raise AiCreativeRequestError(
                f"{item_path}.story 必须是非空单行文本",
                field_path=f"{item_path}.story",
            )
        hooks = item.get("hooks")
        if not isinstance(hooks, list) or len(hooks) != 2:
            raise AiCreativeRequestError(
                f"{item_path}.hooks 必须恰好包含2个钩子",
                field_path=f"{item_path}.hooks",
            )
        clean_hooks: List[Dict[str, Any]] = []
        for hook_index, hook in enumerate(hooks):
            hook_path = f"{item_path}.hooks[{hook_index}]"
            if not isinstance(hook, dict):
                raise AiCreativeRequestError(
                    f"{hook_path} 必须是对象",
                    field_path=hook_path,
                )
            text = str(hook.get("text") or "").strip()
            if not text or "\n" in text or "\r" in text:
                raise AiCreativeRequestError(
                    f"{hook_path}.text 必须是非空单行文本",
                    field_path=f"{hook_path}.text",
                )
            scenes = hook.get("scenes")
            if not isinstance(scenes, list) or len(scenes) != 3:
                raise AiCreativeRequestError(
                    f"{hook_path}.scenes 必须恰好包含3个画面建议",
                    field_path=f"{hook_path}.scenes",
                )
            clean_scenes: List[str] = []
            for scene_index, scene in enumerate(scenes):
                scene_path = f"{hook_path}.scenes[{scene_index}]"
                scene_text = str(scene or "").strip()
                if (
                    not scene_text
                    or "\n" in scene_text
                    or "\r" in scene_text
                    or len(scene_text) > 80
                ):
                    raise AiCreativeRequestError(
                        f"{scene_path} 必须是非空单行文本且不超过80个字符",
                        field_path=scene_path,
                    )
                clean_scenes.append(scene_text)
            clean_hooks.append({"text": text, "scenes": clean_scenes})
        result.append({"story": story, "hooks": clean_hooks})
    return result


def _visual_recommendation_payload(value: Any) -> Any:
    if isinstance(value, str):
        return _visual_recommendation_payload(_parse_json_object_text(value))
    if isinstance(value, dict) and "choices" in value:
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AiCreativeRequestError("AI返回结果缺少choices", field_path="choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict) or "content" not in message:
            raise AiCreativeRequestError(
                "AI返回结果缺少正文",
                field_path="choices[0].message.content",
            )
        return _visual_recommendation_payload(message["content"])
    if not isinstance(value, dict) or set(value) != {"items"}:
        raise AiCreativeRequestError(
            "AI视觉返回结果必须只有items字段",
            field_path="items",
        )
    return value["items"]


def _visual_text(value: Any, label: str, *, field_path: str = "") -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise AiCreativeRequestError(
            f"AI视觉返回的{label}不能为空",
            field_path=field_path or label,
        )
    if "://" in text.lower() or VISUAL_BARE_DOMAIN_URL_PATTERN.search(text):
        raise AiCreativeRequestError(
            f"AI视觉返回的{label}不能包含网址",
            field_path=field_path or label,
        )
    return text


def _visual_text_list(value: Any, label: str) -> List[str]:
    if not isinstance(value, list) or not value:
        raise AiCreativeRequestError(
            f"AI视觉返回的{label}必须是非空列表",
            field_path=label,
        )
    return [
        _visual_text(item, label, field_path=f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def validate_visual_creative_recommendations(
    value: Any,
    *,
    carousel_config: Mapping[str, Any] | None = None,
    tag_catalog: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """严格验证展示类视觉创意的三项完整 schema。"""

    config = _normalize_visual_carousel_request(carousel_config)
    items = _visual_recommendation_payload(value)
    if not isinstance(items, list) or len(items) != 3:
        raise AiCreativeRequestError(
            "AI视觉返回结果必须正好包含3个方案",
            field_path="items",
        )

    # 新展示流程的首帧 schema；保留下面旧 schema 分支以兼容历史批次。
    if any(isinstance(item, Mapping) and "first_frame" in item for item in items):
        result: List[Dict[str, Any]] = []
        mode = str((config or {}).get("count_mode") or "none").strip().lower()
        requested = (config or {}).get("count")
        for item_index, item in enumerate(items):
            item_path = f"items[{item_index}]"
            if not isinstance(item, Mapping):
                raise AiCreativeRequestError(
                    f"AI视觉第{item_index + 1}个方案格式无效",
                    field_path=item_path,
                )
            allowed = {
                "title", "creative_summary", "creative_sources", "frame_count",
                "visual_continuity_rules", "frame_plan", "first_frame",
            }
            if set(item) != allowed:
                raise AiCreativeRequestError(
                    "AI视觉首帧方案字段结构无效",
                    field_path=item_path,
                )
            title = _visual_text(
                item.get("title"),
                "title",
                field_path=f"{item_path}.title",
            )
            summary = _visual_text(
                item.get("creative_summary"),
                "creative_summary",
                field_path=f"{item_path}.creative_summary",
            )
            sources = _validate_visual_text_list(
                item.get("creative_sources"),
                "creative_sources",
                field_path=f"{item_path}.creative_sources",
            )
            continuity = _validate_visual_text_list(
                item.get("visual_continuity_rules"),
                "visual_continuity_rules",
                field_path=f"{item_path}.visual_continuity_rules",
            )
            try:
                frame_count = int(item.get("frame_count") or 0)
            except (TypeError, ValueError) as exc:
                raise AiCreativeRequestError(
                    "frame_count必须是整数",
                    field_path=f"{item_path}.frame_count",
                ) from exc
            if mode == "none":
                if frame_count != 1:
                    raise AiCreativeRequestError(
                        "不轮播方案的frame_count必须为1",
                        field_path=f"{item_path}.frame_count",
                    )
            elif mode == "fixed":
                if not isinstance(requested, int) or frame_count != requested or frame_count not in range(2, 6):
                    raise AiCreativeRequestError(
                        "固定轮播方案的frame_count必须等于用户指定数量",
                        field_path=f"{item_path}.frame_count",
                    )
            elif mode == "ai":
                if frame_count not in range(2, 6):
                    raise AiCreativeRequestError(
                        "AI决定的frame_count必须为2至5",
                        field_path=f"{item_path}.frame_count",
                    )
            else:
                raise AiCreativeRequestError(
                    "AI视觉轮播配置无效",
                    field_path="carousel_config.count_mode",
                )
            raw_plan = item.get("frame_plan")
            if not isinstance(raw_plan, list) or len(raw_plan) != frame_count:
                raise AiCreativeRequestError(
                    "frame_plan必须完整覆盖frame_count",
                    field_path=f"{item_path}.frame_plan",
                )
            plan: List[Dict[str, Any]] = []
            for frame_offset, raw_frame in enumerate(raw_plan):
                expected_index = frame_offset + 1
                frame_path = f"{item_path}.frame_plan[{frame_offset}]"
                if not isinstance(raw_frame, Mapping) or set(raw_frame) != {"index", "description"}:
                    raise AiCreativeRequestError(
                        "frame_plan字段结构无效",
                        field_path=frame_path,
                    )
                try:
                    actual_index = int(raw_frame.get("index") or 0)
                except (TypeError, ValueError) as exc:
                    raise AiCreativeRequestError(
                        "frame_plan序号必须是整数",
                        field_path=f"{frame_path}.index",
                    ) from exc
                if actual_index != expected_index:
                    raise AiCreativeRequestError(
                        "frame_plan序号必须从1连续递增",
                        field_path=f"{frame_path}.index",
                    )
                plan.append(
                    {
                        "index": expected_index,
                        "description": _visual_text(
                            raw_frame.get("description"),
                            "frame_plan.description",
                            field_path=f"{frame_path}.description",
                        ),
                    }
                )
            first = item.get("first_frame")
            if not isinstance(first, Mapping) or set(first) != {"index", "content", "image_generation_instruction"}:
                raise AiCreativeRequestError(
                    "first_frame字段结构无效",
                    field_path=f"{item_path}.first_frame",
                )
            try:
                first_index = int(first.get("index") or 0)
            except (TypeError, ValueError) as exc:
                raise AiCreativeRequestError(
                    "first_frame.index必须是整数",
                    field_path=f"{item_path}.first_frame.index",
                ) from exc
            if first_index != 1:
                raise AiCreativeRequestError(
                    "first_frame.index必须为1",
                    field_path=f"{item_path}.first_frame.index",
                )
            first_content = _visual_text(
                first.get("content"),
                "first_frame.content",
                field_path=f"{item_path}.first_frame.content",
            )
            image_instruction = _visual_text(
                first.get("image_generation_instruction"),
                "first_frame.image_generation_instruction",
                field_path=f"{item_path}.first_frame.image_generation_instruction",
            )
            result.append({
                "title": title,
                "subtitle": first_content,
                "creative_description": summary,
                "core_subject": first_content,
                "layout": first_content,
                "visual_style": "；".join(continuity),
                "content_extensions": [frame["description"] for frame in plan[1:]] or [first_content],
                "reference_sources": [{"name": source, "note": "模型提供的创意来源"} for source in sources],
                "keywords": ["展示类", "连续画面"],
                "image_prompt": image_instruction,
                "creative_summary": summary,
                "creative_sources": sources,
                "frame_count": frame_count,
                "visual_continuity_rules": continuity,
                "frame_plan": plan,
                "first_frame": {
                    "index": 1,
                    "content": first_content,
                    "image_generation_instruction": image_instruction,
                },
            })
        return result
    if not config:
        result: List[Dict[str, Any]] = []
        text_fields = (
            "title",
            "subtitle",
            "creative_description",
            "core_subject",
            "layout",
            "visual_style",
            "image_prompt",
        )
        for item_index, item in enumerate(items):
            item_path = f"items[{item_index}]"
            if not isinstance(item, dict) or set(item) != set(VISUAL_CREATIVE_ITEM_FIELDS):
                raise AiCreativeRequestError(
                    "AI视觉返回的每个方案必须符合批准字段结构",
                    field_path=item_path,
                )
            cleaned = {
                field: _visual_text(
                    item.get(field),
                    field,
                    field_path=f"{item_path}.{field}",
                )
                for field in text_fields
            }
            cleaned["content_extensions"] = _validate_visual_text_list(
                item.get("content_extensions"),
                "content_extensions",
                field_path=f"{item_path}.content_extensions",
            )
            cleaned["keywords"] = _validate_visual_text_list(
                item.get("keywords"),
                "keywords",
                field_path=f"{item_path}.keywords",
            )
            sources = item.get("reference_sources")
            if not isinstance(sources, list) or not sources:
                raise AiCreativeRequestError(
                    "AI视觉返回的reference_sources必须是非空列表",
                    field_path=f"{item_path}.reference_sources",
                )
            cleaned_sources: List[Dict[str, str]] = []
            for source_index, source in enumerate(sources):
                source_path = f"{item_path}.reference_sources[{source_index}]"
                if not isinstance(source, dict) or set(source) != {"name", "note"}:
                    raise AiCreativeRequestError(
                        "AI视觉返回的参考来源只能包含name和note",
                        field_path=source_path,
                    )
                cleaned_sources.append({
                    "name": _visual_text(
                        source.get("name"),
                        "reference_sources.name",
                        field_path=f"{source_path}.name",
                    ),
                    "note": _visual_text(
                        source.get("note"),
                        "reference_sources.note",
                        field_path=f"{source_path}.note",
                    ),
                })
            cleaned["reference_sources"] = cleaned_sources
            result.append({field: cleaned[field] for field in VISUAL_CREATIVE_ITEM_FIELDS})
        return result

    if str(config.get("count_mode") or "").strip() == "fixed":
        count = config.get("count")
        if not isinstance(count, int) or not 2 <= count <= 5:
            raise AiCreativeRequestError(
                "AI视觉轮播固定数量必须在2到5之间",
                field_path="carousel_config.count",
            )
    elif str(config.get("count_mode") or "").strip() == "ai":
        count = config.get("count")
        if count is not None and (not isinstance(count, int) or not 2 <= count <= 5):
            raise AiCreativeRequestError(
                "AI视觉轮播数量必须在2到5之间",
                field_path="carousel_config.count",
            )
    else:
        raise AiCreativeRequestError(
            "AI视觉轮播配置无效",
            field_path="carousel_config.count_mode",
        )

    result = []
    required_fields = set(VISUAL_CREATIVE_ITEM_FIELDS) | {"carousel"}
    for item_index, item in enumerate(items):
        item_path = f"items[{item_index}]"
        if not isinstance(item, dict) or set(item) != required_fields:
            raise AiCreativeRequestError(
                "AI视觉返回的每个方案必须符合批准字段结构",
                field_path=item_path,
            )
        cleaned = {
            field: _visual_text(
                item.get(field),
                field,
                field_path=f"{item_path}.{field}",
            )
            for field in (
                "title",
                "subtitle",
                "creative_description",
                "core_subject",
                "layout",
                "visual_style",
                "image_prompt",
            )
        }
        cleaned["content_extensions"] = _validate_visual_text_list(
            item.get("content_extensions"),
            "content_extensions",
            field_path=f"{item_path}.content_extensions",
        )
        cleaned["keywords"] = _validate_visual_text_list(
            item.get("keywords"),
            "keywords",
            field_path=f"{item_path}.keywords",
        )
        sources = item.get("reference_sources")
        if not isinstance(sources, list) or not sources:
            raise AiCreativeRequestError(
                "AI视觉返回的reference_sources必须是非空列表",
                field_path=f"{item_path}.reference_sources",
            )
        cleaned_sources: List[Dict[str, str]] = []
        for source_index, source in enumerate(sources):
            source_path = f"{item_path}.reference_sources[{source_index}]"
            if not isinstance(source, dict) or set(source) != {"name", "note"}:
                raise AiCreativeRequestError(
                    "AI视觉返回的参考来源只能包含name和note",
                    field_path=source_path,
                )
            cleaned_sources.append({
                "name": _visual_text(
                    source.get("name"),
                    "reference_sources.name",
                    field_path=f"{source_path}.name",
                ),
                "note": _visual_text(
                    source.get("note"),
                    "reference_sources.note",
                    field_path=f"{source_path}.note",
                ),
            })
        cleaned["reference_sources"] = cleaned_sources
        try:
            clean_carousel = normalize_visual_carousel_frames(item.get("carousel"))
        except CarouselValidationError as exc:
            relative_path = str(getattr(exc, "field_path", "") or "carousel")
            raise AiCreativeRequestError(
                str(exc),
                field_path=f"{item_path}.{relative_path}",
            ) from exc
        carousel_count = int(clean_carousel["count"])
        if str(config.get("count_mode") or "").strip() == "fixed":
            expected_count = int(config["count"])
            if carousel_count != expected_count:
                raise AiCreativeRequestError(
                    "AI视觉返回的carousel.count必须与固定屏数一致",
                    field_path=f"{item_path}.carousel.count",
                )
        cleaned["carousel"] = clean_carousel
        result.append({
            field: cleaned[field] for field in VISUAL_CREATIVE_ITEM_FIELDS
        } | {
            "carousel": clean_carousel,
            "carousel_frames": [frame["index"] for frame in clean_carousel["frames"]],
        })
    return result


def public_visual_creative_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    """返回可对普通用户公开的视觉创意项，不暴露生图提示词。"""

    public_item = dict(item)
    public_item.pop("image_prompt", None)
    return public_item


def generate_visual_creative_recommendations(
    tags: Dict[str, List[str]],
    *,
    config: AiCreativeConfig,
    task_type: str = "",
    task_description: str = "",
    aspect_ratio: str = "16:9",
    product_evidence_summary: str = "",
    reference_file_names: Any = None,
    carousel_config: Mapping[str, Any] | None = None,
    tag_catalog: Mapping[str, Any] | None = None,
    conversation_id: str = "",
    parent_message_id: str = "",
    continuation_prompt: str = "",
    transport: Callable[..., Any] = requests.post,
) -> AiCreativeGenerationResult:
    """调用已配置的 AI 服务生成三项展示类视觉创意。"""

    conversation_id = str(conversation_id or "").strip()
    parent_message_id = str(parent_message_id or "").strip()
    if bool(conversation_id) != bool(parent_message_id):
        raise AiCreativeRequestError("AI续聊标识必须同时提供")
    if conversation_id:
        prompt = str(continuation_prompt or AI_VISUAL_CREATIVE_CONTINUATION_PROMPT).strip()
    else:
        prompt = build_visual_creative_prompt(
            tags,
            config.prompt_template,
            task_type=task_type,
            task_description=task_description,
            aspect_ratio=aspect_ratio,
            product_evidence_summary=product_evidence_summary,
            reference_file_names=reference_file_names,
            carousel_config=carousel_config,
            tag_catalog=tag_catalog,
        )
    payload = {
        "model": config.model,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 5000,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
        payload["parent_message_id"] = parent_message_id
    started_at = time.perf_counter()
    response_payload: Any = None
    items: List[Dict[str, Any]] | None = None
    attempt_limit = 1 if _normalize_visual_carousel_request(carousel_config) else 2
    for attempt in range(1, attempt_limit + 1):
        try:
            response = transport(
                config.api_url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise AiCreativeQueueTimeoutError("AI排队超时") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f"（HTTP {status}，请检查 AI 网关会话）" if status else "，请检查 AI 网关是否运行"
            raise AiCreativeRequestError(f"AI接口请求失败{suffix}") from exc
        try:
            response_payload = response.json()
            items = validate_visual_creative_recommendations(
                response_payload,
                carousel_config=carousel_config,
                tag_catalog=tag_catalog,
            )
            response_conversation_id = str(
                response_payload.get("conversation_id") or ""
            ).strip() if isinstance(response_payload, dict) else ""
            response_assistant_message_id = str(
                response_payload.get("assistant_message_id") or ""
            ).strip() if isinstance(response_payload, dict) else ""
            if config.provider == "chatgpt-web" and (
                not response_conversation_id or not response_assistant_message_id
            ):
                raise AiCreativeRequestError(
                    "AI会话标识缺失，无法继续生成",
                    field_path=(
                        "conversation_id"
                        if not response_conversation_id
                        else "assistant_message_id"
                    ),
                )
            _log_ai_response_diagnostics(config, response_payload, attempt=attempt, outcome="success")
            break
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            _log_ai_response_diagnostics(config, None, attempt=attempt, outcome="response_json_error")
            if attempt == attempt_limit:
                raise AiCreativeRequestError(
                    "AI接口返回内容无法解析",
                    field_path="$",
                ) from exc
        except AiCreativeRequestError:
            _log_ai_response_diagnostics(config, response_payload, attempt=attempt, outcome="format_error")
            if attempt == attempt_limit:
                raise
    if items is None:
        raise AiCreativeRequestError("AI返回结果无法解析", field_path="$")
    latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    input_tokens, output_tokens, total_tokens = _extract_token_usage(response_payload)
    usage_source = "exact"
    if input_tokens is None and output_tokens is None and total_tokens is None:
        input_tokens, output_tokens, total_tokens = estimate_creative_request_tokens(prompt, items)
        usage_source = "estimated" if total_tokens is not None else "unavailable"
    return AiCreativeGenerationResult(
        items=items,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        usage_source=usage_source,
        cost_amount=None,
        cost_currency="",
        latency_ms=latency_ms,
        conversation_id=str(
            response_payload.get("conversation_id") or ""
        ).strip() if isinstance(response_payload, dict) else "",
        assistant_message_id=str(
            response_payload.get("assistant_message_id") or ""
        ).strip() if isinstance(response_payload, dict) else "",
    )


def generate_creative_recommendations(
    tags: Dict[str, List[str]],
    *,
    config: AiCreativeConfig,
    game_info: str = "",
    task_type: str = "",
    task_description: str = "",
    script_type: str = "",
    conversation_id: str = "",
    parent_message_id: str = "",
    continuation_prompt: str = "",
    transport: Callable[..., Any] = requests.post,
) -> AiCreativeGenerationResult:
    """调用已配置的 AI 服务并返回创意、token 用量与耗时。"""

    conversation_id = str(conversation_id or "").strip()
    parent_message_id = str(parent_message_id or "").strip()
    if bool(conversation_id) != bool(parent_message_id):
        raise AiCreativeRequestError("AI续聊标识必须同时提供")
    if conversation_id:
        prompt = str(continuation_prompt or AI_CREATIVE_CONTINUATION_PROMPT).strip()
    else:
        prompt = build_creative_prompt(
            tags,
            config.prompt_template,
            game_info=game_info,
            task_type=task_type,
            task_description=task_description,
            script_type=script_type,
        )
    payload = {
        "model": config.model,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
        # 叙事结构包含 5 个故事、10 个钩子和 30 个画面建议，需要更大的输出预算。
        "max_tokens": 10000,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
        payload["parent_message_id"] = parent_message_id
    started_at = time.perf_counter()
    response_payload: Any = None
    items: List[Dict[str, Any]] | None = None
    for attempt in range(1, 3):
        try:
            request_payload = payload
            if attempt == 2 and not conversation_id:
                request_payload = dict(payload)
                request_payload["messages"] = [
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n{AI_CREATIVE_FORMAT_REPAIR_PROMPT}",
                    }
                ]
            response = transport(
                config.api_url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise AiCreativeQueueTimeoutError("AI排队超时") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f"（HTTP {status}，请检查 AI 网关会话）" if status else "，请检查 AI 网关是否运行"
            raise AiCreativeRequestError(f"AI接口请求失败{suffix}") from exc
        try:
            response_payload = response.json()
            items = validate_creative_recommendations(response_payload)
            response_conversation_id = str(
                response_payload.get("conversation_id") or ""
            ).strip() if isinstance(response_payload, dict) else ""
            response_assistant_message_id = str(
                response_payload.get("assistant_message_id") or ""
            ).strip() if isinstance(response_payload, dict) else ""
            if config.provider == "chatgpt-web" and (
                not response_conversation_id or not response_assistant_message_id
            ):
                raise AiCreativeRequestError(
                    "AI会话标识缺失，无法继续生成",
                    field_path=(
                        "conversation_id"
                        if not response_conversation_id
                        else "assistant_message_id"
                    ),
                )
            _log_ai_response_diagnostics(
                config,
                response_payload,
                attempt=attempt,
                outcome="success",
            )
            break
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            _log_ai_response_diagnostics(
                config,
                None,
                attempt=attempt,
                outcome="response_json_error",
            )
            if attempt == 2:
                raise AiCreativeRequestError(
                    "AI接口返回内容无法解析",
                    field_path="$",
                ) from exc
        except AiCreativeRequestError:
            _log_ai_response_diagnostics(
                config,
                response_payload,
                attempt=attempt,
                outcome="format_error",
            )
            if attempt == 2:
                raise
    if items is None:
        raise AiCreativeRequestError("AI返回结果无法解析", field_path="$")
    latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    input_tokens, output_tokens, total_tokens = _extract_token_usage(response_payload)
    usage_source = "exact"
    if input_tokens is None and output_tokens is None and total_tokens is None:
        input_tokens, output_tokens, total_tokens = estimate_creative_request_tokens(prompt, items)
        usage_source = "estimated" if total_tokens is not None else "unavailable"
    return AiCreativeGenerationResult(
        items=items,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        usage_source=usage_source,
        cost_amount=None,
        cost_currency="",
        latency_ms=latency_ms,
        conversation_id=str(
            response_payload.get("conversation_id") or ""
        ).strip() if isinstance(response_payload, dict) else "",
        assistant_message_id=str(
            response_payload.get("assistant_message_id") or ""
        ).strip() if isinstance(response_payload, dict) else "",
    )


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _extract_token_usage(payload: Any) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None, None, None
    input_tokens = _optional_nonnegative_int(usage.get("prompt_tokens", usage.get("input_tokens")))
    output_tokens = _optional_nonnegative_int(usage.get("completion_tokens", usage.get("output_tokens")))
    total_tokens = _optional_nonnegative_int(usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _response_diagnostics(payload: Any) -> Dict[str, Any]:
    """只提取响应结构信息，避免把模型正文或推理内容写入日志。"""

    choices = payload.get("choices") if isinstance(payload, dict) else None
    first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    content_text = content if isinstance(content, str) else ""
    reasoning = message.get("reasoning")
    if reasoning is None:
        reasoning = message.get("reasoning_content")
    input_tokens, output_tokens, total_tokens = _extract_token_usage(payload)
    return {
        "finish_reason": str(first.get("finish_reason") or ""),
        "content_empty": not bool(content_text.strip()),
        "content_length": len(content_text),
        "reasoning_present": bool(reasoning),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _log_ai_response_diagnostics(
    config: AiCreativeConfig,
    payload: Any,
    *,
    attempt: int,
    outcome: str,
) -> None:
    """记录可排错但不含正文、提示词、标签或密钥的响应元数据。"""

    diagnostics = _response_diagnostics(payload)
    AI_LOGGER.info(
        "ai_creative_response model=%s prompt_version=%s attempt=%d outcome=%s "
        "finish_reason=%s content_empty=%s content_length=%d reasoning_present=%s "
        "input_tokens=%s output_tokens=%s total_tokens=%s",
        config.model,
        config.prompt_version,
        attempt,
        outcome,
        diagnostics["finish_reason"],
        int(diagnostics["content_empty"]),
        diagnostics["content_length"],
        int(diagnostics["reasoning_present"]),
        diagnostics["input_tokens"],
        diagnostics["output_tokens"],
        diagnostics["total_tokens"],
    )


def estimate_creative_request_tokens(
    prompt: str,
    items: List[Any] | None = None,
) -> tuple[int | None, int | None, int | None]:
    """服务商不返回 usage 时，以中文字符数保守估算 token。"""

    prompt_text = str(prompt or "")
    output_text = ""
    for item in (items or []):
        if isinstance(item, dict):
            output_text += str(item.get("story") or "")
            for hook in item.get("hooks") or []:
                if isinstance(hook, dict):
                    output_text += str(hook.get("text") or "")
                    for scene in hook.get("scenes") or []:
                        output_text += str(scene or "")
                else:
                    output_text += str(hook or "")
        else:
            output_text += str(item)
    if not prompt_text and not output_text:
        return None, None, None
    input_tokens = max(1, (len(prompt_text) + 1) // 2) if prompt_text else 0
    output_tokens = max(1, (len(output_text) + 1) // 2) if output_text else 0
    return input_tokens, output_tokens, input_tokens + output_tokens
