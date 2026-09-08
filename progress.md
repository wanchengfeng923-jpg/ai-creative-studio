# 当前项目进度（2026-09-04）

## 2026-09-06 公网使用手册

- 新增 `docs/deployment/public-startup-guide.md`，按 RDP 登录、启动器代理桥、控制令牌注入、网页公网启动、健康检查和下线步骤编写。
- 手册不包含 Token、Cookie 或代理密码；记录当前入口 `http://42.194.220.18:8775/`，AI 网关 `8780` 保持本机访问。

## 2026-09-06 公网 8775 验收

- 用户确认只开放网页 `8775`，不使用 `80`、域名或反向代理；AI 网关 `8780` 保持回环监听。
- 服务器网页已绑定 `0.0.0.0:8775`，本机 `/api/health` 返回 200；从外部对 `42.194.220.18:8775/api/health` 的只读请求返回 200。
- 该变更只调整监听地址和 Windows 防火墙规则，未修改工作台页面、数据库或 Prompt；公网暴露后的认证、HTTPS 和长期运维风险仍需后续处理。

## 2026-09-06 轮播主体锚点与公开字段贯通

- 轮播 Prompt 增加总视觉锚点、`core_subject`、逐帧主体/状态/结果约束，并移除对图片 Prompt 的过度短句化要求。
- 轮播 schema 将 `core_subject` 设为必填；公开投影和正式前端直接读取该字段，保留旧 `image_description` 兼容回退。
- 更新 Prompt registry 哈希、deterministic fake 和相关契约夹具；脚本缓存版本更新为 `20260906-carousel-core-subject1`。
- 验证：AI v2 定向 123 项、全量 unittest 198 项、Node 语法、compileall、`git diff --check` 通过；未执行真实 AI 质量评测或真实网页点击验证。

## 2026-09-06 部署步骤 0 确认完成

- 用户确认以本机项目及 `data/` 为权威迁移源，允许覆盖目标同名旧数据，并同意 `E:\AI-Creative-Studio\` 下 app/data/staging 目录规划。
- 实时部署记录已进入步骤 1 只读盘点；实际目录、任务、数据读写者和传输通道待核验，尚未上传、覆盖或修改服务器。
- 修正先前记录：用户只明确不需要正式域名，反向代理尚未决定；备份位置、保留期限和公网入口方案在后续步骤落实。
- 步骤 1：用户回传服务器检查结果，`E:\AI-Creative-Studio` 尚不存在；E 盘根目录、非系统任务及应用读写者仍待盘点，未创建目录或上传文件。
- 后续用户明确服务器为全新实例，要求跳过旧环境检查；已按此更新实时文档，不再要求旧应用、任务或旧数据库清单。
- 本机初步统计 `data/`、网关 images/job state 共 571133590 字节（约 545 MiB），尚非一致性快照；发现应用默认数据路径仍依赖代码目录，独立 E 盘数据路径需在打包前适配验证。本轮只读盘点和文档更新，未上传或迁移。
- 已完成路径配置切片：`CREATIVE_STUDIO_DATA_DIR` 注入工作台数据根目录，启动器同时预留网关图片与 job state 目录变量；定向测试、compileall、diff-check 通过。全量重跑受既有 carousel fixture/Prompt 不一致影响（`carousel-05` 和文本断言），未归因于本切片，发布包前需处理。
- 暂停制作发布包：当前工作树已有 Prompt registry production/candidate 断言冲突、Prompt 文案断言冲突和 `carousel-05` deterministic fake 评测冲突；需单独决定以当前生产 Prompt 更新测试，还是回到 candidate 基线。
- 用户确认以当前 production Prompt 为事实源；已更新 Prompt 断言、轮播帧数量归一化评测案例和 release gate 统计。全量 unittest 200 项、AI v2 release gate 124 项、compileall、diff-check 通过。
- 步骤 2：生成并恢复验证部署前备份，`verified=true`、`references_verified=true`；恢复库确认 3 用户（2 admin、1 user）。生成不含 `.env`/数据库/图片/上传文件的程序包，SHA-256 为 `6515DA374282A906BA4BF4CC6CEC69456EFA9479DEDC6919497BFD2034291178`。尚未上传服务器。
- 用户已将程序包解压到服务器 `E:\AI-Creative-Studio`；尚未启动、覆盖数据或注入敏感配置，等待服务器端只读结构核验。
- 服务器核验确认程序目录层级正确；根目录没有 `database`/`images`，业务备份应在暂存目录或其他层级，尚未创建正式 data 目录。

## 2026-09-06 图片网关瞬时失败处理

- 修正图片 provider unavailable/state unknown 的错误映射为可重试图片错误，HTTP 层返回 503 语义而不是不可重试的 400。
- 图片网关提交在同一 `request_id` 下增加一次短暂重试；网关请求键幂等，避免连接瞬断时重复创建供应商任务。
- `py_compile` 和 `git diff --check` 通过；现有静态/轮播定向测试受用户当前 Prompt deterministic fixture 变更影响，未作为本次改动通过证据。

## 2026-09-06 启动器单实例保护

- 核查未发现 Windows 启动项或计划任务自动启动本项目；重复服务来自启动器没有单实例保护，旧的系统 Python launcher 可与 `.venv` launcher 并存并各自拉起 8775/8780。
- `launcher.py` 增加 Windows 命名互斥锁；第二个启动器现在直接提示已有控制台，不再创建第二套网页/网关进程。
- `py_compile` 和 diff 检查通过；网关定向测试受当前 Prompt deterministic fixture 与 Windows 临时 SQLite 文件锁影响，未将失败归因于本次锁改动。

## 2026-09-06 轮播 Prompt 标签落地约束

- 在轮播 Prompt 输出格式前增加标签落地要求：主目标用户、玩家欲望、产品卖点和展示内容必须转化为具体主体、玩法状态和可见结果，标题与轮播主线保持一致，三套方案使用不同标签组合或观看方式。
- 已更新轮播 Prompt registry 哈希；registry 校验、Prompt registry/schema 定向测试 11 项通过，`git diff --check` 通过。

## 2026-09-06 静态/轮播公开字段补齐

- 根因：静态和轮播 Prompt/schema 未要求 `content_extensions`、`reference_sources`，公开投影和前端因此显示空字段。
- 修复：两类 schema、Prompt 示例、公开投影和 schema 测试已同步补齐这两个字段；Prompt registry 哈希已更新。
- 验证：schema、projection、registry 定向测试 15 项通过，Node 检查和 `git diff --check` 通过。

## 2026-09-06 轮播结果字段与图片入口修复

- 修复正式根页面读取 v2 轮播帧时使用旧字段导致画面路线内容为空的问题：统一映射公开的 `description`/`index` 字段。
- 修复轮播卡片首个图片按钮误调用静态方案 `/schemes/{id}/image` 的问题；现在按待生成帧调用 `/frames/{index}/image`，避免 `invalid_use_case`。
- 新增前端回归测试；定向 AI v2 测试 22 项、Node 语法检查和 `git diff --check` 通过。

## 2026-09-06 AI v2 生成并发排队显示

- 新增进程内 FIFO 生成队列，最多同时运行 6 个文字生成会话；第 7 个及之后的请求返回排队 ticket，并按提交顺序等待空闲槽位。
- 新增队列状态查询接口，公开 ticket 状态和队列位置；任务完成或失败都会释放运行槽位，不暴露会话 ID、供应商游标或 Prompt。
- 前端生成按钮增加“排队中 · 前面还有 N 个”状态，轮到任务后显示原有生成计时，完成后沿用现有历史刷新和错误提示。
- 验证：队列单元测试、AI v2 应用集成测试通过；待完成全量 unittest、Node、compileall 和 diff-check。

## 2026-09-06 建立实时部署记录

- 新增 `docs/deployment/live-deployment.md`，记录部署目标、软件/数据边界、分步门禁、验证证据和回滚原则。
- 当前只完成文档初始化；未执行服务器部署、端口开放、数据库迁移、生产数据覆盖或 `.env` 修改。
- 步骤 0 已确认目标为公网 Windows 单服务器、全量迁移并继续使用 SQLite；服务器地址、同事提供的端口用途、远程管理通道和开机自动启动仍待确认。
- 用户提供聊天截图：出现公网地址 `42.194.220.18:8775`，并提到已开放 `80`；当前仅记录为网页入口候选，尚未验证公网端口或 RDP 管理通道。截图中的 Token/Cookie 已遮挡，未读取或记录。
- 只读网络探测结果：`3389`、`5985` TCP 可达；`80`、`8775`、`5986` 不可达。尚未进行 RDP/WinRM 认证或远程命令往返。
- 用户确认已通过 Windows 自带远程桌面登录服务器；当前仅把 RDP 作为管理通道记录，尚未执行远程命令或上传。
- 服务器只读盘点：主机名 `10_10_2_15`，RDP/WinRM 监听于 `3389`/`5985`，工作台端口未监听；C 盘可用约 33.14 GB，E 盘可用约 99.89 GB。暂建议 E 盘作为应用与数据承载盘，待步骤 1 确认目录。

## 2026-09-06 生成失败修复：编辑器轮次元数据误入 v2 输入

- 根因：项目标签中的 `visual_carousel_rounds` 是 UI 编辑器对象数组，但 v2 `creative_tags` 契约只接受字符串数组；轮播、静态和叙事生成都会因此返回 `invalid_type`。8775/8780 当时均正常监听，非端口问题。
- 修复：前端生成请求过滤 `visual_carousel_rounds` 和非字符串标签；服务端输入边界同步忽略该编辑器专用字段，避免旧页面/其他客户端再次触发同一错误。
- 回归：当前项目 57 的真实保存输入归一化通过；全量 unittest 184 项通过，Node 检查通过。
- 按用户授权经启动器代理桥完成真实三类文字 smoke：叙事项目 21 run 11、静态项目 31 run 12、轮播项目 12 run 13 均成功，公开字段扫描无私有字段泄露，未调用图片。

## 2026-09-06 启动器与旧 v1 引用审查

- 核对 `launcher.py` -> `chat2api/main.py` -> `creative_studio.app`：启动器传递的网关、模型、控制令牌和 `CREATIVE_STUDIO_AI_V2_LIVE=1` 与组合根读取项一致，并主动移除旧 `WEB_ERP_AI_*` 环境变量。
- 未发现旧 `generation_service`、`ai_creative`、`model_client`、`image_jobs` 等生产模块或旧业务路由文件；旧 `/v1` 网关接口属于当前 v2 adapter 的传输协议，不是创意工作台 v1 业务路由。
- 修正 `chat2api/README.md`、`chat2api/config.py`、`chat2api/routes_session.py` 中残留的 ERP/8700 说明，独立启动默认端口统一为 8780。
- 启动器/网关定向测试 47 项、Node、compileall、git diff-check 通过。

## 2026-09-06 AI v2 cutover follow-up

- 复核真实数据库：项目 12 的 `run_id=8` 文字 run 成功，方案 19 的 `attempt_id=7` 图片任务成功；公开投影未暴露私有 prompt 字段。当前表结构不保存耗时或 trace id，因此这两项无法从历史记录补录。
- 本地根页面已打开并确认登录门；因没有可用生产账号密码，未进入登录后步骤流/项目抽屉/历史视图，未改账号或生产数据。
- live 环境关闭时 `create_application()` 返回稳定 `ai_not_enabled`，不会构造 candidate 假结果。临时网页进程已停止。
- 继续复核：`.venv` 下 AI v2 定向测试 110 项通过，release gate 的 v2-contract/compileall/Node/diff-check/boundary 均为 `ok`；全量测试仍仅因环境缺少 `curl_cffi` 导入失败。8775/8780/8791 均无监听，7897 为外部 Clash。
- 使用项目 `.venv` 重跑全量 unittest，184 项全部通过；确认此前错误仅由系统 Python 环境缺少 `curl_cffi` 引起。
- 使用本机账号完成桌面 UI 检查：步骤流、项目抽屉、三套方案与历史结果可见，1280x720 无横向溢出、控制台无 error；浏览器后端不支持动态视口调整，390x844 尚未验证。
- 追加响应式 CSS 静态复核：移动断点、`min-width:320px`、关键容器 `min-width:0` 和表格局部横向滚动规则均存在；未修改代码。

## 2026-09-05 AI v2 P0/P1 正式入口收口

### 已完成

- 按 `docs/superpowers/handoffs/2026-09-05-ai-v2-production-integration-handoff.md` 建立 `.scratch/ai-v2-production-integration/spec.md` 和 `docs/superpowers/plans/2026-09-05-ai-v2-production-integration.md`。
- P0 基线记录确认分支为 `codex/tag-accordion-prototype`、HEAD 为 `1bb6dd1`；修改前已停止明确属于本项目的 8775 网页进程和 8780 网关进程，未停止其他进程。
- 正式 composition root 在未设置 `CREATIVE_STUDIO_AI_V2_LIVE=1` 且没有显式测试文字模型时返回稳定 `ai_not_enabled` 配置错误，不再静默构造 candidate text/image model；显式 deterministic fake 注入和 live gateway 构造保持可测试。
- 根页面 `static/app.js` 现在解析 v2 `error_code`、`phase`、`retryable`、`trace_id`、`field_path`，映射为安全中文提示并附追踪 ID；生成成功后的 history 刷新失败和项目列表刷新失败分开提示，保留已返回的生成方案。
- 保持 Prompt registry 三项为 `candidate`、`caller=null`；未设置 live，未修改 `chat2api/.env`，未调用新的真实 AI/图片请求，未写入真实数据库、图片或上传目录。

### 验证

- `python -m unittest discover -s tests -q`：176 项通过。
- `python -m unittest discover -s tests -p "test_ai_v2_*.py" -q`：103 项通过。
- `python -m creative_studio.ai_v2.release_gate`：103 项通过；`v2-contract`、`compileall`、`node`、`diff-check`、`boundary` 均为 `ok`；报告仍为 `evidence_type=deterministic_fake`、`quality_claim=contract_only`、真实模型质量 `not-run`。
- `node --check static\\app.js`、`node --check static\\ai-v2\\app.js`、`python -m compileall -q src chat2api`、AI v2 boundary 和 `git diff --check`：通过。

### 未完成与下一步

- Prompt 审批、production caller、独立 production readiness gate、受控真实文字/图片评测和本机正式切换仍未执行。
- 下一步只能在用户分别确认 Prompt 评审结论与真实调用预算后进入 P2/P3；不得把 deterministic contract 证据表述为生产质量通过。

## 2026-09-05 清理旧 AI 测试

### 已完成

- 删除仅覆盖已退休旧生成服务、模型客户端、图片任务、旧提示词/Schema、旧视觉接口和旧正式页面的测试。
- 保留认证、项目与参考文件、仓储迁移/runtime 数据、通用评估和全部 AI v2 测试；应用 API 测试仅保留认证及通用数据错误映射。
- 修正公开投影哈希种子测试的子进程 `PYTHONPATH`，保持跨进程稳定性断言。

### 验证

- `PYTHONPATH=src python -m pytest -q`：202 项通过，1 条既有 Pydantic 弃用警告。
- `git diff --check` 通过；未修改生产源码或前端文件，未发起真实 AI 请求。

## 2026-09-05 AI v2 网关运行时审查修复

### 已完成

- 修复首次图片 POST 返回未知结果时遗留不可恢复 session/attempt 的问题；首次未知现在在本地建状态前返回可重试 503，重复请求保持同一供应商幂等键。
- 将 chat2api 普通 `failed` 和重启失败包络保持为 unknown；只有显式终态标记才允许在同一图片会话内创建新 attempt。
- 逻辑 `request_key` 保持稳定，供应商 `request_id` 按 attempt 编号区分；轮播续帧立即成功时正确递增已有 cursor revision。
- 生产 composition root 不再构造旧文字模型、旧图片 worker 或旧生成服务，旧生成 HTTP 路由已退休；三份 v2 Prompt registry 项分别指向唯一的用例 caller。
- 审查证据记录在 `.scratch/ai-v2-gateway-runtime/review-ledger.md`。

### 验证

- reviewer 红灯阶段：22 项定向测试中 9 failures、4 errors；修复后同一组 22 项全部通过。
- `python -m unittest discover -s tests -p 'test_ai_v2_*.py' -v`：78 项通过。
- 认证、认证刷新、项目 round-trip/search 和 v2 应用集成：20 项通过。
- 全量 `341` 项中 `329` 项通过；其余 `3 failures + 9 errors` 均为已退休旧 composition root/API 的历史测试，不恢复旧生产行为，留给正式切换清理删除或替换。
- Python compileall、v2 boundary 和 `git diff --check` 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

## 2026-09-04 AI v2 Task 0 冻结点与会话策略

### 已完成

- 建立 `.scratch/ai-v2-text-first-implementation/spec.md`，记录 `codex/tag-accordion-prototype` 分支、既有用户脏文件、三字段输入、文字/图片会话边界、重试对账、旧 AI 隔离、回滚和验收例子。
- 新增 `docs/adr/0005-ai-v2-boundary-and-session-policy.md`，固定每批一个文字会话、每方案一个图片会话、轮播帧共享会话、孤儿任务恢复和“只有明确终态失败才创建新 attempt”的规则。
- 在 AI v2 预览设计稿加入变更卡和 ADR 索引，并保留 Prompt 正文/真实评测/正式 caller 的单独审批门禁。

### 验证

- `git diff --check -- .scratch/ai-v2-text-first-implementation/spec.md docs/adr/0005-ai-v2-boundary-and-session-policy.md docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 1：建立 `ai_v2` 命名空间和零引用守卫；Task 2/3/6 在其通过后执行。

## 2026-09-04 AI v2 Task 1 边界守卫

### 已完成

- 新增独立 `src/creative_studio/ai_v2/` 命名空间和 `boundary.py`，扫描 v2 源码/静态资源/配置目录的旧 AI import、旧 API 路由和旧表名。
- 导出 `assert_ai_v2_boundary(root)` 与稳定 `AiV2BoundaryViolation`；实现不在导入时打开数据库或访问网络。
- 新增临时文件 red/green 测试，覆盖完整包导入、裸旧模块导入、旧路由/表名和 `dataclasses/json/sqlite3/requests` 中立依赖。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_boundary -v`：2 项通过。
- `python -m compileall -q src/creative_studio/ai_v2`：通过。
- `git diff --check -- src/creative_studio/ai_v2 tests/test_ai_v2_boundary.py`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 2：三字段输入标准化与批次指纹。

## 2026-09-04 AI v2 Task 2 三字段输入与 fingerprint

### 已完成

- 新增 `src/creative_studio/ai_v2/input_contract.py`，独立实现三字段 `AiV2Input`、空值/重复标签清理、任务长度和画幅枚举校验。
- v2 顶层未知字段（含产品证据/参考文件）和缺失字段直接拒绝；标签组名称开放，轮播控制标签保持在 `creative_tags`。
- 新增 `resolve_use_case()` 选择叙事/静态/轮播，新增稳定 SHA-256 `fingerprint()`，不引用旧 `normalize_creative_tags`。
- 新增 6 项定向测试，覆盖空任务、类型错误、资料字段拒绝、轮播判定和标签顺序稳定性。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_input_contract -v`：6 项通过。
- `python -m unittest tests.test_ai_v2_boundary -q`：2 项通过。
- `python -m compileall -q src/creative_studio/ai_v2`：通过。
- `git diff --check -- src/creative_studio/ai_v2 tests/test_ai_v2_input_contract.py tests/test_ai_v2_boundary.py`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 3：版本化 JSON Schema 与无依赖 schema runner。

## 2026-09-04 AI v2 Task 3 版本化 JSON Schema

### 已完成

- 新增 `src/creative_studio/ai_v2/schema.py`，提供 `load_schema(schema_id, version)` 和无第三方依赖的 `validate_json()`，支持计划要求的 Schema 子集和稳定 JSON path/reason code。
- 新增 `config/ai_v2/schemas/narrative-text-v1.json`、`static-text-v1.json`、`carousel-text-v1.json`；固定叙事 5×2×3、静态 3 案/单条图片 Prompt、轮播 3 案/2–5 帧。
- 轮播 runner 额外校验帧索引连续性及 `frames`/`image_prompts` 数量和索引一致；所有对象默认拒绝额外字段。
- 新增 5 项 schema 定向测试，覆盖缺字段、类型、数量、额外字段、轮播越序和 Prompt 对齐。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_schema -v`：5 项通过。
- `python -m unittest tests.test_ai_v2_schema tests.test_ai_v2_boundary -q`：7 项通过。
- `python -m compileall -q src/creative_studio/ai_v2`：通过；三份 schema JSON 解析通过。
- `git diff --check -- src/creative_studio/ai_v2 config/ai_v2/schemas tests/test_ai_v2_schema.py`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 4：Prompt 专项设计与评测资产；Prompt 正文保持候选，不接生产 caller。

## 2026-09-04 AI v2 Task 4 Prompt 设计与评测资产

### 已完成

- 新增 `docs/ai/ai-v2-prompt-design.md`，固定叙事/静态/轮播三种唯一任务、三字段数据区序列化、公开/内部一致性、单次调用失败策略和评测顺序。
- 新增 `config/evals/ai_v2/prompt-cases.jsonl`，共 30 个脱敏 case，叙事/静态/轮播各 10 个，覆盖空标签、画幅、2/3/4/5 屏、额外字段、私有字段、重复、空描述和供应商失败语义。
- 新增 `config/evals/ai_v2/expected-hard-constraints.json`，声明输入字段、三类输出数量、私有字段禁出、调用次数和失败策略。

### 验证

- JSONL/JSON 结构检查：30 cases、ID 唯一、每类 10 个、硬约束字段通过。
- `python -m unittest tests.test_ai_v2_boundary tests.test_ai_v2_schema tests.test_ai_v2_input_contract -q`：13 项通过。
- `git diff --check -- docs/ai/ai-v2-prompt-design.md config/evals/ai_v2`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 审批门禁

- Prompt 正文和 production caller 尚未获用户单独审批；Task 5 不接 production，候选设计和评测资产可继续供 deterministic fake 使用。

### 下一任务

- 可安全执行 Task 6（文字/图片端口与会话策略）及其后置 Task 7/8；Task 5 等待 Prompt 审批。

## 2026-09-04 AI v2 Task 6 模型端口与会话策略

### 已完成

- 新增 `src/creative_studio/ai_v2/model_ports.py`，定义 v2 私有 typed 文字/图片请求、会话游标、artifact、提交和对账结果。
- 新增 `session.py` 稳定图片会话/逻辑帧 request key；新增 `fakes.py` deterministic text/image adapter，支持工作中、成功、终态失败和未知对账状态，不联网、不读凭据。
- 新增 4 项会话测试，锁定每批一个文字会话、每方案一个图片会话、轮播同方案多帧复用会话和未知对账不新建会话。
- 修复并验证 Python `Protocol` 导入兼容性；边界守卫从仓库根目录扫描通过。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_session -v`：4 项通过。
- `python -m unittest tests.test_ai_v2_session tests.test_ai_v2_boundary -q`：6 项通过。
- `python -c "...assert_ai_v2_boundary(Path('.'))..."`：`v2 boundary ok`。
- `python -m compileall -q src/creative_studio/ai_v2`：通过。
- `git diff --check -- src/creative_studio/ai_v2 tests/test_ai_v2_session.py`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 7：v2 SQLite 存储与 additive migration。

