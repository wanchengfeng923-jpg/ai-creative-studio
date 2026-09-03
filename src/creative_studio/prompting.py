"""Reusable prompt compilation helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping


_DOUBLE_BRACE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


class PromptCompilationError(ValueError):
    """The prompt template or supplied variables violate the compiler contract."""


def prompt_variable_names(template: str) -> frozenset[str]:
    """Return the variables declared by a double-brace prompt template."""

    return frozenset(match.group(1) for match in _DOUBLE_BRACE_PATTERN.finditer(str(template)))


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted((_normalize(item) for item in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class CompiledPrompt:
    template: str
    variables: Mapping[str, Any] = field(default_factory=dict)
    expected_template_hash: str | None = None

    def render(self) -> str:
        variables = {str(key): str(value) for key, value in self.variables.items()}
        required = set(prompt_variable_names(self.template))
        provided = set(variables)
        missing = sorted(required - provided)
        unknown = sorted(provided - required)
        if missing:
            raise PromptCompilationError(f"提示词缺失变量：{', '.join(missing)}")
        if unknown:
            raise PromptCompilationError(f"提示词包含未知变量：{', '.join(unknown)}")
        if self.expected_template_hash is not None:
            expected = str(self.expected_template_hash).strip().lower()
            if expected != self.template_hash():
                raise PromptCompilationError("提示词模板 hash 不匹配")

        def replace_double_brace(match: re.Match[str]) -> str:
            return variables[match.group(1)]

        # re.sub only scans the original template, so inserted user data is never
        # interpreted as another template fragment.
        return _DOUBLE_BRACE_PATTERN.sub(replace_double_brace, self.template)

    def template_hash(self) -> str:
        return sha256(self.template.encode("utf-8")).hexdigest()

    def stable_hash(self) -> str:
        payload = {
            "template": self.template,
            "variables": _normalize(self.variables),
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return sha256(encoded.encode("utf-8")).hexdigest()


def compile_prompt(
    template: str,
    variables: Mapping[str, Any] | None = None,
    *,
    expected_template_hash: str | None = None,
) -> CompiledPrompt:
    return CompiledPrompt(
        template=template,
        variables=dict(variables or {}),
        expected_template_hash=expected_template_hash,
    )


__all__ = [
    "CompiledPrompt",
    "PromptCompilationError",
    "compile_prompt",
    "prompt_variable_names",
]
