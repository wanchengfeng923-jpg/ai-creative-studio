import unittest

from creative_studio.model_client import ModelRequest, ModelResponse
from creative_studio.model_ports import DeterministicImageModel, DeterministicTextModel, ImageModelRequest


class ModelPortTests(unittest.TestCase):
    def test_deterministic_text_port_is_replayable_and_counts_requests(self):
        fake = DeterministicTextModel([ModelResponse(content='{}')])
        fake.generate(ModelRequest("m", [], None, 10))
        self.assertEqual(len(fake.requests), 1)
        self.assertFalse(fake.capabilities.structured_output_enforced)

    def test_deterministic_image_port_keeps_reference_mime(self):
        fake = DeterministicImageModel()
        ref = fake.submit(ImageModelRequest("draw", reference_images=(b"jpg",), reference_mimes=("image/jpeg",)), request_id="x")
        self.assertEqual(ref.job_id, "x")
        self.assertEqual(fake.requests[0].reference_mimes, ("image/jpeg",))


if __name__ == "__main__":
    unittest.main()
