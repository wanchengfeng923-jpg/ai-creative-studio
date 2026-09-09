# Carousel Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将轮播继续生成改造成可恢复的后台 Operation，并让 API 与正式前端按公开逐帧状态观察进度。

**Architecture:** 在现有 SQLite `display_frames` 事实之上增加 `carousel_operations` 操作表。HTTP 层只创建/读取公开 Operation，后台协调器负责 lease、heartbeat、逐帧 claim、图片等待及原子完成；`PublicResultMapper` 统一投影 operation 和 scheme。旧 continue URL 保留，语义改为立即返回。

**Tech Stack:** Python 标准库 HTTP、SQLite、`ThreadPoolExecutor`、原生 JavaScript/CSS、`unittest`。

**Spec:** `.scratch/ai-phase-4/spec.md`

## Global Constraints

- 只修改轮播 contract/module、图片 worker/store、状态查询 API、前端轮询及对应文档/测试。
- 不修改静态 v1、叙事 v6、认证、监听、真实数据库、真实图片目录或 `chat2api/.env`。
- 所有公开结果必须由 `PublicResultMapper` deny-by-default 生成。
- 先写可变红测试并观察失败，再写最小实现。
- 不调用真实 AI、图片网关或带认证浏览器。

### Task 1: Operation persistence and lease primitives

**Files:**
- Modify: `src/creative_studio/repository.py`
- Modify: `src/creative_studio/public_projection.py`
- Test: `tests/test_carousel_operations.py`

**Interfaces:**
- `StudioRepository.get_or_create_carousel_operation(scheme_id: int, request_key: str, lease_seconds: int) -> dict[str, Any]`
- `StudioRepository.heartbeat_carousel_operation(operation_id: int, lease_token: str, lease_seconds: int) -> bool`
- `StudioRepository.claim_carousel_frame(operation_id: int, lease_token: str, frame_index: int) -> dict[str, Any] | None`
- `StudioRepository.complete_carousel_frame_atomic(operation_id: int, lease_token: str, frame_index: int, attempt: int, image_path: str, image_mime: str, conversation_id: str, parent_message_id: str) -> bool`
- `StudioRepository.finish_carousel_operation(operation_id: int, lease_token: str, status: str, error_code: str = "", error: str = "") -> bool`
- `StudioRepository.recover_stale_carousel_operations(lease_grace_seconds: int) -> list[int]`
- `PublicResultMapper.carousel_operation(value: Mapping[str, Any]) -> dict[str, Any]`

- [x] Write tests for idempotent creation, duplicate request, heartbeat, stale lease recovery, conditional claim, atomic completion, stale completion rejection, and private-field projection.
- [x] Add additive `carousel_operations` schema with request key, lease token, revision, current frame, status, timestamps and safe error fields.
- [x] Implement repository transactions using `BEGIN IMMEDIATE` and conditional lease/attempt updates.
- [x] Implement public projection with only allowlisted operation fields.
- [x] Re-run targeted tests and keep all existing tests green.

### Task 2: Carousel operation coordinator

**Files:**
- Create: `src/creative_studio/carousel_operations.py`
- Modify: `src/creative_studio/generation_service.py`
- Modify: `src/creative_studio/image_jobs.py`
- Test: `tests/test_carousel_operations.py`

**Interfaces:**
- `CarouselOperationCoordinator.start(scheme_id: int, request_key: str) -> dict[str, Any]`
- `CarouselOperationCoordinator.run(operation_id: int) -> None`
- `CarouselOperationCoordinator.recover() -> list[int]`
- `CarouselOperationCoordinator.stop() -> None`

- [x] Add fake image runner tests proving frame order, first-frame gate, retry limit, operation terminal states, and no real static enqueue changes.
- [x] Implement a dedicated executor-backed coordinator with bounded worker count and a heartbeat loop.
- [x] Move the synchronous loop behind coordinator execution and expose a named carousel compiler seam.
- [x] Make each frame wait for its image task before claiming the next, and atomically persist image result plus scheme cursor.
- [x] On stale lease or stale attempt, stop without overwriting newer state.
- [x] Re-run targeted tests and existing display-frame tests.

### Task 3: API and public status surfaces

**Files:**
- Modify: `src/creative_studio/app.py`
- Modify: `src/creative_studio/public_projection.py`
- Modify: `tests/test_app_api.py`
- Test: `tests/test_carousel_operations.py`

**Interfaces:**
- `POST /api/visual-items/{id}/continue` returns `success=true`, `operation`, and `scheme` immediately.
- `GET /api/visual-items/{id}/operation/{operation_id}` returns public operation and scheme.
- Existing `GET /api/visual-items/{id}/frames/status` remains public and adds operation summary when available.

- [x] Add API tests for immediate return, ownership and private-field rejection; operation lookup uses the same public route.
- [x] Wire project ownership checks before operation lookup and use mapper for all returned objects.
- [x] Preserve existing error envelope and start/recover/stop coordinator with the application lifecycle.
- [x] Re-run API and full deterministic tests.

### Task 4: Prompt/registry and old-path cleanup

**Files:**
- Modify: `config/ai_visual_carousel_prompt_v1.txt`
- Modify: `config/prompts/registry.json`
- Modify: `src/creative_studio/carousel.py`
- Modify: `src/creative_studio/generation_service.py`
- Test: `tests/test_carousel.py`

- [x] Add contract tests proving the production carousel prompt no longer promises independent first-frame text sessions or visible follow-up JSON.
- [x] Update prompt wording to shared planner + private first-frame instruction + image-only follow-up policy; keep declared output fields and registry hash synchronized.
- [x] Replace hard-coded follow-up policy text with a named carousel compiler/policy seam and preserve private instruction exclusion.
- [x] Re-run registry and carousel contract tests.

### Task 5: Frontend polling and responsive verification

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css` only if required for operation status layout
- Modify: `tests/test_frontend_tag_reports.py`

- [x] Add static contract tests for operation id rendering, 2-second polling, terminal cleanup, retry/continue labels, and no synchronous long-request assumption.
- [x] Implement operation state in page memory only as a cache; refresh truth from operation/status API and history.
- [x] Poll active operations and restore active operations from history after reload.
- [x] Run `node --check static/app.js`; responsive browser verification remains unperformed without an authenticated session.

### Task 6: Documentation, verification, and checkpoint

**Files:**
- Modify: `progress.md`
- Modify: `docs/project-rules/项目代码地图.md`
- Modify: `docs/project-rules/operations.md`
- Modify: `CHANGELOG.md` if user-visible polling behavior is recorded there

- [x] Document Operation lifecycle, lease recovery, public fields, endpoint behavior and rollback.
- [x] Run full unittest, Node syntax, Python compileall and `git diff --check`.
- [x] Confirm no `.env`, `data/`, generated images or uploads are staged.
- [x] Record verification results and explicitly unverified real AI/image/browser-auth items in `progress.md`.
- [ ] Create the final checkpoint commit after the last verification pass.
