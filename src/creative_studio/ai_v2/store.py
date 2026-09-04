"""AI v2 SQLite store：canonical 运行、方案、帧和图片 attempt 的事务边界。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from .migrations import migrate
from .model_ports import ImageArtifact, ImageSessionCursor, ReconcileResult, TextSession


class AiV2StoreConflict(RuntimeError):
    """v2 状态不允许当前操作，或条件更新已被其他 worker 抢先完成。"""


class AiV2Store(Protocol):
    def reserve_run(self, project_id: int, use_case: str, input_fingerprint: str, batch_index: int) -> "RunRecord": ...
    def claim_image_session(self, scheme_id: int, session_key: str) -> tuple["ImageSessionRecord", bool]: ...
    def initialize_image_session(self, session_id: int, cursor: ImageSessionCursor | None, provider_job_id: str | None = None) -> "ImageSessionRecord": ...
    def release_image_session_claim(self, session_id: int) -> None: ...
    def claim_image_attempt(self, attempt_id: int) -> bool: ...


@dataclass(frozen=True)
class RunRecord:
    run_id: int
    project_id: int
    use_case: Literal["narrative", "static", "carousel"] | str
    batch_index: int
    input_fingerprint: str
    aspect_ratio: str = "16:9"


@dataclass(frozen=True)
class ImageAttempt:
    attempt_id: int
    scheme_id: int
    frame_index: int
    request_key: str
    attempt_no: int
    status: Literal["pending", "generating", "success", "failed"] | str
    image_session_id: int
    provider_job_id: str | None


@dataclass(frozen=True)
class ImageAttemptView:
    attempt_id: int
    status: Literal["pending", "generating", "success", "failed"] | str
    image_url: str | None
    error_code: str | None


@dataclass(frozen=True)
class ImageSessionRecord:
    session_id: int
    scheme_id: int
    session_key: str
    cursor: ImageSessionCursor | None
    provider_job_id: str | None


def _cursor_columns(cursor: ImageSessionCursor | None) -> tuple[str | None, str | None, str | None, int]:
    if cursor is None:
        return None, None, None, 0
    return cursor.provider, cursor.conversation_id, cursor.parent_message_id, cursor.revision


def _cursor_from_row(row: sqlite3.Row) -> ImageSessionCursor | None:
    if row["conversation_id"] is None and row["parent_message_id"] is None:
        return None
    return ImageSessionCursor(row["provider"], row["conversation_id"], row["parent_message_id"], row["revision"])


class SqliteAiV2Store:
    """v2 自有 SQLite 存储，构造时只连接调用方显式传入的数据库路径。"""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        migrate(self.connection)

    def close(self) -> None:
        self.connection.close()

    def migrate(self) -> None:
        migrate(self.connection)

    def reserve_run(self, project_id: int, use_case: str, input_fingerprint: str, batch_index: int, *, aspect_ratio: str = "16:9") -> RunRecord:
        if batch_index not in (1, 2):
            raise AiV2StoreConflict("only two v2 batches are allowed")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute(
                "SELECT COUNT(DISTINCT batch_index) FROM ai_v2_runs WHERE project_id=? AND use_case=? AND input_fingerprint=? AND status <> 'failed'",
                (project_id, use_case, input_fingerprint),
            ).fetchone()[0]
            duplicate = self.connection.execute(
                "SELECT 1 FROM ai_v2_runs WHERE project_id=? AND use_case=? AND input_fingerprint=? AND batch_index=? AND status <> 'failed'",
                (project_id, use_case, input_fingerprint, batch_index),
            ).fetchone()
            if duplicate is not None or existing >= 2:
                raise AiV2StoreConflict("v2 batch limit reached")
            cursor = self.connection.execute(
                "INSERT INTO ai_v2_runs(project_id, use_case, batch_index, input_fingerprint, aspect_ratio) VALUES (?, ?, ?, ?, ?)",
                (project_id, use_case, batch_index, input_fingerprint, aspect_ratio),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return RunRecord(cursor.lastrowid, project_id, use_case, batch_index, input_fingerprint, aspect_ratio)  # type: ignore[arg-type]

    def fail_run(self, run_id: int, error_code: str) -> None:
        with self.connection:
            updated = self.connection.execute(
                "UPDATE ai_v2_runs SET status='failed', error_code=? WHERE run_id=? AND status <> 'success'",
                (error_code, run_id),
            ).rowcount
        if updated != 1:
            raise AiV2StoreConflict("run is already completed or missing")

    def save_text_result(self, run_id: int, canonical: Mapping[str, Any], text_session: TextSession) -> None:
        canonical_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        with self.connection:
            row = self.connection.execute("SELECT use_case, status FROM ai_v2_runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] == "success":
                raise AiV2StoreConflict("run is missing or already completed")
            self.connection.execute(
                "UPDATE ai_v2_runs SET status='success', canonical_json=?, text_session_id=?, text_conversation_id=?, text_parent_message_id=? WHERE run_id=?",
                (canonical_json, text_session.session_id, text_session.conversation_id, text_session.parent_message_id, run_id),
            )
            items = canonical.get("items")
            if not isinstance(items, list):
                return
            for scheme_index, item in enumerate(items, start=1):
                if not isinstance(item, Mapping):
                    continue
                scheme_version = f"v2-run-{run_id}-scheme-{scheme_index}"
                scheme_cursor = self.connection.execute(
                    "INSERT INTO ai_v2_schemes(run_id, scheme_index, scheme_version, canonical_json) VALUES (?, ?, ?, ?)",
                    (run_id, scheme_index, scheme_version, json.dumps(item, ensure_ascii=False, separators=(",", ":"))),
                )
                scheme_id = scheme_cursor.lastrowid
                if row["use_case"] == "narrative":
                    continue
                if row["use_case"] == "static":
                    frames = [(1, item.get("image_description", ""), (item.get("execution") or {}).get("image_prompt", ""))]
                else:
                    raw_frames = item.get("frames") or []
                    raw_prompts = ((item.get("execution") or {}).get("image_prompts") or [])
                    prompt_by_index = {
                        prompt.get("index"): prompt.get("prompt", "")
                        for prompt in raw_prompts
                        if isinstance(prompt, Mapping)
                    }
                    frames = [
                        (frame.get("index"), frame.get("description", ""), prompt_by_index.get(frame.get("index"), ""))
                        for frame in raw_frames
                        if isinstance(frame, Mapping)
                    ]
                self.connection.executemany(
                    "INSERT INTO ai_v2_frames(scheme_id, frame_index, description, execution_prompt) VALUES (?, ?, ?, ?)",
                    [(scheme_id, index, description, prompt) for index, description, prompt in frames],
                )

    def read_public_run(self, project_id: int, run_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT run_id, project_id, use_case, batch_index, input_fingerprint, aspect_ratio, status, canonical_json, error_code FROM ai_v2_runs WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        if row is None:
            raise AiV2StoreConflict("run not found")
        return {
            "run_id": row["run_id"],
            "project_id": row["project_id"],
            "use_case": row["use_case"],
            "batch_index": row["batch_index"],
            "input_fingerprint": row["input_fingerprint"],
            "aspect_ratio": row["aspect_ratio"],
            "status": row["status"],
            "canonical": json.loads(row["canonical_json"]) if row["canonical_json"] else None,
            "error_code": row["error_code"],
        }

    def list_public_runs(self, project_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT run_id FROM ai_v2_runs WHERE project_id=? ORDER BY run_id DESC",
            (project_id,),
        ).fetchall()
        return [self.read_public_run(project_id, row["run_id"]) for row in rows]

    def read_public_run_by_id(self, run_id: int) -> dict[str, Any]:
        row = self.connection.execute("SELECT project_id FROM ai_v2_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise AiV2StoreConflict("run not found")
        return self.read_public_run(row["project_id"], run_id)

    def list_schemes(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT scheme_id, run_id, scheme_index, scheme_version, canonical_json FROM ai_v2_schemes WHERE run_id=? ORDER BY scheme_index",
            (run_id,),
        ).fetchall()
        return [
            {
                "scheme_id": row["scheme_id"],
                "run_id": row["run_id"],
                "scheme_index": row["scheme_index"],
                "scheme_version": row["scheme_version"],
                "canonical": json.loads(row["canonical_json"]),
            }
            for row in rows
        ]

    def list_frames(self, scheme_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT frame_id, scheme_id, frame_index, description, execution_prompt, status, success_artifact_id FROM ai_v2_frames WHERE scheme_id=? ORDER BY frame_index",
            (scheme_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def read_scheme(self, scheme_id: int) -> dict[str, Any]:
        """读取单个 v2 方案及其运行类型，供图片用例构造 typed request。"""

        row = self.connection.execute(
            "SELECT s.scheme_id, s.run_id, s.scheme_index, s.scheme_version, s.canonical_json, r.use_case, r.aspect_ratio FROM ai_v2_schemes s JOIN ai_v2_runs r ON r.run_id=s.run_id WHERE s.scheme_id=?",
            (scheme_id,),
        ).fetchone()
        if row is None:
            raise AiV2StoreConflict("scheme not found")
        return {
            "scheme_id": row["scheme_id"],
            "run_id": row["run_id"],
            "scheme_index": row["scheme_index"],
            "scheme_version": row["scheme_version"],
            "use_case": row["use_case"],
            "aspect_ratio": row["aspect_ratio"],
            "canonical": json.loads(row["canonical_json"]),
        }

    def read_frame(self, scheme_id: int, frame_index: int) -> dict[str, Any]:
        """读取单帧私有执行指令和公开状态。"""

        row = self.connection.execute(
            "SELECT frame_id, scheme_id, frame_index, description, execution_prompt, status, success_artifact_id FROM ai_v2_frames WHERE scheme_id=? AND frame_index=?",
            (scheme_id, frame_index),
        ).fetchone()
        if row is None:
            raise AiV2StoreConflict("frame not found")
        return dict(row)

    def read_image_attempt_state(self, attempt_id: int) -> dict[str, Any]:
        """读取 attempt 的安全状态和 artifact 是否存在。"""

        row = self.connection.execute(
            "SELECT a.attempt_id, a.scheme_id, a.frame_index, a.request_key, a.attempt_no, a.status, a.image_session_id, a.provider_job_id, a.error_code, a.retryable, ar.artifact_id FROM ai_v2_image_attempts a LEFT JOIN ai_v2_artifacts ar ON ar.attempt_id=a.attempt_id WHERE a.attempt_id=?",
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise AiV2StoreConflict("attempt not found")
        return dict(row)

    def read_artifact(self, attempt_id: int) -> tuple[bytes, str] | None:
        row = self.connection.execute(
            "SELECT content, mime_type FROM ai_v2_artifacts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        return None if row is None else (bytes(row["content"]), str(row["mime_type"]))

    def save_adoption(self, project_id: int, scheme_id: int, source_scheme_version: str, snapshot: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(snapshot), ensure_ascii=False, separators=(",", ":"))
        with self.connection:
            self.connection.execute(
                "INSERT INTO ai_v2_adoptions(project_id, scheme_id, source_scheme_version, snapshot_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET scheme_id=excluded.scheme_id, source_scheme_version=excluded.source_scheme_version, snapshot_json=excluded.snapshot_json, updated_at=CURRENT_TIMESTAMP",
                (project_id, scheme_id, source_scheme_version, payload),
            )

    def read_adoption(self, project_id: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT project_id, scheme_id, source_scheme_version, snapshot_json, updated_at FROM ai_v2_adoptions WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            return None
        return {"project_id": row["project_id"], "scheme_id": row["scheme_id"], "source_scheme_version": row["source_scheme_version"], "snapshot": json.loads(row["snapshot_json"]), "updated_at": row["updated_at"]}

    def read_artifact_for_frame(self, scheme_id: int, frame_index: int) -> ImageArtifact:
        """读取已成功帧的 bytes/MIME，供下一帧图片请求作为参考。"""

        row = self.connection.execute(
            "SELECT ar.content, ar.mime_type, ar.sha256 FROM ai_v2_frames f JOIN ai_v2_artifacts ar ON ar.artifact_id=f.success_artifact_id WHERE f.scheme_id=? AND f.frame_index=? AND f.status='success'",
            (scheme_id, frame_index),
        ).fetchone()
        if row is None:
            raise AiV2StoreConflict("successful frame artifact not found")
        return ImageArtifact(row["content"], row["mime_type"], row["sha256"])

    def count_runs(self, project_id: int, input_fingerprint: str) -> int:
        return self.connection.execute(
            "SELECT COUNT(*) FROM ai_v2_runs WHERE project_id=? AND input_fingerprint=?",
            (project_id, input_fingerprint),
        ).fetchone()[0]

    def count_image_sessions(self, scheme_id: int | None = None) -> int:
        if scheme_id is None:
            return self.connection.execute("SELECT COUNT(*) FROM ai_v2_image_sessions").fetchone()[0]
        return self.connection.execute("SELECT COUNT(*) FROM ai_v2_image_sessions WHERE scheme_id=?", (scheme_id,)).fetchone()[0]

    def ensure_image_session(
        self,
        scheme_id: int,
        session_key: str,
        cursor: ImageSessionCursor | None,
        provider_job_id: str | None = None,
    ) -> ImageSessionRecord:
        existing = self.find_image_session(scheme_id, session_key)
        if existing is not None:
            return existing
        provider, conversation_id, parent_message_id, revision = _cursor_columns(cursor)
        with self.connection:
            try:
                inserted = self.connection.execute(
                    "INSERT INTO ai_v2_image_sessions(scheme_id, session_key, provider, conversation_id, parent_message_id, revision, provider_job_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (scheme_id, session_key, provider or "unknown", conversation_id, parent_message_id, revision, provider_job_id),
                )
            except sqlite3.IntegrityError:
                existing = self.find_image_session(scheme_id, session_key)
                if existing is not None:
                    return existing
                raise
        return ImageSessionRecord(inserted.lastrowid, scheme_id, session_key, cursor, provider_job_id)  # type: ignore[arg-type]

    def claim_image_session(self, scheme_id: int, session_key: str) -> tuple[ImageSessionRecord, bool]:
        """原子地占用方案图片会话，避免并发首击重复创建供应商会话。"""

        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT session_id, scheme_id, session_key, provider, conversation_id, parent_message_id, revision, provider_job_id FROM ai_v2_image_sessions WHERE scheme_id=? AND session_key=?",
                (scheme_id, session_key),
            ).fetchone()
            if row is not None:
                self.connection.commit()
                return (
                    ImageSessionRecord(row["session_id"], row["scheme_id"], row["session_key"], _cursor_from_row(row), row["provider_job_id"]),
                    False,
                )
            inserted = self.connection.execute(
                "INSERT INTO ai_v2_image_sessions(scheme_id, session_key, provider, revision) VALUES (?, ?, 'pending', 0)",
                (scheme_id, session_key),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return ImageSessionRecord(inserted.lastrowid, scheme_id, session_key, None, None), True  # type: ignore[arg-type]

    def initialize_image_session(
        self,
        session_id: int,
        cursor: ImageSessionCursor | None,
        provider_job_id: str | None = None,
    ) -> ImageSessionRecord:
        """写入首个供应商游标；已初始化的会话保持原值并可安全复用。"""

        provider, conversation_id, parent_message_id, revision = _cursor_columns(cursor)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT session_id, scheme_id, session_key, provider, conversation_id, parent_message_id, revision, provider_job_id FROM ai_v2_image_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise AiV2StoreConflict("image session not found")
            if row["conversation_id"] is None and row["parent_message_id"] is None and row["provider"] == "pending":
                self.connection.execute(
                    "UPDATE ai_v2_image_sessions SET provider=?, conversation_id=?, parent_message_id=?, revision=?, provider_job_id=? WHERE session_id=?",
                    (provider or "unknown", conversation_id, parent_message_id, revision, provider_job_id, session_id),
                )
                row = self.connection.execute(
                    "SELECT session_id, scheme_id, session_key, provider, conversation_id, parent_message_id, revision, provider_job_id FROM ai_v2_image_sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return ImageSessionRecord(row["session_id"], row["scheme_id"], row["session_key"], _cursor_from_row(row), row["provider_job_id"])

    def release_image_session_claim(self, session_id: int) -> None:
        """供应商首建结果未知时释放本地占位，不留下不可恢复的空会话。"""

        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute(
                "DELETE FROM ai_v2_image_sessions WHERE session_id=? AND provider='pending' AND conversation_id IS NULL AND parent_message_id IS NULL",
                (session_id,),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def find_image_session(self, scheme_id: int, session_key: str) -> ImageSessionRecord | None:
        row = self.connection.execute(
            "SELECT session_id, scheme_id, session_key, provider, conversation_id, parent_message_id, revision, provider_job_id FROM ai_v2_image_sessions WHERE scheme_id=? AND session_key=?",
            (scheme_id, session_key),
        ).fetchone()
        if row is None:
            return None
        return ImageSessionRecord(row["session_id"], row["scheme_id"], row["session_key"], _cursor_from_row(row), row["provider_job_id"])

    def find_image_session_by_id(self, session_id: int) -> ImageSessionRecord | None:
        """Resolve the session already attached to a local image attempt."""

        row = self.connection.execute(
            "SELECT session_id, scheme_id, session_key, provider, conversation_id, parent_message_id, revision, provider_job_id FROM ai_v2_image_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return ImageSessionRecord(row["session_id"], row["scheme_id"], row["session_key"], _cursor_from_row(row), row["provider_job_id"])

    def find_image_attempt(self, scheme_id: int, frame_index: int, request_key: str) -> ImageAttempt | None:
        row = self.connection.execute(
            "SELECT attempt_id, scheme_id, frame_index, request_key, attempt_no, status, image_session_id, provider_job_id FROM ai_v2_image_attempts WHERE scheme_id=? AND frame_index=? AND request_key=? ORDER BY attempt_no DESC LIMIT 1",
            (scheme_id, frame_index, request_key),
        ).fetchone()
        if row is None:
            return None
        return ImageAttempt(row["attempt_id"], row["scheme_id"], row["frame_index"], row["request_key"], row["attempt_no"], row["status"], row["image_session_id"], row["provider_job_id"])

    def reserve_image_attempt(self, scheme_id: int, frame_index: int, request_key: str) -> ImageAttempt:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            session = self.connection.execute(
                "SELECT session_id FROM ai_v2_image_sessions WHERE scheme_id=? ORDER BY session_id LIMIT 1",
                (scheme_id,),
            ).fetchone()
            if session is None:
                raise AiV2StoreConflict("image session is required before an attempt")
            frame = self.connection.execute(
                "SELECT status FROM ai_v2_frames WHERE scheme_id=? AND frame_index=?",
                (scheme_id, frame_index),
            ).fetchone()
            if frame is None:
                raise AiV2StoreConflict("frame not found")
            if frame_index > 1:
                previous = self.connection.execute(
                    "SELECT COUNT(*) FROM ai_v2_frames WHERE scheme_id=? AND frame_index < ? AND status <> 'success'",
                    (scheme_id, frame_index),
                ).fetchone()[0]
                if previous:
                    raise AiV2StoreConflict("previous frame must succeed first")
            latest = self.connection.execute(
                "SELECT attempt_id, attempt_no, status, provider_job_id FROM ai_v2_image_attempts WHERE scheme_id=? AND frame_index=? AND request_key=? ORDER BY attempt_no DESC LIMIT 1",
                (scheme_id, frame_index, request_key),
            ).fetchone()
            if latest is not None and latest["status"] != "failed":
                raise AiV2StoreConflict("image attempt already active or successful")
            attempt_no = (latest["attempt_no"] + 1) if latest is not None else 1
            inserted = self.connection.execute(
                "INSERT INTO ai_v2_image_attempts(scheme_id, frame_index, request_key, attempt_no, image_session_id, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                (scheme_id, frame_index, request_key, attempt_no, session["session_id"]),
            )
            self.connection.execute("UPDATE ai_v2_frames SET status='pending' WHERE scheme_id=? AND frame_index=?", (scheme_id, frame_index))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return ImageAttempt(inserted.lastrowid, scheme_id, frame_index, request_key, attempt_no, "pending", session["session_id"], None)  # type: ignore[arg-type]

    def claim_image_attempt(self, attempt_id: int) -> bool:
        """将待处理 attempt 原子标记为 generating，避免并发 worker 重复提交。"""

        self.connection.execute("BEGIN IMMEDIATE")
        try:
            attempt = self.connection.execute(
                "SELECT scheme_id, frame_index, status FROM ai_v2_image_attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                raise AiV2StoreConflict("attempt not found")
            self._assert_latest_attempt(attempt_id, attempt["scheme_id"], attempt["frame_index"])
            if attempt["status"] == "pending":
                self.connection.execute(
                    "UPDATE ai_v2_image_attempts SET status='generating' WHERE attempt_id=? AND status='pending'",
                    (attempt_id,),
                )
                self.connection.commit()
                return True
            self.connection.commit()
            return False
        except Exception:
            self.connection.rollback()
            raise

    def _update_session_cursor(self, session_id: int, cursor: ImageSessionCursor, provider_job_id: str | None = None) -> None:
        current = self.connection.execute(
            "SELECT provider, conversation_id, parent_message_id, revision FROM ai_v2_image_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if current is None or cursor.revision < current["revision"]:
            raise AiV2StoreConflict("stale image session cursor")
        if cursor.revision == current["revision"] and current["conversation_id"] is not None:
            if (current["provider"], current["conversation_id"], current["parent_message_id"]) != (
                cursor.provider,
                cursor.conversation_id,
                cursor.parent_message_id,
            ):
                raise AiV2StoreConflict("conflicting image session cursor")
        self.connection.execute(
            "UPDATE ai_v2_image_sessions SET provider=?, conversation_id=?, parent_message_id=?, revision=?, provider_job_id=COALESCE(?, provider_job_id) WHERE session_id=?",
            (cursor.provider, cursor.conversation_id, cursor.parent_message_id, cursor.revision, provider_job_id, session_id),
        )

    def complete_image_attempt_atomic(self, attempt_id: int, artifact: ImageArtifact, cursor: ImageSessionCursor) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            attempt = self.connection.execute(
                "SELECT scheme_id, frame_index, image_session_id, status, attempt_no FROM ai_v2_image_attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            if attempt is None or attempt["status"] == "success":
                raise AiV2StoreConflict("attempt is missing or already successful")
            self._assert_latest_attempt(attempt_id, attempt["scheme_id"], attempt["frame_index"])
            frame = self.connection.execute(
                "SELECT status FROM ai_v2_frames WHERE scheme_id=? AND frame_index=?",
                (attempt["scheme_id"], attempt["frame_index"]),
            ).fetchone()
            if frame is None or frame["status"] == "success":
                raise AiV2StoreConflict("frame is already successful")
            self._update_session_cursor(attempt["image_session_id"], cursor)
            artifact_row = self.connection.execute(
                "INSERT INTO ai_v2_artifacts(attempt_id, content, mime_type, sha256) VALUES (?, ?, ?, ?)",
                (attempt_id, artifact.content, artifact.mime_type, artifact.sha256),
            )
            self.connection.execute(
                "UPDATE ai_v2_image_attempts SET status='success', error_code=NULL WHERE attempt_id=? AND status <> 'success'",
                (attempt_id,),
            )
            updated = self.connection.execute(
                "UPDATE ai_v2_frames SET status='success', success_artifact_id=? WHERE scheme_id=? AND frame_index=? AND status <> 'success'",
                (artifact_row.lastrowid, attempt["scheme_id"], attempt["frame_index"]),
            ).rowcount
            if updated != 1:
                raise AiV2StoreConflict("frame completion was superseded")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def fail_image_attempt(self, attempt_id: int, error_code: str, retryable: bool) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            attempt = self.connection.execute("SELECT scheme_id, frame_index, status FROM ai_v2_image_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if attempt is None or attempt["status"] == "success":
                raise AiV2StoreConflict("attempt is missing or successful")
            self._assert_latest_attempt(attempt_id, attempt["scheme_id"], attempt["frame_index"])
            self.connection.execute(
                "UPDATE ai_v2_image_attempts SET status='failed', error_code=?, retryable=? WHERE attempt_id=?",
                (error_code, int(retryable), attempt_id),
            )
            self.connection.execute(
                "UPDATE ai_v2_frames SET status='failed' WHERE scheme_id=? AND frame_index=? AND status <> 'success'",
                (attempt["scheme_id"], attempt["frame_index"]),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _assert_latest_attempt(self, attempt_id: int, scheme_id: int, frame_index: int) -> None:
        latest = self.connection.execute(
            "SELECT attempt_id FROM ai_v2_image_attempts WHERE scheme_id=? AND frame_index=? ORDER BY attempt_no DESC LIMIT 1",
            (scheme_id, frame_index),
        ).fetchone()
        if latest is None or latest["attempt_id"] != attempt_id:
            raise AiV2StoreConflict("image attempt was superseded")

    def reconcile_image_attempt(self, attempt_id: int, result: ReconcileResult) -> None:
        attempt = self.connection.execute(
            "SELECT image_session_id, scheme_id, frame_index FROM ai_v2_image_attempts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        if attempt is None:
            raise AiV2StoreConflict("attempt not found")
        if result.state == "success":
            if result.artifact is None or result.cursor is None:
                raise AiV2StoreConflict("provider success is missing artifact or cursor")
            self.complete_image_attempt_atomic(attempt_id, result.artifact, result.cursor)
            return
        if result.state == "working" and result.cursor is not None:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_latest_attempt(attempt_id, attempt["scheme_id"], attempt["frame_index"])
                self._update_session_cursor(attempt["image_session_id"], result.cursor, result.provider_job_id)
                self.connection.execute(
                    "UPDATE ai_v2_image_attempts SET status='generating', provider_job_id=? WHERE attempt_id=? AND status <> 'success'",
                    (result.provider_job_id, attempt_id),
                )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
            return
        if result.state == "terminal_failure":
            self.fail_image_attempt(attempt_id, result.error_code or "image_generation_failed", True)
            return
        if result.state == "unknown":
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_latest_attempt(attempt_id, attempt["scheme_id"], attempt["frame_index"])
                if result.provider_job_id:
                    self.connection.execute(
                        "UPDATE ai_v2_image_attempts SET provider_job_id=? WHERE attempt_id=? AND status <> 'success'",
                        (result.provider_job_id, attempt_id),
                    )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise


__all__ = [
    "AiV2Store",
    "AiV2StoreConflict",
    "ImageAttempt",
    "ImageAttemptView",
    "ImageSessionRecord",
    "RunRecord",
    "SqliteAiV2Store",
]
