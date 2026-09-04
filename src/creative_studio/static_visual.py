"""静态展示类生成 Module：canonical contract、prompt 编译和有限 repair。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .model_client import ModelClient, ModelRequest, ModelResponse, ModelResponseFormatError
from .model_ports import TextModelPort
from .prompting import compile_prompt, parse_json_object_text, prompt_variable_names


class StaticVisualOutputError(ValueError):
    """模型输出不满足 StaticVisualResult.v1。"""

    error_code = "model_output_invalid"
    phase = "validation"
    retryable = False

    def __init__(self, message: str, *, field_path: str) -> None:
        super().__init__(message)
        self.field_path = str(field_path or "$")


@dataclass(frozen=True)
class StaticVisualPromptInput:
    """StaticVisualPromptInput.v1 的有界输入。"""

    task_type: str = ""
    task_description: str = ""
    creative_tags: Mapping[str, Sequence[str]] = field(default_factory=dict)
    aspect_ratio: str = "16:9"
    product_evidence_summary: str = ""
    reference_file_names: tuple[str, ...] = ()
    reference_context: tuple[str, ...] = ()


@dataclass(frozen=True)
class StaticVisualResult:
    """StaticVisualResult.v1 的规范化结果。"""

    items: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class StaticVisualImageRequest:
    """静态首图进入图片队列时的私有 typed request。"""

    scheme_id: int
    generation_id: int
    aspect_ratio: str
    prompt: str
    request_id: str
    reference_assets: tuple[bytes, ...] = ()


_ITEM_FIELDS = frozenset({
    "concept_id",
    "title",
    "creative_summary",
    "audience_tension",
    "product_value",
    "visual_mechanism",
    "creative_sources",
    "evidence_ledger",
    "static_frame",
    "asset_plan",
    "production_risks",
    "review",
    "image_generation_instruction",
})
_FRAME_FIELDS = frozenset({
    "visual_event",
    "hero_subject",
    "composition",
    "attention_order",
    "medium_and_art_direction",
    "copy",
    "product_proof",
    "legibility_notes",
})
_COPY_FIELDS = frozenset({"headline", "supporting_line", "brand_line", "cta"})
_EVIDENCE_FIELDS = frozenset({"confirmed", "inferred", "to_confirm"})
_ASSET_FIELDS = frozenset({"asset", "status", "fallback"})
_RISK_FIELDS = frozenset({"risk", "mitigation"})
_REVIEW_FIELDS = frozenset({"stop_reason", "why_make_next", "first_validation"})
_ASSET_STATUSES = frozenset({"existing", "needs_capture", "needs_design", "to_confirm"})
def _text(value: Any, path: str, *, max_length: int = 500, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise StaticVisualOutputError(f"{path} 必须是文本", field_path=path)
    text = value.strip()
    if not text and not allow_empty:
        raise StaticVisualOutputError(f"{path} 不能为空", field_path=path)
    if "\n" in value or "\r" in value:
        raise StaticVisualOutputError(f"{path} 必须是单行文本", field_path=path)
    if len(text) > max_length:
        raise StaticVisualOutputError(f"{path} 超出长度限制", field_path=path)
    if "http://" in text.lower() or "https://" in text.lower() or "www." in text.lower():
        raise StaticVisualOutputError(f"{path} 不得包含 URL", field_path=path)
    if "```" in text or text.startswith("#"):
        raise StaticVisualOutputError(f"{path} 不得包含 Markdown", field_path=path)
    return text


def _text_list(value: Any, path: str, *, max_length: int = 300, non_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise StaticVisualOutputError(f"{path} 必须是文本列表", field_path=path)
    if non_empty and not value:
        raise StaticVisualOutputError(f"{path} 不能为空", field_path=path)
    return [
        _text(item, f"{path}[{index}]", max_length=max_length)
        for index, item in enumerate(value)
    ]


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StaticVisualOutputError(f"{path} 必须是对象", field_path=path)
    return value


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], path: str) -> None:
    if set(value) != expected:
        raise StaticVisualOutputError(f"{path} 字段结构无效", field_path=path)


def _validate_item(raw: Any, index: int) -> dict[str, Any]:
    path = f"items[{index}]"
    source = _mapping(raw, path)
    _exact_fields(source, _ITEM_FIELDS, path)
    concept_id = _text(source["concept_id"], f"{path}.concept_id", max_length=1)
    if concept_id not in {"A", "B", "C"}:
        raise StaticVisualOutputError("concept_id 必须为 A、B 或 C", field_path=f"{path}.concept_id")
    clean: dict[str, Any] = {
        "concept_id": concept_id,
        "title": _text(source["title"], f"{path}.title"),
        "creative_summary": _text(source["creative_summary"], f"{path}.creative_summary"),
        "audience_tension": _text(source["audience_tension"], f"{path}.audience_tension"),
        "product_value": _text(source["product_value"], f"{path}.product_value"),
        "visual_mechanism": _text(source["visual_mechanism"], f"{path}.visual_mechanism"),
        "creative_sources": _text_list(source["creative_sources"], f"{path}.creative_sources"),
        "image_generation_instruction": _text(
            source["image_generation_instruction"],
            f"{path}.image_generation_instruction",
            max_length=1200,
        ),
    }

    evidence = _mapping(source["evidence_ledger"], f"{path}.evidence_ledger")
    _exact_fields(evidence, _EVIDENCE_FIELDS, f"{path}.evidence_ledger")
    clean["evidence_ledger"] = {
        key: _text_list(evidence[key], f"{path}.evidence_ledger.{key}", non_empty=True)
        for key in ("confirmed", "inferred", "to_confirm")
    }

    frame = _mapping(source["static_frame"], f"{path}.static_frame")
    _exact_fields(frame, _FRAME_FIELDS, f"{path}.static_frame")
    copy_value = _mapping(frame["copy"], f"{path}.static_frame.copy")
    _exact_fields(copy_value, _COPY_FIELDS, f"{path}.static_frame.copy")
    cta = copy_value["cta"]
    if cta is not None:
        cta = _text(cta, f"{path}.static_frame.copy.cta", allow_empty=True)
    clean["static_frame"] = {
        "visual_event": _text(frame["visual_event"], f"{path}.static_frame.visual_event"),
        "hero_subject": _text(frame["hero_subject"], f"{path}.static_frame.hero_subject"),
        "composition": _text(frame["composition"], f"{path}.static_frame.composition"),
        "attention_order": _text_list(frame["attention_order"], f"{path}.static_frame.attention_order", max_length=120),
        "medium_and_art_direction": _text(
            frame["medium_and_art_direction"],
            f"{path}.static_frame.medium_and_art_direction",
            max_length=800,
        ),
        "copy": {
            "headline": _text(copy_value["headline"], f"{path}.static_frame.copy.headline", max_length=80),
            "supporting_line": _text(
                copy_value["supporting_line"],
                f"{path}.static_frame.copy.supporting_line",
                max_length=120,
                allow_empty=True,
            ),
            "brand_line": _text(copy_value["brand_line"], f"{path}.static_frame.copy.brand_line", max_length=80),
            "cta": cta,
        },
        "product_proof": _text_list(frame["product_proof"], f"{path}.static_frame.product_proof"),
        "legibility_notes": _text(frame["legibility_notes"], f"{path}.static_frame.legibility_notes"),
    }

    asset_plan = source["asset_plan"]
    if not isinstance(asset_plan, list) or not asset_plan:
        raise StaticVisualOutputError("asset_plan 不能为空", field_path=f"{path}.asset_plan")
    clean["asset_plan"] = []
    for asset_index, raw_asset in enumerate(asset_plan):
        asset_path = f"{path}.asset_plan[{asset_index}]"
        asset = _mapping(raw_asset, asset_path)
        _exact_fields(asset, _ASSET_FIELDS, asset_path)
        status = _text(asset["status"], f"{asset_path}.status", max_length=30)
        if status not in _ASSET_STATUSES:
            raise StaticVisualOutputError("asset_plan.status 无效", field_path=f"{asset_path}.status")
        clean["asset_plan"].append({
            "asset": _text(asset["asset"], f"{asset_path}.asset"),
            "status": status,
            "fallback": _text(asset["fallback"], f"{asset_path}.fallback"),
        })

    risks = source["production_risks"]
    if not isinstance(risks, list) or not risks:
        raise StaticVisualOutputError("production_risks 不能为空", field_path=f"{path}.production_risks")
    clean["production_risks"] = []
    for risk_index, raw_risk in enumerate(risks):
        risk_path = f"{path}.production_risks[{risk_index}]"
        risk = _mapping(raw_risk, risk_path)
        _exact_fields(risk, _RISK_FIELDS, risk_path)
        clean["production_risks"].append({
            "risk": _text(risk["risk"], f"{risk_path}.risk"),
            "mitigation": _text(risk["mitigation"], f"{risk_path}.mitigation"),
        })

    review = _mapping(source["review"], f"{path}.review")
    _exact_fields(review, _REVIEW_FIELDS, f"{path}.review")
    clean["review"] = {
        key: _text(review[key], f"{path}.review.{key}")
        for key in ("stop_reason", "why_make_next", "first_validation")
    }
    return clean


def validate_static_visual_result(value: Any) -> StaticVisualResult:
    """验证并规范化 StaticVisualResult.v1。"""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StaticVisualOutputError("静态展示结果不是合法 JSON", field_path="$") from exc
    if not isinstance(value, Mapping) or set(value) != {"items"}:
        raise StaticVisualOutputError("静态展示结果根对象只能包含items", field_path="$" )
    items = value.get("items")
    if not isinstance(items, list) or len(items) != 3:
        raise StaticVisualOutputError("items 必须正好包含3个方案", field_path="items")
    clean_items = [_validate_item(item, index) for index, item in enumerate(items)]
    concept_ids = [item["concept_id"] for item in clean_items]
    if set(concept_ids) != {"A", "B", "C"}:
        raise StaticVisualOutputError("concept_id 必须唯一覆盖 A、B、C", field_path="items")
    mechanisms = [item["visual_mechanism"] for item in clean_items]
    if len(set(mechanisms)) != len(mechanisms):
        duplicate_index = next(index for index, value in enumerate(mechanisms) if value in mechanisms[:index])
        raise StaticVisualOutputError("三套方案的 visual_mechanism 必须有可观察差异", field_path=f"items[{duplicate_index}].visual_mechanism")
    return StaticVisualResult(tuple(clean_items))


@dataclass
class StaticVisualGeneration:
    """静态展示类生产用例，隐藏 prompt 和一次有限格式修复。"""

    model: ModelClient | TextModelPort
    prompt_template: str | None = None
    model_name: str = "gpt-5-6-mini"
    last_response: ModelResponse | None = None

    def _prompt(self, data: StaticVisualPromptInput, *, repair: str = "") -> str:
        tags = "；".join(
            f"{key}={','.join(str(item) for item in values)}"
            for key, values in sorted((data.creative_tags or {}).items(), key=lambda item: str(item[0]))
        ) or "（未选择标签）"
        references = "、".join(data.reference_context or data.reference_file_names) or "（无参考文件，仅表示未提供文件名）"
        template = self.prompt_template or (
            "任务类型：{{task_type}}\n任务描述：{{task_description}}\n展示类标签：{{creative_tags}}\n"
            "目标画幅：{{aspect_ratio}}\n产品信息：{{product_evidence_summary}}\n"
            "参考文件名：{{reference_file_names}}\n请只返回 StaticVisualResult.v1 JSON。"
        )
        values = {
            "task_type": data.task_type,
            "task_description": data.task_description,
            "creative_tags": tags,
            "aspect_ratio": data.aspect_ratio,
            "product_evidence_summary": data.product_evidence_summary or "（无产品资料摘要）",
            "reference_file_names": references,
        }
        declared = prompt_variable_names(template)
        prompt = compile_prompt(template, {key: values[key] for key in declared if key in values}).render()
        if repair:
            prompt += f"\n上一次校验错误字段：{repair}。请修复该字段并只返回合法 JSON。"
        return prompt

    def generate(
        self,
        data: StaticVisualPromptInput,
        *,
        conversation_id: str = "",
        parent_message_id: str = "",
    ) -> StaticVisualResult:
        last_error: StaticVisualOutputError | None = None
        for attempt in range(2):
            try:
                response = self.model.generate(ModelRequest(
                    model=self.model_name,
                    messages=[{"role": "user", "content": self._prompt(data, repair=last_error.field_path if last_error else "")}],
                    response_format={"type": "json_object"},
                    max_tokens=5000,
                    conversation_id=conversation_id,
                    parent_message_id=parent_message_id,
                ))
                result = validate_static_visual_result(parse_json_object_text(response.content))
                self.last_response = response
                return result
            except ModelResponseFormatError as exc:
                last_error = StaticVisualOutputError(str(exc), field_path=exc.field_path)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc if isinstance(exc, StaticVisualOutputError) else StaticVisualOutputError(
                    "静态展示结果 JSON 无效", field_path="$"
                )
        assert last_error is not None
        raise last_error


__all__ = [
    "StaticVisualGeneration",
    "StaticVisualImageRequest",
    "StaticVisualOutputError",
    "StaticVisualPromptInput",
    "StaticVisualResult",
    "validate_static_visual_result",
]
