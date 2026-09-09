# AI 创意工作台当前状态交接

日期：2026-09-06

## 交接目的

本文档用于下一次对话直接接手仓库。当前工作重点是 AI v2 正式入口、启动器/代理桥、旧 v1 清理和真实 smoke 结果。除本文档外，先读 `AGENTS.md`、`progress.md`、`docs/project-rules/项目代码地图.md`、`docs/project-rules/operations.md` 和 `docs/ai-rebuild-master-plan.md`。

## 仓库与工作树

- 仓库：`D:\code\ai_creative_studio`
- 分支：`codex/tag-accordion-prototype`
- 基线 HEAD：`1bb6dd1`
- 当前工作树有大量既有未提交修改；不要 `reset --hard`、`checkout`、批量覆盖或删除。
- 不提交工作树，除非用户明确要求。
- 不修改 `chat2api/.env`，不输出 Token、Cookie 或代理密码。
- 不删除真实数据库、图片、上传文件或历史 scratch 证据。

## 正式运行链路

启动器：`launcher.py`

1. 启动器读取 `chat2api/.env`，构造子进程环境。
2. `_prepare_proxy_environment()` 保持 ClipProxy 经本机 Clash HTTP `7897` 的代理桥；固定代理时临时使用 `127.0.0.1:7896`。
3. 子进程启动 `chat2api/main.py`，网关监听 `127.0.0.1:8780`。
4. 子进程启动 `python -m creative_studio.app`，网页监听 `127.0.0.1:8775`。
5. 启动器显式传递：
   - `CREATIVE_STUDIO_AI_GATEWAY_URL=http://127.0.0.1:8780`
   - `CREATIVE_STUDIO_AI_API_KEY=local-chatgpt-gateway`
   - `CREATIVE_STUDIO_AI_MODEL=gpt-5-6-mini`
   - `CREATIVE_STUDIO_AI_CONTROL_TOKEN`（来自本机 `.env`）
   - `CREATIVE_STUDIO_AI_V2_LIVE=1`
6. 启动器会移除继承环境中的 `WEB_ERP_AI_*` 变量。

当前独立网关默认端口也已统一为 8780；`chat2api/README.md`、`chat2api/config.py`、`chat2api/routes_session.py` 的旧 ERP/8700 文案已修正。

## AI v2 生产入口

正式业务代码只在 `src/creative_studio/ai_v2/`：

- `application.py`：v2 门面和显式模型注入。
- `narrative.py`：叙事类文字生成，每批 5 套。
- `static_visual.py`：静态展示类文字生成，每批 3 套。
- `carousel_visual.py`：轮播规划，每批 3 套，按固定或 AI 决定的帧数生成计划。
- `image_worker.py` / `session.py` / `store.py`：图片状态、会话游标、重试和持久化。
- `http_api.py`：`/api/v2` 路由。
- `projection.py`：公开 DTO，禁止暴露 `image_prompt`、会话 ID 和供应商游标。
- `input_contract.py`：只接受 `task_description`、`aspect_ratio`、`creative_tags` 三个顶层字段。

生产 Prompt registry：`config/ai_v2/prompts/registry.json`。当前三份 Prompt 为 `lifecycle=production`，各自绑定唯一 canonical caller：

- narrative -> `NarrativeTextUseCase.generate`
- static -> `StaticTextUseCase.generate`
- carousel -> `CarouselTextUseCase.generate`

网关中的 `/v1/chat/completions` 和 `/v1/images/*` 是当前 v2 adapter 的传输协议，不是旧创意业务路由，不能误删。`web_proof.py` 中的 `legacy` 指 ChatGPT 上游协议兼容，也不是项目 v1 业务。

## 最近修复的真实 bug

症状：轮播、静态或叙事点击生成后显示“AI 请求失败”。

根因：项目保存的 `creative_tags` 包含 UI 编辑器专用字段：

```json
"visual_carousel_rounds": [
  {"index": 1, "mode": "base", "overrides": {}}
]
```

该字段是对象数组，但 v2 输入契约只接受字符串数组，因此服务端返回 `invalid_type`。前端未映射该错误码，显示了默认错误文案。8775/8780 当时均正常监听，根因不是端口。

修复内容：

