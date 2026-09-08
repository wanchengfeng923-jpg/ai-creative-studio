# AI v2 Production Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the root AI v2 entry point fail closed before live approval and expose actionable, traceable v2 errors without touching real AI or runtime data.

**Architecture:** Keep deterministic candidate adapters available only through explicit test injection. The production composition root returns a typed `ai_not_enabled` application error when live is not explicitly enabled, while the existing gateway adapters remain behind the explicit live flag. Centralize browser error normalization in `static/app.js`, preserving the existing v2 envelope and separating generation failures from post-generation history/project refresh failures.

**Tech Stack:** Python standard-library HTTP server, SQLite-backed AI v2 application, native browser JavaScript, Python `unittest`, Node syntax checks.

**Spec:** `docs/superpowers/handoffs/2026-09-05-ai-v2-production-integration-handoff.md` and `.scratch/ai-v2-production-integration/spec.md`

## Global Constraints

- Do not set `CREATIVE_STUDIO_AI_V2_LIVE=1` during this plan.
- Do not call external AI/image providers or modify `chat2api/.env`.
- Use temporary SQLite and image/upload directories in tests; never write `data/`.
- Preserve existing user changes and retired-AI isolation; no legacy fallback, dual-write, or dual-read.
- Error responses must not expose Prompt text, credentials, paths, stack traces, or complete provider responses.
- Every behavior change follows RED -> GREEN -> REFACTOR and is verified with fresh commands.

---

### Task 1: Establish P0 baseline and handoff artifacts

**Files:**
- Create: `.scratch/ai-v2-production-integration/spec.md`
- Create: `docs/superpowers/plans/2026-09-05-ai-v2-production-integration.md`
- Modify: `progress.md` only after implementation and verification are complete

**Interfaces:**
- Consumes: current handoff and repository validation commands.
- Produces: a scoped change card, this plan, and a recorded service state for the P1 work.

- [x] **Step 1: Record current branch, HEAD, worktree, and service state**

Run:

```powershell
git status --short --branch
git log --oneline -5
Get-NetTCPConnection -LocalPort 8775,8780 -State Listen -ErrorAction SilentlyContinue
```

Expected: branch and existing user changes are recorded; ports are stopped before code edits.

- [x] **Step 2: Write the change card and plan**

Use the exact files and contracts listed above. Keep real-call budget at zero and state rollback explicitly.

- [x] **Step 3: Run the fresh baseline gates**

Run:

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -q
python -m unittest discover -s tests -p "test_ai_v2_*.py" -q
node --check static\app.js
node --check static\ai-v2\app.js
python -m compileall -q src chat2api
python -m creative_studio.ai_v2.release_gate
python -c "from pathlib import Path; from creative_studio.ai_v2.boundary import assert_ai_v2_boundary; assert_ai_v2_boundary(Path('.'))"
git diff --check
```

Expected: capture actual counts and any pre-existing failures before P1 changes.

- [x] **Step 4: Commit only if the repository workflow requires a P0 checkpoint**

No checkpoint commit was required in this session; the two P0 documents remain in the working tree with existing user changes untouched.

### Task 2: Make the production composition root fail closed

**Files:**
- Modify: `src/creative_studio/app.py:create_application`
- Modify: `src/creative_studio/ai_v2/application.py` for stable `AiV2ApplicationError` semantics if needed
- Test: `tests/test_ai_v2_gateway_runtime.py`
- Test: `tests/test_ai_v2_app_integration.py` if HTTP-level coverage is needed

**Interfaces:**
- Consumes: explicit `ai_v2_text_model`/`ai_v2_image_model` injection for deterministic tests and `CREATIVE_STUDIO_AI_V2_LIVE` for live composition.
- Produces: `AiV2ApplicationError("ai_not_enabled", ..., phase="configuration", retryable=False)` from the formal entry point when no explicit test models and live is disabled.

- [x] **Step 1: Write the failing composition-root test**

Add a test that creates an application with temporary paths and an empty environment, accesses the v2 application, and asserts a stable `ai_not_enabled` error before any candidate generation can occur. Keep existing explicit fake-injection tests green.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest tests.test_ai_v2_gateway_runtime.AiV2GatewayRuntimeTests.test_composition_root_fails_closed_without_live_or_injected_models -v
```

