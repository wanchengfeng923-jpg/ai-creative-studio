# 展示类轮播逐轮创意定位实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不触发前置 AI 的前提下，让展示类轮播支持固定轮次定位、继承/自定义和最终生成时的 AI 标签补全。

**Architecture:** 保留现有原生前端、Python HTTP 服务、SQLite JSON 项目字段和图片队列。新增一个小型 Python 轮播规则模块处理输入规范化与继承，扩展展示类提示词和结果 schema；固定屏数在前端编辑，`AI决定` 在同一次最终生成响应中返回统一的 2～5 屏。

**Tech Stack:** Python 标准库 + `unittest`、原生 HTML/CSS/JavaScript、SQLite、现有 OpenAI 兼容文字网关和图片网关。

**Spec:** `docs/superpowers/specs/2026-09-01-visual-carousel-positioning-design.md`

## Global Constraints

- 第 1、2 步只做本地状态编辑和自动保存，不调用 AI。
- `是否轮播` 必须由用户先选择“是/否”；其他适用标签 UI 选填，空值在最终生成时由 AI 补全。
- 用户明确选择的值优先；后续轮次默认跟随第 1 轮，手动修改后为本轮自定义。
- 固定数量严格匹配 `2～5屏`；`AI决定` 时三套方案统一返回同一个 2～5 屏数量。
- AI 补全标签只能来自 `config/creative_tag_options.json`；产品卖点与展示内容必须满足既有依赖关系。
- 每套方案只生成第 1 轮代表图；不增加逐轮图片生成或补图接口。
- 不修改叙事类逻辑、每批 3 套/最多 2 批限制、数据库表结构或 `chat2api/.env`。
- 测试以功能路径为主，不在本轮建立完整 AI 评估集或逐字段质量评分。

## 文件地图

- Create `src/creative_studio/carousel.py`: 轮播请求规范化、固定轮次继承展开、数量和字段边界。
- Modify `src/creative_studio/ai_creative.py`: 轮播提示词上下文、轮播返回 schema、标签合法性校验、生成函数参数。
- Create `config/ai_visual_carousel_prompt_v1.txt`: 轮播展示类一次性生成模板。
- Modify `src/creative_studio/app.py`: 读取轮播配置、选择 schema/prompt、把配置纳入指纹并传给 AI。
- Modify `static/app.js`: 轮次编辑器、继承切换、最终 payload、轮播结果展示。
- Modify `static/styles.css`: 轮次标签页、继承状态和移动端布局。
- Modify `tests/test_tag_options.py`: 补充轮播配置/提示词的功能断言。
- Create `tests/test_carousel.py`: 轮次规范化与继承的最小功能测试。
- Modify `progress.md`、`CHANGELOG.md`: 记录用户可见行为、验证和未验证项。

---

### Task 1: 建立轮播配置和继承的纯函数

**Files:**
- Create: `src/creative_studio/carousel.py`
- Create: `tests/test_carousel.py`

**Interfaces:**
- `normalize_visual_carousel_config(tags: Mapping[str, Any], *, require_enabled: bool = False) -> dict[str, Any]`
- `expand_visual_carousel_rounds(config: Mapping[str, Any]) -> list[dict[str, Any]]`
- `CarouselValidationError(ValueError)`

- [ ] **Step 1: Write the functional tests first**

