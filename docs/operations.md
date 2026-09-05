# 运维手册

## 当前边界

当前默认只允许本机访问：网页服务监听 `127.0.0.1:8775`，AI 网关监听 `127.0.0.1:8780`。网页已有登录和项目归属控制，备份工具和临时恢复演练已具备，但仍不具备正式多人部署所需的自动调度、外部限流和公网安全能力。此前的局域网共享已撤回；再次开放局域网或公网必须单独走高风险变更卡，不得只修改监听地址。

网页默认只绑定 `127.0.0.1`。如需局域网或公网访问，必须另开高风险变更卡并同时完成认证、HTTPS、限流、防火墙和回滚评审；不得只修改监听地址。

## 启动

AI v2 Prompt registry 位于 `config/ai_v2/prompts/registry.json`。当前三份 Prompt 均为
`candidate` 且 `caller=null`；网页组合根默认构造 deterministic candidate text/image
models，不连接真实网关。只有经过独立审批并显式设置 `CREATIVE_STUDIO_AI_V2_LIVE=1`，
才会通过保留的 `chat2api` 构造文字和图片 adapter。
1. 确认 `chat2api/.env` 存在，并且令牌仍有效。
2. 双击 `启动AI创意工作台.bat`，等待启动控制台出现。
3. 在“登录配置”中填写 Access Token 或 Session Cookie，点击“保存配置”；代理配置请使用独立的“网络代理工作台”。
4. 点击“启动”；控制台会拉起本项目自己的网关和网页，并自动打开 `http://127.0.0.1:8775/`。
5. 可在控制台点击“检测连接”，或访问 `http://127.0.0.1:8775/api/health` 和 `http://127.0.0.1:8780/v1/models`。

### 配置固定 ISP 代理

在启动控制台点击“网络代理工作台”，或单独运行 `python proxy_workbench.py`。填写代理商提供的协议、地址、端口和可选账号密码，点击“测试出口 IP”确认公网出口，再点击“保存代理”。测试使用与网关相同的 `curl_cffi` 客户端，兼容 HTTP/HTTPS/SOCKS5；配置写入 `chat2api/.env` 的 `PROXY_URL`，不会与登录凭据混在一起；保存后必须重启 AI 网关。

启动器会原样保留已配置的 ClipProxy 地址，确保 Chat2API 的最终出口仍是你设置的固定 IP，不会被普通 Clash 节点替换。没有配置 `PROXY_URL` 时，才会读取本机 Clash 配置中的 `mixed-port`、`socks-port` 和 `port`，自动识别可用的 HTTP/SOCKS5 入口；也可用 `CHAT2API_CLASH_PORT` 和 `CHAT2API_CLASH_PROTOCOL` 覆盖。配置固定代理且 Clash 可用时，启动器会临时占用本机 `7896` 作为转发入口，停止网关后自动释放。

代理工作台的“测试出口 IP”与网关启动使用同一条选择逻辑：已配置 ClipProxy 且 Clash 可用时，会启动只监听 `127.0.0.1:7896` 的轻量转发器，让 ClipProxy 经 Clash 出站后再探测固定出口；没有可用 Clash 时才直连 ClipProxy。测试结束会自动停止转发器，不会留下监听进程。

代理密码不会写入日志或界面摘要。不要把包含密码的完整代理 URL 发给他人或提交 Git。若清除代理并重启网关，ChatGPT 请求将恢复直连。

迁移到新电脑时重新填写 ClipProxy 信息并测试即可；启动器不会绑定旧电脑的节点 IP 或端口。需要本机运行提供 HTTP/SOCKS5 入口的 Clash/Mihomo，转发器会自动使用当前入口和当前节点。

只填写 Session Cookie 时，启动控制台会在网关就绪后自动请求 `/v1/session` 换取 Access Token，并将轮换后的值保存到本机 `.env`。这依赖 Cookie 仍有效和 ChatGPT 网页接口可访问。

## 停止

在控制台点击“停止”或关闭窗口会停止本次拉起的网页和网关进程。更新代码或配置前，应先确认 `8775` 和 `8780` 已停止，再进行备份和替换。

## 当前数据位置

| 数据 | 位置 | 说明 |
|---|---|---|
| 项目和历史 | `data/creative_studio.db` | SQLite 运行库 |
| AI 图片 | `data/images/` | 按生成记录和视觉项分目录 |
| 参考文件 | `data/uploads/` | 用户上传的本地参考文件 |
| AI 令牌 | `chat2api/.env` | 敏感配置，不进 Git |

## 备份与恢复

