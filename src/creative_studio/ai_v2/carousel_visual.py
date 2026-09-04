"""AI v2 轮播文字规划和按序逐帧图片入口。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .input_contract import AiV2Input, fingerprint
from .model_ports import (
    ImageContinuation,
    ImageModelPort,
    ImageRequest,
    ImageSubmission,
    ReconcileRequest,
    ReconcileResult,
    TextModelPort,
    TextRequest,
)
from .prompt_registry import AiV2PromptRegistry, compile_prompt
from .projection import public_run
from .schema import SchemaViolation, load_schema, validate_json
from .store import AiV2Store, AiV2StoreConflict, ImageAttempt, ImageAttemptView


class CarouselTextUseCaseError(RuntimeError):
    """轮播 v2 规划或逐帧图片操作失败。"""

    def __init__(self, error_code: str, message: str, *, field_path: str = "$", retryable: bool = True) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.field_path = field_path
        self.retryable = retryable


def _tags_json(value: Mapping[str, tuple[str, ...]]) -> str:
    return json.dumps({key: list(values) for key, values in value.items()}, ensure_ascii=False, separators=(",", ":"))


def _requested_count(tags: Mapping[str, tuple[str, ...]]) -> int | None:
    values = tags.get("visual_carousel_count", ())
    if not values:
        raise CarouselTextUseCaseError("missing_carousel_count", "carousel count is required", retryable=False)
    selected = str(values[0]).strip()
    if selected.lower() in {"ai", "ai决定"}:
        return None
    try:
        count = int(selected)
    except ValueError as exc:
        raise CarouselTextUseCaseError("invalid_carousel_count", "carousel count is invalid", retryable=False) from exc
    if count not in range(2, 6):
        raise CarouselTextUseCaseError("invalid_carousel_count", "carousel count must be between 2 and 5", retryable=False)
    return count


class CarouselTextUseCase:
    """独立轮播用例；文字一次规划，图片每次只推进当前帧。"""

    def __init__(
        self,
        registry: AiV2PromptRegistry,
        text_model: TextModelPort,
        store: AiV2Store,
        *,
        image_model: ImageModelPort | None = None,
    ) -> None:
        self.registry = registry
        self.text_model = text_model
        self.store = store
        self.image_model = image_model

    def generate(self, project_id: int, input_value: AiV2Input, batch_index: int) -> dict[str, Any]:
        """一次规划调用保存三套路线和私有逐帧图片指令。"""

        requested_count = _requested_count(input_value.creative_tags)
        spec = self.registry.get("creative.ai_v2.carousel", "v1")
        input_fingerprint = fingerprint(input_value, "carousel", prompt_version=spec.version)
        try:
            run = self.store.reserve_run(project_id, "carousel", input_fingerprint, batch_index, aspect_ratio=input_value.aspect_ratio)
        except AiV2StoreConflict as exc:
            raise CarouselTextUseCaseError("batch_conflict", str(exc), retryable=False) from exc
        try:
            response = self.text_model.start_text(TextRequest(
                prompt=compile_prompt(spec, {
                    "task_description": input_value.task_description,
                    "aspect_ratio": input_value.aspect_ratio,
                    "creative_tags": _tags_json(input_value.creative_tags),
                }),
                prompt_id=spec.prompt_id,
                schema_version=spec.output_schema,
                model="candidate",
                idempotency_key=f"v2:{project_id}:{input_fingerprint}:{batch_index}:{run.run_id}",
            ))
            try:
                canonical = json.loads(response.raw_text)
                validate_json(canonical, load_schema("carousel-text", "v1"))
                if requested_count is not None:
                    for item in canonical["items"]:
                        if len(item["frames"]) != requested_count:
                            raise SchemaViolation("$.items[].frames", "frame_count_mismatch", "frame count does not match selected count")
            except (TypeError, json.JSONDecodeError) as exc:
                self.store.fail_run(run.run_id, "model_output_invalid")
                raise CarouselTextUseCaseError("model_output_invalid", "carousel output is not JSON") from exc
            except SchemaViolation as exc:
                self.store.fail_run(run.run_id, "model_output_invalid")
                raise CarouselTextUseCaseError("model_output_invalid", "carousel output does not match schema", field_path=exc.field_path) from exc
            self.store.save_text_result(run.run_id, canonical, response.session)
            return self._public_run(run.run_id, project_id)
        except CarouselTextUseCaseError:
            raise
        except Exception as exc:
            try:
                self.store.fail_run(run.run_id, "provider_unavailable")
            except Exception:
                pass
            raise CarouselTextUseCaseError("provider_unavailable", "text provider unavailable") from exc

    def _public_run(self, run_id: int, project_id: int) -> dict[str, Any]:
        record = self.store.read_public_run(project_id, run_id)
        schemes: list[dict[str, Any]] = []
        for scheme in self.store.list_schemes(run_id):
            states = []
            for frame in self.store.list_frames(scheme["scheme_id"]):
                request_key = scheme["scheme_version"] + f":frame:{frame['frame_index']}"
                attempt = self.store.find_image_attempt(scheme["scheme_id"], frame["frame_index"], request_key)
                states.append({
                    **frame,
                    "image_state": self.store.read_image_attempt_state(attempt.attempt_id) if attempt else {"status": frame["status"], "attempt_no": 0},
                })
            scheme["use_case"] = "carousel"
            scheme["frames"] = states
            schemes.append(scheme)
        record["schemes"] = schemes
        return public_run(record)

    def request_frame(self, scheme_id: int, frame_index: int) -> ImageAttemptView:
        """只生成当前允许的一帧，后续帧必须等待上一帧成功。"""

        if self.image_model is None:
            raise CarouselTextUseCaseError("provider_unavailable", "image provider unavailable")
        scheme = self.store.read_scheme(scheme_id)
        if scheme["use_case"] != "carousel":
            raise CarouselTextUseCaseError("invalid_use_case", "scheme is not carousel", retryable=False)
        if frame_index < 1:
            raise CarouselTextUseCaseError("invalid_frame", "frame index must be positive", retryable=False)
        if frame_index > 1 and self.store.read_frame(scheme_id, frame_index - 1)["status"] != "success":
            raise CarouselTextUseCaseError("frame_order_conflict", "previous frame must succeed first", retryable=False)
        frame = self.store.read_frame(scheme_id, frame_index)
        session_key = f"v2-run-{scheme['run_id']}-scheme-{scheme_id}"
        request_key = f"{scheme['scheme_version']}:frame:{frame_index}"
        session = self.store.find_image_session(scheme_id, session_key)
        attempt = self.store.find_image_attempt(scheme_id, frame_index, request_key)
        terminal_failure_confirmed = False

        if attempt is not None and attempt.status == "success":
            return self._view(attempt.attempt_id)
        if attempt is not None and attempt.status in {"pending", "generating"}:
            return self._view(attempt.attempt_id)
        if attempt is not None and attempt.status == "failed" and session is not None:
            reconcile = self.image_model.reconcile(ReconcileRequest(session_key, request_key, session.cursor, session.provider_job_id))
            if reconcile.state in {"success", "working"}:
                self.store.reconcile_image_attempt(attempt.attempt_id, reconcile)
                return self._view(attempt.attempt_id)
            if reconcile.state == "unknown":
                return self._view(attempt.attempt_id)
            terminal_failure_confirmed = reconcile.state == "terminal_failure"
            attempt = None

        if session is None:
            if frame_index != 1:
                raise CarouselTextUseCaseError("frame_order_conflict", "first frame must be generated first", retryable=False)
            submission = self.image_model.start_image_session(ImageRequest(
                scheme["scheme_version"],
                frame_index,
                frame["execution_prompt"],
                session_key,
                request_key,
                scheme["aspect_ratio"],
                None,
                provider_request_id=f"{request_key}:attempt:1",
            ))
            if submission.state == "unknown":
                raise CarouselTextUseCaseError(
                    submission.error_code or "provider_state_unknown",
                    "image provider state is unknown",
                )
            session = self.store.ensure_image_session(scheme_id, session_key, submission.cursor, submission.provider_job_id)
            attempt = self.store.reserve_image_attempt(scheme_id, frame_index, request_key)
            self._apply_submission(attempt, submission)
            return self._view(attempt.attempt_id)

        if attempt is None:
            orphan = ReconcileResult("terminal_failure", session.provider_job_id, session.cursor, None, None)
            if not terminal_failure_confirmed and frame_index == 1:
                orphan = self.image_model.reconcile(ReconcileRequest(session_key, request_key, session.cursor, session.provider_job_id))
            if orphan.state == "unknown":
                raise CarouselTextUseCaseError("provider_state_unknown", "image state is unknown")
            attempt = self.store.reserve_image_attempt(scheme_id, frame_index, request_key)
            if orphan.state in {"success", "working"}:
                self._apply_reconcile(attempt, orphan)
                return self._view(attempt.attempt_id)

        if session.cursor is None:
            raise CarouselTextUseCaseError("provider_protocol_invalid", "image session cursor unavailable")
        reference = self.store.read_artifact_for_frame(scheme_id, frame_index - 1) if frame_index > 1 else None
        submission = self.image_model.continue_image_session(ImageContinuation(
            ImageRequest(
                scheme["scheme_version"],
                frame_index,
                frame["execution_prompt"],
                session_key,
                request_key,
                scheme["aspect_ratio"],
                reference,
                provider_request_id=f"{request_key}:attempt:{attempt.attempt_no}",
            ),
            session.cursor,
        ))
        self._apply_submission(attempt, submission)
        return self._view(attempt.attempt_id)

    def _apply_submission(self, attempt: ImageAttempt, submission: ImageSubmission) -> None:
        if submission.state == "success":
            if submission.artifact is None or submission.cursor is None:
                self.store.fail_image_attempt(attempt.attempt_id, "provider_protocol_invalid", False)
                return
            self.store.complete_image_attempt_atomic(attempt.attempt_id, submission.artifact, submission.cursor)
        elif submission.state == "working":
            self._apply_reconcile(attempt, ReconcileResult("working", submission.provider_job_id, submission.cursor, None, None))
        elif submission.state == "terminal_failure":
            self.store.fail_image_attempt(attempt.attempt_id, submission.error_code or "image_generation_failed", True)

    def _apply_reconcile(self, attempt: ImageAttempt, result: ReconcileResult) -> None:
        if result.state == "success" and (result.artifact is None or result.cursor is None):
            self.store.fail_image_attempt(attempt.attempt_id, "provider_protocol_invalid", False)
            return
        self.store.reconcile_image_attempt(attempt.attempt_id, result)

    def _view(self, attempt_id: int) -> ImageAttemptView:
        state = self.store.read_image_attempt_state(attempt_id)
        image_url = f"/api/v2/image-attempts/{attempt_id}/image" if state.get("artifact_id") else None
        return ImageAttemptView(attempt_id, state["status"], image_url, state.get("error_code"))


__all__ = ["CarouselTextUseCase", "CarouselTextUseCaseError"]
