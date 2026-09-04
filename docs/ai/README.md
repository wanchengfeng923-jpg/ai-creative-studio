# AI 文档入口

当前 AI 能力的唯一实施基线是 [`../ai-rebuild-master-plan.md`](../ai-rebuild-master-plan.md)。后续 Agent 处理提示词、模型调用、图片任务、生成历史、公开结果或相关测试时，必须先阅读该总纲，再沿总纲的 Phase 0 至 Phase 5 顺序执行。

## 文档职责

- `../ai-rebuild-master-plan.md`：当前真实生产链路、已确认问题、目标接口、PromptRegistry、契约、状态机、迁移阶段、测试/评测门禁和 Agent 交接协议。
- `../../AGENTS.md`：项目级安全边界、工作方式、验证和高风险操作门禁。
- `../../项目代码地图.md`：当前代码入口、生产调用链、API、数据表和修改导航。
- `../operations.md`：启动、停止、备份、恢复和故障处置步骤。
- `../../progress.md`：按日期追加的历史记录，不覆盖、不作为当前架构事实。
- [`quality-evaluation.md`](quality-evaluation.md)：固定脱敏评测集、当前 deterministic 证据和真实质量评测边界。
- [`../superpowers/handoffs/2026-09-04-ai-rebuild-phase-5-handoff.md`](../superpowers/handoffs/2026-09-04-ai-rebuild-phase-5-handoff.md)：下一会话继续 Phase 5 的执行顺序、caller 审计、临时 scrub/恢复演练和完成门禁。

如果未来把总纲拆成 `00-current-facts.md`、`01-problem-register.md` 等文件，只能由本入口指向拆分后的章节，不能复制同一事实。拆分完成并经过一致性检查前，总纲仍是唯一权威。

## Agent 最短执行路径

1. 先确认 `src/creative_studio/app.py` 的 composition root 和实际 production caller。
2. 在变更卡中写目标、非目标、不变量、验收例子、风险和回滚。
3. 先用 fake adapter 和生产入口测试 prompt、contract、validator、公开 DTO、持久化及失败路径。
4. 完成对应阶段门禁后再切换生产调用；旧路径必须有废弃条件和删除证据。
5. 收尾更新当前事实、必要 ADR、`progress.md` 和验证结果，并明确真实 AI/图片/浏览器检查是否执行。