仓库现在提供可重复的 `creative_studio.backup` 工具，但尚未安装定时任务；调度仍需由部署负责人按发布变更卡配置。默认命令只读检查数据库、图片和上传目录，不创建输出：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m creative_studio.backup --dry-run --output .scratch\backup-smoke
```

执行实际备份前停止网页和网关，并使用独立、带日期的空目录：

```powershell
python -m creative_studio.backup --database data\creative_studio.db --images data\images --uploads data\uploads --output .scratch\backup-2026-09-04
```

工具会保存 `manifest.json`、SQLite 在线备份和图片/上传文件 SHA-256。恢复先写入同级临时目录，
校验 manifest、SQLite 可读性以及 `project_files`/成功图片引用完整性，成功后才切换为目标目录；
失败不会留下半成品目标目录。恢复只能写入新目录或空目录：

```powershell
python -m creative_studio.backup --restore-from .scratch\backup-2026-09-04 --target .scratch\restored-2026-09-04
```

JSON 结果中的 `verified=true` 和 `references_verified=true` 必须同时出现；manifest 路径穿越、重复
路径、非法 SHA-256、文件缺失或数据库引用缺失都会拒绝恢复。

保留策略目前是只读计划，不会自动删除用户备份。部署负责人可按变更卡查询“保留最近 N 份”计划：

```powershell
python -m creative_studio.backup --retention-root .scratch --keep-latest 7
```

输出的 `keep`、`eligible_for_removal` 和 `invalid` 目录必须人工复核；仓库没有默认删除命令，
避免调度器误删唯一可恢复副本。

不要复制或明文散落 `chat2api/.env`；令牌单独放在受保护的位置。恢复演练通过后仍需对项目、图片和上传引用做只读 smoke，禁止直接覆盖当前运行目录。多人内网正式上线前，必须把该工具接入受控调度器，设置保留策略、失败告警，并至少完成一次跨目录恢复。

## AI v2 运行边界

正式 AI 入口只使用 `/api/v2`。请求只接受 `task_description`、`aspect_ratio`、
`creative_tags` 三个业务字段；项目文件和产品证据字段不进入 v2。文字生成同步返回，
静态方案首次点击才创建图片会话，轮播每次点击只推进一帧。公开响应不包含 Prompt、
execution、会话游标、供应商 job id、本地路径、完整响应或堆栈。

每批文字使用一个新的文字 session，最多一次模型调用。每个展示方案最多创建一个图片
session，轮播同一方案的全部帧复用该 session。图片重试必须先读取本地 attempt 并向供应商
对账：供应商成功时完成原 attempt，仍在工作时重新挂接，只有明确终态失败才在同一 session
内创建新 attempt；未知、超时、断开或 5xx 不得创建第二个 session。

旧 `/api/projects/{id}/generate`、`/api/visual-items/*` 和旧采用接口返回 404。根包旧 AI
模块、Prompt、v1 评测资产和仓储方法已删除，不存在 fallback、双写或双读。

## 历史数据库兼容

`StudioRepository` 新建数据库时只创建用户、会话、审计、项目和项目文件表。
`SqliteAiV2Store` 在同一数据库中创建独立的 `ai_v2_*` 表。已有数据库中的
`generations`、`visual_items`、`display_frames`、`carousel_operations`、
`adoptions` 仅作为历史数据原样保留；当前初始化不创建、迁移、读取或删除这些表。

`creative_studio.backup` 继续只读检查历史 `visual_items` / `display_frames` 中标记成功的
图片路径，确保旧数据库备份仍能发现缺失文件。这项兼容不恢复旧 AI 运行时。不要手工 DROP
旧表；任何历史数据归档或删除都必须另开高风险变更卡、先备份并完成恢复演练。

## AI v2 验证

代码或 Prompt 变化后运行：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -q
python -m unittest discover -s tests -p "test_ai_v2_*.py" -q
node --check static\app.js
node --check static\ai-v2\app.js
python -m compileall -q src chat2api
python -m creative_studio.ai_v2.release_gate
git diff --check
```

release gate 的 deterministic 结果只证明 contract、schema、隐私和调用预算边界；真实模型
质量与供应商稳定性仍需单独审批和受控评测。
## 故障处理

### 账号初始化与会话

- 首次部署使用 `PYTHONPATH=src python -m creative_studio.auth_cli init-admin --username <name> --password-stdin`，通过标准输入提供至少 3 位密码；公网环境建议使用更长的随机密码，命令不会打印密码。
- 也可仅在首次启动时设置 `CREATIVE_STUDIO_BOOTSTRAP_USERNAME` 与 `CREATIVE_STUDIO_BOOTSTRAP_PASSWORD`。数据库已有任意账号后，这两个变量不会创建或覆盖账号。
- 管理员在网页中管理普通账号。停用或重置密码会立即撤销该账号的全部会话；重置密码只在响应中显示一次，随后必须修改密码。
- 备份数据库前先停止服务；升级前先复制数据库到临时路径并验证迁移，禁止直接覆盖运行库。

### 页面打不开

- 检查启动窗口是否仍在运行。
- 检查端口 `8775` 是否被其他程序占用。
- 访问 `/api/health` 判断是网页服务问题还是浏览器问题。

### AI 生成失败

- 先检查 `8780` 是否监听。
- 再访问 `/v1/models`，确认网关和令牌可用。
- 查看启动窗口错误，不把令牌、完整提示词或完整模型回复发到群聊。
- 记录时间、项目名称、类型和错误类别；不要连续重复点击消耗额度。

### 图片一直排队

- 保留当前数据库和图片目录，不要删除队列记录。
- 重启服务前先保留备份；启动器会尝试恢复排队任务。
- 若仍失败，记录项目、视觉项和错误信息，作为变更卡或缺陷处理。

## 升级门禁

涉及数据库、端口、令牌、多人访问、自动启动、HTTPS、内网或公网时，先写变更卡，确认备份和回滚，再执行。当前文档不授权任何生产或服务器写入动作。

## 临时内网撤回

若曾启用临时内网共享，停止共享后将 `launcher.py` 中 `WEB_BIND_HOST` 恢复为 `127.0.0.1`，删除防火墙规则 `AI创意工作台网页 8775（局域网）`，再重启网页服务。
