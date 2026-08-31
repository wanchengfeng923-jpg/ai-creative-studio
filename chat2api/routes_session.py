"""会话控制接口：网页 ERP 调用。

- GET  /v1/session-info   查当前会话/自动续期/下次更换 Cookie 时间。
- POST /v1/session         传入新会话 Cookie，立即更新并换新 access token。
两者均需 X-Control-Token 与配置的 CHATGPT_CONTROL_TOKEN 一致（未配置则仅本机）。
"""

from __future__ import annotations

import time
from ipaddress import ip_address

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import settings
from auth_refresh import (
    cookie_updated_at,
    next_cookie_update_ts,
    renew_access_token,
    stamp_cookie_update,
    token_expiry,
)

router = APIRouter()


def _authorized(request: Request) -> bool:
    token = settings.chatgpt_control_token.strip()
    if not token:
        client = getattr(request, "client", None)
        host = str(getattr(client, "host", "") or "").split("%", 1)[0]
        try:
            return ip_address(host).is_loopback
        except ValueError:
            return False
    supplied = (request.headers.get("x-control-token") or "").strip()
    return supplied == token


def _auth_fail():
    return JSONResponse(status_code=403, content={"ok": False, "error": "unauthorized"})


def _overview():
    exp = token_expiry(settings.chatgpt_access_token)
    return {
        "ok": True,
        "has_token": bool(settings.chatgpt_access_token.strip()),
        "auto_refresh": bool(settings.chatgpt_session_cookie.strip()),
        "token_expires_at": int(exp) if exp else None,
        "seconds_to_expire": max(0, int(exp - time.time())) if exp else None,
        "cookie_configured": bool(settings.chatgpt_session_cookie.strip()),
        "cookie_updated_at": int(cookie_updated_at()) or None,
        "next_cookie_update": int(next_cookie_update_ts()),
    }


@router.get("/v1/session-info")
async def session_info(request: Request):
    if not _authorized(request):
        return _auth_fail()
    return JSONResponse(_overview())


@router.post("/v1/session")
async def set_session(request: Request):
    if not _authorized(request):
        return _auth_fail()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid json"})
    cookie = str((body or {}).get("session_cookie") or "").strip()
    if not cookie:
        return JSONResponse(status_code=400, content={"ok": False, "error": "session_cookie required"})

    # 1) 落盘 + 记录更换时刻
    stamp_cookie_update(cookie)
    # 2) 立即用新会话 Cookie 换新 access token（失败不阻断保存 Cookie，但会提示）
    error = ""
    try:
        await renew_access_token()
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:200]

    overview = _overview()
    if error:
        return JSONResponse({
            **overview,
            "ok": False,
            "error": error,
            "cookie_saved": True,
        })
    return JSONResponse({
        **overview,
        "ok": True,
        "error": "",
    })
