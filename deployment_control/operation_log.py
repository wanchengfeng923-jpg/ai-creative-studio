"""Structured, aggressively redacted operation logging."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_SENSITIVE_KEY = re.compile(
    r"(token|secret|password|passwd|cookie|authorization|auth[_-]?header|api[_-]?key)",
    re.IGNORECASE,
)
_CREDENTIAL_PROXY_URL = re.compile(
    r"(?i)\b(?:https?|socks(?:4|5)?):\/\/[^\/\s:@]+:[^\/\s@]+@[^\/\s]+"
)
_KEY_VALUE_SECRET = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key)\s*=\s*[^,\s;]+"
)
_INLINE_SECRET_HEADER = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)\s*:\s*[^\r\n,;]+"
)


def sanitize_sensitive(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact secrets without reading any environment files."""
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_sensitive(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_sensitive(item) for item in value]
    if isinstance(value, str):
        redacted = _CREDENTIAL_PROXY_URL.sub("[REDACTED_PROXY_URL]", value)
        redacted = _KEY_VALUE_SECRET.sub(
            lambda match: f"{match.group(1)}=[REDACTED]",
            redacted,
        )
        return _INLINE_SECRET_HEADER.sub(
            lambda match: f"{match.group(1)}: [REDACTED]",
            redacted,
        )
    return value


class OperationLogger:
    """Append one sanitized JSON object per operation."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    def record(self, *, action: str, result: str, details: Mapping[str, Any] | None = None) -> None:
        """Append a structured event; sensitive fields are removed before serialization."""
        entry = {
            "timestamp": self._clock().isoformat(),
            "action": action,
            "result": result,
            "details": sanitize_sensitive(dict(details or {})),
        }
        serialized = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(serialized + "\n")
