# AI 用例评测状态

本文档记录当前仓库内可复现的评测资产和仍未验证的质量门禁。它不把 deterministic fake 的契约通过误写成真实模型质量结论。

## 固定评测集

| 用例 | 评测集 | 样例数 | 当前可验证内容 |
|---|---|---:|---|
| 叙事 | `config/evals/narrative.v1.json` | 10 | 数量、结构、事实边界、注入防护和第二批去重约束 |
| 静态展示 | `config/evals/static.v1.json` | 10 | 三案结构、证据状态、机制差异、私有字段和 repair 失败 |
| 轮播 | `config/evals/carousel.v1.json` | 10 | 2/3/4/5 帧、路线连续性、私有首帧指令和失败状态 |

这些 fixture 只包含脱敏输入、硬约束和评测维度，不包含真实模型输出。每次 prompt 或 contract 变更至少运行对应的 fixture 测试和全量 deterministic unittest。

## 当前证据

- 全量 deterministic unittest：254 项通过。
- `PromptRegistry` 在启动时校验路径、hash、变量、contract、生命周期和唯一 production caller。
- 叙事、静态、轮播 production caller 均穿过各自 Module；图片任务使用 deterministic fake 验证排队、失败、重试和恢复。
- 真实 AI 输出质量、事实准确性、机制人工评分、成本/延迟 baseline、真实图片质量和供应商成功率尚未验证。
- 本地 `python -m creative_studio.evaluation_harness --validate-only` 会校验 3 套 fixture（共 30 个 case）和三份 `not_run` 报告；它不调用模型或图片供应商。

## 离线硬约束 lint

`creative_studio.evaluation_harness` 提供三层离线检查：

- `lint_case_output(use_case, case, output)` 使用对应 canonical validator，并递归拒绝图片指令、供应商游标、路径和 raw response 等私有字段。
- `evaluate_case_outputs(...)` 汇总一组 case 的硬约束通过率和失败分类；它只评价结构/边界，不替代人工创意评分。
- `lint_evaluation_result(...)` 对 `complete`/`failed` 报告强制要求 `hard_constraint_pass_rate`、`calls`、`latency_ms`、合法失败分类和 `evidence_type`。

失败分类使用固定枚举：`model_output_invalid`、`provider_protocol_invalid`、
`image_generation_failed`、`carousel_operation_failed`；`aggregate_failure_classifications(...)`
可跨结果聚合，未知分类或负数计数会使门禁失败。

## 报告契约

`config/evals/report-template.v1.json` 是版本化报告模板。每份报告必须保留
`baseline`、`candidate` 和 `repair_failure` 三个结果槽位；未执行的结果使用 `status: "not_run"`，不得用
deterministic fake 结果冒充真实供应商质量。非 `not_run` 结果至少记录硬约束通过率、实际调用次数、延迟和
失败分类。稳定失败分类为 `model_output_invalid`、`provider_protocol_invalid`、
`image_generation_failed` 和 `carousel_operation_failed`。

deterministic fake 不写入 baseline/candidate/repair_failure。运行
`python -m creative_studio.evaluation_harness --deterministic-fake-summary` 只输出
`deterministic-contract-evidence.v1`，并明确 `evidence_type=deterministic_fake`、
`quality_claim=contract_only`；这份输出不能被解释为真实模型质量报告。

## 真实评测前置条件

真实模型或图片网关评测必须使用固定脱敏输入、独立评测输出目录和明确预算；不得读取或修改 `data/`、`chat2api/.env`，也不得把完整模型回复写入公开日志。评测报告至少应包含硬约束通过率、事实错误数、机制差异人工评分、可制作性/一眼可懂评分、第二批重复率、调用次数、延迟和失败分类。

在获得单独授权并完成备份/回滚变更卡前，真实 AI、真实图片网关和带认证浏览器均保持“未验证”。
