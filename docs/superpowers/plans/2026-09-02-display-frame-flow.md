# 展示类连续画面生成流程实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有工作台 API、历史和首图兼容行为的前提下，实现展示类“3 套首帧方案 + 选中后按序生成后续画面”的后端流程。

**Architecture:** 继续使用现有 `app.py`、`generation_service.py`、`repository.py`、`image_jobs.py` 和 `model_client.py` 分层。首批方案一次生成并并行提交三张首图；用户选择方案后，服务端为该方案幂等创建 GPT 会话，并以方案级锁逐画面执行文字调用、图片任务和持久化。旧 `visual_items` 继续承载方案/首图兼容字段，新增画面级持久化由仓储层统一隐藏。

**Tech Stack:** Python 标准库 HTTP、SQLite、`unittest`、现有 OpenAI 兼容文字模型客户端和图片网关适配器。

**Spec:** `docs/superpowers/specs/2026-09-02-display-frame-flow-design.md`；总体边界参见 `docs/superpowers/specs/2026-09-01-ai-generation-architecture-design.md`。

## Global Constraints

- 展示类首次请求固定返回 3 套方案；不轮播为每套方案 1 张图，固定数量为 2～5，AI 决定时每套方案独立决定并锁定 2～5 张。
- 同一方案后续画面只能按 `2, 3, ...` 顺序生成；下一张必须等待上一张文字和图片成功，且使用上一张实际图片和画面信息。
- 用户一次继续操作只允许启动一个方案级流程；重复点击必须幂等或返回状态冲突。
- 首图失败只影响对应方案；图片单次自动重试一次，仍失败后保留成功结果并可从失败画面恢复。
- `image_generation_instruction`、完整模型消息、本地图片路径和秘密不得进入浏览器响应、历史或日志。
- 不修改叙事类业务规则，不发起真实 AI 请求，不修改 `.env`、运行数据库或无关模块。
- 测试使用假模型、假图片提供器和临时 SQLite，保持快速确定性；不新增第三方测试依赖。

---

### Task 1: 固化展示类首帧和后续画面领域模型

**Files:**
- Create: `src/creative_studio/display_frame_models.py`
- Modify: `src/creative_studio/generation_models.py`
- Test: `tests/test_display_frame_models.py`

**Interfaces:**
- Consumes: 现有 `VisualRecommendationSchema`、`CreativeGenerationRequest` 和 `ModelRequest`。
- Produces: `DisplayScheme`, `PlannedFrame`, `CompletedFrame`, `FrameGenerationState`, `SchemeGenerationState`、`SelectSchemeRequest`、`ContinueFramesRequest` 等带类型标注的内部对象；提供 `validate_frame_count(mode, requested, actual)` 和 `next_frame_index(frames)`。

- [ ] **Step 1: Write the failing test**

```python
def test_ai_count_is_independent_per_scheme_and_locked():
    def payload(frame_count):
        return {"title": "方案", "frame_count": frame_count, "frame_plan": [{"index": index, "description": "画面"} for index in range(1, frame_count + 1)]}

    schemes = [DisplayScheme.from_payload(payload(count)) for count in (2, 5)]
    assert [scheme.frame_count for scheme in schemes] == [2, 5]
    assert schemes[0].frame_count != schemes[1].frame_count
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_models -v`