```python
class CarouselTests(unittest.TestCase):
    def test_fixed_count_expands_inherited_rounds(self):
        config = normalize_visual_carousel_config({
            "visual_carousel": ["是"],
            "visual_carousel_count": ["3屏"],
            "visual_carousel_rounds": [
                {"index": 1, "mode": "base", "overrides": {"visual_product_selling_points": ["卖点A"]}},
                {"index": 2, "mode": "inherit", "overrides": {}},
                {"index": 3, "mode": "custom", "overrides": {"visual_motif": ["母题C"]}},
            ],
        }, require_enabled=True)
        rounds = expand_visual_carousel_rounds(config)
        self.assertEqual(rounds[1]["visual_product_selling_points"], ["卖点A"])
        self.assertEqual(rounds[2]["visual_motif"], ["母题C"])

    def test_ai_count_has_no_predefined_rounds(self):
        config = normalize_visual_carousel_config({
            "visual_carousel": ["是"],
            "visual_carousel_count": ["AI决定"],
        }, require_enabled=True)
        self.assertEqual(config["count_mode"], "ai")
        self.assertEqual(expand_visual_carousel_rounds(config), [])

    def test_missing_carousel_choice_is_rejected_only_for_generation(self):
        with self.assertRaises(CarouselValidationError):
            normalize_visual_carousel_config({}, require_enabled=True)
        saved = normalize_visual_carousel_config({})
        self.assertEqual(saved["enabled"], "")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `$env:PYTHONPATH = "D:\code\ai_creative_studio\src"; python -m unittest tests.test_carousel -v`

Expected: FAIL because `carousel.py` and its public functions do not exist.

- [ ] **Step 3: Implement the minimal pure rules**

Implement `CarouselValidationError`, map `AI决定` to `count_mode="ai"`, map `2屏`～`5屏` to `count_mode="fixed"` and integer `count`, preserve hidden values when `enabled="否"`, validate fixed round indexes and count, and expand only `product_selling_points`, `display_contents`, and `motif`. Treat missing per-round values as `None` for AI completion; do not synthesize labels in this module.

- [ ] **Step 4: Run the focused test and verify it passes**

Run the same unittest command. Expected: all three tests PASS.

- [ ] **Step 5: Commit the isolated rules**

```powershell
git add src/creative_studio/carousel.py tests/test_carousel.py
git commit -m "feat: add carousel positioning rules"
```

### Task 2: Extend visual prompt input and output validation

**Files:**
- Modify: `src/creative_studio/ai_creative.py`
- Create: `config/ai_visual_carousel_prompt_v1.txt`
- Modify: `tests/test_tag_options.py`

**Interfaces:**
- `build_visual_creative_prompt(..., carousel_config: Mapping[str, Any] | None = None, tag_catalog: Mapping[str, Any] | None = None) -> str`
- `validate_visual_creative_recommendations(value: Any, *, carousel_config: Mapping[str, Any] | None = None, tag_catalog: Mapping[str, Any] | None = None) -> list[dict[str, Any]]`
- `generate_visual_creative_recommendations(..., carousel_config: Mapping[str, Any] | None = None, tag_catalog: Mapping[str, Any] | None = None) -> AiCreativeGenerationResult`
- `load_ai_visual_creative_config(..., carousel: bool = False) -> AiCreativeConfig`

- [ ] **Step 1: Add functional prompt/schema tests**

Extend `tests/test_tag_options.py` with a fixed `carousel_config` and assert that the built prompt contains the round indexes, `count_mode`, and an explicit instruction that blank applicable tags are AI-filled. Add a minimal valid 3-item carousel response fixture and assert the validator returns three items with `carousel_frames`.

- [ ] **Step 2: Run the focused tests and verify the new assertions fail**

Run: `$env:PYTHONPATH = "D:\code\ai_creative_studio\src"; python -m unittest tests.test_tag_options -v`

Expected: FAIL because the new function parameters, prompt template, and carousel fields are not implemented.

- [ ] **Step 3: Add the carousel prompt context**

Keep `format_creative_tags_for_prompt` for flat global tags. Add a bounded formatter in `ai_creative.py` that emits user-selected values, inherited overrides, blank applicable groups, fixed/AI count mode, and a compact catalog of valid labels grouped by key. Update `load_ai_visual_creative_config` to select the new prompt file and version `visual-carousel-v1` when `carousel=True`; otherwise preserve the existing path/version. Replace `{{carousel_context}}` in the new template; append the context if the marker is absent. Never include `image_prompt` in any public item.

- [ ] **Step 4: Add the carousel response schema and validator**

Keep the existing non-carousel validator path unchanged. When `carousel_config` is enabled, require the existing top-level visual fields plus `resolved_tags` and `carousel_frames`; validate exactly 3 items, fixed count equality or uniform 2～5 AI count, frame indexes, allowed configured labels, and the existing selling-point/display relation. Permit empty arrays only for non-applicable fields; every applicable blank input must have a valid AI-resolved value.

- [ ] **Step 5: Pass the new arguments through the generation function**

Add optional keyword arguments to `generate_visual_creative_recommendations`, pass them into `build_visual_creative_prompt`, and pass the same request into validation. Do not add retries or a second AI call when validation fails.

- [ ] **Step 6: Re-run the focused tests and commit**

Run: `$env:PYTHONPATH = "D:\code\ai_creative_studio\src"; python -m unittest tests.test_tag_options -v`

Expected: all existing and new functional tests PASS.

```powershell
git add src/creative_studio/ai_creative.py config/ai_visual_carousel_prompt_v1.txt tests/test_tag_options.py
git commit -m "feat: validate carousel creative output"
```

### Task 3: Connect application orchestration and history fingerprints

**Files:**
- Modify: `src/creative_studio/app.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- `StudioApplication._fingerprint(project: dict[str, Any]) -> str` includes normalized carousel config.
- `StudioApplication.generate(project_id: int) -> dict[str, Any]` rejects missing `visual_carousel` before reserving an AI request.

