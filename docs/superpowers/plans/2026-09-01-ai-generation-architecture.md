# AI 创意生成架构重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有工作台 API、SQLite 历史读取和 `chat2api` 通用职责的前提下，将创意生成迁移为一次请求、明确轮播层级、可测试且可恢复的应用服务架构。

**Architecture:** `app.py` 只负责 HTTP 适配；新增 `generation_service.py` 编排输入快照、提示词、模型、schema、仓储和图片首帧任务。纯规则分别放入 `carousel.py`、`prompting.py`、`schemas.py`，通用模型协议放入 `model_client.py`；旧 `ai_creative.py` 入口保留为兼容适配器，SQLite 采用加法迁移。

**Tech Stack:** Python 标准库、`unittest`、SQLite、现有 `requests` HTTP 客户端、原生 HTML/CSS/JavaScript；不新增框架、Agent 或供应商业务逻辑。

**Spec:** `docs/superpowers/specs/2026-09-01-ai-generation-architecture-design.md`

## Global Constraints

- 保留 `POST /api/projects/{id}/generate`、历史接口、项目数据和既有 JSON 成功/失败包络。
- 一次正常生成只进行一次文字模型调用；仅允许一次格式修复重试，不增加独立标签补全调用。
- 轮播是一项方案内的 `frames`；一批固定 3 个方案，固定屏数 2--5，AI 决定时三项方案统一屏数。
- 不再要求或持久化 AI `resolved_tags` 作为用户标签事实；旧历史仍可读取。
- 展示类每个方案只创建一个首帧图片任务；按轮次图片不在本计划内。
- `image_prompt` 只保留在服务端，不进入浏览器历史响应。
- 不修改 `chat2api` 的创意业务边界，不引入认证、权限、多人部署或 React 正式迁移。
- 不删除或覆盖运行数据库、图片、上传文件；修改前保留现有用户工作区差异。
- 每个任务先写失败测试，再实现，再运行定向测试；任务完成后独立提交。

---

### Task 1: 冻结轮播与输出合同

**Files:**
- Create: `src/creative_studio/carousel.py` (扩展现有纯规则模块)
- Modify: `src/creative_studio/ai_creative.py:validate_visual_creative_recommendations`
- Test: `tests/test_carousel.py`, `tests/test_tag_options.py`

**Interfaces:**
- Consumes: 现有 `normalize_visual_carousel_config()`、`expand_visual_carousel_rounds()` 和视觉标签目录。
- Produces: `CarouselInput` 兼容数据（先以 dataclass 前的 dict 适配）、方案内 `carousel.frames` 校验；旧 `carousel_frames`/`resolved_tags` 历史读取保持不变。

- [ ] **Step 1: Write the failing tests**

```python
def test_validate_visual_carousel_accepts_frames_per_item_without_resolved_tags():
    result = validate_visual_creative_recommendations(
        {"items": [carousel_item_with_frames() for _ in range(3)]},
        carousel_config={"count_mode": "fixed", "count": 3},
    )
    self.assertEqual([len(item["carousel"]["frames"]) for item in result], [3, 3, 3])
    self.assertNotIn("resolved_tags", result[0])

def test_validate_visual_carousel_rejects_mismatched_ai_frame_counts():
    payload = {"items": [carousel_item_with_frames(2), carousel_item_with_frames(3), carousel_item_with_frames(2)]}
    with self.assertRaisesRegex(AiCreativeRequestError, "统一轮播屏数"):
        validate_visual_creative_recommendations(payload, carousel_config={"count_mode": "ai", "count": None})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_tag_options tests.test_carousel -v`
Expected: FAIL because the current validator requires `resolved_tags` and `carousel_frames` at item root.

- [ ] **Step 3: Implement the minimal contract change**

Add normalization of `carousel` with `count`, `form`, and `frames`; validate each frame object has a continuous 1-based `index` and non-empty display description. For fixed count require exact length; for AI count capture the first item's count and require all three items to match. Keep a compatibility branch in the repository/public-history conversion for legacy root fields, and remove only the generation-time requirement for `resolved_tags`.

- [ ] **Step 4: Run focused and regression tests**

Run: `python -m unittest tests.test_tag_options tests.test_carousel tests.test_repository -v`
Expected: PASS, including existing legacy history assertions.

- [ ] **Step 5: Commit**

```powershell
git add src/creative_studio/carousel.py src/creative_studio/ai_creative.py tests/test_carousel.py tests/test_tag_options.py
git commit -m "refactor: define carousel frames contract"
```

### Task 2: Introduce Shared Generation Models and Service

**Files:**
- Create: `src/creative_studio/generation_models.py`
- Create: `src/creative_studio/generation_service.py`
- Modify: `src/creative_studio/app.py:StudioApplication.generate`
- Test: `tests/test_generation_service.py`

