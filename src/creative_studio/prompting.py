"""Reusable prompt compilation helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from string import Template
from typing import Any, Mapping


_DOUBLE_BRACE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


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

    def render(self) -> str:
        rendered = self.template
        variables = {str(key): str(value) for key, value in self.variables.items()}

        def replace_double_brace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise KeyError(key)
            return variables[key]

        rendered = _DOUBLE_BRACE_PATTERN.sub(replace_double_brace, rendered)
        return Template(rendered).substitute(variables)

    def stable_hash(self) -> str:
        payload = {
            "template": self.template,
            "variables": _normalize(self.variables),
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return sha256(encoded.encode("utf-8")).hexdigest()


def compile_prompt(template: str, variables: Mapping[str, Any] | None = None) -> CompiledPrompt:
    return CompiledPrompt(template=template, variables=dict(variables or {}))


__all__ = ["CompiledPrompt", "compile_prompt"]
