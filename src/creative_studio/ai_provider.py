"""独立工作台所需的最小 OpenAI 兼容地址适配。"""

from .ai_service_settings import normalize_ai_base_url


def chat_completions_url(base_url: str) -> str:
    return f"{normalize_ai_base_url(base_url)}/chat/completions"
