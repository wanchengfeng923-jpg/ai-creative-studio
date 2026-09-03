"""叙事类生成 Module：编译 prompt、校验 canonical 结果并投影公开 DTO。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .model_client import ModelClient, ModelRequest, ModelResponseFormatError
from .model_ports import TextModelPort
from .prompting import compile_prompt, prompt_variable_names


class NarrativeOutputError(ValueError):
    """模型输出不满足 NarrativeResult.v1。"""

    error_code = "model_output_invalid"
    phase = "validation"
    retryable = False

    def __init__(self, message: str, *, field_path: str) -> None:
        super().__init__(message)
        self.field_path = field_path


@dataclass(frozen=True)
class NarrativeInput:
    """叙事 prompt 的有界输入。"""

    task_type: str = ""
    task_description: str = ""
    creative_tags: Mapping[str, Sequence[str]] = field(default_factory=dict)
    game_info: str = ""
    reference_file_names: tuple[str, ...] = ()
    batch_index: int = 0
    previous_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class NarrativeResult:
    """NarrativeResult.v1 的规范化结果。"""

    items: tuple[dict[str, Any], ...]


def _text(value: Any, path: str, *, max_length: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise NarrativeOutputError(f"{path} 必须是非空单行文本", field_path=path)
    value = value.strip()
    if len(value) > max_length:
        raise NarrativeOutputError(f"{path} 超出长度限制", field_path=path)
    return value


def validate_narrative_result(value: Any) -> NarrativeResult:
    """验证并归一化 NarrativeResult.v1。"""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise NarrativeOutputError("叙事结果不是合法 JSON", field_path="$ ".strip()) from exc
    if not isinstance(value, Mapping) or set(value) != {"items"}:
        raise NarrativeOutputError("叙事结果根对象只能包含items", field_path="items")
    items = value.get("items")
    if not isinstance(items, list) or len(items) != 5:
        raise NarrativeOutputError("items 必须正好包含5个故事", field_path="items")
    result: list[dict[str, Any]] = []
    concept_ids: set[str] = set()
    stories: set[str] = set()
    for index, raw in enumerate(items):
        path = f"items[{index}]"
        if not isinstance(raw, Mapping):
            raise NarrativeOutputError(f"{path} 必须是对象", field_path=path)
        legacy = set(raw) == {"story", "hooks"}
        allowed = {"concept_id", "story", "audience_tension", "product_value", "hooks", "evidence", "risks"}
        if not legacy and set(raw) != allowed:
            raise NarrativeOutputError(f"{path} 字段结构无效", field_path=path)
        concept_id = _text(raw.get("concept_id", chr(65 + index)), f"{path}.concept_id", max_length=40)
        if concept_id in concept_ids:
            raise NarrativeOutputError("concept_id 必须唯一", field_path=f"{path}.concept_id")
        concept_ids.add(concept_id)
        story = _text(raw.get("story"), f"{path}.story")
        if not legacy and story in stories:
            raise NarrativeOutputError("故事必须彼此不同", field_path=f"{path}.story")
        stories.add(story)
        hooks = raw.get("hooks")
        if not isinstance(hooks, list) or len(hooks) != 2:
            raise NarrativeOutputError("hooks 必须恰好包含2个钩子", field_path=f"{path}.hooks")
        clean_hooks: list[dict[str, Any]] = []
        hook_texts: set[str] = set()
        for hook_index, raw_hook in enumerate(hooks):
            hook_path = f"{path}.hooks[{hook_index}]"
            if not isinstance(raw_hook, Mapping) or set(raw_hook) != {"text", "scenes"}:
                raise NarrativeOutputError("钩子字段结构无效", field_path=hook_path)
            hook_text = _text(raw_hook.get("text"), f"{hook_path}.text")
            if hook_text in hook_texts:
                raise NarrativeOutputError("同一故事的两个钩子必须不同", field_path=f"{hook_path}.text")
            hook_texts.add(hook_text)
            scenes = raw_hook.get("scenes")
            if not isinstance(scenes, list) or len(scenes) != 3:
                raise NarrativeOutputError("scenes 必须恰好包含3个画面", field_path=f"{hook_path}.scenes")
            clean_hooks.append({"text": hook_text, "scenes": [
                _text(scene, f"{hook_path}.scenes[{scene_index}]", max_length=160)
                for scene_index, scene in enumerate(scenes)
            ]})
        evidence = raw.get("evidence", {"confirmed": [], "inferred": [], "to_confirm": []})
        if not isinstance(evidence, Mapping) or set(evidence) != {"confirmed", "inferred", "to_confirm"}:
            raise NarrativeOutputError("evidence 字段结构无效", field_path=f"{path}.evidence")
        clean_evidence: dict[str, list[str]] = {}
        for key in ("confirmed", "inferred", "to_confirm"):
            values = evidence.get(key)
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                raise NarrativeOutputError("evidence 列表格式无效", field_path=f"{path}.evidence.{key}")
            clean_evidence[key] = [item.strip() for item in values if item.strip()]
        risks = raw.get("risks", [])
        if not isinstance(risks, list) or any(not isinstance(item, str) or not item.strip() for item in risks):
            raise NarrativeOutputError("risks 必须是文本列表", field_path=f"{path}.risks")
        result.append({
            "concept_id": concept_id,
            "story": story,
            "audience_tension": _text(raw.get("audience_tension", "未提供"), f"{path}.audience_tension"),
            "product_value": _text(raw.get("product_value", "未提供"), f"{path}.product_value"),
            "hooks": clean_hooks,
            "evidence": clean_evidence,
            "risks": [item.strip() for item in risks],
        })
    return NarrativeResult(tuple(result))


class NarrativeGeneration:
    """叙事类生产用例，隐藏 prompt 和有限模型重试细节。"""

    def __init__(self, model: ModelClient | TextModelPort, *, prompt_template: str | None = None, model_name: str = "gpt-5-6-mini") -> None:
        self.model = model
        self.model_name = model_name
        self.last_response = None
        self.prompt_template = prompt_template or (
            "任务类型：{{task_type}}\n任务描述：{{task_description}}\n创意标签：{{creative_tags}}\n"
            "游戏资料：{{game_info}}\n参考资料：{{reference_file_names}}\n"
            "请只返回 NarrativeResult.v1 JSON。"
        )

    def _prompt(self, data: NarrativeInput, *, repair: str = "") -> str:
        tags = "；".join(f"{key}={','.join(values)}" for key, values in (data.creative_tags or {}).items())
        references = "、".join(data.reference_file_names) or "（无参考文件）"
        values = {
            "task_type": data.task_type,
            "task_description": data.task_description,
            "creative_tags": tags,
            "game_info": data.game_info,
            "reference_file_names": references,
        }
        declared = prompt_variable_names(self.prompt_template)
        prompt = compile_prompt(
            self.prompt_template,
            {key: values[key] for key in declared if key in values},
        ).render()
        if data.batch_index > 0:
            previous = "、".join(data.previous_items) or "（上一批摘要缺失）"
            prompt += f"\n这是第{data.batch_index + 1}批。上一批故事摘要：{previous}。不得重复上一批故事或钩子。"
        if repair:
            prompt += f"\n上一次校验错误字段：{repair}。请修复该字段并只返回合法 JSON。"
        return prompt

    def generate(self, data: NarrativeInput, *, conversation_id: str = "", parent_message_id: str = "") -> NarrativeResult:
        last_error: NarrativeOutputError | None = None
        for attempt in range(2):
            try:
                response = self.model.generate(ModelRequest(
                    model=self.model_name,
                    messages=[{"role": "user", "content": self._prompt(data, repair=last_error.field_path if last_error else "")}],
                    response_format={"type": "json_object"},
                    max_tokens=10000,
                    conversation_id=conversation_id,
                    parent_message_id=parent_message_id,
                ))
                result = validate_narrative_result(json.loads(response.content))
                self.last_response = response
                return result
            except ModelResponseFormatError as exc:
                last_error = NarrativeOutputError(str(exc), field_path=exc.field_path)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc if isinstance(exc, NarrativeOutputError) else NarrativeOutputError("叙事结果 JSON 无效", field_path="$ ".strip())
        assert last_error is not None
        raise last_error

    @staticmethod
    def public_items(result: NarrativeResult) -> list[dict[str, Any]]:
        """显式映射旧 UI 所需字段，不透传 canonical 私有扩展。"""

        return [{"story": item["story"], "hooks": item["hooks"]} for item in result.items]


__all__ = ["NarrativeGeneration", "NarrativeInput", "NarrativeOutputError", "NarrativeResult", "validate_narrative_result"]
