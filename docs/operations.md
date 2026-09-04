# 运维手册

## 当前边界

当前默认只允许本机访问：网页服务监听 `127.0.0.1:8775`，AI 网关监听 `127.0.0.1:8780`。网页已有登录和项目归属控制，备份工具和临时恢复演练已具备，但仍不具备正式多人部署所需的自动调度、外部限流和公网安全能力。此前的局域网共享已撤回；再次开放局域网或公网必须单独走高风险变更卡，不得只修改监听地址。

注意：当前工作树中 `launcher.py` 的 `WEB_BIND_HOST = "0.0.0.0"` 是用户已有未提交修改，不能视为本手册默认，也不能在本路线中擅自回退或继续扩大暴露范围；启动前应由负责人确认监听边界。

## 启动

应用在 HTTP server bind 前加载 `config/prompts/registry.json`，校验 prompt 文件路径、模板
变量/hash、production contract 映射和生命周期；校验失败时启动终止。叙事生产项当前为
`creative.narrative.generate@v6`，旧 v5 仅作为 retired inventory。旧 `WEB_ERP_AI_*_PROMPT_PATH`
仅作兼容输入，叙事已完成 Phase 2 切换，非轮播静态展示已切换到
`creative.visual.static.generate@static-v1`，轮播使用
`creative.visual.carousel.plan@visual-carousel-v1` 和 `CarouselVisualGeneration`；该版本由一次共享 planner
直接产出每套私有首帧指令，后续画面由后台 operation 按锁定路线编排。旧静态
`creative.visual.static.generate@visual-v2.3` 仅保留在 registry 的 retired inventory；历史行通过公开投影兼容读取，不能作为新 caller，也不会再执行旧 prompt。

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

## 静态展示生成边界

非轮播展示生成从 `StaticVisualGeneration` 进入 `StaticVisualResult.v1` 校验；一批固定三案，成功后为每案创建一个首图任务。`generation_service.py` 通过
`StaticVisualImageRequest` 把画幅、私有指令和稳定 request id 交给图片队列。canonical 正文写入
`generations.items_json` 和 `visual_items.content_json`，私有
`image_generation_instruction` 只写入 `visual_items.image_prompt` 和受控图片队列，静态方案不写入
`display_frames`。浏览器 history/status/adopt 由 `StaticVisualPublicDTO.v1` 白名单投影，不能包含私有图片指令、完整模型响应、本地路径或 gateway job id。

本阶段的 registry、临时 SQLite、fake model/image runner、参考资料边界和前端 canonical renderer 已通过当前 `254` 项 deterministic unittest，以及 Node 语法和 Python compileall 检查；真实 AI、图片网关、认证浏览器、真实数据库写入和图片质量未验证。遇到这些需求时，先建立独立变更卡，不要直接对 `data/` 或 `chat2api/.env` 操作。

## 轮播后台 Operation

轮播继续接口 `POST /api/visual-items/{id}/continue` 在首图成功后创建持久化
`carousel_operations`，立即返回 HTTP `202`、`operation_id` 和方案公开 DTO。前端随后轮询
`GET /api/visual-items/{id}/operation/{operation_id}`，逐帧状态仍以
`GET /api/visual-items/{id}/frames/status` 为准。operation 的公开状态为 `queued`、`running`、
`completed`、`blocked` 或 `failed`，只暴露安全进度和错误摘要。

后台 coordinator 使用 lease token 和 heartbeat 独占 operation。每次图片成功会在同一事务中提交
图片 artifact、frame 状态、方案会话游标和 operation revision；旧 worker 的 token 或 attempt 不匹配时
不能覆盖新状态。lease 过期恢复只回收明确失活的 operation，并把崩溃 worker 遗留的当前
`generating` 帧重置为 `pending`，已成功帧不会重复生成。两次图片失败后 operation 进入 `blocked`，
保留 frame 错误供人工重试；不会删除 operation 或生成失败记录。

轮播 v1 的流程决策见 [`docs/adr/0003-carousel-v1-background-operation.md`](adr/0003-carousel-v1-background-operation.md)。
真实 AI、图片网关、认证浏览器和多进程生产竞态仍未验证；当前测试全部使用 deterministic fake。

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

截至 2026-09-04，对默认运行库执行过一次只读 dry-run，结果为 `scanned_rows=3`、`changed_rows=2`、`private_field_occurrences=6`、`invalid_json_rows=0`、`unknown_kind_rows=0`。因此当前运行库仍需要单独的备份、恢复演练和历史 scrub 变更卡；本次未执行 `--apply`，也未写入真实数据。

Phase 5 临时副本恢复演练已由 `tests/test_projection_scrub.py` 覆盖：副本先 dry-run，再使用新 backup
apply；从 backup 恢复后再次 apply，最后 dry-run 达到 `changed_rows=0` 和
`private_field_occurrences=0`。演练只使用临时目录，不代表真实运行库已经迁移。

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
