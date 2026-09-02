"""POST /v1/images/generations & /v1/images/edits — 通过 ChatGPT Web 端生成图片。"""

import base64
import asyncio
import hmac
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import settings
from image_job_store import ImageJobStore
from image_utils import SIZE_TABLE, resolve_image_size
from web_client import WebImageClient
from task_limiter import AiTaskQueueTimeoutError, ai_task_limiter

router = APIRouter()

# 图片保存目录
IMAGES_DIR = os.path.abspath(os.environ.get("CHATGPT_IMAGES_DIR") or os.path.join(os.getcwd(), "images"))
os.makedirs(IMAGES_DIR, exist_ok=True)
IMAGE_JOB_DIR = Path(os.environ.get("CHATGPT_IMAGE_JOB_DIR") or os.path.join(os.getcwd(), "image_job_state"))
IMAGE_JOB_STORE = ImageJobStore(IMAGE_JOB_DIR)
IMAGE_JOB_STORE.recover_interrupted()
BACKGROUND_IMAGE_TASKS: dict[str, asyncio.Task] = {}


class ImageGenerationError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


@router.post("/v1/images/generations")
async def image_generations(request: Request):
    body: dict[str, Any] = await request.json()
    return await _create_image(body, edit=False)


@router.post("/v1/images/edits")
async def image_edits(request: Request):
    body: dict[str, Any] = await request.json()
    return await _create_image(body, edit=True)


def _control_authorized(request: Request) -> bool:
    expected = str(settings.chatgpt_control_token or "").strip()
    if not expected:
        return True
    supplied = str(request.headers.get("X-Control-Token") or "").strip()
    return bool(supplied and hmac.compare_digest(supplied, expected))


@router.post("/v1/images/jobs")
async def submit_image_job(request: Request):
    if not _control_authorized(request):
        return JSONResponse(status_code=401, content={"error": {"message": "unauthorized"}})
    body: dict[str, Any] = await request.json()
    request_id = str(body.get("request_id") or "").strip()
    if not request_id or not str(body.get("prompt") or "").strip():
        return JSONResponse(status_code=400, content={"error": {"message": "request_id and prompt are required"}})
    job = IMAGE_JOB_STORE.create(request_id)
    job_id = str(job["job_id"])
    if job["status"] == "queued" and job_id not in BACKGROUND_IMAGE_TASKS:
        task = asyncio.create_task(_run_image_job(job_id, body))
        BACKGROUND_IMAGE_TASKS[job_id] = task
        task.add_done_callback(lambda _task, key=job_id: BACKGROUND_IMAGE_TASKS.pop(key, None))
    return JSONResponse(status_code=202, content={"job_id": job_id, "status": job["status"]})


@router.get("/v1/images/jobs/{job_id}")
async def image_job_status(job_id: str, request: Request):
    if not _control_authorized(request):
        return JSONResponse(status_code=401, content={"error": {"message": "unauthorized"}})
    job = IMAGE_JOB_STORE.get(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": {"message": "image job not found"}})
    return JSONResponse(content=job)


async def _run_image_job(job_id: str, body: dict[str, Any]) -> None:
    try:
        IMAGE_JOB_STORE.update(job_id, status="generating")
        data = await _generate_image_data(body, edit=False)
        image_url = str((data[0] if data else {}).get("url") or "").strip()
        if not image_url:
            raise ImageGenerationError(502, "failed to save images")
        IMAGE_JOB_STORE.update(
            job_id,
            status="success",
            image_url=image_url,
            conversation_id=str(body.get("_result_conversation_id") or ""),
            parent_message_id=str(body.get("_result_parent_message_id") or ""),
        )
    except Exception as error:
        IMAGE_JOB_STORE.update(job_id, status="failed", error=" ".join(str(error).split())[:500])


async def _create_image(body: dict[str, Any], edit: bool) -> JSONResponse:
    try:
        data = await _generate_image_data(body, edit=edit)
    except ImageGenerationError as error:
        return JSONResponse(status_code=error.status_code, content={"error": {"message": str(error)}})
    return JSONResponse(status_code=200, content={"created": int(time.time()), "data": data})


async def _generate_image_data(body: dict[str, Any], edit: bool) -> list[dict[str, str]]:
    token = settings.chatgpt_access_token.strip()
    if not token:
        raise ImageGenerationError(500, "CHATGPT_ACCESS_TOKEN not configured")

    prompt = body.get("prompt", "")
    if not prompt:
        raise ImageGenerationError(400, "prompt is required")

    n = body.get("n", 1) or body.get("count", 1) or 1
    size = body.get("size", "1024x1024")
    ratio = body.get("ratio") or body.get("aspect_ratio") or ""
    web_model = body.get("web_model") or settings.web_image_model

    # 参考图
    ref_images = body.get("ref_assets", []) or body.get("images", []) or []
    if body.get("image"):
        ref_images = [body["image"]] + ref_images
    if edit and not ref_images:
        # edit 模式但没有参考图，当普通生成处理
        pass

    # 从 size 推导 ratio
    if not ratio:
        ratio = _ratio_from_size(size)

    client = WebImageClient(
        session_token=token,
        base_url=settings.chatgpt_base_url,
        proxy_url=settings.proxy_url,
    )

    try:
        await ai_task_limiter.acquire()
    except AiTaskQueueTimeoutError as exc:
        raise ImageGenerationError(503, str(exc)) from exc

    try:
        assets = await client.generate_image(
            prompt=prompt,
            size=size,
            ratio=ratio,
            n=n,
            ref_images=ref_images,
            web_model=web_model,
            conversation_id=str(body.get("conversation_id") or ""),
            parent_message_id=str(body.get("parent_message_id") or ""),
        )
        body["_result_conversation_id"] = client.last_conversation_id
        body["_result_parent_message_id"] = client.last_parent_message_id
    except Exception as e:
        raise ImageGenerationError(502, str(e)) from e
    finally:
        ai_task_limiter.release()

    if not assets:
        raise ImageGenerationError(502, "returned 0 images")

    # 保存图片到本地，返回可访问的 URL
    data = []
    for asset in assets:
        url = asset["url"]
        mime = asset.get("mime", "image/png")
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)

        # 从 data URL 解码保存
        if url.startswith("data:"):
            _, b64_data = url.split(",", 1)
            img_bytes = base64.b64decode(b64_data)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
        else:
            # 直接是文件路径或外部 URL（不太可能走到这里）
            continue

        # 构造本地访问 URL
        local_url = f"http://localhost:{settings.port}/images/{filename}"
        data.append({"url": local_url})

    if not data:
        raise ImageGenerationError(502, "failed to save images")

    return data


def _ratio_from_size(size: str) -> str:
    """从 size 推导 ratio。"""
    size_to_ratio: dict[str, str] = {}
    for tier_sizes in SIZE_TABLE.values():
        for ratio, s in tier_sizes.items():
            size_to_ratio[s] = ratio
    return size_to_ratio.get(size.strip(), "1:1")
