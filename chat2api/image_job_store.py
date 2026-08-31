"""Persistent state for asynchronous image gateway jobs."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


VALID_STATUSES = {"queued", "generating", "success", "failed"}


class ImageJobStore:
    def __init__(self, root: Path, now: Callable[[], float] = time.time) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.now = now
        self._lock = threading.RLock()

    def create(self, request_id: str) -> dict[str, Any]:
        normalized_request_id = str(request_id or "").strip()
        if not normalized_request_id:
            raise ValueError("request_id is required")
        with self._lock:
            for path in self.root.glob("*.json"):
                record = self._read(path)
                if record and record.get("request_id") == normalized_request_id:
                    return record
            timestamp = float(self.now())
            record = {
                "job_id": uuid.uuid4().hex,
                "request_id": normalized_request_id,
                "status": "queued",
                "image_url": "",
                "error": "",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            self._write(record)
            return dict(record)

    def get(self, job_id: str) -> dict[str, Any] | None:
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            return None
        with self._lock:
            return self._read(self.root / f"{normalized_job_id}.json")

    def update(
        self,
        job_id: str,
        *,
        status: str,
        image_url: str = "",
        error: str = "",
    ) -> dict[str, Any]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in VALID_STATUSES:
            raise ValueError("invalid image job status")
        with self._lock:
            record = self.get(job_id)
            if record is None:
                raise KeyError(str(job_id))
            record.update(
                status=normalized_status,
                image_url=str(image_url or "") if normalized_status == "success" else "",
                error=str(error or "")[:500] if normalized_status == "failed" else "",
                updated_at=float(self.now()),
            )
            self._write(record)
            return dict(record)

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        with self._lock:
            for path in sorted(self.root.glob("*.json")):
                record = self._read(path)
                if not record or record.get("status") not in {"queued", "generating"}:
                    continue
                self.update(record["job_id"], status="failed", error="gateway_restarted")
                recovered.append(str(record["job_id"]))
        return recovered

    def _read(self, path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    def _write(self, record: dict[str, Any]) -> None:
        target = self.root / f"{record['job_id']}.json"
        temporary = self.root / f".{record['job_id']}.{os.getpid()}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(record, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
