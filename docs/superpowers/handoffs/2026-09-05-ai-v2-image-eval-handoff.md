# AI v2 图片评测交接：静态单图与轮播逐帧会话

> 交给下一执行会话的工作文档。文字轮播评测已完成；下一阶段只验证真实图片网关和图片会话状态机。本文不授权 production caller、默认 live 或正式发布。

## 先看结论

- 产品语义已确认保持当前逻辑：展示类轮播只调用 carousel Prompt，不先调用 static Prompt。
- 最新轮播文字真实评测 10/10 通过，包含 `AI决定`；图片调用为 0。
- 下一任务是 P5 受控真实图片评测，先静态单图，再轮播最小两帧。
- 当前 8775（工作台）和 8780（chat2api）正在监听。现有 8780 进程使用已有 `chat2api` 图片/job 状态目录，不能把它当作隔离图片评测环境。
- 必须使用临时 SQLite、临时工作台图片目录，以及专用网关图片/job 目录；不得写入真实 `data/`、已有 `chat2api/images/` 或 `chat2api/image_job_state/`。

## 当前完成状态

仓库：`D:\code\ai_creative_studio`
分支：`codex/tag-accordion-prototype`

工作树有用户和本任务已有的未提交修改，必须保留；不要使用 `reset --hard`、`checkout` 或批量覆盖命令。

最近一次轮播文字证据：

- 报告：`.scratch/ai-v2-real-text-eval/carousel-compact-rerun-3-report.json`
- 模型：`gpt-5-6-mini`
- 网关：本地 `chat2api`
- 文字调用：10
- 图片调用：0
- 成功：10/10
- 固定 2/3/4/5 屏全部通过
- `AI决定` 三套方案统一返回 3 屏
- `stop_reason`: `null`

最近代码侧验证：

- 全量 unittest：179 项通过
- AI v2 unittest：106 项通过
- release gate、compileall、Node、boundary、diff-check：通过
- carousel Prompt hash：`fcc05b0f9a91d990a80c1bcf8d54127fb876725a63c44ade2a9b17147446dd73`
- 三份 Prompt 仍为 `candidate`，`caller=null`
- 未设置 `CREATIVE_STUDIO_AI_V2_LIVE=1`
- 未修改 `chat2api/.env`

## 下一阶段目标

只验证真实图片链路，不重新做文字质量评测，不修改 carousel-only 调用顺序。

### A. 静态单图

使用 deterministic 合法 static 文本 fixture 创建一个隔离 run，避免图片评测再次消耗文字调用。

验证一个方案的首次点击：

1. `POST /api/v2/schemes/{scheme_id}/image` 创建一个图片 session 和一条 attempt。
2. 通过 `GET /api/v2/image-attempts/{attempt_id}` 轮询到 `success` 或明确终态失败。
3. 成功时验证 artifact 存在、MIME 为 `image/png`、`image/jpeg` 或 `image/webp`，公开 URL 可访问，公开 DTO 不泄漏游标、job id、token、本地路径或图片 Prompt。
4. 对同一方案重复点击，必须复用已有成功结果，不创建第二个 session、job 或 attempt。

### B. 轮播最小两帧

使用 deterministic 合法 carousel 文本 fixture，固定两帧，选择一个方案。

验证顺序：

1. 请求第 2 帧先被 `frame_order_conflict` 拒绝，不创建图片任务。
2. 请求第 1 帧，等待成功。
3. 请求第 2 帧，验证复用同一个图片 session，并携带第 1 帧成功 artifact 作为参考图。
4. 验证第 2 帧使用递增 cursor/revision、独立 request id/attempt，但不创建第二个图片 session。
5. 重复请求已成功的第 2 帧，必须幂等返回原 attempt，不重复提交供应商任务。
6. 检查两张图片的 MIME、artifact、公开 URL 和公开字段边界。

### C. 对账和失败边界

真实图片评测至少记录 `queued/generating/success` 的轮询过程。若真实供应商返回未知、超时、断开或 5xx：

- 先调用 job reconcile；
- 未确认终态失败时，不创建新 session，不盲目新建 attempt；
- 只有明确 `terminal_failure` 才允许在原 session 内递增 attempt；
- 不添加隐藏重试，不把 unknown 伪装成失败或成功。

终态失败的完整重试迁移已由 deterministic image tests 覆盖；真实图片阶段若无法稳定触发供应商终态失败，记录为 `not_exercised`，不要人为制造供应商错误。

## 隔离与授权门

开始真实图片请求前，必须在任务记录或报告中确认：

- 图片 use case：static 单图 + carousel 两帧；
- 最大供应商图片提交数：建议首轮最多 3 个（static 1 个、carousel 2 个）；
- 状态轮询不计入图片生成提交数，但要记录次数和总延迟；
- 使用模型、预计成本和停止条件；
- 输出目录、临时数据库和清理策略；
- 发生认证失败、连续两次 provider unknown、或超过预算立即停止。

