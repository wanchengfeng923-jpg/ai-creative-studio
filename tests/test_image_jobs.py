from __future__ import annotations

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import requests

from creative_studio.image_jobs import GatewayJob, GptWebImageClient, ImageJobRunner
from creative_studio.repository import StudioRepository


VISUAL_ITEM = {
    "title": "首帧方案",
    "image_prompt": "仅供服务端使用的提示词",
}


def result(items):
    return SimpleNamespace(
        items=items,
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
        usage_source="exact",
        latency_ms=4,
        conversation_id="conversation",
        assistant_message_id="message",
    )


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class DownloadResponse:
    def __init__(self, data: bytes, content_type: str) -> None:
        self.content = data
        self.headers = {"Content-Type": content_type}
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []

    def __call__(self, *args, **kwargs) -> FakeResponse:
        request_id = str(kwargs["json"]["request_id"])
        self.calls.append(request_id)
        self.prompts.append(str(kwargs["json"]["prompt"]))
        return FakeResponse(
            {
                "job_id": f"job-{len(self.calls)}",
                "status": "queued",
                "image_url": "",
                "error": "",
            }
        )


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, wait=True, cancel_futures=False):
        return None


class FakeImageClient:
    def __init__(self) -> None:
        self.submissions: list[str] = []

    def submission_key_for_item_attempt(self, item_id: int, attempt: int) -> str:
        return GptWebImageClient.submission_key_for_item_attempt(item_id, attempt)

    def submit(self, prompt: str, aspect_ratio: str, request_id: str) -> GatewayJob:
        self.submissions.append(str(request_id))
        return GatewayJob(job_id=f"job-{request_id}", status="success", image_url=f"https://gateway/{request_id}.png")

    def status(self, job_id: str) -> GatewayJob:
        return GatewayJob(job_id=str(job_id), status="success", image_url=f"https://gateway/{job_id}.png")

    def download(self, image_url: str):
        return SimpleNamespace(
            data=b"\x89PNG\r\n\x1a\npng",
            mime="image/png",
            extension=".png",
        )


