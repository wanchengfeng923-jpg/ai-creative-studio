# Phase 5 交接：清理、数据治理与发布准备

> 给下一会话的执行文档。这里的“完成”指有代码、测试或临时演练证据；没有证据的事项保持进行中。

## 先看结论

当前项目已经完成 Phase 0 至 Phase 4 的主要代码迁移，但 Phase 5 尚未完成。下一会话的首要任务不是继续扩展功能，而是回答三个问题：

1. 哪些旧路径已经没有生产调用者，可以删除？
2. 历史公开投影能否在临时副本上安全 scrub、备份和恢复？
3. 评测和失败分类是否足以支撑发布决策？

当前最重要的事实：

- HEAD 为 `9e911e9`；实现检查点为 `5ad827c`。
- 工作树已经有两组先于本次 handoff 的未提交修改。第一组是用户保留的 `launcher.py`：`WEB_BIND_HOST = "0.0.0.0"`。第二组是独立的普通创意标签可选任务：`config/creative_tag_options.json`、`static/app.js`、`tests/test_tag_options.py`、`tests/test_frontend_tag_reports.py`、`CHANGELOG.md`、`progress.md`、`项目代码地图.md`、`docs/adr/0004-optional-tag-groups.md` 和 `.scratch/optional-tag-selection/`。两组都要保留，不能混入 P5 提交。
- 全量 deterministic unittest 最近一次结果为 `220` 项通过；标签可选任务的定向测试和完整门禁应由其原任务继续收尾。
- 默认运行库只做过只读 scrub：`scanned_rows=3`、`changed_rows=2`、`private_field_occurrences=6`。真实库未达到 fixed point，不能 `--apply`。
- 真实 AI、真实图片网关、认证浏览器、多进程生产竞态、真实数据库写入和备份恢复尚未验证。

## 1. 启动步骤

下一会话开始修改前，按项目规定完整阅读：

1. `AGENTS.md`
2. `progress.md`
3. `项目代码地图.md`
4. `docs/operations.md`
5. 本文档
6. `docs/ai-rebuild-master-plan.md`
7. `docs/ai/quality-evaluation.md`
8. `docs/adr/0001-public-result-projection.md`
9. `docs/adr/0003-carousel-v1-background-operation.md`
10. `docs/adr/0004-optional-tag-groups.md`（若继续处理标签可选任务）

然后执行事实快照：

```powershell
git status --short --branch
git log --oneline -8
rg -n "LegacyCreativeGenerationAdapter|VisualRecommendationSchema|load_ai_visual_first_frame_prompt|load_ai_visual_follow_up_prompt|complete_visual_generation" src tests config docs --glob '!docs/superpowers/handoffs/*'
```

事实快照完成标准：输出已保存到本次 P5 变更卡或 progress，并且已把标签可选任务与 P5 分开记录。

## 2. 当前架构基线

### 2.1 三条 active production 链路

| 用例 | PromptSpec | Module / caller | 公开结果 |
|---|---|---|---|
| 叙事 | `creative.narrative.generate@v6` | `NarrativeGeneration` / `narrative` | `NarrativeResult.v1` |
| 静态展示 | `creative.visual.static.generate@static-v1` | `StaticVisualGeneration` / `static` | `StaticVisualPublicDTO.v1` |
| 轮播 | `creative.visual.carousel.plan@visual-carousel-v1` | `CarouselVisualGeneration` / `carousel` | `CarouselPublicDTO.v1` |

`PromptRegistry` 在启动时校验 prompt 文件、hash、变量、contract、生命周期和唯一 production caller。三个 active 项均有 deterministic fake 和生产入口测试。

### 2.2 轮播当前行为

轮播首帧来自共享 planner 响应中的私有图片指令；后续画面由 `CarouselVisualGeneration.follow_up_image_prompt()` 编排。继续接口创建 `carousel_operations`，返回 `202`，后台协调器负责 lease、heartbeat、逐帧 claim、图片等待、原子提交和过期恢复。公开投影不包含 token、revision、图片指令、会话游标、gateway job id、本地路径或完整异常。

### 2.3 旧路径现状

