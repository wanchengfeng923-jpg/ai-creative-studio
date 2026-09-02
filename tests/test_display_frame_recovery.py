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
    def test_reference_image_is_sent_as_data_without_local_path(self) -> None:
        client = GptWebImageClient("http://gateway")
        with patch("creative_studio.image_jobs.requests.post", return_value=_Response()) as post:
            client.submit("画面", "16:9", "frame-key", reference_image=b"image")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["ref_assets"], ["data:image/png;base64," + base64.b64encode(b"image").decode("ascii")])
        self.assertNotIn("image", str(payload.get("previous_image_path", "")))


if __name__ == "__main__":
    unittest.main()
