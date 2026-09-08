# AI v2 多轮图片继续生成故障交接

日期：2026-09-06

## 目标

修复并真实验证同一个会话内的多轮图片生成链路：首帧生成成功后，点击“继续生成”必须在同一会话中创建下一帧任务，页面显示真实进行中状态、收到结果，并且第 2、3 帧可以连续提交。

## 用户报告

- 点击“继续生成图片”后立即显示完成/失败提示。
- 会话里看不到新的用户消息或图片任务。
- 新建任务也会出现相同现象。
- 多次重启网页、重试无效。
- 用户已手动登录管理员账号，要求下一会话直接查日志并修复。

## 当前已确认事实

仓库：`D:\\code\\ai_creative_studio`

正式服务由 `launcher.py` 启动，并必须经过启动器代理桥：

- 代理桥：`7896`
- 创意工作台：`8775`
- AI 网关：`8780`
- 外部 Clash：`7897`，不属于本项目

截至本次交接：

- 登录 session `id=53`，管理员用户仍 active。
- 浏览器当前 URL：`http://127.0.0.1:8775/`。
- 当前网页项目为 `project=74`，只有定位表单保存记录。
- 项目 74 没有 `run`、`scheme` 或 `attempt`。
- 最近一次网页操作只产生了 `PUT /api/projects/74`，没有产生：
  - `POST /api/v2/projects/74/generate`
  - 图片生成 POST
  - 新的 AI run
- `gateway.log` 目前只有持续的 `/api/v2/queue` GET；`web.log` 无 stdout 内容。
- 旧方案 `105/106/107` 的 attempt `24/25/26` 成功，但来自此前直接后端调用，不能作为网页真实点击验证。

结论：当前阻塞点发生在浏览器前端“确认定位/生成方案”或“继续生成”点击到 API 调用之间；不能先假定是图片供应商、端口冲突或代理失败。必须先证明点击后是否进入前端 handler、是否发出 generate/continue 请求。

## 已完成的相关改动

- `static/app.js`
  - 单帧提交前刷新历史，发现旧成功 attempt 时避免重复 POST。
  - 继续生成前刷新历史，按真实 attempt 状态选择下一帧。
  - 生成标签时过滤 `visual_carousel_rounds` 等 UI 编辑器对象字段。
- `static/index.html`
  - 当前脚本版本：`app.js?v=20260906-continue2`。
- `src/creative_studio/ai_v2/image_worker.py`
  - 改为按当前 attempt 的 provider job 轮询。
- `src/creative_studio/ai_v2/input_contract.py`
  - 服务端兼容旧页面的 `visual_carousel_rounds` 对象数组。

这些改动已有定向回归覆盖，但尚未完成“浏览器真实点击 -> 同一会话多轮图片”的端到端证明。

## 下一会话必须做的事

1. 先读本文件、`AGENTS.md`、`progress.md` 和当前工作树；不要 reset、checkout、删除数据库或 scratch 证据。
2. 确认 7896/8775/8780 进程归属，保留 launcher 代理桥，不修改 `chat2api/.env`。
3. 开启可脱敏的网页请求/前端事件日志，重点记录：
   - 定位页最终按钮 click 是否触发。
   - `generate` 请求的 URL、method、status、响应错误码。
   - 首帧成功后“继续生成”按钮的 click、目标 frame、attempt 创建结果。
4. 用浏览器真实操作创建一个新轮播项目，选择 3 屏，完成定位并点击最终生成；不要用脚本直接调用后端冒充网页测试。
5. 生成首帧后，分别点击继续生成第 2、3 帧，确认每轮：
   - 页面出现新的进行中状态；
   - 网关收到图片 POST；
   - 数据库新增正确 `attempt`，而不是返回旧成功 attempt；
   - 会话/历史中出现对应的新轮次。
6. 若按钮 click 有日志但没有 POST，继续查前端状态机、事件冒泡、按钮 disabled/loading 条件和异常吞掉位置；若有 POST 但无 attempt，再查后端幂等键、batch/frame 游标和 provider job 轮询。
7. 修复后至少运行：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
& .venv\\Scripts\\python.exe -m unittest discover -s tests -q
node --check static\\app.js
& .venv\\Scripts\\python.exe -m compileall -q src chat2api
git diff --check
```

## 重要边界

- AI 请求必须走 launcher 的 `_prepare_proxy_environment()` 代理桥。
- 不打印账号密码、Token、Cookie、代理凭证或完整请求体中的敏感字段。
- 不修改 `chat2api/.env`。
- 不删除或恢复真实数据库、图片、上传文件和已有 scratch 目录。
- 不把 direct/backend smoke 结果称为浏览器端到端通过。
- 完成后追加 `progress.md`，记录真实请求证据和 attempt/run 编号。

## 建议的第一条排查命令

```powershell
Get-NetTCPConnection -State Listen -LocalPort 7896,8775,8780 |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

随后查看当前服务日志、浏览器 Network/console，并对照 `data/creative_studio.db` 中 project 74 是否出现新的 run。只有看到网页真实发出 generate/continue 请求，才进入图片供应商层排查。