Expected: FAIL because the new typed objects and validation helpers do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement immutable dataclasses and validation with these rules: `none` requires count `1`; `fixed` requires the requested integer `2..5`; `ai` accepts an independent actual count `2..5`; frame indexes must be continuous from `1`; frame route and visual continuity fields are immutable after construction. Keep hidden image instructions on internal frame objects only.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_models -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/creative_studio/display_frame_models.py src/creative_studio/generation_models.py tests/test_display_frame_models.py
git commit -m "feat: define display frame domain models"
```

### Task 2: 增加画面级持久化和兼容读取

**Files:**
- Modify: `src/creative_studio/repository.py`
- Modify: `tests/test_repository.py`
- Create: `tests/test_display_frame_repository.py`

**Interfaces:**
- Consumes: Task 1 的 `DisplayScheme`、`CompletedFrame` 和状态枚举。
- Produces: `save_display_schemes(generation_id, schemes)`, `get_display_scheme(scheme_id)`, `reserve_scheme_continuation(scheme_id)`, `save_completed_frame(scheme_id, frame)`, `fail_frame(scheme_id, frame_index, failure)`, `public_display_history(project_id, fingerprint)`。

- [ ] **Step 1: Write the failing test**

```python
def test_frame_state_and_hidden_instruction_survive_restart_without_public_leak(self):
    scheme_id = self.repo.save_display_schemes(self.generation_id, [self.scheme])[0]
    self.repo.save_completed_frame(scheme_id, self.frame_2)
    restored = self.repo.get_display_scheme(scheme_id)
    public = self.repo.public_display_history(project_id=self.project_id, fingerprint="fp")
    assert restored.frames[1].image_generation_instruction == "hidden prompt"
    assert "image_generation_instruction" not in json.dumps(public, ensure_ascii=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_repository -v`

Expected: FAIL because the frame table/repository methods do not exist.

- [ ] **Step 3: Write minimal implementation**

Add an idempotent additive migration for a frame-level table keyed by the existing scheme `visual_items` row and `frame_index`. Keep frame 1 readable from the legacy visual item and expose it through the same repository object as later frames. Store hidden image instructions only in the protected database/task payload. Add a scheme-level continuation lease/status updated in a transaction; stale leases become recoverable according to the existing pending timeout policy. Do not delete or rewrite legacy rows.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_repository tests.test_repository -v`

Expected: PASS, including existing legacy history tests.

- [ ] **Step 5: Commit**

```bash
git add src/creative_studio/repository.py tests/test_repository.py tests/test_display_frame_repository.py
git commit -m "feat: persist display frame state compatibly"
```

### Task 3: 实现首帧方案编排和三套首图部分成功

**Files:**
- Modify: `src/creative_studio/generation_service.py`
- Modify: `src/creative_studio/image_jobs.py`
- Modify: `src/creative_studio/ai_creative.py`
- Test: `tests/test_generation_service.py`

**Interfaces:**
- Consumes: Task 1 的首帧模型和 Task 2 的仓储方法；现有 `ModelClient` 与 `ImageJobRunner`/`GptWebImageClient` 边界。
- Produces: `CreativeGenerationService.generate_display_initial(...)` 和 `ImageJobRunner.enqueue_frame(...)`；返回公开方案、首图状态和隐藏字段已过滤的任务引用。

- [ ] **Step 1: Write the failing test**

```python
def test_initial_display_generation_returns_three_schemes_with_partial_first_image_failure(self):
    outcome = self.service.generate_display_initial(self.request)
    assert len(outcome.schemes) == 3
    assert [scheme.first_frame.image_status for scheme in outcome.schemes] == ["success", "failed", "success"]
    assert outcome.public_payload["items"][0].get("image_generation_instruction") is None
    assert self.fake_image_provider.max_parallel_submissions == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest tests.test_generation_service -v`

Expected: FAIL because the display-specific initial orchestration and per-scheme result are not implemented.

- [ ] **Step 3: Write minimal implementation**

Reuse the existing first prompt/schema path to create three locked schemes and their full frame plans. Submit exactly one frame-1 image task per scheme through the existing runner, allowing the three schemes to run independently. Wait for each first-frame task to reach success or failed before forming the response; one scheme failure must not fail the batch. Preserve the existing narrative path and API envelope.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest tests.test_generation_service -v`

Expected: PASS, including existing narrative and one-call model tests.

- [ ] **Step 5: Commit**

```bash
git add src/creative_studio/generation_service.py src/creative_studio/image_jobs.py src/creative_studio/ai_creative.py tests/test_generation_service.py
git commit -m "feat: orchestrate display initial frames"
```

### Task 4: 实现方案选择、独立会话和串行继续生成

**Files:**
- Modify: `src/creative_studio/generation_service.py`
- Modify: `src/creative_studio/model_client.py`
- Modify: `src/creative_studio/repository.py`
- Create: `tests/test_display_frame_continuation.py`

**Interfaces:**
- Consumes: Task 2 的方案锁、画面状态和 Task 3 的首帧实际结果。
- Produces: `CreativeGenerationService.select_scheme(scheme_id)`, `CreativeGenerationService.continue_scheme(scheme_id)`, `build_follow_up_frame_request(...)`；每次后续模型请求只带一个待生成序号和上一个实际画面。

- [ ] **Step 1: Write the failing test**

```python
def test_continue_is_serial_reuses_one_session_and_passes_previous_actual_image(self):
    self.service.select_scheme(self.scheme_id)
    self.service.continue_scheme(self.scheme_id)
    assert [call.frame_index for call in self.fake_model.follow_up_calls] == [2, 3]
    assert self.fake_model.follow_up_calls[1].previous_image_id == "frame-2-image"
    assert len(self.fake_model.created_conversations) == 1

def test_duplicate_continue_is_rejected_while_scheme_is_running(self):
    self.service.repository.reserve_scheme_continuation(self.scheme_id)
    with self.assertRaises(GenerationConflictError):
        self.service.continue_scheme(self.scheme_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_continuation -v`

Expected: FAIL because selection/session creation and serial continuation are not implemented.

- [ ] **Step 3: Write minimal implementation**

Make selection idempotently create one conversation and persist its message cursor. In `continue_scheme`, reserve the scheme lease, find the first incomplete frame, call the follow-up prompt once, persist the returned actual content, submit exactly one image, wait for its terminal state, then advance to the next frame. Pass the previous successful image through an explicit provider input object rather than a local path. Release the lease on success or failure; mark the scheme `completed` only when all locked frames succeed.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_continuation -v`

Expected: PASS with exactly one conversation and ordered frame calls.

- [ ] **Step 5: Commit**

```bash
git add src/creative_studio/generation_service.py src/creative_studio/model_client.py src/creative_studio/repository.py tests/test_display_frame_continuation.py
git commit -m "feat: generate display frames serially"
```

### Task 5: 完成失败重试、HTTP 接口和公开响应过滤

**Files:**
- Modify: `src/creative_studio/app.py`
- Modify: `src/creative_studio/image_jobs.py`
- Modify: `src/creative_studio/repository.py`
- Modify: `tests/test_app_api.py`
- Create: `tests/test_display_frame_recovery.py`

**Interfaces:**
- Consumes: Task 4 的 `select_scheme`、`continue_scheme` 和方案级状态。
- Produces: HTTP routes for selecting a scheme, continuing generation, retrying a failed first frame, and querying public frame status; stable request IDs `creative-studio-{visual_item_id}-frame-{frame_index}-attempt-{attempt}`.

- [ ] **Step 1: Write the failing test**

```python
def test_failed_frame_retries_once_then_can_resume_from_same_index(self):
    result = self.service.continue_scheme(self.scheme_id)
    assert result.scheme_status == "blocked"
    assert result.completed_frame_indexes == [1]
    resumed = self.service.continue_scheme(self.scheme_id)
    assert resumed.completed_frame_indexes == [1, 2, 3]
    assert self.fake_image_provider.attempts_for(self.scheme_id, 2) == 2

def test_http_public_history_hides_server_image_instruction(self):
    response = self.get("/api/projects/1/history")
    assert "image_generation_instruction" not in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_recovery tests.test_app_api -v`

Expected: FAIL because the new routes and recovery transitions are not implemented.

- [ ] **Step 3: Write minimal implementation**

Add server-side routes that call the service and map input/resource/conflict/upstream errors to the existing JSON envelope. Apply one automatic image retry per frame attempt; after the second failure set `blocked` without touching successful frames. A later continue reserves the same scheme and resumes from the failed index. Keep first-frame retry compatible with `/api/visual-items/{id}/retry`; expose no hidden prompt, full model message, gateway path, or local path.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m unittest tests.test_display_frame_recovery tests.test_app_api -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/creative_studio/app.py src/creative_studio/image_jobs.py src/creative_studio/repository.py tests/test_app_api.py tests/test_display_frame_recovery.py
git commit -m "feat: add display frame recovery APIs"
```

### Task 6: 回归验证和进度记录

**Files:**
- Modify: `progress.md`
- Modify: `CHANGELOG.md` only if the final implementation changes user-visible behavior.

**Interfaces:**
- Consumes: Tasks 1-5 completed code and tests.
- Produces: deterministic verification record and explicit note that real AI/image gateway calls remain unverified.

- [ ] **Step 1: Run focused fast tests**

Run:

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest tests.test_display_frame_models tests.test_display_frame_repository tests.test_display_frame_continuation tests.test_display_frame_recovery -v
```

Expected: PASS without network access or writes to `data/`.

- [ ] **Step 2: Run required repository checks**

Run:

```powershell
python -m unittest discover -s tests -v
node --check static\app.js
python -m compileall -q src chat2api
git diff --check
```

Expected: all deterministic checks pass; real AI generation and gateway image continuity remain explicitly unverified.

- [ ] **Step 3: Update progress**

Record the changed API/state behavior, focused and full test commands, migration compatibility, and remaining risk. Do not record tokens, full prompts, model responses, local image paths, or runtime database contents.

- [ ] **Step 4: Commit**

```bash
git add progress.md CHANGELOG.md
git commit -m "docs: record display frame flow implementation"
```

## Self-Review Checklist

- 首次三套方案、首图并行、部分失败返回：Task 3。
- `none`、固定数量、AI 独立数量锁定：Task 1。
- 方案路线锁定且不可重新规划：Task 1、Task 2、Task 4。
- 选择后单一 GPT 会话和后续游标复用：Task 4。
- 每张后续画面使用上一张实际图片并串行等待：Task 4。
- 自动重试一次、失败阻断、从失败序号恢复：Task 5。
- 隐藏图片指令不出浏览器/历史：Task 2、Task 5。
- 旧历史、叙事类路径和现有 API 兼容：Task 2、Task 3、Task 5。
- 无真实 AI 请求、测试简单快速：Global Constraints、Task 6。