- `static/app.js` 新增 `collectGenerationTags()`，生成请求移除 `visual_carousel_rounds` 和非字符串标签。
- `src/creative_studio/ai_v2/input_contract.py` 在服务端输入边界忽略 `visual_carousel_rounds`，兼容旧页面和其他客户端。
- `tests/test_ai_v2_input_contract.py` 增加对象轮次元数据回归测试。

## 最近真实 smoke 证据

真实文字测试使用启动器环境和驻留代理桥；没有调用图片模型：

- 叙事项目 `21`：成功，`run_id=11`，约 11 秒。
- 静态项目 `31`：成功，`run_id=12`，约 14 秒。
- 轮播项目 `12`：成功，`run_id=13`，约 10 秒。
- 三次公开结果扫描均未发现 `image_prompt`、`conversation_id`、`parent_message_id`、`session_id`。

第一次轮播尝试因 smoke harness 错误复用了已有 `batch_index=1`，命中 `batch_conflict`，没有发起模型请求；改用下一批次后成功。

真实图片 smoke 的既有证据：

- 静态图片成功，`attempt_id=7`，方案 `19`。
- 真实图片隔离评测目录：`.scratch/ai-v2-real-image-eval-20260906/`。
- 旧图片评测 scratch 中存在冲突证据，不要把旧混合报告当作新的质量结论。

## 验证状态

最近验证结果：

- `.venv` 全量 unittest：184 项通过。
- AI v2 定向测试：110 项通过。
- 启动器/网关定向测试：47 项通过。
- `python -m creative_studio.ai_v2.release_gate`：`v2-contract`、`compileall`、Node、diff-check、boundary 均 `ok`。
- `node --check static\\app.js`：通过。
- `python -m compileall -q src chat2api`：通过。
- `git diff --check`：通过。

运行测试时使用项目虚拟环境，不要用系统 Python：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
& .venv\Scripts\python.exe -m unittest discover -s tests -q
node --check static\app.js
& .venv\Scripts\python.exe -m compileall -q src chat2api
git diff --check
```

## 当前未完成或已明确忽略

- `390x844` 的真实浏览器 viewport 检查：用户已决定暂不处理；当前 Codex 会话只有不可调 viewport 的 In-app Browser。
- 耗时和 trace ID 的数据库补录：用户稍后会增加日志和数据库字段，再补数据。
- 移动端登录后完整 UI 检查：随移动 viewport 项一起暂不处理。

桌面 `1280x720` 已验证：步骤流、项目抽屉、三套方案、历史结果可见；`scrollWidth=1265`、`clientWidth=1265`，无横向溢出，控制台无 error。

## 运行数据与端口边界

- `data/creative_studio.db` 是真实运行库；本轮真实文字 smoke 已写入 run 11、12、13。
- `data/images/`、`data/uploads/` 是真实运行数据。
- `8775` 和 `8780` 若已有监听，先确认进程属于本项目，再决定是否停止；不要误杀用户已有服务。
- `7897` 是外部 Clash 监听，不属于本项目。
- 真实 smoke 前必须使用 launcher 的 `_prepare_proxy_environment()`，保持代理桥生命周期直到调用完成。
- 三类文字 smoke 不自动触发图片；图片测试必须单独授权。

## 下一对话建议顺序

1. 先读本文件和 `AGENTS.md`，执行 `git status --short --branch`。
2. 检查 8775/8780 进程归属和 `.env` 是否存在，不打印敏感值。
3. 若继续真实 AI 调用，明确项目、调用次数和是否允许图片，再走 launcher 代理桥。
4. 若处理日志，先设计 trace/duration 字段和脱敏规则，再写迁移、测试和公开 DTO 边界。
5. 完成任何修改后跑 `.venv` 全量测试、Node、compileall、diff-check，并追加 `progress.md`。

## 重要安全边界

- 不开放局域网或公网。
- 不修改 `chat2api/.env`、Token、Cookie 或代理配置，除非用户明确授权。
- 不把 `image_prompt`、会话 ID、供应商 job ID 或绝对本地路径返回给浏览器。
- 不删除旧数据库表；旧表只作为历史数据保留，当前代码不创建、不读取、不迁移。
- 不把 deterministic fake 或 contract gate 说成模型质量通过。
