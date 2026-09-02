from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Any


class AuthDataError(RuntimeError):
    """Authentication data validation error with safe messaging."""


class AuthError(RuntimeError):
    """Safe authentication failure suitable for an HTTP response."""


class AuthRateLimitError(AuthError):
    pass


class AuthPermissionError(AuthError):
    pass


@dataclass(frozen=True)
class AuthResult:
    user: dict[str, Any]
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class SessionContext:
    user: dict[str, Any]
    session: dict[str, Any]


_GENERIC_LOGIN_ERROR = "用户名或密码错误"
_DUMMY_PASSWORD_HASH: str | None = None


_USERNAME_RE = re.compile(r"^[a-z0-9._-]+$")
_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 390000
_PBKDF2_SALT_BYTES = 16
_PBKDF2_DKLEN = 32
_TOKEN_BYTES = 32


def normalize_username(value: str) -> str:
    if not isinstance(value, str):
        raise AuthDataError("invalid username")
    normalized = value.lower()
    if not (3 <= len(normalized) <= 64):
        raise AuthDataError("invalid username")
    if not _USERNAME_RE.fullmatch(normalized):
        raise AuthDataError("invalid username")
    return normalized


def validate_password(value: str) -> None:
    if not isinstance(value, str) or len(value) < 12:
        raise AuthDataError("invalid password")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_PBKDF2_DKLEN,
    )
    return "$".join(
        (
            _PBKDF2_ALGORITHM,
            str(_PBKDF2_ITERATIONS),
            _b64encode(salt),
            _b64encode(digest),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or not isinstance(encoded, str):
        return False
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded.split("$")
        if algorithm != _PBKDF2_ALGORITHM:
            return False
        iterations = int(iterations_text)
        if iterations != _PBKDF2_ITERATIONS:
            return False
        salt = _b64decode(salt_text)
        expected_digest = _b64decode(digest_text)
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected_digest),
        )
    except (ValueError, TypeError, UnicodeError, base64.binascii.Error):
        return False
    return hmac.compare_digest(actual_digest, expected_digest)


def new_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def token_digest(token: str) -> str:
    if not isinstance(token, str):
        raise AuthDataError("invalid token")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _dummy_hash() -> str:
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-value")
    return _DUMMY_PASSWORD_HASH


class AuthService:
    """Application-level authentication and account-management policy."""

    def __init__(self, repository: Any, cookie_secure: bool = False) -> None:
        self.repository = repository
        self.cookie_secure = bool(cookie_secure)

    def login(self, username: str, password: str, client_ip: str = "", user_agent: str = "") -> AuthResult:
        try:
            normalized = normalize_username(username)
        except AuthDataError:
            verify_password(password if isinstance(password, str) else "", _dummy_hash())
            raise AuthError(_GENERIC_LOGIN_ERROR)
        attempt = self.repository.get_login_attempt(normalized, client_ip)
        if attempt and attempt.get("is_locked"):
            raise AuthRateLimitError("登录尝试过于频繁，请稍后再试")
        credentials = self.repository.get_user_credentials(normalized)
        encoded = credentials.get("password_hash") if credentials else _dummy_hash()
        password_ok = verify_password(password, str(encoded))
        if not credentials or not password_ok or not bool(credentials.get("is_active")):
            failed = self.repository.record_login_failure(normalized, client_ip)
            if failed.get("is_locked"):
                raise AuthRateLimitError("登录尝试过于频繁，请稍后再试")
            raise AuthError(_GENERIC_LOGIN_ERROR)
        self.repository.clear_login_attempt_window(normalized, client_ip)
        session_token = new_token()
        csrf_token = new_token()
        session = self.repository.create_session(
            int(credentials["id"]), session_token, csrf_token, client_ip, user_agent
        )
        self.repository.mark_user_login(int(credentials["id"]))
        user = self.repository.get_user(int(credentials["id"])) or {}
        self.repository.record_audit(int(credentials["id"]), "login", "user", str(credentials["id"]), metadata={"ip": client_ip})
        return AuthResult(user=user, session_token=session_token, csrf_token=csrf_token)

    def authenticate_session(self, session_token: str | None, csrf_token: str | None = None) -> SessionContext | None:
        if not session_token:
            return None
        session = self.repository.get_session(session_token)
        if not session:
            return None
        if csrf_token is not None and not self.repository.verify_session_csrf(session_token, csrf_token):
            return None
        if not self.repository.touch_session(session_token):
            return None
        user = self.repository.get_user(int(session["user_id"]))
        if not user or not user.get("is_active"):
            return None
        return SessionContext(user=user, session=session)

    def logout(self, session_token: str | None, actor_user_id: int | None = None) -> None:
        if session_token:
            self.repository.revoke_session(session_token)
        if actor_user_id is not None:
            self.repository.record_audit(actor_user_id, "logout", "session", result="success")

    def init_admin(self, username: str, password: str) -> dict[str, Any]:
        return self.repository.create_bootstrap_admin(username, password)

    def change_password(self, user_id: int, current_password: str, new_password: str) -> dict[str, Any]:
        credentials = self.repository.get_user_credentials(int(user_id))
        if not credentials or not verify_password(current_password, str(credentials["password_hash"])):
            raise AuthError("当前密码错误")
        validate_password(new_password)
        user = self.repository.reset_user_password(int(user_id), new_password, must_change_password=False)
        self.repository.record_audit(user_id, "change_password", "user", str(user_id))
        return user

    def _require_admin(self, actor_user_id: int) -> dict[str, Any]:
        actor = self.repository.get_user(int(actor_user_id))
        if not actor or not actor.get("is_active") or actor.get("role") != "admin":
            raise AuthPermissionError("需要管理员权限")
        return actor

    def create_user(self, actor_user_id: int, username: str, password: str) -> dict[str, Any]:
        self._require_admin(actor_user_id)
        user = self.repository.create_user(username, password)
        self.repository.record_audit(actor_user_id, "create_user", "user", str(user["id"]))
        return user

    def set_user_active(self, actor_user_id: int, target_user_id: int, is_active: bool) -> dict[str, Any]:
        self._require_admin(actor_user_id)
        target = self.repository.get_user(int(target_user_id))
        if not target or target.get("role") != "user":
            raise AuthPermissionError("只能管理普通账号")
        user = self.repository.set_user_active(int(target_user_id), bool(is_active))
        self.repository.record_audit(actor_user_id, "set_user_active", "user", str(target_user_id), metadata={"status": bool(is_active)})
        return user

    def reset_user_password(self, actor_user_id: int, target_user_id: int) -> tuple[dict[str, Any], str]:
        self._require_admin(actor_user_id)
        target = self.repository.get_user(int(target_user_id))
        if not target or target.get("role") != "user":
            raise AuthPermissionError("只能管理普通账号")
        temporary_password = secrets.token_urlsafe(18)
        user = self.repository.reset_user_password(int(target_user_id), temporary_password, must_change_password=True)
        self.repository.record_audit(actor_user_id, "reset_password", "user", str(target_user_id))
        return user, temporary_password
