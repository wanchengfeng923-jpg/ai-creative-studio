import unittest

from creative_studio.carousel_visual import CarouselPromptInput, CarouselVisualGeneration


class CarouselVisualGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = CarouselVisualGeneration(
            "carousel-model",
            "类型={{task_type}} 任务={{task_description}} 标签={{creative_tags}} 画幅={{aspect_ratio}} "
            "证据={{product_evidence_summary}} 参考={{reference_file_names}} 轮播={{carousel_context}}",
        )
        self.prompt_input = CarouselPromptInput(
            tags={"visual_motif": ["时间冻结"]},
            task_type="展示广告",
            task_description="突出产品价值",
            aspect_ratio="9:16",
            product_evidence_summary="可确认的产品事实",
            reference_file_names=("brief.txt",),
            carousel_config={"count_mode": "fixed", "count": 3},
            tag_catalog={},
        )

    def test_build_request_uses_shared_planner_contract_and_cursor(self) -> None:
        request = self.module.build_request(
            self.prompt_input,
            conversation_id="conversation",
            parent_message_id="message",
        )

        self.assertEqual(request.model, "carousel-model")
        self.assertEqual(request.response_format, {"type": "json_object"})
        self.assertEqual(request.max_tokens, 5000)
        self.assertEqual(request.conversation_id, "conversation")
        self.assertEqual(request.parent_message_id, "message")
        self.assertIn("突出产品价值", request.messages[0]["content"])

    def test_follow_up_prompt_carries_prior_actual_content_and_next_route(self) -> None:
        prompt = self.module.follow_up_image_prompt(
            {
                "title": "方案",
                "aspect_ratio": "16:9",
                "frame_plan": [{"index": 2, "description": "产品证据被看见"}],
                "visual_continuity_rules": ["主体一致"],
            },
            [
                {
                    "frame_index": 1,
                    "actual_content": "首帧实际画面",
                    "image_status": "success",
                },
                {"frame_index": 2, "actual_content": "", "image_status": "pending"},
            ],
            2,
        )

        self.assertIn("首帧实际画面", prompt)
        self.assertIn("产品证据被看见", prompt)
        self.assertIn("直接生成一张图片", prompt)


if __name__ == "__main__":
    unittest.main()
