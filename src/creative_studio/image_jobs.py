"""展示类参考图的持久化异步任务。"""

from __future__ import annotations

import mimetypes
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from .repository import StudioRepository


@dataclass(frozen=True)
class GatewayJob:
    job_id: str
    status: str
    image_url: str = ""
    error: str = ""


class GptWebImageClient:
    def __init__(self, base_url: str, control_token: str = "") -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.control_token = str(control_token or "").strip()

    def _headers(self) -> dict[str, str]:
        return {"X-Control-Token": self.control_token} if self.control_token else {}

    @staticmethod
    def _parse_job(payload: object) -> GatewayJob:
        source = payload if isinstance(payload, dict) else {}
        job_id = str(source.get("job_id") or "").strip()
        status = str(source.get("status") or "").strip().lower()
        if not job_id or status not in {"queued", "generating", "success", "failed"}:
            raise RuntimeError("图片网关返回了无效任务状态")
        return GatewayJob(
            job_id=job_id,
            status=status,
            image_url=str(source.get("image_url") or "").strip(),
            error=str(source.get("error") or "").strip(),
        )

    def submit(self, prompt: str, aspect_ratio: str, request_id: str) -> GatewayJob:
        response = requests.post(
            f"{self.base_url}/images/jobs",
            json={
                "request_id": request_id,
                "prompt": str(prompt or ""),
                "n": 1,
                "size": "1K",
                "aspect_ratio": str(aspect_ratio or "16:9"),
            },
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return self._parse_job(response.json())

    def status(self, job_id: str) -> GatewayJob:
        response = requests.get(
            f"{self.base_url}/images/jobs/{job_id}",
            headers=self._headers(),
            timeout=15,
            allow_redirects=False,
        )
        response.raise_for_status()
        return self._parse_job(response.json())

    def download(self, image_url: str) -> tuple[bytes, str]:
        parsed = urlsplit(str(image_url or ""))
        gateway = urlsplit(self.base_url)
        if not parsed.scheme and not parsed.netloc:
            parsed = urlsplit(urlunsplit((gateway.scheme, gateway.netloc, parsed.path, parsed.query, "")))
        elif (parsed.hostname or "").casefold() in {"localhost", "127.0.0.1"}:
            parsed = urlsplit(urlunsplit((gateway.scheme, gateway.netloc, parsed.path, parsed.query, "")))
        if self._origin(parsed) != self._origin(gateway):
            raise RuntimeError("图片网关返回了跨来源地址")
        response = requests.get(
            urlunsplit(parsed),
            headers=self._headers(),
            timeout=30,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise RuntimeError("图片下载不允许重定向")
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        data = bytes(response.content or b"")
        if not content_type.startswith("image/") or not data:
            raise RuntimeError("图片网关没有返回有效图片")
        extension = ".jpg" if content_type == "image/jpeg" else (mimetypes.guess_extension(content_type) or "")
        if not extension:
            raise RuntimeError("图片格式不受支持")
        return data, extension

    @staticmethod
    def _origin(parsed) -> tuple[str, str, int]:
        scheme = str(parsed.scheme or "").casefold()
        host = str(parsed.hostname or "").casefold()
        if scheme not in {"http", "https"} or not host:
            raise RuntimeError("图片地址无效")
        return scheme, host, int(parsed.port or (443 if scheme == "https" else 80))


class ImageJobRunner:
    def __init__(self, repository: StudioRepository, images_dir: Path, client: GptWebImageClient) -> None:
        self.repository = repository
        self.images_dir = Path(images_dir).resolve()
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="creative-image")
        self._scheduled: set[int] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        self.enqueue(self.repository.recover_visual_items())

    def enqueue(self, item_ids: list[int]) -> None:
        for item_id in item_ids:
            normalized = int(item_id)
            with self._lock:
                if normalized in self._scheduled:
                    continue
                self._scheduled.add(normalized)
            self.executor.submit(self._run_and_release, normalized)

    def retry(self, item_id: int) -> None:
        self.enqueue([int(item_id)])

    def stop(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _run_and_release(self, item_id: int) -> None:
        try:
            self._run(item_id)
        finally:
            with self._lock:
                self._scheduled.discard(item_id)

    def _run(self, item_id: int) -> None:
        item = self.repository.claim_visual_item(item_id)
        if item is None:
            return
        attempt = int(item["image_attempt"])
        try:
            gateway_job_id = str(item.get("gateway_job_id") or "").strip()
            if gateway_job_id:
                job = self.client.status(gateway_job_id)
            else:
                job = self.client.submit(
                    str(item["image_prompt"]),
                    str(item["aspect_ratio"]),
                    f"creative-studio-{item_id}-attempt-{attempt}",
                )
                gateway_job_id = job.job_id
                if not self.repository.set_gateway_job(item_id, attempt, gateway_job_id):
                    return
            deadline = time.monotonic() + 600
            while job.status in {"queued", "generating"}:
                if time.monotonic() >= deadline:
                    raise RuntimeError("AI参考图生成超过10分钟")
                time.sleep(2)
                job = self.client.status(gateway_job_id)
            if job.status == "failed":
                raise RuntimeError(job.error or "AI参考图生成失败")
            if not job.image_url:
                raise RuntimeError("图片任务完成但没有图片地址")
            data, extension = self.client.download(job.image_url)
            target_dir = self.images_dir / str(item["generation_id"]) / str(item_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"attempt-{attempt}{extension}"
            target.write_bytes(data)
            if not self.repository.complete_visual_item(item_id, attempt, str(target)):
                target.unlink(missing_ok=True)
        except Exception as exc:
            self.repository.fail_visual_item(item_id, attempt, str(exc) or exc.__class__.__name__)


def gateway_base_from_environment() -> str:
    api_url = str(os.environ.get("WEB_ERP_AI_API_URL") or "http://127.0.0.1:8780/v1/chat/completions").rstrip("/")
    suffix = "/chat/completions"
    return api_url[: -len(suffix)] if api_url.lower().endswith(suffix) else api_url