推荐使用专用网关进程，设置独立环境变量：

```text
CHATGPT_IMAGES_DIR=<temporary-gateway-images>
CHATGPT_IMAGE_JOB_DIR=<temporary-gateway-job-state>
HOST=127.0.0.1
PORT=<unused-loopback-port>
```

不要读取或复制凭据到文档；不要修改 `chat2api/.env`。如果必须复用当前 8780，先确认其图片/job 目录可审计隔离，否则停止并启动专用实例。

工作台侧使用临时 `AiV2Store`、临时 `images_dir` 和显式注入的 `ImageGatewayAdapter`；不要打开正式 composition root 的 live 开关。

## 相关实现入口

- 轮播图片状态机：[src/creative_studio/ai_v2/carousel_visual.py](D:/code/ai_creative_studio/src/creative_studio/ai_v2/carousel_visual.py)
- 静态图片状态机：[src/creative_studio/ai_v2/static_visual.py](D:/code/ai_creative_studio/src/creative_studio/ai_v2/static_visual.py)
- 图片网关适配器：[src/creative_studio/ai_v2/adapters/image_gateway.py](D:/code/ai_creative_studio/src/creative_studio/ai_v2/adapters/image_gateway.py)
- 图片异步 worker：[src/creative_studio/ai_v2/image_worker.py](D:/code/ai_creative_studio/src/creative_studio/ai_v2/image_worker.py)
- 图片 HTTP 接口：[src/creative_studio/ai_v2/http_api.py](D:/code/ai_creative_studio/src/creative_studio/ai_v2/http_api.py)
- chat2api 图片任务：[chat2api/routes_images.py](D:/code/ai_creative_studio/chat2api/routes_images.py)
- 静态图片 deterministic 测试：[tests/test_ai_v2_static_visual.py](D:/code/ai_creative_studio/tests/test_ai_v2_static_visual.py)
- 轮播图片 deterministic 测试：[tests/test_ai_v2_carousel_visual.py](D:/code/ai_creative_studio/tests/test_ai_v2_carousel_visual.py)
- 网关运行时测试：[tests/test_ai_v2_gateway_runtime.py](D:/code/ai_creative_studio/tests/test_ai_v2_gateway_runtime.py)

## 报告要求

新建独立目录：`.scratch/ai-v2-real-image-eval/`。至少保存：

- `static-real-image-report.json`
- `carousel-real-image-report.json`
- 临时 SQLite 路径或其摘要
- 供应商提交数、轮询数、session 数、attempt 数、artifact 数
- 每个 case 的状态、延迟、MIME、错误码、是否重用 session

报告不得保存完整供应商响应、图片 Prompt、Cookie、token、conversation id、parent message id 或本地绝对路径。质量声明使用 `controlled_real_image_eval`，不要写成 production pass。

## 完成标准

- [ ] 专用或已验证隔离的图片网关环境已确认。
- [ ] static 首次点击成功路径通过，重复点击无重复 session/attempt。
- [ ] carousel 第 2 帧越序保护通过。
- [ ] carousel 两帧共享一个 session，第二帧携带上一帧 artifact。
- [ ] 成功 artifact 的 MIME、URL、公开 DTO 隐私边界通过。
- [ ] working/unknown/terminal_failure 的处理结果已记录；未覆盖的供应商状态明确标记。
- [ ] 图片提交数、轮询数、成本和停止原因写入报告。
- [ ] deterministic 全量测试和必要的网关/边界检查重新通过。
- [ ] 不修改 Prompt、registry、caller、`.env` 或 production live 开关。

## 禁止事项

- 不要把 static Prompt 串到 carousel 前面。
- 不要在真实图片评测中重新调用文字 Prompt，除非另行取得授权并单独计数。
- 不要复用或污染当前 `chat2api/images/`、`chat2api/image_job_state/`、真实 `data/` 或生产上传目录。
- 不要跨方案共享图片 session；轮播只允许同一方案的帧共享 session。
- 不要在 unknown/timeout/5xx 后盲目创建第二 session。
- 不要为了得到成功率而自动重试、修改供应商响应或删除失败记录。
- 不要设置 `CREATIVE_STUDIO_AI_V2_LIVE=1`，不要把 candidate registry 改成 production。
- 不要提交当前工作树，除非用户明确要求。

## 接手第一步

1. 读取本 handoff、`docs/superpowers/handoffs/2026-09-05-ai-v2-next-session-handoff.md`、`progress.md` 和当前 git status。
2. 检查 8775/8780、当前网关工作目录和图片/job 输出目录；不要打印控制令牌。
3. 先运行 deterministic 图片相关测试，确认基线仍为绿色。
4. 取得或确认本阶段图片预算、输出目录和停止条件。
5. 准备隔离网关后，再按 static → carousel 顺序执行真实图片验证。
