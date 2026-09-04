"""生成链路的脱敏结构化观测实现。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Mapping


SAFE_EVENT_KEYS = frozenset({
    "event", "run_id", "request_id", "operation_id", "project_id", "kind", "stage",
    "status", "error_code", "retryable", "attempt", "latency_ms", "input_tokens",
    "output_tokens", "total_tokens", "usage_source", "provider", "model",
})
PRIVATE_EVENT_KEYS = frozenset({"prompt", "content", "raw_response", "token", "secret", "path", "body"})


def sanitize_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """只保留有限字段和标量，防止 prompt/正文随日志扩散。"""
    clean: dict[str, Any] = {}
    for key, value in event.items():
        key_text = str(key)
        if key_text in PRIVATE_EVENT_KEYS or key_text not in SAFE_EVENT_KEYS:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[key_text] = value
    return clean


@dataclass
class StructuredObservability:
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("creative_studio.observability"))
    events: list[dict[str, Any]] = field(default_factory=list)
    max_events: int = 1000

    def record(self, event: Mapping[str, Any]) -> None:
        clean = sanitize_event(event)
        self.events.append(clean)
        limit = max(1, int(self.max_events))
        if len(self.events) > limit:
            del self.events[: len(self.events) - limit]
        self.logger.info("creative_studio_event %s", json.dumps(clean, ensure_ascii=False, sort_keys=True))


__all__ = ["StructuredObservability", "sanitize_event"]
