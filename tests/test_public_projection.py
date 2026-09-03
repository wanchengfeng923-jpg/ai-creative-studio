from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import unittest
from typing import Any

from creative_studio.public_projection import PublicResultMapper


PRIVATE_FIELDS = {
    "image_prompt",
    "image_generation_instruction",
    "conversation_id",
    "parent_message_id",
    "assistant_message_id",
    "image_path",
    "stored_name",
    "gateway_job_id",
    "raw_response",
    "private_context",
    "stack_trace",
    "error_detail",
}


def private_fields_in(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PRIVATE_FIELDS:
                found.add(key)
            found.update(private_fields_in(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(private_fields_in(child))
    return found


def private_visual() -> dict[str, Any]:
    return {
        "id": 9,
        "item_index": 1,
        "title": "方案",
        "subtitle": "副标题",
        "creative_description": "描述",
        "core_subject": "主体",
        "layout": "布局",
        "visual_style": "风格",
        "content_extensions": ["扩展"],
        "reference_sources": [
            {
                "name": "来源",
                "note": "说明",
                "private_context": {"conversation_id": "nested"},
            }
        ],
        "keywords": ["关键词"],
        "image_prompt": "秘密图片提示词",
        "image_generation_instruction": "秘密图片指令",
        "conversation_id": "conversation",
        "parent_message_id": "message",
        "image_path": "D:/private/image.png",
        "gateway_job_id": "job-private",
        "first_frame": {
            "index": 1,
            "content": "首帧",
            "image_generation_instruction": "nested-secret",
            "private_context": {"raw_response": "model body"},
        },
        "carousel": {
            "count": 2,
            "form": ["左右滑动"],
            "frames": [
                {
                    "index": 1,
                    "display_description": "第一屏",
                    "image_prompt": "nested",
                },
                {"index": 2, "display_description": "第二屏"},
            ],
        },
        "carousel_frames": [1, 2],
        "aspect_ratio": "16:9",
        "image_status": "failed",
        "image_url": "D:/private/disguised-as-url.png",
        "image_error": "token=secret D:/private/image.png",
        "frames": [
            {
                "frame_index": 1,
                "planned_content": "第一屏",
                "actual_content": "首帧",
                "image_status": "failed",
                "image_url": "D:/private/frame-disguised-as-url.png",
                "image_error": "traceback and token",
                "image_path": "D:/private/frame.png",
                "image_generation_instruction": "nested",
            }
        ],
    }


class PublicResultMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = PublicResultMapper()

    def test_history_rebuilds_visual_items_and_failures_from_allowlists(self) -> None:
        raw = {
            "batches": [
                {
                    "id": 7,
                    "batch_index": 1,
                    "input_fingerprint": "fp",
                    "items": [private_visual()],
                    "usage": {"input_tokens": 1, "secret": "drop"},
                    "created_at": "2026-09-03 10:00:00",
                    "private_context": {"raw_response": "drop"},
                }
            ],
            "stale_batches": [],
            "failed_generations": [
                {
                    "id": 8,
                    "batch_index": 2,
                    "input_fingerprint": "fp",
                    "error": "D:/private/model.txt token=secret validator detail",
                    "error_code": "model_output_invalid",
                    "error_phase": "validation",
                    "error_field_path": "items[0].first_frame.content",
                    "error_retryable": 0,
                    "error_trace_id": "trace-1",
                    "error_detail": "raw model response and token",
                    "created_at": "2026-09-03 10:01:00",
                }
            ],
            "remaining_generations": 2,
        }

        public = self.mapper.history(raw, recommendation_kind="visual")

        self.assertEqual(private_fields_in(public), set())
        self.assertEqual(public["batches"][0]["items"][0]["title"], "方案")
        self.assertEqual(
            public["batches"][0]["items"][0]["image_error"],
            "图片生成失败，请重试",
        )
        self.assertEqual(public["batches"][0]["usage"], {"input_tokens": 1})
        self.assertEqual(public["failed_generations"][0]["error_code"], "model_output_invalid")
        self.assertEqual(public["failed_generations"][0]["error"], "AI返回结果格式无效")
        self.assertNotIn("error_detail", public["failed_generations"][0])
        self.assertNotIn("secret", json.dumps(public, ensure_ascii=False))
        self.assertEqual(public["batches"][0]["items"][0]["image_url"], "")
        self.assertEqual(public["batches"][0]["items"][0]["frames"][0]["image_url"], "")

    def test_legacy_generic_failure_text_is_replaced_with_safe_summary(self) -> None:
        failure = self.mapper.failure(
            {
                "id": 8,
                "error": "token=secret D:/private/image.png Traceback",
                "error_code": "generation_failed",
                "error_detail": "raw model response",
            }
        )

        self.assertEqual(failure["error"], "生成失败，请重试")
        self.assertNotIn("secret", str(failure))
        self.assertNotIn("private", str(failure))

    def test_project_and_adoption_snapshots_use_the_same_result_mapper(self) -> None:
        raw_project = {
            "id": 1,
            "name": "项目",
            "script_type": "展示类",
            "task_type": "产品展示",
            "task_description": "说明",
            "creative_tags": {
                "visual_target_audiences": [
                    "玩家",
                    {"image_prompt": "nested tag secret"},
                ],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {
                            "visual_product_selling_points": ["卖点A"],
                            "private_context": {"raw_response": "round secret"},
                        },
                        "image_prompt": "round prompt secret",
                    }
                ],
                "image_prompt": "top-level tag secret",
                "private_context": {"conversation_id": "nested tag cursor"},
            },
            "aspect_ratio": "16:9",
            "product_evidence_summary": "证据",
            "owner_user_id": 2,
            "created_at": "created",
            "updated_at": "updated",
            "reference_files": [
                {
                    "id": 3,
                    "original_name": "brief.png",
                    "stored_name": "private-upload-name.png",
                    "size_bytes": 4,
                    "created_at": "created",
                }
            ],
            "adoption": {
                "recommendation_kind": "visual",
                "reference_id": "9",
                "snapshot": private_visual(),
                "updated_at": "updated",
            },
        }

        public = self.mapper.project(raw_project)

        self.assertEqual(private_fields_in(public), set())
        self.assertEqual(
            public["creative_tags"],
            {
                "visual_target_audiences": ["玩家"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "base",
                        "overrides": {
                            "visual_product_selling_points": ["卖点A"],
                        },
                    }
                ],
            },
        )
        self.assertEqual(public["reference_files"][0]["original_name"], "brief.png")
        self.assertEqual(public["adoption"]["snapshot"]["title"], "方案")

    def test_project_json_order_is_stable_across_hash_seeds(self) -> None:
        script = textwrap.dedent(
            """
            import json
            from creative_studio.public_projection import PublicResultMapper

            tags = {
                "visual_motif": ["母题"],
                "content_forms": ["形式"],
                "target_audiences": ["人群"],
                "visual_voice_hook": ["声音"],
                "product_evidences": ["证据"],
                "visual_display_contents": ["内容"],
                "secondary_opening_hooks": ["副钩子"],
                "visual_carousel_rounds": [
                    {
                        "index": 1,
                        "mode": "custom",
                        "overrides": {
                            "visual_motif": ["母题"],
                            "visual_display_contents": ["内容"],
                            "visual_product_selling_points": ["卖点"],
                        },
                    }
                ],
            }
            projected = PublicResultMapper().project({"creative_tags": tags})
            print(json.dumps(projected["creative_tags"], ensure_ascii=False, separators=(",", ":")))
            """
        )
        outputs = []
        for seed in ("1", "2", "3", "4"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            completed = subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            outputs.append(completed.stdout.strip())

        self.assertEqual(len(set(outputs)), 1, outputs)

    def test_project_summary_is_rebuilt_from_an_allowlist(self) -> None:
        public = self.mapper.project_summary(
            {
                "id": 1,
                "name": "项目",
                "script_type": "展示类",
                "owner_user_id": 2,
                "updated_at": "updated",
                "adopted_kind": "visual",
                "adopted_title": "方案",
                "stored_name": "private-upload.png",
                "private_context": {"conversation_id": "secret"},
            }
        )

        self.assertEqual(
            public,
            {
                "id": 1,
                "name": "项目",
                "script_type": "展示类",
                "owner_user_id": 2,
                "updated_at": "updated",
                "adopted_kind": "visual",
                "adopted_title": "方案",
            },
        )
        self.assertEqual(private_fields_in(public), set())

    def test_status_and_display_scheme_share_safe_error_projection(self) -> None:
        item_status = self.mapper.visual_status(
            {
                "id": 9,
                "image_status": "failed",
                "image_error": "D:/secret token=abc",
                "image_path": "D:/secret/image.webp",
                "gateway_job_id": "job-1",
            }
        )
        scheme = self.mapper.display_scheme(private_visual())

        self.assertEqual(private_fields_in(item_status), set())
        self.assertEqual(item_status["image_error"], "图片生成失败，请重试")
        self.assertEqual(private_fields_in(scheme), set())
        self.assertEqual(scheme["frames"][0]["image_error"], "图片生成失败，请重试")

    def test_narrative_projection_drops_unknown_nested_fields(self) -> None:
        item = {
            "story": "故事",
            "hooks": [
                {
                    "text": "钩子",
                    "scenes": ["画面1", "画面2", "画面3"],
                    "private_context": {"raw_response": "secret"},
                }
            ],
            "conversation_id": "secret",
        }

        public = self.mapper.result_item(item, recommendation_kind="narrative")

        self.assertEqual(
            public,
            {"story": "故事", "hooks": [{"text": "钩子", "scenes": ["画面1", "画面2", "画面3"]}]},
        )

    def test_narrative_projection_drops_non_string_scenes(self) -> None:
        public = self.mapper.narrative_item(
            {
                "story": "故事",
                "hooks": [
                    {
                        "text": "钩子",
                        "scenes": ["画面", 1, 1.5, True, {"private_context": "secret"}],
                    }
                ],
            }
        )

        self.assertEqual(public["hooks"][0]["scenes"], ["画面"])

    def test_text_and_usage_fields_do_not_stringify_private_containers(self) -> None:
        public = self.mapper.history(
            {
                "batches": [
                    {
                        "id": 1,
                        "items": [
                            {
                                "title": {"raw_response": "title secret"},
                                "reference_sources": [
                                    {
                                        "name": {"private_context": "source secret"},
                                        "note": "公开说明",
                                    }
                                ],
                            }
                        ],
                        "usage": {
                            "input_tokens": {"raw_response": "usage secret"},
                            "usage_source": ["private usage source"],
                        },
                    }
                ],
                "stale_batches": [],
                "failed_generations": [],
                "remaining_generations": 1,
            },
            recommendation_kind="visual",
        )

        item = public["batches"][0]["items"][0]
        self.assertEqual(item["title"], "")
        self.assertEqual(item["reference_sources"][0]["name"], "")
        self.assertEqual(public["batches"][0]["usage"], {})
        self.assertNotIn("secret", json.dumps(public, ensure_ascii=False))

    def test_public_text_lists_drop_numbers_and_booleans(self) -> None:
        raw_visual = private_visual()
        raw_visual["content_extensions"] = ["扩展", 1, 1.5, True]
        raw_visual["keywords"] = ["关键词", 2, False]
        raw_visual["creative_sources"] = ["来源", 3, True]
        raw_visual["visual_continuity_rules"] = ["连续", 4.5, False]
        raw_visual["carousel"]["form"] = ["左右滑动", 5, True]
        raw_visual["carousel_frames"] = [1, 2, "3", 4.5, True]

        visual = self.mapper.visual_item(raw_visual)
        project = self.mapper.project(
            {
                "creative_tags": {
                    "target_audiences": ["玩家", 1, 1.5, True],
                    "visual_carousel_rounds": [
                        {
                            "index": 1,
                            "mode": "custom",
                            "overrides": {
                                "visual_product_selling_points": ["卖点", 2, 2.5, False],
                            },
                        }
                    ],
                }
            }
        )

        self.assertEqual(visual["content_extensions"], ["扩展"])
        self.assertEqual(visual["keywords"], ["关键词"])
        self.assertEqual(visual["creative_sources"], ["来源"])
        self.assertEqual(visual["visual_continuity_rules"], ["连续"])
        self.assertEqual(visual["carousel"]["form"], ["左右滑动"])
        self.assertEqual(visual["carousel_frames"], [1, 2, "3"])
        self.assertEqual(project["creative_tags"]["target_audiences"], ["玩家"])
        self.assertEqual(
            project["creative_tags"]["visual_carousel_rounds"][0]["overrides"],
            {"visual_product_selling_points": ["卖点"]},
        )


if __name__ == "__main__":
    unittest.main()
