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

- 全量 deterministic unittest：220 项通过。
- `PromptRegistry` 在启动时校验路径、hash、变量、contract、生命周期和唯一 production caller。
- 叙事、静态、轮播 production caller 均穿过各自 Module；图片任务使用 deterministic fake 验证排队、失败、重试和恢复。
- 真实 AI 输出质量、事实准确性、机制人工评分、成本/延迟 baseline、真实图片质量和供应商成功率尚未验证。

## 真实评测前置条件

真实模型或图片网关评测必须使用固定脱敏输入、独立评测输出目录和明确预算；不得读取或修改 `data/`、`chat2api/.env`，也不得把完整模型回复写入公开日志。评测报告至少应包含硬约束通过率、事实错误数、机制差异人工评分、可制作性/一眼可懂评分、第二批重复率、调用次数、延迟和失败分类。

在获得单独授权并完成备份/回滚变更卡前，真实 AI、真实图片网关和带认证浏览器均保持“未验证”。