class ImageJobTests(unittest.TestCase):
    def test_download_returns_bytes_mime_and_canonical_extension_from_magic_bytes(self) -> None:
        cases = (
            (b"\xff\xd8\xff\xe0jpeg", "image/jpeg", ".jpg"),
            (b"\x89PNG\r\n\x1a\npng", "image/png", ".png"),
            (b"RIFF\x08\x00\x00\x00WEBPwebp", "image/webp", ".webp"),
        )
        client = GptWebImageClient("http://gateway")
        for data, mime, extension in cases:
            with self.subTest(mime=mime), patch(
                "creative_studio.image_jobs.requests.get",
                return_value=DownloadResponse(data, mime),
            ):
                artifact = client.download("/image")
            self.assertEqual(getattr(artifact, "data", None), data)
            self.assertEqual(getattr(artifact, "mime", None), mime)
            self.assertEqual(getattr(artifact, "extension", None), extension)

    def test_download_rejects_header_and_magic_byte_mismatch(self) -> None:
        client = GptWebImageClient("http://gateway")
        response = DownloadResponse(b"\x89PNG\r\n\x1a\npng", "image/jpeg")

        with patch("creative_studio.image_jobs.requests.get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "MIME"):
                client.download("/image")

    def test_duplicate_submit_key_reuses_one_gateway_job(self) -> None:
        gateway = RecordingGateway()
        client = GptWebImageClient("http://gateway")

        with patch("creative_studio.image_jobs.requests.post", side_effect=gateway):
            first = client.submit("prompt", "16:9", GptWebImageClient.submission_key_for_item_attempt(7, 1))
            second = client.submit("prompt", "16:9", GptWebImageClient.submission_key_for_item_attempt(7, 1))

        self.assertEqual(first, second)
        self.assertEqual(gateway.calls, ["creative-studio-7-attempt-1"])
        self.assertIn("直接生成一张图片", gateway.prompts[0])
        self.assertIn("不要回复文字", gateway.prompts[0])

    def test_transient_submit_failure_does_not_poison_same_key_retry(self) -> None:
        client = GptWebImageClient("http://gateway")
        calls: list[str] = []

        def post(*args, **kwargs):
            calls.append(str(kwargs["json"]["request_id"]))
            if len(calls) == 1:
                raise requests.Timeout("timeout")
            return FakeResponse(
                {
                    "job_id": "job-success",
                    "status": "queued",
                    "image_url": "",
                    "error": "",
                }
            )

        request_id = GptWebImageClient.submission_key_for_item_attempt(7, 1)
        with patch("creative_studio.image_jobs.requests.post", side_effect=post):
            with self.assertRaises(requests.Timeout):
                client.submit("prompt", "16:9", request_id)
            job = client.submit("prompt", "16:9", request_id)

        self.assertEqual(job.job_id, "job-success")
        self.assertEqual(calls, [request_id, request_id])

    def test_recovery_requeues_only_stale_generating_items(self) -> None:
        with TemporaryDirectory() as tempdir:
            repo = StudioRepository(Path(tempdir) / "studio.db")
            project = repo.create_project("展示项目", "展示类")
            reservation = repo.reserve_generation(project["id"], "visual", "visual.v1", "fingerprint")
            item_ids = repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")
            repo.claim_visual_item(item_ids[0])
            repo.claim_visual_item(item_ids[1])
            repo.complete_visual_item(item_ids[1], 1, str(Path(tempdir) / "sibling.png"))

            runner = ImageJobRunner(repo, Path(tempdir) / "images", FakeImageClient())
            runner.executor = InlineExecutor()
            runner.start()

            first = repo.visual_item(item_ids[0])
            second = repo.visual_item(item_ids[1])
            third = repo.visual_item(item_ids[2])

            self.assertEqual(first["image_status"], "success")
            self.assertEqual(first["image_mime"], "image/png")
            self.assertEqual(Path(first["image_path"]).suffix, ".png")
            with closing(repo._connect()) as connection:
                frame_mime = connection.execute(
                    "SELECT image_mime FROM display_frames WHERE scheme_id=? AND frame_index=1",
                    (item_ids[0],),
                ).fetchone()[0]
            self.assertEqual(frame_mime, "image/png")
            self.assertEqual(first["image_attempt"], 2)
            self.assertEqual(second["image_status"], "success")
            self.assertEqual(second["image_attempt"], 1)
            self.assertEqual(third["image_status"], "success")
            self.assertEqual(
                runner.client.submissions,
                [
                    GptWebImageClient.submission_key_for_item_attempt(item_ids[0], 2),
                    GptWebImageClient.submission_key_for_item_attempt(item_ids[2], 1),
                ],
            )

    def test_retry_advances_only_the_retried_item_attempt(self) -> None:
        with TemporaryDirectory() as tempdir:
            repo = StudioRepository(Path(tempdir) / "studio.db")
            project = repo.create_project("展示项目", "展示类")
            reservation = repo.reserve_generation(project["id"], "visual", "visual.v1", "fingerprint")
            item_ids = repo.complete_visual_generation(reservation["id"], result([VISUAL_ITEM] * 3), "16:9")

            first_claim = repo.claim_visual_item(item_ids[0])
            self.assertEqual(first_claim["image_attempt"], 1)
            self.assertTrue(repo.fail_visual_item(item_ids[0], 1, "boom"))
            self.assertTrue(repo.retry_visual_item(item_ids[0]))
            second_claim = repo.claim_visual_item(item_ids[0])
            self.assertEqual(second_claim["image_attempt"], 2)
            self.assertFalse(repo.complete_visual_item(item_ids[0], 1, str(Path(tempdir) / "stale.png")))
            self.assertEqual(repo.visual_item(item_ids[0])["image_status"], "generating")
            self.assertTrue(repo.complete_visual_item(item_ids[0], 2, str(Path(tempdir) / "fresh.png")))

            sibling = repo.visual_item(item_ids[1])
            self.assertEqual(sibling["image_status"], "queued")
            self.assertEqual(sibling["image_attempt"], 0)


if __name__ == "__main__":
    unittest.main()
