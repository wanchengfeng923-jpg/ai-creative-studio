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

from .ai_service_settings import AiServiceSettings
from .ai_provider import chat_completions_url


AI_LOGGER = logging.getLogger("web_erp.http")


CREATIVE_TAG_KEYS = (
    "target_audiences",
    "secondary_target_audiences",
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
NARRATIVE_TAG_KEYS = CREATIVE_TAG_KEYS[:10]
VISUAL_TAG_KEYS = CREATIVE_TAG_KEYS[10:]
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


class AiCreativeRequestError(RuntimeError):
    """AI 创意服务请求失败或返回结果不符合约定。"""


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
    """只保留 ERP 当前五类创意定位及其主、副定位选项。"""

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


def _default_game_info_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "ai_creative_game_info_v1.json"


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
    content = template.replace("{{game_info}}", str(game_info or "").strip())
    content = content.replace("{{creative_tags}}", tags_text)
    bounded_task_type = _bounded_context_text(task_type, AI_TASK_TYPE_MAX_LENGTH)
    bounded_task_description = _bounded_context_text(task_description, AI_TASK_DESCRIPTION_MAX_LENGTH)
    raw_script_type = script_type or (tags.get("script_type") if isinstance(tags, dict) else "")
    bounded_script_type = _bounded_context_text(raw_script_type, AI_SCRIPT_TYPE_MAX_LENGTH)
    content = content.replace("{{task_type}}", bounded_task_type)
    content = content.replace("{{task_description}}", bounded_task_description)
    content = content.replace("{{script_type}}", bounded_script_type)
    if "{{creative_tags}}" not in template:
        content = f"{content}\n\n创意标签数据：\n{tags_text}"
    if "{{task_type}}" not in template and bounded_task_type:
        content = f"{content}\n\n任务类型参考：\n{bounded_task_type}"
    if "{{task_description}}" not in template and bounded_task_description:
        content = f"{content}\n\n任务描述参考：\n{bounded_task_description}"
    if "{{script_type}}" not in template and bounded_script_type:
        content = f"{content}\n\n脚本类型参考：\n{bounded_script_type}"
    return content


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


def load_ai_visual_creative_config(
    environ: Mapping[str, str] | None = None,
    *,
    service_settings: AiServiceSettings | None = None,
) -> AiCreativeConfig:
    """加载展示类 AI 的独立提示词配置，复用同一服务商配置。"""

    source = dict(environ if environ is not None else os.environ)
    source.pop("WEB_ERP_AI_PROMPT_TEMPLATE", None)
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
) -> str:
    """以批准的展示类上下文填充视觉创意提示词。"""

    template = str(prompt_template or "").strip()
    if not template:
        raise AiCreativeConfigurationError("AI视觉提示词尚未配置")
    reference_names = "、".join(_clean_text_list(reference_file_names)) or "（无参考文件）"
    replacements = {
        "{{task_type}}": _bounded_context_text(task_type, AI_TASK_TYPE_MAX_LENGTH),
        "{{task_description}}": _bounded_context_text(task_description, AI_TASK_DESCRIPTION_MAX_LENGTH),
        "{{creative_tags}}": format_creative_tags_for_prompt(tags, mode="visual"),
        "{{aspect_ratio}}": str(aspect_ratio or "").strip() or "16:9",
        "{{product_evidence_summary}}": str(product_evidence_summary or "").strip(),
        "{{reference_file_names}}": reference_names,
    }
    content = template
    for marker, replacement in replacements.items():
        content = content.replace(marker, replacement)
    return content


def _parse_json_object_text(value: str) -> Dict[str, Any]:
    """解析严格 JSON，或从模型附加说明中提取首个完整 JSON 对象。"""

    text = str(value or "").strip()
    if not text:
        raise AiCreativeRequestError("AI返回结果无法解析")
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
        raise AiCreativeRequestError("AI返回结果无法解析")
    if not isinstance(payload, dict):
        raise AiCreativeRequestError("AI返回结果无法解析")
    return payload


