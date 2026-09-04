"""AI v2 Prompt 编译边界的窄 facade。"""

from __future__ import annotations

from collections.abc import Mapping

from .prompt_registry import AiV2PromptSpec, compile_prompt


def compile_v2_prompt(spec: AiV2PromptSpec, values: Mapping[str, str]) -> str:
    """保留独立命名空间的 Prompt 编译入口。"""

    return compile_prompt(spec, values)


__all__ = ["compile_v2_prompt"]

