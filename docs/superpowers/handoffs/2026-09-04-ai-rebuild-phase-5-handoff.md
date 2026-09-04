# AI 重构 Phase 5 交接文档：清理、历史数据与发布准备

- 日期：2026-09-04
- 项目：`D:\\code\\ai_creative_studio`
- 当前分支：`codex/tag-accordion-prototype`
- 当前实现基线：`5ad827c feat: complete carousel operations and AI governance checkpoint`
- 当前文档验证提交：`e6382e6 docs: refresh verification counts`
- 工作树例外：用户已有的 `launcher.py` 修改 `WEB_BIND_HOST = "0.0.0.0"` 仍未暂存；必须保留，不要把它当作 P5 变更。

本文是下一会话继续执行 Phase 5 的事实交接。Phase 5 的目标是清理已经满足删除条件的旧路径、完成临时库上的历史 scrub/备份恢复演练、补齐评测与供应商失败分类，并让文档与 registry 一致。本文不授权真实运行库写入、删除用户数据、修改监听地址、修改 `chat2api/.env` 或调用真实 AI/图片网关。

## 1. 下一会话开始顺序

开始任何分析或修改前完整阅读：

1. `AGENTS.md`
2. `progress.md`
3. `项目代码地图.md`
4. `docs/operations.md`
5. 本文档
6. `docs/ai-rebuild-master-plan.md`
7. `docs/ai/quality-evaluation.md`
8. `docs/adr/0001-public-result-projection.md`
9. `docs/adr/0003-carousel-v1-background-operation.md`

随后执行只读事实检查：

```powershell
git status --short --branch
git log --oneline -8
rg -n "LegacyCreativeGenerationAdapter|VisualRecommendationSchema|load_ai_visual_first_frame_prompt|load_ai_visual_follow_up_prompt|complete_visual_generation" src tests config docs --glob '!docs/superpowers/handoffs/*'
```

## 2. 已完成事实

### AI 三条生产链路

`PromptRegistry` 当前有三个唯一 production 项：

| 用例 | registry 项 | production caller | canonical contract |
|---|---|---|---|
| 叙事 | `creative.narrative.generate@v6` | `narrative` | `NarrativeResult.v1` |
| 静态展示 | `creative.visual.static.generate@static-v1` | `static` | `StaticVisualResult.v1` |
| 轮播 | `creative.visual.carousel.plan@visual-carousel-v1` | `carousel` | `CarouselResult.v1` |

三个 production caller 均穿过对应 Module、validator、公开 DTO 和 deterministic fake seam。旧 v5、旧静态 v2.3、独立首帧 prompt 和独立后续 prompt 均已在 registry 标为 `retired`，并设有 replacement、`deprecated_since`、`new_callers_forbidden` 和删除条件。

### 轮播后台 Operation

- `POST /api/visual-items/{id}/continue` 已改为 `202`，返回公开 operation 摘要和方案。
- `carousel_operations` 保存 lease、heartbeat、revision、逐帧进度和终态。
- `CarouselOperationCoordinator` 串行领取下一帧；图片、frame、会话游标和 operation revision 原子提交。
- 过期 lease 恢复时只回收明确失活操作，并把崩溃 worker 遗留的 `generating` 帧重置为 `pending`。
- 公开层不返回 token、revision、图片指令、会话游标、gateway job id、本地路径或完整异常。

### 验证证据

- `python -m unittest discover -s tests -v`：220 项通过。
- `node --check static\\app.js`：通过。
- `python -m compileall -q src chat2api`：通过。
- `git diff --check`：通过。
- `config/evals/narrative.v1.json`、`static.v1.json`、`carousel.v1.json` 均有 10 个脱敏 case；新增 `tests/test_narrative_evals.py` 约束叙事评测集数量和脱敏字段。
- 未调用真实 AI、图片网关或带认证浏览器。

## 3. Phase 5 当前未完成项

### 3.1 旧代码清理前的 caller 审计

先建立一份只读审计结果，区分 production、测试、历史读取和 dead code：

- `src/creative_studio/generation_service.py:LegacyCreativeGenerationAdapter`：显式 `model_client=None` 时的兼容 seam；测试覆盖其 metadata 和 legacy persistence。默认 `create_application()` 注入 model client，不能只因默认 composition root 不走该分支就立即删除。
- `src/creative_studio/schemas.py:VisualRecommendationSchema`：仍被 `tests/test_schemas.py` 和旧视觉/轮播兼容校验引用；在轮播旧 contract、历史读取和测试迁移完成前保留。
- `src/creative_studio/ai_creative.py:load_ai_visual_first_frame_prompt` 与 `load_ai_visual_follow_up_prompt`：当前仅为 retired loader/审计 seam；需先补“无生产 caller”测试和历史读取说明，再删除实现与对应 prompt 文件。
- `complete_visual_generation()`：仍是旧视觉/轮播持久化入口；静态 production 已切到 `complete_static_generation()`，但轮播和兼容测试仍依赖它，不能在 P5 初始步骤删除。

