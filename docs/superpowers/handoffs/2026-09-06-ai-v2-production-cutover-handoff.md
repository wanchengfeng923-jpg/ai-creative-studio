# AI v2 正式切换前交接

> 历史切换快照：本文保留 2026-09-06 的 production/cutover 记录，不能单独证明当前 registry 可加载、服务器已切换或正式发布已获授权。先读取 [`docs/current-state.md`](../../current-state.md) 并按当前 ref 重新验证。

日期：2026-09-06

## 当前结论

- 三份 AI v2 Prompt 已按用户明确批准晋级 `production`。
- registry 已绑定唯一 production caller：
  - narrative：`creative_studio.ai_v2.narrative.NarrativeTextUseCase.generate`
  - static：`creative_studio.ai_v2.static_visual.StaticTextUseCase.generate`
  - carousel：`creative_studio.ai_v2.carousel_visual.CarouselTextUseCase.generate`
- 独立 production readiness gate 已通过，验证 composition root、caller 可达性、schema 映射、hash 和 `max_model_calls=1`。
- candidate contract gate 已改为从临时降级 registry 重建，30 个 case、29 个自动 contract outcome 通过；质量 case 和真实模型质量仍不作通过结论。
- 真实图片隔离评测已完成，报告目录：`.scratch/ai-v2-real-image-eval-20260906/`。
- 当前仍未启用 `CREATIVE_STUDIO_AI_V2_LIVE=1`，没有执行本机正式切换。

## 最新验证

- 全量 unittest：184 项通过。
- AI v2 unittest：110 项通过。
- release gate：`v2-contract`、compileall、Node、diff-check、boundary 全部通过。
- production readiness gate：通过。
- backup dry-run：生成 `.scratch/backup-smoke-20260906` 只读 manifest，未修改真实运行数据。
- backup/restore 临时测试：7 项通过，覆盖 `verified`、引用完整性和篡改拒绝。
- static/carousel/gateway/production gate 定向测试：34 项通过。
- 8775、8780、8791、7896 均未监听。

## 真实图片证据

- 使用模型：`gpt-5-6-mini`。
- 文字调用：0。
- 供应商图片提交：3，总计 static 1、carousel 2。
- static：1 session、1 attempt、1 artifact，PNG；重复点击复用成功 attempt。
- carousel：越序请求得到 `frame_order_conflict`；两帧成功，共用 1 session，revision=2；第二帧带参考图和 cursor；重复请求幂等。
- 两类公开 DTO 私有字段泄露数：0。
- 旧目录 `.scratch/ai-v2-real-image-eval/` 曾被两轮脚本覆盖，已在 `2026-09-06-ai-v2-image-evidence-reconciliation.md` 标记为冲突证据；不要把旧目录当作单一实验结果。

## 当前工作树

- 分支：`codex/tag-accordion-prototype`
- HEAD 基线：`1bb6dd1`
- 工作树包含用户和本任务既有未提交修改，必须保留；不要使用 `reset --hard`、`checkout` 或批量覆盖。
- 本任务新增/修改重点：production registry、production gate、release gate candidate fixture、Prompt 审批/质量文档、operations/代码地图、评测 harness、progress 和本交接文档。
- 不要提交当前工作树，除非用户明确要求。

## 下一步：本机正式切换

只有收到正式切换授权后执行：

1. 停止网页和网关，确认 8775/8780 无监听。
2. 对真实 `data/creative_studio.db`、`data/images/`、`data/uploads/` 做独立备份。
3. 在新目录执行 restore smoke，必须得到 `verified=true` 和 `references_verified=true`。
4. 通过启动器向 web 子进程显式传递 `CREATIVE_STUDIO_AI_V2_LIVE=1`；不要依赖未确认的全局环境变量。
5. 启动单实例，检查 runtime adapter、registry、caller、health 和端口。
6. 在用户指定项目执行一次真实文字 smoke 和一次按需图片 smoke，记录调用数、耗时、错误码和 trace id。
7. 做 `1280x720`、`390x844` 根页面检查、控制台检查和横向溢出检查。
8. 关闭 live 并重启，确认回滚后返回 `ai_not_enabled`，不产生 candidate 假结果。

## 切换停止条件

出现认证失败、代理出口无法确认、备份/恢复校验失败、连续 provider unknown、调用超预算、schema 连续失败、私有字段泄露、重复图片 session 或旧 AI 路径恢复时立即停止。不要删除新增 `ai_v2_*` 数据或图片作为回滚手段。

## 未授权事项

本交接不自动授权：修改 `chat2api/.env`、复制或输出 token/Cookie、开放局域网/公网、提交工作树、删除真实数据、默认永久启用 live 或正式发布。正式切换需要用户在新会话中明确确认。
