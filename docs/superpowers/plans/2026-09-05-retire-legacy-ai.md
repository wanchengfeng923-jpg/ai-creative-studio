# 旧 AI 实现退役 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除全部旧 AI 可执行资产，同时保持项目、认证、备份和 AI v2 行为可用。

**Architecture:** 用独立的中立项目投影替换旧公开结果 mapper；将 `StudioRepository` 收缩为认证、项目和项目文件仓储。旧数据库表只保留、不迁移、不读取，新数据库不再创建旧 AI 表。

**Tech Stack:** Python 3 标准库、SQLite、`unittest`、原生 JavaScript。

**Spec:** `docs/superpowers/specs/2026-09-05-retire-legacy-ai-design.md`

## Global Constraints

- 保留 `src/creative_studio/ai_v2/`、`config/ai_v2/`、`config/evals/ai_v2/` 和 `chat2api/`。
- 不删除或修改真实数据库、图片、上传文件和 `.env`。
- 保留历史 ADR、handoff、计划、研究和 progress 记录。
- 所有新测试使用临时目录；不发真实 AI 请求。
- 当前会话内联执行，不使用子 agent。

---

### Task 1: 中立项目投影

**Files:**
- Create: `src/creative_studio/project_projection.py`
- Create: `tests/test_project_projection.py`
- Modify: `src/creative_studio/app.py`

**Interfaces:**
- Consumes: repository 返回的项目 mapping。
- Produces: `ProjectProjection.project(value) -> dict[str, Any]` 与 `ProjectProjection.summary(value) -> dict[str, Any]`。

- [x] **Step 1: 写失败测试**

```python
def test_project_projection_whitelists_project_and_file_fields(self):
    public = ProjectProjection().project({
        "id": 1,
        "name": "项目",
        "creative_tags": {"target_audiences": ["玩家"], "unknown": ["private"]},
        "reference_files": [{"id": 2, "original_name": "brief.txt", "stored_name": "secret.bin"}],
        "private": "secret",
    })
    self.assertEqual(public["reference_files"][0]["original_name"], "brief.txt")
    self.assertNotIn("stored_name", public["reference_files"][0])
    self.assertNotIn("private", public)
```

- [x] **Step 2: 验证 RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_project_projection -v`

Expected: FAIL，因为 `creative_studio.project_projection` 尚不存在。

- [x] **Step 3: 实现最小投影并替换 app 注入**

实现显式字段白名单、文件名净化和轮播标签投影；将 `StudioApplication.public_mapper` 改名为 `project_projection`，所有项目 API 使用新方法。

- [x] **Step 4: 验证 GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_project_projection tests.test_app_api -v`

Expected: PASS。

### Task 2: 收缩中立仓储

**Files:**
- Modify: `tests/test_repository.py`
- Modify: `src/creative_studio/repository.py`

**Interfaces:**
- Consumes: 认证服务、项目 API、AI v2 project provider 使用的既有方法。
- Produces: 只创建/访问 `projects`、`project_files`、`users`、`sessions`、`login_attempts`、`audit_logs` 的 `StudioRepository`。

- [x] **Step 1: 删除旧行为测试并写失败仓储边界测试**

```python
def test_new_database_contains_only_neutral_repository_tables(self):
    names = self._table_names(self.repo.database_path)
    self.assertFalse({"generations", "visual_items", "display_frames", "adoptions", "carousel_operations"} & names)

def test_initialization_preserves_existing_retired_tables_and_rows(self):
    # 建立带 retired_records 哨兵行的旧表，初始化 StudioRepository 后断言表和行未变。
```

- [x] **Step 2: 验证 RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_repository -v`

Expected: FAIL，当前仓储仍创建五类旧 AI 表。

- [x] **Step 3: 删除旧 schema、迁移和方法**

保留中立建表与迁移；`list_projects()` 不再 join `adoptions`，`get_project()` 不再查询旧采用表；删除 `get_visual_item_owner_id()` 以及项目文件记录之后的旧 AI/reference-asset 方法。

- [x] **Step 4: 验证 GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_repository tests.test_auth tests.test_auth_refresh tests.test_backup -v`

Expected: PASS。

### Task 3: 删除旧资产并强化边界

**Files:**
- Delete: `src/creative_studio/` 下非 `ai_v2` 的旧 AI 模块。
- Delete: 旧 Prompt、旧 v1 eval fixture/report、旧 AI 单元测试。
- Modify: `tests/test_tag_options.py`
- Modify: `tests/test_ai_v2_gateway_runtime.py`
- Modify: `tests/test_ai_v2_boundary.py`
- Create: `tests/test_retired_ai_cleanup.py`

**Interfaces:**
- Consumes: 设计规格中的精确退役清单。
- Produces: 旧模块/资产不存在且 AI v2 composition root 不依赖旧运行时的守卫。

- [x] **Step 1: 写失败退役守卫**

```python
def test_retired_python_modules_and_configuration_are_absent(self):
    for relative_path in RETIRED_PATHS:
        with self.subTest(path=relative_path):
            self.assertFalse((ROOT / relative_path).exists())
```

- [x] **Step 2: 验证 RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_retired_ai_cleanup -v`

Expected: FAIL，并列出仍存在的旧模块或配置。

- [x] **Step 3: 删除旧资产并调整保留测试**

使用 `apply_patch` 删除精确清单；标签测试只验证仍由页面使用的 `creative_tag_options.json`；gateway 测试直接断言 composition root 不暴露旧 runtime 属性，旧路由仍返回 404。

- [x] **Step 4: 验证 GREEN 与引用扫描**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_retired_ai_cleanup tests.test_tag_options tests.test_ai_v2_boundary tests.test_ai_v2_gateway_runtime -v`

Expected: PASS；`rg` 只允许历史文档和显式退役守卫出现旧名称。

### Task 4: 同步当前事实并完成验证

**Files:**
- Modify: `AGENTS.md`
- Modify: `CODE_STYLE.md`
- Modify: `项目代码地图.md`
- Modify: `docs/operations.md`
- Modify: `docs/ai/README.md`
- Modify: `CHANGELOG.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: 已验证代码和删除清单。
- Produces: 当前代码地图、运行边界、变更记录和最终提交。

- [x] **Step 1: 更新当前事实文档**

说明正式 AI 仅为 v2，旧表保留但不创建/不读取，备份保持只读兼容，Prompt 仍是 candidate。

- [x] **Step 2: 运行完整门禁**

```powershell
$env:PYTHONPATH='D:\code\ai_creative_studio\src'
python -m unittest discover -s tests -q
python -m unittest discover -s tests -p 'test_ai_v2_*.py' -q
node --check static\app.js
node --check static\ai-v2\app.js
python -m compileall -q src chat2api
python -m creative_studio.ai_v2.release_gate
git diff --check
```

- [x] **Step 3: 审核并提交**

确认暂存区不含 `.env`、数据库、图片、上传和运行产物，然后提交：

```powershell
git commit -m "chore: remove retired ai implementation"
```
