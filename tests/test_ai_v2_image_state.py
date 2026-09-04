from __future__ import annotations

import unittest

from creative_studio.ai_v2.image_state import ImageStateConflict, can_start_frame, can_start_static, stable_image_key, transition


class AiV2ImageStateTests(unittest.TestCase):
    def test_static_pending_and_failed_can_start_but_generating_and_success_cannot(self) -> None:
        self.assertTrue(can_start_static("pending"))
        self.assertTrue(can_start_static("failed"))
        self.assertFalse(can_start_static("generating"))
        self.assertFalse(can_start_static("success"))

    def test_carousel_only_current_pending_or_failed_frame_after_successful_prefix_can_start(self) -> None:
        self.assertTrue(can_start_frame(["pending", "pending", "pending"], 1))
        self.assertFalse(can_start_frame(["generating", "pending", "pending"], 1))
        self.assertFalse(can_start_frame(["failed", "pending", "pending"], 2))
        self.assertTrue(can_start_frame(["success", "pending", "pending"], 2))
        self.assertTrue(can_start_frame(["success", "success", "failed"], 3))
        self.assertFalse(can_start_frame(["success", "success", "success"], 3))

    def test_transitions_are_explicit_and_invalid_events_have_stable_code(self) -> None:
        self.assertEqual(transition("pending", "start"), "generating")
        self.assertEqual(transition("generating", "success"), "success")
        self.assertEqual(transition("generating", "failure"), "failed")
        self.assertEqual(transition("failed", "retry"), "generating")
        with self.assertRaises(ImageStateConflict) as context:
            transition("success", "start")
        self.assertEqual(context.exception.error_code, "image_already_successful")
        with self.assertRaises(ImageStateConflict) as context:
            transition("pending", "success")
        self.assertEqual(context.exception.error_code, "invalid_image_transition")

    def test_stable_image_key_uses_scheme_version_and_frame_index(self) -> None:
        self.assertEqual(stable_image_key("v2-run-1-scheme-2", 3), "v2-run-1-scheme-2:frame:3")
        with self.assertRaises(ImageStateConflict):
            stable_image_key("scheme", 0)


if __name__ == "__main__":
    unittest.main()
