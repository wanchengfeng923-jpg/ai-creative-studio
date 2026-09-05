# AI 文档入口

当前 AI 业务实现只保留 `creative_studio.ai_v2`。后续处理 Prompt、模型调用、图片任务、历史、公开 DTO 或相关测试时，以 `项目代码地图.md`、`operations.md`、AI v2 ADR 和当前代码为事实来源；旧重建总纲保留为迁移审计记录，不再作为待执行队列。

## 文档职责

- `../ai-rebuild-master-plan.md`：旧 AI 到 AI v2 的历史迁移总纲和决策记录。
- `../../AGENTS.md`：项目级安全边界、工作方式、验证和高风险操作门禁。
- `../../项目代码地图.md`：当前代码入口、生产调用链、API、数据表和修改导航。
- `../operations.md`：启动、停止、备份、恢复和故障处置步骤。
- `../../progress.md`：按日期追加的历史记录，不覆盖、不作为当前架构事实。
- [`quality-evaluation.md`](quality-evaluation.md)：固定脱敏评测集、当前 deterministic 证据和真实质量评测边界。
- [`ai-v2-prompt-approval.md`](ai-v2-prompt-approval.md)：AI v2 候选 Prompt、registry hash、contract 证据和审批边界。
- [`../adr/0005-ai-v2-boundary-and-session-policy.md`](../adr/0005-ai-v2-boundary-and-session-policy.md)：AI v2 输入、会话、重试和旧 AI 隔离边界。

历史 ADR、handoff、计划和研究文档允许继续提及已删除模块与旧表；它们不能被当作恢复旧运行时的依据。

## Agent 最短执行路径

1. 先确认 `src/creative_studio/app.py` 的 composition root 和实际 production caller。
2. 在变更卡中写目标、非目标、不变量、验收例子、风险和回滚。
3. 先用 fake adapter 和生产入口测试 prompt、contract、validator、公开 DTO、持久化及失败路径。
4. 运行 `python -m creative_studio.ai_v2.release_gate`；production caller 和 live 开关仍需独立审批。
5. 收尾更新当前事实、必要 ADR、`progress.md` 和验证结果，并明确真实 AI/图片/浏览器检查是否执行。
