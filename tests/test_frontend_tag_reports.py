from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")


class FrontendTagReportTests(unittest.TestCase):
    def test_tag_renderer_uses_report_tables_and_per_group_confirmation_state(self):
        self.assertIn("creative-position-table", APP_JS)
        self.assertIn("data-confirm-tag", APP_JS)
        self.assertIn("data-edit-tag", APP_JS)
        self.assertIn("creative-position-table", STYLES)

    def test_tag_report_state_keeps_all_groups_and_target_summary(self):
        self.assertIn("confirmationProjectId", APP_JS)
        self.assertIn("selected-tag-summary", APP_JS)
        self.assertIn("target_audiences", APP_JS)

    def test_selected_options_remain_in_table_with_highlight_and_plain_text_summary(self):
        self.assertIn("items.map((option) => optionButton", APP_JS)
        self.assertIn("selected: selected.has(option.label)", APP_JS)
        self.assertIn("class=\"selected-report-value\"", APP_JS)
        self.assertIn(".selected-report-value { padding:0; border:0;", STYLES)
        self.assertIn("background:transparent", STYLES)

    def test_brief_is_embedded_at_top_of_positioning_flow(self):
        self.assertNotIn('id="stepBrief"', INDEX_HTML)
        self.assertNotIn('id="taskType"', INDEX_HTML)
        self.assertIn('id="taskDescription"', INDEX_HTML)
        self.assertLess(INDEX_HTML.index('id="taskDescription"'), INDEX_HTML.index('id="tagControls"'))
        self.assertIn('data-step="1"><span>1</span><strong>创意定位</strong>', INDEX_HTML)
        self.assertIn('data-step="2"', INDEX_HTML)

    def test_frontend_uses_two_step_navigation_without_task_type(self):
        self.assertNotIn("stepBrief", APP_JS)
        self.assertNotIn("taskType", APP_JS)
        self.assertIn("currentStep = 1", APP_JS)
        self.assertIn("currentStep = 2", APP_JS)

    def test_task_description_is_a_single_line_input(self):
        self.assertIn('<input id="taskDescription"', INDEX_HTML)
        self.assertNotIn('<textarea id="taskDescription"', INDEX_HTML)

    def test_tag_options_replace_oldest_selection_instead_of_disabling_remaining_options(self):
        self.assertIn("selectWithReplacement", APP_JS)
        self.assertNotIn("disabled: !selected.has(option.label) && selected.size >= max", APP_JS)
        self.assertNotIn("disabled: !selected.includes(option.label) && selected.length >= max", APP_JS)
        self.assertIn('key === "visual_art_style_references" ? 2', APP_JS)
        self.assertIn("round.overrides[key] = selectWithReplacement", APP_JS)
        self.assertIn("if (ordered.length >= totalMax) ordered.shift()", APP_JS)

    def test_generation_button_shows_unlimited_elapsed_wait_time(self):
        self.assertIn("generationStartedAt", APP_JS)
        self.assertIn("generationTimer", APP_JS)
        self.assertIn("已等待", APP_JS)
        self.assertIn("setInterval", APP_JS)
        self.assertIn("clearInterval", APP_JS)
        self.assertNotIn("generationTimeout", APP_JS)

    def test_frame_statuses_are_translated_for_scheme_details(self):
        self.assertIn("displayFrameStatusLabel", APP_JS)
        self.assertIn('success: "已完成"', APP_JS)
        self.assertIn('failed: "生成失败"', APP_JS)
        self.assertIn('pending: "等待中"', APP_JS)
        self.assertNotIn('esc(frame.image_status)</div>', APP_JS)

    def test_generation_refreshes_canonical_history_after_success(self):
        generate_body = APP_JS.split("async function generate()", 1)[1].split("async function retryImage", 1)[0]
        self.assertIn("await loadHistory(true);", generate_body)

    def test_portrait_image_frame_uses_full_9_by_16_ratio(self):
        self.assertIn(".image-frame.portrait { aspect-ratio: 9/16;", STYLES)
        self.assertIn(".image-frame img { width: 100%; height: 100%; object-fit: contain;", STYLES)

    def test_visual_carousel_cards_only_offer_continue_and_adopt_actions(self):
        self.assertNotIn('data-select-scheme="${item.id}"', APP_JS)
        self.assertNotIn('data-select-scheme]', APP_JS)
        self.assertNotIn("selectScheme(Number(button.dataset.selectScheme))", APP_JS)
        self.assertIn('data-continue-scheme="${item.id}"', APP_JS)
        self.assertIn('data-adopt-visual="${item.id}"', APP_JS)
        self.assertIn("/api/visual-items/${itemId}/continue", APP_JS)

    def test_continue_action_shows_in_progress_state_while_request_runs(self):
        self.assertIn("continuingSchemes", APP_JS)
        self.assertIn("继续生成中", APP_JS)

    def test_workspace_drops_realtime_brief_sidebar(self):
        self.assertNotIn('id="briefSummary"', INDEX_HTML)
        self.assertNotIn("briefSummary", APP_JS)
        self.assertIn(".step-layout { width:min(1360px,calc(100vw - 40px));", STYLES)
        self.assertIn("grid-template-columns:1fr;", STYLES)


if __name__ == "__main__":
    unittest.main()
