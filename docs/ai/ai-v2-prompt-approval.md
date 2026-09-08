# AI v2 候选 Prompt 审批包

- 日期：2026-09-05
- 当前状态：叙事、静态、轮播均已获用户批准进入 production；本次晋级不包含默认 live 或正式发布
- 可审批范围：候选 Prompt 文本是否可进入后续受控真实模型评测
- 不在本次审批范围：production caller、默认 live 模式、真实网关请求、正式发布

## 候选清单

| 用例 | Prompt | 输出 Schema | SHA-256 | 生命周期 | caller | 用户结论 |
|---|---|---|---|---|---|---|
| 叙事 | `config/ai_v2/prompts/narrative-text-v1.txt` | `narrative-text-v1` | `33f55fb7d3c0c90903a3c879efe3de6a15ccdc4ec83a262a94aa131967392851` | `production` | `creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate` | 已批准 production |
| 静态 | `config/ai_v2/prompts/static-text-v1.txt` | `static-text-v1` | `1eed12efce5e04e505f1e4d4134d8e85ca2c528ad4931cc220278c1736e63f2d` | `production` | `creative_studio.ai_v2.static_visual.StaticTextUseCase.generate` | 已批准 production |
| 轮播 | `config/ai_v2/prompts/carousel-text-v1.txt` | `carousel-text-v1` | `fcc05b0f9a91d990a80c1bcf8d54127fb876725a63c44ade2a9b17147446dd73` | `production` | `creative_studio.ai_v2.carousel_visual.CarouselTextUseCase.generate` | 已批准 production |

三份候选都只接受 `task_description`、`aspect_ratio`、`creative_tags`，每批最多一次文字模型调用。Prompt 明确写出完整 JSON 骨架、固定方案数量、必填字段和私有 `execution` 结构；registry 加载时会重新计算文件 hash，并拒绝 hash、变量或生命周期不一致。

用户说明：具体效果内容已有其他材料承载，本次批准保持现有 Prompt，不新增效果字段或扩展输出范围。轮播 Prompt 后续因真实评测暴露固定屏数契约缺口，已补充明确的屏数约束和紧凑 JSON 输出要求；该修改需要重新评审。

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

在用户单独确认真实评测的样例、调用次数、预算、输出位置和停止条件前：

- `registry.json` 中三项现为 `lifecycle=production` 并绑定唯一 v2 caller；
- 不设置默认 `CREATIVE_STUDIO_AI_V2_LIVE=1`；
- 不修改 `chat2api/.env`，不读取或写入真实数据库、图片和上传目录；
- 不把本报告当作 production 发布批准。

本次批准覆盖三份 Prompt 晋级 production caller；不批准默认 live、生产数据切换或正式发布。

## 评审批注

评审时应分别检查三份 Prompt 是否准确表达对应业务任务、是否遗漏必要内容约束，以及是否存在会诱导模型扩展产品事实或剧情的措辞。评审结论应明确为“允许进入受控真实评测”“需修改后再评”或“不批准”；即使允许真实评测，也不等于批准 production caller 或正式发布。
