"""AI v2 application facade and dependency composition."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .carousel_visual import CarouselTextUseCase, CarouselTextUseCaseError
from .input_contract import AiV2Input, InputContractError, normalize_input, resolve_use_case
from .model_ports import ImageModelPort, TextModelPort
from .narrative import NarrativeTextUseCase, NarrativeTextUseCaseError
from .prompt_registry import AiV2PromptRegistry
from .projection import public_image_state, public_run
from .static_visual import StaticTextUseCase, StaticTextUseCaseError
from .store import AiV2Store, AiV2StoreConflict, ImageAttemptView


class AiV2ApplicationError(RuntimeError):
    def __init__(self, error_code: str, message: str, *, phase: str = "application", retryable: bool = False, field_path: str = "$") -> None:
        super().__init__(message)
        self.error_code = error_code
        self.phase = phase
        self.retryable = retryable
        self.field_path = field_path


class AiV2Application:
    """Own v2 use cases; no legacy generation service is consulted."""

    def __init__(self, store: AiV2Store, *, text_model: TextModelPort, image_model: ImageModelPort | None = None, registry: AiV2PromptRegistry | None = None, project_provider: Callable[[int], Mapping[str, Any] | None] | None = None) -> None:
        self.store = store
        self.registry = registry or AiV2PromptRegistry()
        self.project_provider = project_provider or (lambda project_id: {"id": project_id, "script_type": "展示类"})
        self.narrative = NarrativeTextUseCase(self.registry, text_model, store)
        self.static = StaticTextUseCase(self.registry, text_model, store, image_model=image_model)
        self.carousel = CarouselTextUseCase(self.registry, text_model, store, image_model=image_model)

    def _input(self, body: Mapping[str, Any]) -> AiV2Input:
        try:
            return normalize_input(body)
        except InputContractError as exc:
            raise AiV2ApplicationError(exc.reason_code, str(exc), phase="input", field_path=exc.field_path) from exc

    def _use_case(self, project_id: int, input_value: AiV2Input) -> str:
        project = self.project_provider(project_id)
        if project is None:
            raise AiV2ApplicationError("project_not_found", "project not found", phase="authorization")
        try:
            return resolve_use_case(str(project.get("script_type") or project.get("kind") or ""), input_value.creative_tags)
        except InputContractError as exc:
            raise AiV2ApplicationError(exc.reason_code, str(exc), phase="input", field_path=exc.field_path) from exc

    def generate(self, project_id: int, body: Mapping[str, Any], batch_index: int = 1) -> dict[str, Any]:
        input_value = self._input(body)
        use_case = self._use_case(project_id, input_value)
        try:
            if use_case == "narrative":
                return self.narrative.generate(project_id, input_value, batch_index)
            if use_case == "carousel":
                return self.carousel.generate(project_id, input_value, batch_index)
            return self.static.generate(project_id, input_value, batch_index)
        except (NarrativeTextUseCaseError, StaticTextUseCaseError, CarouselTextUseCaseError) as exc:
            raise AiV2ApplicationError(exc.error_code, str(exc), phase="text", retryable=exc.retryable, field_path=exc.field_path) from exc

    def history(self, project_id: int) -> dict[str, Any]:
        if self.project_provider(project_id) is None:
            raise AiV2ApplicationError("project_not_found", "project not found", phase="authorization")
        return {"schema_version": "ai-v2-history-v1", "runs": [public_run(run) for run in self.store.list_public_runs(project_id)]}

    def run(self, project_id: int, run_id: int) -> dict[str, Any]:
        try:
            return public_run(self.store.read_public_run_by_id(run_id))
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("run_not_found", "run not found", phase="lookup") from exc

    def image(self, scheme_id: int) -> ImageAttemptView:
        try:
            scheme = self.store.read_scheme(scheme_id)
            if scheme["use_case"] != "static":
                raise AiV2ApplicationError("invalid_use_case", "scheme is not static", phase="image")
            return self.static.request_image(scheme_id)
        except StaticTextUseCaseError as exc:
            raise AiV2ApplicationError(exc.error_code, str(exc), phase="image", retryable=exc.retryable) from exc

    def frame_image(self, scheme_id: int, frame_index: int) -> ImageAttemptView:
        try:
            return self.carousel.request_frame(scheme_id, frame_index)
        except CarouselTextUseCaseError as exc:
            raise AiV2ApplicationError(exc.error_code, str(exc), phase="image", retryable=exc.retryable) from exc

    def image_attempt(self, attempt_id: int) -> dict[str, Any]:
        try:
            state = self.store.read_image_attempt_state(attempt_id)
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("attempt_not_found", "image attempt not found", phase="lookup") from exc
        return public_image_state({**state, "image_url": f"/api/v2/image-attempts/{attempt_id}/image" if state.get("artifact_id") else None})


__all__ = ["AiV2Application", "AiV2ApplicationError"]
