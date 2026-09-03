"""PromptSpec registry：只读取配置数据并在启动时 fail closed。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import CONTRACT_BINDINGS, validate_contract_ids


class PromptRegistryError(RuntimeError):
    """Prompt registry 配置不满足启动门禁。"""


@dataclass(frozen=True)
class GenerationPolicy:
    stages: tuple[Mapping[str, Any], ...]
    max_model_calls: int
    max_output_tokens: int
    timeout_seconds: float
    failure_strategy: str
    evaluation_set: str


@dataclass(frozen=True)
class PromptSpec:
    id: str
    version: str
    path: str
    template_sha256: str
    variables: frozenset[str]
    input_schema: str
    output_schema: str
    validator: str
    public_dto: str
    provider: str
    model: str
    lifecycle: str
    caller: str
    generation_policy: GenerationPolicy | None = None
    deprecated_since: str = ""
    replacement: str = ""
    new_callers_forbidden: bool = False
    removal_condition: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return self.id, self.version


def _hash_template(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()


def _template_variables(path: Path) -> frozenset[str]:
    text = path.read_text(encoding="utf-8").strip()
    return frozenset(match.group(1) for match in re.finditer(r"\{\{([A-Za-z0-9_]+)\}\}", text))


class PromptRegistry:
    """不可变 prompt 清单；JSON 不参与 Python import 或执行。"""

    def __init__(self, specs: tuple[PromptSpec, ...], *, root: Path) -> None:
        self._specs = specs
        self.root = root.resolve()
        self._by_key = {spec.key: spec for spec in specs}

    @classmethod
    def load(cls, path: Path) -> "PromptRegistry":
        registry_path = Path(path).resolve()
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise PromptRegistryError("prompt registry 无法读取") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("prompts"), list):
            raise PromptRegistryError("prompt registry 格式无效")
        root = registry_path.parents[2]
        seen: set[tuple[str, str]] = set()
        specs: list[PromptSpec] = []
        for raw in payload["prompts"]:
            if not isinstance(raw, Mapping):
                raise PromptRegistryError("PromptSpec 必须是对象")
            try:
                spec_id, version, lifecycle = str(raw["id"]), str(raw["version"]), str(raw["lifecycle"])
                key = (spec_id, version)
                if key in seen:
                    raise PromptRegistryError(f"重复 PromptSpec: {key}")
                seen.add(key)
                if lifecycle not in {"production", "candidate", "retired"}:
                    raise PromptRegistryError(f"非法 lifecycle: {lifecycle}")
                prompt_path = (root / str(raw["path"])).resolve()
                config_root = (root / "config").resolve()
                if config_root not in prompt_path.parents and prompt_path != config_root:
                    raise PromptRegistryError("prompt 路径越界")
                if not prompt_path.is_file():
                    raise PromptRegistryError(f"prompt 文件不存在: {raw['path']}")
                if _hash_template(prompt_path) != str(raw["template_sha256"]):
                    raise PromptRegistryError(f"prompt hash 不匹配: {spec_id}@{version}")
                if _template_variables(prompt_path) != frozenset(str(v) for v in raw.get("variables", [])):
                    raise PromptRegistryError(f"prompt 变量不匹配: {spec_id}@{version}")
                binding = CONTRACT_BINDINGS.get(spec_id)
                if lifecycle == "production":
                    if binding is None:
                        raise PromptRegistryError(f"production prompt 未绑定 contract: {spec_id}")
                    validate_contract_ids(raw)
                    if str(raw.get("caller") or "") != binding.production_caller:
                        raise PromptRegistryError(f"production caller 不匹配: {spec_id}")
                policy_raw = raw.get("generation_policy")
                policy = None
                if isinstance(policy_raw, Mapping):
                    policy = GenerationPolicy(
                        tuple(policy_raw.get("stages") or ()), int(policy_raw.get("max_model_calls", 0)),
                        int(policy_raw.get("max_output_tokens", 0)), float(policy_raw.get("timeout_seconds", 0)),
                        str(policy_raw.get("failure_strategy") or ""), str(policy_raw.get("evaluation_set") or ""),
                    )
                specs.append(PromptSpec(
                    id=spec_id, version=version, path=str(raw["path"]), template_sha256=str(raw["template_sha256"]),
                    variables=frozenset(str(v) for v in raw.get("variables", [])), input_schema=str(raw.get("input_schema") or ""),
                    output_schema=str(raw.get("output_schema") or ""), validator=str(raw.get("validator") or ""),
                    public_dto=str(raw.get("public_dto") or ""), provider=str(raw.get("provider") or ""),
                    model=str(raw.get("model") or ""), lifecycle=lifecycle, caller=str(raw.get("caller") or ""),
                    generation_policy=policy, deprecated_since=str(raw.get("deprecated_since") or ""),
                    replacement=str(raw.get("replacement") or ""), new_callers_forbidden=bool(raw.get("new_callers_forbidden", False)),
                    removal_condition=str(raw.get("removal_condition") or ""),
                ))
            except KeyError as exc:
                raise PromptRegistryError(f"PromptSpec 缺少字段: {exc.args[0]}") from exc
        production = [s for s in specs if s.lifecycle == "production"]
        for prompt_id in CONTRACT_BINDINGS:
            matches = [s for s in production if s.id == prompt_id]
            if len(matches) != 1:
                raise PromptRegistryError(f"production prompt 数量不正确: {prompt_id}")
        return cls(tuple(specs), root=root)

    def get(self, prompt_id: str, version: str | None = None) -> PromptSpec:
        matches = [s for s in self._specs if s.id == prompt_id and (version is None or s.version == version)]
        if len(matches) != 1:
            raise PromptRegistryError(f"prompt 不可唯一解析: {prompt_id}@{version or '*'}")
        spec = matches[0]
        if spec.lifecycle != "production" and version is None:
            raise PromptRegistryError("candidate/retired prompt 不可作为 production contract")
        return spec

    def inventory(self) -> tuple[PromptSpec, ...]:
        return self._specs


__all__ = ["GenerationPolicy", "PromptRegistry", "PromptRegistryError", "PromptSpec"]