**Interfaces:**
- Consumes: `StudioRepository`, existing AI functions through a temporary adapter, and `ImageJobRunner.enqueue()`.
- Produces: `CreativeGenerationRequest`, `CreativeInputSnapshot`, `GenerationContext`, `GenerationOutcome`, and `CreativeGenerationService.generate(request)`.

- [ ] **Step 1: Write failing service contract tests**

Use fake model/repository/image coordinator objects and assert: one normal model call; blank carousel hints still succeed; narrative creates no image jobs; visual creates exactly three image jobs; model failure calls `fail_generation`.

- [ ] **Step 2: Run the new test file and verify failure**

Run: `python -m unittest tests.test_generation_service -v`
Expected: FAIL with missing module/classes.

- [ ] **Step 3: Implement dataclasses and orchestration**

Define frozen request/context dataclasses with explicit types. Build the input snapshot from the project, normalize carousel input, choose `narrative.v1`, `visual.v1`, or `visual.carousel.v2`, reserve once, call the adapter once, complete the appropriate repository record, enqueue visual IDs, and fail the reservation on exceptions.

- [ ] **Step 4: Switch `app.py` to the service and run tests**

Keep `StudioApplication.generate(project_id)` as the HTTP-facing method, but make it load the project/reference files and construct `CreativeGenerationRequest`; remove prompt/schema decisions from this method. Run: `python -m unittest tests.test_generation_service tests.test_repository -v`.

- [ ] **Step 5: Commit**

```powershell
git add src/creative_studio/generation_models.py src/creative_studio/generation_service.py src/creative_studio/app.py tests/test_generation_service.py
git commit -m "refactor: add creative generation service"
```

### Task 3: Extract Prompting, Schemas, and Model Client

**Files:**
- Create: `src/creative_studio/prompting.py`
- Create: `src/creative_studio/schemas.py`
- Create: `src/creative_studio/model_client.py`
- Modify: `src/creative_studio/ai_creative.py`
- Modify: `src/creative_studio/generation_service.py`
- Test: `tests/test_prompting.py`, `tests/test_schemas.py`, `tests/test_model_client.py`

**Interfaces:**
- Consumes: existing prompt files/config loaders and `requests.post` transport.
- Produces: `CompiledPrompt`, `ModelRequest`, `ModelResponse`, `ModelClient`, `NarrativeRecommendationSchema`, `VisualRecommendationSchema`, and `CarouselRecommendationSchema`.

- [ ] **Step 1: Add failing pure-module tests**

Cover template variable substitution and stable prompt hash, model request/response conversion, narrative five-story validation, static three-item validation, carousel frame continuity, and absence of `resolved_tags` requirement.

- [ ] **Step 2: Verify failures**

Run: `python -m unittest tests.test_prompting tests.test_schemas tests.test_model_client -v`
Expected: FAIL because modules and interfaces do not exist.

- [ ] **Step 3: Extract implementations without changing public behavior**

Move only reusable logic from `ai_creative.py`; keep existing exported functions as thin adapters that call the new compiler/schema/client. The client owns generic HTTP, response parsing, usage extraction, latency, continuation IDs, and the single format-repair retry policy; it must not import creative tag constants.

- [ ] **Step 4: Point the service at the new interfaces and run all AI-structure tests**

Run: `python -m unittest tests.test_prompting tests.test_schemas tests.test_model_client tests.test_tag_options tests.test_generation_service -v`.
Expected: PASS with no real network request.

- [ ] **Step 5: Commit**

```powershell
git add src/creative_studio/prompting.py src/creative_studio/schemas.py src/creative_studio/model_client.py src/creative_studio/ai_creative.py src/creative_studio/generation_service.py tests/test_prompting.py tests/test_schemas.py tests/test_model_client.py
git commit -m "refactor: separate generation contracts and model client"
```

### Task 4: Persist Generation Context, Request IDs, and Recovery

**Files:**
- Modify: `src/creative_studio/repository.py`
- Modify: `src/creative_studio/generation_models.py`, `src/creative_studio/generation_service.py`
- Modify: `src/creative_studio/app.py` (error mapping)
- Test: `tests/test_repository.py`, `tests/test_generation_service.py`, `tests/test_app_api.py`

**Interfaces:**
- Consumes: `GenerationContext` and `request_id` from the service.
- Produces: additive `generations.context_json`, `generations.request_id`, pending expiration/recovery, and typed errors mapped to 422/404/409/500/502/503.

- [ ] **Step 1: Add failing migration/recovery/API tests**

Assert old databases open unchanged; new reservations persist context/request ID; stale pending rows become `expired` and no longer block the next batch; duplicate pending returns 409; malformed input returns 422; upstream failure returns 502.

- [ ] **Step 2: Verify failures**