Expected: FAIL because the current composition root constructs candidate models.

- [x] **Step 3: Implement the smallest fail-closed change**

Keep the factory lazy. If neither explicit text/image models nor live is configured, return an application whose first use raises the stable configuration error, or raise from the factory with the same safe error before constructing candidate adapters. Do not remove candidate classes; tests and explicit development seams may still inject them.

- [x] **Step 4: Run focused green tests**

Run the new test plus the existing gateway runtime and integration tests. Expected: the new fail-closed assertion passes, explicit fake injection still generates deterministic results, and explicit live still constructs gateway adapters without making a network request.

- [x] **Step 5: Refactor only after green**

Consolidate any duplicated configuration error construction without changing the envelope or error code.

### Task 3: Make root-page v2 errors actionable and separate refresh failures

**Files:**
- Modify: `static/app.js:api`, `static/app.js:generate`, `static/app.js:loadHistory`, `static/app.js:loadProjects`
- Test: existing frontend contract test file covering `static/app.js`, or create `tests/test_frontend_ai_v2_errors.py` if no suitable seam exists

**Interfaces:**
- Consumes: v2 error envelope fields `error_code`, `phase`, `retryable`, `trace_id`, and `field_path`.
- Produces: `Error` objects with safe user-facing `message`, `errorCode`, `phase`, `retryable`, `traceId`, and `fieldPath`; generation flow preserves a returned batch when a subsequent refresh fails.

- [x] **Step 1: Write failing frontend contract tests**

Cover these exact behaviors:

```javascript
// api() turns {error_code:"ai_not_enabled", trace_id:"t1"}
// into an Error whose message includes the safe Chinese mapping and trace id.
// generate() keeps an already-rendered generated batch when history refresh fails,
// and reports a separate refresh message instead of replacing it with "请求失败".
```

Use the repository's existing static-source contract pattern; do not add a browser dependency solely for this change.

- [x] **Step 2: Run the focused frontend tests and verify RED**

Run the exact test file with `python -m unittest ... -v` and confirm the current generic `请求失败` behavior fails the new assertions.

- [x] **Step 3: Implement typed error normalization**

Add a small internal mapping for known codes (`ai_not_enabled`, `invalid_input`, `unknown_field`, `batch_conflict`, `provider_unavailable`, `model_output_invalid`, `unauthorized`, `forbidden`) with a safe fallback. Attach trace metadata to the thrown `Error` without exposing server internals. Keep 401 login behavior and legacy `{error: ...}` responses compatible.

- [x] **Step 4: Separate generation and post-generation refresh catches**

In `generate()`, keep the generated response rendering as-is, wrap `loadHistory(true)` and `loadProjects()` in a distinct refresh path, and show a refresh-specific toast while retaining the generated cards. A generation request failure must show the normalized v2 error and may attempt a best-effort history refresh without overwriting the primary error.

- [x] **Step 5: Run focused green tests and Node syntax**

Run:

```powershell
python -m unittest tests.test_frontend_ai_v2_errors -v
node --check static\app.js
```

Expected: all new assertions pass and the JavaScript parses cleanly.

### Task 4: Full P1 verification and progress record

**Files:**
- Modify: `progress.md`
- Modify: `.scratch/ai-v2-production-integration/spec.md`

**Interfaces:**
- Consumes: green P1 tests and fresh repository gates.
- Produces: an auditable progress entry stating exactly what passed and what remains unverified.

- [x] **Step 1: Run the complete gate set**

Run the commands from Task 1 Step 3 plus the focused P1 tests. Expected: record exact counts and any unrelated baseline failure without relabeling it as success.

- [x] **Step 2: Inspect the diff and privacy boundary**

Run `git diff --check` and `rg -n "CandidateTextModel|CandidateImageModel|ai_not_enabled|trace_id|请求失败" src static tests`. Confirm candidate classes are not selected by the production root and no private data is added to responses or UI.

- [x] **Step 3: Append progress and update the change card**

Record branch, files, tests, no-live/no-real-call status, and remaining P2-P5 gates. Do not claim production readiness.

- [x] **Step 4: Review worktree before any commit**

Run `git status --short --branch`; stage only files belonging to this P0/P1 change if a checkpoint commit is explicitly needed.