def _recommendation_payload(value: Any) -> Any:
    if isinstance(value, dict) and "items" in value:
        return value["items"]
    if isinstance(value, str):
        return _recommendation_payload(_parse_json_object_text(value))
    if isinstance(value, dict) and "choices" in value:
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AiCreativeRequestError("AI返回结果缺少choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict) or "content" not in message:
            raise AiCreativeRequestError("AI返回结果缺少正文")
        return _recommendation_payload(message["content"])
    return value


def validate_creative_recommendations(value: Any) -> List[Dict[str, Any]]:
    """验证 AI 返回值必须满足 5 个故事、每故事 2 个钩子、每钩子 3 个画面。"""

    items = _recommendation_payload(value)
    if not isinstance(items, list) or len(items) != 5:
        raise AiCreativeRequestError("AI返回结果必须正好包含5个故事")
    result: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise AiCreativeRequestError("AI返回的每个故事必须是对象")
        story = str(item.get("story") or "").strip()
        if not story or "\n" in story or "\r" in story:
            raise AiCreativeRequestError("AI返回的每个故事必须是非空单行文本")
        hooks = item.get("hooks")
        if not isinstance(hooks, list) or len(hooks) != 2:
            raise AiCreativeRequestError("AI返回的每个故事必须恰好包含2个钩子")
        clean_hooks: List[Dict[str, Any]] = []
        for hook in hooks:
            if not isinstance(hook, dict):
                raise AiCreativeRequestError("AI返回的每个钩子必须是对象")
            text = str(hook.get("text") or "").strip()
            if not text or "\n" in text or "\r" in text:
                raise AiCreativeRequestError("AI返回的每个钩子必须包含非空单行文本")
            scenes = hook.get("scenes")
            if not isinstance(scenes, list) or len(scenes) != 3:
                raise AiCreativeRequestError("AI返回的每个钩子必须恰好包含3个画面建议")
            clean_scenes: List[str] = []
            for scene in scenes:
                scene_text = str(scene or "").strip()
                if (
                    not scene_text
                    or "\n" in scene_text
                    or "\r" in scene_text
                    or len(scene_text) > 80
                ):
                    raise AiCreativeRequestError(
                        "AI返回的每条画面建议必须是非空单行文本且不超过80个字符"
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
            raise AiCreativeRequestError("AI返回结果缺少choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict) or "content" not in message:
            raise AiCreativeRequestError("AI返回结果缺少正文")
        return _visual_recommendation_payload(message["content"])
    if not isinstance(value, dict) or set(value) != {"items"}:
        raise AiCreativeRequestError("AI视觉返回结果必须只有items字段")
    return value["items"]


def _visual_text(value: Any, label: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise AiCreativeRequestError(f"AI视觉返回的{label}不能为空")
    if "://" in text.lower() or VISUAL_BARE_DOMAIN_URL_PATTERN.search(text):
        raise AiCreativeRequestError(f"AI视觉返回的{label}不能包含网址")
    return text


def _visual_text_list(value: Any, label: str) -> List[str]:
    if not isinstance(value, list) or not value:
        raise AiCreativeRequestError(f"AI视觉返回的{label}必须是非空列表")
    return [_visual_text(item, label) for item in value]


def validate_visual_creative_recommendations(value: Any) -> List[Dict[str, Any]]:
    """严格验证展示类视觉创意的三项完整 schema。"""

    items = _visual_recommendation_payload(value)
    if not isinstance(items, list) or len(items) != 3:
        raise AiCreativeRequestError("AI视觉返回结果必须正好包含3个方案")
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
    for item in items:
        if not isinstance(item, dict) or set(item) != set(VISUAL_CREATIVE_ITEM_FIELDS):
            raise AiCreativeRequestError("AI视觉返回的每个方案必须符合批准字段结构")
        cleaned = {field: _visual_text(item.get(field), field) for field in text_fields}
        cleaned["content_extensions"] = _visual_text_list(
            item.get("content_extensions"), "content_extensions"
        )
        cleaned["keywords"] = _visual_text_list(item.get("keywords"), "keywords")
        sources = item.get("reference_sources")
        if not isinstance(sources, list) or not sources:
            raise AiCreativeRequestError("AI视觉返回的reference_sources必须是非空列表")
        cleaned_sources: List[Dict[str, str]] = []
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"name", "note"}:
                raise AiCreativeRequestError("AI视觉返回的参考来源只能包含name和note")
            cleaned_sources.append({
                "name": _visual_text(source.get("name"), "reference_sources.name"),
                "note": _visual_text(source.get("note"), "reference_sources.note"),
            })
        cleaned["reference_sources"] = cleaned_sources
        result.append({field: cleaned[field] for field in VISUAL_CREATIVE_ITEM_FIELDS})
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
    for attempt in range(1, 3):
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
        except requests.RequestException as exc:
            raise AiCreativeRequestError("AI接口请求失败，请稍后重试") from exc
        try:
            response_payload = response.json()
            items = validate_visual_creative_recommendations(response_payload)
            response_conversation_id = str(
                response_payload.get("conversation_id") or ""
            ).strip() if isinstance(response_payload, dict) else ""
            response_assistant_message_id = str(
                response_payload.get("assistant_message_id") or ""
            ).strip() if isinstance(response_payload, dict) else ""
            if config.provider == "chatgpt-web" and (
                not response_conversation_id or not response_assistant_message_id
            ):
                raise AiCreativeRequestError("AI会话标识缺失，无法继续生成")
            _log_ai_response_diagnostics(config, response_payload, attempt=attempt, outcome="success")
            break
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            _log_ai_response_diagnostics(config, None, attempt=attempt, outcome="response_json_error")
            if attempt == 2:
                raise AiCreativeRequestError("AI接口返回内容无法解析") from exc
        except AiCreativeRequestError:
            _log_ai_response_diagnostics(config, response_payload, attempt=attempt, outcome="format_error")
            if attempt == 2:
                raise
    if items is None:
        raise AiCreativeRequestError("AI返回结果无法解析")
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
        except requests.RequestException as exc:
            raise AiCreativeRequestError("AI接口请求失败，请稍后重试") from exc
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
                raise AiCreativeRequestError("AI会话标识缺失，无法继续生成")
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
                raise AiCreativeRequestError("AI接口返回内容无法解析") from exc
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
        raise AiCreativeRequestError("AI返回结果无法解析")
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
