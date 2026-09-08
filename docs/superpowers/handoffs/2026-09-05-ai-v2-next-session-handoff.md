# AI v2 下一会话交接：Prompt 审批、轮播语义与受控上线

> 交给下一执行会话的工作文档。本文记录当前真实代码、用户已提出的轮播语义问题和下一阶段门禁。不授权真实模型调用、Prompt production caller 或正式发布。

## 先看结论

代码侧 P1 已完成并通过验证：

- 正式 composition root 在没有 CREATIVE_STUDIO_AI_V2_LIVE=1 且没有显式注入测试文字模型时 fail-closed，返回 ai_not_enabled。
- 根页面会解析 v2 error_code、phase、retryable、trace_id 和 field_path，并把生成失败与 history/project 刷新失败分开提示。
- 全量 unittest 176 项通过；AI v2 unittest 103 项通过；release gate、Node 语法、compileall、boundary 和 git diff --check 均通过。
- release evidence 仍是 deterministic_fake、contract_only、real_model_quality=not-run。
- 三份 Prompt 仍为 candidate，caller=null；没有 production caller。

当前最重要的未决事项不是代码实现，而是产品语义确认：

> 展示类轮播当前直接走 carousel Prompt，不会先走 static Prompt。需要用户确认是否保持这一逻辑，还是改成“static 先行、必要时再 carousel”的两阶段流程。

## 接手事实快照

- 仓库：D:\code\ai_creative_studio
- 分支：codex/tag-accordion-prototype
- HEAD：1bb6dd1 chore: remove retired ai implementation
- 当前工作树有代码侧 P1 未提交修改，必须保留，不要使用 reset、checkout 或批量覆盖命令。
- 当前服务端口 8775、8780 应保持关闭。
- 当前未设置 live，未修改 chat2api/.env，未向真实数据库、图片或上传目录写入新的验收数据。

有意修改的主要文件：

~~~text
progress.md
src/creative_studio/app.py
static/app.js
tests/test_ai_v2_app_integration.py
tests/test_ai_v2_frontend_contract.py
tests/test_ai_v2_gateway_runtime.py
.scratch/ai-v2-production-integration/spec.md
docs/superpowers/plans/2026-09-05-ai-v2-production-integration.md
docs/superpowers/handoffs/2026-09-05-ai-v2-production-integration-handoff.md
~~~

## 当前展示类轮播逻辑

代码入口：

- src/creative_studio/ai_v2/input_contract.py:98：展示类且 visual_carousel 选择“是”时返回 carousel，否则返回 static。
- src/creative_studio/ai_v2/application.py:166：根据唯一 use_case 选择一个文字用例，不会串行调用两个文字 Prompt。
- src/creative_studio/ai_v2/carousel_visual.py:72：轮播生成阶段只调用一次 creative.ai_v2.carousel 文字 Prompt，返回 3 套方案和逐帧私有图片指令。
- src/creative_studio/ai_v2/carousel_visual.py:136：图片按用户点击推进；第 1 帧创建 session，后续帧复用同一 session、cursor 和上一帧 artifact。

当前调用顺序：

~~~text
展示类 + visual_carousel=是
  -> carousel 文字 Prompt（一次）
  -> 返回 3 套轮播方案
  -> 用户点击第 1 帧
  -> 图片 session 首帧
  -> 用户继续点击
  -> 同一图片 session 继续生成后续帧
~~~

### 产品决策门：必须先确认

完成接手第 0 步和 P0 回归门禁后，向用户确认以下二选一：

1. 保持当前逻辑：展示类轮播只调用 carousel 文字 Prompt；静态 Prompt 只用于非轮播展示类项目。
2. 改为两阶段逻辑：先调用 static Prompt（是否还要先生成静态基准图也需明确），再调用 carousel Prompt。

若用户选择两阶段，不能只调整调用顺序。必须重新设计并评审两次文字调用的预算和幂等键、static 输出如何传入 carousel、中间状态与失败恢复、Prompt contract、registry、release evidence、production gate，以及前端是否展示中间结果。

在用户确认前，不要修改这条调用链。

## 下一步执行顺序

### 接手第 0 步：读取与保存状态

先读取 AGENTS.md、progress.md、本 handoff、production integration plan、operations、AI 文档和相关 ADR；然后保存 git status --short --branch，并确认 8775/8780 没有监听、live 没有被设置。不要先改代码、Prompt 或启动服务。

### P0：接手回归门禁

先运行，不要先启用 live：

~~~powershell
Set-Location D:\code\ai_creative_studio
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -q
python -m unittest discover -s tests -p "test_ai_v2_*.py" -q
node --check static\app.js
node --check static\ai-v2\app.js
python -m compileall -q src chat2api
python -m creative_studio.ai_v2.release_gate
python -c "from pathlib import Path; from creative_studio.ai_v2.boundary import assert_ai_v2_boundary; assert_ai_v2_boundary(Path('.'))"
git diff --check
~~~

完成标准：保存命令输出；若失败，先修复或报告，不跳到 Prompt 或真实评测。

### P1-产品：确认轮播产品语义

向用户展示当前逻辑和上面的两种方案，取得用户本人或指定审批人的明确结论。结论记录在 progress 条目或新的变更卡中。

完成标准：有明确的“保持当前逻辑”或“两阶段逻辑”结论；没有把推测当成需求。

### P2：Prompt 审批

