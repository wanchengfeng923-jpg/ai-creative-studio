from __future__ import annotations

import unittest
from pathlib import Path
import json

from creative_studio.ai_v2.projection import public_scheme


ROOT = Path(__file__).resolve().parents[1]


class AiV2RootFrontendRegressionTests(unittest.TestCase):
    def test_public_carousel_projection_preserves_database_frame_index(self) -> None:
        projected = public_scheme({
            "scheme_id": 1,
            "use_case": "carousel",
            "frames": [{"frame_index": 1, "description": "首帧"}, {"frame_index": 2, "description": "续帧"}],
        })
        self.assertEqual([frame["index"] for frame in projected["frames"]], [1, 2])

    def test_public_carousel_projection_exposes_core_subject(self) -> None:
        projected = public_scheme({
            "scheme_id": 1,
            "use_case": "carousel",
            "canonical": {"core_subject": "固定主体", "frames": []},
        })
        self.assertEqual(projected["core_subject"], "固定主体")

    def test_public_carousel_projection_falls_back_to_first_frame_subject(self) -> None:
        projected = public_scheme({
            "scheme_id": 1,
            "use_case": "carousel",
            "frames": [{"frame_index": 1, "description": "首帧主体"}],
        })
        self.assertEqual(projected["core_subject"], "首帧主体")

    def test_carousel_frames_use_public_description_and_frame_image_endpoint(self) -> None:
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("planned_content: frame.description", js)
        self.assertIn("data-generate-frame", js)
        self.assertIn("frameImage(itemId, frameIndex)", js)
        self.assertIn("item.frames?.[0]?.description", js)

    def test_image_generation_polls_direct_attempt_response(self) -> None:
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const attemptId = Number(payload.attempt_id", js)
        self.assertIn("图片任务未创建，请检查服务日志", js)
        self.assertIn("const latestItem = state.history", js)
        self.assertIn("该参考图已完成，页面已刷新", js)
        self.assertIn("state_conflict: \"图片状态刚刚发生变化，已刷新当前状态\"", js)

    def test_image_operation_state_is_scoped_to_the_frame(self) -> None:
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("function frameOperationKey(itemId, frameIndex)", js)
        self.assertIn("const operationKey = frameOperationKey(itemId, frameIndex)", js)
        self.assertIn("state.operationIds.has(operationKey)", js)
        self.assertIn("pollImageAttempt(itemId, attemptId, frameIndex)", js)
        self.assertIn("第${esc(frameIndex)}张生成中…", js)
        self.assertIn("/app.js?v=20260906-carousel-core-subject1", html)

    def test_carousel_uses_one_unified_image_action(self) -> None:
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("data-continue-scheme", js)
        self.assertNotIn("function continueScheme", js)
        self.assertIn("data-generate-frame", js)
        self.assertIn("const frame = frames.find((candidate) => candidate.image_status !== \"success\")", js)

    def test_history_refresh_does_not_force_results_step_after_editing_tags(self) -> None:
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("if (selectLatest && history.batches.length && currentStep < 2)", js)


if __name__ == "__main__":
    unittest.main()
