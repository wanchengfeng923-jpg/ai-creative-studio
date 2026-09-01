# 当前项目进度（2026-09-01）

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

## 2026-08-31 工程技能仓库配置

### 已完成

- 按 `setup-matt-pocock-skills` 设置本仓库工程技能约定。
- Issue tracker 采用 `.scratch/<feature-slug>/` 下的本地 Markdown。
- Triage 使用 `needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix` 五个默认标签。
- 领域文档采用根目录 `CONTEXT.md` 和 `docs/adr/` 的单上下文布局；文档按需延迟创建。
- `AGENTS.md` 已增加 `Agent skills` 导航，详细约定位于 `docs/agents/`。

### 验证

- 已检查新增文档路径、相互引用和 Markdown 差异。
- 本次仅修改工程协作文档，未修改业务代码。

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
- 将原页面中部的“当前项目”入口重做为品牌右侧的“项目列表”按钮；当前项目名称继续独立显示并可直接编辑。
- 移动端顶部栏收敛为品牌图标、项目列表图标、项目名和保存状态，避免两行顶部栏占用内容空间。
- 在 `AGENTS.md` 固化顶部导航的短操作路径约定，并新增 `.scratch/header-brand-project-menu/spec.md` 变更卡。

### 验证

- `1280x720` 下项目列表按钮位于品牌右侧（约 `x=198px`），点击可打开项目抽屉；页面无横向溢出。
- `390x844` 下项目列表按钮约位于 `x=68px`，抽屉可正常打开；页面宽度与视口一致，无横向溢出。
- 未调用真实 AI、未修改数据库结构、AI 网关或生成链路。
