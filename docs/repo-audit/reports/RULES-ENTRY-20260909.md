# 规则与入口整理专项：核心入口单元

## 当前状态

- 状态：核心入口与支持文档单元均已完成；专项待新会话做一次独立读者接手复核。
- 本轮单元：`docs/project-rules/CODE_STYLE.md`、`docs/project-rules/CONTEXT.md`、`docs/project-rules/operations.md`、`docs/project-rules/项目代码地图.md` 的职责一致性。
- 本专项计划：[`docs/superpowers/plans/2026-09-09-rules-entry-core.md`](../../superpowers/plans/2026-09-09-rules-entry-core.md)
- 本报告不是 T01-T08 的替代报告；旧审计状态保持 `complete_with_limits`。

## 基线、保护范围与目标

- 仓库：`D:/code/ai_creative_studio`。
- 当前 HEAD：`be89f8a5ec7d8103c83ad86bf49dbb95971ff70a`。
- 工作树已有 T05/T06 文档差异、用户对 `progress.md` 的整理、未跟踪的审计目录/任务包和压缩包；本轮未 reset、stash、删除或覆盖这些既有改动。
- 本轮未修改 `src/`、`chat2api/`、`config/`、`static/`、`tests/`、部署配置、Prompt 或 registry。
- 目标是让普通任务按风险和领域找到第一份必要资料，避免把历史时间线、完整总纲和所有运行手册变成默认全量阅读；同时修正进度摘要中与当前 `master` 不符的状态。

## 实际阅读与核对

- 项目规则：`AGENTS.md`、`docs/project-rules/CODE_STYLE.md`。
- 核心入口：`README.md`、`docs/current-state.md`、`docs/project-rules/CONTEXT.md`。
- 相关职责边界：`docs/project-rules/operations.md`、`docs/project-rules/项目代码地图.md`、`docs/ai-rebuild-master-plan.md`。
- 审计证据：`docs/repo-audit/STATE.md`、`QUEUE.csv`、`findings.csv`、T05-001/T06-001/T07-001/T08-001 报告。
- 进度摘要：`progress.md`；本轮按用户明确授权处理它，但没有恢复被此前整理移除的逐日流水账。

## 规则处置表

| 旧出处或规则组 | 问题与依据 | 本轮处置及新位置 | 含义/范围/例外 | 核对结果 |
|---|---|---|---|---|
| `AGENTS.md` 顶部默认按固定顺序阅读 `progress.md`、代码地图、operations、AI 总纲和研究资料 | 当前事实已由 `docs/current-state.md` 承接；固定顺序把历史资料和与任务无关的资料变成常驻成本 | 改为按任务路由：日常代码、AI v2、文档/规则、启动/部署、历史回顾分别给出第一入口和补充资料 | 保留“先读根规则”、AI/部署高风险门禁和按需读取研究资料；未撤销任何安全或验证要求 | 目标文件链接检查通过；路由与当前文件职责一致 |
| `AGENTS.md` 对 `progress.md` 的描述 | 原文同时称追加式时间线和当前读取入口，容易与当前事实索引混淆 | 明确为简洁历史/维护指针，不是当前架构事实；历史回顾按需读取 | 不禁止维护 `progress.md`；当前事实仍须回到源码、registry、本文档和定向验证 | `progress.md` 已改为入口性质并回链 `docs/current-state.md` |
| `docs/current-state.md` 只有资料清单，没有按任务分流 | T08 已证明该索引是当前事实入口，但普通开发仍需自行判断下一份资料 | 新增“按任务选择入口”表，说明第一入口、继续读取和不默认读取 | 不新增第二份状态表；历史 handoff/审计报告只在追溯时使用 | 相对链接检查通过；T08 的 registry/live/历史分层语义保留 |
| `README.md` 只有使用说明和零散开发验证命令 | 用户和开发者需要从 README 判断当前事实、规则、运维和历史资料的起点 | 新增“阅读入口”段，并补 `git diff --check` 到现有最小检查命令 | 不把 README 变成完整规则或审计报告；原启动、账号和代理说明保留 | 相对链接检查通过 |
| `progress.md` 的当前摘要 | 原摘要将 `6f18b62`、T02-003、production gate 通过和公网入口写成当前事实；与当前 HEAD `be89f8a`、T08 complete_with_limits 和 F-006 阻塞冲突 | 修正为当前工作树和历史发布快照分层，登记 T01-T08 完成、F-003/F-004/F-005/F-006 deferred，并追加本专项记录 | 保留历史发布测试数字，但明确“不代表当前工作树”；不把 registry `production` 声明解释成运行就绪 | 旧 HEAD、旧 T02 下一任务和误报 gate 表述扫描为 0 |

