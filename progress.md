# AI 创意工作台进度入口（截至 2026-09-09）

> 本文件是简洁的历史/维护指针，不是当前事实索引，也不替代源码、配置和验证输出。当前版本、registry 可加载性、部署/审批边界以 [`docs/current-state.md`](docs/current-state.md) 为准；历史变更见 Git、`CHANGELOG.md` 和对应的部署/审计文档。

## 当前结论

- 当前正式代码链路为 **AI v2**；旧生成服务、旧 Prompt、旧图片任务和旧生成路由已退役。
- `registry.json` 将三类文字 Prompt 声明为 `production` 并绑定唯一 caller；当前 static/carousel 模板 hash 不一致，registry 初始化和 production/release gate 保持 blocked，不能据此宣称当前运行就绪或真实质量通过。
- 开发机 Git 仓库 `D:\code\ai_creative_studio` 是唯一代码源；服务器只作为发布运行副本，禁止从服务器反向覆盖开发机。
- 生产数据和配置与代码分离：服务器 SQLite、图片、上传文件和生产 `.env` 是生产权威源，发布包不得覆盖这些内容。
- 本机默认入口仍为 `http://127.0.0.1:8775/`，AI 网关为 `127.0.0.1:8780`；历史部署记录中的 `http://42.194.220.18:8775/` 不等同于当前 `master` 已验证的公网状态，HTTPS 仍未配置。

## 版本与发布基准

| 项目 | 当前值 |
|---|---|
| Git 分支 | `master`（跟踪 `origin/master`） |
| 当前工作树 HEAD | `be89f8a5ec7d8103c83ad86bf49dbb95971ff70a` |
| 正式基准 tag | `production-baseline-20260908` |
| 远端仓库 | `wanchengfeng923-jpg/ai-creative-studio`（GitHub 私有仓库） |
| 发布代码清单 | 112 个文件 |
| 原始字节聚合 SHA-256 | `e0261357199ce918f5429a24e9afe2304ecca924554e2c1d8ce5b13ec33cea88` |
| 跨平台规范化 SHA-256 | `b929837a172cb8dfbd7de3eebd62c8c3dab6ff82f933b1bbdbe2918914156e30` |
| 服务器代码 | 与发布包逐文件一致 |

代码基准、清单算法和服务器取证详见 [`docs/deployment/code-baseline-20260908.md`](docs/deployment/code-baseline-20260908.md)。

## 当前功能

- 账号登录、登出、强制改密、管理员账号管理、CSRF 和项目所有权隔离。
- 创意项目新建、搜索、打开、删除、自动保存、历史记录和采用/替换。
- 叙事类：一次生成故事、钩子和画面建议，并保留历史定位。
- 静态展示类：一次生成三套文字方案；每套首图按需提交，支持状态轮询、失败重试和原图预览。
- 轮播展示类：固定 2 至 5 帧或由 AI 决定；三套方案各自维护路线，后续帧按序生成并复用同一图片会话。
- 标签配置按项目类型动态渲染，支持卖点到展示内容过滤、视觉风格级联、选择上限和轮播逐轮定位继承/自定义。
- 文字生成支持进程内 FIFO 队列，最多同时运行 6 个会话；排队状态对前端可见但不泄露 Prompt、会话游标或供应商任务 ID。
- 图片任务具备幂等键、attempt 隔离、异步状态对账、瞬时失败短重试和进程恢复能力。
- 浏览器公开 DTO 使用白名单投影，不暴露 Prompt、执行字段、会话游标、供应商 job ID、本地路径、完整响应或堆栈。

## 运行与部署现状

### 本机

- 工作台默认：`127.0.0.1:8775`
- AI 网关默认：`127.0.0.1:8780`
- 启动入口：`启动AI创意工作台.bat` / `launcher.py`
- 数据根目录可由 `CREATIVE_STUDIO_DATA_DIR` 指定；默认仍为仓库 `data/`。
- 网关图片和任务状态目录可由 `CHATGPT_IMAGES_DIR`、`CHATGPT_IMAGE_JOB_DIR` 指定。
- 启动器已具备 Windows 单实例保护，不应同时启动多个启动器、网关或网页进程。

### 服务器

- 程序目录：`E:\AI-Creative-Studio`
- 公网网页：`0.0.0.0:8775`，外部 `/api/health` 已验证返回 200。
- AI 网关：`127.0.0.1:8780`，健康检查可返回 200，控制令牌不写入本文档。
- 服务器代码目录已与发布包逐文件核对一致；服务器上的 SQLite、图片、上传文件和 `.env` 不随代码发布包覆盖。
- 公网使用步骤、启动命令、下线命令和常见故障处理见 [`docs/deployment/public-startup-guide.md`](docs/deployment/public-startup-guide.md)。
- 部署过程的备份、恢复、切换和回滚门禁见 [`docs/deployment/live-deployment.md`](docs/deployment/live-deployment.md)。

## 验证证据

历史发布基准的验证记录（对应 `production-baseline-20260908`，不代表当前工作树）：

- 全量 unittest：`200` 项通过。
- AI v2 定向测试：`124` 项通过。
- `python -m compileall -q src chat2api`：通过。
- `node --check static\\app.js`、`node --check static\\ai-v2\\app.js`：通过。
- `git diff --check`：通过。
- Prompt registry、schema、公开投影、边界和 production readiness gate：该历史快照记录为通过；当前工作树的 static/carousel hash mismatch 见 [`docs/current-state.md`](docs/current-state.md)，需重新验证。

