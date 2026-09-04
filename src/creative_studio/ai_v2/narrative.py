"""AI v2 叙事文字用例：一次候选 Prompt 调用、schema 校验和公开投影。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .input_contract import AiV2Input, fingerprint
from .model_ports import TextModelPort, TextRequest
from .prompt_registry import AiV2PromptRegistry, compile_prompt
from .projection import public_run
from .schema import SchemaViolation, load_schema, validate_json
from .store import AiV2Store, AiV2StoreConflict


class NarrativeTextUseCaseError(RuntimeError):
    """叙事 v2 生成失败，公开层可按稳定 code 处理。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        field_path: str = "$",
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.field_path = field_path
        self.retryable = retryable


def _tags_json(value: Mapping[str, tuple[str, ...]]) -> str:
    return json.dumps({key: list(values) for key, values in value.items()}, ensure_ascii=False, separators=(",", ":"))


class NarrativeTextUseCase:
    """独立叙事用例，不依赖旧 AI builder/validator/存储。"""

    def __init__(
        self,
        registry: AiV2PromptRegistry,
        text_model: TextModelPort,
        store: AiV2Store,
    ) -> None:
        self.registry = registry
        self.text_model = text_model
        self.store = store

    def generate(self, project_id: int, input_value: AiV2Input, batch_index: int) -> dict[str, Any]:
        """为一个批次执行一次文字调用并返回公开叙事 DTO。"""

        spec = self.registry.get("creative.ai_v2.narrative", "v1")
        input_fingerprint = fingerprint(input_value, "narrative", prompt_version=spec.version)
        try:
            run = self.store.reserve_run(project_id, "narrative", input_fingerprint, batch_index, aspect_ratio=input_value.aspect_ratio)
        except AiV2StoreConflict as exc:
            raise NarrativeTextUseCaseError("batch_conflict", str(exc), retryable=False) from exc
        try:
            prompt = compile_prompt(spec, {
                "task_description": input_value.task_description,
                "aspect_ratio": input_value.aspect_ratio,
                "creative_tags": _tags_json(input_value.creative_tags),
            })
            response = self.text_model.start_text(TextRequest(
                prompt=prompt,
                prompt_id=spec.prompt_id,
                schema_version=spec.output_schema,
                model="candidate",
                idempotency_key=f"v2:{project_id}:{input_fingerprint}:{batch_index}:{run.run_id}",
            ))
            try:
                canonical = json.loads(response.raw_text)
            except (TypeError, json.JSONDecodeError) as exc:
                self.store.fail_run(run.run_id, "model_output_invalid")
                raise NarrativeTextUseCaseError("model_output_invalid", "narrative output is not JSON", retryable=True) from exc
            try:
                validate_json(canonical, load_schema("narrative-text", "v1"))
            except SchemaViolation as exc:
                self.store.fail_run(run.run_id, "model_output_invalid")
                raise NarrativeTextUseCaseError(
                    "model_output_invalid",
                    "narrative output does not match schema",
                    field_path=exc.field_path,
                    retryable=True,
                ) from exc
            self.store.save_text_result(run.run_id, canonical, response.session)
            return public_run(self.store.read_public_run(project_id, run.run_id))
        except NarrativeTextUseCaseError:
            raise
        except Exception as exc:
            try:
                self.store.fail_run(run.run_id, "provider_unavailable")
            except Exception:
                pass
            raise NarrativeTextUseCaseError("provider_unavailable", "text provider unavailable", retryable=True) from exc


__all__ = ["NarrativeTextUseCase", "NarrativeTextUseCaseError"]
