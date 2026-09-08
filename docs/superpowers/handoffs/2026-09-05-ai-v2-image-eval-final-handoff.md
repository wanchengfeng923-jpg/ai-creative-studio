# AI v2 图片评测最终交接：工作台代理桥下的真实图片链路

> 交给下一执行会话。真实图片链路已在与工作台相同的本机代理桥下通过受控评测；不授权 production caller、默认 live 或正式发布。

## 结论

- 图片功能已实现且可用，问题不是 v2 图片状态机、图片回传或轮播会话逻辑。
- 根因是启动方式：工作台启动器会把远程 ClipProxy SOCKS 接入本机 Clash/Mihomo，并为 chat2api 提供本地 HTTP 转发桥；手动直接运行 `chat2api/main.py` 会绕过该桥，导致 `curl (97) Failed to receive SOCKS response`。
- 通过工作台同样的本地桥（发现端点为 Clash/Mihomo `7897/http`，relay 监听 `127.0.0.1:7896`）后，静态单图和轮播两帧均成功。
- 手动启动 chat2api 时必须经过 `launcher.py` 的 `_prepare_proxy_environment()`，不能直接把 `.env` 中远程 `socks5://...` 交给 chat2api。

## 已完成代码改动

- `chat2api/routes_images.py`：图片请求统一先调用 `ensure_fresh_token()`，与文字链路使用同一 token 刷新路径。
- `chat2api/web_client.py`：首页 bootstrap 改为尽力执行；requirements、prepare、conversation 错误增加阶段前缀，便于诊断。
- `tests/test_chat2api_web_client.py`：新增 bootstrap 失败不阻断后续图片会话的回归测试。
- 未修改 `chat2api/.env`、Prompt、registry、production live 开关或真实数据目录。

## 真实评测证据

报告：

- `.scratch/ai-v2-real-image-eval/static-real-image-report.json`
- `.scratch/ai-v2-real-image-eval/carousel-real-image-report.json`

在本机代理桥下：

- Static：1 次供应商提交，50 次轮询，约 44.5 秒成功；PNG；1 session、1 attempt、1 artifact；重复点击复用原 attempt，未重复提交。
- Carousel：第 2 帧越序返回 `frame_order_conflict` 且未提交；第 1/2 帧均成功；共用 1 session，revision=2；第 2 帧带参考图和 cursor；重复请求幂等；PNG artifact；公开 DTO 私有字段泄露为 0。
- 真实评测没有调用文字模型，证据类型为 `controlled_real_image_eval`，不构成 production 质量批准。

## 最近验证

- AI v2 gateway/runtime + chat2api 回归：19 项通过。
- 之前全量 unittest：180 项通过。
- release gate、compileall、Node、boundary、diff-check 均通过。
- 评测完成后已停止专用 `8791` 网关和 `7896` relay；检查时无专用监听残留。

## 下一会话步骤

1. 先读本 handoff、`2026-09-05-ai-v2-image-eval-handoff.md`、`progress.md` 和当前 `git status`，保留既有未提交修改。
2. 如需重新验证，使用工作台启动器启动服务，让它执行 `ClipProxyRelay`；不要直接运行 `chat2api/main.py` 作为真实图片网关。
3. 重新运行 deterministic 图片测试和必要 release gate；真实图片只在明确预算下使用临时 SQLite、临时图片/job 目录。
4. 继续记录 `queued/generating/success`、供应商提交数、轮询数、session/attempt/artifact 数和公开 DTO 隐私扫描。
5. 只有明确终态失败时才在原 session 内递增 attempt；unknown/timeout/5xx 先对账，不创建新 session。
6. 若要让“直接运行 chat2api”也支持远程 ClipProxy，需要另开变更：复用 `launcher.py` 的 relay 初始化或把 relay 提取为共享启动组件，并为该启动路径添加集成测试。

## 禁止事项

- 不要把远程 `socks5://` 直接作为 chat2api 的真实评测启动方式。
- 不要修改 `.env`、复制 token/Cookie、写入真实 `images/`、`image_job_state/` 或 `data/`。
- 不要把本次 controlled real image evidence 描述成 production pass。
- 不要提交当前工作树，除非用户明确要求。