- [ ] **Step 1: Add the orchestration behavior test**

Add repository/application tests that store `visual_carousel_rounds` in `creative_tags`, read the project back unchanged, and assert `StudioApplication._fingerprint` changes when only a round override changes. Complete a visual generation containing `carousel_frames` and confirm history exposes the frames while still hiding `image_prompt`.

- [ ] **Step 2: Run the focused repository tests and verify the new test fails**

Run: `$env:PYTHONPATH = "D:\code\ai_creative_studio\src"; python -m unittest tests.test_repository -v`

Expected: FAIL because the fingerprint currently ignores nested round overrides and the new functional fixture is not yet asserted.

- [ ] **Step 3: Integrate the request in `app.py`**

Load `load_tag_options()` once for the generation request, call `normalize_visual_carousel_config(project["creative_tags"], require_enabled=True)` for visual projects, include that normalized config in `_fingerprint`, select `visual.carousel.v1` and `load_ai_visual_creative_config` with the carousel prompt only when enabled, and pass config/catalog into `generate_visual_creative_recommendations`. Preserve the existing non-carousel visual and narrative branches.

- [ ] **Step 4: Verify the existing repository snapshot behavior**

Confirm `complete_visual_generation` continues to remove `image_prompt` only from the public response while retaining the full content JSON for the image runner. Do not change `repository.py`, add a database migration, or alter existing columns and image state transitions.

- [ ] **Step 5: Run the focused tests and commit**

Run: `$env:PYTHONPATH = "D:\code\ai_creative_studio\src"; python -m unittest tests.test_repository tests.test_carousel -v`

Expected: all tests PASS.

```powershell
git add src/creative_studio/app.py tests/test_repository.py
git commit -m "feat: connect carousel generation flow"
```

