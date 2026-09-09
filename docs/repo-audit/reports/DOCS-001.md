# DOCS-001 项目规则目录归档

## 任务 ID、目标与范围

- 任务 ID：`DOCS-001`
- 目标：将规则/支持文档集中到根目录下的 `docs/project-rules/`，并修正仓库内相关地址。
- 范围：`CODE_STYLE.md`、`CONTEXT.md`、`docs/operations.md`、`项目代码地图.md` 及其入口、计划、handoff、审计台账和发布脚本引用。
- 非目标：不重跑 T01-T08，不修改业务代码、Prompt、registry、schema、依赖或部署配置；不改写既有审计结论。

## 开始和结束时的基线 / 差异

- 仓库：`D:/code/ai_creative_studio`
- 开始基线：`master` / `97e33ef869e47c88a0def40c1c990ae42c339668`；工作树已有未提交的规则、审计、部署文档和 `progress.md` 改动，均保留。
- 结束差异：四个文件完成 Git 移动；相关 Markdown、CSV、handoff、计划、发布清单和状态入口同步路径；源码、配置、静态资源和测试目录没有本轮差异。
- 收尾工作树计数：`git status --porcelain --untracked-files=all` 共 87 条记录，其中 37 条已跟踪文件变更、50 个未跟踪文件、0 条暂存记录；其中既有工作树内容与本轮文档整理均包含在内。

## 实际读取与核对的关键资料

- `repo-audit-kit/RUN_ONE_TASK.md`、`repo-audit-kit/HANDOFF_FORMAT.md`
- `AGENTS.md`、`docs/current-state.md`、`docs/repo-audit/STATE.md`、`docs/repo-audit/QUEUE.csv`
- 移动后的四份规则/支持文档、`README.md`、`docs/ai/README.md`、`scripts/build_release.ps1`
- 仓库内历史 handoff、计划、报告和部署/发布文档中的路径引用

## 已证实结论及证据

1. 根目录不再保留四份支持文档；统一目录为 `docs/project-rules/`。
2. 根目录 `AGENTS.md` 保留为自动规则加载入口，且已指向新目录。
3. 当前入口和历史文档引用已更新；历史内容只改地址，不改原结论、版本或审批语义。
4. `scripts/build_release.ps1` 已将 `docs/project-rules/operations.md` 纳入发布清单。

## 推断与待确认意图

- 将 `AGENTS.md` 留在根目录是为了保留项目规则自动加载能力；其余四份文档属于支持资料，集中归档不改变职责。
- 历史 `.scratch/deployment-package-20260906-v2` 是已生成的快照，不属于本轮源文档；本轮未保留对其路径的机械改写。

## 实际修改与原因

- `git mv CODE_STYLE.md docs/project-rules/CODE_STYLE.md`
- `git mv CONTEXT.md docs/project-rules/CONTEXT.md`
- `git mv docs/operations.md docs/project-rules/operations.md`
- `git mv 项目代码地图.md docs/project-rules/项目代码地图.md`
- 更新根入口、当前事实索引、AI 总纲、AI 入口、部署/发布文档、handoff、计划、审计台账、进度指针和发布脚本中的地址。
- 修正迁移后相对链接：规则目录内回链 `AGENTS.md`、`current-state.md` 和变更卡模板使用正确层级。

## 执行的检查、结果及日志位置

- Markdown 相对链接检查：移动和相关入口文档无缺失链接；仓库另有既存 `.scratch/ai-v2-text-first-preview-design.md` 指向缺失的历史 scratch 文件，本轮未改动。
- 旧路径残留扫描：除移动文档内部合法的同目录短名外，未发现旧根路径或 `docs/operations.md` 残留；两处绝对 Windows handoff 路径已更新。
- `git diff --check`：退出码 0；Git 仅提示已有文档 CRLF 的标准化提醒。
- 源码范围检查：`src/`、`static/`、`frontend/`、`config/`、`tests/`、`chat2api/` 无本轮差异。
- 未运行全量测试、真实 AI、浏览器、部署或服务器操作，原因是本轮仅为文档路径整理且 RUN_ONE_TASK 要求不重跑已完成 T01-T08。

## 未完成项与拆分后的任务 ID

- 无本轮未完成的路径迁移项。
- 既有 F-003/F-004/F-005/F-006、审批、live、真实 AI/图片、浏览器和部署限制保持原状态，不在本任务修复。

## 对其他任务的影响

- T01-T08 的历史报告和完成状态不变；仅更新其中的文件地址以反映真实当前位置。
- 后续文档任务应从 `docs/project-rules/` 读取四份资料；根 `AGENTS.md`、`README.md` 和 `docs/current-state.md` 已提供入口。

## 完成条件逐项核对

- [x] 四份目标文档集中到 `docs/project-rules/`。
- [x] 活跃入口、发布脚本和相关文档地址已同步。
- [x] 历史结论未被重写，业务代码未修改。
- [x] 链接、旧路径和差异检查已执行并记录限制。
- [x] 状态、队列和报告已保存，可安全交接。

## 下一轮最小必读资料与下一动作

- 最小入口：`AGENTS.md`、`docs/current-state.md`、`docs/project-rules/`、本报告。
- 下一动作：无；只有规则目录、registry/hash、审批、部署或程序边界再次变化时，按 RUN_ONE_TASK 建立新的增量任务。