## 2026-09-04 AI v2 Task 7 SQLite 存储与 additive migration

### 已完成

- 新增 `src/creative_studio/ai_v2/migrations.py`，只创建 `ai_v2_runs`、`ai_v2_schemes`、`ai_v2_frames`、`ai_v2_image_sessions`、`ai_v2_image_attempts`、`ai_v2_artifacts` 及索引。
- 新增 `src/creative_studio/ai_v2/store.py`，提供冻结 `RunRecord`/`ImageAttempt`/`ImageSessionRecord`、`AiV2Store` 协议、两批限制、canonical 方案/帧保存、图片 session/attempt 幂等和原子 artifact/cursor 完成。
- 失败运行记录保留；轮播越序、成功覆盖、旧 cursor/attempt 条件更新和重复 request key 均 fail-closed；本地 attempt 缺失但方案 session 存在时可恢复。
- 新增 7 项临时 SQLite 测试，显式确认没有创建旧表或写入旧 AI 数据结构。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_store -v`：7 项通过。
- `python -m unittest tests.test_ai_v2_boundary tests.test_ai_v2_input_contract tests.test_ai_v2_schema tests.test_ai_v2_session -q`：17 项通过。
- `python -m compileall -q src/creative_studio/ai_v2`：通过。
- `git diff --check -- src/creative_studio/ai_v2 tests/test_ai_v2_store.py`：通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 8：v2 公开投影；使用 v2 schema/store，不读取旧 `PublicResultMapper`。

## 2026-09-04 AI v2 Task 8 公开投影

### 已完成

- 新增 `src/creative_studio/ai_v2/projection.py`，从空对象重建叙事、静态、轮播公开 DTO；未知字段和 `execution` 不会透传。
- `public_image_state()` 只暴露稳定状态、attempt、可重试标记、安全错误码、operation id 和 `/api/v2/` 图片 URL；拒绝内部状态。
- 新增 4 项递归隐私测试，覆盖 Prompt、execution、conversation cursor、gateway job id、本地路径、完整响应、堆栈和未知字段。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_projection -v`：4 项通过。
- `python -m unittest tests.test_ai_v2_boundary tests.test_ai_v2_input_contract tests.test_ai_v2_schema tests.test_ai_v2_session tests.test_ai_v2_store -q`：24 项通过。
- `python -c "...assert_ai_v2_boundary(Path('.'))..."`：`v2 boundary ok`；compileall 和 diff check 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 5 仅实现候选 Prompt registry/compiler（不建 production caller）；随后继续 Task 9 前置模块。

## 2026-09-04 AI v2 Task 5 候选 Prompt registry/compiler

### 已完成

- 新增 `src/creative_studio/ai_v2/prompt_registry.py` 和 `prompting.py`，独立加载静态 v2 registry，校验原始 UTF-8 hash、三字段占位符、路径边界和生命周期。
- 新增 `config/ai_v2/prompts/registry.json` 及三份候选模板；三项均为 `candidate`、`caller=null`、每批最多一次模型调用。
- 编译器只做一次 `{{name}}` 字面替换，插入值中的 `$`、`${...}`、`{{...}}`、换行和 Unicode 不会二次解析；未知/缺失值 fail-closed。
- 新增 3 项 registry/compiler 定向测试。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_prompt_registry -v`：3 项通过。
- `python -m unittest tests.test_ai_v2_boundary tests.test_ai_v2_input_contract tests.test_ai_v2_schema tests.test_ai_v2_session tests.test_ai_v2_store tests.test_ai_v2_projection -q`：28 项通过。
- `python -c "...assert_ai_v2_boundary(Path('.'))..."`：`v2 boundary ok`；compileall 和 diff check 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置；未创建 production caller。

### 审批门禁

- Prompt 正文仍为候选，用户尚未批准生产接入；后续用例仅可由 deterministic fake/候选 registry 测试驱动。

### 下一任务

- Task 9A：叙事文字用例（先红测试）；随后 Task 9B/9C。

## 2026-09-04 AI v2 Task 9A 叙事文字用例

### 已完成

- 新增 `src/creative_studio/ai_v2/narrative.py`，独立使用候选 registry、typed text port、叙事 schema、v2 store 和公开投影。
- 每批只调用一次文字模型；JSON/Schema 错误直接将当前 run 标记失败并返回稳定 `model_output_invalid`，不做隐藏格式修复。
- 叙事成功固定 5 套、每套 2 钩子/每钩子 3 场景；空任务合法；失败重试和第二批都新建文字 session，不创建图片 session。
- 调整 v2 store 允许失败批次同 `batch_index` 重试，同时按不同批次限制最多两批。
- 新增 4 项叙事定向测试。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_narrative -v`：4 项通过。
- v2 全套（boundary/input/schema/session/store/projection/prompt registry/narrative）：35 项通过。
- 根目录 `assert_ai_v2_boundary(Path('.'))`：`v2 boundary ok`；compileall 和 diff check 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 9B：静态文字用例和按需首图入口。

## 2026-09-04 AI v2 Task 9B 静态文字与按需首图

### 已完成

- 新增 `src/creative_studio/ai_v2/static_visual.py`，独立完成三案文字生成、schema 校验、pending 公开投影和按需单图入口。
- 首次点击只创建方案唯一图片 session 和一条 attempt；重复点击复用；成功 artifact 锁定不可重生成。
- 终态失败重试先对账，明确失败后在原 session 内递增 attempt 并继续，不调用第二个 session；未知状态不盲目扩张。
- 补充 v2 store 的方案/帧/attempt 状态读取 seam；新增 4 项静态定向测试。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_static_visual -v`：4 项通过。
- v2 全套（含 narrative/static/store/session/projection/prompt/schema/input/boundary）：39 项通过。
- 根目录 `assert_ai_v2_boundary(Path('.'))`：`v2 boundary ok`；compileall 和 diff check 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 9C：轮播文字用例和逐帧图片入口。

## 2026-09-04 AI v2 Task 9C 轮播文字与逐帧图片

### 已完成

- 新增 `src/creative_studio/ai_v2/carousel_visual.py`，独立完成轮播一次规划、固定/AI 帧数校验、三案路线保存和公开投影。
- 固定屏数支持 2/3/4/5，缺数量或不匹配直接失败；后续帧不再调用文字模型。
- `request_frame()` 严格按序：首帧首次点击创建方案唯一图片 session，后续帧复用 cursor 并携带上一张成功 artifact 的真实 MIME；重复点击幂等，终态失败重试先对账再在原 session 内新 attempt。
- 新增 6 项轮播定向测试。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_carousel_visual -v`：6 项通过。
- v2 全套（boundary/input/schema/session/store/projection/prompt/narrative/static/carousel）：45 项通过。
- 根目录 `assert_ai_v2_boundary(Path('.'))`：`v2 boundary ok`；compileall 和 diff check 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 10：图片状态机与幂等规则。

## 2026-09-04 AI v2 Task 10 图片状态机与幂等规则

### 已完成

- 新增 `src/creative_studio/ai_v2/image_state.py`，提供纯函数 `can_start_static`、`can_start_frame`、`transition` 和 `stable_image_key`。
- 图片状态只允许 pending/generating/success/failed；成功再启动返回 `image_already_successful`，其他非法迁移返回 `invalid_image_transition`。
- 轮播必须满足当前帧 pending/failed、所有前序 success；成功图片在逻辑帧键内锁定。
- 新增 4 项状态机测试，覆盖成功/失败重试、越序阻断、稳定键和稳定错误码。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_ai_v2_image_state -v`：4 项通过。
- v2 全套定向回归：49 项通过。
- 根目录 `assert_ai_v2_boundary(Path('.'))`：`v2 boundary ok`；compileall 和 diff check 通过。
- 未调用真实文字/图片 AI，未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置。

### 下一任务

- Task 11：v2 图片 Adapter、worker 与供应商会话对账。

## 2026-09-04 AI v2 文字优先独立预览

### 本次完成

- 用户批准 `docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md` 用于纯前端预览；规格新增旧 AI 冻结、新 AI 零引用、零回退、零双写/双读、零兼容串联和入口级单向切换硬不变量。
- 新增 `.scratch/ai-v2-text-first-preview/index.html` 自包含预览；顶层仍只有叙事类和展示类，展示类内部再切换静态与轮播。
- 使用固定假数据呈现叙事 5 套、静态 3 套、轮播 3 套；叙事不含图片，展示类默认只显示文字，图片由用户按需触发。
- 纯 reducer 实现静态一次生成、成功锁定、失败重试，以及轮播逐张解锁、失败阻断和成功后继续；DOM 层不参与状态决策。
- 预览不加载生产 JavaScript/CSS、旧 AI 资源或远程资源，不调用生产 API，不读写数据库，也未修改正式页面。

### 验证

- 内联 JavaScript 语法检查通过；结构标签数量平衡。
- 静态隔离检查确认 `fetch`、XHR、WebSocket、外链脚本/样式/图片和生产模块引用均为 0。
- reducer 定向行为检查通过：静态成功锁定、轮播越序拒绝、失败不解锁后续、失败重试成功后解锁下一张。
- 假数据数量检查通过：叙事 5 套、静态 3 套、轮播 3 套。
- 浏览器工具受安全策略限制，不能打开本地 `file://` 页面；本次未完成 `1280x720`、`390x844` 视觉截图、真实点击和控制台检查，需由用户打开预览后确认。
- 未调用真实文字 AI、图片 AI、生产接口或数据库；未修改 `chat2api/.env`、真实运行数据或 `launcher.py`。

## 2026-09-04 修复视觉结果轮询闪烁与详情收回

### 本次完成

- 定位到图片状态轮询每 2 秒重建结果卡片，导致原生 `details` 展开状态丢失；同时 `Date.now()` 图片缓存参数使同一图片被浏览器反复当作新资源加载。
- 轮询重绘前记录已展开的方案详情，重绘后按稳定方案 ID 恢复展开状态。
- 图片地址改为稳定 URL；图片状态从排队/生成变为成功时仍会正常加载，后续轮询不再强制刷新同一图片。

### 验证

- 新增前端回归契约测试；定向测试通过。
- 全量 deterministic unittest `263` 项、Node 语法、Python compileall 和 `git diff --check` 均通过。
- 未调用真实 AI 或图片请求；未修改真实数据库、上传文件或 `chat2api/.env`。

## 2026-09-04 静态方案卡片收敛

### 本次完成

- 不轮播静态方案改为与轮播方案一致的简洁默认展示：首屏仅显示标题和创意摘要。
- 详细定位、证据、画面、文案、素材计划、风险和评审信息继续保留在“查看方案细节”中。

### 验证

- Node 语法、静态前端定向测试和 `git diff --check` 通过。
- 8775 服务已重启并确认加载紧凑版静态卡片。

## 2026-09-04 叙事类钩子字段兼容修复

### 本次完成

- 修正 `NarrativeResult.v1` 校验：模型在钩子对象中附带 `rationale`、类型等非契约元数据时，不再误报“钩子字段结构无效”；canonical 结果仍只保留 `text` 和 `scenes`。
- 保持钩子必需字段、文本类型、场景数量和长度校验不变，缺失或非法内容仍会进入有限修复/失败路径。

### 验证

- 新增叙事回归测试，证明附加钩子元数据会被丢弃且不会触发多余模型重试。
- 定向叙事测试通过；全量 deterministic unittest `262` 项、Node 语法、Python compileall 和 `git diff --check` 均通过。
- 未发起真实 AI 或图片请求；未修改真实数据库、图片、上传文件或 `chat2api/.env`。

## 2026-09-04 启动器显示 GPT 用户名

- 在连接状态的 Token 到期信息下增加“GPT 用户名”。
- 用户名从 Access Token 的 `https://api.openai.com/profile` claims 本地解析，优先显示 `name`，其次使用 `username`/`email`；无有效字段时显示“未识别”。
- Session Cookie 换取新 Token 后同步刷新该显示值。
- 定向启动器测试 29 项通过，未读取或发送额外凭据。
- 修复 Session Cookie 热更新后启动器用户名未同步的问题：成功换取新 Token 后立即回读 `.env` 并刷新用户名。

## 2026-09-04 Session Cookie 热更新修复

### 本次完成

- 修复启动器保存 Session Cookie 只写入 `chat2api/.env`、运行中网关继续使用旧会话的问题。
- 网关在线且 Cookie 发生变化时，启动器后台调用受控 `/v1/session` 立即换取新 Access Token；网关未运行或热更新失败时给出明确的重启提示。
- 新增请求构造、成功响应和凭据脱敏回归测试。

### 验证

- `python -m unittest tests.test_launcher_proxy -q`：28 项通过。
- `python -m py_compile launcher.py`、`git diff --check` 通过。
- 未主动调用真实 `/v1/session`，未修改当前真实凭据、数据库或图片。

## 2026-09-04 首次生成结果立即展示修复

### 本次完成

- 修复历史接口与生成服务使用不同指纹规则的问题：历史读取现在复用生成服务的 canonical snapshot，包含 PromptRegistry 元数据，刚生成批次不会再被归入“旧定位”。
- 前端生成接口返回后立即渲染已校验的文字方案，随后继续刷新图片状态；图片慢加载不阻塞文字首帧。
- 修复自动保存与生成并发时的竞态：生成会等待正在进行的项目保存完成，避免快照和历史查询落在不同定位。
- 增加本次生成批次的前端短期 pin：历史刷新遇到并发定位漂移时，仍先展示生成接口返回的文字方案，直到用户主动修改定位或切换项目。
- 新增生产入口回归测试，覆盖生成后立即读取 history 的当前批次归类。

### 验证

- `python -m unittest discover -s tests -q`：261 项通过。
- `python -m creative_studio.release_gate`：unittest、Node、compileall、governance、evaluation、backup-dry-run、diff-check 全部通过。
- 8775 服务已重启，`/api/health` 返回成功；未修改真实数据库、图片、上传文件或凭据。

## 2026-09-04 图片任务 401 修复

### 本次完成

- 定位图片立即失败原因：网页服务进程未继承 `chat2api/.env` 中的 `CHATGPT_CONTROL_TOKEN`，向 `/v1/images/jobs` 提交时收到 401。
- 按正式启动器方式重启网页服务，将现有控制令牌仅注入进程环境；未读取、输出或修改凭据文件。

### 验证

- 使用当前令牌访问网关受保护图片任务路由，返回 404（鉴权通过后表示任务不存在），不再返回 401。
- 网页 `/api/health` 正常；未发起额外真实图片生成请求。

## 2026-09-04 创意说明改为选填

### 本次完成

- 移除生成服务对 `task_description` 的统一非空拦截；展示类“创意说明”和叙事类“任务描述”现在都允许留空。
- 空白输入继续统一裁剪为空字符串，并照常进入生成快照、指纹和提示词；项目、额度、轮播配置等其他生成校验保持不变。
- 新增展示类与叙事类服务回归测试，并扩展隔离浏览器验收以覆盖两种空说明生成流程。

### 验证

- 两项定向服务测试已按 TDD 从失败转为通过，分别覆盖展示类和叙事类空白说明的快照归一化及适配器调用。
- 使用隔离 API 夹具和本机 Chrome 验证展示类、叙事类空说明均可发起生成，且不出现“请先填写创意说明”；`1280x720`、`390x844` 均无横向溢出，页面异常为零。
- Node 语法、Python compileall、标签 JSON 解析和 evaluation fixture 校验通过。
- 完整 unittest 共运行 `255` 项，其中 `11` 项在加载 PromptRegistry 时因工作区既有的 `config/ai_visual_static_creative_prompt_v1.txt` 与注册哈希不一致而报错；该无关提示词改动未在本次任务中覆盖。全局 `git diff --check` 同样只报告该文件末尾新增空行。
- 隔离浏览器仅使用本地 API 夹具；未访问真实数据库、账号、AI 或图片网关。

## 2026-09-04 Phase 5+ 后续门禁补齐

### 本次完成

- 修正全量收口设计文档中的过时事实：`LegacyCreativeGenerationAdapter` 不再由服务默认构造，轮播生产路径不再调用 `complete_visual_generation()`；二者仅作为兼容/历史 seam 保留。
- 扩展 `evaluation_harness`：增加 canonical case output lint、报告结果硬约束 lint、固定失败分类聚合，以及带 `evidence_type=deterministic_fake` / `quality_claim=contract_only` 标识的独立证据输出。
- 强化备份恢复：manifest 路径/重复项/SHA-256/大小 fail-closed 校验；恢复先写同级 staging 目录，失败自动清理；恢复成功后验证 `project_files` 上传引用和成功图片引用，返回 `references_verified=true`。
- 强化参考资料边界：repository 和 filesystem adapter 都拒绝跨项目路径；prompt 注入统一使用 basename，并清理 URL、绝对路径和私有字段赋值；新增生产生成入口端到端隐私回归。
- 新增 14 项 deterministic unittest，当前全量为 `254` 项通过；release gate、评测 schema/lint、backup dry-run、Node syntax、compileall 和 `git diff --check` 均通过。

### 本次验证

- `python -m unittest discover -s tests -q`：254 项通过。
- `python -m creative_studio.release_gate`：unittest、Node、compileall、governance、evaluation、backup-dry-run、diff-check 全部 `ok`。
- `python -m creative_studio.evaluation_harness --validate-only`：3 套 fixture、30 个 case、3 份 not-run 报告通过。
- `python -m creative_studio.evaluation_harness --deterministic-fake-summary`：输出独立的 `deterministic-contract-evidence.v1`，明确仅代表 contract/privacy 证据。
- 所有备份/恢复测试使用临时 SQLite 和临时目录；真实运行库本次仍只执行 dry-run，没有执行 scrub `--apply`、恢复覆盖或供应商请求。

### 仍需单独变更卡

- 真实 AI/图片供应商质量评测、带认证浏览器验收、多进程竞态/压力、自动备份调度、真实库 scrub 或恢复覆盖、端口/防火墙/HTTPS/Windows 服务和 `chat2api/.env` 凭据操作。

## 2026-09-04 Phase 5+ 全量收口切片

### 已完成

- 新增 [`docs/superpowers/specs/2026-09-04-ai-studio-complete-roadmap-design.md`](docs/superpowers/specs/2026-09-04-ai-studio-complete-roadmap-design.md)、`.scratch/phase-5-completion/spec.md` 和实施计划，覆盖 P5 canonical seam、P6 参考资料、P7 质量/观测、P8 备份恢复、P9 发布回滚。
- `generation_models.py` 新增 `GenerationRun`、`ReferenceAsset`、`ReferenceAssetContent`、`RunStorePort`、`ReferenceAssetPort` 和 `ObservabilityPort`；SQLite 以 additive migration 保存参考资料 digest/MIME/提取状态/受控摘要。
- 生成服务改用 `RunStorePort` reserve/complete/fail seam；轮播生产路径不再调用 `complete_visual_generation()`，旧 adapter 不再在服务构造时默认实例化。
- 上传文件记录 SHA-256、MIME 和受控摘要；prompt 只注入名称+摘要，运行 fingerprint/context 包含参考资料 metadata。
- 新增离线评测 harness、脱敏结构化观测和 `creative_studio.backup` 备份/恢复 CLI；备份 manifest 包含 SHA-256，恢复只能落到新目录。
- 新增发布 gate、发布/回滚 runbook，更新 operations、README、代码地图和 CHANGELOG。

### 验证

- `python -m unittest discover -s tests -q`：`240` 项通过。
- `python -m creative_studio.release_gate`：unittest、Node syntax、compileall、registry governance、评测 schema 和 backup dry-run 全部通过。
- 未写入真实数据库、图片、上传目录或 `chat2api/.env`；备份只读扫描真实运行库和图片目录，未执行真实库 scrub `--apply`。

### 未完成/需单独授权

- 自动调度备份、真实库历史 scrub/恢复覆盖、真实 AI/图片供应商质量报告、带认证浏览器、多进程竞态和正式多人内网部署仍未验证。
- 旧 adapter、旧 schema、retired prompt 文件继续保留为历史/兼容读取 seam，待完整观察周期和删除变更卡后清理。

## 2026-09-04 逐轮创意定位扩展与折叠

### 已完成

- 逐轮覆盖字段由产品卖点、展示内容、视觉母题三组扩展为主目标用户、玩家欲望、产品卖点、展示内容、视觉母题、动态方案六组；不包含美术表现风格、语音钩子和轮播流程控件。
- 每组沿用正式标签配置的选项与数量上限；第 1 轮可从全局主选/辅助选择初始化，旧项目缺少新增覆盖字段时也会使用全局选择补齐初始值。
- 六组改为按轮次独立保存状态的折叠面板；视觉母题、动态方案默认展开，其余四组默认收起。
- 同步扩展轮播归一化、继承展开、提示词上下文和浏览器公开投影白名单，新增字段会实际进入最终生成链路。

### 验证

- 前端、轮播归一化、提示词和公开投影定向测试按 TDD 从失败转为通过，相关 `55` 项、完整 deterministic unittest `238` 项通过；Node 语法、Python compileall、标签 JSON 解析和 `git diff --check` 通过。
- 使用隔离 API 夹具和本机 Chrome 验证六组顺序、默认展开、选择后保持展开、每轮独立折叠状态及零页面异常；`1280x720`、`390x844` 均无横向溢出。
- 未访问真实数据库、账号、AI 或图片网关。

## 2026-09-04 “是否轮播”标题行精简

### 已完成

- 删除“是否轮播”标题下方重复的“是 / 否”选择行，将原“确认”按钮改为标题行内同尺寸的“是”和“否”按钮。
- 选中态继续使用青绿色样式；轮播开关保持必选，选择“是”继续显示数量和形式，选择“否”继续清空数量、形式和逐轮配置。
- 未修改数据库、API、标签目录或 AI 契约。

### 验证

- 定向前端测试按 TDD 从失败转为通过；完整 deterministic unittest `227` 项通过，Node 语法、Python compileall、标签 JSON 解析和 `git diff --check` 通过。
- 使用隔离 API 夹具和本机 Chrome 验证“是 / 否”标题行、条件显示及清理联动，并检查 `1280x720`、`390x844` 均无横向溢出。
- 未访问真实数据库、账号、AI 或图片网关。

## 2026-09-04 Phase 5 治理证据补齐

### 已完成

- 新增 `phase5_governance` 静态审计：retired 首帧/后续 prompt loader 在 `src` 中没有运行时调用点；PromptRegistry 三个 production caller 的唯一性由测试锁定。
- 新增 [`docs/ai/phase5-caller-audit.md`](docs/ai/phase5-caller-audit.md)，逐项记录旧 adapter、schema、loader 和持久化入口的 production/test/history/dead 分类及删除条件；仍有兼容用途的项未删除。
- 根据零 caller 审计移除 `load_ai_visual_first_frame_prompt()`、`load_ai_visual_follow_up_prompt()` 及其旧路径 helper；retired registry 条目和提示词文件暂保留为历史 inventory。
- 完成真实运行库只读 scrub 与临时副本演练：真实库仍为 `changed_rows=2`、`private_field_occurrences=6`；临时副本 apply 后 fixed-point 为 `changed_rows=0`、`private_field_occurrences=0`，从 backup 恢复后重新 dry-run 仍可重复得到待 scrub 统计。
- 新增 `config/evals/reports/` 下 narrative/static/carousel 三份版本化 `not_run` 报告，明确未执行真实模型、图片网关和供应商质量评测。
- 新增 `config/evals/report-template.v1.json`，固定 baseline/candidate/repair_failure 三槽位、`not_run` 状态和供应商失败分类；新增 fixture 数量/唯一 ID 与报告 schema 测试。
- 扩展临时 projection scrub 测试，证明 backup 恢复后可再次 apply，并在最终 dry-run 达到 fixed point；未读取或写入真实运行库。

