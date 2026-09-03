"""轮播 v1 的规划请求、输出校验和后续图片编排策略。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .ai_creative import build_visual_creative_prompt, validate_visual_creative_recommendations
from .model_client import ModelRequest


@dataclass(frozen=True)
class CarouselPromptInput:
    """共享 planner 所需的服务端归一化输入。"""

    tags: Mapping[str, list[str]]
    task_type: str
    task_description: str
    aspect_ratio: str
    product_evidence_summary: str
    reference_file_names: tuple[str, ...]
    carousel_config: Mapping[str, Any]
    tag_catalog: Mapping[str, Any]


class CarouselVisualGeneration:
    """隐藏轮播 v1 的 prompt 细节和图片连续性编排。"""

    def __init__(self, model_name: str, prompt_template: str) -> None:
        self.model_name = str(model_name)
        self.prompt_template = str(prompt_template)

    def build_request(
        self,
        prompt_input: CarouselPromptInput,
        *,
        conversation_id: str = "",
        parent_message_id: str = "",
    ) -> ModelRequest:
        """构造一次共享 planner 请求，首帧指令由同一响应直接提供。"""

        prompt = build_visual_creative_prompt(
            prompt_input.tags,
            self.prompt_template,
            task_type=prompt_input.task_type,
            task_description=prompt_input.task_description,
            aspect_ratio=prompt_input.aspect_ratio,
            product_evidence_summary=prompt_input.product_evidence_summary,
            reference_file_names=prompt_input.reference_file_names,
            carousel_config=prompt_input.carousel_config,
            tag_catalog=prompt_input.tag_catalog,
        )
        return ModelRequest(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=5000,
            conversation_id=str(conversation_id or ""),
            parent_message_id=str(parent_message_id or ""),
        )

    @staticmethod
    def validate(
        payload: Any,
        prompt_input: CarouselPromptInput,
    ) -> list[dict[str, Any]]:
        """校验并归一化共享 planner 的三套方案。"""

        return validate_visual_creative_recommendations(
            payload,
            carousel_config=prompt_input.carousel_config,
            tag_catalog=prompt_input.tag_catalog,
        )

    @staticmethod
    def follow_up_image_prompt(
        scheme: Mapping[str, Any], frames: list[Mapping[str, Any]], frame_index: int
    ) -> str:
        """按锁定路线编排下一帧图片指令，并携带上一帧实际画面信息。"""

        completed = [
            {
                "frame_index": int(frame["frame_index"]),
                "actual_content": str(frame.get("actual_content") or ""),
            }
            for frame in frames
            if int(frame["frame_index"]) < frame_index
            and str(frame.get("image_status")) == "success"
        ]
        previous = next(
            (frame for frame in frames if int(frame["frame_index"]) == frame_index - 1),
            None,
        )
        next_plan = next(
            (
                item.get("description")
                for item in scheme.get("frame_plan", [])
                if int(item.get("index") or 0) == frame_index
            ),
            "",
        )
        return "\n".join(
            [
                "直接生成一张图片。不要回复文字、JSON、Markdown或解释，只返回图片结果。",
                f"目标画幅：{scheme.get('aspect_ratio') or '16:9'}。",
                f"方案标题：{scheme.get('title') or ''}。",
                f"任务描述：{scheme.get('task_description') or ''}。",
                f"产品证据：{scheme.get('product_evidence_summary') or ''}。",
                f"创意来源：{'；'.join(str(item) for item in scheme.get('creative_sources', []))}。",
                f"核心主体：{scheme.get('core_subject') or ''}。",
                f"画面布局：{scheme.get('layout') or ''}。",
                f"视觉风格：{scheme.get('visual_style') or ''}。",
                f"内容延展：{'；'.join(str(item) for item in scheme.get('content_extensions', []))}。",
                f"视觉连续性规则：{'；'.join(str(item) for item in scheme.get('visual_continuity_rules', []))}。",
                f"已完成画面：{json.dumps(completed, ensure_ascii=False)}。",
                f"上一张画面：{str((previous or {}).get('actual_content') or '')}。",
                f"当前第{frame_index}张路线：{next_plan}。",
                "保持上一张实际图片中的主体身份、关键产品证据、色彩和材质连续，仅按当前路线改变画面状态。",
            ]
        )


__all__ = ["CarouselPromptInput", "CarouselVisualGeneration"]
