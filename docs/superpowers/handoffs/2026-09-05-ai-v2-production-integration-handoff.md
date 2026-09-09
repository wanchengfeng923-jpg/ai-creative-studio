# AI v2 正式版接入交接

> 交给下一执行会话的工作文档。本文定义从 candidate 模式进入正式 AI 接入的执行顺序，
> 不代替 `AGENTS.md`、`docs/project-rules/operations.md`、ADR 或后续实施计划。

## 先看结论

当前根页面 `/` 已接入 AI v2 HTTP、存储、历史、按需图片和采用流程，但尚未接入正式模型：

- `config/ai_v2/prompts/registry.json` 的三份 Prompt 仍为 `candidate`、`caller=null`。
- `create_application()` 默认构造 `CandidateTextModel` 和 `CandidateImageModel`。
- 只有进程环境显式设置 `CREATIVE_STUDIO_AI_V2_LIVE=1` 才构造 gateway adapters。
- 页面显示的“候选展示方案 1/2/3”和 1x1 图片是本地占位结果，不是模型输出。
- 当前 release gate 只接受 candidate registry，不能作为 production 发布门禁。

用户已明确要求开始正式版接入流程。这表示可以开始设计、修复门禁和准备受控验收；不等于已经批准 Prompt、真实外部请求、真实数据写入、默认 live、内网或公网发布。每个高风险动作仍需按本文检查点单独确认。

## 本阶段目标

把当前本机正式入口 `/` 从“默认静默返回候选结果”改为可审计、可回滚的真实 AI v2 运行模式：

1. 正式入口不会把 fake/candidate 内容伪装成真实结果。
2. 文字和图片只通过 `creative_studio.ai_v2` 与本项目 `chat2api` 网关调用。
3. 三份已审批 Prompt 各有唯一 production caller，registry、运行时和 release gate 一致。
4. 失败向用户显示稳定、可操作的错误类别和 trace id，不再只有“请求失败”。
5. 真实文字与图片先在临时数据上受控验收，再决定是否切换本机正式运行数据。
6. 禁用 live 并重启即可停止新的真实调用；数据库和 artifact 不做破坏性回滚。

## 非目标

- 不恢复任何已删除的旧 AI 模块、Prompt、路由、表写入、fallback 或双写/双读。
- 不清理已有数据库中的旧 AI 历史表和记录。
- 不在本阶段开放局域网、公网、HTTPS、系统服务或多人部署。
- 不修改或提交 `chat2api/.env`、令牌、Cookie、代理密码或真实模型响应。
- 不把 deterministic contract 通过表述为真实模型质量通过。
- 不把独立 `/ai-v2/` 页面切换为正式入口；正式用户流程继续使用根页面 `/`。

## 接手基线

- 仓库：`D:\code\ai_creative_studio`
- 分支：`codex/tag-accordion-prototype`
- AI v2 主页面 checkpoint：`c80330d`
- 旧 AI 清理提交：`1bb6dd1`
- 旧 AI 可执行源码、旧 Prompt、v1 eval 和对应测试已删除。
- 全量测试基线：173 项通过；AI v2：100 项通过；v2 release gate：100 项通过。
- Node 语法、Python compileall、AI v2 boundary 和 `git diff --check` 均通过。
- 真实 AI 质量、正式 caller、默认 live 和生产发布仍未通过门禁。

开始修改前按顺序完整阅读：

1. `AGENTS.md`
2. `progress.md`
3. `docs/project-rules/项目代码地图.md`
4. `docs/project-rules/operations.md`
5. `docs/project-rules/CODE_STYLE.md`
6. `docs/ai/README.md`
7. `docs/ai/ai-v2-prompt-approval.md`
8. `docs/ai/quality-evaluation.md`
9. `docs/adr/0005-ai-v2-boundary-and-session-policy.md`
10. `docs/release/runbook.md`
11. 本 handoff

事实快照：

```powershell
Set-Location D:\code\ai_creative_studio
git status --short --branch
git log --oneline -5
rg -n "CREATIVE_STUDIO_AI_V2_LIVE|CandidateTextModel|CandidateImageModel|lifecycle|caller|error_code" src static config tests docs/ai
```

保留接手时已有改动；不使用 `reset`、`checkout` 或批量覆盖命令。

## 已确认的正式接入阻断项

### 1. 正式入口会静默使用 candidate

