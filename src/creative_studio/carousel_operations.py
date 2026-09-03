"""轮播后续画面的后台 Operation 协调器。"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping

from .generation_models import GenerationConflictError, GenerationNotFoundError
from .repository import StudioRepository


class CarouselOperationCoordinator:
    """按方案顺序运行轮播后续帧，并维护 operation lease。"""

    def __init__(
        self,
        repository: StudioRepository,
        image_runner: Any,
        *,
        prompt_builder: Callable[[Mapping[str, Any], list[Mapping[str, Any]], int], str],
        lease_seconds: int = 60,
        wait_timeout_seconds: int = 600,
    ) -> None:
        self.repository = repository
        self.image_runner = image_runner
        self.prompt_builder = prompt_builder
        self.lease_seconds = max(5, int(lease_seconds))
        self.wait_timeout_seconds = max(1, int(wait_timeout_seconds))
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="creative-carousel")
        self._stopped = threading.Event()

    def start(self, scheme_id: int, request_key: str | None = None) -> dict[str, Any]:
        """创建或复用 operation，并立即把它提交给后台 worker。"""

        operation = self.repository.get_or_create_carousel_operation(
            int(scheme_id), str(request_key or uuid.uuid4().hex), self.lease_seconds
        )
        if operation.get("_created") and str(operation.get("status")) == "queued":
            self.executor.submit(self.run, int(operation["id"]))
        return operation

    def run(self, operation_id: int) -> None:
        """运行单个 operation；所有状态写入均受 lease token 保护。"""

        operation = self.repository.get_carousel_operation(int(operation_id))
        if operation is None or str(operation.get("status")) not in {"queued", "running"}:
            return
        token = str(operation.get("lease_token") or "")
        if not self.repository.start_carousel_operation(operation_id, token, self.lease_seconds):
            return
        try:
            while not self._stopped.is_set():
                operation = self.repository.get_carousel_operation(operation_id)
                if operation is None or str(operation.get("lease_token")) != token:
                    return
                if str(operation.get("status")) == "completed":
                    return
                scheme = self.repository.get_display_scheme(int(operation["scheme_id"]))
                if scheme is None:
                    raise GenerationNotFoundError("展示方案不存在")
                frame_index = int(operation.get("current_frame_index") or 0)
                frames = [dict(frame) for frame in scheme.get("frames", [])]
                if frame_index <= 1:
                    raise GenerationConflictError("首图未成功，请先重试首图")
                current = next((frame for frame in frames if int(frame.get("frame_index") or 0) == frame_index), None)
                if current is None:
                    self.repository.finish_carousel_operation(operation_id, token, "completed")
                    return
                for attempt_number in range(2):
                    if not self.repository.heartbeat_carousel_operation(operation_id, token, self.lease_seconds):
                        return
                    prompt = self.prompt_builder(scheme, frames, frame_index)
                    previous = next((frame for frame in frames if int(frame.get("frame_index") or 0) == frame_index - 1), None)
                    enqueue_frame = getattr(self.image_runner, "enqueue_frame", None)
                    if not callable(enqueue_frame):
                        raise GenerationConflictError("图片网关暂不支持连续画面参考图")
                    enqueue_frame(
                        int(operation["scheme_id"]),
                        frame_index,
                        prompt,
                        str(scheme.get("aspect_ratio") or "16:9"),
                        str((previous or {}).get("image_path") or ""),
                        str(scheme.get("conversation_id") or ""),
                        str(scheme.get("parent_message_id") or ""),
                        operation_id,
                        token,
                    )
                    if self._wait_for_frame(operation_id, token, frame_index):
                        break
                    if attempt_number == 1:
                        failed_scheme = self.repository.get_display_scheme(int(operation["scheme_id"])) or {}
                        failed_frame = next(
                            (item for item in failed_scheme.get("frames", []) if int(item.get("frame_index") or 0) == frame_index),
                            {},
                        )
                        error_code = (
                            "provider_protocol_invalid"
                            if "provider_protocol_invalid" in str(failed_frame.get("image_error") or "")
                            else "image_generation_failed"
                        )
                        self.repository.finish_carousel_operation(
                            operation_id,
                            token,
                            "blocked",
                            error_code,
                            "连续画面图片生成失败",
                        )
                        return
                else:
                    return
        except Exception as exc:
            self.repository.finish_carousel_operation(
                operation_id,
                token,
                "failed",
                "carousel_operation_failed",
                str(exc),
            )

    def _wait_for_frame(self, operation_id: int, token: str, frame_index: int) -> bool:
        deadline = time.monotonic() + self.wait_timeout_seconds
        while time.monotonic() < deadline and not self._stopped.is_set():
            operation = self.repository.get_carousel_operation(operation_id)
            if operation is None or str(operation.get("lease_token")) != token:
                return False
            self.repository.heartbeat_carousel_operation(operation_id, token, self.lease_seconds)
            scheme = self.repository.get_display_scheme(int(operation["scheme_id"]))
            frame = next(
                (item for item in (scheme or {}).get("frames", []) if int(item.get("frame_index") or 0) == frame_index),
                None,
            )
            if frame is not None and str(frame.get("image_status")) in {"success", "failed"}:
                return str(frame.get("image_status")) == "success"
            time.sleep(0.1)
        return False

    def recover(self) -> list[int]:
        """回收失活 operation 并重新提交 queued worker。"""

        operation_ids = self.repository.recover_stale_carousel_operations(self.lease_seconds)
        for operation_id in operation_ids:
            self.executor.submit(self.run, operation_id)
        return operation_ids

    def stop(self) -> None:
        self._stopped.set()
        self.executor.shutdown(wait=True, cancel_futures=True)


__all__ = ["CarouselOperationCoordinator"]
