"""AI task concurrency limiter shared by chat and image routes."""

import asyncio

from config import settings


class AiTaskQueueTimeoutError(TimeoutError):
    """Raised when a task waits too long for an available AI slot."""


class AiTaskLimiter:
    def __init__(self, max_concurrent: int, queue_timeout_seconds: float):
        self.max_concurrent = max(1, int(max_concurrent))
        self.queue_timeout_seconds = max(0.01, float(queue_timeout_seconds))
        self._semaphore = asyncio.BoundedSemaphore(self.max_concurrent)
        self._active = 0
        self._waiting = 0

    async def acquire(self) -> None:
        self._waiting += 1
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.queue_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise AiTaskQueueTimeoutError("AI任务排队超时，请稍后重试") from exc
        finally:
            self._waiting -= 1
        self._active += 1

    def release(self) -> None:
        self._semaphore.release()
        self._active -= 1

    def snapshot(self) -> dict[str, int]:
        active = max(0, self._active)
        return {
            "max_concurrent": self.max_concurrent,
            "active": active,
            "waiting": max(0, self._waiting),
            "available": max(0, self.max_concurrent - active),
        }


ai_task_limiter = AiTaskLimiter(
    max_concurrent=settings.max_concurrent_tasks,
    queue_timeout_seconds=settings.task_queue_timeout,
)
