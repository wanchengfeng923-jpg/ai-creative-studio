# Static Visual Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将静态展示类生成迁移到 `StaticVisualResult.v1` canonical contract，同时保持叙事 v6、轮播和现有 HTTP/图片状态机不变。

**Architecture:** 新增静态展示深模块负责输入、registry prompt、校验和有限 repair；生成服务只按类型分派。静态使用专用 persistence/public projection 入口复用现有 SQLite 表和图片 worker，静态不创建 `display_frames`，最后才切换 registry production caller。

**Tech Stack:** Python 标准库、`unittest`、SQLite、原生 JavaScript、现有 `PromptRegistry`、`ModelClient` 和 `ImageJobRunner`。

**Spec:** `.scratch/ai-phase-3/spec.md`

## Global Constraints

- 每批静态结果恰好 3 个方案，每案恰好 1 个首图任务。
- `image_generation_instruction` 只能存在于内部对象、受控图片任务或私有存储列，不得进入公开 DTO。
- 不修改叙事 v6、轮播 prompt/validator/继续生成/逐帧状态机、真实 `data/`、`launcher.py` 或 `chat2api/.env`。
- 新静态结果不得写入 `subtitle`、`core_subject`、`layout`、`visual_style` 等旧别名；旧 alias 仅可在历史读取兼容层出现。
- 所有生产入口测试使用临时 SQLite、deterministic fake、固定时钟和隔离环境。

---

### Task 1: Canonical Static Contract

**Files:**
- Create: `src/creative_studio/static_visual.py`
- Modify: `tests/test_static_visual.py`
- Modify: `.scratch/ai-phase-3/spec.md`

**Interfaces:**
- Consumes: `PromptRegistry`, `ModelClient`/`ModelRequest`, existing prompt compiler helpers.
- Produces: `StaticVisualPromptInput`, `StaticVisualResult`, `StaticVisualOutputError`, `StaticVisualGeneration.generate()` and `to_persisted_item()`.

- [ ] **Step 1: Write the failing test**

  Add tests for exact root/item keys, A/B/C uniqueness, evidence and asset status validation, URL/Markdown rejection, mechanism difference, and private instruction exclusion from public projection.