审批材料：docs/ai/ai-v2-prompt-approval.md。

三份 Prompt：

- config/ai_v2/prompts/narrative-text-v1.txt
- config/ai_v2/prompts/static-text-v1.txt
- config/ai_v2/prompts/carousel-text-v1.txt

每份必须取得用户本人或指定审批人的以下三种结论之一：

- 允许进入受控真实评测；
- 需修改后再评；
- 不批准。

中文审阅稿只在对话中展示过，未写回生产 Prompt。任何 Prompt 文本、schema 或 caller 变化都必须同步 hash、定向测试和评测记录。

完成标准：三份 Prompt 都有独立结论；批准进入真实评测不等于批准 production caller 或正式发布。

若产品语义保持当前的 carousel-only 路径，carousel Prompt 的批准是进入 carousel 真实文字评测的必要条件；static 和 narrative Prompt 的批准仍应单独记录，但不应被默认为 carousel 评测的隐式 production 批准。若产品语义改为两阶段，static 与 carousel 两份 Prompt 都是该链路的前置审批。

### P3：独立 production readiness gate

保留现有 candidate contract gate，不要放宽或删除。新增独立 gate，至少检查：

- registry lifecycle 为 production；
- 每个 Prompt 恰好一个 caller；
- caller 能从正式 composition root 到达对应 use case；
- caller、Prompt id、schema、hash 和最大调用次数一致；
- candidate evidence 不被伪装成 production evidence。

只有 P2 明确批准且用户要求进入 production caller 设计后，才修改 registry 或新增 production gate。

### P4：受控真实文字评测

执行前必须再次向用户确认脱敏样例、最大调用次数和总预算、预计成本、输出目录、停止条件。文字评测授权只能覆盖明确列出的 use case 和模型调用，不自动授权图片调用或正式入口 live。

评测必须使用临时 SQLite、临时图片/上传目录和独立输出目录。不得读取或写入仓库真实 data/，不得修改 chat2api/.env，不得保留 token、Cookie、完整供应商响应或私有 Prompt。

完成标准：叙事、静态、轮播分别有真实证据；记录 schema 通过率、失败分类、延迟、调用数、人工质量审查和 trace id；不把结果描述成生产通过，除非后续 gate 明确允许。

### P5：受控真实图片与会话验收

在用户或指定审批人明确批准图片评测的 use case、最大调用次数、总预算、预计成本、输出目录和停止条件后验证：

1. 静态方案单击一次只创建一个图片 session/attempt/artifact。
2. 轮播最小两帧共享一个图片 session；后续帧复用 cursor 和上一帧 artifact。
3. 明确终态失败后，在同一 session 内递增 attempt。
4. timeout、断开、5xx、unknown 先对账，不创建第二 session 或盲目重试。
5. 校验 MIME、图片 URL、刷新恢复和公开 DTO 隐私边界。

### P6：本机正式切换

只有 P1-P5 全部通过并取得明确切换批准后执行：备份与 restore smoke、显式 live opt-in、单实例启动、production registry/caller/health 检查、指定项目 smoke、桌面/移动端验收和回滚演练。

## 硬性约束

- 真实评测默认使用隔离 harness 和显式注入的 gateway/fake，不设置 CREATIVE_STUDIO_AI_V2_LIVE=1。
- 只有用户明确批准具体阶段、入口、模型/供应商、最大调用次数、预算和停止条件后，才允许设置 CREATIVE_STUDIO_AI_V2_LIVE=1；该开关会同时构造文字和图片 gateway，不能把它理解为只打开文字评测。
- 不调用真实文字/图片 AI，除非已记录脱敏样例、预算、输出位置和停止条件。
- 不修改 chat2api/.env、token、Cookie、代理密码或真实模型响应。
- 不写入真实 data/、图片或上传目录；测试使用临时目录。
- 不恢复旧 AI、旧路由、旧表、fallback、双写或双读。
- 不把 deterministic fake、临时代理结果或 contract gate 描述为生产质量通过。
- 不提交当前工作树，除非用户明确要求提交；不覆盖用户已有修改。

## 当前验证证据

- 全量 unittest：176 项通过。
- AI v2 unittest：103 项通过。
- release gate：v2-contract: ok、compileall: ok、node: ok、diff-check: ok、boundary: ok。
- release evidence：30 个 deterministic case；其中 29 个有可自动判定的 contract outcome，均通过；23 个成功公开 DTO 的私有字段扫描结果为 0；7 个故意坏输出归类为 model_output_invalid。这些指标来自不同检查维度，不能用 29+23+7 推导总 case 数；真实模型质量 not-run。
- 当前分支没有新的提交；代码侧 P1 代码和文档保留在工作树中供审阅。

## 交接完成清单

- [ ] 新会话已先读取 AGENTS.md、progress.md、本 handoff、production integration plan、operations、AI 文档和相关 ADR。
- [ ] 接手者已保存 git status --short --branch，没有覆盖既有修改。
- [ ] P0 回归门禁有新鲜输出。
- [ ] 用户已确认展示类轮播采用单阶段还是两阶段语义。
- [ ] 三份 Prompt 各自取得审批结论。
- [ ] candidate contract gate 与 production readiness gate 分离。
- [ ] 真实文字和图片评测均有独立预算、脱敏输入、临时数据边界和停止条件。
- [ ] 正式切换前完成备份、恢复 smoke 和回滚演练。
