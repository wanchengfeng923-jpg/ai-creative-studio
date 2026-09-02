"""POST /v1/chat/completions — 通过 ChatGPT Web 端实现 Chat Completions。"""

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from config import settings
from http_client import build_session
from web_fingerprint import WebFingerprint
from web_proof import build_legacy_requirements_token, build_proof_token
from auth_refresh import ensure_fresh_token, renew_access_token
from task_limiter import AiTaskQueueTimeoutError, ai_task_limiter

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """通过 ChatGPT Web 端实现 OpenAI 兼容的 chat completions。"""
    token = settings.chatgpt_access_token.strip()
    if not token:
        return JSONResponse(status_code=500, content={"error": {"message": "CHATGPT_ACCESS_TOKEN not configured"}})

    body: dict[str, Any] = await request.json()
    if "messages" not in body:
        return JSONResponse(status_code=400, content={"error": {"message": "messages is required"}})
    try:
        _conversation_context(body)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": {"message": str(exc)}})

    model = body.get("model", settings.web_chat_model)
    stream = body.get("stream", False)

    try:
        await ai_task_limiter.acquire()
    except AiTaskQueueTimeoutError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": str(exc)}},
            headers={"Retry-After": "2"},
        )

    if stream:
        return StreamingResponse(
            _stream_chat_with_slot_release(token, model, body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    try:
        result = await _complete_chat(token, model, body)
        if _response_is_auth_failure(result):
            result = await _refresh_and_retry_chat(model, body)
        return result
    except Exception as e:
        # Access tokens can be revoked before their JWT expiry. Refresh once
        # when the upstream boundary explicitly reports an authentication error.
        if _exception_is_auth_failure(e):
            try:
                return await _refresh_and_retry_chat(model, body)
            except Exception as refreshed_error:
                e = refreshed_error
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=502, content={"error": {"message": str(e)}})
    finally:
        ai_task_limiter.release()


def _response_is_auth_failure(response: JSONResponse) -> bool:
    if response.status_code not in {401, 403, 502}:
        return False
    body = getattr(response, "body", b"")
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    return any(marker in text for marker in ("upstream 401", "upstream 403", "Requirements failed: 401", "Requirements failed: 403", "Prepare failed: 401", "Prepare failed: 403"))


def _exception_is_auth_failure(error: Exception) -> bool:
    text = str(error)
    return any(marker in text for marker in ("Requirements failed: 401", "Requirements failed: 403", "Prepare failed: 401", "Prepare failed: 403"))


async def _refresh_and_retry_chat(model: str, body: dict[str, Any]) -> JSONResponse:
    await renew_access_token()
    return await _complete_chat(settings.chatgpt_access_token.strip(), model, body)


async def _stream_chat_with_slot_release(token: str, model: str, body: dict[str, Any]):
    try:
        async for chunk in _stream_chat(token, model, body):
            yield chunk
    finally:
        ai_task_limiter.release()


async def _complete_chat(token: str, model: str, body: dict[str, Any]) -> JSONResponse:
    """非流式 chat completion。"""
    fp = WebFingerprint()
    base = settings.chatgpt_base_url.rstrip("/")

    async with build_session() as session:
        # 自动续期：临近过期时用会话 Cookie 换取新 token
        token = await ensure_fresh_token()
        # 获取 requirements
        reqs = await _get_requirements(session, fp, base, token)

        # 准备对话
        conversation_id, parent_message_id = _conversation_context(body)
        conduit = await _prepare_conversation(
            session, fp, base, token, model, reqs,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
        )

        # 发起对话
        messages = body.get("messages", [])
        prompt = _messages_to_prompt(messages)

        path = "/backend-api/f/conversation"
        conv_body = _build_conversation_body(
            model, prompt,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
        )
        headers = fp.image_headers(token, path, reqs["token"], reqs["proof_token"], reqs["so_token"], conduit=conduit, accept="text/event-stream")

        resp = await session.post(f"{base}{path}", json=conv_body, headers=headers)
        if resp.status_code >= 400:
            return JSONResponse(status_code=resp.status_code, content={"error": {"message": f"upstream {resp.status_code}: {resp.text[:300]}"}})

        # 解析完整响应
        content, response_conversation_id, assistant_message_id = _parse_chat_response(resp.text)

        # 粗略估算 token
        prompt_tokens = len(prompt) // 4 + 1
        completion_tokens = len(content) // 4 + 1

        return JSONResponse(status_code=200, content={
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
            "conversation_id": response_conversation_id or conversation_id,
            "assistant_message_id": assistant_message_id,
        })


async def _stream_chat(token: str, model: str, body: dict[str, Any]):
    """流式 chat completion — 先获取完整响应，再逐步输出给客户端。"""
    fp = WebFingerprint()
    base = settings.chatgpt_base_url.rstrip("/")

    async with build_session() as session:
        # 自动续期：临近过期时用会话 Cookie 换取新 token
        token = await ensure_fresh_token()
        # 获取 requirements
        reqs = await _get_requirements(session, fp, base, token)

        # 准备对话
        conversation_id, parent_message_id = _conversation_context(body)
        conduit = await _prepare_conversation(
            session, fp, base, token, model, reqs,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
        )

        # 发起对话
        messages = body.get("messages", [])
        prompt = _messages_to_prompt(messages)

        path = "/backend-api/f/conversation"
        conv_body = _build_conversation_body(
            model, prompt,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
        )
        headers = fp.image_headers(token, path, reqs["token"], reqs["proof_token"], reqs["so_token"], conduit=conduit, accept="text/event-stream")

        resp = await session.post(f"{base}{path}", json=conv_body, headers=headers)
        if resp.status_code >= 400:
            error_chunk = json.dumps({"error": {"message": f"upstream {resp.status_code}: {resp.text[:300]}"}})
            yield f"data: {error_chunk}\n\n"
            return

        chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        # 解析完整 SSE，收集所有增量内容
        last_content = ""
        chunks: list[str] = []

        for line in resp.text.split("\n"):
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            new_content = _extract_content_from_web_chunk(payload)
            if new_content and len(new_content) > len(last_content):
                delta = new_content[len(last_content):]
                last_content = new_content
                chunks.append(delta)

        # 逐 chunk 输出给客户端
        for delta in chunks:
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # finish
        finish_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(finish_chunk)}\n\n"
        yield "data: [DONE]\n\n"


