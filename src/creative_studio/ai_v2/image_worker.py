"""AI v2 image submission, reconciliation, and atomic completion worker."""

from __future__ import annotations

from .model_ports import ImageContinuation, ImageModelPort, ImageRequest, ReconcileRequest, ReconcileResult
from .store import AiV2Store, AiV2StoreConflict, ImageAttempt


class ImageWorker:
    """Process one reserved attempt without creating duplicate sessions."""

    def __init__(self, store: AiV2Store, image_model: ImageModelPort) -> None:
        self.store = store
        self.image_model = image_model

    def submit(self, attempt_id: int) -> None:
        state = self.store.read_image_attempt_state(attempt_id)
        if state["status"] == "success":
            return
        scheme = self.store.read_scheme(state["scheme_id"])
        frame = self.store.read_frame(state["scheme_id"], state["frame_index"])
        session = self.store.find_image_session_by_id(state["image_session_id"])
        if session is None:
            raise AiV2StoreConflict("image session is missing for attempt")
        session_key = session.session_key

        attempt = self.store.find_image_attempt(state["scheme_id"], state["frame_index"], state["request_key"])
        if attempt is None:
            raise AiV2StoreConflict("image attempt is missing")

        provider_job_id = attempt.provider_job_id or session.provider_job_id
        if attempt.status in {"pending", "generating"} and provider_job_id:
            result = self.image_model.reconcile(ReconcileRequest(
                session_key,
                attempt.request_key,
                session.cursor,
                provider_job_id,
            ))
            self._apply_reconcile(attempt, result)
            return

        if attempt.status == "failed":
            result = self.image_model.reconcile(ReconcileRequest(session_key, attempt.request_key, session.cursor, session.provider_job_id))
            if result.state in {"success", "working"}:
                self._apply_reconcile(attempt, result)
                return
            if result.state != "terminal_failure":
                self.store.reconcile_image_attempt(attempt.attempt_id, result)
                return
            attempt = self.store.reserve_image_attempt(state["scheme_id"], state["frame_index"], attempt.request_key)
            state = self.store.read_image_attempt_state(attempt.attempt_id)

        if session.cursor is None:
            result = self.image_model.reconcile(ReconcileRequest(session_key, attempt.request_key, None, attempt.provider_job_id))
            if result.state != "terminal_failure":
                self._apply_reconcile(attempt, result)
                return
            attempt = self.store.reserve_image_attempt(state["scheme_id"], state["frame_index"], attempt.request_key)
            session = self.store.find_image_session_by_id(attempt.image_session_id)
            if session is None or session.cursor is None:
                raise AiV2StoreConflict("image session cursor unavailable")

        reference = None
        if scheme["use_case"] == "carousel" and state["frame_index"] > 1:
            reference = self.store.read_artifact_for_frame(state["scheme_id"], state["frame_index"] - 1)
        submission = self.image_model.continue_image_session(ImageContinuation(
            ImageRequest(
                scheme["scheme_version"],
                state["frame_index"],
                frame["execution_prompt"],
                session_key,
                attempt.request_key,
                scheme["aspect_ratio"],
                reference,
                provider_request_id=f"{attempt.request_key}:attempt:{attempt.attempt_no}",
            ),
            session.cursor,
        ))
        self._apply_submission(attempt, submission)

    def _apply_submission(self, attempt: ImageAttempt, submission) -> None:
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


__all__ = ["ImageWorker"]