### 验证

- `python -m unittest tests.test_phase5_governance tests.test_projection_scrub -v`：8 项通过。
- 临时 scrub/backup/restore 命令演练完成；真实库命令仅使用只读模式。

### 未验证

- 真实 AI/图片供应商、认证浏览器、多进程竞态和真实运行库 scrub/恢复仍未验证；旧 adapter、旧 schema 和 `complete_visual_generation()` 仍按 handoff 条件保留。

## 2026-09-04 普通创意标签改为可选

### 已完成

- 标签目录升级为 `tags-2026-09-04-v3`，显式声明叙事类和展示类的目标人群必选，其余普通创意标签可选。
- 正式页面允许空选普通标签后确认收起，并在摘要中保留“未选择”和修改入口。
- “是否轮播”、轮播数量和轮播形式继续作为必选流程控件，原有条件联动和服务端校验不变。
- 决策记录见 [`docs/adr/0004-optional-tag-groups.md`](docs/adr/0004-optional-tag-groups.md)。

### 验证

- 定向规则测试已按 TDD 从失败转为通过；标签与前端定向测试 `32` 项、完整 deterministic unittest `226` 项通过，Node 语法、Python compileall、JSON 解析和 `git diff --check` 通过。
- 使用隔离 API 夹具和本机 Chrome 在 `1280x720`、`390x844` 实际验证空选确认、必选拦截、重新修改和横向溢出；截图保存在 `.scratch/optional-tag-selection/`。
- 未修改真实数据库、图片、上传文件、`chat2api/.env` 或监听配置；未调用真实 AI 或图片网关。

### 未验证

- 未使用真实账号和真实数据库执行带认证浏览器流程。

## 2026-09-04 Phase 4 轮播后台状态机与 Phase 5 治理收口

### 已完成

- 轮播 v1 采用共享 planner + 图片直出首帧的流程已写入 [`docs/adr/0003-carousel-v1-background-operation.md`](docs/adr/0003-carousel-v1-background-operation.md)，删除 prompt 中独立首帧文字会话的错误承诺。
- 新增 `CarouselVisualGeneration`，把轮播 planner 请求、契约校验和后续图片编排从生成服务中抽出；registry 绑定升级为 `CarouselResult.v1` / `CarouselResultValidator.v1`。
- 继续生成改为持久化 `carousel_operations` 后台 Operation，接口返回 `202` 和 operation id；lease、heartbeat、过期恢复、逐帧 claim、图片/会话游标/operation revision 原子提交和前端轮询均已接线。
- 恢复逻辑会把崩溃 worker 遗留的当前 `generating` 帧重置为 `pending`，保留已成功帧和失败证据；新增 API 归属、202 响应、operation 隐私和恢复回归测试。
- 补齐 `config/evals/carousel.v1.json` 的 10 个脱敏 case，并同步代码地图、运维手册和 CHANGELOG。

### 验证

- 定向轮播、后台 operation、API、生成服务、prompt registry 和叙事评测 fixture 测试通过；最终完整 deterministic unittest 为 `220` 项，Node 语法、Python compileall、JSON 解析和 `git diff --check` 均通过。
- 未修改真实 `data/`、`data/images/`、`data/uploads/`、`chat2api/.env` 或监听配置；保留 `launcher.py` 中用户已有的 `WEB_BIND_HOST = "0.0.0.0"` 未暂存修改。

### 未验证与保留项

- 真实 AI 输出质量、真实图片网关、带认证浏览器、多进程生产竞态和真实运行库升级仍未验证；本阶段测试仅使用 deterministic fake 和临时 SQLite。
- `LegacyCreativeGenerationAdapter`、旧视觉 schema 和 retired prompt 文件继续作为历史/兼容读取 seam，Phase 5 的删除条件是三个 production caller 均为零且完成保留期与回归评估，不能因本次 operation 接线强行删除。
- 2026-09-04 对真实 `data/creative_studio.db` 仅执行只读 projection scrub dry-run：`scanned_rows=3`、`changed_rows=2`、`private_field_occurrences=6`、`invalid_json_rows=0`、`unknown_kind_rows=0`；未执行 `--apply`，真实历史 scrub/备份/恢复演练仍待单独变更卡。
- 新增 [`docs/ai/quality-evaluation.md`](docs/ai/quality-evaluation.md)，集中记录三套 10-case 脱敏评测集、deterministic 证据和真实模型质量评测边界；没有把 fake 测试表述为真实质量通过。
- 本阶段 checkpoint 提交：`5ad827c`（未包含用户已有的 `launcher.py` 修改）；随后以 docs-only 提交记录该哈希。
- 已新增 [`docs/superpowers/handoffs/2026-09-04-ai-rebuild-phase-5-handoff.md`](docs/superpowers/handoffs/2026-09-04-ai-rebuild-phase-5-handoff.md)，供下一会话继续 Phase 5；交接明确旧 caller 删除条件、临时数据库 scrub/恢复步骤、质量评测报告和最终门禁；提交为 `a525962`。
- 2026-09-04 应用户反馈重写 Phase 5 handoff：补充当前工作树中的标签可选独立任务、旧路径逐项 caller 证据、P5-A 至 P5-D 工作包、临时 scrub/恢复验收、停止条件和提交切片；最终文档提交为 `1626fbd`，哈希记录提交为 `48d73ae`。

## 2026-09-03 Phase 3 静态迁移收尾与 Phase 4 交接

### 已完成

- Task 4 已提交为 `7e74b70`：`static-v1` 成为唯一静态 production，`visual-v2.3` 进入 retired inventory；静态 canonical renderer、10 个脱敏评估 case 和 registry contract 测试已纳入提交。
- Phase 4 handoff docs-only 提交为 `8bb7d54`。
- 修正显式 `model_client=None` 的 legacy adapter 边界：旧视觉结果继续走 `complete_visual_generation()`，不会因 registry 已加载而误写入静态 canonical persistence；新增回归测试覆盖该条件。
- Phase 3 handoff 已标记为实施前历史契约；新增 [`docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md`](docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md)，记录 static-v1 registry、Module、DTO、repository、图片 request、旧 alias caller、状态恢复、隐私边界、回滚和 Phase 4 范围。

### 验证

- `$env:PYTHONPATH='D:\\code\\ai_creative_studio\\src'; python -m unittest discover -s tests -v`：`202` 项通过。
- `node --check static\\app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 测试使用临时 SQLite、隔离图片目录、deterministic fake 和固定输入；未修改真实 `data/`、`data/images/`、`data/uploads/` 或 `chat2api/.env`。
- `launcher.py` 保留用户已有的 `WEB_BIND_HOST = "0.0.0.0"` 修改，未暂存；默认部署和监听边界未因本阶段改变。

### 未验证

- 真实 AI 输出质量、真实图片网关成功率/画质、带认证浏览器流程、真实数据库升级/历史 scrub、Chat2API 真实参数语义、参考文件内容传递和多进程生产竞态仍未验证。

### 下一阶段

- Phase 4 只处理轮播 v1 的 ADR、后续画面 prompt/编排、Operation/lease/heartbeat、逐帧状态查询和轮播前端轮询；不得提前修改 static-v1 或静态 persistence。

## 2026-09-03 正式页面项目删除与标签交互迁移

### 已完成

- 项目列表每行增加删除图标，删除当前项目后按原位置打开下一个或前一个项目；删除非当前项目保持当前工作区，全部删除后才显示空状态。
- 移除标签组展开区重复的已选标签芯片，保留表格高亮、章节摘要和顶部汇总。
- “是否轮播”改为独立的“是/否”单行控件；选择“否”会清理轮播屏数、形式和逐轮配置。
- 展示内容章节始终保留，未选择产品卖点时显示提示；选择卖点后按 `product_display` 关系过滤，并清理失效展示内容。
- 标签达到上限后禁用未选项，已选项仍可取消；普通标签、主副标签、美术风格和轮播轮次不再自动顶替最早选择。
- 轮播第 2 轮起支持继承第 1 轮、首次编辑转为自定义、按上限替换以及重新继承时丢弃覆盖值。

### 验证

- 新增并通过前端契约测试：`python -m unittest tests.test_frontend_tag_reports -q`，19 项通过。
- 全量确定性测试：`python -m unittest discover -s tests -v`，201 项通过。
- `node --check static/app.js`、`git diff --check` 通过。
- 已连接本地页面检查；正式页面需要登录，未使用或索取凭据，因此未完成带认证的 `1280x720` / `390x844` 人工浏览器验收。
- 未调用真实 AI 或图片网关，未修改数据库、上传文件或 `chat2api/.env`。

## 2026-09-03 AI 重构 Phase 3 静态展示类迁移（实现完成）

### 已完成

- `src/creative_studio/static_visual.py` 提供 `StaticVisualPromptInput`、`StaticVisualResult.v1`、严格 validator、一次字段路径 repair 和私有图片指令分离。
- `StudioRepository.complete_static_generation()` 与 `PublicResultMapper.static_visual_item()` 已接入；新静态写入不包含 `subtitle`、`creative_description`、`core_subject`、`layout`、`visual_style`，不创建 `display_frames`，私有图片指令只进入 `visual_items.image_prompt` 和受控图片任务。
- `CreativeGenerationService` 的正式非轮播展示路径进入 `StaticVisualGeneration`；每批 3 个方案、每案 1 个 `StaticVisualImageRequest`，叙事 v6、轮播 prompt/validator/继续生成和逐帧状态机保持原路径。
- `config/prompts/registry.json` 将 `creative.visual.static.generate@static-v1` 设为唯一静态 production；`visual-v2.3` 标记 `retired`，禁止新 caller，并写明 replacement、deprecated_since 和 Phase 5 removal condition。
- `config/evals/static.v1.json` 已建立 10 个脱敏 case，覆盖空白 brief、画幅、仅文件名参考、未确认事实、缺失素材、机制重复、超长文案、URL/Markdown 注入和 repair 失败。
- `static/app.js` 对含 `static_frame` 的结果优先呈现用户张力、产品价值、视觉机制、证据台账、静态画面、素材计划、制作风险和 review；旧 carousel 结果继续使用原渲染逻辑。

### 验证

- 实现提交：`c0d86a0`、`42ebc83`、`08492ca`；Task 4 配置/评估/前端和文档收尾提交见当前分支日志。
- 静态定向测试 23 项通过；完整 deterministic unittest、Node 语法、Python compileall、`git diff --check` 和工作树门禁在本次收尾前重新执行。
- 测试只使用临时 SQLite、fake model/image runner 和隔离路径；未修改真实 `data/`、`data/images/`、`data/uploads/` 或 `chat2api/.env`。
- 未调用真实 AI、图片网关或带认证浏览器；真实数据库升级/历史 scrub 和图片质量仍未验证。

### Phase 4 输入

- Phase 4 只处理轮播 v1 的 ADR、后续画面 prompt/编排、Operation/lease/heartbeat、逐帧状态查询和轮播前端轮询。
- static-v1 的实际路径、旧 alias 读取 caller、首图 typed request、部分成功/人工 retry/重启恢复和隐私边界记录在 `docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md`。

## 2026-09-03 Phase 3 交接文档深度复核

### 已完成

- 重新核对 Phase 3 直接相关的架构设计、展示画面流程、提示词工程研究、Phase 2 交接、总纲、公开投影 ADR、静态提示词、registry、静态生产 caller、validator、repository、图片任务和公开 DTO。
- 深度完善 [`docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md`](docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md)：以当前 HEAD 为事实基线，写清静态 v2.3 production 与 static-v1 candidate 的差异、旧字段伪造路径、持久化副本、图片入队 seam、StaticVisualResult.v1/StaticVisualPublicDTO.v1 目标、私有图片指令边界、deterministic harness、质量评估、失败/重试/回滚和 Phase 4 启动条件。
- 明确 Phase 3 不修改轮播 prompt、继续生成、逐帧状态机、真实运行数据、网关凭据或真实外部调用；`launcher.py` 接手前已有修改继续保留。
- 本次内容通过独立 docs-only 提交保存；提交后仍需保持 `launcher.py` 为未暂存用户修改。

### 验证

- 已交叉核对当前 registry、代码 caller、持久化字段和测试事实；文档不含未决占位语句。
- 本次仅修改交接文档和本进度记录，未修改业务代码、数据库、图片、上传文件或 `chat2api/.env`，未调用真实 AI、图片网关或浏览器。

## 2026-09-03 Phase 3 交接文档

- Phase 2 实现提交：`1c681cc2b82fcaaee9416111ccd15b96bdf4efe9`。
- 已生成 [`docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md`](docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md)，下一阶段只允许静态展示类重构；不进入轮播 Phase 4。

# 2026-09-03 AI 重构 Phase 2 叙事类重构（已完成）

### 已完成

- 新增 `src/creative_studio/narrative.py`，建立 `NarrativeGeneration`、`NarrativeInput` 和 `NarrativeResult.v1` canonical contract；固定 5 个故事、每故事 2 个钩子、每钩子 3 个场景，并校验故事/钩子差异、证据台账和风险字段。
- 叙事生产 prompt 升级为 `config/prompts/narrative/v6.txt`，明确注入游戏资料与参考文件名；registry 登记 `creative.narrative.generate@v6`，v5 标记 retired。
- 生产 `CreativeGenerationService` 叙事分支接入新 Module；格式 repair 携带上次校验字段路径，第二批携带上一批摘要和显式去重约束；旧 UI 通过白名单 DTO 保持 `story/hooks` 兼容。
- 新增 deterministic fake 叙事 contract 测试和固定评估样例；更新代码地图、运维边界和 registry contract 映射。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -q`：185 项通过。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 未调用真实 AI、图片网关或浏览器；未修改真实数据库、图片、上传文件或 `chat2api/.env`。

### 保留项

- `LegacyCreativeGenerationAdapter` 和旧叙事校验函数仍保留为无 model client/历史兼容 caller，删除条件为三个新业务 Module 均切换且 legacy production caller 为零；本阶段不进入 Phase 3。

# 2026-09-03 AI 重构 Phase 1 实现（已完成）

### 已完成

- 新增 `config/prompts/registry.json`，登记三个 production PromptSpec、一个 candidate 和两个 retired inventory；模板 hash 使用规范化 UTF-8 SHA-256。
- 新增 `prompt_registry.py`、`contracts.py`、`model_ports.py` 和 provider capability 声明；registry 对缺文件、越界路径、错 hash、错变量、未知 contract 和生命周期规则 fail closed。
- `create_application()` 启动时加载 registry；生成完成记录以加法迁移保存 prompt id/version/hash、schema 版本、model/provider；新增 deterministic text/image fake。
- registry/port 定向测试和全量确定性测试共 181 项通过。

### 边界

- 未切换用户可见输出，未调用真实 AI、图片网关或浏览器；未写入真实数据库、图片、上传文件或 `chat2api/.env`。
- 工作树接手时已有标签目录同步和启动器局域网配置修改，均已随实现提交保留；未调用真实 AI、图片网关或浏览器。
- Phase 1 实现提交为 `1704bea`；Phase 2 交接文档随后以 docs-only 提交生成。

# 2026-09-03 叙事标签选择上限调整

### 已完成

- 更新 `config/creative_tag_options.json`：副目标人群最多 2 项、美术风格 1 项、内容形式 3 项、产品证据 4 项。
- 增加标签配置契约测试，锁定上述选择上限；展示类上限保持不变。

### 验证

- 待本次改动完成后运行完整单元测试、前端语法检查、Python 编译检查和 `git diff --check`。

# 2026-09-03 叙事与展示标签目录同步

### 已完成

- 以 `C:\Users\admin\Downloads\叙事类标签_重制版.xlsx` 和 `C:\Users\admin\Downloads\展示类标签.xlsx` 为来源，更新 `config/creative_tag_options.json` 至 `tags-2026-09-03-v2`。
- 叙事类新增“美术风格”组并置于“目标人群”之后；叙事目录更新为 6 组、139 个选项，展示目标用户更新为 34 项，展示美术风格按重复参考作品行归并为 35 项。
- 将叙事 `art_style` 接入统一标签规范化、生成指纹、`{{creative_tags}}` prompt 注入和公开项目投影；未修改 `config/ai_creative_prompt_v5.txt`。
- 保留展示类产品卖点→展示内容关系表；旧数据库中的历史标签值未迁移或删除。

### 验证

- 新增标签目录、prompt、指纹和公开投影契约测试；定向标签/投影测试通过。
- 尚未调用真实 AI、图片网关或浏览器；未修改数据库、图片、上传文件或 `chat2api/.env`。

### 未完成

- 尚未在正式页面逐项人工验收新增标签的桌面/移动端显示；需要后续按项目要求检查 `1280x720` 和 `390x844`。

# 2026-09-03 AI 重构 Phase 1 交接准备

### 已完成

- 新增 `docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-1-handoff.md`，记录 Phase 0 检查点、Phase 1 精确范围、执行顺序、完成门禁和验证/提交要求。
- 交接要求下一会话完整完成并提交 Phase 1 后，生成一份无占位符、包含真实提交和验证证据的 Phase 2 新会话交接文档；Phase 1 未通过时不得宣称可以进入 Phase 2。
- 修正总纲 Phase 1 允许文件，使范围覆盖 registry、port、生成元数据和 production contract harness 的必要接线文件；同时将 Phase 2 开始条件收紧为 Phase 1 全部门禁、实现提交和工作树检查均完成，继续排除提前切换用户可见输出。

### 当前状态

- Phase 1 尚未开始；当前仅准备交接文档，没有实现 PromptRegistry、ContractRegistry、model port 或 contract harness。
- 本次不修改业务代码、UI、数据库、图片、上传文件或 `chat2api/.env`，不调用真实 AI、图片网关或浏览器。

# 2026-09-03 AI 重构 Phase 0 安全止血与事实收口

### 已完成

- 新增统一的 `PublicResultMapper`，history、status、adopt、项目采用快照、visual item 和 display frame 均按稳定顺序的白名单重建公开对象；递归私有字段清单覆盖供应商游标和内部错误详情。仓库当前没有 export 路由，因此本阶段无 export caller 可迁移。
- 新增 dry-run 优先的 projection scrub；工具以 SQLite `mode=ro` 扫描，写入只允许显式指定的非生产副本且强制先备份，遇到无效 JSON 或未知 recommendation kind 会中止，并拒绝直接 apply `data/creative_studio.db`。
- prompt 编译器收敛为 `{{name}}` 单次字面替换；缺失变量、多余变量和 hash 不匹配均 fail closed，不再二次解释用户输入中的 `$` 或 `{{...}}`。
- JPEG、PNG、WebP 参考图与下载 artifact 现在校验 magic bytes、MIME 和规范扩展名，并在 SQLite 中持久化 `image_mime`。
- 生成失败记录不再被同 fingerprint 的后续请求删除；错误增加稳定 `error_code`、阶段、字段路径、可重试性和 trace id，公开响应只返回安全摘要。
- 新旧模型调用路径的 JSON 解析失败统一使用根路径 `$`，`HttpModelClient` 在 transport 边界保留畸形 `choices` 路径，叙事各层 validator、视觉 wrapper 和供应商游标错误使用精确字段路径；公开文本列表拒绝数字和布尔值，仅旧 `carousel_frames` 继续兼容整数索引。
- 轮播数量缺失或不在 2 至 5 时会在 reservation 和模型调用前失败；`none` 保持 1 帧，AI 数量仍允许每套独立返回 2 至 5 帧。
- 移除 `creative_studio.app` 的 import-time composition root；`create_application()` 支持临时 SQLite、fake model/image queue、隔离环境和固定 clock seam。叙事游戏资料默认路径已改为 v2。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：175 项通过。
- `node --check static\app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 对真实默认数据库仅执行只读 dry-run：扫描 8 行，6 行投影会变化，发现 25 处私有字段，0 行无效 JSON，0 行未知 recommendation kind；`applied=false`，未创建备份，执行前后 SHA-256 均为 `F7DA1AA20D5FBAC7A3785C0D81096B1096749DE40025874644F37E1AD461DFA8`，未写入数据库。
- 在临时 SQLite 副本验证 dry-run、强制备份 apply、写后重读和从备份恢复；未对真实数据库执行 `--apply`。

### 边界与后续

- 未调用真实 AI、图片网关或浏览器；未修改真实数据库、图片、上传文件或 `chat2api/.env`。
- `LegacyCreativeGenerationAdapter`、旧 schema，以及 retired 的首帧/后续帧 prompt loader 仍保留，按变更卡中的删除条件留待后续阶段处理。
- Phase 0 门禁完成后才可另开 Phase 1；本条不实现 PromptRegistry、ContractRegistry 或新业务契约。

## 2026-09-03 AI 创意能力重构总纲

### 已完成

- 完成 AI 能力的生产链路审计，记录叙事、静态展示、轮播、图片任务、提示词编译、网关参数、持久化、公开 DTO、测试和文档治理问题。
- 新增 [`docs/ai-rebuild-master-plan.md`](docs/ai-rebuild-master-plan.md)，作为当前 AI 重构的唯一实施基线：包含当前真实事实、P0/P1/P2 问题台账、目标深模块和 port/adapter、PromptRegistry 与契约、公开 DTO、轮播状态机、质量评测、Phase 0 至 Phase 5 迁移门禁、回滚和后续 Agent 执行协议。
- 新增 [`docs/ai/README.md`](docs/ai/README.md) 作为 AI 文档入口，并同步修正 `AGENTS.md`、`项目代码地图.md` 和 `docs/operations.md` 中已确认的登录/项目归属、监听地址和轮播首帧事实冲突。

### 验证

- 已通过静态审计确认真实 production composition root 为 `StudioApplication -> CreativeGenerationService -> HttpModelClient -> chat2api`；轮播首帧当前直接使用共享规划响应，提示词中的独立文字会话描述属于待清理漂移。
- 本次只修改文档和工程治理入口；未修改业务代码、数据库、图片、上传文件或 `chat2api/.env`，未调用真实 AI/图片网关。

### 当时未完成

- 本条记录形成时尚未执行 AI 重构 Phase 0；其完成情况以文件顶部更新的 Phase 0 记录为准。

## 2026-09-02 补充工作树整理与提交要求

### 已完成

- 在 `AGENTS.md` 新增提交与工作树整理约定：单需求单提交、历史堆积时使用明确的 checkpoint 快照、提交前验证、敏感运行数据排除和提交后状态复核。
- 记录测试存在环境依赖失败时的报告要求，避免将部分通过表述为全部通过。

### 验证

- 文档差异通过 `git diff --check`。
- 已确认此前整理快照提交 `73d770a` 后工作树干净；本次只新增代理规范和进度记录。

### 未完成

- 未修改业务代码、数据库、运行数据或 AI 配置；未发起真实 AI 请求。

## 2026-09-02 补齐轮播提示词上下文与图片模式约束

### 已完成

- 展示方案持久化保留核心主体、画面布局、视觉风格、内容延展、参考来源、关键词及任务/产品证据，继续生成时完整注入同一方案上下文。
- 首帧和后续画面提示词明确区分规划 JSON 与图片执行指令；图片指令要求直接生成图片，不返回文字、JSON、Markdown 或解释。
- 图片网关入口统一增加图片模式前缀，降低上游模型将生图请求误判为文字问答的概率。
- 继续生成不再向可见文字会话发送后续 JSON 请求，直接依据锁定路线生成图片提示词并提交图片网关；上一张成功图片继续作为参考图。
- 网页服务在未由启动器注入环境变量时，自动回退到本项目本地 AI 网关和版本化提示词路径；不读取或改写令牌配置。

### 验证

- 轮播继续生成、图片任务、生成服务和仓储回归测试通过。
- 全量确定性测试：127 项中 126 项通过；唯一错误仍为当前环境缺少 `pydantic_settings`，导致既有 `test_auth_refresh` 无法导入。

## 2026-09-02 修正轮播继续生成会话路线

### 已完成

- 将展示类轮播批次固定为一次共享文字会话输出三套方案和完整画面路线。
- 每套方案在独立的新文字会话中重新生成第 1 帧，持久化独立 `conversation_id` / `parent_message_id`，首帧图片再进入该方案任务。
- 继续生成复用方案自己的会话，按帧序串行生成后续画面；旧历史方案缺少会话时也会先补建首帧并等待首图完成。
- 前端继续按钮增加“继续生成中”状态和重复点击保护；隐藏图片指令仍不进入公开响应。

### 验证

- 新增生成服务回归测试：确认 1 次共享方案请求后有 3 次无会话首帧请求，三套方案会话游标各不相同，首帧内容来自独立会话。
- 连续画面会话测试、仓储测试和前端契约测试通过；`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 全量确定性测试：127 项中 126 项通过；唯一错误为当前环境缺少 `pydantic_settings`，导致既有 `test_auth_refresh` 无法导入。