async def _get_requirements(session, fp: WebFingerprint, base: str, token: str) -> dict[str, str]:
    """获取 chat requirements。"""
    path = "/backend-api/sentinel/chat-requirements"
    body = {"p": build_legacy_requirements_token(fp.user_agent)}
    headers = fp.base_headers(token, path)
    headers["Content-Type"] = "application/json"

    resp = await session.post(f"{base}{path}", json=body, headers=headers)
    if resp.status_code >= 400:
        raise Exception(f"Requirements failed: {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    req_token = data.get("token", "")
    if not req_token:
        raise Exception("Requirements missing token")

    proof = ""
    pow_data = data.get("proofofwork", {})
    if pow_data.get("required") and pow_data.get("seed") and pow_data.get("difficulty"):
        proof = build_proof_token(pow_data["seed"], pow_data["difficulty"], fp.user_agent)

    return {"token": req_token, "proof_token": proof, "so_token": data.get("so_token", "")}


async def _prepare_conversation(
    session,
    fp: WebFingerprint,
    base: str,
    token: str,
    model: str,
    reqs: dict[str, str],
    *,
    conversation_id: str = "",
    parent_message_id: str = "client-created-root",
) -> str:
    """准备对话获取 conduit token。"""
    path = "/backend-api/f/conversation/prepare"
    body = {
        "action": "next",
        "fork_from_shared_post": False,
        "parent_message_id": parent_message_id or "client-created-root",
        "model": model,
        "client_prepare_state": "none",
        "timezone_offset_min": -480,
        "timezone": "Asia/Shanghai",
        "conversation_mode": {"kind": "primary_assistant"},
        "system_hints": [],
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "client_contextual_info": {"app_name": "chatgpt.com"},
        "thinking_effort": "standard",
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    headers = fp.image_headers(token, path, reqs["token"], reqs["proof_token"], reqs["so_token"], accept="*/*")
    resp = await session.post(f"{base}{path}", json=body, headers=headers)
    if resp.status_code >= 400:
        raise Exception(f"Prepare failed: {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    conduit = data.get("conduit_token", "")
    if not conduit:
        raise Exception("Prepare missing conduit token")
    return conduit


def _build_conversation_body(
    model: str,
    prompt: str,
    *,
    conversation_id: str = "",
    parent_message_id: str = "client-created-root",
) -> dict[str, Any]:
    """构造对话请求体。"""
    body = {
        "action": "next",
        "fork_from_shared_post": False,
        "parent_message_id": parent_message_id or "client-created-root",
        "model": model,
        "client_prepare_state": "success",
        "timezone_offset_min": -480,
        "timezone": "Asia/Shanghai",
        "conversation_mode": {"kind": "primary_assistant"},
        "enable_message_followups": True,
        "system_hints": [],
        "supports_buffering": True,
        "supported_encodings": [],
        "client_contextual_info": {
            "is_dark_mode": False,
            "time_since_loaded": 30,
            "page_height": 1111,
            "page_width": 1731,
            "pixel_ratio": 1.5,
            "screen_height": 1440,
            "screen_width": 2560,
            "app_name": "chatgpt.com",
        },
        "paragen_cot_summary_display_override": "allow",
        "force_parallel_switch": "auto",
        "thinking_effort": "standard",
        "messages": [{
            "id": str(uuid.uuid4()),
            "author": {"role": "user"},
            "create_time": int(time.time()),
            "content": {"content_type": "text", "parts": [prompt]},
            "metadata": {
                "developer_mode_connector_ids": [],
                "selected_github_repos": [],
                "selected_all_github_repos": False,
                "serialization_metadata": {"custom_symbol_offsets": []},
            },
        }],
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    return body


def _conversation_context(body: dict[str, Any]) -> tuple[str, str]:
    """读取并校验真实 ChatGPT 续聊所需的成对标识。"""

    conversation_id = str(body.get("conversation_id") or "").strip()
    parent_message_id = str(body.get("parent_message_id") or "").strip()
    if bool(conversation_id) != bool(parent_message_id):
        raise ValueError("conversation_id 和 parent_message_id 必须同时提供")
    for value in (conversation_id, parent_message_id):
        if len(value) > 256 or "\n" in value or "\r" in value:
            raise ValueError("AI会话标识格式无效")
    return conversation_id, parent_message_id or "client-created-root"


def _messages_to_prompt(messages: list[dict]) -> str:
    """将 OpenAI messages 格式转为单个 prompt 文本。"""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(text_parts)
        if content:
            if role == "system":
                parts.append(f"[System]: {content}")
            elif role == "assistant":
                parts.append(f"[Assistant]: {content}")
            else:
                parts.append(content)
    return "\n\n".join(parts)


def _parse_chat_response(sse_text: str) -> tuple[str, str, str]:
    """解析 ChatGPT Web SSE，返回正文、会话 ID 和最终助手消息 ID。"""
    last_content = ""
    conversation_id = ""
    assistant_message_id = ""
    for line in sse_text.split("\n"):
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        content, chunk_conversation_id, chunk_message_id = _extract_chat_chunk(payload)
        if chunk_conversation_id:
            conversation_id = chunk_conversation_id
        # 内容是累积的，取最长的那个
        if content and len(content) >= len(last_content):
            last_content = content
            assistant_message_id = chunk_message_id or assistant_message_id
    return last_content, conversation_id, assistant_message_id


def _extract_content_from_web_chunk(payload: str) -> str:
    """从 ChatGPT Web SSE chunk 中提取文本内容。"""
    return _extract_chat_chunk(payload)[0]


def _extract_chat_chunk(payload: str) -> tuple[str, str, str]:
    """提取单个 SSE chunk 的助手正文及真实会话标识。"""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return "", "", ""

    if not isinstance(data, dict):
        return "", "", ""

    # 新格式: {"v": {"message": {...}}} 或 {"p": "", "o": "add", "v": {"message": {...}}}
    v = data.get("v") if isinstance(data.get("v"), dict) else {}
    conversation_id = str(data.get("conversation_id") or v.get("conversation_id") or "").strip()
    msg = data.get("message")
    if not isinstance(msg, dict):
        msg = v.get("message")
    if not isinstance(msg, dict):
        return "", conversation_id, ""

    author = msg.get("author")
    if not isinstance(author, dict) or author.get("role") != "assistant":
        return "", conversation_id, ""

    assistant_message_id = str(msg.get("id") or "").strip()
    content = msg.get("content")
    if not isinstance(content, dict):
        return "", conversation_id, assistant_message_id
    parts = content.get("parts", [])
    # 返回最后一个字符串 part（即使为空也返回，因为内容是累积的）
    for part in reversed(parts):
        if isinstance(part, str):
            return part, conversation_id, assistant_message_id
    return "", conversation_id, assistant_message_id


# 账户探测失败时的候选模型（真实可用列表以 /backend-api/models 为准）
FALLBACK_WEB_MODELS = (
    "gpt-5-6", "gpt-5-5", "gpt-5-6-mini", "gpt-5-5-mini",
    "gpt-5-6-t-mini", "gpt-5-4-t-mini", "gpt-5-3-mini", "gpt-5-6-t-mini-mini", "auto",
)


@router.get("/v1/models")
async def list_models():
    """返回当前 ChatGPT 账号可用的模型列表；探测失败时返回候选模型。"""
    token = await ensure_fresh_token()
    if not token:
        return JSONResponse(status_code=500, content={"object": "list", "data": [], "detected": False, "error": "CHATGPT_ACCESS_TOKEN not configured"})
    fp = WebFingerprint()
    base = settings.chatgpt_base_url.rstrip("/")
    try:
        async with build_session() as session:
            path = "/backend-api/models"
            headers = fp.base_headers(token, path)
            headers["Accept"] = "application/json"
            resp = await session.get(f"{base}{path}", headers=headers)
            if resp.status_code < 400:
                payload = resp.json()
                raw = payload.get("models") if isinstance(payload, dict) else None
                if isinstance(raw, list):
                    ids: list[str] = []
                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        slug = str(item.get("slug") or "").strip()
                        if slug and slug not in ids:
                            ids.append(slug)
                    if ids:
                        return JSONResponse(status_code=200, content={"object": "list", "data": [{"id": model_id} for model_id in ids], "detected": True})
    except Exception:
        pass
    return JSONResponse(status_code=200, content={"object": "list", "data": [{"id": model_id} for model_id in FALLBACK_WEB_MODELS], "detected": False})
