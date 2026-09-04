"""AI v2 候选 Prompt registry 与一次性字面编译器。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping


class AiV2PromptRegistryError(ValueError):
    """Prompt registry 或模板编译失败。"""


@dataclass(frozen=True)
class AiV2PromptSpec:
    prompt_id: str
    version: str
    template_sha256: str
    input_schema: str
    output_schema: str
    max_model_calls: int
    template_text: str = ""
    allowed_variables: tuple[str, ...] = ()
    lifecycle: str = "candidate"
    caller: str | None = None
    prompt_path: str = ""


_PLACEHOLDER = re.compile(r"\{\{([a-z_][a-z0-9_]*)\}\}")
_EXPECTED_VARIABLES = ("task_description", "aspect_ratio", "creative_tags")


def _resolve_inside(base: Path, relative_path: str) -> Path:
    candidate = (base / relative_path).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise AiV2PromptRegistryError("prompt path escapes registry directory") from exc
    return candidate


class AiV2PromptRegistry:
    """只读取静态 v2 registry 声明，不支持环境变量或动态 import。"""

    def __init__(self, registry_path: str | Path | None = None) -> None:
        self.registry_path = Path(registry_path) if registry_path else Path(__file__).resolve().parents[3] / "config" / "ai_v2" / "prompts" / "registry.json"
        self._specs: dict[tuple[str, str], AiV2PromptSpec] = {}
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AiV2PromptRegistryError("v2 prompt registry is unavailable") from exc
        entries = payload.get("prompts") if isinstance(payload, Mapping) else None
        if not isinstance(entries, list):
            raise AiV2PromptRegistryError("v2 prompt registry must contain prompts")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise AiV2PromptRegistryError("v2 prompt entry must be an object")
            required = ("id", "version", "path", "template_sha256", "input_schema", "output_schema", "max_model_calls", "lifecycle")
            if any(key not in entry for key in required):
                raise AiV2PromptRegistryError("v2 prompt entry is incomplete")
            prompt_path = _resolve_inside(self.registry_path.parent, str(entry["path"]))
            try:
                template_bytes = prompt_path.read_bytes()
                template_text = template_bytes.decode("utf-8")
            except OSError as exc:
                raise AiV2PromptRegistryError("v2 prompt template is unavailable") from exc
            except UnicodeDecodeError as exc:
                raise AiV2PromptRegistryError("v2 prompt template is not UTF-8") from exc
            actual_hash = hashlib.sha256(template_bytes).hexdigest()
            if actual_hash != str(entry["template_sha256"]):
                raise AiV2PromptRegistryError("v2 prompt template hash mismatch")
            placeholders = tuple(dict.fromkeys(_PLACEHOLDER.findall(template_text)))
            if placeholders != _EXPECTED_VARIABLES:
                raise AiV2PromptRegistryError("v2 prompt variables must be the three declared inputs")
            lifecycle = str(entry["lifecycle"])
            caller = entry.get("caller")
            if lifecycle == "candidate" and caller is not None:
                raise AiV2PromptRegistryError("candidate prompt cannot have a production caller")
            if lifecycle == "production" and not isinstance(caller, str):
                raise AiV2PromptRegistryError("production prompt requires a caller")
            max_model_calls = entry["max_model_calls"]
            if not isinstance(max_model_calls, int) or max_model_calls < 1:
                raise AiV2PromptRegistryError("max_model_calls must be positive")
            spec = AiV2PromptSpec(
                prompt_id=str(entry["id"]),
                version=str(entry["version"]),
                template_sha256=actual_hash,
                input_schema=str(entry["input_schema"]),
                output_schema=str(entry["output_schema"]),
                max_model_calls=max_model_calls,
                template_text=template_text,
                allowed_variables=placeholders,
                lifecycle=lifecycle,
                caller=caller if isinstance(caller, str) else None,
                prompt_path=str(prompt_path),
            )
            key = (spec.prompt_id, spec.version)
            if key in self._specs:
                raise AiV2PromptRegistryError("duplicate v2 prompt spec")
            self._specs[key] = spec

    def get(self, prompt_id: str, version: str) -> AiV2PromptSpec:
        """按静态 id/version 读取候选或 production 声明。"""

        try:
            return self._specs[(prompt_id, version)]
        except KeyError as exc:
            raise AiV2PromptRegistryError("unknown v2 prompt spec") from exc


def compile_prompt(spec: AiV2PromptSpec, values: Mapping[str, str]) -> str:
    """对三个输入执行一次扫描、一次字面替换，禁止二次模板解释。"""

    allowed = spec.allowed_variables or _EXPECTED_VARIABLES
    if set(values) != set(allowed):
        raise AiV2PromptRegistryError("prompt values must exactly match declared variables")
    if any(not isinstance(value, str) for value in values.values()):
        raise AiV2PromptRegistryError("prompt values must be strings")
    template = spec.template_text
    placeholders = tuple(dict.fromkeys(_PLACEHOLDER.findall(template)))
    if placeholders != tuple(allowed):
        raise AiV2PromptRegistryError("prompt template variables do not match spec")
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)


__all__ = ["AiV2PromptRegistry", "AiV2PromptRegistryError", "AiV2PromptSpec", "compile_prompt"]
