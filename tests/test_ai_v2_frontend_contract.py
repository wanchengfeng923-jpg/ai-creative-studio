from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "static" / "ai-v2"


class AiV2FrontendContractTests(unittest.TestCase):
    def test_assets_are_self_contained_and_use_only_v2_api(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("/ai-v2/app.js", html)
        self.assertIn("/ai-v2/styles.css", html)
        self.assertNotRegex(js, r"/api/(?!v2/)")
        self.assertNotRegex(js, r"\b(?:execution|conversation_id|parent_message_id|gateway_job_id|image_prompt|prompt)\b")
        self.assertIn("/api/v2/", js)

    def test_page_has_three_inputs_and_explicit_on_demand_image_controls(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        for field in ("task-description", "aspect-ratio", "tag-groups"):
            self.assertIn(field, html)
        self.assertIn("addEventListener('click'", js)
        self.assertIn("/api/v2/image-attempts/", js)
        self.assertNotIn("setInterval", js)


if __name__ == "__main__":
    unittest.main()