### 未完成

- 未在真实浏览器和有效 AI 凭据下执行轮播首帧/继续生成；真实网关和图片质量仍未验证。

## 2026-09-02 修正竖版画面显示比例

### 已完成

- 将竖版图片容器比例从 `9:12` 修正为 `9:16`，与项目竖版画幅一致。
- 保持图片使用 `object-fit: contain`，完整显示画面内容。

### 验证

- `tests.test_frontend_tag_reports.FrontendTagReportTests.test_portrait_image_frame_uses_full_9_by_16_ratio`：通过。
- `node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 生成成功后自动刷新结果

### 已完成

- 生成接口成功返回后，前端自动重新读取规范化历史数据并渲染最新方案。
- 修复 POST 生成响应缺少类型字段时误用叙事卡片渲染展示类方案的问题。
- 保留图片后台生成和状态轮询，不需要用户手动刷新浏览器。

### 验证

- `tests.test_generation_service` 与 `tests.test_frontend_tag_reports`：28 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 展示类文字结果优先返回

### 已完成

- 展示类文字方案完成校验和图片任务入队后立即返回，不再等待全部图片进入终态。
- 前端先渲染方案文字与图片占位，图片继续由后台任务和已有轮询更新。
- 叙事类生成和连续画面继续生成逻辑保持不变。

### 验证

- `tests.test_generation_service` 与 `tests.test_frontend_tag_reports`：26 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 方案细节状态中文化

### 已完成

- 方案细节中的画面状态由内部英文值转换为中文：排队中、等待中、生成中、已完成、生成失败。
- 未知状态统一显示为“处理中”，避免内部枚举直接泄漏到界面。

### 验证

- `tests.test_frontend_tag_reports.FrontendTagReportTests.test_frame_statuses_are_translated_for_scheme_details`：通过。
- `node --check static/app.js`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 展示方案操作收敛

### 已完成

- 移除展示类轮播方案卡上独立的“选择方案”按钮及其前端监听器。
- 每套方案只保留“继续生成”和“采用此方案”；继续生成直接调用对应方案接口，由后端自动建立/复用该方案独立会话并按序推进后续画面。
- 保持多套方案可同时点击继续生成，各方案使用独立会话和状态锁，任务不会互相串线。

### 验证

- 新增前端契约测试，确认不存在选择方案入口且继续/采用动作仍存在。
- `tests.test_frontend_tag_reports`：10 项通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 全量确定性测试：122 项中 121 项通过；唯一错误为当前环境缺少 `pydantic_settings`，导致既有 `test_auth_refresh` 无法导入。

### 未完成

- 未在真实浏览器会话中点击多套方案的并行继续生成。
- 未发起真实 AI 文字或图片请求。

## 2026-09-02 生成阶段显示等待时长

### 已完成

- 最终生成按钮从点击开始显示已等待时长，并每秒刷新一次。
- 等待时长支持持续累计（超过 1 小时显示小时），不增加超时、重试或生成次数限制。
- 请求成功、失败后清理计时器，避免页面残留后台定时任务。

### 验证

- `tests.test_frontend_tag_reports.FrontendTagReportTests.test_generation_button_shows_unlimited_elapsed_wait_time`：通过。
- `node --check static/app.js`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 移除实时创意简报并改为单列工作区

### 已完成

- 删除创意定位页面右侧“实时创意简报”栏及其前端状态绑定。
- 桌面和移动端统一使用单列主工作区，释放横向空间并保留任务描述、标签、画幅、历史、生成与采用功能。
- 清理桌面媒体查询中遗留的双列和简报定位规则，避免空侧栏占位。

### 验证

- `tests.test_frontend_tag_reports`：前端契约测试通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 浏览器静态检查确认简报 DOM 不存在、桌面实际计算为单列且 1280x720/390x844 无横向溢出。

### 未完成

- 未发起真实 AI 文字或图片请求。

## 2026-09-02 最新 Session Cookie 验证与连接检测修复

### 已完成

- 确认用户新填的 Session Cookie 能换出与旧 Token 不同的新 Token，并通过真实 `chat-requirements` 认证探测。
- 定位启动器问题：旧 Token 只要 JWT 未到期，检测就跳过 Cookie 换 Token，导致新 Cookie 未被当前网关使用。
- 修正检测流程：先验证 `/v1/models`；仅当上游未验证且存在 Cookie 时，才用 Cookie 更新 Token 并重新验证。
- 当前网关通过新 Cookie 更新后，`/v1/models` 返回 `detected=true`、模型列表非空；最小真实 `/v1/chat/completions` 返回 `OK`，会话标识正常。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_launcher_proxy tests.test_auth_refresh -v`：28 项全部通过。
- 全量确定性测试：121 项中 120 项通过；唯一失败为既有前端契约测试 `test_workspace_drops_realtime_brief_sidebar`，与本次认证/启动器修复无关。
- `python -m compileall -q src chat2api launcher.py`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 当前启动控制台进程仍是旧代码；需重启启动控制台后，点击“检测连接”才能使用新的 Cookie 回退验证逻辑。
- 三条业务路径的真实文字/图片生成尚未在本次复测中展开；网关认证和最小文字调用已恢复。

## 2026-09-02 标签满额后可继续选择

### 已完成

- 对照展示类、叙事类标签 Excel 规则，修正单选、主+辅选择和多选达到上限后的交互。
- 取消未选项的满额禁用；再次选择会自动替换最早选中的标签，主选/副选槽位同步重排；美术参考作品和逐轮定位字段也遵循同一规则。
- 保留取消已选项、选项上限、级联清理和服务端字段结构。

### 验证

- `tests.test_frontend_tag_reports`：新增满额替换契约测试并通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 已核对两份 Excel 的交互形式与选择规则，未修改 Excel 原文件或标签配置 JSON。

### 未完成

- 未在带认证的正式页面中逐项人工点击验收；未发起真实 AI 请求。

## 2026-09-02 修复启动器连接状态误报

### 已完成

- 修复“检测连接”只检查本地 `/health` 的 Token 存在和到期时间、却不验证上游可用性的逻辑。
- 现在检测会额外检查 `/v1/models` 的 `detected=true` 和非空模型列表；上游返回 `token_revoked` 或探测失败时显示连接失败并保留错误原因。
- 区分“已通过上游验证”和“Access Token 已自动填入”，不再在未刷新 Token 时误称已自动填入。
- 新增启动器连接验证回归测试。

### 验证

- 当前真实网关 `/v1/models` 返回 `detected=false` 时，`gateway_upstream_verified()` 返回 `False`，与上游 Token 已撤销的真实状态一致。
- `PYTHONPATH=src python -m unittest tests.test_launcher_proxy tests.test_auth_refresh -v`：28 项全部通过。
- 全量确定性测试：121 项中 120 项通过；唯一失败为既有前端契约测试 `test_workspace_drops_realtime_brief_sidebar`，与本次启动器/认证修复无关，保留用户现有前端改动。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 账号 Access Token 仍被上游撤销；更新有效凭据并重启网关后，检测才会显示“已通过上游验证”。

## 2026-09-02 真实 AI 请求认证问题修复与复测

### 已完成

- 定位并修复 ChatGPT Session Cookie 头组装问题：旧的未分片值与 NextAuth `.0/.1` 分片同时存在时，服务端可能优先读取已失效的旧值；现在分片值优先，Cookie 轮换后也保持同一规则。
- 新增脱敏回归测试，覆盖 Cookie 规范化和轮换场景；未记录任何令牌、Cookie 或完整模型响应。
- 通过项目专用 ClipProxy 中转真实调用 `/api/auth/session`，修复后返回 `200` 且拿到 access token。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：117 项全部通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。
- 修复后的真实 `/v1/chat/completions` 最小请求仍返回上游 `401 token_revoked`；说明代理、Cookie 头和网关链路可达，但当前 Access Token 已被 ChatGPT 撤销，Session Cookie 返回的 token 也仍是该失效 token。
- 临时真实测试网关和中转已停止；现有本地网页/网关进程未被停止。

### 未完成

- 当前账号凭据不可用于真实文字或图片生成，叙事类、展示类首帧和连续画面三条业务路径均在网关认证层之前被同一 `token_revoked` 阻断，未继续重复请求消耗额度。
- 需要用户在启动控制台重新登录并提供有效 Session Cookie、Access Token 或可用的 Auth0 refresh token 后，再做三条业务路径的真实冒烟。

## 2026-09-02 任务描述输入框收紧

### 已完成

- 将“创意定位”顶部任务描述从多行文本框改为单行输入框，限制最大长度为 500 字符。
- 保持 `taskDescription`、自动保存和后端 `task_description` 字段不变。

### 验证

- `tests.test_frontend_tag_reports`：6 项通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 静态页面结构检查确认输入元素为 `INPUT`，桌面和移动端页面宽度无溢出。

### 未完成

- 未发起真实 AI 请求；未在带认证的正式服务中执行完整生成流程。

## 2026-09-02 任务描述并入创意定位

### 已完成

- 删除独立的“任务说明”步骤和“任务类型”输入框。
- 将唯一的任务描述输入框放到“创意定位”流程顶部，画幅控件同步保留在该标题区域。
- 工作流步骤调整为“创意定位 → 生成与采用”，后端仍兼容发送空 `task_type` 字段。

### 验证

- `tests.test_frontend_tag_reports`：5 项通过。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 浏览器结构冒烟：`1280x720`、`390x844` 均无横向溢出，步骤条为两步，任务描述位于标签控件之前。

### 未完成

- 未发起真实 AI 请求；未在带认证的正式服务中执行完整生成流程。

## 2026-09-02 修正固定出口被普通节点替换

### 已完成

- 定位到启动器把已配置的 ClipProxy `38.248.239.46` 替换成普通 Clash `127.0.0.1:7897`，导致出口 IP 错误。
- 已修正为：有 `PROXY_URL` 时始终使用已配置的 ClipProxy 固定出口；仅在没有固定代理时才探测 Clash 入口。
- 不再把普通 Clash 节点冒充固定出口；固定代理场景由轻量转发器占用 `7896`，最终出口仍由 ClipProxy 决定。
- 新增只监听 `127.0.0.1:7896` 的轻量转发器：Clash HTTP 隧道 -> ClipProxy SOCKS5 认证 -> 目标连接；替代旧 Mihomo 链式实现。

### 验证

- `tests.test_launcher_proxy`：修正后定向测试通过。
- 当前机器真实出口测试成功：返回固定 IP `38.248.239.46`；停止后 `7896` 无监听进程。
- 尚未进行真实 Chat2API AI 生成请求验证；公网出口和代理链路已验证。

## 2026-09-02 展示类连续画面生成流程实现

### 已完成

- 新增展示类画面领域模型，支持不轮播 1 张、固定 2～5 张和每套方案独立 AI 决定 2～5 张。
- SQLite 增加画面级状态表和方案级继续操作锁，兼容旧 `visual_items` 首图历史；服务端公开历史过滤图片生成隐藏字段和本地路径。
- 首次展示生成保留三套方案和三张首图并行任务，并等待首图分别进入成功/失败终态后返回；单套失败不影响其他方案。
- 新增方案选择、独立会话游标、按序继续生成和上一张实际图片参考输入；一次继续操作在后端逐画面串行执行。
- 图片网关参考图以受控 data URL 传递；首图失败自动重试一次，连续画面失败后可从失败序号恢复；新增服务端选择/继续接口。
- 同步修正展示类 AI 输出校验，允许 AI 模式三套方案独立锁定不同画面数量。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：106 项全部通过。
- 定向连续画面、仓储、图片任务和 API 测试通过。
- `python -m compileall -q src chat2api`、`node --check static\\app.js`、`git diff --check`：通过。
- 未发起真实 AI 文字/图片请求；未验证真实网关对连续参考图的实际生成质量。

### 未完成

- 需要在真实 AI 网关可用时验证三套首图部分失败、后续串行图片参考和人工恢复链路。
- 前端尚未接入选择/继续接口，当前仅完成后端业务流程。

## 2026-09-02 Clash 端口自动发现

### 已完成

- 代理中转启动前自动读取 `CLASH_CONFIG_PATH`、`CLASH_HOME` 和 Clash Verge 常见配置文件。
- 支持从配置识别 `mixed-port`/`port` 的 HTTP 入口和 `socks-port` 的 SOCKS5 入口，不再固定依赖 `7897`。
- 保留 `CHAT2API_CLASH_PORT` 覆盖；可用 `CHAT2API_CLASH_PROTOCOL=http|socks5` 指定覆盖端口协议。
- 中转日志现在显示实际使用的协议和端口。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：19 项通过。
- `python -m py_compile launcher.py`、`python -m compileall -q src chat2api launcher.py`、`node --check static\\app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 请求；不同电脑的实际 Clash 配置需在对应机器上首次启动时确认日志。

## 2026-09-02 展示类连续画面流程设计复审修订

### 已完成

- 根据已确认业务逻辑补充展示类连续画面设计：三套首图部分成功返回、后续逐画面调用和串行等待、方案级继续操作幂等、独立 GPT 会话持久化、上一张实际图片输入、图片/文字失败恢复和服务端隐藏字段过滤。
- 明确方案路线锁定、首图/后续画面数据结构、方案状态和画面状态，并补充选择、继续、首图重试、失败恢复和状态查询接口边界。
- 修正整体 AI 架构设计中“AI 决定后统一数量”的冲突，统一为每套方案独立决定并锁定 2～5 张。

### 验证

- 设计文档和相关研究笔记已按项目要求完整阅读。
- `git diff --check`：通过（仅有 Windows 换行转换提示）。
- 未修改业务代码、数据库、运行数据或 `.env`；未发起真实 AI 请求。

### 未完成

- 等待用户确认修订后的设计；确认后再使用 `writing-plans` skill 编写实现计划。

## 2026-09-02 连接检测避免无条件刷新 Cookie

### 已完成

- 连接检测现在先依据网关健康状态和 Token 到期时间判断是否需要刷新会话。
- 已有明确有效的 Access Token 时直接完成检测，不再因失效 Cookie 刷新失败误报连接失败。
- Token 缺失、过期或到期时间无法判断时，仍会使用 Session Cookie 尝试换取新 Token。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：17 项通过。
- `python -m py_compile launcher.py`、`git diff --check`：通过。

### 未完成

- 需要重启当前启动控制台后重新检测；未发起真实 AI 生成请求。

## 2026-09-02 检测失败显示真实原因

### 已完成

- 修复启动器连接检测只显示 `RuntimeError` 的问题。
- 现在日志会显示异常正文的脱敏前 240 个字符，保留 HTTP 状态或会话刷新失败原因，同时隐藏 Cookie/Token。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：15 项通过。
- `python -m py_compile launcher.py`、`git diff --check`：通过。

### 未完成

- 需要重启当前启动控制台后再点击“检测连接”，才能加载新的错误显示逻辑；未发起真实 AI 请求。

## 2026-09-02 项目代理中转孤儿进程清理

### 已完成

- 定位 `7896` 端口被遗留 `verge-mihomo.exe` 占用的原因；确认其命令行指向本项目 `.runtime/proxy-bridge.yaml`。
- 启动项目代理中转前读取端口 PID 和进程命令行，仅对明确属于本项目的旧中转执行 `taskkill /T /F` 回收。
- 其他程序或 Clash Verge 主进程占用 `7896` 时保持失败并提示确认，不自动误杀。
- 已清理本机现场孤儿进程 PID `23276`，确认 `7896` 释放。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：13 项通过。
- `python -m py_compile launcher.py`、`python -m compileall -q src chat2api launcher.py`、`node --check static\\app.js`、`git diff --check`：通过。
- 当前 `7896` 无监听；未发起真实 AI 请求。

### 未完成

- 尚未在带桌面的真实 Windows 会话中完整验证“关闭后再启动”的人工流程。

## 2026-09-02 整体架构复审问题修复

### 已完成

- 服务端对 `must_change_password` 用户强制阻止业务 API，仅允许改密和登出。
- 图片任务在旧 worker 仍处于调度集合时记录重排请求，避免快速重试被吞掉。
- 新模型客户端路径对格式/结构错误执行一次有限重试；网络超时仍映射为 503。
- 新增认证门禁和模型修复重试回归测试。
- 稳定 pending 冲突回归测试的时间夹具，避免随系统日期过期。

### 验证

- 定向生成、认证、图片测试 8 项通过。
- Python 编译、JavaScript 语法和 `git diff --check` 通过。
- 全量确定性测试：`python -m unittest discover -s tests -v`，92 项全部通过；未发起真实 AI 请求。
- 修复提交：`80ee1ea`。

## 2026-09-02 启动控制台关闭释放端口

### 已完成

- 修复关闭启动控制台时，后台启动线程可能在关闭后继续拉起网页或 AI 网关的竞态。
- 统一停止子进程并等待退出；正常终止超时后升级为强制结束，避免 8775/8780 端口残留。
- 新增回归测试覆盖终止等待和强制结束路径。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：11 项通过。
- `python -m py_compile launcher.py`、`python -m compileall -q src chat2api launcher.py`、`node --check static\\app.js`、`git diff --check`：通过。

### 未完成

- 尚未在带桌面的真实 Windows 会话中逐按钮验证；未发起真实 AI 请求。
- 关闭浏览器页面不会停止服务，仍需关闭启动控制台或点击“停止”。

## 2026-09-02 项目专用 ClipProxy 链式中转

### 已完成

- 启动器新增项目专用 Mihomo 链式中转：chat2api 使用 `127.0.0.1:7896`，ClipProxy 经本机 Clash 出站，不修改系统代理、TUN 或主 Clash 订阅。
- 代理工作台和网关启动共用同一条中转路径；无本机 Clash 时明确降级为 ClipProxy 直连，不再把普通 Clash 节点显示为固定 ISP 出口。
- 默认发现 Clash 常见 HTTP 端口 `7897/7890/7891`；非标准端口可通过 `CHAT2API_CLASH_PORT` 指定，避免迁移时复制旧订阅。

### 验证

- Mihomo 配置检查通过；真实启动中转并探测出口成功，返回 ClipProxy 固定 IP `38.248.239.46`。
- 代理定向测试 10 项、全量确定性测试 87 项、Python 编译、JavaScript 语法检查和 `git diff --check` 均通过。

## 2026-09-02 ClipProxy 静态 IP 多浏览器范围研究

### 已完成

- 核对 ClipProxy 官方静态 IP 购买、提取、白名单、指纹浏览器和多设备计费文档。
- 确认官方未给出“一个静态 IP 支持几个指纹浏览器/并发会话”的固定数字，也未承诺无限并发。
- 研究笔记已保存为 `docs/research/2026-09-02-clipproxy-static-ip-multi-browser.md`。

## 2026-09-02 代理跨电脑自动路由

### 已完成

- 复现确认：当前远程 ClipProxy 端点在 Python 进程中超时，而本机 Clash `127.0.0.1:7897` 可成功返回出口 IP。
- 启动器新增自动选择逻辑：优先已保存的远程代理，失败后探测本机 Clash 常用端口并仅对本次网关进程切换，不修改系统 VPN/TUN 或 `.env` 原配置。
- 代理工作台“测试出口 IP”同步使用自动路由，避免远程端点在 Python 分流下超时却误显示失败。
- 实测自动回退可连通，但出口会随 Clash 节点变化（本轮为 `67.159.48.146`），已在提示中明确不等于 ClipProxy 固定 IP。
- 追加诊断：运行中的旧网关 `/health` 正常但 `/v1/models` 超时，需完全重启启动器/网关后才能加载自动回退环境；仅点击“检测连接”不会替换已有网关进程。

### 验证

- 代理工作台定向测试 6 项通过。
- 当前机器真实运行选择结果为 `http://127.0.0.1:7897`，出口 IP `203.27.106.146`。
- Python 编译、`compileall` 与 `git diff --check` 通过。

## 2026-09-02 AI 生成架构任务 3 修复

### 已完成

- 将创意生成服务接到可注入的 `ModelClient`，并在环境变量齐全时由 `StudioApplication` 注入 `HttpModelClient`。
- `ai_creative.py` 的提示词组装改为通过 `CompiledPrompt` 渲染，保留原有提示词内容和兼容出口。
- `schemas.py` 补上了展示类文本 URL 拦截、`content_extensions` / `keywords` 非空校验，以及三套视觉方案轮播屏数一致性检查。
- 新增回归测试，覆盖 generic model client 运行路径和展示类 schema 的收紧规则。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_schemas tests.test_generation_service -v`
- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest discover -s tests -v`
- `python -m compileall -q src chat2api`
- `node --check static\app.js`
- `git diff --check`

### 未完成

- 真实 AI 网关调用未执行；当前验证全部基于确定性测试和本地编译检查。

## 2026-09-02 已选标签保留并高亮

### 已完成

- 修正报表选择行为：已选标签不再从表格移除，而是继续显示在原分类位置并使用高亮/勾选状态。
- 保留顶部摘要、确认后整组收起、点击“修改”重新展开及点击已选项取消选择。

### 验证

