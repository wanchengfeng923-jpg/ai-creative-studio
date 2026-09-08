# AI v2 接手核验与 readiness gate 设计输入

- 日期：2026-09-06
- 范围：交接读取、离线基线、审批状态与门禁设计；本轮未实现新 gate。
- 分支：`codex/tag-accordion-prototype`
- HEAD：`1bb6dd1`，`chore: remove retired ai implementation`
- 接手时 8775、8780、8791 均未监听；进程、用户、系统级 `CREATIVE_STUDIO_AI_V2_LIVE` 均未设置。
- 本轮真实文字/图片请求为 0；未修改凭据、live、真实运行目录或提交工作树。

## 新鲜验证

使用项目 `.venv/Scripts/python.exe` 和 `PYTHONPATH=src`：

- 全量 unittest：180 项通过。
- static/carousel 定向 unittest：12 项通过。
- release gate 内 AI v2 unittest：106 项通过。
- release gate 的 v2-contract、compileall、Node、diff-check、boundary 全部通过。
- 正式 `static/app.js` Node 语法、完整 `src chat2api` compileall、独立 boundary 检查通过。
- candidate contract evidence：30 个 case，29 个可自动判定 outcome 通过，1 个质量 case 未运行；证据仍为 `deterministic_fake` / `contract_only`。

## 本轮实现

- 新增 `src/creative_studio/ai_v2/production_gate.py` 和 `tests/test_ai_v2_production_gate.py`。
- `python -m creative_studio.ai_v2.production_gate` 是独立 production readiness 命令；当前仓库 registry 预期以非零状态报告 candidate 阻断。
- gate 不改 registry，不发网络请求，不写真实数据；临时 production registry 测试验证三类 canonical caller 和源码可达性。
- gate 同时确认 `creative_studio.app.create_application` 的 v2 factory 入口存在，并拒绝用例与 output schema 不匹配。

## 审批和当前代码

- `app.py:create_application()` 已在未启用 live 且没有显式文字模型注入时返回 `ai_not_enabled`。
- `AiV2Application` 已连接 narrative/static/carousel 三个用例；代码可达不等于已批准 production caller。
- registry 三项均为 `candidate`、`caller=null`、`max_model_calls=1`，hash 与 schema 检查通过。
- 审批表记录叙事/静态允许受控真实评测；当前轮播文本为“需修改后再评”。没有 production 批准。

## 需要核清的证据冲突

1. `2026-09-06-ai-v2-next-session-handoff.md` 和 progress 记录图片停在 unknown、轮播未执行；`2026-09-05-ai-v2-image-eval-final-handoff.md` 及现存 JSON 报告却记录静态和两帧成功。仅凭文档日期无法认定哪一次运行是最终完整证据。
2. 图片 final handoff 写静态提交 1 次，当前 static JSON 写 `provider_image_submissions=3`；carousel JSON 写提交 0 次却记录两帧成功。
3. carousel JSON 的两帧 artifact 字节数和 SHA-256 前缀相同。这不足以证明第二帧发生了独立的供应商生成，也不足以单独断定状态机缺陷，需要核对评测脚本的计数、复用与对账来源。
4. operations 和代码地图仍写正式入口默认 candidate，与当前 fail-closed 代码不一致；AI 总纲的旧链路按 `docs/ai/README.md` 只作为迁移审计背景。
5. Prompt 审批文档尾部仍笼统写三份均获准，表格却将修订后的轮播标为待重评。生产审批不能由这些含混文字推定。

原始报告本轮只读，未重写。上述图片证据不得直接作为 production pass。

## 建议的独立 gate

目标：增加独立 `production_readiness_gate`，在离线环境证明已批准注册信息和正式调用链一致。

- 保留现有 candidate gate 的严格语义和报告类型。
- 拒绝 candidate、缺失或多个 caller、错误 caller、缺失用例、hash/schema/id/version 漂移以及非整数或不等于 1 的调用预算。
- 使用临时目录和显式 fake 模型，从 `create_application()` 经 v2 API/应用分发执行三个用例；验证实际 caller、模型请求、schema、公开 DTO 和调用数。轮播只走 carousel，不先走 static。
- 正向用例使用临时 production registry 夹具；不得为了测试变绿而修改仓库中的候选审批状态。组合根若需 registry 注入，应保持默认配置来源不变。
- 使用独立报告 schema，明确 `evidence_type=deterministic_fake`、真实模型质量未验证；不接受 candidate/controlled 报告作为 production 质量证据。
- 对当前仓库执行新 gate 应返回非零并列出审批/caller 阻断项。注册及调用链检查通过也不等于 live、图片质量、备份恢复或正式切换通过。

验收重点：合法临时 production registry 能通过；candidate、伪造 caller、重复 caller、断开的组合根、错 schema/hash、调用超额和错误证据类型均被拒绝。测试必须能因真实接线错误而失败。

非目标：改 Prompt、升级 lifecycle、修改图片状态机、增加真实请求、默认 live、迁移运行数据或发布。

回滚：后续 gate 作为独立命令引入，撤回其新增模块、测试及可选依赖注入即可；不需要数据回滚。当前仅追加核验文档。

## 接手时工作树快照

```text
## codex/tag-accordion-prototype
 M chat2api/routes_images.py
 M chat2api/web_client.py
 M config/ai_v2/prompts/carousel-text-v1.txt
 M config/ai_v2/prompts/registry.json
 M docs/ai/ai-v2-prompt-approval.md
 M progress.md
 M src/creative_studio/ai_v2/carousel_visual.py
 M src/creative_studio/app.py
 M static/app.js
 M tests/test_ai_v2_app_integration.py
 M tests/test_ai_v2_carousel_visual.py
 M tests/test_ai_v2_frontend_contract.py
 M tests/test_ai_v2_gateway_runtime.py
 M tests/test_ai_v2_prompt_registry.py
?? .scratch/ai-v2-production-integration/
?? .scratch/ai-v2-real-image-eval-current/
?? .scratch/ai-v2-real-image-eval-direct/
?? .scratch/ai-v2-real-image-eval-fixed/
?? .scratch/ai-v2-real-image-eval-relay/
?? .scratch/ai-v2-real-image-eval-retry-now/
?? .scratch/ai-v2-real-image-eval-retry/
?? .scratch/ai-v2-real-image-eval-retry2/
?? .scratch/ai-v2-real-image-eval-socks5h/
?? .scratch/ai-v2-real-image-eval-stage/
?? .scratch/ai-v2-real-image-eval/
?? .scratch/ai-v2-real-text-eval/
?? .scratch/ai-v2-same-process/
?? docs/superpowers/handoffs/2026-09-05-ai-v2-image-eval-final-handoff.md
?? docs/superpowers/handoffs/2026-09-05-ai-v2-image-eval-handoff.md
?? docs/superpowers/handoffs/2026-09-05-ai-v2-next-session-handoff.md
?? docs/superpowers/handoffs/2026-09-05-ai-v2-production-integration-handoff.md
?? docs/superpowers/handoffs/2026-09-06-ai-v2-next-session-handoff.md
?? docs/superpowers/plans/2026-09-05-ai-v2-production-integration.md
?? tests/test_chat2api_web_client.py
```
