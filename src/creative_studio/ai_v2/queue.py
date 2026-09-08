"""Small in-process FIFO queue for bounded AI generation concurrency."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass
class GenerationTicket(Generic[T]):
    ticket_id: str
    _queue: "GenerationQueue[T]"
    _future: Future[T]
    _sequence: int

    def status(self) -> str:
        return self._queue._status(self.ticket_id)

    def position(self) -> int:
        return self._queue._position(self.ticket_id)

    def result(self, timeout: float | None = None) -> T:
        return self._future.result(timeout=timeout)


class GenerationQueue(Generic[T]):
    def __init__(self, *, max_running: int = 6) -> None:
        if max_running < 1:
            raise ValueError("max_running must be positive")
        self.max_running = max_running
        self._executor = ThreadPoolExecutor(max_workers=max_running, thread_name_prefix="ai-v2")
        self._lock = threading.Lock()
        self._states: dict[str, str] = {}
        self._sequences: dict[str, int] = {}
        self._next_sequence = 0
        self._active_count = 0

    def submit(self, function: Callable[[], T]) -> GenerationTicket[T]:
        ticket_id = uuid.uuid4().hex
        with self._lock:
            sequence = self._next_sequence
            self._next_sequence += 1
            immediate = self._active_count < self.max_running
            self._states[ticket_id] = "running" if immediate else "queued"
            if immediate:
                self._active_count += 1
            self._sequences[ticket_id] = sequence

        def run() -> T:
            with self._lock:
                if self._states[ticket_id] == "queued":
                    self._states[ticket_id] = "running"
                    self._active_count += 1
            try:
                result = function()
            except BaseException:
                with self._lock:
                    self._states[ticket_id] = "failed"
                    self._active_count -= 1
                raise
            else:
                with self._lock:
                    self._states[ticket_id] = "success"
                    self._active_count -= 1
                return result

        future = self._executor.submit(run)
        return GenerationTicket(ticket_id, self, future, sequence)

    def snapshot(self, ticket_id: str) -> dict[str, int | str] | None:
        with self._lock:
            status = self._states.get(ticket_id)
            if status is None:
                return None
            position = self._position_locked(ticket_id)
            return {"ticket_id": ticket_id, "status": status, "position": position}

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {
                "running": sum(status == "running" for status in self._states.values()),
                "waiting": sum(status == "queued" for status in self._states.values()),
                "capacity": self.max_running,
            }

    def _status(self, ticket_id: str) -> str:
        with self._lock:
            return self._states.get(ticket_id, "unknown")

    def _position(self, ticket_id: str) -> int:
        with self._lock:
            return self._position_locked(ticket_id)

    def _position_locked(self, ticket_id: str) -> int:
        sequence = self._sequences.get(ticket_id)
        if sequence is None or self._states.get(ticket_id) != "queued":
            return 0
        return 1 + sum(
            1
            for other_id, other_sequence in self._sequences.items()
            if other_sequence < sequence and self._states.get(other_id) == "queued"
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)


__all__ = ["GenerationQueue", "GenerationTicket"]
