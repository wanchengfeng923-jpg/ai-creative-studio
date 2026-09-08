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
        self.assertIn("/api/auth/status", js)
        self.assertIn("/api/auth/login", js)
        self.assertIn("/api/projects", js)
        self.assertIn("/api/tag-options", js)
        self.assertNotIn("/api/projects/1/generate", js)
        self.assertNotIn("/api/projects/1/adopt", js)
        self.assertNotRegex(js, r"\b(?:execution|conversation_id|parent_message_id|gateway_job_id|image_prompt|prompt)\b")
        self.assertIn("/api/v2/", js)

    def test_page_has_three_inputs_and_explicit_on_demand_image_controls(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        for field in ("login-form", "project-select", "project-kind", "task-description", "aspect-ratio", "tag-groups"):
            self.assertIn(field, html)
        self.assertIn("loadProjects", js)
        self.assertIn("state.project", js)
        self.assertIn("addEventListener('click'", js)
        self.assertIn("/api/v2/image-attempts/", js)
        self.assertNotIn("setInterval", js)

    def test_frontend_keeps_dense_inputs_scannable_and_labels_result_fields(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("field-hint", html)
        self.assertIn("createElement('details')", js)
        self.assertIn("createElement('summary')", js)
        self.assertIn("scheme-field", js)
        self.assertIn("scheme-label", js)
        self.assertIn("auto-fit", (ROOT / "styles.css").read_text(encoding="utf-8"))

    def test_existing_workspace_exposes_on_demand_v2_image_actions(self) -> None:
        static_root = ROOT.parent
        html = (static_root / "index.html").read_text(encoding="utf-8")
        js = (static_root / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="resultsGrid"', html)
        self.assertIn("data-generate-image", js)
        self.assertIn("pollImageAttempt", js)
        self.assertIn("/api/v2/schemes/", js)
        self.assertNotIn("参考图会继续在后台完成", js)

    def test_root_workspace_exposes_v2_error_details_and_refresh_boundaries(self) -> None:
        js = (ROOT.parent / "app.js").read_text(encoding="utf-8")
        self.assertIn("ai_not_enabled:", js)
        self.assertIn("batch_conflict:", js)
        self.assertIn("provider_unavailable:", js)
        self.assertIn("traceId", js)
        self.assertIn("历史刷新失败", js)
        self.assertIn("项目列表刷新失败", js)
        self.assertNotIn('throw new Error(payload.error || "请求失败")', js)


if __name__ == "__main__":
    unittest.main()
