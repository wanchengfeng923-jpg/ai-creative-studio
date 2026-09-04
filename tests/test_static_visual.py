import json
import unittest

from creative_studio.model_client import ModelResponse
from creative_studio.static_visual import (
    StaticVisualGeneration,
    StaticVisualOutputError,
    StaticVisualPromptInput,
    StaticVisualResult,
    validate_static_visual_result,
)


def _item(concept_id: str, mechanism: str) -> dict[str, object]:
    return {
        "concept_id": concept_id,
        "title": f"方案{concept_id}",
        "creative_summary": "用一个静态对照证明产品价值。",
        "audience_tension": "想快速理解产品是否值得尝试。",
        "product_value": "帮助用户清楚看到核心玩法。",
        "visual_mechanism": mechanism,
        "creative_sources": ["产品资料中的观看结构"],
        "evidence_ledger": {
            "confirmed": ["产品资料确认的游戏名称"],
            "inferred": ["画面表现使用清晰的对照关系"],
            "to_confirm": ["制作前确认最终 Logo 素材"],
        },
        "static_frame": {
            "visual_event": "主体和对照物形成一眼可见的差异。",
            "hero_subject": "游戏界面与武侠角色关系。",
            "composition": "主体在左侧，对照物在右侧，顶部留出文案区。",
            "attention_order": ["主体", "产品证据", "文案"],
            "medium_and_art_direction": "平面广告构图，清晰材质和高对比字体。",
            "copy": {
                "headline": "一眼看懂玩法",
                "supporting_line": "",
                "brand_line": "剑侠传奇",
                "cta": None,
            },
            "product_proof": ["可见的产品界面证据"],
            "legibility_notes": "缩小后保留主体轮廓和主文案对比。",
        },
        "asset_plan": [
            {"asset": "游戏截图", "status": "existing", "fallback": "素材缺失时预留截图区域。"}
        ],
        "production_risks": [
            {"risk": "截图文字缩小后不可读", "mitigation": "制作时保留清晰局部并做缩略图检查。"}
        ],
        "review": {
            "stop_reason": "对照关系让用户第一眼看懂价值。",
            "why_make_next": "产品证据明确且可快速制作。",
            "first_validation": "先检查缩小后主体和文案是否仍清楚。",
        },
        "image_generation_instruction": "16:9 静态平面广告，左侧游戏主体，右侧留白文案区，清晰材质和高对比，禁止动态镜头。",
    }


def valid_payload() -> dict[str, object]:
    return {
        "items": [
            _item("A", "主体与缺失位置形成替换关系"),
            _item("B", "产品证据与对照物形成并置关系"),
            _item("C", "产品元素从常见结构中暴露出来"),
        ]
    }


class StaticVisualContractTests(unittest.TestCase):
    def test_valid_result_has_exact_canonical_shape(self) -> None:
        result = validate_static_visual_result(valid_payload())

        self.assertIsInstance(result, StaticVisualResult)
        self.assertEqual([item["concept_id"] for item in result.items], ["A", "B", "C"])
        self.assertNotIn("subtitle", result.items[0])
        self.assertIn("static_frame", result.items[0])

    def test_extra_field_is_rejected_with_exact_path(self) -> None:
        payload = valid_payload()
        payload["items"][0]["subtitle"] = "旧别名"

        with self.assertRaises(StaticVisualOutputError) as context:
            validate_static_visual_result(payload)

        self.assertEqual(context.exception.field_path, "items[0]")

    def test_duplicate_visual_mechanism_is_rejected(self) -> None:
        payload = valid_payload()
        payload["items"][1]["visual_mechanism"] = payload["items"][0]["visual_mechanism"]

        with self.assertRaises(StaticVisualOutputError) as context:
            validate_static_visual_result(payload)

        self.assertEqual(context.exception.field_path, "items[1].visual_mechanism")

    def test_invalid_asset_status_and_url_text_are_rejected(self) -> None:
        payload = valid_payload()
        payload["items"][0]["asset_plan"][0]["status"] = "unknown"

        with self.assertRaises(StaticVisualOutputError) as status_error:
            validate_static_visual_result(payload)
        self.assertEqual(status_error.exception.field_path, "items[0].asset_plan[0].status")

        payload = valid_payload()
        payload["items"][0]["title"] = "查看 https://example.invalid"
        with self.assertRaises(StaticVisualOutputError) as url_error:
            validate_static_visual_result(payload)
        self.assertEqual(url_error.exception.field_path, "items[0].title")

    def test_generation_repairs_once_with_validation_path(self) -> None:
        invalid = valid_payload()
        invalid["items"][0]["visual_mechanism"] = invalid["items"][1]["visual_mechanism"]
        client = _SequenceModelClient(
            [
                ModelResponse(content=json.dumps(invalid, ensure_ascii=False)),
                ModelResponse(content=json.dumps(valid_payload(), ensure_ascii=False)),
            ]
        )
        module = StaticVisualGeneration(
            client,
            prompt_template="任务：{{task_description}}\n标签：{{creative_tags}}",
        )

        result = module.generate(
            StaticVisualPromptInput(task_description="测试静态创意"),
        )

        self.assertEqual(len(result.items), 3)
        self.assertEqual(len(client.requests), 2)
        self.assertIn("items[1].visual_mechanism", client.requests[1].messages[0]["content"])

    def test_accepts_json_object_wrapped_in_provider_explanation(self) -> None:
        wrapped = "结果如下：```json\n" + json.dumps(valid_payload(), ensure_ascii=False) + "\n```"
        client = _SequenceModelClient([ModelResponse(content=wrapped)])
        module = StaticVisualGeneration(
            client,
            prompt_template="任务：{{task_description}}\n标签：{{creative_tags}}",
        )

        result = module.generate(StaticVisualPromptInput(task_description="测试静态创意"))

        self.assertEqual([item["concept_id"] for item in result.items], ["A", "B", "C"])


class _SequenceModelClient:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.requests = []

    def generate(self, request: object) -> ModelResponse:
        self.requests.append(request)
        return self.responses.pop(0)


if __name__ == "__main__":
    unittest.main()
