"""Framework-neutral v2 HTTP route adapter."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .application import AiV2Application, AiV2ApplicationError
from .store import AiV2StoreConflict
from .queue import GenerationQueue, GenerationTicket


@dataclass
class _QueuedGeneration:
    project_id: int
    ticket: GenerationTicket[dict[str, Any]]


class AiV2HttpApi:
    def __init__(self, application: AiV2Application) -> None:
        self.application = application
        self._generation_queue = GenerationQueue(max_running=6)
        self._generation_tickets: dict[str, _QueuedGeneration] = {}

    def dispatch(self, method: str, path: str, body: Mapping[str, Any] | None, *, authenticated: bool = True) -> tuple[int, dict[str, Any]]:
        trace_id = uuid.uuid4().hex
        if not authenticated:
            return 401, {"error_code": "unauthorized", "phase": "authorization", "retryable": False, "trace_id": trace_id}
        try:
            if method == "POST":
                match = re.fullmatch(r"/api/v2/projects/(\d+)/generate", path)
                if match:
                    project_id = int(match.group(1))
                    ticket = self._generation_queue.submit(
                        lambda: self._run_generation(project_id, body or {})
                    )
                    self._generation_tickets[ticket.ticket_id] = _QueuedGeneration(project_id, ticket)
                    if self._generation_queue.snapshot(ticket.ticket_id)["position"] == 0:
                        result = ticket.result()
                        if result.get("ok"):
                            return 200, result["result"]
                        return 422, result
                    return 202, {"queue": self._queue_view(ticket)}
                match = re.fullmatch(r"/api/v2/schemes/(\d+)/image", path)
                if match:
                    view = self.application.image(int(match.group(1)))
                    return (200 if view.status == "success" else 202), self._view(view)
                match = re.fullmatch(r"/api/v2/schemes/(\d+)/frames/(\d+)/image", path)
                if match:
                    view = self.application.frame_image(int(match.group(1)), int(match.group(2)))
                    return (200 if view.status == "success" else 202), self._view(view)
                match = re.fullmatch(r"/api/v2/projects/(\d+)/adopt", path)
                if match:
                    raw_scheme_id = (body or {}).get("scheme_id")
                    if isinstance(raw_scheme_id, bool) or not isinstance(raw_scheme_id, (int, str)) or not str(raw_scheme_id).isdigit():
                        raise AiV2ApplicationError("invalid_scheme_id", "scheme_id is required", phase="input", field_path="$.scheme_id")
                    return 200, self.application.adopt(int(match.group(1)), int(raw_scheme_id))
            if method == "GET":
                if path == "/api/v2/queue":
                    return 200, {"queue": self._generation_queue.summary()}
                match = re.fullmatch(r"/api/v2/queue/([a-f0-9]{32})", path)
                if match:
                    return self._queue_status(match.group(1))
                match = re.fullmatch(r"/api/v2/projects/(\d+)/history", path)
                if match:
                    return 200, self.application.history(int(match.group(1)))
                match = re.fullmatch(r"/api/v2/runs/(\d+)", path)
                if match:
                    return 200, self.application.run(0, int(match.group(1)))
                match = re.fullmatch(r"/api/v2/image-attempts/(\d+)", path)
                if match:
                    return 200, self.application.image_attempt(int(match.group(1)))
                match = re.fullmatch(r"/api/v2/projects/(\d+)/adoption", path)
                if match:
                    adoption = self.application.adoption(int(match.group(1)))
                    return 200, adoption or {"project_id": int(match.group(1)), "adoption": None}
            return 404, {"error_code": "not_found", "phase": "routing", "retryable": False, "trace_id": trace_id}
        except AiV2ApplicationError as exc:
            status = 503 if exc.retryable and exc.phase == "image" else 502 if exc.error_code == "provider_auth_failed" else 409 if exc.error_code in {"frame_order_conflict", "batch_conflict", "image_already_successful"} else 422 if exc.phase == "input" else 404 if exc.error_code.endswith("_not_found") else 400
            return status, {"error_code": exc.error_code, "phase": exc.phase, "retryable": exc.retryable, "trace_id": trace_id, "field_path": exc.field_path}
        except AiV2StoreConflict:
            return 409, {"error_code": "state_conflict", "phase": "image", "retryable": False, "trace_id": trace_id}

    def project_id_for_queue_ticket(self, ticket_id: str) -> int:
        queued = self._generation_tickets.get(ticket_id)
        if queued is None:
            raise AiV2ApplicationError("queue_ticket_not_found", "排队任务不存在", phase="queue")
        return queued.project_id

    def _run_generation(self, project_id: int, body: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return {"ok": True, "result": self.application.generate(project_id, body)}
        except AiV2ApplicationError as exc:
            return {
                "ok": False,
                "error_code": exc.error_code,
                "phase": exc.phase,
                "retryable": exc.retryable,
                "field_path": exc.field_path,
            }

    def _queue_view(self, ticket: GenerationTicket[dict[str, Any]]) -> dict[str, Any]:
        snapshot = self._generation_queue.snapshot(ticket.ticket_id) or {
            "ticket_id": ticket.ticket_id,
            "status": "unknown",
            "position": 0,
        }
        return {
            "ticket_id": snapshot["ticket_id"],
            "status": snapshot["status"],
            "position": snapshot["position"],
        }

    def _queue_status(self, ticket_id: str) -> tuple[int, dict[str, Any]]:
        queued = self._generation_tickets.get(ticket_id)
        if queued is None:
            return 404, {"error_code": "queue_ticket_not_found", "phase": "queue", "retryable": False}
        view = self._queue_view(queued.ticket)
        if view["status"] == "success" and queued.ticket._future.done():
            result = queued.ticket.result()
            if result.get("ok"):
                return 200, {"queue": view, **result["result"]}
            return 422, {"queue": view, **result}
        return 202, {"queue": view}

    @staticmethod
    def _view(view) -> dict[str, Any]:
        result = {"attempt_id": view.attempt_id, "status": view.status}
        if view.image_url:
            result["image_url"] = view.image_url
        if view.error_code:
            result["error_code"] = view.error_code
        return result


__all__ = ["AiV2HttpApi"]
