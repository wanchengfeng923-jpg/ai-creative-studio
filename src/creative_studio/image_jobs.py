"""展示类参考图的持久化异步任务。"""

from __future__ import annotations

import base64
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

import requests

from .repository import StudioRepository
from .static_visual import StaticVisualImageRequest


@dataclass(frozen=True)
class GatewayJob:
    job_id: str
    status: str
    image_url: str = ""
    error: str = ""
    conversation_id: str = ""
    parent_message_id: str = ""


@dataclass(frozen=True)
class ImageArtifact:
    data: bytes
    mime: str
    extension: str


def image_artifact(data: bytes, declared_mime: str = "") -> ImageArtifact:
    """Validate image bytes and return their canonical MIME and extension."""

    content = bytes(data or b"")
    if content.startswith(b"\xff\xd8\xff"):
        mime, extension = "image/jpeg", ".jpg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, extension = "image/png", ".png"
    elif len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        mime, extension = "image/webp", ".webp"
    else:
        raise RuntimeError("图片字节格式不受支持")
    declared = str(declared_mime or "").split(";", 1)[0].strip().lower()
    if declared and declared != mime:
        raise RuntimeError("图片 MIME 与内容不一致")
    return ImageArtifact(data=content, mime=mime, extension=extension)


class GptWebImageClient:
    def __init__(self, base_url: str, control_token: str = "") -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.control_token = str(control_token or "").strip()
        self._submit_lock = threading.Lock()
        self._submitted_jobs: dict[str, GatewayJob] = {}
        self._submit_inflight: dict[str, threading.Event] = {}

    def _headers(self) -> dict[str, str]:
        return {"X-Control-Token": self.control_token} if self.control_token else {}

    @staticmethod
    def submission_key_for_item_attempt(item_id: int, attempt: int) -> str:
        return f"creative-studio-{int(item_id)}-attempt-{int(attempt)}"

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
            conversation_id=str(source.get("conversation_id") or "").strip(),
            parent_message_id=str(source.get("parent_message_id") or "").strip(),
        )

    def submit(
        self,
        prompt: str,
        aspect_ratio: str,
        request_id: str,
        reference_image: bytes | None = None,
        conversation_id: str = "",
        parent_message_id: str = "",
    ) -> GatewayJob:
        request_id = str(request_id or "").strip()
        with self._submit_lock:
            cached = self._submitted_jobs.get(request_id)
            if cached is not None:
                return cached
            event = self._submit_inflight.get(request_id)
            if event is None:
                event = threading.Event()
                self._submit_inflight[request_id] = event
                owner = True
            else:
                owner = False
        if not owner:
            event.wait()
            with self._submit_lock:
                cached = self._submitted_jobs.get(request_id)
                if cached is not None:
                    return cached
            raise RuntimeError("图片网关提交状态丢失")
        try:
            payload: dict[str, object] = {
                "request_id": request_id,
                # Keep the provider in image mode even when the generated
                # instruction contains explanatory or copy-like wording.
                "prompt": self._image_only_prompt(prompt),
                "n": 1,
                "size": "1K",
                "aspect_ratio": str(aspect_ratio or "16:9"),
            }
            if reference_image:
                reference = image_artifact(reference_image)
                payload["ref_assets"] = [
                    f"data:{reference.mime};base64," + base64.b64encode(reference.data).decode("ascii")
                ]
            if conversation_id:
                payload["conversation_id"] = str(conversation_id)
                payload["parent_message_id"] = str(parent_message_id or "")
            response = requests.post(
                f"{self.base_url}/images/jobs",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            job = self._parse_job(response.json())
            with self._submit_lock:
                self._submitted_jobs[request_id] = job
            return job
        finally:
            with self._submit_lock:
                inflight = self._submit_inflight.pop(request_id, None)
                if inflight is not None:
                    inflight.set()

    @staticmethod
    def _image_only_prompt(prompt: str) -> str:
        text = str(prompt or "").strip()
        prefix = "直接生成一张图片。不要回复文字、JSON、Markdown或解释，只返回图片结果。"
        return f"{prefix}\n\n{text}" if text else prefix

    def status(self, job_id: str) -> GatewayJob:
        response = requests.get(
            f"{self.base_url}/images/jobs/{job_id}",
            headers=self._headers(),
            timeout=15,
            allow_redirects=False,
        )
        response.raise_for_status()
        job = self._parse_job(response.json())
        with self._submit_lock:
            for request_id, cached in list(self._submitted_jobs.items()):
                if cached.job_id == job.job_id:
                    self._submitted_jobs[request_id] = job
        return job

    def download(self, image_url: str) -> ImageArtifact:
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
        return image_artifact(data, content_type)

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
        self._reschedule: set[int] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        self.enqueue(self.repository.recover_visual_items())

    def enqueue(self, item_ids: list[int]) -> None:
        for item_id in item_ids:
            normalized = int(item_id)
            with self._lock:
                if normalized in self._scheduled:
                    self._reschedule.add(normalized)
                    continue
                self._scheduled.add(normalized)
            self.executor.submit(self._run_and_release, normalized)

    def retry(self, item_id: int) -> None:
        self.enqueue([int(item_id)])

    def enqueue_frame(
        self,
        scheme_id: int,
        frame_index: int,
        prompt: str,
        aspect_ratio: str,
        previous_image_path: str = "",
        conversation_id: str = "",
        parent_message_id: str = "",
    ) -> None:
        self.executor.submit(
            self._run_frame,
            int(scheme_id),
            int(frame_index),
            str(prompt or ""),
            str(aspect_ratio or "16:9"),
            str(previous_image_path or ""),
            str(conversation_id or ""),
            str(parent_message_id or ""),
        )

    def _run_frame(
        self,
        scheme_id: int,
        frame_index: int,
        prompt: str,
        aspect_ratio: str,
        previous_image_path: str,
        conversation_id: str,
        parent_message_id: str,
    ) -> None:
        frame = self.repository.claim_display_frame(scheme_id, frame_index)
        if frame is None:
            return
        attempt = int(frame["image_attempt"])
        try:
            if frame_index > 1 and not (conversation_id and parent_message_id):
                raise RuntimeError("连续画面缺少首帧图片会话标识")
            reference = Path(previous_image_path).read_bytes() if previous_image_path else None
            submit_kwargs = {"reference_image": reference}
            if conversation_id and parent_message_id:
                submit_kwargs.update(conversation_id=conversation_id, parent_message_id=parent_message_id)
            job = self.client.submit(
                prompt,
                aspect_ratio,
                f"creative-studio-{scheme_id}-frame-{frame_index}-attempt-{attempt}",
                **submit_kwargs,
            )
            deadline = time.monotonic() + 600
            while job.status in {"queued", "generating"}:
                if time.monotonic() >= deadline:
                    raise RuntimeError("AI连续画面生成超过10分钟")
                time.sleep(2)
                job = self.client.status(job.job_id)
            if job.status == "failed" or not job.image_url:
                raise RuntimeError(job.error or "AI连续画面生成失败")
            artifact = self.client.download(job.image_url)
            target_dir = self.images_dir / str(scheme_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"frame-{frame_index}-attempt-{attempt}{artifact.extension}"
            target.write_bytes(artifact.data)
            if not self.repository.complete_display_frame(
                scheme_id,
                frame_index,
                attempt,
                str(target),
                artifact.mime,
            ):
                target.unlink(missing_ok=True)
            if job.conversation_id and job.parent_message_id:
                self.repository.update_scheme_session(scheme_id, job.conversation_id, job.parent_message_id)
        except Exception as exc:
            self.repository.fail_display_frame(scheme_id, frame_index, attempt, str(exc) or exc.__class__.__name__)

    def wait_for_items(self, item_ids: list[int], timeout_seconds: int = 600) -> list[dict[str, object]]:
        """等待指定首图进入终态；返回每项公开状态，不改变调度线程。"""

        deadline = time.monotonic() + max(1, int(timeout_seconds))
        normalized = [int(item_id) for item_id in item_ids]
        while time.monotonic() < deadline:
            items = [self.repository.visual_item(item_id) for item_id in normalized]
            if all(item is not None and item["image_status"] in {"success", "failed"} for item in items):
                return [
                    {
                        "id": int(item["id"]),
                        "image_status": str(item["image_status"]),
                        "image_error": str(item.get("image_error") or ""),
                    }
                    for item in items
                    if item is not None
                ]
            time.sleep(0.1)
        raise RuntimeError("AI参考图生成等待超时")

    def stop(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _run_and_release(self, item_id: int) -> None:
        try:
            self._run(item_id)
        finally:
            with self._lock:
                self._scheduled.discard(item_id)
                should_reschedule = item_id in self._reschedule
                self._reschedule.discard(item_id)
                if should_reschedule:
                    self._scheduled.add(item_id)
            if should_reschedule:
                self.executor.submit(self._run_and_release, item_id)

    def enqueue_static(self, requests: list[StaticVisualImageRequest]) -> None:
        """接收静态首图 typed request，并复用现有 SQLite worker。"""

        self.enqueue([int(request.scheme_id) for request in requests])

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
                conversation_id = str(item.get("conversation_id") or "")
                parent_message_id = str(item.get("parent_message_id") or "")
                submit_kwargs = {}
                if conversation_id and parent_message_id:
                    submit_kwargs.update(conversation_id=conversation_id, parent_message_id=parent_message_id)
                job = self.client.submit(
                    str(item["image_prompt"]),
                    str(item["aspect_ratio"]),
                    self.client.submission_key_for_item_attempt(item_id, attempt),
                    **submit_kwargs,
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
            artifact = self.client.download(job.image_url)
            target_dir = self.images_dir / str(item["generation_id"]) / str(item_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"attempt-{attempt}{artifact.extension}"
            target.write_bytes(artifact.data)
            if not self.repository.complete_visual_item(
                item_id,
                attempt,
                str(target),
                artifact.mime,
            ):
                target.unlink(missing_ok=True)
            if job.conversation_id and job.parent_message_id:
                self.repository.update_scheme_session(item_id, job.conversation_id, job.parent_message_id)
        except Exception as exc:
            self.repository.fail_visual_item(item_id, attempt, str(exc) or exc.__class__.__name__)
            if attempt == 1 and self.repository.retry_visual_item(item_id):
                self.enqueue([item_id])


def gateway_base_from_environment(environment: Mapping[str, str] | None = None) -> str:
    source = environment if environment is not None else os.environ
    api_url = str(source.get("WEB_ERP_AI_API_URL") or "http://127.0.0.1:8780/v1/chat/completions").rstrip("/")
    suffix = "/chat/completions"
    return api_url[: -len(suffix)] if api_url.lower().endswith(suffix) else api_url