- 前端专项测试、JavaScript 语法检查和差异检查通过。
- 浏览器交互确认已选项保留在表格中并高亮；未发起真实 AI 请求。

## 2026-09-01 ClipProxy 与 VPN 路由研究

### 已完成

- 核对 ClipProxy 官方帮助中心、静态 ISP 使用/白名单、协议 FAQ 与 Mihomo 官方 TUN 文档。
- 补充 Mihomo GitHub issue 的 TUN+外部 SOCKS5、Mihomo+WARP 叠加故障案例，以及论坛个案边界。
- 结论：官方未要求或建议额外开启 VPN；VPN 只在改善到 ClipProxy 的可达性/路径时可能有帮助，叠加会增加路径和回环风险。
- 研究笔记已保存为 `docs/research/2026-09-01-clipproxy-vpn-routing.md`。

### 验证

- 官方静态 IP 文档示例支持直接使用 IP+端口（账号密码或白名单）连接，并提供 SOCKS5 `curl` 验证方式。
- Mihomo 官方文档确认 TUN `auto-route` 会把全局流量导入虚拟网卡；未发现商业 VPN 必须开启的要求。

## 2026-09-01 代理工作台复核修复

### 已完成

- 修复代理工作台 SOCKS5/SOCKS5H 出口测试原先误用标准库 `urllib` 的问题，改用与 `chat2api` 一致的 `curl_cffi` 客户端。
- 增加无效端口和无效代理 URL 的容错，避免保存/测试时窗口异常。

### 验证

- `tests.test_launcher_proxy`：5 项通过。
- 使用项目 `.venv` 通过本机 `127.0.0.1:7897` 代理实测出口 IP 返回成功。
- Python 编译、`compileall` 和 `git diff --check` 通过。

## 2026-09-01 独立网络代理工作台

### 已完成

- 新增独立 `proxy_workbench.py` 入口，也可从启动控制台打开独立窗口；代理配置不再混入登录配置。
- 支持 HTTP、HTTPS、SOCKS5/SOCKS5H、地址、端口、可选账号密码的可视化编辑。
- 支持代理 URL 构造、解析、密码脱敏、保存/清除 `PROXY_URL` 和通过公网回显服务测试出口 IP。
- 新增 `tests/test_launcher_proxy.py`，覆盖凭据编码、解析和脱敏。

### 验证

- 代理定向测试 3 项通过；`python -m py_compile launcher.py proxy_workbench.py`、`python -m compileall -q src chat2api launcher.py proxy_workbench.py` 通过。
- 全量测试仍受工作树既有 `creative_studio.generation_models` 缺失、认证仓储接口缺失及 SQLite Windows 文件锁测试失败影响，与本次代理功能无关。
- 未修改当前 `.env` 的代理值，未发起 ClipProxy 真实代理测试。

## 2026-09-01 报表式标签编辑器

### 已完成

- 将正式第 2 步从章节折叠改为图 1 的报表式标签布局；分类作为表格列，选项使用紧凑选择按钮。
- 展示类和叙事类所有现有标签组统一支持独立“确认 → 上方摘要/收起 → 修改展开”状态；目标人群保留主/副选择。
- 保留现有标签配置、`creative_tags` 字段、自动保存、卖点过滤、美术级联和轮播条件逻辑。
- 编辑报表时，已选选项从可选列表逐项消失，并可通过已选标签移除后重新选择。
- 新增 `.scratch/report-tag-editor/spec.md` 变更卡及前端结构契约测试。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_frontend_tag_reports -v`：2 项通过；全量测试受工作树中既有 `creative_studio.carousel` 导入缺失和轮播校验失败影响，未通过（与本次前端改动无关）。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 浏览器实测桌面和移动端：报表确认后收起、修改后展开，`390px` 无横向溢出；未发起真实 AI 请求。

### 未完成

- 尚未人工验收真实 AI 文字/图片生成质量。

## 2026-09-01 AI 创意生成架构重构设计

### 已完成

- 基于轮播功能引入后的实际调用链，重新梳理整体 AI 架构并确认采用 B 路线：保留现有页面、工作台 API、SQLite 和 `chat2api`，重建内部生成模块接口。
- 明确文字创意采用“一次用户请求、一次正常文字 AI 调用、直接返回最终创意”；标签和轮次是给 AI 的 brief，不要求 AI 回填 `resolved_tags`。
- 将轮播建模为单个创意方案内部的 `frames`，与一批中的 3 个方案分离；第一阶段保持每个展示类方案一张首帧参考图。
- 新增并提交设计文档：`docs/superpowers/specs/2026-09-01-ai-generation-architecture-design.md`，提交 `267e4b1`。

### 验证

- 已完成设计文档自检和 `git diff --check`；本次未修改业务代码、数据库、AI 网关或运行数据。

### 未完成

- 等待用户审阅设计文档；尚未编写实现计划或开始代码重构。

## 2026-09-01 撤回临时内网访问

### 已完成

- 用户确认同事使用结束，撤回临时内网共享。
- 启动器网页服务绑定恢复为 `127.0.0.1:8775`。
- 删除 Windows 防火墙规则 `AI创意工作台网页 8775（局域网）`。
- AI 网关继续保持 `127.0.0.1:8780`。

### 验证

- 网页进程已重启并确认只监听回环地址；防火墙规则查询为空。
- 已验证本机健康接口可访问，内网地址请求失败；当前未检测到 8780 网关监听，未发起真实 AI 请求。

## 2026-09-01 临时开放网页内网访问

### 已完成

- 用户明确确认同事需要从内网访问，启用临时共享模式。
- 启动器网页服务绑定改为 `0.0.0.0:8775`。
- 防火墙仅放行 TCP 8775 的 `LocalSubnet` 入站访问；AI 网关继续保持 `127.0.0.1:8780`。
- 本机内网地址为 `192.168.1.135`，同事可访问 `http://192.168.1.135:8775/`。

### 风险和回滚

- 当前应用无登录、权限和项目隔离；临时共享期间同事可访问和修改本机全部项目数据。
- 使用结束后将 `WEB_BIND_HOST` 恢复为 `127.0.0.1`，删除规则 `AI创意工作台网页 8775（局域网）`，再重启网页服务。

## 2026-09-01 撤回网页内网开放

### 已完成

- 按用户要求撤回刚才的内网访问配置。
- 启动器网页服务绑定恢复为 `127.0.0.1:8775`。
- 删除 Windows 防火墙规则 `AI创意工作台网页 8775（局域网）`。
- AI 网关继续保持 `127.0.0.1:8780`，未对内网开放。

### 验证

- 已检查启动器配置和防火墙规则状态；当前网页与网关进程仍在运行，但均只监听回环地址。
- 已执行 Python/JavaScript 语法、仓储单测和差异检查；未发起真实 AI 请求。

### 未完成

- 当前仍为本机单用户版本；如需再次开放内网，必须重新确认并先补认证、权限和数据隔离方案。

## 2026-09-01 章节标题显示已选标签

### 已完成

- 将章节标题下的“x 项已选”替换为实际已选标签名称，展示类和叙事类均适用；多项选择以顿号分隔，长文本按标题区域截断显示。
- 美术表现风格章节同时显示已选相关度、具体风格和参考作品摘要，保持级联选择结果可见。
- 修正章节推进：确认最后一个可见章节后不再循环打开第一个章节，而是将所有章节收起。
- 保留选项点击取消、主选/辅助递补、条件章节过滤、自动保存和生成逻辑。

### 验证

- 浏览器实测展示类标题显示“全静态”等实际选项；叙事类 5 个章节均可显示已选名称。
- 最后一个可见章节确认后展开章节数为 `0`；`1280x720` 和 `390x844` 无横向溢出，浏览器控制台 error/warn 为空。
- 已恢复当前项目为展示类；未发起真实 AI 文字或图片请求。

## 2026-09-01 叙事类标签交互与展示类统一

### 已完成

- 将叙事类从“按 category 拆成多个章节”调整为与展示类一致的“一个标签组一个章节”。
- 叙事类每个章节内部仍按 category 分组展示选项，保留 5 个标签组和全部 125 个选项。
- 叙事类复用展示类相同的主选/辅助顺序、选项上限、选中摘要、章节折叠和确认继续逻辑；未修改标签 key、数据结构、API 或生成逻辑。

### 验证

- 浏览器实测叙事类显示 5 个章节；“目标人群”展开后显示 5 个分类、25 个选项，主选摘要正常。
- `1280x720` 和 `390x844` 下章节及选项无横向溢出；浏览器控制台 error/warn 为空。
- 已恢复当前项目为展示类；未发起真实 AI 文字或图片请求。

## 2026-09-01 创意类型切换固定对齐

### 已完成

- 修正“02 创意定位”标题右侧的展示类/叙事类切换布局，将工具组明确固定为占据剩余空间并靠右对齐。
- 展示类与叙事类选中状态使用同一位置和宽度，不再因模式切换出现控件跑到左侧的视觉跳动。
- 移动端继续使用整行模式切换，保留原有画幅显隐和项目保存逻辑。

### 验证

- 浏览器实测 `1280x720` 和 `390x844`：展示类、叙事类切换位置稳定，无横向溢出。
- 已恢复当前项目为展示类；浏览器控制台 error/warn 为空，未发起真实 AI 文字或图片请求。

## 2026-09-01 画幅控件移至任务说明

### 已完成

- 将横版/竖版画幅控件从“02 创意定位”标题工具组移至“01 任务说明”标题右侧，保留原有 `#aspectField`、画幅值和自动保存逻辑。
- “02 创意定位”标题右侧仅保留展示类/叙事类切换，并在桌面端保持靠右对齐。
- 移动端将画幅控件和类型切换分别整理为整行布局，避免标题挤压和横向溢出。

### 验证

- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：画幅位置、类型切换位置及展示/叙事显隐正确，无横向溢出。
- 浏览器控制台 error/warn 为空；未发起真实 AI 文字或图片请求。

## 2026-09-01 标签选项密度收紧

### 已完成

- 桌面端标签选项改为约 `190px` 的紧凑列宽，按可用空间自动排列，避免少量选项被 `1fr` 拉伸到整行。
- 选项间距收紧到 `6px`，单项高度调整为 `34px`；移动端恢复 `38px` 触控高度并保持单列。
- 保留选项选择、禁用、提示、主/辅助芯片和章节交互，不修改标签配置或数据合同。

### 验证

- `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：四项可在桌面同排、宽屏自动增列、移动端单列，无横向溢出；控制台 error/warn 为空。
- 未发起真实 AI 文字或图片请求。

## 2026-09-01 定位工具组对齐微调

### 已完成

- 移除“目标画幅”四字标签，仅保留横版/竖版分段按钮。
- 将画幅按钮贴近“创意定位”标题右侧，展示类/叙事类切换固定在同一工具组最右端。
- 移动端保持类型切换与画幅上下排列，桌面/移动端现有交互和自动保存不变。

### 验证

- `node --check static/app.js`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：标题旁控件顺序、尺寸、类型切换和画幅显隐正确，无横向溢出；控制台 error/warn 为空。
- 当前项目设置保持为展示类；未发起真实 AI 文字或图片请求。

## 2026-09-01 创意定位工具组重排

### 已完成

- 将展示类/叙事类切换从页面顶部介绍区移至“02 创意定位”标题右侧。
- 将目标画幅从高级生成设置移至同一标题工具组；叙事类仍自动隐藏画幅控件，展示类恢复显示。
- 桌面端工具组采用紧凑分段控件，移动端自动换行，保留原有模式切换、画幅选择、自动保存和生成行为。

### 验证

- `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：标题旁工具组尺寸稳定、展示/叙事切换和画幅显隐正确、无横向溢出。
- 浏览器控制台 error/warn 为空；当前项目设置已恢复为展示类；未发起真实 AI 文字或图片请求。

### 未完成

- 仍需人工验收真实 AI 生成质量和图片任务链路；当前应用仍只适合本机单用户使用。

## 2026-09-01 标签章节文案精简

### 已完成

- 移除第 2 步章节列表上方的“展示类/叙事类创意定位”摘要、流程说明和总选计数。
- 移除展开章节中重复的模块名、通用说明、`按顺序选择`提示、额外计数条以及必填未完成状态的“需要完成”文案。
- 保留章节标题、已完成数量、分类标题、已选标签芯片、选项上限和确认章节行为；未修改标签规则、API、数据库和生成链路。

### 验证

- `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 浏览器实测展示类展开章节：摘要块、重复标题、顺序提示和计数条均未渲染，11 个选项正常显示；`390x844` 无横向溢出。
- 未发起真实 AI 文字或图片请求。

## 2026-09-01 桌面工作区排版密度重设计

### 已完成

- 将正式页面的介绍区、步骤条、编辑区和结果区从固定 `1120px` 窄栏扩展为带安全边距的宽屏工作区，宽屏最多使用 `1720px`。
- 第 2 步章节闭合时使用两列排列，展开章节横跨编辑区整行；展示/叙事标签选项按桌面宽度使用三列/四列网格，减少长列表滚动。
- 右侧实时创意简报扩大到 `320px` 并在桌面滚动时吸附；第 3 步结果区改为直接占满步骤列，消除旧居中偏移造成的右侧空白。
- 移动端继续使用单列章节、固定底部操作栏和项目抽屉，不修改 API、数据库、标签规则或生成链路。

### 验证

- `node --check static/app.js`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：展示类/叙事类章节单开、展开章节横跨整行、结果区宽度正确，三种视口无横向溢出。
- 浏览器控制台 error/warn 为空；未发起真实 AI 文字或图片请求。

### 未完成

- 仍需人工验收真实 AI 生成质量和图片任务链路；当前应用仍只适合本机单用户使用。

## 2026-09-01 章节收起交互调整

### 已完成

- 移除章节底部左侧“完成本章/跳过本章”按钮，仅保留“确认本章并继续”。
- 进入第 2 步“创意定位”时自动将所有章节设为收起；当前章节即使没有选择，也可点击标题正常收起。

### 验证

- `node --check static/app.js`、`git diff --check` 通过；页面章节标题折叠逻辑保持可用。

## 2026-09-01 主辅标签顺序选取优化

### 已完成

- 将主选/辅助从两套重复选项改为统一选择池：第一次选择自动成为主选并带星标，后续选择自动成为辅助。
- 删除主选后，最早的辅助标签自动递补为主选；底层 `creative_tags` 仍按原主选字段和辅助字段保存，兼容现有接口。

### 验证

- 浏览器实测首选、后续选择、移除主选递补均符合顺序规则；单元测试、JavaScript 语法和差异检查通过。

## 2026-09-01 正式版接入方案 C 标签章节流程

### 已完成

- 将方案 C 的章节式标签选择接入正式第 2 步“创意定位”，保留现有项目、自动保存和 `creative_tags` 字段结构。
- 展示类按配置模块形成章节；叙事类按大模块下的分类拆分章节，左侧分组标题、章节序号和完成状态保持清晰。
- 主选/辅助选择、单选限制、美术风格三级级联、卖点→展示内容事实过滤、轮播条件字段和标签定义提示均改为章节内交互。
- 点击其他章节自动折叠当前章节；支持确认本章并继续和跳过本章；叙事类标签末尾问号仅在显示层移除。
- 增加依赖清理：卖点、轮播或美术相关度变化后，自动清理不再适用的临时标签，避免保存失配值。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 正式页面 `127.0.0.1:8775` 实测叙事类章节、主/辅助选择、完成状态和问号显示；展示类及条件联动沿用前轮验证。
- 1280×720 与 390×844 检查无横向溢出；浏览器 error/warn 日志为空。

### 未完成

- 未发起真实 AI 文字或图片生成请求，仍需人工验收生成质量。
- 当前页面仍只适合本机单用户使用，未涉及内网部署、认证或权限。

## 2026-09-01 标签折叠流程视觉原型

### 已完成

- 根据展示类与叙事类 Excel 的模块定义、选择规则和条件关系，新增隔离原型 `static/tag-flow-prototype.*`；没有修改两份 Excel 或正式标签配置。
- 完成 A“聚焦卡片”、B“清单工作台”、C“章节轨道”三个结构差异明显的方案，通过 `?variant=A|B|C` 和底部切换器比较。
- 三个方案都支持单模块展开、返回编辑、完成并继续、必填校验、可选项明确跳过、全部配置抽屉和展示/叙事模式切换。
- 根据 C 方案补齐展示类模块专属展示逻辑：主目标用户与附目标用户拆分为独立模块；主选/辅助角色位分离；产品卖点实时过滤展示内容；美术风格按相关度、具体风格、参考对象三级展示；动态方案使用主体×背景九宫格；语音钩子、视觉母题和轮播形式按分组呈现。
- 选择多画面轮播时动态插入轮播数量和轮播形式，进度分母同步变化；切回单画面时清除条件配置并提示。
- 新增 `.scratch/tag-accordion-prototype/spec.md`，记录设计问题、非目标、验收和回滚。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`node --check static/tag-flow-prototype.js`、`python -m compileall -q src chat2api` 和 `git diff --check`：通过。
- 浏览器实测 A/B/C 均只有一个展开模块；完成继续、明确跳过、条件模块、摘要抽屉和叙事模式切换可用，控制台无 error/warn。
- 1280px 下 A/B/C 均无横向溢出；390×844 下为单列、吸顶摘要、固定底部主操作，页面无横向溢出。
- 原型只使用内存中的代表性标签样例，未连接真实 API、SQLite 或 AI；正式页面尚未修改，等待用户选择方向。
- 本轮浏览器检查：C 方案初始展示类为 `9/12`，默认展开“动态方案”；卖点变更会清理失配展示内容；九宫格渲染 9 个组合；390px 视口 `scrollWidth=clientWidth=375`，控制台无 error/warn。

## 2026-09-01 代码规范文档

### 已完成

- 新增根目录 `CODE_STYLE.md`，按真实代码区分正式原生前端、Python 后端和隔离 React 原型的技术栈与边界。
- 统一组件职责、领域命名、文件组织、导入顺序、格式、CSS、API/数据安全和提交前检查规则。
- 明确复杂注释应解释原因与约束；JavaScript/TypeScript 对公共和复杂边界使用 JSDoc，Python 使用文档字符串。
- 在 `AGENTS.md`、README 和项目代码地图中增加规范入口；新增 `.scratch/code-style/spec.md` 记录目标、非目标、验收和回滚。

### 验证

- 本次只修改工程文档，没有修改业务代码、依赖、数据库、AI 网关或运行数据。
- 已核对规范与当前正式 `static/`、Python `src/`、测试以及 `frontend/` 原型配置一致。
- `git diff --check` 通过（仅有既有 Windows 换行转换提示）；独立读者能够准确识别正式技术栈、原型边界、注释规则、结构变更要求和最小检查。
- 根据独立读者反馈补清公共函数、上下文编码、ARIA、临时状态、依赖锁定、API 包络、秘密注入和测试夹具的适用边界。

## 当前结论

- 已从原 Web ERP 快速提取出独立项目 `D:\code\ai_creative_studio`。
- 当前独立项目是单机网页原型：网页 `8775`，AI 网关 `8780`，数据保存在自己的 `data/`。
- 展示类和叙事类生成入口、项目 CRUD、历史、采用关系、参考文件和展示类异步图片任务已经具备。
- 原 ERP 代码、数据库、账号令牌和服务端口未被本项目接管；原项目保持原样。
- 未来目标是公司内网多人使用；认证、项目归属、权限、自动备份和服务器部署尚未开始。

## 本轮文档整理

### 已完成

- 新增项目级 `AGENTS.md`，定义智能体阅读顺序、修改门禁、数据边界和验证规则。
- 新增 `项目代码地图.md`，记录真实入口、调用链、API、数据表和已知缺口。
- 新增 `docs/operations.md`，记录当前单机启停、数据、备份和恢复边界。
- 新增 `docs/变更卡模板.md`，统一后续需求和验收记录。
- 新增 `CHANGELOG.md`，建立用户可见变更记录入口。
- 新增 `docs/research/2026-08-31-ai-software-engineering-process.md`，收录 NIST、OpenAI、Anthropic、OWASP、DORA、GitHub、SQLite、SemVer 等一手资料及当前项目差距。

### 验证

- 文档路径和相互引用已检查。
- 文档整理未修改业务代码。
- 独立项目此前已通过仓储定向测试 `3 passed`、Python 编译、JavaScript 语法和本地 API 冒烟。

## 2026-08-31 启动控制台

### 已完成

- 新增 `launcher.py` 本地 Tk 启动控制台，支持保存脱敏编辑的 Access Token 和 Session Cookie。
- 支持启动、停止、重启、连接检测和打开网页；启动后自动打开 `127.0.0.1:8775`。
- 将 `启动AI创意工作台.bat` 调整为环境准备和打开控制台，不再直接占用命令行窗口。
- README 和运维手册已补充控制台用法。

### 验证

- 已完成 `python -m py_compile launcher.py`、`node --check static/app.js`、`python -m compileall -q src chat2api launcher.py`、`git diff --check`；仓储测试 `3 passed`。
- 已定位并修复 Windows 批处理仅 LF 换行导致的 `cmd.exe` 解析失败；已通过批处理级启动验证，成功拉起 `launcher.py`。

### 未完成

- 尚未在带桌面交互的真实 Windows 会话中逐按钮验证视觉效果和进程停止行为。
- 代理地址不再在控制台显示；检测连接增加等待状态和超时失败提示；Cookie-only 启动会自动换取 Access Token。
- 启动按钮改为后台拉起服务并立即反馈“启动中”，避免进程初始化阻塞控制台操作。
- 修复 Token/Cookie 超长文本导致 Tk Entry 点击卡顿：默认仅显示固定长度占位，点击输入框后直接粘贴新值，不载入旧长文本。
- “检测连接”在仅有 Session Cookie 时会自动启动网关、换取 Access Token 并回填为已配置状态。
- 修复检测流程跳过“已过期但非空”的旧 Token：存在 Cookie 时每次检测都会强制换取新 Token。

## 2026-08-31 标签选择控件

### 已完成

- 根据用户提供的叙事类和《剑侠传奇》展示类 Excel 配置，整理出 `config/creative_tag_options.json`；包含叙事类 125 个选项和展示类 11 个输入模块。
- 新增 `GET /api/tag-options` 只读配置接口；扩展服务端标签规范化和 AI 提示词分组，保留已有项目标签兼容性。
- 前端改为按叙事类/展示类动态渲染单选、多选和美术风格三级级联控件。
- 展示类支持产品卖点→展示内容事实过滤、轮播数量/形式条件显示、辅助标签和三级参考最多选择 2 项。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、标签 JSON 校验和 `git diff --check` 已通过。
- 本地页面已实际检查叙事/展示模式切换、展示内容过滤、轮播条件显示和叙事类选项选择。
- 未验证真实 AI 文字/图片生成质量；未在带桌面的真实启动器会话中逐按钮验证。

## 2026-08-31 工程协作文档配置

### 已完成

- 建立本仓库的工程协作文档约定。
- Issue tracker 采用 `.scratch/<feature-slug>/` 下的本地 Markdown。
- 变更卡和研究笔记按需保存在仓库文档目录中。

### 验证

- 已检查新增文档路径、相互引用和 Markdown 差异。
- 本次仅修改工程协作文档，未修改业务代码。

## 2026-09-01 清理旧工程技能影响

### 已完成

- 移除旧工程技能专属的导航文档和 `AGENTS.md` 中对应入口。
- 清理旧工程技能专名及安装脚本名称，保留既有变更卡、原型和研究资料。

### 验证

- 已搜索仓库文本，未发现旧技能专名或路径引用。
- 未修改业务代码、依赖、数据库、AI 网关或运行数据。

## 下一步（按优先级）

1. 用户先阅读并确认这套文档结构和边界。
2. 建立第一批固定 AI 评估样例，先验证展示类/叙事类输出质量。
3. 补齐当前单机应用的日志、配置模板和一键备份说明。
4. 另开变更卡设计多人内网版本：账号、项目归属、管理员和审计。
5. 多人版本通过内网验收后，再讨论 Windows 服务化、HTTPS 和公网门禁。

## 尚未完成

- 未把当前版本部署到公司内网。
- 未实现登录、权限、数据隔离、自动备份或公网访问。
- 未执行真实 AI 文字/图片生成验收。
- 未迁移原 ERP 历史项目、图片或数据库数据。

## 决策记录

- 2026-08-31：用户要求先整理 `AGENTS.md`、代码地图和项目管理文件，暂停直接落地多人登录/部署设计。
- 2026-08-31：研究文档完成，后续按“变更卡 → 定向验证 → 备份/回滚 → 记录进度”的小批量流程推进。

## 2026-08-31 UI 重设计原型

### 已完成

- 新增独立假数据页面 `static/ui-prototype.html`，通过 `?variant=A|B|C` 比较三栏工作台、分步创作流和结果优先画板三种信息架构。
- 新增统一原型设计系统、假项目和固定 3 套假方案；支持项目/模式/步骤/配置抽屉/方案选择/采用等内存交互。
- 原型与当前生产页面隔离，没有修改现有 `static/index.html`、`static/app.js`、`static/styles.css`，没有连接真实 API、数据库或 AI。

### 验证

- `node --check static/ui-prototype.js` 通过，本地静态服务返回 HTTP 200。
- A/B/C 桌面渲染和关键交互已检查；浏览器没有 error/warn 日志。
- 390px 宽度下三个变体均无横向溢出；展示类固定显示 3 套假方案。

### 未完成

- 尚未由用户选择最终布局或混搭方向，未把任何原型提升为正式页面。
- 尚未接入真实项目、标签、历史、图片任务或生成 API；未执行真实 AI 请求。

## 2026-08-31 UI 组件与产品参考调研

### 已完成

- 新增 `docs/research/2026-08-31-ui-component-and-app-inspiration.md`，对照 Midjourney、Runway、Adobe Firefly、Lightroom、Linear、InvokeAI 和主流 React 组件库整理下一版方向。
- 明确下一版不再采用传统 dashboard 或全量表单首屏，改为“生成 Feed + 视觉选片网格 + 紧凑项目导航 + 按需配置 Sheet”。
- 推荐组件底座为 shadcn/ui；Origin UI 只挑选少量输入组件；Magic UI、Cult UI、Aceternity 和 Tremor 不作为应用骨架。
- 建议后续以隔离的 Vite + React + TypeScript + Tailwind CSS 前端做假数据原型，保留现有 Python API、SQLite 和原生页面直到新 UI 验收。

### 未完成

- 尚未得到用户对 React/Vite 隔离原型范围的明确确认，因此没有新增依赖、脚手架或正式前端迁移代码。
- 尚未确定最终 Design System、组件版本、构建产物路径和 Python 静态托管切换方案。

## 2026-08-31 React UI 假数据原型（第二版）

### 已完成

- 用户已确认用隔离的 React/Vite 原型继续探索；新增 `frontend/`，采用 React 19、TypeScript、Tailwind CSS 和 shadcn/ui 组合方式。
- 完成三个信息架构差异明显的可点击方案：A“会话流”、B“素材审阅”、C“专注对比”，入口为 `http://127.0.0.1:8796/?variant=A|B|C`。
- 实现假项目切换、创意方向选择、采用/收藏反馈、生成模拟、参数摘要和右侧创意配置 Sheet；多选项使用可搜索的 Command/Popover 交互。
- 新增 `.scratch/ui-redesign-v2/spec.md` 记录范围与验收；旧 `static/ui-prototype.*` 保留用于对照，当前正式 `static/` 页面和 Python 后端未切换。

