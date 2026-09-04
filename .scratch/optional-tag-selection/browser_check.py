from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Route, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
TAG_CONFIG = json.loads((ROOT / "config" / "creative_tag_options.json").read_text(encoding="utf-8"))
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROJECT = {
    "id": 1,
    "name": "标签规则浏览器验收",
    "script_type": "展示类",
    "task_type": "",
    "task_description": "",
    "product_evidence_summary": "",
    "aspect_ratio": "16:9",
    "creative_tags": {},
    "reference_files": [],
    "adoption": None,
    "updated_at": "2026-09-04T11:00:00+08:00",
}
project_state = dict(PROJECT)
generation_requests: list[dict[str, str]] = []


def handle_api(route: Route) -> None:
    path = route.request.url.split("?", 1)[0]
    print(f"api {route.request.method} {path}", flush=True)
    if path.endswith("/api/auth/status"):
        payload = {"success": True, "authenticated": True, "user": {"id": 1, "username": "browser-check", "role": "user", "must_change_password": False}}
    elif path.endswith("/api/tag-options"):
        payload = {"success": True, "config": TAG_CONFIG}
    elif path.endswith("/api/projects"):
        payload = {"success": True, "projects": [project_state]}
    elif path.endswith("/api/projects/1/generate"):
        generation_requests.append(
            {
                "script_type": str(project_state["script_type"]),
                "task_description": str(project_state["task_description"]),
            }
        )
        payload = {"success": True}
    elif path.endswith("/api/projects/1/history"):
        payload = {
            "success": True,
            "recommendation_kind": "visual",
            "batches": [],
            "stale_batches": [],
            "remaining_generations": 2,
            "adoption": None,
        }
    elif path.endswith("/api/projects/1"):
        if route.request.method == "PUT":
            project_state.update(route.request.post_data_json)
        payload = {"success": True, "project": project_state}
    else:
        payload = {"success": True}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload, ensure_ascii=False))


def assert_no_horizontal_overflow(page) -> None:
    sizes = page.evaluate("() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth})")
    assert sizes["scroll"] <= sizes["client"], sizes


