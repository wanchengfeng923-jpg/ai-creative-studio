from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets


class AuthDataError(RuntimeError):
    """Authentication data validation error with safe messaging."""


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
