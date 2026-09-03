import base64
import unittest
from unittest.mock import patch

from creative_studio.image_jobs import GptWebImageClient


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"job_id": "job-1", "status": "queued"}


class DisplayFrameRecoveryTests(unittest.TestCase):
    def test_reference_image_uses_magic_byte_mime_without_local_path(self) -> None:
        cases = (
            ("jpeg", b"\xff\xd8\xff\xe0jpeg", "image/jpeg"),
            ("png", b"\x89PNG\r\n\x1a\npng", "image/png"),
            ("webp", b"RIFF\x08\x00\x00\x00WEBPwebp", "image/webp"),
        )
        for name, image_bytes, mime in cases:
            with self.subTest(name=name):
                client = GptWebImageClient("http://gateway")
                with patch("creative_studio.image_jobs.requests.post", return_value=_Response()) as post:
                    client.submit("画面", "16:9", f"frame-{name}", reference_image=image_bytes)
                payload = post.call_args.kwargs["json"]
                self.assertEqual(
                    payload["ref_assets"],
                    [f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii")],
                )
                self.assertNotIn("previous_image_path", payload)


if __name__ == "__main__":
    unittest.main()
