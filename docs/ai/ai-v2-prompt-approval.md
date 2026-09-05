# AI v2 候选 Prompt 审批包

- 日期：2026-09-05
- 当前状态：等待用户评审
- 可审批范围：候选 Prompt 文本是否可进入后续受控真实模型评测
- 不在本次审批范围：production caller、默认 live 模式、真实网关请求、正式发布

## 候选清单

| 用例 | Prompt | 输出 Schema | SHA-256 | 生命周期 | caller |
|---|---|---|---|---|---|
| 叙事 | `config/ai_v2/prompts/narrative-text-v1.txt` | `narrative-text-v1` | `33f55fb7d3c0c90903a3c879efe3de6a15ccdc4ec83a262a94aa131967392851` | `candidate` | `null` |
| 静态 | `config/ai_v2/prompts/static-text-v1.txt` | `static-text-v1` | `1eed12efce5e04e505f1e4d4134d8e85ca2c528ad4931cc220278c1736e63f2d` | `candidate` | `null` |
| 轮播 | `config/ai_v2/prompts/carousel-text-v1.txt` | `carousel-text-v1` | `ed85430d70935166cf37d149c77eee1e7f44001fdcdf883764cfd558a81db46b` | `candidate` | `null` |

三份候选都只接受 `task_description`、`aspect_ratio`、`creative_tags`，每批最多一次文字模型调用。Prompt 明确写出完整 JSON 骨架、固定方案数量、必填字段和私有 `execution` 结构；registry 加载时会重新计算文件 hash，并拒绝 hash、变量或生命周期不一致。

## 确定性证据

可复核报告位于 `config/evals/ai_v2/reports/candidate-contract-evidence.v1.json`，由以下命令在临时 SQLite 和 deterministic fake 上重建：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m creative_studio.ai_v2.release_gate
```

当前报告记录：

- 30 个脱敏 case，叙事、静态、轮播各 10 个；30 个 case 的三字段输入和预期字段均完整。
- 29 个可自动判定的文字 contract outcome 全部符合预期；`narrative-07` 的机制重复属于真实质量判断，保持 `not-run`。
- 30 次 deterministic 文字调用，每 case 恰好 1 次；图片调用为 0，总声明预算为 30 次。
- 7 个故意构造的坏输出全部归类为 `model_output_invalid`，没有隐藏格式修复调用。
- 23 个成功公开 DTO 经递归扫描，私有字段泄露数为 0。
- 三份候选的文件 hash、输入 schema、输出 schema、生命周期和 caller 均与 registry 对齐。

## 证据边界

这份报告的 `evidence_type` 是 `deterministic_fake`，`quality_claim` 是 `contract_only`。它只证明输入、Prompt 编译、Schema、存储、公开投影和失败分类契约可重复运行，不证明候选 Prompt 在真实模型上的创意质量、事实准确性、机制差异、可制作性、延迟、成本或供应商稳定性。

在用户批准候选文本并单独授权真实评测前：

- `registry.json` 中三项继续保持 `lifecycle=candidate`、`caller=null`；
- 不设置默认 `CREATIVE_STUDIO_AI_V2_LIVE=1`；
- 不修改 `chat2api/.env`，不读取或写入真实数据库、图片和上传目录；
- 不把本报告当作 production 发布批准。

## 评审批注

评审时应分别检查三份 Prompt 是否准确表达对应业务任务、是否遗漏必要内容约束，以及是否存在会诱导模型扩展产品事实或剧情的措辞。评审结论应明确为“允许进入受控真实评测”“需修改后再评”或“不批准”；即使允许真实评测，也不等于批准 production caller 或正式发布。
