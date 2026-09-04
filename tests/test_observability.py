import unittest

from creative_studio.observability import StructuredObservability, sanitize_event


class ObservabilityTests(unittest.TestCase):
    def test_sanitize_event_keeps_metrics_and_drops_private_values(self):
        event = sanitize_event({
            "event": "generation_finished",
            "run_id": 3,
            "latency_ms": 12,
            "prompt": "不要记录",
            "content": "模型正文",
            "unknown": {"secret": "x"},
        })
        self.assertEqual(event["run_id"], 3)
        self.assertNotIn("prompt", event)
        self.assertNotIn("content", event)
        self.assertNotIn("unknown", event)

    def test_recorder_keeps_safe_event_copy(self):
        recorder = StructuredObservability()
        recorder.record({"event": "failed", "error_code": "model_output_invalid", "body": "raw"})
        self.assertEqual(recorder.events, [{"event": "failed", "error_code": "model_output_invalid"}])


if __name__ == "__main__":
    unittest.main()
