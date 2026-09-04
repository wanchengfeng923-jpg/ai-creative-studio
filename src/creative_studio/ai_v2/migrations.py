"""AI v2 SQLite additive migration。"""

from __future__ import annotations

import sqlite3


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS ai_v2_runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        use_case TEXT NOT NULL,
        batch_index INTEGER NOT NULL,
        input_fingerprint TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        canonical_json TEXT,
        text_session_id TEXT,
        text_conversation_id TEXT,
        text_parent_message_id TEXT,
        error_code TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_v2_schemes (
        scheme_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES ai_v2_runs(run_id),
        scheme_index INTEGER NOT NULL,
        scheme_version TEXT NOT NULL UNIQUE,
        canonical_json TEXT NOT NULL,
        UNIQUE(run_id, scheme_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_v2_frames (
        frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_id INTEGER NOT NULL REFERENCES ai_v2_schemes(scheme_id),
        frame_index INTEGER NOT NULL,
        description TEXT NOT NULL,
        execution_prompt TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        success_artifact_id INTEGER,
        UNIQUE(scheme_id, frame_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_v2_image_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_id INTEGER NOT NULL REFERENCES ai_v2_schemes(scheme_id),
        session_key TEXT NOT NULL,
        provider TEXT NOT NULL,
        conversation_id TEXT,
        parent_message_id TEXT,
        revision INTEGER NOT NULL DEFAULT 0,
        provider_job_id TEXT,
        UNIQUE(scheme_id, session_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_v2_image_attempts (
        attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_id INTEGER NOT NULL REFERENCES ai_v2_schemes(scheme_id),
        frame_index INTEGER NOT NULL,
        request_key TEXT NOT NULL,
        attempt_no INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        image_session_id INTEGER NOT NULL REFERENCES ai_v2_image_sessions(session_id),
        provider_job_id TEXT,
        error_code TEXT,
        retryable INTEGER NOT NULL DEFAULT 1,
        UNIQUE(scheme_id, frame_index, attempt_no)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_v2_artifacts (
        artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL UNIQUE REFERENCES ai_v2_image_attempts(attempt_id),
        content BLOB NOT NULL,
        mime_type TEXT NOT NULL,
        sha256 TEXT NOT NULL
    )
    """,
)


def migrate(connection: sqlite3.Connection) -> None:
    """只执行 v2 加法迁移，不修改其他表或历史数据。"""

    connection.execute("PRAGMA foreign_keys = ON")
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS ai_v2_image_attempt_request_idx "
        "ON ai_v2_image_attempts(scheme_id, frame_index, request_key, attempt_no)"
    )
    connection.commit()


__all__ = ["SCHEMA_STATEMENTS", "migrate"]