- [ ] **Step 2: Run test to verify it fails**

  Run: `$env:PYTHONPATH='D:\code\ai_creative_studio\src'; python -m unittest tests.test_static_visual -v`
  Expected: import/contract failures because `static_visual.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

  Implement frozen dataclasses and explicit mapping validation. Compile only declared prompt variables with the existing literal compiler. Allow one format repair request carrying the exact field path and safe reason; cap calls at the registry policy.

- [ ] **Step 4: Run test to verify it passes**

  Run the same focused command and confirm all contract tests pass.

- [ ] **Step 5: Commit**

  `git add src/creative_studio/static_visual.py tests/test_static_visual.py .scratch/ai-phase-3/spec.md; git commit -m "refactor: add static visual canonical contract"`

### Task 2: Static Persistence and Public Projection

**Files:**
- Modify: `src/creative_studio/repository.py`
- Modify: `src/creative_studio/public_projection.py`
- Modify: `tests/test_repository.py`
- Modify: `tests/test_public_projection.py`

**Interfaces:**
- Consumes: `StaticVisualResult` and its typed item/prompt split from Task 1.
- Produces: `StudioRepository.complete_static_generation()` and `PublicResultMapper.static_visual_item()`.

- [ ] **Step 1: Write the failing test**

  Add temporary SQLite tests that persist three canonical items, assert no old aliases and no `display_frames`, assert `image_prompt` is private, and scan history/status/adoption projections for private keys.

- [ ] **Step 2: Run test to verify it fails**

  Run: `$env:PYTHONPATH='D:\code\ai_creative_studio\src'; python -m unittest tests.test_repository tests.test_public_projection -v`
  Expected: missing method/mapper or assertions fail because current visual persistence writes aliases and frames.

- [ ] **Step 3: Write minimal implementation**

  Add a transactionally isolated static completion method using existing `generations`, `visual_items`, and `image_prompt` columns. Store only canonical public content in JSON and keep private prompt in `image_prompt`; do not call carousel/display-frame persistence. Route static public data through an explicit allowlist branch while leaving carousel projection unchanged.

- [ ] **Step 4: Run test to verify it passes**

  Run focused repository/projection tests and existing carousel repository tests.

- [ ] **Step 5: Commit**

  `git add src/creative_studio/repository.py src/creative_studio/public_projection.py tests/test_repository.py tests/test_public_projection.py; git commit -m "refactor: persist static visual canonical items"`

### Task 3: Composition Root Caller and Image Request Seam

**Files:**
- Modify: `src/creative_studio/generation_service.py`
- Modify: `src/creative_studio/image_jobs.py`
- Modify: `src/creative_studio/app.py`
- Modify: `tests/test_generation_service.py`
- Create: `tests/test_static_generation_integration.py`

**Interfaces:**
- Consumes: Task 1 `StaticVisualGeneration`, Task 2 static repository/mapper.
- Produces: production static path through `create_application(model_client=fake, image_runner=fake)`, typed `StaticVisualImageRequest` at the queue boundary, and unchanged narrative/carousel paths.

- [ ] **Step 1: Write the failing test**

  Add composition-root tests for complete/blank inputs, one shared model request plus bounded repair, three image requests, no private history fields, and unchanged narrative/carousel prompt refs. Add partial image failure/retry assertions.

- [ ] **Step 2: Run test to verify it fails**

  Run: `$env:PYTHONPATH='D:\code\ai_creative_studio\src'; python -m unittest tests.test_static_generation_integration -v`
  Expected: fake caller still reaches legacy visual validator/persistence and canonical assertions fail.

- [ ] **Step 3: Write minimal implementation**

  Dispatch only non-carousel visual snapshots to `StaticVisualGeneration`; construct static persistence records and enqueue exactly one request per scheme. Keep old adapter fallback for explicit `model_client=None` and keep carousel branch untouched. Add a small request dataclass/adapter without changing worker scheduling or request-id semantics.

- [ ] **Step 4: Run test to verify it passes**

  Run integration tests, then narrative and carousel targeted tests.

- [ ] **Step 5: Commit**

  `git add src/creative_studio/generation_service.py src/creative_studio/image_jobs.py src/creative_studio/app.py tests/test_generation_service.py tests/test_static_generation_integration.py; git commit -m "refactor: route static generation through canonical module"`

### Task 4: Registry Flip, Frontend Compatibility, and Evaluation Fixtures

**Files:**
- Modify: `config/prompts/registry.json`
- Modify: `static/app.js`
- Create: `config/evals/static.v1.json`
- Create: `tests/test_static_evals.py`
- Modify: `tests/test_frontend_tag_reports.py`

**Interfaces:**
- Consumes: Task 3 production static caller and public DTO.
- Produces: `creative.visual.static.generate@static-v1` as the sole static production item, old `visual-v2.3` retired, frontend canonical-first rendering, and a reproducible 10-case hard-constraint evaluation fixture.

- [ ] **Step 1: Write the failing test**

  Add registry lifecycle/caller uniqueness tests, canonical-first frontend contract tests, and fixture tests requiring at least 10 cases with fact/quality/privacy fields.

- [ ] **Step 2: Run test to verify it fails**

  Run: `$env:PYTHONPATH='D:\code\ai_creative_studio\src'; python -m unittest tests.test_static_evals tests.test_frontend_tag_reports -v`
  Expected: registry still points production to `visual-v2.3`, frontend only knows legacy fields, and fixture is absent.

- [ ] **Step 3: Write minimal implementation**

  Flip registry only after Tasks 1-3 are green, set `static-v1` metadata to the explicit contract/caller/policy, retire v2.3 with removal condition, render canonical fields with one historical fallback, and add 10 sanitized cases covering blank brief, aspect ratio, filename-only references, unconfirmed facts, missing assets, duplicate mechanisms, long copy, URL/Markdown injection, and repair failure.

- [ ] **Step 4: Run test to verify it passes**

  Run focused registry/frontend/evaluation tests and the full deterministic suite.

- [ ] **Step 5: Commit**

  `git add config/prompts/registry.json static/app.js config/evals/static.v1.json tests/test_static_evals.py tests/test_frontend_tag_reports.py; git commit -m "feat: enable static visual v1 production contract"`

### Task 5: Documentation and Phase 4 Handoff

**Files:**
- Modify: `progress.md`
- Modify: `项目代码地图.md`
- Modify: `docs/operations.md`
- Create: `docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md`

**Interfaces:**
- Consumes: all implementation commits and verification output from Tasks 1-4.
- Produces: current-fact documentation with actual hashes, callers, tests, rollback and explicit unverified real-AI/image/browser/database items.

- [ ] **Step 1: Write the failing test**

  Add a docs consistency check only if an existing test harness supports it; otherwise use `rg` assertions during review for registry key, module path, caller and retired alias.

- [ ] **Step 2: Run test to verify it fails**

  Run: `rg -n "static-v1|StaticVisualGeneration|complete_static_generation|Phase 4" progress.md 项目代码地图.md docs/operations.md`
  Expected: current docs do not contain final implementation evidence.

- [ ] **Step 3: Write minimal implementation**

  Update only statements contradicted by the final code; record implementation commit hashes, verification counts, old alias caller list, no-real-data boundary, and Phase 4 scope.

- [ ] **Step 4: Run test to verify it passes**

  Run the required unittest, Node syntax, compileall, diff-check, status, and `launcher.py` diff checks.

- [ ] **Step 5: Commit**

  `git add progress.md 项目代码地图.md docs/operations.md docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md; git commit -m "docs: hand off AI rebuild phase 4"`