| 旧项 | 当前真实引用 | P5 处理 |
|---|---|---|
| `LegacyCreativeGenerationAdapter` | `generation_service.py` 中作为 `model_client=None` 兼容 seam；`tests/test_generation_service.py` 验证 metadata 和 legacy persistence | 先做 caller 审计；没有“零 production caller + 保留期结束”证据时保留 |
| `schemas.py:VisualRecommendationSchema` | `tests/test_schemas.py` 直接使用；旧视觉/轮播兼容校验仍依赖旧形状 | 不要直接删除；先确认轮播和历史读取不再依赖，并迁移测试 |
| `load_ai_visual_first_frame_prompt()`、`load_ai_visual_follow_up_prompt()` | 当前为 retired loader 定义；registry 中对应 prompt 已 retired | 先添加无生产调用者的静态检查/测试，再删除 loader 和文件 |
| `complete_visual_generation()` | `generation_service.py` 的轮播 production 分支仍调用；多个 repository/image 测试直接调用 | 不是当前可删除项；轮播 canonical persistence 替换完成后再评估 |
| 旧视觉字段 `subtitle`、`creative_description`、`core_subject`、`layout`、`visual_style` | 历史读取、轮播兼容和旧测试仍存在 | 新静态写入不得恢复这些字段；历史读取保留直到 scrub/保留期门禁完成 |

关键判断：`create_application()` 默认会注入 model client，但这不等于所有兼容 seam 已经没有生产风险。删除前必须有可重复的 caller 证据，而不是只看默认构造参数。

## 3. P5 工作包

### P5-A：旧路径 caller 审计

目标：形成能支持“删除/保留”决策的证据，而不是简单 grep 清单。

执行：

1. 对上表每个旧项记录 `production`、`test`、`history/import`、`dead` 四类引用。
2. 对每个引用写明调用入口、输入/输出 contract 和是否读写用户数据。
3. 为确认结果添加最小测试或静态审计脚本；测试必须在临时目录运行。
4. 只有当旧项的 production caller 为零、历史读取不再依赖、替代路径已通过回归且保留期结束，才建立独立删除提交。

验收：

- registry 的三个 active 项各自恰好一个 production caller；
- 旧 loader 没有运行时代码调用；
- `LegacyCreativeGenerationAdapter`、`VisualRecommendationSchema`、`complete_visual_generation()` 的保留理由和删除条件都落在文档/测试中；
- 未删除仍被轮播 production 使用的旧持久化入口。

停止条件：发现任何旧项仍写入新 static canonical 数据、任何公开 DTO 出现私有字段，立即停止删除，保留诊断结果。

### P5-B：临时数据库 scrub、备份和恢复

目标：证明 projection scrub 可重复、可回滚，而不是直接修改用户运行库。

