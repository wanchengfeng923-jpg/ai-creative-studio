"""AI 服务配置契约，供从 ERP 提取的创意引擎使用。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any


@dataclass(frozen=True)
class AiServiceSettings:
    base_url: str
    api_key: str
    model: str
    daily_quota: int | None = None
    monthly_quota: int | None = None
    provider: str = "custom"
    updated_at: str = ""
    updated_by: int = 0


def normalize_ai_base_url(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    suffix = "/chat/completions"
    if text.lower().endswith(suffix):
        text = text[: -len(suffix)].rstrip("/")
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("AI基础地址必须是有效的 http 或 https 地址")
    return text
