"""AI v2 静态展示文字用例和按需单图入口。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .input_contract import AiV2Input, fingerprint
from .model_ports import (
    ImageContinuation,
    ImageModelPort,
    ImageRequest,
    ImageSessionCursor,
    ImageSubmission,
    ReconcileResult,
    ReconcileRequest,
    TextModelPort,
    TextRequest,
)
from .prompt_registry import AiV2PromptRegistry, compile_prompt
from .projection import public_image_state, public_run
from .schema import SchemaViolation, load_schema, validate_json
from .store import AiV2Store, AiV2StoreConflict, ImageAttempt, ImageAttemptView


class StaticTextUseCaseError(RuntimeError):
    """静态 v2 文字或图片请求失败。"""

    def __init__(self, error_code: str, message: str, *, field_path: str = "$", retryable: bool = True) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.field_path = field_path
        self.retryable = retryable


def _tags_json(value: Mapping[str, tuple[str, ...]]) -> str:
    return json.dumps({key: list(values) for key, values in value.items()}, ensure_ascii=False, separators=(",", ":"))


class StaticTextUseCase:
    """独立静态展示用例；图片只在 request_image 被调用时执行。"""

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
        """一次文字调用保存三案，图片保持 pending。"""

        spec = self.registry.get("creative.ai_v2.static", "v1")
        input_fingerprint = fingerprint(input_value, "static", prompt_version=spec.version)
        try:
            run = self.store.reserve_run(project_id, "static", input_fingerprint, batch_index, aspect_ratio=input_value.aspect_ratio)
        except AiV2StoreConflict as exc:
            raise StaticTextUseCaseError("batch_conflict", str(exc), retryable=False) from exc
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
            except (TypeError, json.JSONDecodeError) as exc:
                self.store.fail_run(run.run_id, "model_output_invalid")
                raise StaticTextUseCaseError("model_output_invalid", "static output is not JSON") from exc
            try:
                validate_json(canonical, load_schema("static-text", "v1"))
            except SchemaViolation as exc:
                self.store.fail_run(run.run_id, "model_output_invalid")
                raise StaticTextUseCaseError("model_output_invalid", "static output does not match schema", field_path=exc.field_path) from exc
            self.store.save_text_result(run.run_id, canonical, response.session)
            return self._public_run(run.run_id, project_id)
        except StaticTextUseCaseError:
            raise
        except Exception as exc:
            try:
                self.store.fail_run(run.run_id, "provider_unavailable")
            except Exception:
                pass
            raise StaticTextUseCaseError("provider_unavailable", "text provider unavailable") from exc

    def _public_run(self, run_id: int, project_id: int) -> dict[str, Any]:
        record = self.store.read_public_run(project_id, run_id)
        schemes: list[dict[str, Any]] = []
        for scheme in self.store.list_schemes(run_id):
            frames = self.store.list_frames(scheme["scheme_id"])
            frame = frames[0] if frames else None
            attempt_state: dict[str, Any] = {"status": frame["status"] if frame else "pending", "attempt_no": 0}
            if frame:
                attempt = self.store.find_image_attempt(
                    scheme["scheme_id"], frame["frame_index"], scheme["scheme_version"] + f":frame:{frame['frame_index']}"
                )
                if attempt is not None:
                    attempt_state = self.store.read_image_attempt_state(attempt.attempt_id)
            scheme["use_case"] = "static"
            scheme["image_state"] = attempt_state
            schemes.append(scheme)
        record["schemes"] = schemes
        return public_run(record)

    def request_image(self, scheme_id: int) -> ImageAttemptView:
        """按需提交静态方案唯一图片，并在失败重试前完成供应商对账。"""

        if self.image_model is None:
            raise StaticTextUseCaseError("provider_unavailable", "image provider unavailable", retryable=True)
        scheme = self.store.read_scheme(scheme_id)
        if scheme["use_case"] != "static":
            raise StaticTextUseCaseError("invalid_use_case", "scheme is not static", retryable=False)
        frame = self.store.read_frame(scheme_id, 1)
        session_key = f"v2-run-{scheme['run_id']}-scheme-{scheme_id}"
        request_key = f"{scheme['scheme_version']}:frame:1"
        session = self.store.find_image_session(scheme_id, session_key)
        attempt = self.store.find_image_attempt(scheme_id, 1, request_key)
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
            session, owns_session = self.store.claim_image_session(scheme_id, session_key)
            if not owns_session:
                if session.cursor is None:
                    raise StaticTextUseCaseError("provider_state_unknown", "image session is still initializing")
            else:
                submission = self.image_model.start_image_session(ImageRequest(
                    scheme["scheme_version"],
                    1,
                    frame["execution_prompt"],
                    session_key,
                    request_key,
                    scheme["aspect_ratio"],
                    None,
                    provider_request_id=f"{request_key}:attempt:1",
                ))
                if submission.state == "unknown":
                    self.store.release_image_session_claim(session.session_id)
                    raise StaticTextUseCaseError(
                        submission.error_code or "provider_state_unknown",
                        "image provider state is unknown",
                        retryable=(submission.error_code or "provider_state_unknown") in {"provider_unavailable", "provider_state_unknown"},
                    )
                session = self.store.initialize_image_session(session.session_id, submission.cursor, submission.provider_job_id)
                attempt = self.store.reserve_image_attempt(scheme_id, 1, request_key)
                self._apply_submission(attempt, submission)
                return self._view(attempt.attempt_id)

        if attempt is None:
            orphan = ReconcileResult("terminal_failure", session.provider_job_id, session.cursor, None, None)
            if not terminal_failure_confirmed:
                orphan = self.image_model.reconcile(ReconcileRequest(session_key, request_key, session.cursor, session.provider_job_id))
            if orphan.state == "unknown":
                raise StaticTextUseCaseError("provider_state_unknown", "image state is unknown", retryable=True)
            attempt = self.store.reserve_image_attempt(scheme_id, 1, request_key)
            if orphan.state in {"success", "working"}:
                self._apply_reconcile(attempt, orphan)
                return self._view(attempt.attempt_id)

        cursor = session.cursor
        if cursor is None:
            raise StaticTextUseCaseError("provider_protocol_invalid", "image session cursor unavailable")
        submission = self.image_model.continue_image_session(ImageContinuation(
            ImageRequest(
                scheme["scheme_version"],
                1,
                frame["execution_prompt"],
                session_key,
                request_key,
                scheme["aspect_ratio"],
                None,
                provider_request_id=f"{request_key}:attempt:{attempt.attempt_no}",
            ),
            cursor,
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

    def _apply_reconcile(self, attempt: ImageAttempt, result: Any) -> None:
        if result.state == "success" and (result.artifact is None or result.cursor is None):
            self.store.fail_image_attempt(attempt.attempt_id, "provider_protocol_invalid", False)
            return
        self.store.reconcile_image_attempt(attempt.attempt_id, result)

    def _view(self, attempt_id: int) -> ImageAttemptView:
        state = self.store.read_image_attempt_state(attempt_id)
        image_url = f"/api/v2/image-attempts/{attempt_id}/image" if state.get("artifact_id") else None
        return ImageAttemptView(attempt_id, state["status"], image_url, state.get("error_code"))


__all__ = ["StaticTextUseCase", "StaticTextUseCaseError"]