### 验证

- `npm run build` 通过：TypeScript 编译和 Vite 生产构建均成功。
- 在 1280×720 下检查 A/B/C 首屏、图片加载、选择状态和配置 Sheet；浏览器控制台无 error。
- 在 390×844 下检查 A/B/C，页面宽度均为 390px，无横向溢出。
- 所有项目、方案、评分和动作仍为前端内存假数据，没有发出真实 AI、API 或数据库请求。

### 未完成

- 尚未由用户确定主方案，以及是否把 A 的生成流、B 的选片网格和 C 的对比视图合并为正式产品结构。
- 尚未接入真实项目/API/SQLite/图片任务，未确定构建产物如何由 Python 服务托管，也未替换正式页面。
- 尚未实现登录、权限、数据隔离、内网/公网部署、自动备份或数据库迁移。

## 2026-08-31 旧版 B UI 最终优化

### 已完成

- 按最终设计交接优化隔离的 `static/ui-prototype.*` 旧版 B 假数据原型，未修改正式原生页面、`frontend/` React 原型或后端。
- 将流程从四步收为三步：任务说明、创意定位、生成与采用；对比视图改为第 3 步原位切换。
- 第 1 步改为展示类/叙事类两级任务类型与单一任务描述；项目名移至顶部并随项目切换更新。
- 第 3 步实现 3 个稳定方案位、完整正文展开、单项排队/生成/完成/失败/重试假状态，以及直接采用/替换。
- 增加左侧覆盖式项目栏、结果阶段简报摘要、移动端固定操作栏和炭灰 × 青绿 B 专属视觉系统。
- 更新 `.scratch/ui-redesign/spec.md`，记录最终实现边界和验证结果。

### 验证

- `node --check static\\ui-prototype.js`：通过。
- `git diff --check`：通过（仅有既有换行格式提示）。
- 本地 `127.0.0.1:8795` 浏览器检查：三步流程、两级任务类型、项目栏、定位控件、方案网格/对比、采用、失败重试均可交互。
- 390px 视口检查：底部操作栏存在，`scrollWidth` 与 `clientWidth` 均为 375，无横向溢出；浏览器 `error/warn` 日志为空。

### 未完成

- 仅验证假数据 UI，未验证真实 API、数据库、AI 文字或图片生成。
- 尚未由用户验收最终视觉，也未将原型接入正式页面。

## 2026-08-31 正式页面迁移到 B 三步工作流

### 已完成

- 用户确认将旧版 B 设计提升为正式页面；创建 `codex/formal-b-ui` 分支并建立 `.scratch/formal-b-ui/spec.md` 变更卡。
- 正式 `static/index.html`、`static/app.js`、`static/styles.css` 替换为炭灰 × 青绿三步工作流，同时继续连接真实项目、SQLite、标签配置、历史、采用和图片任务接口。
- 正式页面支持顶部项目入口与覆盖式项目栏、可编辑项目名、自动保存状态、前两步实时简报、第 3 步真实历史和移动端底部操作区。
- 保留展示/叙事分支、标签依赖过滤、两批上限、图片单项重试、旧定位历史和采用替换行为。
- `AGENTS.md` 已记录正式前端入口、原型边界、回滚方式和桌面/移动端验证要求；代码地图和变更日志同步更新。
- `.gitignore` 补充网关任务状态、生成图片和运行数据子目录，防止运行产物进入 Git。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api launcher.py`、`git diff --check`：通过。
- 正式服务在 `127.0.0.1:8797` 加载真实 SQLite 叙事项目和历史成功；三步切换、项目入口和真实结果渲染可用。
- 390px 视口无横向溢出，修复旧移动端侧栏规则造成的顶部空白；浏览器控制台无 error/warn。
- 收尾复核：默认正式端口 `127.0.0.1:8775` 已启动并加载正式页面；临时验证端口 `8797` 已停止。
- Git 检查点为分支 `codex/formal-b-ui`、提交 `e39b571`；提交后的全量 `git diff --check` 通过。

### 未完成

- 本次未发起真实 AI 文字或图片生成请求；AI 质量和真实图片任务链路仍未验证。
- 正式页面尚未部署到内网或公网，仍只适合本机单用户使用。

## 2026-09-01 顶部品牌与项目入口

### 已完成

- 将正式页面和项目抽屉中的 `AI` 文字方块替换为原创“轨道＋闪光点”矢量标识，品牌名称统一为“辅助创意工具”。
- 将原页面中部的“当前项目”入口重做为品牌右侧的“项目列表”按钮；根据后续反馈移除顶部和左栏独立命名框，改为选中项目卡内联编辑名称。
- 左侧项目栏使用真实遮罩按钮，点击右侧空白区域即可关闭；移动端顶部栏收敛为品牌图标、项目列表图标和保存状态。
- 在 `AGENTS.md` 固化顶部导航的短操作路径约定，并新增 `.scratch/header-brand-project-menu/spec.md` 变更卡。

### 验证

- `1280x720` 下项目列表按钮位于品牌右侧（约 `x=198px`），项目卡可内联改名并自动保存，切换项目不收栏，点击右侧遮罩可收回；页面无横向溢出。
- `390x844` 下项目列表按钮约位于 `x=68px`，遮罩点击区准确覆盖侧栏右侧 90px 空白；页面宽度与视口一致，无横向溢出。
- 未调用真实 AI、未修改数据库结构、AI 网关或生成链路。

## 2026-09-01 展示类轮播逐轮创意定位

### 已完成

- 展示类轮播支持用户先选择“是/否”；第 1、2 步不调用 AI，仅在最终生成请求时执行一次 AI 流程。
- 固定选择 2～5 屏后显示逐轮定位面板，提供产品卖点、展示内容、视觉母题三个选填字段；第 2 轮起默认继承第 1 轮，可切换为自定义并恢复继承。
- 选择“AI决定”时不预先生成轮次或询问屏数，三套方案在一次 AI 输出中使用统一的 2～5 屏数量。
- AI 轮播返回结构补充 `carousel_frames` 与 `resolved_tags`，空白适用标签必须从配置目录补全；结果卡片展示轮次和最终标签。
- 固定屏数校验放宽为 2～5 屏；未改变既有数据库结构和图片任务链路。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：15 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。
- 本地页面检查：固定屏数轮次页、继承/自定义切换、AI决定隐藏逻辑均正常；未发起真实 AI 请求。

### 未完成

- 尚未进行真实 AI 质量评估和真实图片生成验收；当前仅验证功能链路。

## 2026-09-01 AI接口失败诊断与会话重试

### 已完成

- 根据页面失败截图、生成失败记录和网关状态复现并定位：旧 Access Token 被上游拒绝时，网关此前只返回通用 502，未主动刷新 Session Cookie。
- `chat2api/routes_chat.py` 在 requirements/prepare/对话返回 401 或 403 时最多触发一次 Cookie 会话刷新并重试，避免重复生成请求。
- `src/creative_studio/ai_creative.py` 的接口异常提示增加 HTTP 状态和网关检查方向，不暴露令牌或完整上游响应。
- 当前网关状态已恢复：`/health` 显示令牌有效，`/v1/models` 显示 `detected=true`。

### 验证

- `.venv` 下重试判定辅助函数检查通过。
- `PYTHONPATH=src python -m unittest discover -s tests -v`：15 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未再次主动调用真实 AI 生成，避免重复消耗额度；需要重启网页/网关服务后由用户重新点击生成确认完整链路。

## 2026-09-01 启动器连接检测修复

### 已完成

- 修复启动器在 8780 已有健康网关时重复拉起新网关的问题，检测流程现在优先复用现有健康实例。
- 连接检测和 Cookie 换 Token 失败时记录脱敏后的 HTTP 状态/错误片段，不再只显示“连接失败”。
- 修复检测线程异常回调对局部异常变量的延迟引用，确保错误日志能稳定写入界面。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：15 项通过。
- `python -m compileall -q src chat2api launcher.py`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 启动器进程需要重启后加载本次修改；未再次发起真实 AI 请求。

## 2026-09-01 轮播输出契约迁移（任务1）

### 已完成

- 新增 `src/creative_studio/carousel.py` 中的 `normalize_visual_carousel_frames()`，把展示类轮播输出收敛为 `count`、可选 `form` 和连续 `frames` 的嵌套结构。
- `src/creative_studio/ai_creative.py` 的 `validate_visual_creative_recommendations()` 已切到新的轮播输出契约：三项方案、每项 `carousel` 对象、固定屏数一致、AI 屏数统一，且不再要求 `resolved_tags` 作为生成时必填用户事实。
- 新增/更新 `tests/test_carousel.py` 与 `tests/test_tag_options.py`，覆盖新嵌套形状、AI 屏数不一致、固定屏数长度/连续性错误，以及旧历史数据兼容路径。
- 代码已提交，首个实现提交为 `2672c4d`。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_carousel -v`
- `PYTHONPATH=src python -m unittest tests.test_tag_options -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `git diff --check -- src/creative_studio/carousel.py src/creative_studio/ai_creative.py tests/test_carousel.py tests/test_tag_options.py`

### 未完成

- 未发起真实 AI 请求，按任务要求也未修改 `chat2api`、数据库结构或前端。

### 追加修复

- 按复核意见补回生成结果中的顶层 `carousel_frames` 兼容字段，保持 `carousel` 作为新契约的唯一权威来源。
- 新增回归测试，确认新生成结果可经由现有历史路径继续渲染，且 `resolved_tags` 仍不作为生成时必填用户事实。
- 最新代码提交为 `9142923`，验证覆盖 `31` 项测试全部通过。

# 2026-09-02 图片任务幂等修复（review follow-up）

### 已完成

- 修正图片提交失败缓存：现在只缓存成功的 gateway 任务，同一 `request_id` 的后续重试可以重新提交，不会被本地失败结果毒化。
- 保留稳定提交键 `creative-studio-{visual_item_id}-attempt-{attempt}`、成功复用和恢复/重试隔离行为。
- 新增回归测试，覆盖“首次超时后同键重试成功”的路径。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_image_jobs tests.test_repository -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `node --check static\app.js`
- `python -m compileall -q src chat2api`
- `git diff --check`

### 说明

- 修复提交为 `0e9e5ab`。
- 未发起真实图片请求。

# 2026-09-02 图片任务幂等（任务5）

### 已完成

- 图片网关提交增加按 `creative-studio-{visual_item_id}-attempt-{attempt}` 的稳定键去重，重复提交同键会复用同一任务。
- `visual_items` 恢复与重试改为事务化，保持失败/成功/恢复边界稳定，旧 worker 不能覆盖新尝试。
- 生成服务把首帧图片派发封装成独立步骤，`image_prompt` 仍只保留在服务端。
- 新增 `tests/test_image_jobs.py`，补上重复提交、恢复重排和重试隔离回归。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_image_jobs tests.test_repository tests.test_generation_service -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `node --check static\app.js`
- `python -m compileall -q src chat2api`
- `git diff --check`

### 说明

- 代码实现提交为 `4aa9ed4`。
- 未发起真实图片生成请求。

## 2026-09-01 生成服务拆分（任务2）

### 已完成

- 新增 `src/creative_studio/generation_models.py`，把生成请求、归一化输入快照、生成上下文和生成结果收敛为冻结数据类。
- 新增 `src/creative_studio/generation_service.py`，把项目加载、输入归一化、指纹、schema 选择、预留、完成、失败回填和视觉队列派发从 `app.py` 中移出。
- `StudioApplication.generate(project_id)` 已改为 HTTP 入口薄封装，保留历史返回包络和现有 API 行为。
- 新增 `tests/test_generation_service.py`，用 fake 适配器和 fake 图片队列验证单次模型调用、空白轮播提示词可通过、叙事类不入队、展示类只入队 3 个首帧任务、异常会回填 `fail_generation`。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_generation_service -v`
- `PYTHONPATH=src python -m unittest tests.test_generation_service tests.test_repository.RepositoryTests.test_project_round_trip_and_search tests.test_repository.RepositoryTests.test_visual_history_hides_image_prompt_and_exposes_carousel_frames tests.test_repository.RepositoryTests.test_new_visual_generation_remains_renderable_through_history_path tests.test_tag_options -v`
- `python -m compileall -q src chat2api`
- `git diff --check`

### 未完成

- `python -m unittest discover -s tests -v` 仍存在与本任务无关的既有仓库失败：`create_bootstrap_admin` 缺失，以及两项旧迁移测试在 Windows 上清理临时 SQLite 文件时的锁定问题。
- 未发起真实 AI 文字或图片生成调用。

## 2026-09-02 权限登录（进行中）

### 已完成

- 已加入 PBKDF2 密码哈希、会话/CSRF 令牌摘要存储、登录限流、审计、管理员普通账号管理和项目所有者隔离。
- 已接入登录、登出、强制改密、管理员账号 API 与前端登录/账号管理界面；支持一次性 CLI 或首次启动环境变量创建管理员。

### 验证

- 认证与仓储测试 25 项通过；全量确定性测试 66 项中 65 项通过。
- 全量测试唯一失败为既有 AI 配置测试，因当前环境缺少 AI 网关地址、密钥、模型和提示词变量；未发起真实 AI 请求。
- `node --check static/app.js`、Python 语法检查和 `git diff --check` 通过。

### 未完成

- 公网 HTTPS、反向代理、外部限流、生产备份和真实公网冒烟尚未配置；当前仍默认绑定 `127.0.0.1`。
# 2026-09-02 展示类提示词输出契约统一

### 已完成

- 首帧展示提示词改为输出 `creative_summary`、`creative_sources`、锁定的 `frame_count`、`visual_continuity_rules`、完整 `frame_plan` 和 `first_frame`。
- 明确 `none`、`fixed`、`ai` 三种数量规则；AI 决定数量时三套方案可独立返回 2 至 5 张。
- 轮播提示词删除旧的 `carousel`、`carousel_frames`、`resolved_tags` 和“三套方案统一屏数”要求。
- 新增版本化后续画面提示词，单次只输出一个 `frame`，包含承接和收束字段。
- 校验器、展示画面入库和公开历史过滤同步支持新结构；服务端隐藏 `image_generation_instruction` 不进入公开数据。

### 验证

- `python -m pytest -q`：107 项通过。
- `python -m compileall -q src chat2api`
- `node --check static\\app.js`
- `git diff --check`

### 说明

- 未发起真实 AI 文字或图片请求。
# 2026-09-02 展示类连续画面架构复审与 P0/P1 修复

### 已完成

- 继续接口改为返回公开逐帧 DTO，过滤 `image_generation_instruction`、本地 `image_path` 和内部会话字段。
- 新增展示方案逐帧状态查询接口 `/api/visual-items/{id}/frames/status` 和逐帧图片接口 `/api/visual-items/{id}/frames/{frame_index}/image`。
- 首帧 `first_frame.content` 写入 `display_frames.actual_content`，后续规划可读取首帧实际画面信息。
- 进程恢复时回收过期的方案继续锁和连续画面生成状态；首图失败时继续操作返回可操作冲突，不错误调用后续画面提示词。
- 新增继续接口脱敏回归断言。
- 选择方案时通过文字模型创建独立 GPT 会话，持久化供应商返回的 `conversation_id` 和 `assistant_message_id`，后续画面复用该游标。
- 历史响应补充逐帧公开状态，新增逐帧图片接口；正式页面已接入方案选择、继续生成和画面路线展示。

### 验证

- `python -m pytest -q`：109 项通过。
- `python -m compileall -q src chat2api`
- `node --check static\\app.js`
- `git diff --check`

### 未完成风险

- 后续文字模型请求仍未通过现有 Chat2API 多模态链路传递上一张实际图片；目前上一张图片只传给图片生成网关。
- 正式前端已接入新的选择、继续和逐帧状态接口，但未进行真实浏览器流程验证。
- 经确认，本阶段采用降级连续性方案：GPT 只依据上一张画面信息和已完成记录规划；图片模型继续接收上一张实际图片作为 `ref_assets`。暂不改造 Chat2API 多模态文字链路。
- 未发起真实 AI 文字或图片请求。

# 2026-09-02 创意类提示词工程研究（进行中）

### 已完成

- 收集并核对 OpenAI、Anthropic、Google、Microsoft 的官方提示词工程与评测指南，以及 Promptfoo、DSPy、DAIR.AI Prompt Engineering Guide、prompts.chat 等社区/开源实践信号。
- 新增研究笔记 `docs/research/2026-09-02-creative-prompt-engineering-research.md`，记录来源、日期、可执行结论和社区证据边界。
- 初步形成创意提示词设计方向：将创意机制与执行细节分离；先发散生成候选，再按事实、受众、差异化、可执行性和风险收敛；用固定评估集验证提示词迭代。

### 验证

- 已通过浏览器读取官方文档和公开论文摘要；未发起真实 AI 生成请求。

### 未完成

- 尚未确定第一版优先优化展示类还是叙事类提示词。
- 尚未把研究结论改写为正式配置提示词或新增评估样例。
# 2026-09-02 AI 辅助功能三路径全链路验证

### 真实请求补充验证

- 已使用当前 `chat2api/.env` 启动临时网关并发起真实 `/v1/chat/completions` 请求。
- 通过现有 SOCKS 代理请求失败：代理握手被关闭，网关返回 `502`。
- 临时绕过代理再次请求失败：无法连接 `chatgpt.com:443`，网关返回 `502`。
- 两个临时网关进程均已停止；未修改 `.env`。

### 验证结果

- 叙事类：假模型生成、结果落库、无图片任务，`2 passed`。
- 展示类不轮播/首帧：假模型生成三套方案、三张首图任务，`2 passed`。
- 展示类连续画面：方案选择、独立会话游标、按序继续、上一张图片引用、状态恢复，`4 passed`。

### 限制

- 本机 `127.0.0.1:8775` 和 `127.0.0.1:8780` 当前未启动。
- 当前进程环境未配置 AI 网关变量；未读取或修改 `chat2api/.env`，因此未发起真实 AI 文字/图片请求。

# 2026-09-02 第一套展示类静态创意提示词

### 已完成

- 新增单文件 `config/ai_visual_static_creative_prompt_v1.txt`，目标为非轮播、单核心静态画面的展示类广告创意。
- 在同一个提示词文件内用模块标题分隔接口契约、字段语义、业务上下文、创意生成引擎、候选筛选和执行约束；接口区块可单独抽取给接口层。
- 输出结构面向创意和制作评审：三套机制不同的方案、用户张力、产品价值、证据台账、静态首帧、素材计划、制作风险、首轮验证动作和服务端私有图片指令。
- 该文件可直接作为单一提示词发送；其余模块只需在不同系统中按区块手动复制，不要求拆成多个附件。

### 验证

- 已完成文本结构和字段边界的人工复核，确认单文件内接口层与业务规则层分离。
- 未修改现有业务代码、数据库、API、前端或旧提示词；未发起真实 AI 文字/图片请求。

### 未完成

