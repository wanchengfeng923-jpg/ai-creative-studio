# AI v2 主页面接入后续交接

> 交给下一执行会话的工作文档。本文记录当前真实代码和验证边界，不代替 `AGENTS.md`、`progress.md`、`docs/operations.md` 或 AI v2 正式实施计划。

## 先看结论

当前主页面已经保留原有工作台结构，并在同一页面的结果区域接入 AI v2 的按需图片交互。下一位执行者不应再把用户引导到独立 `/ai-v2/` 页面，也不应把“页面能显示 deterministic 结果”表述为 Prompt 已上线。

当前真正剩余的工作按优先级是：

1. 重新执行全量门禁，确认接手后的工作树仍可运行。
2. 对主页面做一次可重复的浏览器验收，重点证明“只点击一张图，只推进一个图片会话”。
3. 完成候选 Prompt 的离线评测和审批材料；在审批完成前，不得把 `caller` 改成 production，也不得默认连接真实网关。
4. 在独立变更中决定是否清理隔离用的 `static/ai-v2/` 页面；它当前不是正式入口，不能借清理之名改动主页面流程。
5. 只有在审批、评测和观察周期都满足后，才讨论正式 live caller、真实供应商验收和入口发布。

## 必读顺序

开始任何修改前完整阅读：

1. `AGENTS.md`
2. `progress.md`
3. `项目代码地图.md`
4. `docs/operations.md`
5. `docs/ai-rebuild-master-plan.md`
6. `CODE_STYLE.md`
7. `CONTEXT.md`
8. `docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`
9. `docs/superpowers/plans/2026-09-04-ai-v2-text-first-implementation.md`
10. 相关 ADR、测试和本 handoff，至少包括：
    - `docs/adr/0001-public-result-projection.md`
    - `docs/adr/0003-carousel-v1-background-operation.md`
    - `docs/adr/0005-ai-v2-boundary-and-session-policy.md`
    - `tests/test_ai_v2_app_integration.py`
    - `tests/test_ai_v2_gateway_runtime.py`

然后执行事实快照：

```powershell
Set-Location D:\\code\\ai_creative_studio
git status --short --branch
git log --oneline -8
rg -n "CREATIVE_STUDIO_AI_V2_LIVE|caller|/api/v2|生成参考图|重试参考图|LegacyCreativeGenerationAdapter|complete_visual_generation" src static tests config docs --glob '!docs/superpowers/handoffs/*'
```

不要使用 `reset`、`checkout`、批量删除或覆盖命令。工作树中已有的修改必须先记录并保留。

## 当前已完成事实

### 用户可见行为

- 正式入口仍是 `static/index.html` 对应的根页面 `/`。
- 顶部导航、项目侧栏、创意定位步骤条和结果区域保持现有结构。
- 文字方案生成后，结果区域显示三张方案卡；每张卡独立显示“生成参考图”。
- 只有用户点击某张卡片的按钮，才调用该方案的图片接口。
- 生成中只轮询被点击方案的 attempt；未点击方案不会预取、自动推进或后台发图请求。
- 成功后该卡片按钮锁定为完成态；明确失败后才显示“重试参考图”。
- 原有“采用方案”操作保留在当前页面。
- 独立 `/ai-v2/` 页面仍存在于 `static/ai-v2/`，但没有切换为根入口；它不是本次正式用户流程的一部分。

### v2 业务边界

- 业务输入严格为 `task_description`、`aspect_ratio`、`creative_tags`。
- 一批文字只创建一个文字会话；第二批使用新文字会话。
- 每个展示方案只创建一个图片会话；轮播方案所有帧共享该方案的图片会话。
- 每次点击最多推进一张图片；不预取、不自动推进后续帧。
- 图片重试前必须查询本地 attempt 和供应商会话。
- 供应商成功或仍在工作时复用原会话；只有明确终态失败才在原图片会话内创建新 attempt。
- 本地 attempt 缺失但图片会话存在时，先恢复孤儿任务。
- 浏览器公开 DTO 不包含 Prompt、execution、会话游标、gateway job id、本地路径、完整模型响应或堆栈。