def main() -> None:
    output = ROOT / ".scratch" / "optional-tag-selection"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=CHROME_PATH)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page_errors = []
        page.set_default_timeout(5_000)
        page.on("console", lambda message: print(f"console {message.type}: {message.text}", flush=True))
        page.on("pageerror", lambda error: page_errors.append(f"{error}\n{error.stack}"))
        page.route("**/api/**", handle_api)
        print("browser-started", flush=True)
        page.goto("http://127.0.0.1:8798/index.html")
        print("page-loaded", flush=True)
        page.locator('[data-tag-report="visual_target_audiences"]').wait_for()
        print("visual-tags-ready", flush=True)

        page.locator('[data-tag-report="visual_target_audiences"] [data-confirm-tag]').click()
        assert page.locator('[data-tag-report="visual_target_audiences"]').is_visible()
        assert "请至少选择一项" in page.locator("#toast").inner_text()

        page.locator('[data-tag-report="visual_player_desires"] [data-confirm-tag]').click()
        assert page.locator('[data-tag-report="visual_player_desires"]').count() == 0
        assert "玩家欲望：" in page.locator(".selected-tag-summary").inner_text()
        assert "未选择" in page.locator(".selected-tag-summary").inner_text()
        page.get_by_role("button", name="修改玩家欲望").click()
        assert page.locator('[data-tag-report="visual_player_desires"]').is_visible()

        page.locator("#taskDescription").fill("")
        page.locator("#positionNextButton").click()
        page.locator("#stepOutput:not(.hidden)").wait_for()
        page.locator("#generateButton").click()
        page.locator("#toast", has_text="方案已生成").wait_for()
        assert generation_requests[-1] == {"script_type": "展示类", "task_description": ""}
        assert "请先填写创意说明" not in page.locator("#toast").inner_text()
        page.locator("#outputEditButton").click()

        carousel_report = page.locator('[data-tag-report="visual_carousel"]')
        assert carousel_report.locator(".creative-position-tables").count() == 0
        carousel_choices = carousel_report.locator("[data-carousel-choice]")
        assert carousel_choices.count() == 2
        assert carousel_choices.all_inner_texts() == ["是", "否"]

        carousel_report.locator('[data-carousel-choice="是"]').click()
        assert page.locator('[data-tag-report="visual_carousel_count"]').is_visible()
        assert page.locator('[data-tag-report="visual_carousel_form"]').is_visible()
        page.locator('[data-tag-report="visual_carousel_count"] [data-tag-value]').first.click()
        page.locator('[data-tag-report="visual_carousel_form"] [data-tag-value]').first.click()

        carousel_report.locator('[data-carousel-choice="否"]').click()
        assert page.locator('[data-tag-report="visual_carousel_count"]').count() == 0
        assert page.locator('[data-tag-report="visual_carousel_form"]').count() == 0
        carousel_report.locator('[data-carousel-choice="是"]').click()
        assert page.locator('[data-tag-report="visual_carousel_count"] .tag-option.selected').count() == 0
        assert page.locator('[data-tag-report="visual_carousel_form"] .tag-option.selected').count() == 0
        page.locator('[data-tag-report="visual_carousel_count"] [data-tag-value="3屏"]').click()
        page.locator('[data-tag-report="visual_carousel_form"] [data-tag-value]').first.click()

        round_editor = page.locator(".carousel-round-editor")
        round_toggles = round_editor.locator("[data-carousel-field-toggle]")
        assert round_toggles.count() == 6
        assert round_toggles.locator("strong").all_inner_texts() == [
            "主目标用户",
            "玩家欲望",
            "产品卖点",
            "展示内容",
            "视觉母题",
            "动态方案",
        ]
        assert [item.get_attribute("aria-expanded") for item in round_toggles.all()] == [
            "false", "false", "false", "false", "true", "true"
        ]
        assert "美术表现风格" not in round_editor.inner_text()
        assert "语音钩子" not in round_editor.inner_text()

        target_toggle = round_editor.locator('[data-carousel-field-toggle="visual_target_audiences"]')
        target_toggle.click()
        target_option = round_editor.locator('[data-tag-key="round:1:visual_target_audiences"]').first
        target_option.click()
        assert round_editor.locator('[data-carousel-field-toggle="visual_target_audiences"]').get_attribute("aria-expanded") == "true"
        assert round_editor.locator('[data-tag-key="round:1:visual_target_audiences"].selected').count() == 1

        round_editor.locator('[data-carousel-round="2"]').click()
        assert [item.get_attribute("aria-expanded") for item in round_editor.locator("[data-carousel-field-toggle]").all()] == [
            "false", "false", "false", "false", "true", "true"
        ]
        round_editor.locator('[data-carousel-round="1"]').click()
        assert round_editor.locator('[data-carousel-field-toggle="visual_target_audiences"]').get_attribute("aria-expanded") == "true"
        assert_no_horizontal_overflow(page)
        page.screenshot(path=output / "desktop-1280x720.png", full_page=True)
        print("desktop-checked", flush=True)

        page.set_viewport_size({"width": 390, "height": 844})
        assert_no_horizontal_overflow(page)
        page.screenshot(path=output / "mobile-390x844.png", full_page=True)
        print("mobile-checked", flush=True)

        page.locator("#scriptTypeSelect").select_option(label="叙事类")
        page.locator('[data-tag-report="target_audiences"] [data-confirm-tag]').click()
        assert page.locator('[data-tag-report="target_audiences"]').is_visible()
        page.locator('[data-tag-report="art_style"] [data-confirm-tag]').click()
        assert page.locator('[data-tag-report="art_style"]').count() == 0
        assert "美术风格：" in page.locator(".selected-tag-summary").inner_text()
        page.locator("#taskDescription").fill("")
        page.locator("#positionNextButton").click()
        page.locator("#stepOutput:not(.hidden)").wait_for()
        page.locator("#generateButton").click()
        page.locator("#toast", has_text="方案已生成").wait_for()
        assert generation_requests[-1] == {"script_type": "叙事类", "task_description": ""}
        assert "请先填写创意说明" not in page.locator("#toast").inner_text()
        assert len(generation_requests) == 2
        assert page_errors == [], page_errors
        print("narrative-checked", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