- 尚未用固定脱敏业务样例进行真实模型质量评审。
- 尚未决定是否将该新结构迁移到现有 `ai_creative.py` 校验器和展示历史；后续迁移需另行评审兼容性。
# 2026-09-02 临时开放局域网访问

### 已完成

- 网页启动器改为绑定 `0.0.0.0:8775`，启动链接为 `http://192.168.1.135:8775/`。
- Windows 防火墙新增仅允许 `LocalSubnet` 的 TCP 8775 入站规则；AI 网关 8780 仍只监听回环地址。
- 本机验证首页和 `/api/health` 的回环及局域网地址均返回 200。

### 风险与回滚

- 当前内网用户可访问网页并按账号权限操作项目；不应将端口暴露到公网。
- 结束共享时，将 `launcher.py` 的 `WEB_BIND_HOST` 恢复为 `127.0.0.1`、`WEB_URL` 恢复为 `http://127.0.0.1:8775/`，删除防火墙规则 `AI创意工作台网页 8775（局域网）`，再重启网页服务。
# 2026-09-02 撤回局域网访问

### 已完成

- 停止网页服务并释放 `8775` 监听端口。
- 删除 Windows 防火墙规则 `AI创意工作台网页 8775（局域网）`。
- 启动器恢复为 `127.0.0.1:8775`，后续启动不会再次自动开放内网。

# 2026-09-04 AI v2 会话与重试规则复审

### 本次完成

- 复核 [`AI v2 文字优先与按需生图实施设计草案`](docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md) 和 [`AI v2 正式实施计划`](docs/superpowers/plans/2026-09-04-ai-v2-text-first-implementation.md)，确认没有把图片任务拆成“每张图片一个会话”。
- 明确一批文字只创建一个文字会话；用户点击某个展示方案的图片按钮时才创建该方案唯一的图片会话。三个方案都生成图片时为 1 个文字会话 + 3 个图片会话；轮播同一方案的全部帧共享一个图片会话。
- 将“每次点击只推进一张”写成硬约束：不预取、不自动推进、不在后台生成用户尚未点击的后续帧。
- 补充网页超时、连接断开或 5xx 的非终态语义：这些情况只表示本地结果未知，重试前必须先查本地 attempt 并对账供应商会话。
- 补充对账决策：供应商已成功则原 attempt 原子完成，仍在工作则重新挂接，明确终态失败才在原图片会话内创建同一帧的新 attempt；未知或不可用不创建新 attempt，更不创建第二个图片会话。
- 修正实施计划的并行波次表：Task 2/3/6 可并行，Task 4 在输入与 Schema 契约后进行，Task 13 可在 Task 8 后用冻结 DTO 夹具与 Task 12 并行。

### 验证

- 使用全文检索核对设计稿、实施计划中的会话数量、重试、对账、状态机和隔离表述；已修正任务依赖表与会话锁定键的歧义。
- 本次只修改设计文档、实施计划和进度记录；未修改生产前端、后端、数据库、Prompt、真实 AI 链路、`chat2api/.env` 或运行数据。
- 未执行真实 AI/图片请求；未开始 Task 0-17 的代码实施。

# 2026-09-04 AI v2 Task 11 图片 Adapter 与 worker

### 本次完成

- 新增 `src/creative_studio/ai_v2/adapters/image_gateway.py`，仅将 typed 图片请求翻译为 v2 网关协议，透传 `image_session_key`、`request_key`、游标和上一帧引用摘要；供应商不支持稳定键对账或响应不可判定时统一返回 `unknown`。
- 新增 `src/creative_studio/ai_v2/image_worker.py`，实现已有图片会话内继续、失败重试前对账、未知状态不新建 attempt、明确终态失败后在原会话创建新 attempt，以及成功图片的原子落库。
- 为 worker 增加按 attempt 解析既有图片会话的 store 查询方法；未引入旧图片任务模块或旧数据库表。

### 验证

- `python -m unittest tests.test_ai_v2_image_worker -v`：3 passed。
- 未调用真实 AI/图片网关，未修改真实数据、图片、上传文件或 `chat2api/.env`。

# 2026-09-04 AI v2 Task 12/13 独立应用 API 与前端

### 本次完成

- 新增 `ai_v2.application` 与 `ai_v2.http_api`：独立选择叙事/静态/轮播用例，处理三字段输入、历史/运行/图片状态查询和稳定错误投影；未调用旧 `CreativeGenerationService`。
- 新增 `static/ai-v2/` 独立页面、脚本和样式，支持文字结果、静态按需首图、轮播逐帧按钮和 attempt 轮询；不读取 `execution` 或会话字段。
- 新增 API 与前端 contract tests；未修改旧 `static/index.html`、旧 `static/app.js` 或旧生产路由。

### 验证

- `python -m unittest tests.test_ai_v2_api tests.test_ai_v2_frontend_contract -v`：5 passed。
- `node --check static/ai-v2/app.js`：通过。
- `git diff --check`：通过（仅现有工作树换行提示）。

# 2026-09-04 AI v2 Task 14 契约、隐私与发布门禁

### 本次完成

- 新增 v2 集成测试，覆盖输入到文字 DTO、按需图片 artifact 和旧表零创建。
- 新增隐私测试，递归检查公开投影不含 `execution`、Prompt、会话游标、供应商 job id、本地路径、完整响应或堆栈。
- 新增 `creative_studio.ai_v2.release_gate` 和评测报告格式，明确 `evidence_type=deterministic_fake`、`quality_claim=contract_only`，真实模型质量标记 `not-run`。

### 验证

- v2 release gate：59 项测试通过，compileall、Node v2 语法、diff-check、boundary 全部通过。
- 未执行真实模型质量评测；未调用真实 AI/图片网关。

# 2026-09-04 AI v2 当前交接

### 状态

- Task 0-10、Task 11、Task 12 的独立 Facade/HTTP 适配与 Task 13 独立前端、Task 14 deterministic gate 已完成。
- Task 12 的正式 `app.py` `/api/v2` production 挂载未执行；Task 15 采用功能按默认策略延后；Task 16/17 因用户审批和观察周期未执行。
- Prompt registry 仍为 candidate-only，production caller 保持为空；旧 AI、旧页面和旧入口保持冻结。

### 最终验证

- 全量 unittest：322 passed。
- v2 unittest：59 passed。
- `node --check static/ai-v2/app.js`、`compileall src chat2api`、v2 release gate、`git diff --check`：全部通过。
# 2026-09-05 AI v2 正式收尾

### 已完成

- 网关复审后修复未知图片状态、显式终态重试键、续帧 cursor、唯一 Prompt caller，并从组合根移除旧 AI 生产链。
- 修复 v2 批次唯一性、失败文字重试、画幅持久化、历史重开 DTO、图片 artifact 存储边界。
- 新增 `ai_v2_adoptions` 采用快照 API；正式根页面切换为 v2 DTO 和 v2 图片/采用路由。
- 清理旧 AI 专属测试，保留认证、项目 CRUD、文件和运行数据测试。

### 验证

- 全量 unittest：202 passed。
- v2 unittest：84 passed。
- `node --check static/app.js static/ai-v2/app.js`、`compileall`、v2 release gate、boundary、`git diff --check`：通过。
- 未调用真实 AI/图片供应商，未修改 `chat2api/.env` 或真实运行数据。

# 2026-09-05 AI v2 并发与导入隔离收尾

### 已完成

- 包级初始化改为无副作用；导入 `creative_studio.ai_v2` 不再加载退休的旧 AI 模块、配置或网络依赖。
- v2 文字批次保留使用 `BEGIN IMMEDIATE`，并发同批只允许一个成功，另一个稳定返回冲突。
- 图片方案首建先原子占用本地会话占位，再调用供应商；并发首击不会创建第二个供应商会话，首次未知结果释放占位但保留稳定请求键。
- 图片 attempt 增加原子 claim；并发 worker 轮询不会重复提交同一 attempt。
- 旧 attempt 不能覆盖更新 attempt；失败、成功、对账状态更新均拒绝过期 attempt；同 revision 不同游标被拒绝。
- 叙事历史读取不再假设图片帧；轮播历史保留逐帧公开 `image_state`；重复生成自动使用第二批。
- 应用 v2 lazy composition 增加锁，避免并发首次请求构造多个 v2 store/adapter。

### 验证

- 定向 v2 回归：37 项通过；网关首次未知、worker 并发、状态机、叙事历史、轮播状态和两批生成均覆盖。
- 最终全量和发布门禁将在本条记录后重新执行；真实 AI/图片供应商仍不调用。
- `launcher.py` 既有 `WEB_BIND_HOST="0.0.0.0"` 属于高风险网络配置，按用户已有提交和安全边界未擅自修改，最终报告列为待审批项。

# 2026-09-05 Prompt 审批门禁与监听边界收尾

### 已完成

- v2 三项 Prompt registry 恢复为 `candidate` 且 `caller=null`，与 Prompt 设计文档和审批要求一致。
- 默认组合根改用 deterministic candidate text/image models；只有显式设置 `CREATIVE_STUDIO_AI_V2_LIVE=1` 才构造 gateway adapter，默认不会连接或调用真实 AI。
- 启动器网页监听恢复为 `127.0.0.1`，关闭既有的全接口监听风险；运维文档同步更新。

### 验证

- 审批门禁定向测试、live opt-in 测试和 loopback 监听测试通过。
- 全量 unittest：213 项通过；v2 unittest：95 项通过。
- 未设置 live 开关，未调用真实 AI/图片供应商，未修改 `chat2api/.env` 或真实运行数据。

# 2026-09-05 真实环境受控验收

### 已完成

- 真实 gateway 诊断确认旧远端 SOCKS5 代理握手失败；未修改 `chat2api/.env`。
- 通过进程级本机代理完成真实 v2 文字矩阵：static 3 案、narrative 5 案、carousel 3 案均通过 v2 schema 和公开 DTO 投影。
- 发现并修复候选 Prompt 缺少显式 v2 JSON 字段骨架的问题；新增候选 Prompt 契约测试并同步 registry hash，生命周期仍为 `candidate`、caller 仍为空。
- 在临时图片/job 目录完成一次真实静态图片生成，状态从 generating 到 success；仓库图片目录和真实数据库未写入。

### 约束与环境

- 真实请求仅使用临时 gateway 进程、本机代理和临时 SQLite/图片目录；测试后 gateway、临时目录均已清理。
- 远端 `.env` SOCKS5 代理仍不可用；本机 `127.0.0.1:7897` 可用，属于运行环境配置问题而非 v2 代码问题。

### 最终验证计数

- 全量 unittest：214 项通过；v2 unittest：96 项通过。
- `node --check static\\ai-v2\\app.js`、`node --check static\\app.js`、`compileall`、release gate、`git diff --check`：全部通过。

# 2026-09-05 前端浏览器冒烟复核

### 已验证

- 在临时 SQLite/目录的 deterministic Web 服务中完成登录、项目创建、标签加载、文字方案生成和单次图片生成。
- 文字结果显示 3 个候选展示方案；首个图片按钮点击后进入完成态并锁定，未预取或自动推进其他方案。
- 浏览器页面当前具备完整可用交互骨架，可以进入视觉层和信息架构设计；候选文案仍属于 deterministic 占位输出，Prompt 仍未接入 production caller。

### 验证边界

- 临时服务已停止，临时数据库、job 和图片目录未写入仓库真实数据。
- 本次未调用真实 AI/图片供应商，未修改 `chat2api/.env`，未执行正式入口切换。
- 重新执行全量 unittest：214 项通过；v2 unittest：96 项通过；前端语法、compileall、release gate、`git diff --check`：全部通过。

# 2026-09-05 Task 13 网页可用性设计第一轮

### 已完成

- v2 标签分组改为可折叠详情组，必选分组默认展开，其余分组收起，选项使用有界滚动区域。
- v2 结果卡片增加核心创意、广告文案、画面描述、故事梗概和开场钩子的字段标题。
- v2 图片操作区增加状态说明，结果网格改为响应式 `auto-fit` 布局，并补充键盘焦点样式。
- 保持原有 v2 输入契约、按需单图生成、图片完成后锁定和旧 AI 隔离不变。

### 验证

- 先写失败契约测试，再完成实现；前端定向测试：3 项通过。
- 全量 unittest：215 项通过；v2 unittest：97 项通过。
- `node --check static\\ai-v2\\app.js`、`node --check static\\app.js`、`compileall`、release gate、`git diff --check`：全部通过。
- 临时预览服务已停止，`127.0.0.1:18875` 当前无监听进程；未修改真实数据库、图片、上传文件或 `chat2api/.env`。

# 2026-09-05 主页面 v2 交互接入

### 已完成

- 保留现有主页面的顶部导航、项目侧栏、创意定位步骤条和结果区域，不再要求用户跳转到独立 `/ai-v2/` 页面。
- 主页面结果卡片接入 v2 图片会话入口：每个方案显示“生成参考图”，失败显示“重试参考图”，成功后锁定为完成态。
- 图片请求只在用户点击对应方案时发起；生成中只轮询该方案的 attempt，不再把未点击的 pending 卡片当作后台任务自动刷新。
- 文字生成完成提示改为明确引导用户点击卡片生成图片，旧的“后台自动完成”提示已移除。

### 验证

- 前端契约测试：4 项通过；全量 unittest：216 项通过；v2 unittest：98 项通过。
- `node --check static\\app.js`、`node --check static\\ai-v2\\app.js`、`compileall`、release gate、`git diff --check`：全部通过。
- 没有切换根路由到独立页面；未调用真实 AI/图片供应商，未修改真实数据库、图片、上传文件或 `chat2api/.env`。

# 2026-09-05 AI v2 主页面接入后续交接

- 新增 `docs/superpowers/handoffs/2026-09-05-ai-v2-main-page-followup-handoff.md`，记录主页面接入后的真实状态、P0-P4 后续顺序、Prompt 审批门禁、浏览器验收步骤、回滚方式和未验证边界。
- 明确正式用户流程继续使用根页面 `/`；独立 `/ai-v2/` 不是正式入口，是否清理需单独变更。
- 下一会话应先运行全量门禁和临时数据浏览器验收，再决定是否继续 Prompt 评测或申请 live caller；不得把 deterministic 结果写成生产质量结论。

# 2026-09-05 AI v2 主页面验收与候选 Prompt contract 评测

### 已完成

- 使用临时 SQLite、图片和上传目录在根页面完成 deterministic 浏览器验收；正式入口保持 `/`，没有跳转 `/ai-v2/`。
- 文字生成后出现 3 张方案卡；未点击前只有 1 个文字 run 和 3 个方案，图片 session、attempt、artifact 均为 0。
- 只点击第一张卡后恰好创建 1 个图片 session、1 个 attempt、1 个 artifact；其余两张保持 pending，旧 `generations`、`visual_items`、`adoptions` 均未写入。
- 受控失败重试先对账并复用同一图片 session 和 `request_key`：第一次 attempt 失败，第二次成功，session revision 从 1 递增到 2。
- 修复静态参考图成功后历史 DTO 缺少 `image_url`，导致按钮完成但画面仍等待的问题；新增集成回归测试，刷新后可以恢复真实参考图。
- `1280x720` 与 `390x844` 均无横向溢出，浏览器控制台无 warning/error；临时服务和目录已清理。
- 新增可重复执行的 v2 候选 contract 评测：30 个脱敏 case 定义完整，29 个可自动判定的 contract outcome 全部符合预期，23 个成功公开 DTO 私有字段泄露数为 0，7 个坏输出归类为 `model_output_invalid`。
- 评测运行使用 30 次进程内 deterministic 文字调用、0 次图片调用，没有隐藏格式修复或重试；三份候选 Prompt 的 hash、输入/输出 schema、生命周期和 caller 与 registry 对齐。
- 新增 `docs/ai/ai-v2-prompt-approval.md` 和 `config/evals/ai_v2/reports/candidate-contract-evidence.v1.json`；Prompt 仍为 `candidate`，三项 `caller` 仍为 `null`。

### 验证

- TDD RED：新增 release gate 报告测试先因缺少 `build_candidate_contract_evidence` 失败；实现后同一测试通过。图片历史回归测试也先复现缺少 `image_url`，修复后通过。
- 全量 unittest：218 项通过；v2 release gate：100 项通过，contract、compileall、Node、diff-check、boundary 全部为 `ok`。
- `node --check static\\app.js`、`node --check static\\ai-v2\\app.js`、`python -m compileall -q src chat2api`、`git diff --check`：全部通过。
- 已提交候选报告与运行时重建结果逐字段一致。

### 未做与后续门禁

- 本轮后续执行未发送真实 AI/图片请求，未修改真实数据库、图片、上传文件、`chat2api/.env`、监听地址或入口发布配置。
- `narrative-07` 的机制重复和全部真实模型质量仍为 `not-run`；deterministic 证据只支持 contract 审查，不构成 Prompt 质量或 production 发布批准。
- 独立 `/ai-v2/` 页面是否清理、受控真实模型评测、production caller 和正式发布继续留在单独审批变更中。

# 2026-09-05 旧 AI 实现退役

### 已完成

- 将此前主页面 AI v2 接入与候选 Prompt contract 材料提交为 checkpoint `c80330d`，再从干净工作树执行旧 AI 清理。
- 删除根包 27 个旧 AI Python 模块、旧 Prompt/registry、旧 v1 eval fixture/报告和 7 个旧实现测试；完整保留 `creative_studio.ai_v2`、`config/ai_v2`、`config/evals/ai_v2` 与 `chat2api`。
- 新增中立 `ProjectProjection`，项目详情/列表继续使用白名单并隐藏上传文件内部存储名；旧采用状态不再从项目仓储读取，页面继续通过 v2 adoption API 恢复。
- `StudioRepository` 收缩为用户、会话、审计、项目与项目文件能力；新库不再创建旧 AI 表，已有库中的旧表结构和记录不修改、不读取、不删除。
- `backup.py` 保留对已有旧图片表的只读完整性检查，确保历史数据库仍可备份与恢复。
- 新增退役路径守卫、项目投影测试、新库表边界和旧表哨兵保护测试；同步 README、代码地图、运维、AI 文档入口、质量评测和开发规则。
- 独立审查后修正发布 runbook 的 v2 release gate 路径、项目投影公共方法文档字符串和应用导入顺序；补充项目列表/详情经过白名单投影的 HTTP 接线测试。

### 验证

- TDD RED：项目投影测试先因模块不存在失败；仓储测试先因新库创建五类旧表失败；退役路径守卫先列出 50 个旧路径。
- 定向 GREEN：项目/API 5 项、仓储/认证/备份 34 项、退役/标签/v2 boundary/gateway 25 项通过。
- 最终全量 unittest：173 项通过；AI v2 unittest：100 项通过；v2 release gate：100 项通过。
- `node --check static\\app.js`、`node --check static\\ai-v2\\app.js`、`python -m compileall -q src chat2api`、boundary 和 `git diff --check` 全部通过。
- release gate 继续报告 `evidence_type=deterministic_fake`、`quality_claim=contract_only`、23 个公开 DTO 泄露数为 0；三份 Prompt 仍为 `candidate`、`caller=null`。

### 未做与数据边界

- 未调用真实 AI/图片供应商，未修改或删除真实数据库、图片、上传文件和 `chat2api/.env`。
- 已有数据库中的旧表与历史记录仍原样保留；后续若要归档或删除，必须另开高风险变更、先备份并完成恢复演练。
- 历史 ADR、handoff、实施计划和研究文档保留旧名称作为审计记录，不代表旧运行时仍可用。

# 2026-09-05 AI v2 正式版接入交接

- 新增 `docs/superpowers/handoffs/2026-09-05-ai-v2-production-integration-handoff.md`，将当前状态明确为“主页面和 v2 契约已接入，正式模型尚未启用”。
- 交接把主页面隐藏 `error_code`、正式入口静默使用 candidate、registry/release gate 仅支持 candidate 证据列为首批阻断项。
- 后续按 P0-P5 依次执行：基线与计划、错误可观察性和 fail-closed、Prompt/caller 审批、受控真实文字、受控真实图片、本机正式切换。
- 本次只写交接文档；未启用 live，未调用真实 AI，未修改真实数据库、图片、上传文件或 `chat2api/.env`。

# 2026-09-05 AI v2 下一会话接手与 P0 回归

### 已完成

- 读取 `AGENTS.md`、`progress.md`、AI v2 正式接入计划与交接文档、运维/代码规范、AI 文档和 ADR；保留接手时全部未提交修改。
- 确认分支为 `codex/tag-accordion-prototype`、HEAD 为 `1bb6dd1`；8775/8780 无监听，`CREATIVE_STUDIO_AI_V2_LIVE` 未设置。
- 完成 P0 回归门禁：全量 unittest 176 项、AI v2 unittest 103 项通过；Node 两份正式脚本、compileall、release gate、boundary 和 `git diff --check` 均通过。
- release evidence 仍为 `deterministic_fake` / `contract_only`，真实模型质量 `not-run`；没有真实文字/图片调用。

### 未做与下一门禁

- 当前展示类轮播仍是 carousel-only：一次 carousel Prompt 规划 3 套方案，静态 Prompt 不先行调用；用户必须先确认保持该语义或改为两阶段 static→carousel。
- 在产品语义确认和三份 Prompt 独立审批前，不修改调用链、registry、production caller 或 live 配置。

# 2026-09-05 展示类轮播产品语义确认

- 用户明确确认保持当前 carousel-only 逻辑：展示类选择轮播时只调用 carousel Prompt，不先调用 static Prompt；静态 Prompt 继续只服务非轮播展示类。
- 现有输入契约、应用分发、轮播规划和逐帧会话回归已覆盖该语义，本次无需修改源码或调用链。
- 该确认不等同于三份 Prompt 审批、production caller、真实模型调用授权或正式发布批准。

# 2026-09-05 AI v2 Prompt 受控评测审批

- 用户分别批准 `narrative-text-v1`、`static-text-v1`、`carousel-text-v1` 进入受控真实文字评测。
- 用户确认保持现有 Prompt；具体效果内容由其他材料承载，本次不新增效果字段或扩展输出范围。
- 三份 Prompt 仍保持 `lifecycle=candidate`、`caller=null`；本次批准不包含 production caller、默认 live、图片调用或正式发布。
- 真实文字评测仍需在执行前单独确认脱敏样例、最大调用次数、总预算/预计成本、隔离输出目录和停止条件。

# 2026-09-05 受控真实文字评测预检

- 用户确认使用项目内置标签，并表示不设金额预算上限；硬上限仍为 30 次文字调用、0 次图片调用，异常泄露/状态不明/超调用数立即停止。
- 使用 `.venv` 在 8780 启动本项目 `chat2api` 网关进行只读预检；`/health` 返回 `ok=true`、`has_token=true`、`auto_refresh=true`。
- `/v1/models` 返回 `detected=false`，仅返回候选模型列表，无法证明上游会话已通过验证；因此未发送任何真实文字或图片模型请求。
- 预检网关已关闭，8775/8780 无监听；未读取或修改 `chat2api/.env`，未写入真实数据库、图片或上传目录。

# 2026-09-05 受授权会话刷新结果

