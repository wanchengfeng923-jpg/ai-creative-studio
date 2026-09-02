# 权限登录与账号管理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Python + SQLite + 原生前端工作台中加入安全的账号登录、管理员账号管理和按项目所有者授权，同时保持创意生成与图片任务合同不变。

**Architecture:** 新增独立认证服务层和 SQLite 增量迁移；密码使用可升级的 PBKDF2 哈希，会话只在数据库保存令牌哈希，浏览器使用 HttpOnly 会话 Cookie 和独立 CSRF Cookie。`app.py` 统一认证/授权后再调用现有仓储业务方法，`projects.owner_user_id` 作为项目和关联资源的访问边界；当前仍只监听 `127.0.0.1`。

**Tech Stack:** Python 标准库 `hashlib`/`hmac`/`secrets`/`argparse`、SQLite、Python `unittest`、原生 HTML/CSS/JavaScript。

**Spec:** `docs/superpowers/specs/2026-09-01-auth-permissions-design.md`

## Global Constraints

- 本次不绑定局域网或公网，不配置域名、HTTPS、反向代理、防火墙或外部身份提供商。
- 不提供自助注册、用户删除、项目共享或普通用户改角色；管理员只管理普通账号。
- 历史项目迁移给首个 Bootstrap 管理员；管理员可访问全部项目，普通用户仅可访问自己的项目。
- 不修改 AI 网关、提示词、生成结果结构、图片任务协议和现有业务字段合同。
- 密码最少 3 位；公网部署建议使用更长的随机密码。用户名为小写 ASCII 标识符，长度 3-64，允许字母、数字、`.`、`_`、`-`。
- 数据库只保存密码/会话/CSRF 的哈希，不保存明文密码或会话令牌；日志不得记录秘密、完整请求、模型回复或文件内容。
- 所有业务 API 必须认证；所有写请求（登录除外）必须验证 CSRF；资源授权必须防止 IDOR。
- 测试只使用临时数据库和脱敏夹具，不访问真实 `data/`，不发起真实 AI 请求。
- 完成后更新 `CHANGELOG.md`、`progress.md`、`README.md`、`docs/operations.md` 和变更卡验证记录。

---

### Task 1: 建立认证纯函数和安全参数测试

**Files:**
- Create: `src/creative_studio/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- `normalize_username(value: str) -> str`：返回规范化小写用户名，非法格式抛出 `AuthDataError`。
- `validate_password(value: str) -> None`：验证长度和类型，失败抛出可安全展示的认证错误。
- `hash_password(password: str) -> str` / `verify_password(password: str, encoded: str) -> bool`：使用带算法、迭代参数、盐和摘要的 PBKDF2 编码；比较使用常量时间比较。
- `new_token() -> str` / `token_digest(token: str) -> str`：生成不可预测 URL-safe 令牌并只提供摘要给仓储。
- `AuthDataError`：继承 `RuntimeError`，错误信息不包含秘密。

**Steps:**
- [ ] 先在 `tests/test_auth.py` 写用户名、密码长度、哈希验证、错误密码和令牌唯一性的失败测试。
- [ ] 运行 `PYTHONPATH=src python -m unittest tests.test_auth -v`，确认测试因模块缺失或行为缺失而失败。
- [ ] 实现最小纯函数和格式解析；拒绝空值、超长值、非法用户名和低于 3 位密码。
- [ ] 重新运行定向测试并确认通过；补一条旧/未知哈希格式返回 `False` 而不是抛出内部异常的测试。

**Verification:** `PYTHONPATH=src python -m unittest tests.test_auth -v`

### Task 2: 扩展 SQLite schema 和认证仓储

**Files:**
- Modify: `src/creative_studio/repository.py`
- Test: `tests/test_repository.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- 增量 schema 版本迁移，创建 `users`、`sessions`、`login_attempts`、`audit_logs`，为 `projects.owner_user_id` 创建索引。
- 用户操作：`create_bootstrap_admin`、`create_user`、`list_users`、`get_user`、`set_user_active`、`reset_user_password`。
- 会话操作：创建/查询/触碰/撤销会话，按用户撤销全部会话。
- 登录限流操作：读取/递增失败窗口、清理成功登录窗口。
- 授权辅助：按项目读取所有者，按视觉项关联项目读取所有者。
- 审计写入：记录操作者、动作、目标和结果，禁止传入秘密内容。