Run: `python -m unittest tests.test_repository tests.test_generation_service tests.test_app_api -v`
Expected: FAIL because columns, expiration, and typed mapping are absent.

- [ ] **Step 3: Implement additive migration and typed errors**

Use `PRAGMA table_info` plus `ALTER TABLE ... ADD COLUMN` only for missing nullable columns. Store sanitized JSON context and opaque request ID; never store secrets or full model responses. Add a bounded expiration query for pending text generations at service startup/request time. Map domain exceptions in the existing handler while preserving the public error envelope.

- [ ] **Step 4: Run repository and API regression tests**

Run: `python -m unittest tests.test_repository tests.test_generation_service tests.test_app_api -v`.
Expected: PASS and legacy history remains readable.

- [ ] **Step 5: Commit**

```powershell
git add src/creative_studio/repository.py src/creative_studio/generation_models.py src/creative_studio/generation_service.py src/creative_studio/app.py tests/test_repository.py tests/test_generation_service.py tests/test_app_api.py
git commit -m "feat: persist generation context and recover pending work"
```

### Task 5: Make First-Frame Image Jobs Idempotent

**Files:**
- Modify: `src/creative_studio/image_jobs.py`
- Modify: `src/creative_studio/repository.py`, `src/creative_studio/generation_service.py`
- Test: `tests/test_image_jobs.py`, `tests/test_repository.py`

**Interfaces:**
- Consumes: persisted visual item IDs and `image_prompt` from the private result.
- Produces: stable key `creative-studio-{visual_item_id}-attempt-{attempt}`, gateway status mapping, retry isolation, and startup recovery of queued/generating jobs.

- [ ] **Step 1: Add failing idempotency/state tests**

Submit the same visual item/attempt twice and assert one gateway job; assert a retry increments only that item attempt; assert stale generating jobs return to queued without changing successful siblings.

- [ ] **Step 2: Verify failures**

Run: `python -m unittest tests.test_image_jobs -v`
Expected: FAIL because the current runner has no stable request key or recovery contract.

- [ ] **Step 3: Implement idempotent submission and guarded transitions**

Persist/lookup the attempt key before submitting, translate gateway states into local states, and update rows with an `attempt` predicate so an older worker cannot overwrite a newer retry. Keep one image per visual recommendation and continue hiding `image_prompt` from public history.

- [ ] **Step 4: Run image and full deterministic checks**

Run: `python -m unittest tests.test_image_jobs tests.test_repository -v`; then run the repository-wide commands in the final verification section.

- [ ] **Step 5: Commit**

```powershell
git add src/creative_studio/image_jobs.py src/creative_studio/repository.py src/creative_studio/generation_service.py tests/test_image_jobs.py tests/test_repository.py
git commit -m "fix: make first-frame image jobs idempotent"
```

### Task 6: Documentation, Changelog, and Release Verification

**Files:**
- Modify: `progress.md`
- Modify: `CHANGELOG.md` (only if user-visible API/history behavior changed)
- Modify: `.scratch/ai-generation-architecture/spec.md` (create if absent)

**Interfaces:**
- Consumes: completed commits, test output, and known unverified AI quality status.
- Produces: a dated change card, progress entry, migration/rollback notes, and truthful verification record.

- [ ] **Step 1: Create the change card before implementation starts**

Record goal, non-goals, acceptance examples, affected tables/API, backup requirement, and rollback commit for this plan.

- [ ] **Step 2: Run final deterministic checks**

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -v
node --check static\app.js
python -m compileall -q src chat2api
git diff --check
```

Expected: all commands exit 0. Real AI text/image generation remains explicitly marked unverified unless the user authorizes and performs a real smoke test.

- [ ] **Step 3: Run focused browser smoke if frontend contract changed**

Check `1280x720` and `390x844`, project history rendering, carousel frames display, no console error/warn, and no horizontal overflow. Do not alter binding address or firewall rules.

- [ ] **Step 4: Update progress and changelog**

Record commits, migration behavior, deterministic test results, browser/AI verification status, residual risks, and exact rollback procedure.

- [ ] **Step 5: Commit documentation**

```powershell
git add progress.md CHANGELOG.md .scratch/ai-generation-architecture/spec.md
git commit -m "docs: record generation architecture migration"
```

## Rollback Boundaries

- Tasks 1--3 can be reverted by commit without touching SQLite data; keep old adapter functions and legacy history conversion until the migration is accepted.
- Task 4 uses nullable additive columns only. To roll back, stop reading new columns and revert code; do not drop columns or restore an older database over the current one.
- Task 5 can restore the previous image runner while retaining completed image files and local status rows.
- If any deterministic test or schema compatibility check fails, stop the migration at the last passing task and record the failure in `progress.md`; do not issue real AI requests.
