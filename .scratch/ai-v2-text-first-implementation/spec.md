# AI v2 文字优先与按需生图实施变更卡

- 日期：2026-09-04
- 状态：Task 0 冻结基线，Prompt 正文生产接入仍待用户审批
- 依据：`docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`、`docs/superpowers/plans/2026-09-04-ai-v2-text-first-implementation.md`

## 目标

在旧 AI 冻结且完全隔离的前提下，按实施计划建立独立的 AI v2 边界、三字段输入、版本化契约、文字优先和按需图片执行链路。每个阶段只修改计划列出的文件，并以定向测试和可回滚文档为交付边界。

## 非目标与审批门禁

- 不修改旧 AI builder、validator、结果字典、轮播编排、旧图片 worker 或旧生产路由。
- 不读取、双写、双读或通过兼容层串联旧 AI；v2 失败不回退旧链路。
- 不调用真实文字/图片模型，不修改真实数据库、图片、上传文件、`chat2api/.env`、监听配置或部署。
- Prompt 正文、真实案例质量评测和正式生产 caller 在用户审批前只保持候选/测试状态；不执行正式入口切换。
- v2 暂不接受产品证据、补充资料或参考文件字段。

## 业务边界

HTTP 输入严格为 `task_description`、`aspect_ratio`、`creative_tags` 三个字段。文字生成同步返回：叙事每批 5 套，展示每批 3 套；同一定位最多两批，每批一个新的文字会话，结构错误直接失败，不做隐藏格式修复调用。

图片按方案按需创建：静态方案最多一张，轮播方案所有帧共享一个图片会话，单次点击最多推进一张。重试前先查本地 attempt 和原图片会话并对账；只有供应商明确终态失败时才在原会话内创建同一帧的新 attempt。供应商成功/工作中、未知或不可用分别恢复/挂接或保留当前 attempt，不创建第二个图片会话。

## 影响文件与隔离

Task 0 仅新增本变更卡、`docs/adr/0005-ai-v2-boundary-and-session-policy.md`，并在 v2 设计稿添加链接索引。后续任务只允许修改实施计划文件表列出的 v2 目录、对应测试和明确的组合根挂载点。

## 当前冻结基线

- 分支：`codex/tag-accordion-prototype`
- HEAD：以 Task 0 开始时 `git status --short --branch` 输出为准（执行时未创建新提交）。
- 工作树存在既有用户修改；这些修改全部保留，不得 reset、checkout、覆盖或批量删除。完整列表如下：

```text
M CHANGELOG.md
M README.md
M config/ai_visual_carousel_prompt_v1.txt
M config/ai_visual_static_creative_prompt_v1.txt
M config/creative_tag_options.json
M config/evals/narrative.v1.json
M config/prompts/registry.json
M docs/ai-rebuild-master-plan.md
M docs/ai/quality-evaluation.md
M docs/operations.md
M docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md
M docs/superpowers/specs/2026-09-01-visual-carousel-positioning-design.md
M launcher.py
M progress.md
M src/creative_studio/__init__.py
M src/creative_studio/ai_creative.py
M src/creative_studio/app.py
M src/creative_studio/carousel.py
M src/creative_studio/carousel_visual.py
M src/creative_studio/generation_models.py
M src/creative_studio/generation_service.py
M src/creative_studio/narrative.py
M src/creative_studio/prompting.py
M src/creative_studio/public_projection.py
M src/creative_studio/repository.py
M src/creative_studio/static_visual.py
M static/app.js
M static/styles.css
M tests/test_app_api.py
M tests/test_carousel.py
M tests/test_frontend_tag_reports.py
M tests/test_generation_service.py
M tests/test_launcher_proxy.py
M tests/test_narrative_generation.py
M tests/test_projection_scrub.py
M tests/test_public_projection.py
M tests/test_static_visual.py
M tests/test_tag_options.py
M 项目代码地图.md
?? .scratch/ai-v2-text-first-preview/
?? .scratch/optional-tag-selection/
?? .scratch/phase-5-completion/
?? .scratch/phase-5-governance/
?? config/evals/report-template.v1.json
?? config/evals/reports/
?? docs/adr/0004-optional-tag-groups.md
?? docs/ai/phase5-caller-audit.md
?? docs/release/
?? docs/superpowers/plans/2026-09-04-ai-v2-text-first-implementation.md
?? docs/superpowers/plans/2026-09-04-ai-v2-text-first-preview.md
?? docs/superpowers/plans/2026-09-04-phase-5-and-release-readiness.md
?? docs/superpowers/specs/2026-09-04-ai-studio-complete-roadmap-design.md
?? docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md
?? docs/superpowers/worklogs/
?? src/creative_studio/backup.py
?? src/creative_studio/evaluation_harness.py
?? src/creative_studio/observability.py
?? src/creative_studio/phase5_governance.py
?? src/creative_studio/reference_assets.py
?? src/creative_studio/release_gate.py
?? tests/test_backup.py
?? tests/test_evaluation_harness.py
?? tests/test_generation_models.py
?? tests/test_observability.py
?? tests/test_phase5_governance.py
?? tests/test_reference_prompt_integration.py
```

## 验收例子

1. v2 边界扫描器拒绝任何旧 AI 模块、旧路由或旧表名引用。
2. 相同三个输入和 Prompt 版本产生稳定 fingerprint；空标签组被移除，轮播控制标签保留。
3. 一批文字只创建一个文字会话；三个展示方案都点击生图时为一个文字会话加三个图片会话。
4. 轮播第 2 帧在第 1 帧成功前不可执行；失败重试先对账，不因未知结果创建新 attempt 或新会话。
5. 浏览器响应和日志不含 Prompt、`execution`、会话游标、gateway job id、本地路径、完整模型响应或堆栈。

## 回滚

Task 0 回滚只删除本变更卡、ADR 和设计稿中的索引段。后续代码以任务级提交/差异为边界回滚；不通过 Git 覆盖数据库、图片、上传文件或凭据。真实 Prompt 接入和入口切换在审批前不执行，因而无需生产回滚。

## Task 0 交接

- 任务：Task 0 / 冻结点、变更卡与会话 ADR
- 修改文件：本文件、`docs/adr/0005-ai-v2-boundary-and-session-policy.md`、`docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`
- 未修改的关键边界：旧 AI、旧表、真实凭据、生产数据、监听配置
- 测试：`git diff --check`（Task 0 收尾执行）
- 未验证：真实 AI/图片供应商、认证浏览器、多进程竞态和正式入口
- 下一任务：Task 1；Task 2/3/6 在 Task 1 后