**Steps:**
- [ ] 为临时 SQLite 增加迁移测试：旧 projects 表升级后字段存在，历史项目仍存在且 owner 可回填。
- [ ] 实现事务化 schema 迁移和索引；迁移失败时回滚，不删除已有表或数据。
- [ ] 写 Bootstrap 初始化幂等测试：首个管理员创建并接管 `owner_user_id IS NULL` 项目，重复执行不覆盖账号/项目。
- [ ] 实现用户、会话、限流和审计仓储方法，所有 SQL 使用参数绑定。
- [ ] 写会话过期、撤销、停用用户撤销会话、最后管理员保护和登录失败窗口测试。
- [ ] 写普通用户创建/列表字段脱敏测试，确保不返回 `password_hash`、会话令牌或敏感元数据。
- [ ] 运行 `PYTHONPATH=src python -m unittest tests.test_repository tests.test_auth -v`。

**Verification:** 临时数据库单测全通过，真实 `data/creative_studio.db` 未被读取或写入。

### Task 3: 实现认证服务和一次性管理员 CLI

**Files:**
- Modify: `src/creative_studio/auth.py`
- Create: `src/creative_studio/auth_cli.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- `AuthService(repository, cookie_secure: bool = False)`：编排登录、会话、CSRF、密码修改、管理员操作和审计。
- `login(username, password, client_ip, user_agent) -> AuthResult`：成功返回用户、原始会话令牌和 CSRF 令牌；失败统一错误并执行限流。
- `authenticate_session(session_token, csrf_token) -> SessionContext | None`。
- `init_admin(username, password) -> User`：仅用户表为空时成功；同一事务迁移旧项目。
- CLI `init-admin --username ... --password-stdin`；支持安全隐藏输入/标准输入，不回显密码。
- 启动时仅在 users 为空且两个 Bootstrap 环境变量均存在时尝试初始化；环境变量不写入日志。

**Steps:**
- [ ] 写认证服务失败测试：未知账号统一报错、停用账号不能登录、锁定返回限流、成功登录创建会话。
- [ ] 写 CSRF/session 过期和撤销测试；验证触碰只更新允许字段。
- [ ] 实现 AuthService，确保密码重置/停用立即撤销用户会话，强制改密标记正确。
- [ ] 写 CLI 参数和密码读取测试；缺少参数、弱密码、已初始化和非法用户名均返回非零状态。
- [ ] 实现 `auth_cli.py`，默认数据库路径与项目一致，并允许测试传入临时路径。
- [ ] 运行定向认证测试，确认没有密码/令牌出现在异常和 stdout/stderr 中。

**Verification:** `PYTHONPATH=src python -m unittest tests.test_auth -v`

### Task 4: 接入 HTTP 鉴权、CSRF 和资源授权

**Files:**
- Modify: `src/creative_studio/app.py`
- Create/Modify: `tests/test_auth_http.py`

**Interfaces:**
- 在 `StudioHandler` 中增加统一 `require_authenticated()`、`require_admin()`、`require_project_access(project_id)` 和关联资源授权检查。
- 新增 `/api/auth/status`、`/login`、`/me`、`/logout`、`/password` 及 `/api/admin/users*` 路由。
- 业务 API 统一返回 `401/403/409/429` 与现有成功/失败 JSON 包络。
- 设置/清除 `studio_session` HttpOnly Cookie 和 `studio_csrf` Cookie；`CREATIVE_STUDIO_COOKIE_SECURE=1` 时加 `Secure`。
- `/api/health` 保持最小公开健康响应；`/api/tag-options` 和所有项目/历史/文件/图片接口要求登录。

**Steps:**
- [ ] 先写 HTTP 测试：未登录业务 API 返回 401，管理员接口普通用户返回 403，未知资源不泄露细节。
- [ ] 写项目所有者和视觉项/图片 IDOR 测试，覆盖 GET、PUT、DELETE、POST、文件上传、图片状态/读取/重试。
- [ ] 写登录/退出 Cookie、CSRF 缺失/伪造、会话过期和停用即时失效测试。
- [ ] 实现统一认证入口，避免在每个路由重复解析 Cookie 或 SQL；保留原有业务方法调用顺序。
- [ ] 将项目创建写入当前用户 owner；所有现有项目操作在授权通过后才进入 repository。
- [ ] 处理 `must_change_password`：除认证和改密接口外拒绝业务请求，并返回可操作的 403 错误。
- [ ] 运行 HTTP 定向测试，再运行现有全量 Python 单测。

**Verification:** `PYTHONPATH=src python -m unittest tests.test_auth_http -v` 和全量单测。

### Task 5: 增加登录页、会话状态和管理员账号管理 UI

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`