真实环境验证边界：

- 受控文字 smoke 曾验证叙事、静态、轮播三类入口；后续正式 live smoke 的项目 12 遇到 `provider_unavailable` / HTTP 502，因此不能把文字质量视为生产验收通过。
- 受控真实图片评测完成 1 次静态提交和 2 次轮播续帧提交，未发现公开字段泄露；该结果只证明链路可运行，不代表供应商质量或长期稳定性通过。
- 浏览器桌面流程已检查，`1280x720` 无横向溢出；`390x844` 尚未完成带登录真实流程验收。

## 当前审计状态

- `repo-audit-kit` 已完成 T01-T08；当前审计状态为 `complete_with_limits`。
- 文档/规则整理已建立 `docs/current-state.md` 作为当前事实入口，并保留旧报告、handoff 和部署记录的历史分层。
- 仍登记但未修复：`F-003`、`F-004`、`F-005`、`F-006`；其中 F-006 使默认 registry/production gate 保持阻断。
- 审计队列、发现台账和报告见 [`docs/repo-audit/STATE.md`](docs/repo-audit/STATE.md) 与 [`docs/repo-audit/QUEUE.csv`](docs/repo-audit/QUEUE.csv)。

## 未完成事项

按当前优先级：

1. 确认 static/carousel 的正确 Prompt 模板快照和 registry hash，修复并重新验证 F-006（需独立配置/程序授权）。
2. 补齐三份 Prompt 的最终审批、当前 ref 对应关系，以及 live/真实 AI/图片的受控验证。
3. 按需处理 F-003/F-004/F-005 等程序 deferred 项；本文件不把延期的程序修复写成文档已解决。
4. 完成服务器、备份/恢复、部署回滚和 `390x844` 登录后流程的独立验证。
5. 长期公网使用前补齐 HTTPS、访问限制、外部限流、自动备份和服务化启动。

## 不在当前版本范围

- 不迁移原 ERP 的历史项目、图片或数据库。
- 不恢复旧 AI 生成链路或旧 API 兼容入口。
- 不把 deterministic contract 测试、单次 smoke 或公网 health 结果表述为模型质量通过。
- 不在本文件记录 Token、Cookie、代理密码、数据库内容或完整供应商响应。

## 相关文档

- [`README.md`](README.md)：安装、启动和用户功能。
- [`AGENTS.md`](AGENTS.md)：修改、数据边界和验证规则。
- [`docs/project-rules/项目代码地图.md`](docs/project-rules/项目代码地图.md)：入口、模块和调用链。
- [`docs/project-rules/operations.md`](docs/project-rules/operations.md)：本机运维、备份和恢复。
- [`docs/ai-rebuild-master-plan.md`](docs/ai-rebuild-master-plan.md)：AI v2 设计与门禁。
- [`docs/deployment/code-baseline-20260908.md`](docs/deployment/code-baseline-20260908.md)：代码封板与发布身份。
- [`docs/deployment/live-deployment.md`](docs/deployment/live-deployment.md)：实时部署记录。

## 2026-09-09 规则与入口整理

- 收敛 `AGENTS.md`、`README.md` 和 `docs/current-state.md` 的阅读分流：按任务选择入口，不再要求默认通读完整历史资料。
- 修正本文件的当前 HEAD、registry/hash、审计阶段和公网表述；历史发布验证保留为历史快照，不冒充当前 `master` 通过。
- 本专项已完成“根规则 + 当前事实 + 最短入口 + 进度摘要”以及 `docs/project-rules/` 下的四个资料单元；下一步仅做新会话独立读者接手复核，`docs/ai-rebuild-master-plan.md` 仍不在本轮范围。
## 2026-09-09 部署控制面板

- 新增 `deployment_panel.py`、`deployment_control/` 和 `启动部署控制面板.bat`；面板只管理项目 `7896/8775/8780`，未知进程不会结束。
- 发布清单已同步 `scripts/build_release.ps1`；公网使用手册、运维手册和代码地图已改为面板按钮流程。
- 已完成基础单元测试和面板状态测试；尚未在真实 Windows 防火墙、服务器、公网或真实 AI 链路执行人工验收。

本轮面板共经历 10 个版本（含 `98d0a37` 初始发布页版本）：

1. `98d0a37`：整理独立面板和发布流程页面。
2. `a2d09d1`：上线前强制确认服务已下线。
3. `49eb097`：识别启动器管理的系统 Python 子进程和进程内代理桥。
4. `29198a7`：为 Windows 状态检查增加边界保护。
5. `1231ccb`：修复 Tk 主线程被 WMI 进程枚举阻塞，并隐藏 PowerShell 控制台。
6. `601f64d`：一次刷新复用进程快照，避免每个端口重复扫描。
7. `0e0ce43`：让状态刷新不再锁住整个面板。
8. `8c6ab06`：增加刷新进行中、完成和失败提示。
9. `58cff6d`：允许不同 Python 版本和多级父进程链的项目归属识别。
10. `1b9f39b`：上线结果显示脱敏 PID，不再显示 `Popen` 对象。

最终专项测试为 63 项通过；真实服务器、公网、更新和回滚仍需人工验收。
