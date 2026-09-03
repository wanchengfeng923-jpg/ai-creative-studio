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
        self.assertIn("selected-tag-summary", APP_JS)
        self.assertNotIn("renderSelectedChips(group, draft)", APP_JS)

    def test_project_delete_is_available_on_each_row_and_navigates_after_delete(self):
        self.assertNotIn('id="deleteProjectButton"', INDEX_HTML)
        self.assertIn("data-delete-project=\"${item.id}\"", APP_JS)
        self.assertIn("event.stopPropagation()", APP_JS)
        self.assertIn("async function deleteProject(projectId)", APP_JS)
        self.assertIn("nextProject", APP_JS)
        self.assertIn("previousProject", APP_JS)

    def test_visual_carousel_uses_dedicated_yes_no_control(self):
        self.assertIn("function renderCarouselChoice(group, draft)", APP_JS)
        self.assertIn("data-carousel-choice", APP_JS)
        self.assertIn('value === "否"', APP_JS)
        self.assertIn("renderCarouselChoice(group, draft)", APP_JS)

    def test_display_contents_stays_visible_until_product_selling_point_is_selected(self):
        self.assertIn('group.key === "visual_display_contents"', APP_JS)
        self.assertIn("请先选择产品卖点", APP_JS)
        self.assertIn("product_display", APP_JS)
        self.assertIn("draft.visual_display_contents = (draft.visual_display_contents || []).filter", APP_JS)

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

    def test_tag_options_disable_unselected_values_at_limit_without_replacement(self):
        self.assertIn("selectWithinLimit", APP_JS)
        self.assertNotIn("selectWithReplacement", APP_JS)
        self.assertIn("disabled: !selected.has(option.label) && selected.size >= max", APP_JS)
        self.assertIn("selected.length >= max", APP_JS)
        self.assertNotIn("ordered.shift()", APP_JS)

    def test_carousel_inheritance_can_be_edited_and_reset(self):
        self.assertIn("copyCarouselRoundOverrides", APP_JS)
        self.assertIn("editInheritedSelection", APP_JS)
        self.assertIn("round.mode = \"custom\"", APP_JS)
        self.assertIn('round.mode = "inherit"', APP_JS)
        self.assertNotIn("round.overrides[key] = selectWithReplacement", APP_JS)

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

    def test_static_visual_cards_render_canonical_fields_first(self):
        self.assertIn("item.audience_tension", APP_JS)
        self.assertIn("item.product_value", APP_JS)
        self.assertIn("item.visual_mechanism", APP_JS)
        self.assertIn("item.static_frame", APP_JS)
        self.assertIn("item.evidence_ledger", APP_JS)

    def test_continue_action_shows_in_progress_state_while_request_runs(self):
        self.assertIn("continuingSchemes", APP_JS)
        self.assertIn("继续生成中", APP_JS)

    def test_continue_action_polls_a_background_operation_until_terminal(self):
        self.assertIn("/operation/${operationId}", APP_JS)
        self.assertIn("operationId", APP_JS)
        self.assertIn("scheduleOperationPolling", APP_JS)
        self.assertIn("setTimeout", APP_JS)
        self.assertIn("completed_frame_count", APP_JS)
        self.assertIn("function stopImagePolling()", APP_JS)
        self.assertIn("schedulePolling() {\n    stopImagePolling();", APP_JS)

    def test_history_restores_active_operation_polling_after_reload(self):
        self.assertIn("const operation = item.operation || null", APP_JS)
        self.assertIn("state.operationIds.set(Number(item.id), operationId)", APP_JS)
        self.assertIn("if (!state.operationPollTimers.has(Number(item.id)))", APP_JS)

    def test_workspace_drops_realtime_brief_sidebar(self):
        self.assertNotIn('id="briefSummary"', INDEX_HTML)
        self.assertNotIn("briefSummary", APP_JS)
        self.assertIn(".step-layout { width:min(1360px,calc(100vw - 40px));", STYLES)
        self.assertIn("grid-template-columns:1fr;", STYLES)


if __name__ == "__main__":
    unittest.main()