### Task 4: Add fixed-round and inheritance editing to the formal frontend

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css`

**Interfaces:**
- Internal JS helpers: `carouselCountFromDraft()`, `renderCarouselRounds()`, `renderCarouselRoundEditor(roundIndex)`, `setCarouselRoundMode(roundIndex, mode)`, `collectProject()` includes `visual_carousel_rounds`.

- [ ] **Step 1: Add the local state/render test fixture**

Use the existing browser smoke harness or a temporary console script to load a project with `visual_carousel=["是"]` and `visual_carousel_count=["3屏"]`; assert the rendered DOM contains three round controls, “跟随第1轮” for rounds 2 and 3, and no network request beyond the existing project/tag-option/history loads.

- [ ] **Step 2: Implement draft normalization and round rendering**

Extend `normalizeTagDraft` without changing flat tag limits. Render the round editor directly after the carousel count/form chapters when carousel is enabled and count is fixed. Each round contains the three per-round groups, a mode control, and a reset-to-inherit action. Use existing `optionButton`/grouped rendering so labels, escaping, dependency filtering, and primary/secondary limits remain consistent.

- [ ] **Step 3: Implement inheritance and event delegation**

Add delegated handlers for round mode, round tag selection, and reset actions. Editing round 1 updates the displayed inherited values but does not overwrite custom round overrides. Switching “是/否” hides or restores round data and keeps the saved object. `AI决定` hides the round editor. All handlers call `scheduleSave()` only; none calls the generation API for AI work.

- [ ] **Step 4: Add final generation guards and payload collection**

Make `updateGenerateState`/the generate click path require `visual_carousel` to be either “是” or “否”. `collectProject()` must include the round object and preserve empty tag arrays so the server can distinguish user omissions. Keep the current automatic save and two-batch behavior.

- [ ] **Step 5: Style desktop and mobile states**

Add compact round tabs/mode controls using existing CSS variables and button styles. At `1280x720`, keep the editor within the wide workspace; at `390x844`, use one column and prevent horizontal overflow. Do not add a new framework or inline style system.

- [ ] **Step 6: Run JavaScript syntax and browser smoke checks; commit**

Run: `node --check static/app.js`.

Browser checks: fixed `2屏`/`3屏`, inherited-to-custom switch, reset-to-inherit, switch to “否” and back to “是”, `AI决定` hides tabs, and no console error/warn at both required viewports.

```powershell
git add static/app.js static/styles.css static/index.html
git commit -m "feat: add carousel round editor"
```

### Task 5: Render carousel positioning and AI source labels in results

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css`

**Interfaces:**
- Internal JS helper: `renderCarouselDetails(item) -> string` returns escaped round positioning and resolved tag markup without exposing `image_prompt`.

- [ ] **Step 1: Add a fixed response fixture to the browser smoke data**

Use the existing test server or a local response override containing one visual item with `carousel_frames`, `resolved_tags.global`, and `resolved_tags.frames`; assert the result card still renders its image state and adoption button.

- [ ] **Step 2: Implement result rendering**

Update `renderVisualBatch` to append a collapsible carousel section only when `carousel_frames` is a non-empty array. Show each frame index, title, description, core subject, layout, and resolved labels. Render source labels as text badges for `user`, `inherited`, and `ai`; escape every AI/database string through the existing `esc` helper.

- [ ] **Step 3: Verify compatibility and commit**

Check that old non-carousel items render exactly as before, failed image retry still targets the same item ID, and adoption still posts the existing payload. Run `node --check static/app.js` and the browser smoke checks, then commit:

```powershell
git add static/app.js static/styles.css
git commit -m "feat: show carousel positioning details"
```

### Task 6: Functional verification and project records

**Files:**
- Modify: `progress.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run the focused functional test suite**

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -v
node --check static\app.js
python -m compileall -q src chat2api
git diff --check
```

Expected: existing tests plus carousel functional tests pass; no real AI request is made.

- [ ] **Step 2: Run the required browser paths**

Against the local app, verify one fixed-count carousel, one `AI决定` carousel, one non-carousel visual project, and one narrative project. Confirm one final Generate click starts the text request and the UI never requests AI while editing tags. Check `1280x720` and `390x844` for no horizontal overflow and no console error/warn.

- [ ] **Step 3: Record the result honestly**

Update `progress.md` with the implemented flow, functional tests, browser checks, and the explicit limitation that real AI quality, real image generation, and per-round image supplementation remain unverified. Add a `CHANGELOG.md` entry under the current unreleased section describing per-round carousel positioning and AI completion at final generation.

- [ ] **Step 4: Commit documentation and final diff**

```powershell
git add progress.md CHANGELOG.md
git commit -m "docs: record carousel positioning delivery"
```

## Self-Review Checklist

- Spec coverage: Tasks 1–3 cover JSON storage, inheritance, one-call prompt/input, schema validation and fingerprinting; Tasks 4–5 cover editor, hidden/restored state, AI决定, source labels and result rendering; Task 6 covers regression and records.
- No database migration or pre-step AI call is introduced.
- The plan treats all UI tags as optional while keeping `visual_carousel` as the required generation gate.
- No real AI quality claim is made; verification stays functional as requested.
- All later task interfaces use the exact names introduced in earlier tasks.