- 用户明确授权使用现有 Session Cookie 刷新会话并写回 `chat2api/.env`。
- 本机网关执行一次 `POST /v1/session`；接口返回 `refresh_ok=false`、`has_token=true`、`auto_refresh=true`，刷新失败状态已记录但未输出错误正文或任何凭据。
- `/v1/models` 仍返回 `detected=false`；没有发送真实文字或图片模型请求。
- 网关已关闭，8775/8780 无监听；除网关授权刷新对 `chat2api/.env` 的既定写入外，没有修改其他配置、数据库、图片或上传目录。

# 2026-09-05 受控真实文字评测完成

- 使用项目内置标签、临时 SQLite 和独立 `.scratch/ai-v2-real-text-eval/` 输出目录，调用当前本机 `chat2api` 网关的 `gpt-5-6-mini`。
- 评测完成 30 次文字调用、0 次图片调用；没有重试或隐藏格式修复；总耗时约 418 秒。
- 叙事：10/10 schema-valid，均返回 5 套方案；静态：10/10 schema-valid，均返回 3 套方案。
- 轮播：2/10 schema-valid；8 个失败均为 `model_output_invalid`，字段路径集中在 `$.items[].frames`，未创建图片会话。
- 成功公开 DTO 私有字段泄露数为 0；延迟范围约 10.4–32.6 秒，平均约 13.9 秒，中位数约 13.1 秒。
- 隔离报告为 `.scratch/ai-v2-real-text-eval/report.json`；证据类型为 `controlled_real_text_eval`，质量结论仍为 `real_text_quality_not_production`，不得描述为生产质量通过。

# 2026-09-05 轮播真实评测失败根因诊断

- 直接根因：`carousel-text-v1.txt` 只要求每套返回 2–5 个连续帧，没有把 `visual_carousel_count` 的固定选择明确写成“每套必须恰好返回 N 帧”；而 `carousel_visual.py` 在 schema 通过后额外强制每套帧数等于所选 N，错配统一映射为 `model_output_invalid` / `$.items[].frames`。
- 最小 deterministic 复现已确认：选择 4 屏、返回合法 2 帧时稳定得到同一错误；因此真实评测中前两次偶然命中 2/3 屏，后续错配失败与该契约冲突一致。
- 另一个独立缺口：内置配置屏数标签是 `2屏`/`3屏` 等中文值，`_requested_count()` 只接受纯数字或 `AI决定`；当前评测脚本使用数字字符串绕过该问题，因此它不是本次 8 个模型输出失败的直接原因，但真实页面固定屏数可能在模型调用前失败。
- 未修改 Prompt、输入解析或校验逻辑；待用户确认后再决定采用“Prompt 明确固定 N”还是调整产品契约。

# 2026-09-05 轮播固定屏数契约修复

- 在 `carousel-text-v1` Prompt 中明确：固定 `visual_carousel_count` 时每套必须恰好返回所选帧数；`AI决定` 时才允许选择 2–5 帧且三套统一。
- `_requested_count()` 现在接受内置标签 `2屏`、`3屏`、`4屏`、`5屏`，并继续兼容纯数字和 `AI决定`。
- 新增回归测试覆盖 Prompt 固定屏数指令和 `3屏` 输入；RED 阶段分别复现缺失指令与解析失败，GREEN 后通过。
- 更新轮播 Prompt hash 为 `9a1d7fd6505743af3b41b8f86fe5fe6b7bef7002fb6888942d90274d125229d4`；由于 Prompt 文本变更，轮播审批已标记为“需修改后再评”，叙事/静态审批不变。

### 修复后验证

- 全量 unittest：178 项通过；AI v2：105 项通过。
- 单独 release gate：105 项通过，`v2-contract`、compileall、Node、diff-check、boundary 均为 `ok`；并行首次运行的既有 adoption 时间戳抖动单独重跑后通过。
- 既有 30 次真实文字评测使用旧轮播 Prompt hash，不能作为修复后质量证据；本次未追加真实调用。

# 2026-09-05 轮播修复后受控重测

- 用户要求只重测轮播文字；使用修复后的 Prompt、内置标签、当前 `gpt-5-6-mini` 网关和独立 `carousel-rerun.sqlite3`。
- 完成 10 次轮播文字调用、0 次图片调用；9/10 schema-valid。
- 固定 2/3/4/5 屏的 9 个 case 均返回三套方案且帧数分别精确匹配所选屏数；`carousel-08` 仍有 1 次 `model_output_invalid`，字段路径为 `$.items[].frames`。
- 成功公开 DTO 私有字段泄露数为 0；总耗时约 138 秒，延迟约 11.4–17.8 秒。
- 新报告位于 `.scratch/ai-v2-real-text-eval/carousel-rerun-report.json`；质量结论仍为 `real_text_quality_not_production`。图片链路尚未测试。

### carousel-08 失败定位

- `carousel-08` 的输入固定选择 3 屏，错误路径 `$.items[].frames` 对应 `carousel_visual.py` 第 102 行的 `frame_count_mismatch`，说明至少一套模型方案返回的帧数不是 3。
- 报告未保留供应商原始响应，因此无法安全确定具体返回了 2、4 还是 5 帧；没有证据表明是图片调用或会话问题。
- 该 case 的任务说明是“首帧失败不解锁第二帧”的状态行为描述，不是自然创意 brief，可能增加模型把运行规则混入轮播规划的概率。

# 2026-09-05 轮播 AI决定屏数重测

- 按用户要求执行第二轮 10 个轮播文字 case，其中 9 个固定屏数、1 个 `AI决定`；AI决定 case 使用自然的多屏创意 brief，图片调用仍为 0。
- 10 次文字调用完成，9/10 schema-valid；`AI决定` case 成功，三套方案统一选择 3 帧；固定 2/4/5 屏及其他 3 屏 case 均精确匹配。
- 唯一失败为 `carousel-02`，错误路径为 `$` 的 `model_output_invalid`，不属于帧数错配；无私有字段泄露、无重试或图片会话。
- 报告位于 `.scratch/ai-v2-real-text-eval/carousel-ai-count-rerun-report.json`；仍属于受控真实文字证据，不构成 production 质量通过。

# 2026-09-05 受控真实图片评测预检

- 已读取图片评测 handoff、下一会话 handoff、AGENTS、项目代码地图、运维手册、AI 总纲、代码规范和 Prompt 审批记录；未修改 Prompt、registry、caller、live 开关或 `chat2api/.env`。
- 静态/轮播图片 deterministic 基线 30 项通过；AI v2 全套 106 项、全量 unittest 179 项、release gate、compileall、Node、boundary 和 diff-check 均通过。
- 8775/8780 当前均在监听；8780 的 `chat2api/images/`、`chat2api/image_job_state/` 和项目 `data/images/` 已有非空运行数据，不能作为隔离图片评测环境；健康和模型列表只读检查通过，未发起图片请求。
- 真实图片评测仍待明确授权：use case 为 static 单图 + carousel 两帧，建议最多 3 次供应商图片提交（1+2）、模型沿用 `gpt-5-6-mini`、临时网关/SQLite/图片目录、unknown/认证失败/超预算即停；本次预检不构成图片调用批准。

# 2026-09-05 受控真实图片评测停止于 provider unknown

- 按用户“继续任务”执行默认边界：专用网关 8791、临时 SQLite/图片/job 目录、`gpt-5-6-mini`，最多 3 次图片提交；没有调用文字模型。
- 静态首次点击实际接受 1 个供应商 job，轮询观察到 working 后供应商返回普通 `failed`；v2 adapter 按契约映射为 `unknown`，未创建重试 attempt，随后立即停止，未执行重复点击验收。
- 本地状态保留为 1 个 image session、1 个 generating attempt、0 个 artifact；供应商失败分类为网络代理关闭。轮询 73 次；未发生第二 session 或隐藏重试。
- 轮播未发起真实图片请求，原因是静态 provider unknown；没有把未执行项记为通过。控制令牌预检期间的 2 次 401 未创建供应商 job。
- 报告：`.scratch/ai-v2-real-image-eval/static-real-image-report.json`、`.scratch/ai-v2-real-image-eval/carousel-real-image-report.json`；两份均为 `controlled_real_image_eval`、`status=not_exercised`，不构成生产质量通过。
- 专用网关已停止，8791 已释放；现有 8775/8780 未改动。报告无 Prompt、Cookie、token、job/session 标识或绝对路径；隔离图片目录无生成文件。

# 2026-09-05 AI v2 图片评测交接后回归

- 接手后确认 8775、8780、8791 均未监听，`CREATIVE_STUDIO_AI_V2_LIVE` 未设置；现有工作树修改全部保留。
- deterministic 静态/轮播图片测试 12 项通过；AI v2 release gate、Node、compileall、boundary 和 `git diff --check` 通过。
- 使用 `.venv` 重跑全量 unittest：首次出现既有 adoption `updated_at` 秒级抖动，定向重跑后全量 180 项通过。
- 未发起新的真实文字或图片调用，未修改 `chat2api/.env`、真实数据库、图片或上传目录。

# 2026-09-06 AI v2 接手核验与 readiness 设计输入

- 接手分支 `codex/tag-accordion-prototype`、HEAD `1bb6dd1`；已保存既有工作树快照，保留全部未提交修改。8775/8780/8791 未监听，进程/用户/系统级 live 均未设置。
- 新鲜验证：全量 unittest 180 项、静态/轮播定向 12 项、release gate 内 AI v2 106 项通过；Node、compileall、boundary、diff-check 通过。证据仍仅为 deterministic contract。
- 核实三份 registry 为 candidate/caller=null；叙事/静态仅有受控评测批准，修订后的轮播仍需重评。正式入口实际已 fail-closed，operations/代码地图相关段落滞后。
- 图片交接和现存报告存在冲突：旧记录写 unknown/轮播未执行，当前 JSON 写成功但提交数与 final handoff 不符，轮播两帧 artifact hash 前缀相同。尚未核清来源，不作生产通过结论。
- 独立 production gate 的范围、验收和回滚建议已记录于 `docs/superpowers/handoffs/2026-09-06-ai-v2-readiness-baseline.md`；本轮未实现 gate 或新增代码测试。
- 本轮仅新增核验文档并追加本记录；没有真实模型请求、生产批准、live 切换、运行数据写入或 Git 提交。
- 本轮随后按 TDD 新增独立 `production_gate.py`：candidate registry 以非零阻断，临时 production registry 验证三类 canonical caller 可达、caller 唯一性和 `max_model_calls=1`；新增 3 项定向测试通过。该 gate 仍只证明 deterministic contract，不批准 live 或 production Prompt。
- readiness gate 增加 composition root factory 存在性和 use case/output schema 映射检查；定向测试扩展为 4 项通过。
- 同步修正 `docs/operations.md` 与 `项目代码地图.md` 的过时描述：正式入口未启用 live 时 fail-closed；candidate model/image 仅由测试显式注入。production gate 与 v2 应用集成定向测试共 10 项通过，`git diff --check` 通过。
- 图片评测证据核查完成：发现 `finalize_unknown_report.py` 与 `run_image_eval.py` 会写同一路径，现存 JSON 混有 unknown 与另一轮成功字段，状态标为 `evidence_conflicted`；新增 `docs/superpowers/handoffs/2026-09-06-ai-v2-image-evidence-reconciliation.md`，未覆盖或删除任何 scratch 证据。
- 按用户授权完成新的隔离真实图片评测：`.scratch/ai-v2-real-image-eval-20260906/`，static 1 次提交成功，carousel 2 次提交完成两帧；总提交 3，PNG，1 个轮播 session、revision=2、公开私有字段泄露 0。8791/7896 已停止；未调用文字模型、未改 `.env`/live/registry/真实数据。修正了评测脚本累计提交数报告错误，并保留旧冲突目录不动。
- 执行正式切换前备份 dry-run：生成 `.scratch/backup-smoke-20260906` 只读 manifest，未复制或修改真实运行数据；临时备份恢复测试 7 项通过，均验证 `verified`/引用完整性和篡改拒绝。production gate、网关回归定向测试 23 项通过。
- 用户明确批准叙事、静态、轮播三份 Prompt 全部晋级 production；registry 已绑定三个 canonical caller。production readiness gate 通过，candidate contract gate 从临时降级 registry 重建并通过 30 case；未启用 live、未发起新的真实请求。
- 已创建正式切换前交接：`docs/superpowers/handoffs/2026-09-06-ai-v2-production-cutover-handoff.md`。下一会话从备份/restore smoke、显式 live 传递和本机 smoke 继续；正式切换仍需新会话明确授权。
# 2026-09-06 AI v2 本机正式切换

## 已完成

- 收到用户明确授权后停止残留启动器，确认 `8775`、`8780` 无监听。
- 对真实 `data/creative_studio.db`、`data/images/`、`data/uploads/` 完成正式备份：`.scratch/production-cutover-backup-20260906-$(Get-Date -Format HHmmss)/`。
- 在隔离目录 `.scratch/production-cutover-restore-smoke-20260906/` 完成恢复 smoke，`verified=true`、`references_verified=true`。
- 启动器环境显式传递 `CREATIVE_STUDIO_AI_V2_LIVE=1`；单实例网页和网关启动成功，网页 health 200，网关 `ok=true`、`has_token=true`。
- 关闭 live 后组合根返回 `ai_not_enabled`，随后服务已停止，端口均无监听。

## 验证与未完成

- AI v2 网关运行时/生产门禁定向测试 22 项通过；编译、Node 检查和 `git diff --check` 通过。
- 全量 unittest 运行 184 项，其中 183 项通过，1 项因环境缺少 `curl_cffi` 导入失败（`tests.test_chat2api_web_client`）。
- 未对真实项目执行文字或图片 smoke，因为本次授权未指定项目 ID；未擅自消耗真实模型额度。
- 未修改 `chat2api/.env`、真实数据库、图片或上传文件；未提交工作树。

## 2026-09-06 真实 smoke 停止记录

- 按用户选择使用展示类项目 `12`，启动 live 单实例后执行一次真实文字 smoke。
- 网关返回 HTTP 502，应用分类为 `provider_unavailable`，`phase=text`、`retryable=true`；按停止条件未继续图片调用或重试。
- 服务已停止，`8775`、`8780` 均无监听；未执行真实图片 smoke。

# 2026-09-06 轮播续帧异步 job 对账修复

- 根因确认：续帧提交返回异步 `job_id` 但本地未写入当前 attempt；后续轮询错误回退到同一会话首帧的 job，导致续帧可能被首帧结果完成。
- 修复 `store.py`：异步 working 状态即使暂时没有会话游标，也持久化当前 attempt 的 provider job 并标记 generating。
- 修复 `image_worker.py`：pending/generating attempt 只查询自身 provider job；仅历史 failed attempt 保留会话 job 兼容回退。
- 新增轮播回归测试，覆盖首帧成功、续帧排队、续帧独立 job 对账；相关 20 项测试通过。
- 使用本机网关真实验证同一轮播会话的首帧+第二帧（attempt 17/18，共用一个 image session、同一 conversation、两个独立 provider job）和第三帧（attempt 16）均成功；未创建第二个 image session。
- `/app.js` 实际 HTTP 服务返回已包含 `imageBusyItemId`，Node 检查、compileall、diff-check 通过。
- 继续生成前端补齐直接 `{attempt_id,status}` 响应的轮询绑定；此前只读取旧 `operation.operation_id`，导致提交成功后前端没有继续跟踪。新增前端回归测试 7 项通过；截图对应方案的 attempt 19 已真实轮询至 success。
- 继续生成改为复用单帧提交/轮询函数，并将历史刷新失败与图片提交失败分开处理，避免任务已提交却被前端误报为 `AI 请求失败`。

# 2026-09-06 续帧陈旧页面状态修复

- 发现截图中的方案卡仍显示第 2 帧未生成，但真实数据库中对应 attempt 已成功；点击继续时后端返回已完成，前端表现为误导性提示。
- `static/app.js` 的继续生成入口现在会先刷新历史，再选择下一帧；支持已有 generating 帧，并对无可提交帧和 `state_conflict` 给出明确提示。
- 页面脚本版本更新为 `/app.js?v=20260906-continue2`，8775 实际返回该版本及新逻辑。
- 新方案 107 首帧真实提交创建 `attempt_id=25`，状态由 generating 变为 success；定向回归 14 项、Node 检查和 diff-check 通过。
- 同一方案 107 的第 2 帧通过续帧入口创建 `attempt_id=26` 并最终 success，确认同一 image session 的多轮链路可用。
- 网页请求日志确认陈旧卡片会对已成功的 105/106/107 首帧重复 POST，并收到旧 attempt 的 200 success；前端单帧提交现在会先刷新历史并跳过该重复提交。
# 2026-09-06 继续排查网页点击到生成请求

- 复核正式前端发现“确认定位”点击原先吞掉 `saveProject` 异常后仍推进到生成页，可能造成页面状态与服务端项目状态不一致；现改为保存失败立即停止推进。
- 在定位确认和文字生成入口增加脱敏控制台事件日志，记录项目 ID、步骤、是否排队及 run ID，不记录提示词、Cookie、Token 或完整请求体。
- `node --check static/app.js` 和 `git diff --check` 通过；真实浏览器多轮图片端到端点击仍待下一步用已登录会话验证。
- 诊断确认后端真实数据库中的轮播方案 108：首帧 attempt 27 success，续帧 2 通过 attempt 28 success，复用同一 image session 且使用独立 provider job；未发现后端首帧/续帧对账错误。
- 前端根因修复：图片 operation/poll timer/status 由方案 ID 改为 `scheme_id:frame_index` 键，避免某一帧残留状态静默阻断后续帧；同步 success 路径也会清理“继续生成中”状态。
- 新增 3 帧同 session 回归测试；轮播、图片 worker、前端回归共 12 项通过。
- 更新正式脚本缓存版本至 `continue3`，并通过实际 HTTP 读取确认 8775 返回新版本及 `frameOperationKey`/按帧轮询逻辑。
- 直接相关验证扩大为 16 项通过；全量 unittest 193 项仍有既有 Prompt deterministic fixture 不匹配及 Windows 临时 SQLite 文件锁错误，未归因于本次续帧改动。
# 2026-09-06 轮播续帧误判已完成修复

- 根据用户截图和“已完成，请刷新页面”提示定位：指定后续 frame 时，状态读取错误回退到首帧 `item.image_status`，首帧 success 会把未生成后续帧误判为已完成。
- 现已改为指定 frame 时只读取该 frame 状态，缺失按 pending 处理；正式脚本缓存版本更新为 `continue4`。

# 2026-09-08 开发机、部署包和服务器代码基准盘点

- 新增只读代码盘点脚本 `scripts/code_inventory.ps1`，纳入 `src`、`static`、`config`、`chat2api`、`tests` 和关键启动文件；排除 `.env`、私有配置、虚拟环境、数据库、图片、上传、日志、缓存和暂存内容。
- 开发机当前工作树清单：112 个文件、1,141,279 字节、聚合 SHA-256 `7f29098da58e5ae8a52acd1329ab941976ee8e1a0b07fbe438fdf8e6ba114d9f`。
- 2026-09-06 部署包清单：112 个文件、1,141,155 字节、聚合 SHA-256 `e0261357199ce918f5429a24e9afe2304ecca924554e2c1d8ce5b13ec33cea88`。
- 逐文件比较只有 `launcher.py` 不同：开发机候选改为外部私有配置目录并传递 `CHATGPT_ENV_PATH`，部署包仍读取 `chat2api/.env`；服务器当前实际使用后者。本轮只记录差异，未覆盖或回退用户已有修改。
- 确定开发机 Git 仓库为唯一代码权威源，服务器只作为已发布运行副本；服务器 SQLite、图片、上传和生产 `.env` 则是生产数据/配置权威源。
- 当前 `HEAD` 为 `1bb6dd1c7a523f2f560af5c74d5d62ec0e7fa49d`，但大量现有开发成果尚未提交，不能把该提交当作当前完整代码基准。
- 新增 `docs/deployment/code-baseline-20260908.md`；待取得服务器现场聚合哈希、决定 `launcher.py` 配置路径并完成新鲜全量验证后，再创建正式 Git 基准提交/tag。
- 使用项目 `.venv` 和当前工作树完成新鲜全量 unittest，200 项通过；未发起真实 AI 或图片请求，未修改运行数据和生产配置。
- 首次服务器执行在 Windows PowerShell 5.1 中因绝对 `OutputPath` 被重复拼接而停止，未写入清单；盘点脚本现已兼容绝对/相对输出路径，服务器可直接改用相对输出路径重跑。
- 服务器清单为 111 个文件、1,140,416 字节；与部署包逐文件比较后，清单中的 111 个文件全部一致。唯一漏扫项为 739 字节的 `启动AI创意工作台.bat`，原因是 PowerShell 5.1 未正确解码脚本中的中文文件名；脚本改为按根目录 `.bat` 扩展名发现批处理。
- 仓库规则、运维文档和服务器现实均使用 `chat2api/.env`，因此开发机 `launcher.py` 已移除未落地的外部配置目录选择和 `CHATGPT_ENV_PATH` 注入，与部署包行为收口；未读取或修改任何 `.env` 内容。
- 收口后开发机候选与部署包均为 112 个文件、1,141,155 字节、聚合 SHA-256 `e0261357199ce918f5429a24e9afe2304ecca924554e2c1d8ce5b13ec33cea88`；新鲜全量 unittest 200 项、compileall、Node 语法和 `git diff --check` 通过。
- 服务器直接核验漏扫的启动批处理：739 字节、SHA-256 `6390ffc13978d6049fcaffaab6c47c25a81bfb1d0dad0f4d03a2a15e25d60991`，与部署包一致。合入后服务器完整清单同为 112 个文件、1,141,155 字节、聚合 SHA-256 `e0261357199ce918f5429a24e9afe2304ecca924554e2c1d8ce5b13ec33cea88`。
- 代码盘点完成并封板：开发机 Git 仓库为唯一代码权威源，服务器为已发布运行副本；服务器 SQLite、图片、上传和生产 `.env` 为生产数据/配置权威源。正式 Git 基准提交和 tag 留待下一步。
- Git 整理将 47 个既有文件修改和 23 个新增代码/测试/文档文件纳入一次基准快照；`.scratch/`、日志、暂存目录和私有配置已加入忽略规则，暂存区未包含 `.env`、数据库、图片、压缩包或日志。
- 正式基准使用 annotated tag `production-baseline-20260908`；当前仓库未配置远端，提交和 tag 仅保存在开发机，待后续单独配置代码托管和推送流程。
- 首次将基准快进到 `master` 后，系统级 `core.autocrlf=true` 把 103 个盘点文本检出为 CRLF，文件字节指纹发生变化；代码语义和 `.bat` 未变化。新增 `.gitattributes` 固定普通文本为 LF、Windows `.bat` 为 CRLF，使 Git 检出稳定并可复现规范化代码指纹。
- 盘点脚本升级为 `creative-studio-code-inventory.v2`，同时记录原始字节摘要，并对 UTF-8 文本统一换行为 LF 后生成跨平台代码摘要。开发机与部署包规范化结果一致：112 个文件、1,135,704 字节、SHA-256 `b929837a172cb8dfbd7de3eebd62c8c3dab6ff82f933b1bbdbe2918914156e30`；服务器原始字节指纹 `e026...ea88` 继续保留为现场证据。
