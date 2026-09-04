from __future__ import annotations

import json
import unittest

from creative_studio.ai_v2.projection import public_image_state, public_run, public_scheme


PRIVATE_VALUES = {
    "execution": {
        "image_prompt": "PRIVATE_PROMPT",
        "image_prompts": [{"index": 1, "prompt": "PRIVATE_FRAME_PROMPT"}],
    },
    "conversation_id": "PRIVATE_CONVERSATION",
    "parent_message_id": "PRIVATE_PARENT",
    "gateway_job_id": "PRIVATE_JOB",
    "image_path": "C:/private/image.png",
    "raw_model_response": "PRIVATE_RESPONSE",
    "internal_error": {"stack": "PRIVATE_STACK"},
}


class AiV2ProjectionTests(unittest.TestCase):
    def test_static_public_scheme_is_built_from_allowlist_and_keeps_image_state(self) -> None:
        scheme = {
            "use_case": "static",
            "scheme_id": 11,
            "title": "静态方案",
            "core_idea": "核心",
            "ad_copy": "文案",
            "image_description": "画面",
            "image_state": {"status": "pending", "attempt_no": 1, **PRIVATE_VALUES},
            **PRIVATE_VALUES,
            "unknown": "DROP_ME",
        }
        projected = public_scheme(scheme)
        encoded = json.dumps(projected, ensure_ascii=False)
        self.assertEqual(projected["title"], "静态方案")
        self.assertEqual(projected["image_state"]["status"], "pending")
        for value in ("PRIVATE_PROMPT", "PRIVATE_CONVERSATION", "PRIVATE_JOB", "C:/private/image.png", "DROP_ME"):
            self.assertNotIn(value, encoded)
        self.assertNotIn("execution", encoded)

    def test_carousel_public_scheme_exposes_frames_but_not_execution(self) -> None:
        scheme = {
            "use_case": "carousel",
            "scheme_id": 12,
            "title": "轮播方案",
            "core_idea": "核心",
            "ad_copy": "文案",
            "frames": [
                {"index": 1, "description": "首帧", "image_state": {"status": "success", "image_url": "/api/v2/images/1", **PRIVATE_VALUES}},
                {"index": 2, "description": "第二帧", "image_state": {"status": "pending"}},
            ],
            **PRIVATE_VALUES,
        }
        projected = public_scheme(scheme)
        self.assertEqual(projected["frames"][0]["index"], 1)
        self.assertEqual(projected["frames"][0]["image_state"]["image_url"], "/api/v2/images/1")
        encoded = json.dumps(projected, ensure_ascii=False)
        self.assertNotIn("PRIVATE_", encoded)
        self.assertNotIn("execution", encoded)

    def test_narrative_public_run_only_contains_story_hooks_and_scenes(self) -> None:
        run = {
            "run_id": 7,
            "use_case": "narrative",
            "batch_index": 1,
            "status": "success",
            "canonical": {
                "schema_version": "narrative-text-v1",
                "items": [
                    {
                        "story": "故事",
                        "hooks": [{"text": "钩子", "scenes": ["一", "二", "三"], **PRIVATE_VALUES}],
                        **PRIVATE_VALUES,
                    }
                ],
                **PRIVATE_VALUES,
            },
            **PRIVATE_VALUES,
        }
        projected = public_run(run)
        self.assertEqual(projected["items"][0], {"story": "故事", "hooks": [{"text": "钩子", "scenes": ["一", "二", "三"]}]})
        encoded = json.dumps(projected, ensure_ascii=False)
        self.assertNotIn("PRIVATE_", encoded)
        self.assertNotIn("execution", encoded)

    def test_public_image_state_exposes_only_safe_status_attempt_error_and_url(self) -> None:
        projected = public_image_state({
            "attempt_id": 9,
            "attempt_no": 2,
            "status": "failed",
            "error_code": "image_generation_failed",
            "retryable": True,
            "image_url": "/api/v2/images/9",
            **PRIVATE_VALUES,
        })
        self.assertEqual(projected, {
            "attempt_id": 9,
            "attempt_no": 2,
            "status": "failed",
            "error_code": "image_generation_failed",
            "retryable": True,
            "image_url": "/api/v2/images/9",
        })
        with self.assertRaises(ValueError):
            public_image_state({"status": "provider_cursor"})


if __name__ == "__main__":
    unittest.main()