删除条件必须同时满足：三个 Module 已有稳定生产 caller；`rg` 结果中旧生产 caller 为零；历史 importer/读取不再依赖；保留期结束；回归评测和全量测试通过。否则只补 metadata、审计测试和文档，不强行删除。

### 3.2 历史公开投影 scrub、备份和恢复演练

真实库只允许继续 dry-run：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
python -m creative_studio.projection_scrub --database data\\creative_studio.db
```

2026-09-04 已知结果：`scanned_rows=3`、`changed_rows=2`、`private_field_occurrences=6`、`invalid_json_rows=0`、`unknown_kind_rows=0`。因此真实库尚未达到 fixed point，不能执行 `--apply`。

P5 可安全完成的部分是在 `.scratch\\projection-scrub\\` 创建临时副本，按 `docs/operations.md` 完成：

1. dry-run；
2. 使用新的 backup 路径执行 `--apply`；
3. 对 apply 后副本再次 dry-run，确认 `changed_rows=0`、`private_field_occurrences=0`；
4. 从 backup 复制恢复副本，再 dry-run 比较统计；
5. 用临时副本启动只读应用或直接查询项目/图片记录，确认恢复可读。

临时演练成功不等于真实库迁移完成。真实库 apply 需要独立变更卡、停止服务、数据库/图片/上传目录备份、恢复验证和用户确认；禁止通过绕过工具保护执行。

### 3.3 质量评测报告和供应商失败分类

`docs/ai/quality-evaluation.md` 已记录三套 10-case fixture 和当前 deterministic 证据，但还没有真实模型质量报告。下一会话可以先完成离线报告模板和 fake 失败分类，包含：

- 硬约束通过率、字段路径和私有字段扫描；
- 确认事实错误数、证据状态和不确定性标记；
- 机制差异、可制作性、一眼可懂的人工评分栏；
- 第二批重复率、调用次数、延迟和预算字段；
- `model_output_invalid`、`provider_protocol_invalid`、`image_generation_failed`、`carousel_operation_failed` 等稳定错误码的统计维度。

真实模型/图片网关评测仍需固定脱敏输入、独立输出目录、预算和授权，不得把 fake 结果写成质量通过。

### 3.4 文档一致性与现状更新

完成任何 P5 子任务后同步：

- `progress.md`：追加式记录真实变更、验证和未验证项；
- `docs/ai-rebuild-master-plan.md`：只更新当前事实或 Phase 5 状态；
- `docs/operations.md`：更新可执行备份、恢复和 scrub 证据；
- `项目代码地图.md`：若 caller、表或入口变化则同步；
- `docs/ai/quality-evaluation.md`：记录评测资产和报告状态。

历史 handoff 不要改写成当前事实；若旧文档与当前代码冲突，增加指针或标记历史基线。

## 4. P5 建议执行顺序

1. 建立 `.scratch/ai-phase-5/spec.md`，写目标、非目标、不变量、验收例子、风险、回滚和真实库禁令。
2. 添加 caller 审计测试/脚本，证明 registry 的三个 production caller 唯一，旧路径只剩允许的兼容/历史/测试引用。
3. 在临时 SQLite 副本完成 projection scrub、backup、restore 和 fixed-point 检查；不触碰默认 `data/creative_studio.db`。
4. 为评测和供应商错误分类补齐 deterministic 报告结构与测试。
5. 只有当删除条件全部有证据时，分小提交清理 retired loader、dead schema 或误导性测试；每删一项立即运行定向测试。
6. 更新上述文档和本进度记录。
7. 执行最终门禁：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
python -m unittest discover -s tests -v
node --check static\\app.js
python -m compileall -q src chat2api
git diff --check
git status --short --branch
```

8. 提交前确认 `git diff --cached --name-only` 不包含 `launcher.py`、`data/`、`data/images/`、`data/uploads/`、`chat2api/.env` 或其他运行产物。

## 5. P5 完成门禁

只有以下全部满足时，才可把 Phase 5 标记完成：

- `rg` 证明旧生产 caller 为零，且保留项有明确历史读取/测试理由；
- 每个 active PromptSpec 有唯一 caller、contract、validator、public DTO 和评测集；
- 临时副本 scrub 达到 fixed point，backup 可恢复并可读取；
- 有版本化质量评测报告和供应商失败分类；
- 文档互相一致，progress 记录真实提交哈希；
- 全量测试、Node、compileall 和 diff check 全部通过；
- 真实 AI、图片、浏览器或生产数据库未验证的部分在最终报告中明确列出。

在此之前，Phase 5 状态应写为“进行中”，不要把删除旧代码、deterministic 通过或临时库恢复演练表述为生产发布完成。

## 6. 回滚

- 代码清理按单项提交回滚，不覆盖数据库、图片和上传目录。
- registry/contract 变更优先回滚对应配置和 caller 接线提交。
- projection scrub 只对临时副本 apply；恢复演练保留原副本和 backup，不覆盖默认运行库。
- 如发现公开 DTO 泄露私有字段、旧 worker 覆盖新 attempt、静态路径回归或真实数据误写，立即停止 P5，保留诊断证据并回滚最近代码提交。
