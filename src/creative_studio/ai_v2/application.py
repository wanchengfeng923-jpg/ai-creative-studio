"""AI v2 application facade and dependency composition."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from .carousel_visual import CarouselTextUseCase, CarouselTextUseCaseError
from .image_worker import ImageWorker
from .input_contract import AiV2Input, InputContractError, normalize_input, resolve_use_case
from .model_ports import (
    ImageArtifact,
    ImageContinuation,
    ImageModelPort,
    ImageRequest,
    ImageSessionCursor,
    ImageSubmission,
    ReconcileRequest,
    ReconcileResult,
    TextModelPort,
    TextRequest,
    TextResponse,
    TextSession,
)
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


class CandidateTextModel(TextModelPort):
    """Deterministic candidate-only text port for the local v2 entry point.

    This is deliberately not a production Prompt caller: it creates schema-valid
    placeholder candidates without reading credentials or making network calls.
    A reviewed provider port can be injected at the composition root later.
    """

    def __init__(self) -> None:
        self.start_calls: list[TextRequest] = []

    def start_text(self, request: TextRequest) -> TextResponse:
        self.start_calls.append(request)
        index = len(self.start_calls)
        if request.prompt_id.endswith("narrative"):
            payload: dict[str, Any] = {
                "schema_version": "narrative-text-v1",
                "items": [
                    {
                        "story": f"候选故事 {item}",
                        "hooks": [
                            {"text": "候选钩子一", "scenes": ["场景一", "场景二", "场景三"]},
                            {"text": "候选钩子二", "scenes": ["场景四", "场景五", "场景六"]},
                        ],
                    }
                    for item in range(1, 6)
                ],
            }
        elif request.prompt_id.endswith("carousel"):
            payload = {
                "schema_version": "carousel-text-v1",
                "items": [
                    {
                        "title": f"候选轮播方案 {item}",
                        "core_idea": "候选核心创意",
                        "ad_copy": "候选广告文案",
                        "frames": [
                            {"index": 1, "description": "候选首帧"},
                            {"index": 2, "description": "候选续帧"},
                        ],
                        "execution": {
                            "continuity_rules": ["保持主体和色彩连续"],
                            "image_prompts": [
                                {"index": 1, "prompt": "candidate frame one"},
                                {"index": 2, "prompt": "candidate frame two"},
                            ],
                        },
                    }
                    for item in range(1, 4)
                ],
            }
        else:
            payload = {
                "schema_version": "static-text-v1",
                "items": [
                    {
                        "title": f"候选展示方案 {item}",
                        "core_idea": "候选核心创意",
                        "ad_copy": "候选广告文案",
                        "image_description": "候选画面描述",
                        "execution": {"image_prompt": "candidate static image"},
                    }
                    for item in range(1, 4)
                ],
            }
        return TextResponse(
            raw_text=json.dumps(payload, ensure_ascii=False),
            session=TextSession(f"candidate-text-{index}", f"candidate-text-{index}", f"candidate-message-{index}"),
            usage_source="unavailable",
        )


class CandidateImageModel(ImageModelPort):
    """Deterministic 1x1 PNG image port used until a gateway is explicitly approved."""

    _PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )

    @staticmethod
    def _submission(request: ImageRequest, revision: int) -> ImageSubmission:
        cursor = ImageSessionCursor("candidate", request.image_session_key, request.request_key, revision)
        artifact = ImageArtifact(CandidateImageModel._PNG, "image/png", hashlib.sha256(CandidateImageModel._PNG).hexdigest())
        return ImageSubmission("success", None, cursor, artifact, None)

    def start_image_session(self, request: ImageRequest) -> ImageSubmission:
        return self._submission(request, 1)

    def continue_image_session(self, request: ImageContinuation) -> ImageSubmission:
        return self._submission(request.request, request.cursor.revision + 1)

    def reconcile(self, request: ReconcileRequest) -> ReconcileResult:
        return ReconcileResult("unknown", request.provider_job_id, request.cursor, None, "candidate_state_unknown")


class AiV2Application:
    """Own v2 use cases; no legacy generation service is consulted."""

    def __init__(self, store: AiV2Store, *, text_model: TextModelPort, image_model: ImageModelPort | None = None, registry: AiV2PromptRegistry | None = None, project_provider: Callable[[int], Mapping[str, Any] | None] | None = None) -> None:
        self.store = store
        self.registry = registry or AiV2PromptRegistry()
        self.project_provider = project_provider or (lambda project_id: {"id": project_id, "script_type": "展示类"})
        self.image_worker = ImageWorker(store, image_model) if image_model is not None else None
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
        return {"schema_version": "ai-v2-history-v1", "runs": [self._public_run_with_details(run) for run in self.store.list_public_runs(project_id)]}

    def run(self, project_id: int, run_id: int) -> dict[str, Any]:
        try:
            return self._public_run_with_details(self.store.read_public_run_by_id(run_id))
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
        if state["status"] in {"pending", "generating"} and self.image_worker is not None:
            self.image_worker.submit(attempt_id)
            state = self.store.read_image_attempt_state(attempt_id)
        return public_image_state({**state, "image_url": f"/api/v2/image-attempts/{attempt_id}/image" if state.get("artifact_id") else None})

    def project_id_for_run(self, run_id: int) -> int:
        try:
            return int(self.store.read_public_run_by_id(run_id)["project_id"])
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("run_not_found", "run not found", phase="lookup") from exc

    def project_id_for_scheme(self, scheme_id: int) -> int:
        try:
            scheme = self.store.read_scheme(scheme_id)
            return self.project_id_for_run(int(scheme["run_id"]))
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("scheme_not_found", "scheme not found", phase="lookup") from exc

    def project_id_for_attempt(self, attempt_id: int) -> int:
        try:
            state = self.store.read_image_attempt_state(attempt_id)
            return self.project_id_for_scheme(int(state["scheme_id"]))
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("attempt_not_found", "attempt not found", phase="lookup") from exc

    def image_bytes(self, attempt_id: int) -> tuple[bytes, str]:
        """Return a completed v2 artifact only after the handler has authorized it."""

        try:
            state = self.store.read_image_attempt_state(attempt_id)
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("attempt_not_found", "attempt not found", phase="lookup") from exc
        artifact_id = state.get("artifact_id")
        if not isinstance(artifact_id, int):
            raise AiV2ApplicationError("image_not_found", "image not found", phase="lookup")
        artifact = self.store.read_artifact(attempt_id)
        if artifact is None or artifact[1] not in {"image/png", "image/jpeg", "image/webp"}:
            raise AiV2ApplicationError("image_not_found", "image not found", phase="lookup")
        return artifact

    def _public_run_with_details(self, run: Mapping[str, Any]) -> dict[str, Any]:
        enriched = dict(run)
        schemes = []
        for scheme in self.store.list_schemes(int(run["run_id"])):
            item = dict(scheme)
            item["use_case"] = run["use_case"]
            if run["use_case"] == "carousel":
                frames = []
                for frame in self.store.list_frames(int(scheme["scheme_id"])):
                    current = dict(frame)
                    key = f"{scheme['scheme_version']}:frame:{frame['frame_index']}"
                    attempt = self.store.find_image_attempt(int(scheme["scheme_id"]), int(frame["frame_index"]), key)
                    current["image_state"] = self.store.read_image_attempt_state(attempt.attempt_id) if attempt else {"status": frame["status"], "attempt_no": 0}
                    frames.append(current)
                item["frames"] = frames
            else:
                frame = self.store.list_frames(int(scheme["scheme_id"]))[0]
                key = f"{scheme['scheme_version']}:frame:1"
                attempt = self.store.find_image_attempt(int(scheme["scheme_id"]), 1, key)
                item["image_state"] = self.store.read_image_attempt_state(attempt.attempt_id) if attempt else {"status": frame["status"], "attempt_no": 0}
            schemes.append(item)
        enriched["schemes"] = schemes
        return public_run(enriched)

    def adopt(self, project_id: int, scheme_id: int) -> dict[str, Any]:
        try:
            scheme = self.store.read_scheme(scheme_id)
        except AiV2StoreConflict as exc:
            raise AiV2ApplicationError("scheme_not_found", "scheme not found", phase="lookup") from exc
        if int(self.project_id_for_scheme(scheme_id)) != int(project_id):
            raise AiV2ApplicationError("scheme_not_found", "scheme not found", phase="lookup")
        snapshot = public_run({"use_case": scheme["use_case"], "items": [scheme["canonical"]]})["items"][0]
        self.store.save_adoption(project_id, scheme_id, scheme["scheme_version"], snapshot)
        result = self.store.read_adoption(project_id)
        if result is None:
            raise AiV2ApplicationError("adoption_not_found", "adoption not found", phase="lookup")
        return result

    def adoption(self, project_id: int) -> dict[str, Any] | None:
        return self.store.read_adoption(project_id)


__all__ = ["AiV2Application", "AiV2ApplicationError", "CandidateImageModel", "CandidateTextModel"]
