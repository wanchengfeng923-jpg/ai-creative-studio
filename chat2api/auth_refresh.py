"""Access Token 自动续期：到期前用 ChatGPT 网页会话 Cookie 换取新 accessToken。

原理：
- ChatGPT 网页版不向客户端暴露 refresh token；浏览器通过会话 Cookie
  （__Secure-next-auth.session-token）在 /api/auth/session 静默续期。
- 网关在 access token 剩余有效期小于提前量时，带 Cookie 调用
  /api/auth/session 获取新的 accessToken，并把新旧 token 一并写回 .env，
  重启网关后仍然有效。
- 若未配置 CHATGPT_SESSION_COOKIE，则维持手动更换 token 的方式。
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from config import settings

ENV_PATH = Path(os.environ.get("CHATGPT_ENV_PATH") or Path.cwd() / ".env").resolve()

OPENAI_CLIENT_ID = "pdlLIX2Y72MIl2rhLhTE9VV9bN905kBh"
OPENAI_REDIRECT_URI = "com.openai.chat://auth0.openai.com/ios/com.openai.chat/callback"
AUTH0_TOKEN_URL = "https://auth0.openai.com/oauth/token"

# 会话 Cookie 建议更换周期（天），用于页面自动提醒
COOKIE_VALID_DAYS = 30


def token_expiry(token: str) -> float:
    """解析 JWT 的 exp 字段；解析失败返回 0。"""

    text = str(token or "").strip()
    try:
        _header, payload, _signature = text.split(".")
        padding = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + padding))
        return float(data.get("exp") or 0)
    except Exception:
        return 0.0


def should_refresh(token: str, lead_hours: int = 72) -> bool:
    """剩余有效期低于提前量时返回 True。"""

    exp = token_expiry(token)
    if exp <= 0:
        return False
    return bool(exp - time.time() < int(lead_hours or 0) * 3600)


def env_value(name: str) -> str:
    """读取 .env 中的原始值（不依赖 pydantic 已加载实例）。"""

    if not ENV_PATH.is_file():
        return ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        strip = line.strip()
        if strip.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return ""


def persist_env_pair(access_token: str, session_cookie: str = "", refresh_token: str = "") -> None:
    """把新的 access token / 会话 Cookie / refresh token 写回 .env，保留其它配置。"""

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    def upsert(lines, name, value):
        prefix = name + "="
        escaped = value.replace("\\", "\\\\").replace("\r", "").replace("\n", "")
        for index, line in enumerate(lines):
            if line.strip().startswith(prefix):
                lines[index] = prefix + escaped
                return True
        lines.append(prefix + escaped)
        return True

    upsert(lines, "CHATGPT_ACCESS_TOKEN", access_token)
    if session_cookie:
        upsert(lines, "CHATGPT_SESSION_COOKIE", session_cookie)
    if refresh_token:
        upsert(lines, "CHATGPT_REFRESH_TOKEN", refresh_token)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist_env_values(**updates: str) -> None:
    """批量 upsert 若干 .env 变量并写回，保留其它配置。"""

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    def upsert(name, value):
        prefix = name + "="
        escaped = (value or "").replace("\\", "\\\\").replace("\r", "").replace("\n", "")
        for index, line in enumerate(lines):
            if line.strip().startswith(prefix):
                lines[index] = prefix + escaped
                return
        lines.append(prefix + escaped)

    for name, value in updates.items():
        upsert(name, value)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stamp_cookie_update(cookie: str) -> None:
    """记录本次更换会话 Cookie 的时刻，并把新值落盘 + 更新内存。"""

    persist_env_values(CHATGPT_SESSION_COOKIE=cookie, CHATGPT_COOKIE_UPDATED_AT=str(int(time.time())))
    settings.chatgpt_session_cookie = cookie


def cookie_updated_at() -> float:
    """上次更换会话 Cookie 的时间（epoch）；没有记录时返回当前时间。"""

    raw = env_value("CHATGPT_COOKIE_UPDATED_AT")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value


def next_cookie_update_ts() -> float:
    """建议下次更换会话 Cookie 的时间（epoch）。"""

    base = cookie_updated_at() or time.time()
    return base + COOKIE_VALID_DAYS * 86400


async def renew_access_token() -> str:
    """带会话 Cookie 调用 /api/auth/session 获取新 accessToken，返回新 token。

    CHATGPT_SESSION_COOKIE 保存完整的 Cookie 字符串（NextAuth 会拆成
    __Secure-next-auth.session-token.0/.1 多个 name=value 对，用 ; 分隔）。
    若服务端通过 Set-Cookie 轮换了会话 Cookie，新值也会一并保存。
    """

    from http_client import build_session
    from web_fingerprint import WebFingerprint

    cookie_header = _session_cookie_header(settings.chatgpt_session_cookie)
    if not cookie_header:
        raise RuntimeError("CHATGPT_SESSION_COOKIE not configured")

    base = settings.chatgpt_base_url.rstrip("/")
    path = "/api/auth/session"
    fp = WebFingerprint()
    headers = fp.base_headers("", path)
    headers["Accept"] = "application/json"
    headers["Cookie"] = cookie_header

    async with build_session() as session:
        resp = await session.get(f"{base}{path}", headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"session refresh failed: {resp.status_code}")
        payload = resp.json()
        new_token = str(payload.get("accessToken") or "").strip() if isinstance(payload, dict) else ""
        if not new_token:
            raise RuntimeError("session refresh missing accessToken")

    # 服务端可能轮换会话 Cookie：合并 Set-Cookie 中的 session-token 各分片
    rotated_cookie = _apply_set_cookie_rotation(cookie_header, resp.headers.get_list("set-cookie") or [])

    settings.chatgpt_access_token = new_token
    settings.chatgpt_session_cookie = rotated_cookie
    persist_env_values(
        CHATGPT_ACCESS_TOKEN=new_token,
        CHATGPT_SESSION_COOKIE=rotated_cookie,
        CHATGPT_COOKIE_UPDATED_AT=str(int(time.time())),
    )
    return new_token


def _apply_set_cookie_rotation(cookie_header: str, set_cookies: list[str]) -> str:
    """把 Set-Cookie 中带 session-token 前缀的分片合并进 Cookie 字符串。"""

    pairs = {}
    for piece in cookie_header.split(";"):
        piece = piece.strip()
        if "=" in piece:
            k, v = piece.split("=", 1)
            pairs[k.strip()] = v.strip()
    session_markers = ("__Secure-next-auth.session-token", "__Secure-next-auth.session-token.0", "__Secure-next-auth.session-token.1")
    for raw in set_cookies:
        name, _, value = raw.partition("=")
        name = name.strip()
        if name in session_markers:
            value = value.split(";", 1)[0].strip()
            if value:
                pairs[name] = value
    return "; ".join(f"{k}={v}" for k, v in pairs.items())


def _session_cookie_header(value: str) -> str:
    """把保存的会话 Cookie 规整为 'name=value; ...' 的 Cookie 头。

    同时兼容两种存法：完整的 name=value 分片串，或单段裸的 session-token 值。
    """
    text = (value or "").strip()
    if not text:
        return ""
    if "=" in text:
        return text
    return f"__Secure-next-auth.session-token={text}"


async def renew_via_refresh_token() -> str:
    """用 OpenAI auth0 刷新令牌直接换取 access token（Chat2API 的 refreshToken 方式）。"""

    refresh_token = settings.chatgpt_refresh_token.strip()
    if not refresh_token:
        raise RuntimeError("CHATGPT_REFRESH_TOKEN not configured")

    from http_client import build_session
    from web_fingerprint import WebFingerprint

    fp = WebFingerprint()
    headers = fp.base_headers("", "/oauth/token")
    headers["Content-Type"] = "application/json"

    async with build_session() as session:
        resp = await session.post(
            AUTH0_TOKEN_URL,
            json={
                "client_id": OPENAI_CLIENT_ID,
                "grant_type": "refresh_token",
                "redirect_uri": OPENAI_REDIRECT_URI,
                "refresh_token": refresh_token,
            },
            headers=headers,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"oauth refresh failed: {resp.status_code} {resp.text[:200]}")
    payload = resp.json()
    if not isinstance(payload, dict):
        raise RuntimeError("oauth refresh invalid payload")
    new_token = str(payload.get("access_token") or "").strip()
    if not new_token:
        raise RuntimeError("oauth refresh missing access_token")
    new_refresh = str(payload.get("refresh_token") or "").strip() or refresh_token

    settings.chatgpt_access_token = new_token
    settings.chatgpt_refresh_token = new_refresh
    persist_env_pair(new_token, refresh_token=new_refresh)
    return new_token


async def ensure_fresh_token() -> str:
    """返回当前 access token；到期前自动续期。

    优先使用 auth0 refresh token（最可靠）；未配置时回退会话 Cookie；都未配置则维持原状。
    """

    token = settings.chatgpt_access_token.strip()
    # 若 .env 中的 token 已被外部更新（换号、其他进程续期等），直接采用文件里的值，
    # 避免长期运行的进程继续使用已被吊销的旧 token。
    try:
        persisted = env_value("CHATGPT_ACCESS_TOKEN")
    except Exception:
        persisted = ""
    if persisted and persisted != token:
        settings.chatgpt_access_token = persisted
        token = persisted
    has_refresh = bool(settings.chatgpt_refresh_token.strip())
    has_cookie = bool(settings.chatgpt_session_cookie.strip())
    if not token or (not has_refresh and not has_cookie):
        return token
    if not should_refresh(token, settings.refresh_lead_hours):
        return token
    try:
        if has_refresh:
            token = await renew_via_refresh_token()
        else:
            token = await renew_access_token()
    except Exception as exc:  # noqa: BLE001 - 续期失败不阻断现有流程
        print(f"[auth] auto refresh failed, keep current token: {exc}")
    return settings.chatgpt_access_token.strip()
