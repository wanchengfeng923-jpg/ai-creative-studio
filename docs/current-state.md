# 当前事实索引

核验日期：2026-09-08
仓库：`D:/code/ai_creative_studio`
当前 Git 基线：`master` / `be89f8a5ec7d8103c83ad86bf49dbb95971ff70a`

本文档是当前事实的导航和分层索引，不替代源码、配置、测试输出或历史交接。历史文档保留原文和原始时间；当历史结论与本索引或当前文件冲突时，先按本索引列出的当前证据复核，不能把历史“通过”直接当作当前通过。

## 规则与资料入口

- 长期项目规则：`AGENTS.md`；代码改动规范：`docs/project-rules/CODE_STYLE.md`。
- 当前状态与审计交接：`docs/current-state.md`、`docs/repo-audit/STATE.md`、`docs/repo-audit/QUEUE.csv`。
- AI 实现事实：`src/creative_studio/ai_v2/`、`config/ai_v2/prompts/registry.json`；AI 迁移背景：`docs/ai-rebuild-master-plan.md`。
- 启动、数据和备份边界：`docs/project-rules/operations.md`；部署历史：`docs/deployment/`。
- 设计、决策和过程来源：`docs/adr/`、`docs/research/`、`docs/superpowers/specs/`、`docs/superpowers/plans/`、`docs/superpowers/handoffs/`。
- 进度指针：`progress.md`。它不替代本索引；只有需要追溯时间线或维护记录时才读取。

### 按任务选择入口

| 任务 | 第一入口 | 继续读取 | 不默认读取 |
|---|---|---|---|
| 日常代码/前端修改 | `AGENTS.md`、本索引、`docs/project-rules/项目代码地图.md` | `docs/project-rules/CODE_STYLE.md`；涉及启动/数据时读 `docs/project-rules/operations.md` | 全部历史 handoff、完整 `progress.md` |
| AI v2 用例或 Prompt | 本索引的 Registry 与运行就绪段 | 相关 `src/creative_studio/ai_v2/`、registry、schema、validator、caller、测试；设计/迁移时再读总纲和 ADR | 仅凭历史 gate 数字或审批文字下结论 |
| 启动/备份/部署 | 本索引、`docs/project-rules/operations.md` | 对应 `docs/deployment/` 记录和实际命令 | 与目标动作无关的源码和历史阶段 |
| 规则/文档整理 | `AGENTS.md`、本索引、目标文档 | 需要追溯时读审计报告、handoff、ADR 或研究笔记 | 把任务包或历史报告当作当前规则 |

## 当前可证实事实

### Registry 与运行就绪

当前 `config/ai_v2/prompts/registry.json` 声明三项 Prompt 为 `lifecycle=production`，并各绑定一个 v2 caller：

| id | 声明 caller | registry hash | 当前模板 hash | 可加载结论 |
|---|---|---|---|---|
| `creative.ai_v2.narrative` | `creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate` | `70b3aa...f0e4e` | `70b3aa...f0e4e` | hash 一致，但未因此证明真实质量或正式发布 |
| `creative.ai_v2.static` | `creative_studio.ai_v2.static_visual.StaticTextUseCase.generate` | `c820c9...51139b` | `fb2b09...d64e9` | hash 不一致；registry 加载失败 |
| `creative.ai_v2.carousel` | `creative_studio.ai_v2.carousel_visual.CarouselTextUseCase.generate` | `84c220...5fb08` | `a956e8...5af65d` | hash 不一致；registry 加载失败 |

hash 的完整值和复核来源见 `docs/repo-audit/reports/T05-001.md`、`docs/repo-audit/findings.csv`。使用项目 `.venv` 直接构造 `AiV2PromptRegistry` 的结果为 `AiV2PromptRegistryError: v2 prompt template hash mismatch`。因此当前不能把 registry 的 `production` 字段、任何 deterministic contract gate 或历史审批文字合并解释为“当前运行就绪”或“真实模型质量通过”。

直接调用 `create_application()` 在未显式注入测试模型且未设置 `CREATIVE_STUDIO_AI_V2_LIVE=1` 时仍应 fail-closed；`launcher.py` 注入 live 是实现路径，不是审批或正式发布证明。相关长期约束在 `AGENTS.md` 的“AI 迁移治理”和“启动器与 live 边界”。

### Git 与部署基线

- 当前审计工作树在 `master`，HEAD 为 `be89f8a5...`；`progress.md` 已有用户改动，审计目录和任务包为未跟踪材料，均保留。
- `production-baseline-20260908` tag 解析到 `b28c562b...`，`codex/tag-accordion-prototype` 指向 `ef83cd8...`；它们不是当前 `master` HEAD。`docs/deployment/code-baseline-20260908.md` 的 tag、聚合 hash 和测试结论属于对应历史快照，发布前必须对实际待发布 ref 重新验收。
- `docs/deployment/live-deployment.md` 是实时部署过程记录，包含未开始、进行中、已上传和历史验证等多个时间点；它不能单独证明当前服务器已切换、当前代码可发布或外部入口已安全验收。外部服务器、真实 AI、浏览器移动视口和公网状态仍按审计限制处理。

## 历史与待确认状态

### Prompt 审批与 handoff

`docs/superpowers/handoffs/2026-09-06-ai-v2-next-session-handoff.md` 与 `2026-09-06-ai-v2-readiness-baseline.md` 保留 candidate/caller=null 和单独审批要求；`2026-09-06-ai-v2-production-cutover-handoff.md`、`docs/ai/ai-v2-prompt-approval.md` 记录了 production 批准或切换前结论。它们来自不同提交/时间和文件快照，且当前 static/carousel hash 不可加载，因此本索引不替其中任何一份作出新的业务批准判断。

当前待确认项：

1. static/carousel 的正确 Prompt 模板快照及对应 registry hash。
2. 三份 Prompt 的最终审批记录、批准人/时间与唯一 caller 是否仍适用于当前 `master`。
3. `production-baseline-20260908`、2026-09-06 部署包和服务器目录与当前 `master` 的实际对应关系。
4. live 启用、真实 AI/图片、服务器写入、公网开放和正式发布的独立授权、备份、回滚及受控验证。

## 维护触发条件

- registry、Prompt、schema、validator、caller、版本或 hash 变化：同步复核本索引、AI 文档和定向 gate；hash 不一致时保持 fail-closed 记录。
- 启动/端口/数据目录/部署 ref 变化：更新 `docs/project-rules/operations.md` 或 `docs/deployment/` 的对应权威记录，并按实际 ref 重新验证。
- 审批、任务状态或验证结果变化：更新 `docs/repo-audit/STATE.md`、`QUEUE.csv` 和对应报告；历史 handoff 只追加交叉引用，不覆盖原始证据。
- 仅有局部实现细节变化且不改变上述边界：更新就近说明，不刷新根规则或本索引的日期来代替核验。

## 审计交接

T05、T06-001、T07-001 和新会话执行的 T08-001 已完成；审计状态为 `complete_with_limits`。完整证据、限制和未完成事项见 `docs/repo-audit/STATE.md`、`docs/repo-audit/QUEUE.csv` 与 `docs/repo-audit/reports/T08-001.md`。T08-001 当时未处理 `progress.md`；本专项仅整理其入口和过时摘要，不改变 T08 结论，也未修复 F-003/F-004/F-005/F-006 或执行真实 AI、图片、浏览器、服务器或公网验证。后续仅在 registry/hash、caller/schema、端口/部署 ref、审批或验证结果变化时建立增量复核。