### Prompt 和运行模式

- `config/ai_v2/prompts/registry.json` 中的三项 v2 Prompt 当前保持 `candidate`。
- `caller` 当前必须为 `null`；不得把候选 Prompt 伪装成 production caller。
- 默认组合根使用 deterministic candidate text/image models。
- 只有显式设置 `CREATIVE_STUDIO_AI_V2_LIVE=1` 才构造真实 gateway adapter；默认不会连接真实 AI。
- 候选 Prompt 尚未经过用户批准的 production 接入，不得修改 `chat2api/.env`，不得在无独立变更卡时发送真实请求。

## 当前有意修改的文件

以下文件属于当前工作树的有意修改，接手者不得回滚或覆盖：

```text
config/ai_v2/prompts/carousel-text-v1.txt
config/ai_v2/prompts/narrative-text-v1.txt
config/ai_v2/prompts/registry.json
config/ai_v2/prompts/static-text-v1.txt
progress.md
static/ai-v2/app.js
static/ai-v2/index.html
static/ai-v2/styles.css
static/app.js
static/styles.css
tests/test_ai_v2_frontend_contract.py
tests/test_ai_v2_prompt_registry.py
```

本次接入没有把根路由改成 `/ai-v2/`，也没有修改真实数据库、图片、上传文件或 `chat2api/.env`。

## 下一步执行顺序

### P0：接手后回归门禁