`src/creative_studio/app.py` 在 live 未启用时构造 candidate models。这个默认值适合早期预览，
但正式入口会让用户误以为“候选展示方案”是真实 AI 输出。正式接入必须 fail closed：candidate
models 只允许由测试或显式开发组合根注入，正式启动未配置 live 时返回明确的“AI 尚未启用”错误，
不得生成占位方案或占位图片。

### 2. 主页面隐藏 v2 错误

`static/app.js` 的通用 `api()` 只读取 `payload.error`，而 v2 错误包络返回
`error_code`、`phase`、`retryable`、`trace_id` 和 `field_path`。因此真实错误会被压成“请求失败”。
独立 `static/ai-v2/app.js` 已有读取 `error_code` 的模式，可作为行为参考，但不要直接复制其页面。

2026-09-05 的只读诊断显示最近一次 v2 run 为 `success`，而页面仍出现“请求失败”；这说明
生成后的 history/project 刷新也可能触发同一个宽泛 catch。修复时必须分别标识生成请求、历史刷新
和项目刷新失败，不得把后置刷新失败误报为“生成失败”。

### 3. registry 与 release gate 只支持 candidate 证据

Prompt registry 已能校验：candidate 必须 `caller=null`，production 必须有 caller；但当前测试和
`build_candidate_contract_evidence()` 明确要求全部为 candidate。正式接入需要独立 production gate，
保留 candidate contract gate 作为离线评测，不可简单删除或放宽现有断言。

### 4. 网关可运行不代表正式 AI 已接入

网页 8775 和网关 8780 可以同时监听，但只要 web 进程没有显式 live 配置，应用仍使用 candidate。
正式门禁必须检查运行时 adapter 类型、Prompt caller 和健康状态，不能只检查端口。

## 执行顺序

### P0：建立变更卡、计划和干净基线

1. 新建正式接入变更卡，写明目标、非目标、真实调用预算、数据路径、审批点和回滚。
2. 写分步 implementation plan；前端错误、Prompt lifecycle、真实文字评测、真实图片评测和切换分别提交。
3. 在任何代码修改或真实请求前运行全量门禁。
4. 检查当前服务和工作树；代码变更前停止 8775/8780，避免旧进程掩盖结果。

完成标准：变更卡和计划可定位到具体文件/测试；基线命令有新鲜输出；真实请求仍为 0。

### P1：先修复可观察性与 candidate 误导

先写失败测试，再实现：

- 主页面识别 v2 `error_code`，映射为安全中文提示，并显示 trace id 供排查。
- 生成成功后的 history/project 刷新失败使用独立提示，保留已返回的生成结果。
- 正式 composition root 未启用 live 时返回稳定 `ai_not_enabled`，不返回 candidate 方案。
- candidate models 仅保留在测试 fake 或显式开发入口，不能由正式启动路径静默选择。
- 错误响应不得包含 Prompt、凭据、完整供应商响应、路径或堆栈。

至少覆盖：live 未启用、v2 输入错误、批次冲突、网关不可达、生成成功但 history 刷新失败。

完成标准：根页面不再出现无法定位的“请求失败”；正式入口不再产生“候选展示方案”；全量门禁通过。

### P2：Prompt 审批与 production caller

1. 以 `docs/ai/ai-v2-prompt-approval.md` 为审批输入，分别评审叙事、静态和轮播 Prompt。
2. 用户结论必须是“允许进入受控真实评测”“需修改后再评”或“不批准”。
3. 获准后更新模板、hash、lifecycle 和 caller；caller 必须指向当前 v2 唯一用例入口。
4. 新增 production registry 测试，证明每个 Prompt 恰好一个 caller，caller 确实可从 composition root 到达。
5. 保留 candidate evidence builder；新增独立 production readiness gate，禁止用同一报告混淆两种证据。

Prompt 文本、schema 或 caller 的任何变化都需要定向测试、hash 更新和评测报告；不得只改 JSON 标签。

完成标准：三份 Prompt 的审批结论有记录；registry/hash/schema/caller 一致；production gate 能拒绝 candidate 或无 caller 状态。

### P3：受控真实文字评测

执行真实请求前再次向用户确认：使用的脱敏样例、最大调用次数、预计成本、输出位置和停止条件。

