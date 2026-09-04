import json
import unittest

from creative_studio.model_client import ModelResponse
from creative_studio.model_ports import DeterministicTextModel
from creative_studio.narrative import (
    NarrativeGeneration,
    NarrativeInput,
    NarrativeOutputError,
)


def _payload(prefix: str = "故事") -> dict[str, object]:
    return {
        "items": [
            {
                "concept_id": chr(65 + index),
                "story": f"{prefix}{index}",
                "audience_tension": f"欲望{index}",
                "product_value": f"价值{index}",
                "hooks": [
                    {"text": f"钩子{index}A", "scenes": ["场景一", "场景二", "场景三"]},
                    {"text": f"钩子{index}B", "scenes": ["镜头一", "镜头二", "镜头三"]},
                ],
                "evidence": {"confirmed": ["事实"], "inferred": [], "to_confirm": []},
                "risks": ["风险"],
            }
            for index in range(5)
        ]
    }


class NarrativeGenerationTests(unittest.TestCase):
    def test_production_module_returns_canonical_result_and_public_dto(self):
        model = DeterministicTextModel([ModelResponse(json.dumps(_payload(), ensure_ascii=False))])
        module = NarrativeGeneration(model)
        result = module.generate(
            NarrativeInput(
                task_type="短视频",
                task_description="讲清楚玩法",
                creative_tags={"target_audiences": ("新玩家",)},
                game_info="游戏资料 v2",
                reference_file_names=("brief.pdf",),
            )
        )
        self.assertEqual(result.items[0]["concept_id"], "A")
        self.assertEqual(result.items[0]["evidence"]["confirmed"], ["事实"])
        public = module.public_items(result)
        self.assertEqual(set(public[0]), {"story", "hooks"})
        request_text = model.requests[0].messages[0]["content"]
        self.assertIn("游戏资料 v2", request_text)
        self.assertIn("brief.pdf", request_text)

    def test_format_repair_carries_validation_error_path(self):
        invalid = _payload()
        invalid["items"][0]["story"] = ""
        model = DeterministicTextModel([
            ModelResponse(json.dumps(invalid, ensure_ascii=False)),
            ModelResponse(json.dumps(_payload("修复"), ensure_ascii=False)),
        ])
        module = NarrativeGeneration(model)
        result = module.generate(NarrativeInput(task_type="", task_description="任务"))
        self.assertEqual(result.items[0]["story"], "修复0")
        repair_text = model.requests[1].messages[0]["content"]
        self.assertIn("items[0].story", repair_text)
        self.assertIn("修复", repair_text)

    def test_second_batch_prompt_contains_previous_summary_and_deduplication(self):
        model = DeterministicTextModel([ModelResponse(json.dumps(_payload()))])
        module = NarrativeGeneration(model)
        module.generate(
            NarrativeInput(
                task_description="任务",
                batch_index=1,
                previous_items=("旧故事A", "旧故事B"),
            )
        )
        prompt = model.requests[0].messages[0]["content"]
        self.assertIn("旧故事A", prompt)
        self.assertIn("不得重复", prompt)

    def test_invalid_output_exposes_stable_error_details(self):
        model = DeterministicTextModel([ModelResponse('{"items": []}'), ModelResponse('{"items": []}')])
        module = NarrativeGeneration(model)
        with self.assertRaises(NarrativeOutputError) as raised:
            module.generate(NarrativeInput(task_description="任务"))
        self.assertEqual(raised.exception.error_code, "model_output_invalid")
        self.assertEqual(raised.exception.field_path, "items")
        self.assertFalse(raised.exception.retryable)

    def test_accepts_json_object_wrapped_in_provider_explanation(self):
        wrapped = "下面是结果：```json\n" + json.dumps(_payload("容错"), ensure_ascii=False) + "\n```"
        model = DeterministicTextModel([ModelResponse(wrapped)])
        module = NarrativeGeneration(model)

        result = module.generate(NarrativeInput(task_description="任务"))

        self.assertEqual(result.items[0]["story"], "容错0")

    def test_ignores_non_contract_metadata_on_hook_objects(self):
        payload = _payload("扩展字段")
        payload["items"][0]["hooks"][0]["rationale"] = "模型附加的解释"
        model = DeterministicTextModel([ModelResponse(json.dumps(payload, ensure_ascii=False))])

        result = NarrativeGeneration(model).generate(NarrativeInput(task_description="任务"))

        self.assertEqual(set(result.items[0]["hooks"][0]), {"text", "scenes"})


if __name__ == "__main__":
    unittest.main()