## 接手场景：改前问题与改后答案

1. **普通文档任务：只修改 README 的一处使用说明，需要读什么？**
   - 改后：先读 `AGENTS.md` 的文档/规则路由、`docs/current-state.md` 和 README 目标段；只有涉及启动/数据事实时补读 `docs/project-rules/operations.md`。无需默认通读 `progress.md` 或全部历史报告。
2. **功能定位：轮播后续帧一直生成中，先查哪里？**
   - 改后：从 `AGENTS.md` 的 AI v2 路由和 `docs/current-state.md` 的 registry/runtime 边界开始，再读 `src/creative_studio/ai_v2/carousel_visual.py`、对应 store/worker、公开 DTO 与相关测试；设计或迁移意图才进入总纲/ADR。仅定位不等于授权修复。
3. **当前事实：GUI 启动、直接运行应用和测试注入如何区分？**
   - 改后：当前索引说明直接 `create_application()` 未显式 live 且未注入测试模型时应 fail-closed；`launcher.py` 注入 live 是实现路径，不是审批、发布或真实质量证明；registry hash mismatch 时保持 blocked。
4. **规则边界：改变 AI 输入或公开字段时怎样找约束？**
   - 改后：先看 `AGENTS.md` 的 AI 功能/迁移治理和 `docs/project-rules/CODE_STYLE.md` 的 API 数据边界，再核对当前 schema、validator、mapper、DTO、caller 和测试；总纲/ADR只用于目标和迁移依据，不替代当前实现证据。
5. **日常维护：只改一项启动命令或局部实现，更新什么？**
   - 改后：按 `docs/current-state.md` 的维护触发条件更新受影响的 operations、deployment 或 AI 资料；只有 registry/caller/schema/审批/验证等边界变化才刷新当前索引，`progress.md` 只记简短维护指针，不复制整张事实表。

## 定向检查

- `git diff --check -- AGENTS.md README.md docs/current-state.md progress.md docs/superpowers/plans/2026-09-09-rules-entry-core.md`：退出 0；Git 仅报告既有 CRLF 转换提示。
- 对 `AGENTS.md`、`README.md`、`docs/current-state.md`、`progress.md` 的 Markdown 相对链接检查：4 个文件，缺失链接 0。
- 当前事实核对：HEAD 为 `be89f8a5ec7d8103c83ad86bf49dbb95971ff70a`；当前索引保留 static/carousel hash mismatch 和 `complete_with_limits`；进度摘要不再包含旧 `6f18b62`、旧 T02-003 下一任务或无条件 production gate 通过表述。
- 路径范围核对：本轮业务源码/配置/测试差异 0；未执行 T01-T08、全量 unittest、真实 AI/图片、浏览器、部署或服务器写操作。

## 支持文档单元：规则处置与实际修改

| 文档 | 现场问题 | 本轮处置 | 保留的职责与限制 |
|---|---|---|---|
| `docs/project-rules/CODE_STYLE.md` | 顶部混入高风险授权和当前状态语义；“当前最小检查”容易被理解为所有文档任务都要跑全量代码检查；收尾要求与根规则重复 | 明确只维护代码边界、命名、实现风格和按风险选择检查；把高风险/入口/收尾回链 `AGENTS.md`，把当前事实回链 `docs/current-state.md`；补充文档-only 检查边界 | 代码风险对应的测试、语法、编译、前端和秘密处理要求保留；没有降低代码修改的验证门槛 |
| `docs/project-rules/CONTEXT.md` | 只有账号/权限词汇，未说明职责；run、scheme、image session、attempt、frame 等当前链路词汇需要跨文档重复解释 | 增加“只定义稳定词汇”的职责声明和入口链接；补充最小领域词汇 | 不记录当前端口、版本、审批、任务状态或历史结论，避免成为第二份状态文档 |
| `docs/project-rules/operations.md` | loopback/公网门禁重复；启动段重复维护 Prompt lifecycle/hash；验证段没有区分代码变更与纯文档变更 | 合并 loopback 门禁；启动前回链当前索引，由 `current-state` 维护动态 registry/hash/审批；明确只有代码/Prompt/schema/registry/运行配置变化才执行本节全量验证 | 保留启动、停止、数据路径、备份恢复、AI 运行边界、故障处理和升级门禁；不授权 live、生产发布或服务器写入 |
| `docs/project-rules/项目代码地图.md` | `progress.md` 和 Prompt 目录仍用旧职责/候选措辞；修改导航没有规则、代码规范和运维入口；动态缺口在地图中重复维护 | 增加职责声明和当前索引；修正目录树与 Prompt 目录说明；在修改导航加入规则/代码规范/运维三类入口；将动态缺口回链 `docs/current-state.md` | 保留真实入口、调用链、API、数据表和代码修改导航；历史 candidate/production 记录仍只作来源，不作当前证据 |

