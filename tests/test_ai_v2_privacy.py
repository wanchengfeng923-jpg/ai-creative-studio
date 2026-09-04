from __future__ import annotations

import json
import unittest

from creative_studio.ai_v2.projection import public_run


class AiV2PrivacyTests(unittest.TestCase):
    def test_public_projection_scrubs_private_execution_and_provider_fields(self) -> None:
        payload = public_run({
            "run_id": 1, "project_id": 2, "use_case": "static", "batch_index": 1, "status": "success",
            "canonical": {"schema_version": "static-text-v1", "items": [{"title": "x", "core_idea": "c", "ad_copy": "a", "image_description": "d", "execution": {"image_prompt": "SECRET"}}]},
            "schemes": [{"scheme_id": 7, "use_case": "static", "canonical": {"title": "x", "execution": {"image_prompt": "SECRET"}}, "image_state": {"status": "success", "attempt_id": 1, "image_url": "/api/v2/image-attempts/1/image"}}],
            "conversation_id": "PRIVATE", "gateway_job_id": "PRIVATE", "local_path": "PRIVATE", "raw_response": "PRIVATE",
        })
        encoded = json.dumps(payload, ensure_ascii=False)
        for secret in ("SECRET", "PRIVATE", "execution", "conversation_id", "gateway_job_id", "local_path", "raw_response"):
            self.assertNotIn(secret, encoded)


if __name__ == "__main__":
    unittest.main()

