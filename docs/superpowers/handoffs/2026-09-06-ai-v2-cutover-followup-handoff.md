# AI v2 正式切换后续交接

日期：2026-09-06

## 当前结论

- 用户已明确授权执行 AI v2 本机正式切换。
- 正确启动路径必须经过 `launcher.py` 的 `_prepare_proxy_environment()`，由代理桥把 ClipProxy 转发到本机 Clash HTTP `7897`。
- 之前的 502 是临时脚本未保持代理桥生命周期导致的；之前的图片 401 是手工 smoke 未传 `CREATIVE_STUDIO_AI_CONTROL_TOKEN` 导致的。
- 之前的 `gateway_restarted` 是测试脚本字段读取异常退出后，网关启动恢复机制对遗留 generating 任务的正常标记。
- 使用完整启动器环境和驻留代理桥后，项目 `12` 的真实文字 smoke 成功（`run_id=8`、3 个方案）；方案 `19` 的真实图片 smoke 成功（`attempt_id=7`、最终 `success`）。
- 本轮验证后服务已关闭，`8775`、`8780`、`7896` 均无监听。

## 已完成验证

- 真实数据备份：`.scratch/production-cutover-backup-20260906-$(Get-Date -Format HHmmss)/`。
- 隔离恢复 smoke：`.scratch/production-cutover-restore-smoke-20260906/`，`verified=true`、`references_verified=true`。
- 启动器已修改为显式传递 `CREATIVE_STUDIO_AI_V2_LIVE=1`；该修改位于 `launcher.py`，保留现有用户改动。
- AI v2 网关运行时/生产门禁定向测试 22 项通过；使用 `.venv` 执行全量 unittest 184 项通过；Node、compileall、diff-check 通过。
- 真实文字调用通过代理桥并写入真实数据库；真实图片任务提交 202、轮询最终成功并保存 PNG。

## 下一会话必须继续

1. 检查本次真实 run/image 的公开历史和图片状态，记录调用数、耗时、错误码和 trace id；确认无私有字段泄露。
2. 启动完整应用后使用浏览器检查根页面 `1280x720` 和 `390x844`：步骤流、项目抽屉、真实历史、控制台错误、横向溢出。
3. 验证关闭 live 后重启返回 `ai_not_enabled`，且不会生成 candidate 假结果。
4. 将本次成功 smoke、UI 检查和回滚证据更新到本 handoff、`progress.md`，必要时同步 `docs/project-rules/operations.md`。
5. 最终检查 `git status --short --branch`，保留所有用户既有未提交修改；不要提交工作树，除非用户另行要求。

## 2026-09-06 后续复核记录

- 真实数据库公开记录复核：`run_id=8`（项目 12，static，batch 1）为 `success`；`attempt_id=7`（方案 19，frame 1，attempt 1）为 `success`。当前 schema 没有耗时或 trace id 字段，无法从持久化状态补录这两项；公开查询未发现 `image_prompt` 等私有字段。
- 根页面已在 `1280x720` 浏览器默认视口打开并确认登录门；由于本机没有可用的生产账号密码，本轮未进入登录后的步骤流、项目抽屉和历史视图，也未修改账号或生产数据。
- 未设置 `CREATIVE_STUDIO_AI_V2_LIVE` 时，`create_application()` 稳定抛出 `AiV2ApplicationError(error_code='ai_not_enabled')`，未构造 candidate 假结果。
- 本轮启动的本地网页进程已停止；未提交工作树。
- 使用项目 `.venv` 重跑 AI v2 定向测试：110 项通过；`python -m creative_studio.ai_v2.release_gate` 的 v2-contract、compileall、Node、diff-check、boundary 均为 `ok`。全量 unittest 仍受 `curl_cffi` 缺失影响。
- 当前 `8775`、`8780`、`8791` 均无监听；`7897` 为外部 Clash 监听，不属于本项目服务。
- 在项目 `.venv` 中确认 `curl-cffi` 已安装后重跑全量 unittest：184 项全部通过；此前的导入错误来自系统 Python 而非项目虚拟环境。

## 当前工作树与边界

- 分支：`codex/tag-accordion-prototype`。
- 基线 HEAD：`1bb6dd1`。
- 工作树包含大量既有用户/本任务未提交修改，禁止 `reset --hard`、`checkout`、批量覆盖或删除。
- 不修改 `chat2api/.env`，不输出 token/Cookie，不开放局域网/公网，不删除真实数据。
- 临时脚本 `.scratch/run_launcher_proxy_smoke.py` 仅用于本次验证；后续如需保留，必须在进度文档中说明用途。

## 重要路径

- 代码：`D:\code\ai_creative_studio`
- 备份：`.scratch/production-cutover-backup-20260906-$(Get-Date -Format HHmmss)/`
- 恢复 smoke：`.scratch/production-cutover-restore-smoke-20260906/`
- 正式入口：`src/creative_studio/app.py`、`static/app.js`、`launcher.py`
- AI v2 registry：`config/ai_v2/prompts/registry.json`

## 2026-09-06 登录后 UI 复核

- 使用本机账号 `wcf` 完成登录后的桌面 UI 检查：步骤流、项目抽屉、三套方案和历史结果均可见。
- `1280x720` 下 `scrollWidth=1265`、`clientWidth=1265`，无横向溢出，控制台无 error。
- 当前浏览器后端不提供视口调整能力，`390x844` 移动视口未验证。
- 追加静态响应式复核：`styles.css` 在 `max-width:720px`/`700px` 提供移动布局，`body min-width:320px`，workspace/sidebar/header/stepper 均设置 `min-width:0`，表格使用独立 `overflow-x:auto`；未改代码。
- 按用户授权经启动器 `_prepare_proxy_environment()` 和驻留代理桥完成三类真实文字 smoke：叙事项目 21 `run_id=11` 成功、静态项目 31 `run_id=12` 成功、轮播项目 12 `run_id=13` 成功；三次均未扫描到 `image_prompt`、会话 ID 等私有字段。未调用图片模型。首次轮播尝试因 harness 错用既有 `batch_index=1` 命中 `batch_conflict`，未发起模型请求，随后用 batch 2 重试成功。