真实库只允许执行：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
python -m creative_studio.projection_scrub --database data\\creative_studio.db
```

临时演练步骤：

```powershell
New-Item -ItemType Directory -Force .scratch\\projection-scrub | Out-Null
Copy-Item -LiteralPath data\\creative_studio.db -Destination .scratch\\projection-scrub\\creative-studio-copy.db
python -m creative_studio.projection_scrub --database .scratch\\projection-scrub\\creative-studio-copy.db
python -m creative_studio.projection_scrub --database .scratch\\projection-scrub\\creative-studio-copy.db --apply --backup .scratch\\projection-scrub\\creative-studio-before.db
python -m creative_studio.projection_scrub --database .scratch\\projection-scrub\\creative-studio-copy.db
Copy-Item -LiteralPath .scratch\\projection-scrub\\creative-studio-before.db -Destination .scratch\\projection-scrub\\creative-studio-restored.db
python -m creative_studio.projection_scrub --database .scratch\\projection-scrub\\creative-studio-restored.db
```

验收：

- apply 前副本的统计被记录；
- apply 后副本报告 `changed_rows=0`、`private_field_occurrences=0`、`invalid_json_rows=0`、`unknown_kind_rows=0`；
- restored 副本的统计与 apply 前一致；
- backup、copy、restored 文件都位于 `.scratch/`，不进入 Git；
- 没有对 `data/creative_studio.db`、`data/images/` 或 `data/uploads/` 写入。

停止条件：任何 invalid JSON、unknown kind、统计不一致、备份路径已存在或副本不可读时停止；不要用参数绕过保护。真实库 apply 需要用户确认、停止服务、完整备份和单独变更卡。

### P5-C：评测报告和供应商失败分类

目标：把三套 fixture 变成可审阅的版本化报告结构，同时保持“fake 通过不代表真实质量通过”。

现有资产：

- `config/evals/narrative.v1.json`：10 cases；
- `config/evals/static.v1.json`：10 cases；
- `config/evals/carousel.v1.json`：10 cases；
- `docs/ai/quality-evaluation.md`：当前 deterministic 证据和真实评测边界。

下一会话应补齐：

1. 每个用例的 hard constraints、事实/证据、机制差异、可制作性、一眼可懂、第二批去重、私有字段扫描、调用次数、延迟和预算字段。
2. 失败分类的稳定维度：`model_output_invalid`、`provider_protocol_invalid`、`image_generation_failed`、`carousel_operation_failed`，并区分可重试性、阶段和字段路径。
3. baseline、candidate、repair/failure 三组结果的报告模板；没有真实结果时明确标记 `not_run`。
4. 报告测试：fixture 数量、case id 唯一、敏感凭据不出现、报告 schema 可解析。

验收：报告能回答“格式是否通过、事实是否可追溯、机制是否重复、失败发生在哪个阶段、实际调用几次”，但不虚构人工评分或供应商成功率。

### P5-D：文档和发布准备

只有代码/数据证据变化时才同步相应文档：

- `progress.md`：追加事实、验证命令、结果、提交哈希和未验证项；
- `docs/ai-rebuild-master-plan.md`：更新 Phase 5 当前状态和删除门禁；
- `docs/operations.md`：更新 scrub/备份/恢复实际演练结果；
- `项目代码地图.md`：caller、入口或表变化时更新；
- `docs/ai/quality-evaluation.md`：更新评测报告状态。

不要把历史 handoff 改成当前事实，也不要为了“完成 Phase 5”删除仍有兼容用途的代码。

## 4. 推荐提交切片

按以下边界提交，便于回滚和审查：

1. `test: audit retired AI callers`：只加审计测试/脚本和必要事实文档；
2. `test: rehearse projection scrub restore`：只保留临时演练脚本/测试，不含真实库；
3. `docs: add AI evaluation report schema`：评测报告和失败分类；
4. `refactor: remove retired loader`：只有 P5-A 删除门禁满足时才做；
5. `docs: close phase 5`：所有门禁通过后更新现状和提交哈希。

每个提交后运行受影响的定向测试；最终再运行全量门禁。提交时显式排除 `launcher.py`、标签可选任务的文件、`data/`、`data/images/`、`data/uploads/`、`chat2api/.env` 和 `.scratch` 运行产物。

## 5. 最终完成判定

Phase 5 只能在以下条件全部满足后标记完成：

- 旧 production caller 为零，并且每个保留项有可验证的历史读取/测试理由；
- active PromptSpec、Module、validator、public DTO、persistence 和评测集一一对应；
- 临时副本 scrub 达到 fixed point，backup 可恢复且恢复副本可读；
- 版本化评测报告和供应商失败分类已提交；
- 文档互相一致，`progress.md` 记录真实提交哈希；
- `python -m unittest discover -s tests -v`、`node --check static\\app.js`、`python -m compileall -q src chat2api`、`git diff --check` 全部通过；
- 真实 AI、图片网关、认证浏览器和真实生产库仍未运行的部分在最终报告中逐项列出。

只要其中一项缺失，状态写“Phase 5 进行中”，并把具体缺口留在 progress，不要用“代码已通过测试”代替发布完成。

## 6. 回滚和安全边界

- 代码清理按提交回滚；不通过 Git 覆盖数据库、图片或上传文件。
- registry/contract 回归优先回滚对应配置和 caller 提交。
- scrub 只在临时副本 apply；backup 和 restored 副本作为证据保留。
- 任何真实库写入、真实 AI/图片请求、监听地址变化、凭据变化、部署或认证边界变化，都要先停下，走项目高风险变更卡并取得用户确认。
