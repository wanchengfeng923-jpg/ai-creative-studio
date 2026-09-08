# AI v2 评测状态

本文记录当前仓库内可复现的 AI v2 评测资产和仍未验证的质量门禁。旧 AI v1 fixture、报告模板和评测 harness 已随旧实现删除；相关历史结论仍保留在 ADR、计划、handoff 和 progress 中。

## 固定候选集

AI v2 使用 `config/evals/ai_v2/prompt-cases.jsonl` 的 30 个脱敏 case，叙事、静态、轮播各 10 个。硬约束定义位于 `config/evals/ai_v2/expected-hard-constraints.json`，候选 Prompt 和审批边界见 `docs/ai/ai-v2-prompt-approval.md`。

可重复执行：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m creative_studio.ai_v2.release_gate
```

该命令运行 v2 contract 测试、Python compileall、Node 语法、diff-check 和 boundary 扫描，并输出 deterministic contract evidence。它不会默认连接真实模型或图片供应商。

## 当前证据

报告：`config/evals/ai_v2/reports/candidate-contract-evidence.v1.json`

- 30 个 case 定义完整。
- 29 个可自动判定的文字 contract outcome 符合预期。
- 7 个坏输出归类为 `model_output_invalid`。
- 23 个成功公开 DTO 的递归私有字段扫描泄露数为 0。
- 30 次文字调用全部来自进程内 deterministic fake，每 case 1 次；图片调用为 0。
- 没有隐藏格式修复、文字重试或图片重试。
- `narrative-07` 的机制重复判断和全部真实模型质量为 `not-run`。

三份 v2 registry 项的文件 hash、`AiV2Input.v1`、对应 `*-text-v1` schema、production caller 和 `max_model_calls=1` 已对齐。candidate contract evidence 使用临时降级 registry 重建；production lifecycle 仍不等于真实模型质量通过。

## 失败分类

release gate 使用以下稳定分类：

- `model_output_invalid`
- `provider_protocol_invalid`
- `image_generation_failed`
- `carousel_operation_failed`

报告同时记录 schema 通过率、公开字段泄露数、模型调用数、重试数和每类失败计数。未知分类、超出预算、私有字段泄露、Prompt hash/schema 不匹配或 boundary 违规都会使门禁失败。

## 真实评测前置条件

真实模型或图片评测必须使用固定脱敏输入、临时 SQLite/图片目录和明确预算；不得读取或修改 `data/`、`chat2api/.env`，也不得把完整模型回复写入公开日志。报告至少记录：

- 硬约束通过率与失败分类；
- 事实错误数和机制差异人工评分；
- 可制作性、一眼可懂和第二批重复率；
- 调用次数、成本、延迟和供应商成功率；
- Prompt 版本、schema 版本和审批人。

Prompt 已获 production caller 批准，但在真实质量结论、备份恢复和正式切换完成前，不得默认启用 `CREATIVE_STUDIO_AI_V2_LIVE=1`。