**Interfaces:**
- 登录表单、强制改密表单、当前用户/退出入口、管理员账号管理对话框。
- 统一 `api()`：对写请求自动注入 CSRF Header；401 停止轮询并回登录，403 显示无权限。
- 登录成功后才调用标签、项目和历史初始化；管理员用户列表只显示安全字段。

**Steps:**
- [ ] 先补前端静态结构和最小状态测试/手工检查，保证未登录 DOM 不展示项目数据。
- [ ] 修改 `api()`、`init()` 和状态清理流程，避免未登录时提前请求业务 API。
- [ ] 实现登录、退出、强制改密和会话过期回登录；禁止重复提交并显示进行中/失败状态。
- [ ] 实现管理员创建、停用/启用、重置密码一次性展示和最后管理员保护提示。
- [ ] 复用现有视觉变量和响应式断点，验证 `1280x720`、`390x844` 无横向溢出、键盘可操作和对话框焦点。
- [ ] 运行 `node --check static/app.js`，并用本地服务做登录/越权/管理员流程冒烟。

**Verification:** `node --check static/app.js`；浏览器控制台无 error/warn，未登录不发业务请求。

### Task 6: 启动器、文档、运维和回归收尾

**Files:**
- Modify: `launcher.py`（仅增加初始化提示/命令调用所需的非秘密状态，不显示密码）
- Modify: `README.md`
- Modify: `docs/operations.md`
- Modify: `CHANGELOG.md`
- Modify: `progress.md`
- Modify: `.scratch/auth-permissions/spec.md`

**Steps:**
- [ ] 为运维文档补充备份后迁移、CLI 初始化、环境变量一次性使用、停用/重置和会话故障处理。
- [ ] 在 README 明确登录边界、管理员初始化、当前仍只监听回环地址和公网发布前置条件。
- [ ] 记录用户可见变化、验证结果和未验证的真实 AI/公网 HTTPS 项；不写任何账号密码。
- [ ] 运行全套确定性检查：
  `PYTHONPATH=src python -m unittest discover -s tests -v`
  `node --check static/app.js`
  `python -m compileall -q src chat2api launcher.py`
  `git diff --check`
- [ ] 备份策略只做文档说明和临时数据库演练，不触碰真实运行数据。
- [ ] 检查 Git diff，确认没有 `.env`、令牌、Cookie、数据库、图片或真实上传进入提交。

**Verification:** 全套命令通过；浏览器桌面/移动端静态冒烟通过；真实 AI 请求、公网 HTTPS 和外部限流标记为未验证。

### Task 7: 变更复核和可回滚交付

**Files:**
- Review only: all files changed by Tasks 1-6

**Steps:**
- [ ] 对照设计文档逐条复核角色、项目所有权、IDOR、CSRF、会话撤销、限流和日志脱敏。
- [ ] 检查数据库迁移在空库、旧库、重复启动、无 Bootstrap 环境变量四种状态下的行为。
- [ ] 记录当前 commit、测试输出和未验证项；确认主分支/当前工作树未被重置或覆盖。
- [ ] 准备回滚说明：停止服务、保留现有数据库副本、切回认证前提交、按备份恢复数据，不直接覆盖运行库。
- [ ] 提交一个只包含本变更的实现提交，提交信息说明认证和项目隔离的业务影响。

**Verification:** 代码审查清单无未解释项；回滚步骤可在不删除用户数据的前提下执行。

---

## 执行方式

计划已写入 `docs/superpowers/plans/2026-09-01-auth-permissions.md`。下一步可选：

1. 使用 `superpowers:subagent-driven-development`，逐任务执行并在任务间做两阶段复核；
2. 使用 `superpowers:executing-plans`，在当前会话按任务批次执行并设置检查点。
