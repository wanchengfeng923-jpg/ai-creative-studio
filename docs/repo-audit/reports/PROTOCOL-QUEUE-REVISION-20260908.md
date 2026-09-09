# 中途修正后的协议与队列交接

## 本轮范围

仅合并 `C:/Users/admin/Downloads/从T02-002继续_范围与队列修正.md`：修订统一执行入口、任务卡和审计队列。保留已有 T01、T02-001、T02-002 已完成部分、覆盖/发现台账、用户对 `progress.md` 的优化和所有源码差异。本轮没有重新盘点、程序修复、文档内容修订或 `progress.md` 读取/验证。

## 现场判定

- `T02-002.md` 和 38 项定向测试证明核心 app/auth/repository/backup/project_projection 主体盘点已发生，不能撤销或伪装为未开始。
- 原报告中的 `F-005` 是明确残余范围；因此 `T02-002` 现在标为 `split`，child `T02-007` 负责下一会话的审计型补充。`T02-007` 不执行代码修复，程序修复保持 deferred。
- T03-001/002/003 均真实存在于队列，现已写明文件组、声明类型、T02 依赖、报告入口和完成条件；三项均为 `todo`，无报告即不算完成。
- T04-001/002 仍为计划，显式依赖全部 T03；T05/T06 也补齐全部 T03/T04 阶段门槛。T08 仍需新会话独立验收。

## 阶段计数（QUEUE.csv）

| 阶段 | 任务数 | 状态 |
| --- | ---: | --- |
| T01 | 1 | done 1 |
| T02 | 7 | done 1, split 1, todo 5 |
| T03 | 3 | todo 3 |
| T04 | 2 | todo 2 |
| T05 | 1 | todo 1 |
| T06 | 1 | todo 1 |
| T07 | 1 | todo 1 |
| T08 | 1 | todo 1 |

## 文档到 T03 的映射

- `T03-001`：根规则、README/CONTEXT/代码地图、运维和 AI 主计划；排除 `progress.md`。
- `T03-002`：deployment 与 release 六个实际文档。
- `T03-003`：ADR、research 及受限的当前 superpowers handoff/spec 入口；明确排除完整历史全文和 `progress.md`。
- 当前 `docs/repo-audit/file-inventory.json` 已列出这些文件；本轮未重做文件清单。若后续发现清单漏项，应先追加独立清点任务，不得虚构路径。

## 下一新会话

最小必读：`repo-audit-kit/RUN_ONE_TASK.md`、`docs/repo-audit/STATE.md`、`docs/repo-audit/QUEUE.csv`、本报告、`docs/repo-audit/reports/T02-002.md`、`docs/repo-audit/reports/T02-007.md`、`docs/repo-audit/findings.csv`、`AGENTS.md`。下一任务：`T02-007`，继续 T02-002 的实际残余审计范围。
