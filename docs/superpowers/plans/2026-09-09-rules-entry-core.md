# Rules and Entry Core Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收敛项目规则和当前事实入口，让日常任务按风险和领域读取必要资料，并修正进度摘要中的过时当前事实。

**Architecture:** `AGENTS.md` 只保留跨任务规则和按任务导航；`docs/current-state.md` 维护当前事实、证据层级和维护触发条件；`README.md` 提供用户/开发者最短入口；`progress.md` 仅保留简洁时间线和交接指针，不重复当前事实台账。

**Tech Stack:** Markdown, Git, PowerShell 定向检查。

**Spec:** `C:/Users/admin/Downloads/项目规则与阅读入口整理_专项任务.md`

## Global Constraints

- 保留 T01-T08 审计报告、QUEUE、STATE 及既有用户未提交改动。
- 不修改业务代码、测试、Prompt、registry、schema、依赖、运行配置或部署文件。
- 不重跑 T01-T08，不把历史审批、deterministic gate 或旧测试数字表述为当前通过。
- 分单元推进；后续资料一致性单元只处理已确认职责的文档，不重启 T01-T08。
- `progress.md` 可按用户本轮授权处理，但不恢复成第二份当前事实索引。

---

### Task 1: Rewrite task-based reading navigation

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/current-state.md`

**Interfaces:**
- Produces: 清晰的任务到入口映射、当前事实与历史资料的边界、无默认全量阅读要求。

- [x] 将 `AGENTS.md` 的默认阅读清单改为按任务路由，保留代码、AI、运维和高风险门禁的适用条件。
- [x] 在 `README.md` 增加最短开发/运维入口，并把当前事实与历史进度分开。
- [x] 在 `docs/current-state.md` 增加按任务查阅表，并修正专项处理 `progress.md` 后的历史表述。
- [x] 检查相对链接、默认端口、registry hash 阻塞和 fail-closed 语义未被改写。

### Task 2: Correct the compact progress pointer

**Files:**
- Modify: `progress.md`

**Interfaces:**
- Produces: 与 `docs/current-state.md` 一致的简洁进度入口，不重复完整事实表。

- [x] 修正当前 HEAD、审计阶段、registry/hash 和生产就绪表述。
- [x] 保留已存在的历史/维护信息，不恢复删除的逐日流水账。
- [x] 增加本专项记录和下一维护触发条件。

### Task 3: Record and verify the handoff

**Files:**
- Create: `docs/repo-audit/reports/RULES-ENTRY-20260909.md`

- [x] 记录真实问题、规则处置、改前/改后场景问题和未验证限制。
- [x] 对限定文件执行 Markdown 链接、关键事实和 `git diff --check` 检查。
- [x] 记录下一资料单元，不把本轮结果宣称为整个专项最终验收。

### Task 4: Align supporting documentation responsibilities

**Files:**
- Modify: `docs/project-rules/CODE_STYLE.md`
- Modify: `docs/project-rules/CONTEXT.md`
- Modify: `docs/project-rules/operations.md`
- Modify: `docs/project-rules/项目代码地图.md`

**Interfaces:**
- Consumes: `AGENTS.md` 的任务路由与 `docs/current-state.md` 的当前事实职责。
- Produces: 代码规范、领域词汇、运行手册和代码地图各自单一职责，互相只保留导航引用。

- [x] 明确 `docs/project-rules/CODE_STYLE.md` 只维护代码约定和按风险选择检查，去除当前状态/审计台账的重复职责。
- [x] 明确 `docs/project-rules/CONTEXT.md` 只维护稳定词汇，并补充 run、scheme、image session、attempt、frame 的最小定义。
- [x] 收敛 `docs/project-rules/operations.md` 的 loopback、registry 状态和检查触发条件，保留启动、数据、备份、故障和运行边界。
- [x] 收敛 `docs/project-rules/项目代码地图.md` 的入口、目录、调用链和修改导航，动态缺口回链 `docs/current-state.md`。
- [x] 对四份文档及专项报告做链接、事实和场景定向验证。
