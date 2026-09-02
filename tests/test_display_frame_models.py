import unittest

from creative_studio.display_frame_models import DisplayScheme, next_frame_index, validate_frame_count
from creative_studio.ai_creative import validate_visual_creative_recommendations
from creative_studio.generation_models import GenerationInputError


def _payload(frame_count: int) -> dict[str, object]:
    return {
        "title": "方案",
        "frame_count": frame_count,
        "frame_plan": [
            {"index": index, "description": f"画面{index}"}
            for index in range(1, frame_count + 1)
        ],
    }


class DisplayFrameModelTests(unittest.TestCase):
    def test_ai_count_is_independent_per_scheme_and_locked(self) -> None:
        schemes = [DisplayScheme.from_payload(_payload(count)) for count in (2, 5)]
        self.assertEqual([scheme.frame_count for scheme in schemes], [2, 5])
        self.assertNotEqual(schemes[0].frame_count, schemes[1].frame_count)

    def test_count_modes_and_next_frame(self) -> None:
        self.assertEqual(validate_frame_count("none", None, 1), 1)
        self.assertEqual(validate_frame_count("fixed", 3, 3), 3)
        self.assertEqual(validate_frame_count("ai", None, 5), 5)
        scheme = DisplayScheme.from_payload(_payload(3))
        completed = tuple(frame.__class__(**{**frame.__dict__, "image_status": "success"}) for frame in scheme.frames[:2]) + scheme.frames[2:]
        self.assertEqual(next_frame_index(completed), 3)

    def test_invalid_count_is_rejected(self) -> None:
        with self.assertRaises(GenerationInputError):
            validate_frame_count("fixed", 2, 3)

    def test_new_first_frame_output_shape_is_accepted(self) -> None:
        payload = {
            "items": [
                {
                    "title": f"方案{index}",
                    "creative_summary": "整体方案",
                    "creative_sources": ["原创组合"],
                    "frame_count": index + 1,
                    "visual_continuity_rules": ["保持主体和色彩连续"],
                    "frame_plan": [
                        {"index": frame, "description": f"画面{frame}"}
                        for frame in range(1, index + 2)
                    ],
                    "first_frame": {
                        "index": 1,
                        "content": "首帧内容",
                        "image_generation_instruction": "首帧图片指令",
                    },
                }
                for index in range(1, 4)
            ]
        }
        result = validate_visual_creative_recommendations(
            payload,
            carousel_config={"enabled": "是", "count_mode": "ai", "count": None, "rounds": []},
        )
        self.assertEqual([item["frame_count"] for item in result], [2, 3, 4])
        self.assertEqual(result[0]["first_frame"]["index"], 1)


if __name__ == "__main__":
    unittest.main()