- 使用临时 SQLite、临时图片/上传目录和独立输出目录。
- 先检查 8780 `/v1/models`、认证与代理出口，不打印令牌、Cookie 或完整代理 URL。
- 叙事、静态、轮播分别运行固定脱敏矩阵；每个 case 最多一次文字模型调用。
- 记录 schema 通过率、失败分类、延迟、调用数、质量人工审查和 trace id。
- 结构错误直接失败；不增加隐藏修复调用或旧 AI fallback。
- 原始模型响应若需保留，放在被忽略的受控目录并脱敏；不得提交真实内容。

完成标准：三类用例均有真实证据；硬约束通过；质量问题和未通过项如实记录；仓库真实运行数据无变化。

### P4：受控真实图片与会话验收

在用户批准图片调用预算后执行：

1. 静态方案只点击一个方案，验证只创建一个图片 session/attempt/artifact。
2. 轮播使用最小两帧样例，验证两帧共享同一图片 session，第二帧复用 cursor 和上一帧 artifact。
3. 注入或等待一个明确终态失败，验证先对账、同一 session 内递增 attempt。
4. 对超时、断开、5xx 和 unknown 验证不创建第二 session 或盲目 attempt。
5. 验证 MIME、图片 URL、刷新恢复和公开 DTO 隐私边界。

完成标准：会话数量和状态迁移符合 ADR-0005；没有预取、重复会话、私有字段泄露或真实目录写入。

### P5：本机正式切换

只有 P1-P4 全部通过并获得用户明确切换批准后执行：

1. 停止网页与网关。
2. 对真实数据库、图片和上传目录执行备份，并在新目录完成 restore smoke；要求
   `verified=true`、`references_verified=true`。
3. 由启动器向 web 子进程显式传递正式 live 模式；不要依赖未知的全局 shell 状态。
4. 启动单实例，确认运行时 adapter、registry lifecycle/caller 和健康检查为 production。
5. 在用户指定项目执行一批文字和一次按需图片 smoke，记录调用数、延迟、错误和 trace id。
6. 在 `1280x720`、`390x844` 检查根页面、错误反馈、图片按钮、控制台和横向溢出。
7. 观察期内不开放局域网/公网，不修改认证、权限或历史数据。

完成标准：根页面产生真实、schema-valid 的结果；不存在“候选展示方案”或 1x1 candidate 图片；重启后模式不漂移；回滚演练通过。

## 回滚

- 立即停止真实调用：关闭 live 配置并重启 web 进程；网关可单独停止。
- 代码回滚：按 P1-P5 的独立提交使用 `git revert`，不覆盖运行数据。
- Prompt 回滚：恢复上一份已审批 production 模板、registry hash 和 caller；再次运行 production gate。
- 数据回滚：默认保留新增的 `ai_v2_*` run/session/attempt/artifact 供审计，不删除表或图片。
- 如果必须恢复数据，只使用发布前已验证备份恢复到新目录，经人工确认后切换；不得原地覆盖。

出现以下任一情况立即停止切换：真实响应泄密、旧 AI 引用恢复、双写/双读、图片重复会话、
调用数超预算、schema 连续失败、无法确认代理出口、备份或恢复校验失败。

## 每轮门禁

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

当 registry 进入 production 后，现有 candidate release gate 预期需要由“candidate contract gate +
production readiness gate”取代；必须在计划中先定义两个命令及各自证据，不能为了让旧命令变绿而
删除 candidate 证据。

## 交接验收清单

- [ ] 已记录接手时的分支、HEAD、工作树和运行进程。
- [ ] 已建立正式接入变更卡与 implementation plan。
- [ ] P1 已先解决错误可观察性和 candidate 静默回退。
- [ ] 三份 Prompt 分别取得明确审批结论。
- [ ] production registry 中每份 Prompt 有且仅有一个真实 caller。
- [ ] 真实文字和图片请求均有单独预算授权、脱敏输入和临时数据边界。
- [ ] production gate 与 candidate contract gate 都有新鲜输出。
- [ ] 正式切换前备份和 restore smoke 均通过。
- [ ] 根页面不显示 candidate 内容，错误信息可定位且不泄密。
- [ ] 未开放局域网或公网，未恢复旧 AI，未修改或提交秘密。

## 给下一会话的首条任务

读取本 handoff 和必读文档，先完成 P0，并为 P1 写失败测试与实施计划。不要先设置
`CREATIVE_STUDIO_AI_V2_LIVE=1`，不要先调用真实 AI；先让正式入口在非 live 状态下明确失败，
并让主页面正确显示 v2 错误。
