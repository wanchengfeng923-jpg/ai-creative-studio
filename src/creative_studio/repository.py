"""独立创意工作台的 SQLite 持久化。"""

from __future__ import annotations

import hmac
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .auth import AuthDataError, hash_password, normalize_username, token_digest
from .generation_models import GenerationConflictError, GenerationNotFoundError


PROJECT_FIELDS = {
    "name",
    "script_type",
    "task_type",
    "task_description",
    "creative_tags",
    "aspect_ratio",
    "product_evidence_summary",
}

SCHEMA_VERSION = 1
SESSION_IDLE_SECONDS = 12 * 60 * 60
SESSION_ABSOLUTE_SECONDS = 7 * 24 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60
LOGIN_LOCKOUT_THRESHOLD = 5


class StudioDataError(RuntimeError):
    """可安全展示给本地用户的业务错误。"""


def now_text() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def future_text(seconds: int) -> str:
    return (datetime.now(timezone(timedelta(hours=8))) + timedelta(seconds=int(seconds))).strftime("%Y-%m-%d %H:%M:%S")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


class StudioRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                statements = (
                    """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    script_type TEXT NOT NULL DEFAULT '展示类',
                    task_type TEXT NOT NULL DEFAULT '',
                    task_description TEXT NOT NULL DEFAULT '',
                    creative_tags_json TEXT NOT NULL DEFAULT '{}',
                    aspect_ratio TEXT NOT NULL DEFAULT '16:9',
                    product_evidence_summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                    """
                CREATE TABLE IF NOT EXISTS project_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """,
                    """
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    recommendation_kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    batch_index INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    context_json TEXT,
                    request_id TEXT,
                    items_json TEXT NOT NULL DEFAULT '[]',
                    usage_json TEXT NOT NULL DEFAULT '{}',
                    conversation_id TEXT NOT NULL DEFAULT '',
                    assistant_message_id TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, recommendation_kind, input_fingerprint, batch_index)
                )
                """,
                    """
                CREATE TABLE IF NOT EXISTS visual_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation_id INTEGER NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
                    item_index INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    image_prompt TEXT NOT NULL,
                    aspect_ratio TEXT NOT NULL,
                    image_status TEXT NOT NULL DEFAULT 'queued',
                    image_path TEXT NOT NULL DEFAULT '',
                    image_error TEXT NOT NULL DEFAULT '',
                    gateway_job_id TEXT NOT NULL DEFAULT '',
                    image_attempt INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(generation_id, item_index)
                )
                """,
                    """
                CREATE TABLE IF NOT EXISTS adoptions (
                    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    recommendation_kind TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                    "CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC)",
                    """
                CREATE INDEX IF NOT EXISTS idx_generations_history
                    ON generations(project_id, recommendation_kind, input_fingerprint, batch_index);
                """,
                    "CREATE INDEX IF NOT EXISTS idx_visual_items_status ON visual_items(image_status, updated_at)",
                )
                for statement in statements:
                    connection.execute(statement)
                self._migrate_schema(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _migrate_schema(self, connection: sqlite3.Connection) -> None:
        """Apply repeatable, transactional authentication schema migrations."""
        current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        # Keep every statement idempotent.  A database can have an optimistic
        # user_version from an interrupted/older migration while still missing
        # one of the objects below, so the version check must not short-circuit
        # the existence checks.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_digest TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf_token_digest TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL,
                idle_expires_at TEXT NOT NULL,
                absolute_expires_at TEXT NOT NULL,
                revoked_at TEXT,
                source_ip TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                failure_count INTEGER NOT NULL DEFAULT 0,
                window_started_at TEXT NOT NULL,
                locked_until TEXT,
                UNIQUE(username, client_ip)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(projects)")}
        if "owner_user_id" not in columns:
            connection.execute(
                "ALTER TABLE projects ADD COLUMN owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_owner_user ON projects(owner_user_id)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_digest)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup ON login_attempts(username, client_ip)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)")
        generation_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(generations)")}
        if "context_json" not in generation_columns:
            connection.execute("ALTER TABLE generations ADD COLUMN context_json TEXT")
        if "request_id" not in generation_columns:
            connection.execute("ALTER TABLE generations ADD COLUMN request_id TEXT")
        if current_version < SCHEMA_VERSION:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _safe_user(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
            "is_active": bool(row["is_active"]),
            "must_change_password": bool(row["must_change_password"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "last_login_at": row["last_login_at"],
        }

    @staticmethod
    def _password_hash(value: str) -> str:
        """Return a PBKDF2 hash while accepting a pre-hashed AuthService value."""
        if not isinstance(value, str):
            raise AuthDataError("invalid password")
        if value.startswith("pbkdf2_sha256$"):
            parts = value.split("$")
            if len(parts) != 4 or not parts[1].isdigit() or not parts[2] or not parts[3]:
                raise AuthDataError("invalid password")
            return value
        return hash_password(value)

    def create_bootstrap_admin(self, username: str, password: str) -> dict[str, Any]:
        """Create the first administrator and claim all currently unowned projects."""
        try:
            normalized = normalize_username(username)
            password_hash = self._password_hash(password)
        except AuthDataError:
            raise
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1"
                ).fetchone()
                if existing is not None:
                    # Bootstrap is intentionally idempotent, but it also
                    # repairs ownership for projects created between runs.
                    connection.execute(
                        "UPDATE projects SET owner_user_id=? WHERE owner_user_id IS NULL",
                        (int(existing["id"]),),
                    )
                    row = connection.execute(
                        "SELECT * FROM users WHERE id=?", (int(existing["id"]),)
                    ).fetchone()
                    connection.commit()
                    return self._safe_user(row) or {}
                any_user = connection.execute("SELECT id FROM users LIMIT 1").fetchone()
                if any_user is not None:
                    raise StudioDataError("Bootstrap 管理员只能在账号为空时创建")
                cursor = connection.execute(
                    """
                    INSERT INTO users(username,password_hash,role,is_active,must_change_password,
                                      created_at,updated_at,last_login_at)
                    VALUES(?,?, 'admin',1,0,?,?,NULL)
                    """,
                    (normalized, password_hash, timestamp, timestamp),
                )
                user_id = int(cursor.lastrowid)
                connection.execute(
                    "UPDATE projects SET owner_user_id=? WHERE owner_user_id IS NULL", (user_id,)
                )
                row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._safe_user(row) or {}

    def create_user(self, username: str, password: str) -> dict[str, Any]:
        """Create an active ordinary user; role assignment is intentionally fixed."""
        normalized = normalize_username(username)
        password_hash = self._password_hash(password)
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO users(username,password_hash,role,is_active,must_change_password,
                                      created_at,updated_at,last_login_at)
                    VALUES(?,?, 'user',1,0,?,?,NULL)
                    """,
                    (normalized, password_hash, timestamp, timestamp),
                )
                row = connection.execute(
                    "SELECT * FROM users WHERE id=?", (int(cursor.lastrowid),)
                ).fetchone()
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise StudioDataError("用户名已存在") from exc
            except Exception:
                connection.rollback()
                raise
        return self._safe_user(row) or {}

    def list_users(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [self._safe_user(row) or {} for row in rows]

    def get_user(self, user_id_or_username: int | str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            if isinstance(user_id_or_username, int):
                row = connection.execute(
                    "SELECT * FROM users WHERE id=?", (int(user_id_or_username),)
                ).fetchone()
            else:
                try:
                    username = normalize_username(str(user_id_or_username))
                except AuthDataError:
                    return None
                row = connection.execute(
                    "SELECT * FROM users WHERE username=?", (username,)
                ).fetchone()
        return self._safe_user(row)

    def get_user_credentials(self, user_id_or_username: int | str) -> dict[str, Any] | None:
        """Return auth-only credential data; callers must never serialize it."""
        with closing(self._connect()) as connection:
            if isinstance(user_id_or_username, int):
                row = connection.execute(
                    "SELECT id,username,password_hash,role,is_active,must_change_password FROM users WHERE id=?",
                    (int(user_id_or_username),),
                ).fetchone()
            else:
                try:
                    username = normalize_username(str(user_id_or_username))
                except AuthDataError:
                    return None
                row = connection.execute(
                    "SELECT id,username,password_hash,role,is_active,must_change_password FROM users WHERE username=?",
                    (username,),
                ).fetchone()
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    def mark_user_login(self, user_id: int) -> None:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE users SET last_login_at=?,updated_at=? WHERE id=?",
                (timestamp, timestamp, int(user_id)),
            )

    def set_user_active(self, user_id: int, is_active: bool) -> dict[str, Any]:
        """Toggle account availability and revoke sessions when disabling an account."""
        active = 1 if bool(is_active) else 0
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
                if row is None:
                    raise StudioDataError("用户不存在")
                if active == 0 and row["role"] == "admin" and row["is_active"]:
                    count = connection.execute(
                        "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1"
                    ).fetchone()[0]
                    if int(count) <= 1:
                        raise StudioDataError("不能停用最后一个管理员")
                connection.execute(
                    "UPDATE users SET is_active=?,updated_at=? WHERE id=?",
                    (active, timestamp, int(user_id)),
                )
                if active == 0:
                    connection.execute(
                        "UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                        (timestamp, int(user_id)),
                    )
                updated = connection.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._safe_user(updated) or {}

    def update_user_username(self, user_id: int, username: str) -> dict[str, Any]:
        normalized = normalize_username(username)
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute("SELECT role FROM users WHERE id=?", (int(user_id),)).fetchone()
                if row is None:
                    raise StudioDataError("用户不存在")
                if row["role"] != "user":
                    raise StudioDataError("不能编辑管理员账号")
                connection.execute("UPDATE users SET username=?,updated_at=? WHERE id=?", (normalized, timestamp, int(user_id)))
                updated = connection.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise StudioDataError("用户名已存在") from exc
            except Exception:
                connection.rollback()
                raise
        return self._safe_user(updated) or {}

    def delete_user(self, user_id: int) -> bool:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute("SELECT role FROM users WHERE id=?", (int(user_id),)).fetchone()
                if row is None:
                    raise StudioDataError("用户不存在")
                if row["role"] != "user":
                    raise StudioDataError("不能删除管理员账号")
                cursor = connection.execute("DELETE FROM users WHERE id=?", (int(user_id),))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return cursor.rowcount == 1

    def reset_user_password(
        self, user_id: int, password: str, must_change_password: bool = True
    ) -> dict[str, Any]:
        """Replace a password and revoke every existing session for the account."""
        password_hash = self._password_hash(password)
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute("SELECT id FROM users WHERE id=?", (int(user_id),)).fetchone()
                if row is None:
                    raise StudioDataError("用户不存在")
                connection.execute(
                    "UPDATE users SET password_hash=?,must_change_password=?,updated_at=? WHERE id=?",
                    (password_hash, 1 if must_change_password else 0, timestamp, int(user_id)),
                )
                connection.execute(
                    "UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                    (timestamp, int(user_id)),
                )
                updated = connection.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._safe_user(updated) or {}

    @staticmethod
    def _safe_session(row: sqlite3.Row | None) -> dict[str, Any] | None:
        """Expose session context without either bearer or CSRF secrets."""
        if row is None:
            return None
        result: dict[str, Any] = {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "created_at": str(row["created_at"]),
            "last_active_at": str(row["last_active_at"]),
            "idle_expires_at": str(row["idle_expires_at"]),
            "absolute_expires_at": str(row["absolute_expires_at"]),
            "source_ip": str(row["source_ip"] or ""),
            "user_agent": str(row["user_agent"] or ""),
        }
        # AuthService needs these fields to build a request context.  The
        # credential digests remain an implementation detail of this module.
        for key in ("username", "role", "is_active", "must_change_password"):
            if key in row.keys():
                value = row[key]
                result[key] = bool(value) if key in {"is_active", "must_change_password"} else value
        return result

    @staticmethod
    def _session_digest(value: str) -> str:
        if not isinstance(value, str) or not value:
            raise AuthDataError("invalid token")
        return token_digest(value)

    def create_session(
        self,
        user_id: int,
        session_token: str,
        csrf_token: str,
        source_ip: str = "",
        user_agent: str = "",
        idle_seconds: int = SESSION_IDLE_SECONDS,
        absolute_seconds: int = SESSION_ABSOLUTE_SECONDS,
    ) -> dict[str, Any]:
        """Persist a session using digests of both client-held tokens."""
        session_digest = self._session_digest(session_token)
        csrf_digest = self._session_digest(csrf_token)
        idle_seconds = max(0, int(idle_seconds))
        absolute_seconds = max(0, int(absolute_seconds))
        created = datetime.now(timezone(timedelta(hours=8)))
        created_text = created.strftime("%Y-%m-%d %H:%M:%S")
        idle_expires = (created + timedelta(seconds=idle_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        absolute_expires = (created + timedelta(seconds=absolute_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        source_ip = " ".join(str(source_ip or "").split())[:128]
        user_agent = " ".join(str(user_agent or "").split())[:512]
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                user = connection.execute(
                    "SELECT id,is_active FROM users WHERE id=?", (int(user_id),)
                ).fetchone()
                if user is None:
                    raise StudioDataError("用户不存在")
                if not bool(user["is_active"]):
                    raise StudioDataError("用户已停用")
                cursor = connection.execute(
                    """
                    INSERT INTO sessions(token_digest,user_id,csrf_token_digest,created_at,last_active_at,
                                         idle_expires_at,absolute_expires_at,source_ip,user_agent)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        session_digest,
                        int(user_id),
                        csrf_digest,
                        created_text,
                        created_text,
                        idle_expires,
                        absolute_expires,
                        source_ip,
                        user_agent,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM sessions WHERE id=?", (int(cursor.lastrowid),)
                ).fetchone()
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise StudioDataError("会话已存在") from exc
            except Exception:
                connection.rollback()
                raise
        return self._safe_session(row) or {}

    def get_session(self, session_token: str) -> dict[str, Any] | None:
        """Return only a currently valid session for an active user."""
        try:
            digest = self._session_digest(session_token)
        except AuthDataError:
            return None
        timestamp = now_text()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT s.*,u.username,u.role,u.is_active,u.must_change_password FROM sessions s
                JOIN users u ON u.id=s.user_id
                WHERE s.token_digest=? AND s.revoked_at IS NULL
                  AND u.is_active=1 AND s.idle_expires_at>? AND s.absolute_expires_at>?
                """,
                (digest, timestamp, timestamp),
            ).fetchone()
        return self._safe_session(row)

    def verify_session_csrf(self, session_token: str, csrf_token: str) -> bool:
        """Validate a CSRF token for a live session without exposing its digest."""
        try:
            session_digest = self._session_digest(session_token)
            csrf_digest = self._session_digest(csrf_token)
        except AuthDataError:
            return False
        timestamp = now_text()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT s.csrf_token_digest FROM sessions s
                JOIN users u ON u.id=s.user_id
                WHERE s.token_digest=? AND s.revoked_at IS NULL
                  AND u.is_active=1 AND s.idle_expires_at>? AND s.absolute_expires_at>?
                """,
                (session_digest, timestamp, timestamp),
            ).fetchone()
        return row is not None and hmac.compare_digest(str(row["csrf_token_digest"]), csrf_digest)

    def touch_session(self, session_token: str) -> bool:
        """Refresh idle expiry, capped by the original absolute expiry."""
        try:
            digest = self._session_digest(session_token)
        except AuthDataError:
            return False
        timestamp = now_text()
        now_value = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=8))
        )
        idle_until = (now_value + timedelta(seconds=SESSION_IDLE_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT s.absolute_expires_at FROM sessions s
                    JOIN users u ON u.id=s.user_id
                    WHERE s.token_digest=? AND s.revoked_at IS NULL
                      AND u.is_active=1 AND s.idle_expires_at>? AND s.absolute_expires_at>?
                    """,
                    (digest, timestamp, timestamp),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return False
                new_idle = min(idle_until, str(row["absolute_expires_at"]))
                cursor = connection.execute(
                    """
                    UPDATE sessions SET last_active_at=?,idle_expires_at=?
                    WHERE token_digest=? AND revoked_at IS NULL
                    """,
                    (timestamp, new_idle, digest),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return cursor.rowcount == 1

    def revoke_session(self, session_token: str) -> bool:
        try:
            digest = self._session_digest(session_token)
        except AuthDataError:
            return False
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE sessions SET revoked_at=? WHERE token_digest=? AND revoked_at IS NULL",
                (now_text(), digest),
            )
        return cursor.rowcount == 1

    def revoke_sessions_for_user(self, user_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                (now_text(), int(user_id)),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _safe_login_attempt(row: sqlite3.Row | None, timestamp: str | None = None) -> dict[str, Any] | None:
        if row is None:
            return None
        current = timestamp or now_text()
        locked_until = row["locked_until"]
        return {
            "username": str(row["username"]),
            "client_ip": str(row["client_ip"]),
            "failure_count": int(row["failure_count"]),
            "window_started_at": str(row["window_started_at"]),
            "locked_until": str(locked_until) if locked_until else None,
            "is_locked": bool(locked_until and str(locked_until) > current),
        }

    def get_login_attempt(self, username: str, client_ip: str) -> dict[str, Any] | None:
        normalized = normalize_username(username)
        client_ip = " ".join(str(client_ip or "").split())[:128]
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM login_attempts WHERE username=? AND client_ip=?",
                (normalized, client_ip),
            ).fetchone()
        return self._safe_login_attempt(row)

    def record_login_failure(self, username: str, client_ip: str) -> dict[str, Any]:
        normalized = normalize_username(username)
        client_ip = " ".join(str(client_ip or "").split())[:128]
        timestamp = now_text()
        current = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT * FROM login_attempts WHERE username=? AND client_ip=?",
                    (normalized, client_ip),
                ).fetchone()
                expired = True
                if row is not None:
                    try:
                        started = datetime.strptime(str(row["window_started_at"]), "%Y-%m-%d %H:%M:%S")
                        expired = (current - started).total_seconds() >= LOGIN_WINDOW_SECONDS
                    except ValueError:
                        expired = True
                if row is None or expired:
                    count = 1
                    window_started = timestamp
                else:
                    count = int(row["failure_count"]) + 1
                    window_started = str(row["window_started_at"])
                locked_until = (
                    (current + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
                    if count >= LOGIN_LOCKOUT_THRESHOLD
                    else None
                )
                connection.execute(
                    """
                    INSERT INTO login_attempts(username,client_ip,failure_count,window_started_at,locked_until)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(username,client_ip) DO UPDATE SET
                        failure_count=excluded.failure_count,
                        window_started_at=excluded.window_started_at,
                        locked_until=excluded.locked_until
                    """,
                    (normalized, client_ip, count, window_started, locked_until),
                )
                saved = connection.execute(
                    "SELECT * FROM login_attempts WHERE username=? AND client_ip=?",
                    (normalized, client_ip),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._safe_login_attempt(saved, timestamp) or {}

    def clear_login_attempt_window(self, username: str, client_ip: str) -> bool:
        normalized = normalize_username(username)
        client_ip = " ".join(str(client_ip or "").split())[:128]
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM login_attempts WHERE username=? AND client_ip=?",
                (normalized, client_ip),
            )
        return cursor.rowcount > 0

    _AUDIT_SENSITIVE_KEY = re.compile(
        r"(?:password|passwd|secret|token|cookie|csrf|authorization|credential|request|response|file|content|body|header|hash)",
        re.IGNORECASE,
    )
    _AUDIT_SAFE_KEYS = {
        "ip", "source_ip", "user_agent", "method", "status", "reason", "latency_ms", "count", "kind", "target"
    }

    @classmethod
    def _safe_audit_metadata(cls, metadata: Any) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}

        def clean(value: Any, key: str = "") -> Any:
            if key and (key not in cls._AUDIT_SAFE_KEYS or cls._AUDIT_SENSITIVE_KEY.search(key)):
                return None
            if isinstance(value, dict):
                result: dict[str, Any] = {}
                for child_key, child_value in value.items():
                    child_name = str(child_key)[:64]
                    cleaned = clean(child_value, child_name)
                    if cleaned is not None:
                        result[child_name] = cleaned
                return result
            if isinstance(value, (list, tuple)):
                return [item for item in (clean(item) for item in value[:10]) if item is not None]
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                if cls._AUDIT_SENSITIVE_KEY.search(value):
                    return None
                return " ".join(value.split())[:256]
            return None

        cleaned = clean(metadata)
        if not isinstance(cleaned, dict):
            return {}
        # Keep audit records bounded even when callers supply a large safe map.
        encoded = _json(cleaned)
        if len(encoded.encode("utf-8")) > 4096:
            return {}
        return cleaned

    def record_audit(
        self,
        actor_user_id: int | None,
        action: str,
        target_type: str,
        target_id: str = "",
        result: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        safe_metadata = self._safe_audit_metadata(metadata)
        actor = int(actor_user_id) if actor_user_id is not None else None
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_logs(actor_user_id,action,target_type,target_id,result,metadata_json,created_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    actor,
                    str(action or "")[:120],
                    str(target_type or "")[:120],
                    str(target_id or "")[:255],
                    str(result or "")[:40],
                    _json(safe_metadata),
                    now_text(),
                ),
            )
        return int(cursor.lastrowid)

    def get_project_owner_id(self, project_id: int) -> int | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT owner_user_id FROM projects WHERE id=?", (int(project_id),)
            ).fetchone()
        if row is None or row["owner_user_id"] is None:
            return None
        return int(row["owner_user_id"])

    def get_visual_item_owner_id(self, item_id: int) -> int | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT p.owner_user_id FROM visual_items v
                JOIN generations g ON g.id=v.generation_id
                JOIN projects p ON p.id=g.project_id
                WHERE v.id=?
                """,
                (int(item_id),),
            ).fetchone()
        if row is None or row["owner_user_id"] is None:
            return None
        return int(row["owner_user_id"])

    def create_project(
        self, name: str = "未命名创意", script_type: str = "展示类", owner_user_id: int | None = None
    ) -> dict[str, Any]:
        timestamp = now_text()
        normalized_type = "叙事类" if str(script_type).strip() == "叙事类" else "展示类"
        with closing(self._connect()) as connection:
            if owner_user_id is not None:
                owner = connection.execute(
                    "SELECT id,is_active FROM users WHERE id=?", (int(owner_user_id),)
                ).fetchone()
                if owner is None:
                    raise StudioDataError("用户不存在")
                if not bool(owner["is_active"]):
                    raise StudioDataError("用户已停用")
            cursor = connection.execute(
                "INSERT INTO projects(name, script_type, owner_user_id, created_at, updated_at) VALUES(?,?,?,?,?)",
                (str(name or "").strip()[:120] or "未命名创意", normalized_type, owner_user_id, timestamp, timestamp),
            )
            project_id = int(cursor.lastrowid)
        project = self.get_project(project_id)
        if project is None:
            raise StudioDataError("项目创建失败")
        return project

    def list_projects(self, keyword: str = "") -> list[dict[str, Any]]:
        value = str(keyword or "").strip()
        where = "WHERE p.name LIKE ?" if value else ""
        params: tuple[Any, ...] = (f"%{value}%",) if value else ()
        query = f"""
            SELECT p.*, a.recommendation_kind AS adopted_kind,
                   a.snapshot_json AS adopted_snapshot_json
            FROM projects p
            LEFT JOIN adoptions a ON a.project_id = p.id
            {where}
            ORDER BY p.updated_at DESC, p.id DESC
        """
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            snapshot = _loads(row["adopted_snapshot_json"], {})
            title = str(snapshot.get("title") or snapshot.get("story") or "") if isinstance(snapshot, dict) else ""
            result.append({
                "id": int(row["id"]),
                "name": row["name"],
                "script_type": row["script_type"],
                "owner_user_id": row["owner_user_id"],
                "updated_at": row["updated_at"],
                "adopted_kind": str(row["adopted_kind"] or ""),
                "adopted_title": title,
            })
        return result

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (int(project_id),)).fetchone()
            if row is None:
                return None
            files = connection.execute(
                "SELECT id, original_name, size_bytes, created_at FROM project_files WHERE project_id=? ORDER BY id",
                (int(project_id),),
            ).fetchall()
            adoption = connection.execute(
                "SELECT recommendation_kind, reference_id, snapshot_json, updated_at FROM adoptions WHERE project_id=?",
                (int(project_id),),
            ).fetchone()
        result = {
            "id": int(row["id"]),
            "name": row["name"],
            "script_type": row["script_type"],
            "task_type": row["task_type"],
            "task_description": row["task_description"],
            "creative_tags": _loads(row["creative_tags_json"], {}),
            "aspect_ratio": row["aspect_ratio"],
            "product_evidence_summary": row["product_evidence_summary"],
            "owner_user_id": row["owner_user_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "reference_files": [dict(item) for item in files],
            "adoption": None,
        }
        if adoption is not None:
            result["adoption"] = {
                "recommendation_kind": adoption["recommendation_kind"],
                "reference_id": adoption["reference_id"],
                "snapshot": _loads(adoption["snapshot_json"], {}),
                "updated_at": adoption["updated_at"],
            }
        return result

    def update_project(self, project_id: int, values: dict[str, Any]) -> dict[str, Any]:
        current = self.get_project(project_id)
        if current is None:
            raise StudioDataError("项目不存在")
        merged = {key: current[key] for key in PROJECT_FIELDS}
        for key in PROJECT_FIELDS:
            if key in values:
                merged[key] = values[key]
        name = str(merged["name"] or "").strip()[:120] or "未命名创意"
        script_type = "叙事类" if str(merged["script_type"]).strip() == "叙事类" else "展示类"
        aspect_ratio = "9:16" if str(merged["aspect_ratio"]).strip() == "9:16" else "16:9"
        tags = merged["creative_tags"] if isinstance(merged["creative_tags"], dict) else {}
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE projects
                SET name=?, script_type=?, task_type=?, task_description=?, creative_tags_json=?,
                    aspect_ratio=?, product_evidence_summary=?, updated_at=?
                WHERE id=?
                """,
                (
                    name,
                    script_type,
                    str(merged["task_type"] or "").strip()[:100],
                    str(merged["task_description"] or "").strip()[:4000],
                    _json(tags),
                    aspect_ratio,
                    str(merged["product_evidence_summary"] or "").strip()[:4000],
                    timestamp,
                    int(project_id),
                ),
            )
        updated = self.get_project(project_id)
        if updated is None:
            raise StudioDataError("项目保存失败")
        return updated

    def delete_project(self, project_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute("DELETE FROM projects WHERE id=?", (int(project_id),))
        return cursor.rowcount > 0

    def add_project_file(self, project_id: int, original_name: str, stored_name: str, size_bytes: int) -> dict[str, Any]:
        if self.get_project(project_id) is None:
            raise StudioDataError("项目不存在")
        timestamp = now_text()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO project_files(project_id,original_name,stored_name,size_bytes,created_at) VALUES(?,?,?,?,?)",
                (int(project_id), str(original_name)[:255], str(stored_name), int(size_bytes), timestamp),
            )
            file_id = int(cursor.lastrowid)
        return {"id": file_id, "original_name": str(original_name)[:255], "size_bytes": int(size_bytes), "created_at": timestamp}

    def reference_file_names(self, project_id: int) -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT original_name FROM project_files WHERE project_id=? ORDER BY id", (int(project_id),)
            ).fetchall()
        return [str(row["original_name"]) for row in rows]

    def recover_pending_generations(self, timeout_seconds: int) -> int:
        cutoff = (
            datetime.now(timezone(timedelta(hours=8))) - timedelta(seconds=max(0, int(timeout_seconds)))
        ).strftime("%Y-%m-%d %H:%M:%S")
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE generations
                SET status='expired',updated_at=?
                WHERE status='pending' AND created_at <= ?
                """,
                (timestamp, cutoff),
            )
            connection.commit()
        return int(cursor.rowcount)

    def reserve_generation(
        self,
        project_id: int,
        kind: str,
        schema_version: str,
        fingerprint: str,
        context_json: Mapping[str, Any] | None = None,
        request_id: str = "",
    ) -> dict[str, Any]:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute("SELECT id FROM projects WHERE id=?", (int(project_id),)).fetchone()
            if project is None:
                connection.rollback()
                raise GenerationNotFoundError("项目不存在")
            connection.execute(
                "DELETE FROM generations WHERE project_id=? AND recommendation_kind=? AND input_fingerprint=? AND status='failed'",
                (int(project_id), kind, fingerprint),
            )
            rows = connection.execute(
                """
                SELECT id,batch_index,status,conversation_id,assistant_message_id
                FROM generations
                WHERE project_id=? AND recommendation_kind=? AND input_fingerprint=?
                ORDER BY batch_index
                """,
                (int(project_id), kind, fingerprint),
            ).fetchall()
            active_rows = [row for row in rows if row["status"] in ("pending", "success")]
            if len(active_rows) >= 2:
                connection.rollback()
                raise GenerationConflictError("当前定位已生成2批，请修改输入后再生成")
            if any(row["status"] == "pending" for row in active_rows):
                connection.rollback()
                raise GenerationConflictError("当前项目已有一批正在生成")
            batch_index = (max(int(row["batch_index"]) for row in rows) + 1) if rows else 1
            previous = active_rows[-1] if active_rows else None
            cursor = connection.execute(
                """
                INSERT INTO generations(project_id,recommendation_kind,schema_version,input_fingerprint,
                                        batch_index,status,context_json,request_id,created_at,updated_at)
                VALUES(?,?,?,?,?,'pending',?,?,?,?)
                """,
                (
                    int(project_id),
                    kind,
                    schema_version,
                    fingerprint,
                    batch_index,
                    _json(context_json or {}),
                    str(request_id or "").strip() or None,
                    timestamp,
                    timestamp,
                ),
            )
            connection.commit()
        return {
            "id": int(cursor.lastrowid),
            "batch_index": batch_index,
            "conversation_id": str(previous["conversation_id"] or "") if previous else "",
            "parent_message_id": str(previous["assistant_message_id"] or "") if previous else "",
        }

    def complete_narrative_generation(self, generation_id: int, result: Any) -> None:
        self._complete_generation(generation_id, result, visual_items=None)

    def complete_visual_generation(self, generation_id: int, result: Any, aspect_ratio: str) -> list[int]:
        return self._complete_generation(generation_id, result, visual_items=(result.items, aspect_ratio))

    def _complete_generation(self, generation_id: int, result: Any, visual_items: tuple[Any, str] | None) -> list[int]:
        timestamp = now_text()
        usage = {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "usage_source": result.usage_source,
            "latency_ms": result.latency_ms,
        }
        item_ids: list[int] = []
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE generations
                SET status='success', items_json=?, usage_json=?, conversation_id=?,
                    assistant_message_id=?, error='', updated_at=?
                WHERE id=? AND status='pending'
                """,
                (
                    _json(result.items),
                    _json(usage),
                    str(result.conversation_id or ""),
                    str(result.assistant_message_id or ""),
                    timestamp,
                    int(generation_id),
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise StudioDataError("生成记录状态已经变化")
            if visual_items is not None:
                items, aspect_ratio = visual_items
                for index, source in enumerate(items, start=1):
                    content = dict(source)
                    image_prompt = str(content.pop("image_prompt", ""))
                    child = connection.execute(
                        """
                        INSERT INTO visual_items(generation_id,item_index,content_json,image_prompt,aspect_ratio,
                                                 image_status,created_at,updated_at)
                        VALUES(?,?,?,?,?,'queued',?,?)
                        """,
                        (int(generation_id), index, _json(content), image_prompt, aspect_ratio, timestamp, timestamp),
                    )
                    item_ids.append(int(child.lastrowid))
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE id=(SELECT project_id FROM generations WHERE id=?)",
                (timestamp, int(generation_id)),
            )
            connection.commit()
        return item_ids

    def fail_generation(self, generation_id: int, error: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE generations SET status='failed',error=?,updated_at=? WHERE id=? AND status='pending'",
                (" ".join(str(error or "").split())[:500], now_text(), int(generation_id)),
            )

    def generation_history(self, project_id: int, kind: str, fingerprint: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM generations
                WHERE project_id=? AND recommendation_kind=? AND status='success'
                ORDER BY created_at,id
                """,
                (int(project_id), kind),
            ).fetchall()
            visual_rows = connection.execute(
                """
                SELECT v.* FROM visual_items v JOIN generations g ON g.id=v.generation_id
                WHERE g.project_id=? AND g.recommendation_kind=? ORDER BY v.generation_id,v.item_index
                """,
                (int(project_id), kind),
            ).fetchall()
        visuals: dict[int, list[dict[str, Any]]] = {}
        for row in visual_rows:
            item = _loads(row["content_json"], {})
            item.update({
                "id": int(row["id"]),
                "item_index": int(row["item_index"]),
                "aspect_ratio": row["aspect_ratio"],
                "image_status": row["image_status"],
                "image_url": f"/api/visual-items/{int(row['id'])}/image" if row["image_status"] == "success" else "",
                "image_error": row["image_error"],
            })
            visuals.setdefault(int(row["generation_id"]), []).append(item)
        current: list[dict[str, Any]] = []
        stale: list[dict[str, Any]] = []
        for row in rows:
            entry = {
                "id": int(row["id"]),
                "batch_index": int(row["batch_index"]),
                "input_fingerprint": row["input_fingerprint"],
                "items": visuals.get(int(row["id"]), _loads(row["items_json"], [])),
                "usage": _loads(row["usage_json"], {}),
                "created_at": row["created_at"],
            }
            (current if row["input_fingerprint"] == fingerprint else stale).append(entry)
        return {
            "batches": current,
            "stale_batches": stale,
            "remaining_generations": max(0, 2 - len(current)),
        }

    def visual_item(self, item_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT v.*,g.project_id FROM visual_items v
                JOIN generations g ON g.id=v.generation_id WHERE v.id=?
                """,
                (int(item_id),),
            ).fetchone()
        return dict(row) if row is not None else None

    def recover_visual_items(self) -> list[int]:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE visual_items SET image_status='queued',updated_at=? WHERE image_status='generating'",
                (timestamp,),
            )
            rows = connection.execute("SELECT id FROM visual_items WHERE image_status='queued' ORDER BY id").fetchall()
        return [int(row["id"]) for row in rows]

    def claim_visual_item(self, item_id: int) -> dict[str, Any] | None:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE visual_items SET image_status='generating',image_error='',image_attempt=image_attempt+1,updated_at=?
                WHERE id=? AND image_status='queued'
                """,
                (timestamp, int(item_id)),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            row = connection.execute("SELECT * FROM visual_items WHERE id=?", (int(item_id),)).fetchone()
            connection.commit()
        return dict(row) if row is not None else None

    def set_gateway_job(self, item_id: int, attempt: int, job_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items SET gateway_job_id=?,updated_at=?
                WHERE id=? AND image_status='generating' AND image_attempt=?
                """,
                (str(job_id), now_text(), int(item_id), int(attempt)),
            )
        return cursor.rowcount == 1

    def complete_visual_item(self, item_id: int, attempt: int, image_path: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items
                SET image_status='success',image_path=?,image_error='',updated_at=?
                WHERE id=? AND image_status='generating' AND image_attempt=?
                """,
                (str(image_path), now_text(), int(item_id), int(attempt)),
            )
        return cursor.rowcount == 1

    def fail_visual_item(self, item_id: int, attempt: int, error: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items SET image_status='failed',image_error=?,updated_at=?
                WHERE id=? AND image_status='generating' AND image_attempt=?
                """,
                (" ".join(str(error or "").split())[:500], now_text(), int(item_id), int(attempt)),
            )
        return cursor.rowcount == 1

    def retry_visual_item(self, item_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items
                SET image_status='queued',image_error='',gateway_job_id='',image_path='',updated_at=?
                WHERE id=? AND image_status='failed'
                """,
                (now_text(), int(item_id)),
            )
        return cursor.rowcount == 1

    def adopt_visual(self, project_id: int, item_id: int) -> dict[str, Any]:
        item = self.visual_item(item_id)
        if item is None or int(item["project_id"]) != int(project_id):
            raise StudioDataError("视觉方案不属于当前项目")
        snapshot = _loads(item["content_json"], {})
        self._save_adoption(project_id, "visual", str(item_id), snapshot)
        return snapshot

    def adopt_narrative(self, project_id: int, generation_id: int, item_index: int) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT items_json FROM generations WHERE id=? AND project_id=? AND recommendation_kind='narrative' AND status='success'",
                (int(generation_id), int(project_id)),
            ).fetchone()
        items = _loads(row["items_json"], []) if row is not None else []
        if not isinstance(items, list) or item_index < 0 or item_index >= len(items):
            raise StudioDataError("叙事方案不存在")
        snapshot = items[item_index]
        self._save_adoption(project_id, "narrative", f"{generation_id}:{item_index}", snapshot)
        return snapshot

    def _save_adoption(self, project_id: int, kind: str, reference_id: str, snapshot: Any) -> None:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO adoptions(project_id,recommendation_kind,reference_id,snapshot_json,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET
                    recommendation_kind=excluded.recommendation_kind,
                    reference_id=excluded.reference_id,
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at
                """,
                (int(project_id), kind, reference_id, _json(snapshot), timestamp),
            )
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (timestamp, int(project_id)))

    def image_path_for_item(self, item_id: int) -> Path | None:
        item = self.visual_item(item_id)
        if item is None or item["image_status"] != "success" or not item["image_path"]:
            return None
        return Path(str(item["image_path"]))