先运行，不要先改代码：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
python -m unittest discover -s tests -q
python -m unittest discover -s tests -p "test_ai_v2_*.py" -q
node --check static\\app.js
node --check static\\ai-v2\\app.js
python -m compileall -q src chat2api
python -m creative_studio.ai_v2.release_gate
git diff --check
```

如果失败，先定位并修复当前任务；不要跳过测试继续做 Prompt 或 UI 新功能。测试结果写入 `progress.md`，同时记录具体失败命令和环境原因。

### P1：主页面浏览器验收

使用临时 SQLite、临时图片目录和 deterministic candidate models 启动本地服务。仓库目前没有单独的“浏览器冒烟”命令；优先复用 `tests/test_ai_v2_app_integration.py` 的 `create_application(database_path=..., images_dir=..., uploads_dir=..., ai_v2_text_model=..., ai_v2_image_model=...)` 组合根，在临时目录上挂载本地 HTTP server。严禁让临时验收指向 `data/creative_studio.db`、`data/images/`、`data/uploads/` 或真实 gateway。

验收步骤：

1. 打开 `/`，确认仍是原工作台视觉壳，不自动跳转 `/ai-v2/`。
2. 登录并创建或选择项目。
3. 填写任务说明、画幅和标签，点击“生成方案”。
4. 确认结果仍出现在当前页面结果区，并显示三张方案卡。
5. 确认三张卡各自有“生成参考图”，且未点击前没有图片请求。
6. 只点击第一张卡，确认只有第一张卡进入生成态并最终完成。
7. 确认另外两张卡仍保持未开始状态，没有自动刷新、预取或图片会话。
8. 在受控 fake 失败场景验证重试：先对账原会话，只有明确终态失败才创建同一图片会话内的新 attempt。
9. 刷新页面，确认 history/status 仍能恢复公开状态；不出现 Prompt、execution、游标、gateway job id 或本地路径。
10. 验收结束后停止临时服务，清理临时目录，并确认真实数据目录无变化。

浏览器验收只能证明交互和接口契约；不能证明真实模型质量、真实网关稳定性或 Prompt 已获批准。

### P2：候选 Prompt 评测与审批包

允许做：

- 检查三份候选 Prompt 的 JSON 字段骨架、输入变量、registry hash 和 schema 对齐。
- 运行脱敏 deterministic 评测，记录 hard constraints、字段完整性、私有字段扫描、调用次数和失败分类。
- 生成供用户评审的候选 Prompt 文本、评测样例和报告。
- 更新 `docs/ai/quality-evaluation.md`、对应 ADR 或 progress 中的证据。

禁止做：

- 未经批准把 `caller=null` 改为 production caller。
- 未经批准设置 `CREATIVE_STUDIO_AI_V2_LIVE=1` 作为默认环境。
- 把 deterministic fake 或临时代理请求写成真实质量结论。
- 修改 `chat2api/.env`、令牌、代理配置或真实运行数据。

### P3：隔离页面清理决策

用户当前明确希望“所有页面和之前一样，点击生成后当前页面变动”，因此不要将独立 `/ai-v2/` 作为主流程。是否删除 `static/ai-v2/` 需要单独的小变更：

- 先确认没有测试、文档或内部验收依赖它；
- 先写失败/回归测试证明根页面不依赖它；
- 再做最小删除或改名，并同步代码地图与 handoff；
- 不要在同一变更里顺便改主页面布局或生产 caller。

如果没有明确清理收益，保留它作为隔离验收页面比贸然删除更安全。

### P4：正式 live 与发布（默认后置）

仅当以下条件全部满足后才进入：Prompt 已用户批准、脱敏评测通过、独立真实网关变更卡已记录、凭据/代理/回滚方案已确认、观察周期完成。该阶段才讨论：

- 设置 live opt-in；
- 受控真实文字/图片请求；
- 质量、成本、延迟和失败率记录；
- 正式入口切换或部署。

任何一步缺少审批，状态保持“候选/未发布”，不要用兼容分支绕过门禁。

## 验收标准

下一阶段完成时，至少应能回答：

- 根页面是否保留原有布局且无需跳转独立页面？
- 文字生成是否只创建一个文字会话？
- 是否严格做到每次点击只推进一张图片？
- 未点击方案是否没有图片请求、attempt 或供应商会话？
- 重试是否先对账并复用原图片会话？
- 浏览器公开响应是否通过私有字段递归扫描？
- Prompt 是否仍明确标记为 candidate，且没有 production caller？
- 全量测试、v2 测试、Node 语法、compileall、release gate、diff-check 是否都有命令输出？
- 真实 AI、真实图片、真实数据库、`chat2api/.env` 和正式入口切换是否明确记录为未做或已审批？

## 回滚方式

- 代码和文档回滚以独立 Git 提交为边界；不要用 Git 命令覆盖用户运行数据。
- 前端交互回滚只回滚 `static/app.js`、`static/styles.css` 及对应测试；保留 v2 后端状态机和数据库表，除非另有迁移计划。
- Prompt candidate 变更回滚 `config/ai_v2/prompts/*` 与 registry hash；不要修改真实运行库。
- 真实数据库、图片和上传文件不在本 handoff 的回滚范围内；任何写入必须先备份、单独审批并有恢复演练。
- 发现旧 AI 被重新引用、公开 DTO 泄露私有字段、后台预取图片或重试创建第二图片会话时，立即停止扩展，先恢复到最近通过门禁的代码提交并记录证据。

## 明确未验证 / 未授权内容

- 未把候选 Prompt 接入 production caller。
- 未以默认模式调用真实 AI 或真实图片供应商。
- 未修改 `chat2api/.env`、真实数据库、真实图片和上传文件。
- 未执行未经批准的正式入口切换、部署、公网或局域网开放。
- deterministic 测试通过不代表真实模型质量、供应商可用性、多人并发或生产成本已通过。

## 交接确认

- [ ] 接手者已先读取必读文档。
- [ ] 接手者已保存 `git status`，确认没有覆盖既有修改。
- [ ] P0 门禁已跑完并记录结果。
- [ ] P1 主页面浏览器验收使用临时数据和 deterministic fake。
- [ ] P2 Prompt 仍停在 candidate，审批材料与代码接线分离。
- [ ] 所有真实请求、真实数据写入和入口切换均有明确记录。
