# 持久化状态与交接格式

以下均为字段模板，必须填入真实结果。不要复制示例值冒充检查结论。现有等价记录可复用，但状态与来源必须能对应。

## STATE.md：只保存当前状态

建议控制在一至两屏可读范围，作为维护目标而非硬限制。重要约束不能为了压缩丢失；详情使用链接。

```text
审计标识与仓库：
实际审计目录：
授权范围与有效约束入口：
源码基线及未提交差异摘要：
当前阶段与最近任务 ID：
运行状态：active / waiting / complete_with_limits / complete
已完成的范围摘要：
未完成与关键阻塞：
下一建议任务 ID：
本轮相关报告入口：
当前工具与规则加载核验入口：
```

STATE 是路由入口，QUEUE 是具体任务状态的维护位置。两者不一致时以真实记录和工作区核对，不能机械相信任意一份。

## QUEUE.csv：一行一个实际子任务

```csv
id,card,scope,status,depends_on,children,baseline,report,next_action
```

字段包含逗号或换行时使用标准 CSV 引号规则。多个依赖 ID 用分号分隔。id 采用如 T02-001 的稳定编号；card 使用任务包中真实任务卡的相对路径。

状态：todo、in_progress、done、blocked、split、not_applicable。not_applicable 必须有范围判断依据；不能用它隐藏无法检查的工作。完整依赖必须明确，不使用“参考此前全部任务”等模糊表达。

每行 scope 应描述可验收的实际范围，例如某个真实模块或具体文档组，不能只写“其余全部”。按需要可在同一行增加输入路径与完成条件，或把细节放入该任务报告前部。

## coverage.csv 与 findings.csv

可以采用原指南第 7 节字段，或下列紧凑格式：

```csv
path,category,module,baseline,read_status,crosscheck_status,runtime_status,task_id,evidence,gap
```

```csv
id,category,statement,evidence_status,source,impact,status,owner_task,verification
```

发现状态可用 open、resolved、blocked、deferred。deferred 说明属于明确的后续范围，不能把当前范围内的关键未完成项悄悄推迟。

## reports/任务ID.md

```text
任务 ID、目标与范围：
开始和结束时的基线 / 差异：
实际读取与核对的关键资料：
已证实结论及证据：
推断与待确认意图：
实际修改与原因：
执行的检查、结果及日志位置：
未完成项与拆分后的任务 ID：
对其他任务的影响：
完成条件逐项核对：
下一轮最小必读资料与下一动作：
```

修复任务引用原发现编号；不要改写历史报告来伪装之前已经通过。文件越长时越应引用已有证据，避免复制整个源码和长日志。

## 失效与恢复

每轮记录影响审计结论的源码、规则和文档版本。无 Git 时使用快照或必要文件哈希。审计记录自身的变更应与被审查源文件的变更区分，避免状态文件更新导致无限失效循环。

外部改动导致旧证据不适用时，新增有边界的复核任务；保留旧结论对应的旧版本。恢复中断任务时，先检查实际差异、半成品与检查结果，再决定续做或修复。

## 最终状态

- complete：约定范围已完成，必要验证通过，关键阻塞为零，T08 验收已完成。
- complete_with_limits：报告和可执行整理已完成，但存在明确的验证或访问限制；逐项披露，不能宣称完整验证。
- waiting：当前仍有关键范围未完成，等待用户决定、访问条件或其他依赖。
- active：仍有可以继续执行的范围。

状态不是授权。是否接受限制由用户的实际目标和要求决定，不能把 critical blocked 自动改为 complete_with_limits。
