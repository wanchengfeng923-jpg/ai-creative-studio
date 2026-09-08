import threading
import time
import unittest

from creative_studio.ai_v2.queue import GenerationQueue


class GenerationQueueTests(unittest.TestCase):
    def test_seventh_job_reports_position_until_slot_is_released(self) -> None:
        queue = GenerationQueue(max_running=6)
        started = threading.Event()
        release = threading.Event()
        futures = []

        def work():
            started.set()
            release.wait(2)
            return {"ok": True}

        for _ in range(6):
            futures.append(queue.submit(work))
        self.assertTrue(started.wait(1))
        queued = queue.submit(lambda: {"queued": True})
        self.assertEqual(queued.status(), "queued")
        self.assertEqual(queued.position(), 1)

        release.set()
        self.assertEqual(queued.result(timeout=2), {"queued": True})
        self.assertEqual(queued.status(), "success")
        queue.shutdown()

    def test_failed_job_also_releases_slot(self) -> None:
        queue = GenerationQueue(max_running=1)
        release = threading.Event()

        def fail():
            release.wait(1)
            raise RuntimeError("boom")

        first = queue.submit(fail)
        second = queue.submit(lambda: "done")
        release.set()
        with self.assertRaises(RuntimeError):
            first.result(timeout=2)
        self.assertEqual(second.result(timeout=2), "done")
        queue.shutdown()

    def test_summary_reports_running_and_waiting_jobs(self) -> None:
        queue = GenerationQueue(max_running=1)
        release = threading.Event()
        first = queue.submit(lambda: release.wait(2))
        second = queue.submit(lambda: "done")
        self.assertEqual(queue.summary(), {"running": 1, "waiting": 1, "capacity": 1})
        release.set()
        first.result(timeout=2)
        second.result(timeout=2)
        self.assertEqual(queue.summary(), {"running": 0, "waiting": 0, "capacity": 1})
        queue.shutdown()


if __name__ == "__main__":
    unittest.main()
