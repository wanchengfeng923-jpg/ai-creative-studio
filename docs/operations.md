# 运维手册

## 当前边界

当前默认只允许本机访问：网页服务监听 `127.0.0.1:8775`，AI 网关监听 `127.0.0.1:8780`。网页已有登录和项目归属控制，但仍不具备正式多人部署所需的自动备份、恢复演练、外部限流和公网安全能力。此前的局域网共享已撤回；再次开放局域网或公网必须单独走高风险变更卡，不得只修改监听地址。

## 启动

应用在 HTTP server bind 前加载 `config/prompts/registry.json`，校验 prompt 文件路径、模板
变量/hash、production contract 映射和生命周期；校验失败时启动终止。旧 `WEB_ERP_AI_*_PROMPT_PATH`
仅作兼容输入，Phase 2/3/4 完成对应切换后删除。

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

## 当前手动备份

当前尚未实现自动备份。需要备份时：

1. 停止网页和网关。
2. 将 `data/creative_studio.db`、`data/images/`、`data/uploads/` 复制到带日期的独立备份目录。
3. 不复制或明文散落 `chat2api/.env`；令牌单独放在受保护的位置。
4. 重新启动后，用备份目录复制到临时位置做一次读取检查，不要直接覆盖当前数据。

多人内网版本上线前，必须改成自动备份，并至少恢复一份备份验证数据库、项目记录和图片都能打开。

## 历史公开投影 scrub

Phase 0 提供 `creative_studio.projection_scrub`，用于统计或重建旧 `generations.items_json` 与 `adoptions.snapshot_json` 的公开投影。默认模式只读；工具会通过 SQLite `mode=ro` 打开目标库，不写数据，也不创建备份。

先在仓库根目录执行真实运行库的只读 dry-run：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m creative_studio.projection_scrub --database data\creative_studio.db
```

输出中的 `scanned_rows` 是检查行数，`changed_rows` 是重建后会变化的行数，`private_field_occurrences` 是旧 JSON 中命中的私有字段次数，`invalid_json_rows` 是无法安全重建的行数，`unknown_kind_rows` 是 recommendation kind 不在 `narrative`/`visual` 范围内的行数。只有 `applied=false` 才是 dry-run；该命令不得改为带 `--apply` 的真实库命令。

需要验证写入时，只操作临时副本，并让工具另建一个不存在的 backup 文件：

```powershell
New-Item -ItemType Directory -Force .scratch\projection-scrub | Out-Null
Copy-Item -LiteralPath data\creative_studio.db -Destination .scratch\projection-scrub\creative_studio-copy.db
python -m creative_studio.projection_scrub --database .scratch\projection-scrub\creative_studio-copy.db
python -m creative_studio.projection_scrub --database .scratch\projection-scrub\creative_studio-copy.db --apply --backup .scratch\projection-scrub\creative_studio-before.db
python -m creative_studio.projection_scrub --database .scratch\projection-scrub\creative_studio-copy.db
```

`--apply` 在 `invalid_json_rows` 或 `unknown_kind_rows` 非零时会在创建 backup 和写入之前直接中止，不允许跳过问题行做部分重建。最后一次 dry-run 应报告 `changed_rows=0`、`private_field_occurrences=0`、`invalid_json_rows=0` 和 `unknown_kind_rows=0`。若任一检查不为零，停止处理并保留副本、backup 和输出供诊断，不要尝试绕过保护后修改真实库。

恢复演练同样只针对临时副本。保留 apply 后的副本作为对照，从 backup 创建另一个恢复文件，再重新 dry-run：

```powershell
Copy-Item -LiteralPath .scratch\projection-scrub\creative_studio-before.db -Destination .scratch\projection-scrub\creative_studio-restored.db
python -m creative_studio.projection_scrub --database .scratch\projection-scrub\creative_studio-restored.db
```

恢复文件的统计应与 apply 前的临时副本一致。工具硬拒绝直接 apply 仓库默认 `data/creative_studio.db`；本文档也不授权绕过该保护。若未来确需处理真实运行库，必须另行取得用户确认，停止服务，完成数据库、图片和上传目录的独立备份与恢复演练，再通过单独评审的迁移方案执行。

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