## 支持文档单元：接手场景

1. **修改 Python/前端代码时先看什么？**
   - 从 `AGENTS.md` 的日常代码路由和 `docs/current-state.md` 的相关事实开始，再看 `docs/project-rules/项目代码地图.md` 的目标调用链和 `docs/project-rules/CODE_STYLE.md` 的代码约定；只有触及启动、数据或备份时才读 `docs/project-rules/operations.md`。
2. **只想执行一次备份 dry-run 时先看什么？**
   - 先看 `docs/current-state.md` 的当前数据/部署边界，再看 `docs/project-rules/operations.md` 的备份命令和恢复约束；代码地图只用于定位 `backup.py`，不需要通读代码规范。
3. **要修改 AI 输入或公开字段时如何分流？**
   - 先看 `AGENTS.md` 的 AI 迁移治理和 `docs/current-state.md` 的 registry/runtime 状态，再从代码地图定位 schema、use case、projection 和 caller，最后按 `docs/project-rules/CODE_STYLE.md` 补测试、兼容和回滚说明。
4. **看到一个不熟悉的 `scheme` 或 `image attempt` 术语时看哪里？**
   - 看 `docs/project-rules/CONTEXT.md` 的稳定词汇定义；不要从 `progress.md` 或历史 handoff 推断当前领域含义。
5. **运行命令或故障排查应该修改哪份资料？**
   - 修改启动、数据、备份和故障步骤时改 `docs/project-rules/operations.md`；若端口、registry、审批、部署 ref 或验证结论变化，再按 `docs/current-state.md` 的触发条件更新当前索引。

## 支持文档单元：定向验证

- 对 `docs/project-rules/CODE_STYLE.md`、`docs/project-rules/CONTEXT.md`、`docs/project-rules/operations.md`、`docs/project-rules/项目代码地图.md` 做相对链接检查：4 个文件，缺失链接 0。
- `git diff --check -- docs/project-rules/CODE_STYLE.md docs/project-rules/CONTEXT.md docs/project-rules/operations.md docs/project-rules/项目代码地图.md docs/superpowers/plans/2026-09-09-rules-entry-core.md`：退出 0；仅有既存 CRLF 转换提示。
- 关键过时运行表述扫描：`candidate`/`caller=null` 启动描述、旧 T02 下一任务、旧“追加式历史时间线”残留为 0；代码地图树中的 `docs/current-state.md` 路径已修正为 `docs/` 目录职责。
- 必要文件检查：8 个入口/报告文件存在；当前 HEAD 仍为 `be89f8a5ec7d8103c83ad86bf49dbb95971ff70a`；源码、配置、静态资源和测试目录差异 0。
- 未执行 T01-T08、全量代码测试、真实 AI/图片、浏览器、部署或服务器写操作；这些限制与旧审计结论保持不变。

## 未完成与下一步

- `docs/ai-rebuild-master-plan.md` 只做了定向阅读，尚未重写其历史阶段和日常入口；下一范围如需处理必须单独限定到导航/适用范围，不重写全部阶段。
- 文档修改已完成，但尚未进行真正新会话的独立读者复核；下一会话只读取本报告的场景问题清单，从当前文件独立回答后再比较本报告答案。
- F-003/F-004/F-005/F-006、审批、live、部署、真实质量和移动端验证仍按现有审计记录保留，文档整理不把它们标记为 resolved。

## 交接入口

下一会话读取本报告顶部状态和“未完成与下一步”，只做独立读者接手复核；不要重启旧审计、重写已完成文档或修改程序。复核通过后再决定是否需要为 `docs/ai-rebuild-master-plan.md` 建立单独的导航修订单元。
