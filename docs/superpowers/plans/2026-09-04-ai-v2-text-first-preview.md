# AI v2 文字优先纯前端预览实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个可双击运行的独立页面，用假数据验证叙事文字、静态按需生图和轮播逐张生图的产品流程。

**Architecture:** 所有 HTML、CSS、假数据、纯 reducer 和 DOM 渲染均封装在一个文件中。状态只存在于当前浏览器内存；页面不加载生产资源、不调用网络、不读写数据库，并以入口级隔离示意明确旧 AI 与新 AI 不存在调用关系。

**Tech Stack:** 原生 HTML、CSS、JavaScript；无框架、无依赖、无服务器、无持久化。

**Spec:** `docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`

## Global Constraints

- 只新增 `.scratch/ai-v2-text-first-preview/index.html`，不修改正式 `static/`、`src/`、数据库、Prompt 或配置。
- 页面不得发起 `fetch`、XHR、WebSocket、表单提交或远程资源请求。
- 新 AI 对旧 AI 保持零引用、零回退、零双写/双读和零兼容串联。
- 展示类仍是唯一顶层类型；静态/轮播通过展示类内部模式切换。
- 叙事固定 5 套，每套 1 个故事、2 个钩子、每钩子 3 个画面描述。
- 静态固定 3 套，每套图片状态为 `pending/generating/success/failed`；成功后不可重新生成，失败可重试。
- 轮播固定 3 套，每次只生成下一张；第 N 张仅在第 N-1 张成功后可执行；成功帧不可重新生成。
- 原型不验证 Prompt 质量、真实 AI、图片质量、API、数据库或生产迁移。

---

### Task 1: 固化批准状态与隔离边界

**Files:**
- Modify: `docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`

**Interfaces:**
- Consumes: 用户批准的精简结构和“旧 AI 冻结、新 AI 隔离”要求。
- Produces: 预览及后续正式方案共同遵守的硬不变量。

- [x] **Step 1: 将状态改为已批准用于预览**

明确当前授权只覆盖独立纯前端预览。

- [x] **Step 2: 写入六条隔离硬不变量**

记录零引用、零回退、零双写/双读、零兼容串联、中立基础设施例外和入口级单向切换。

- [x] **Step 3: 收紧预览边界**

要求 HTML 不加载生产或远程资源，运行期间不产生业务网络请求。

### Task 2: 构建自包含流程预览

**Files:**
- Create: `.scratch/ai-v2-text-first-preview/index.html`

**Interfaces:**
- Consumes: 三类固定假数据和 `dispatch(action)` 领域动作。
- Produces: `createInitialState(): PreviewState`、`reduce(state, action): PreviewState`、`deriveFrameAvailability(item): FrameAvailability[]`、`render(state): void`。

- [x] **Step 1: 写入页面骨架和视觉变量**

建立与正式页面一致的深绿页头、浅灰背景、紧凑白色面板、模式分段控件和响应式结果区域，并显示“一次性前端预览 / 无真实 AI 请求”。

- [x] **Step 2: 写入固定假数据**

提供 5 套叙事、3 套静态和 3 套轮播文字方案；所有展示值均作为文本渲染，不包含内部 `execution` 数据。

- [x] **Step 3: 实现纯状态机**

支持 `SELECT_MODE`、`START_IMAGE`、`COMPLETE_IMAGE`、`FAIL_IMAGE`、`RESET_PREVIEW`。非法动作必须返回原状态并产生可见原因；成功图保持锁定，轮播只允许最早未成功帧执行。

- [x] **Step 4: 实现薄 DOM 渲染层**

叙事只呈现文字；静态和轮播根据派生状态显示唯一合法按钮。提供“下次模拟成功/失败”控制，以便人工验证失败重试但不把它误解为产品输入。

- [x] **Step 5: 加入状态检查视图**

显示当前模式、各图片状态、最后一次状态变化和隔离边界；同时提供静态成功锁定、轮播顺序生成、轮播失败重试三个引导场景。

### Task 3: 浏览器人工验收

**Files:**
- Verify: `.scratch/ai-v2-text-first-preview/index.html`

**Interfaces:**
- Consumes: 双击可运行的本地 HTML。
- Produces: 桌面和移动视觉证据、状态机行为记录、零网络请求结论。

- [x] **Step 1: 执行静态隔离检查**

运行：

```powershell
rg -n "fetch\\(|XMLHttpRequest|WebSocket|<script[^>]+src=|<link[^>]+href=|<img[^>]+src=" .scratch/ai-v2-text-first-preview/index.html
```

预期：无匹配。

- [ ] **Step 2: 在 `1280x720` 验证桌面流程**

依次检查三类结果数量；静态成功后按钮锁定；静态失败后按钮变为重试；轮播后续帧在上一帧成功前禁用。

- [ ] **Step 3: 在 `390x844` 验证移动流程**

检查页面无横向滚动、文字不重叠、按钮文案不溢出且状态变化不造成卡片宽度跳动。

- [ ] **Step 4: 检查运行证据**

控制台错误数为零；业务网络请求数为零；本地 HTML 不引用生产文件。

- [x] **Step 5: 检查变更范围**

运行：

```powershell
git diff --check
git status --short --branch
```

确认未修改正式页面、后端、数据库、Prompt 或 `launcher.py`。

### Task 4: 记录结果

**Files:**
- Modify: `progress.md`
- Modify: `docs/superpowers/plans/2026-09-04-ai-v2-text-first-preview.md`

**Interfaces:**
- Consumes: Task 3 的真实验证结果。
- Produces: 可审计的预览范围、验证结论和未验证项。

- [x] **Step 1: 勾选已经完成的实施与验证步骤**

只勾选实际执行且符合预期的项目，失败项保留未勾选并写明原因。

- [x] **Step 2: 追加进度记录**

记录预览文件、三种流程、隔离约束、桌面/移动检查结果，并明确“未调用真实 AI、图片、API 或数据库”。

- [x] **Step 3: 保持正式功能不变**

不更新 `CHANGELOG.md`，因为本任务没有改变正式用户可见行为。
