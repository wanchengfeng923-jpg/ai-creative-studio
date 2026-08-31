# AI 创意工作台 UI 组件与产品参考调研

- 研究日期：2026-08-31
- 研究问题：当前原生单页 UI 应参考哪些成熟产品与组件；是否值得迁移到 React + TypeScript + Tailwind CSS + shadcn/ui
- 资料原则：产品行为以官方帮助文档为准，组件能力与许可以官方文档或官方 GitHub 仓库为准

## 结论

下一版不应继续做传统后台 dashboard，也不应把项目、全部标签、生成按钮和三张结果卡同时常驻首屏。更合适的模型是：

> **Midjourney Create Feed 的生成时间流 + Lightroom 的选片网格 + Linear 的紧凑导航 + Firefly 的按需高级参数。**

技术上建议保留现有 Python API 和 SQLite，只把前端逐步迁移为 **Vite + React + TypeScript + Tailwind CSS + shadcn/ui**。不要先引入 Next.js，不要重写后端，不要一次复制完整模板。先用假数据建立新前端，再逐条接现有只读/写入 API。

## 产品参考

| 参考 | 已验证的官方行为 | 适合借鉴 | 不应照搬 |
| --- | --- | --- | --- |
| Midjourney Web | Create 页以生成 Feed 为中心，图片生成过程中和完成后都留在时间流；悬停图片显示快捷操作；Organize 页支持搜索、筛选、排序、文件夹和批量操作（[Creating on Web](https://docs.midjourney.com/hc/en-us/articles/33390732264589-Creating-on-Web)、[Website Overview](https://docs.midjourney.com/hc/en-us/articles/33329460426765-Website-Overview)） | 生成结果成为主内容；新批次按时间追加；卡片悬浮操作；项目文件夹 | Midjourney 的自由 prompt 模型不适合直接替代本项目结构化定位输入 |
| Runway | 生成内容在右侧面板按时间组织；Tools 提供精确参数，Apps 用于简化特定任务（[Navigating Runway](https://help.runwayml.com/hc/en-us/articles/24298206897043-Navigating-Runway)、[Getting Started with Generative Video](https://help.runwayml.com/hc/en-us/articles/37425232841875-Getting-Started-with-Generative-Video)） | 会话式历史；基础模式和高级模式分层；生成状态紧贴结果 | 不引入模型市场、节点工作流或多供应商概念 |
| Adobe Firefly | 新版工作区将生成、编辑、项目资产和历史放在同一界面；Boards 在底部使用生成栏，高级参数在右侧面板展开（[Generate and edit content](https://helpx.adobe.com/firefly/web/unified-generation-and-editing-experience/generate-and-edit-content.html)、[Partner models in Boards](https://helpx.adobe.com/firefly/web/create-mood-boards/firefly-boards/use-non-adobe-models-to-generate-images.html)） | 底部固定生成栏；高级配置 Sheet；参考文件靠近输入；生成历史不离开工作区 | 不做无限画布、3D 场景和第三方模型选择 |
| Adobe Lightroom | 支持无边框 Photo Grid、带状态的 Square Grid 和单图 Detail；网格中可以直接 Pick/Reject、评分；左侧按相册组织，支持搜索和过滤（[Organize photos](https://helpx.adobe.com/ca/lightroom-cc/using/organize-photos.html)） | 方案网格减少卡片边框；采用/排除动作靠近图片；Grid/Compare/Detail 三种视图 | 不需要完整照片元数据、编辑工具和复杂评分系统 |
| Linear | 侧栏收藏、Command Menu、快捷搜索、列表/看板切换和按需详情侧栏都是核心交互（[Favorites](https://linear.app/docs/favorites)、[Search](https://linear.app/docs/search)、[Project overview](https://linear.app/docs/project-overview)） | 紧凑项目导航；`Cmd/Ctrl+K` 搜项目和动作；详情侧栏按需开关 | 不复制 issue 管理语义和过度键盘化 |
| InvokeAI | 本地 React Web UI 提供 Unified Canvas、Board/Gallery 管理和图片元数据召回；官方仓库为 Apache-2.0（[官方文档](https://invoke-ai.github.io/InvokeAI/)、[GitHub](https://github.com/invoke-ai/InvokeAI)） | 本地优先创意工具的整体密度；Gallery 与生成参数关联；任务状态 | 产品范围远大于本项目，不复制其工作流节点或完整 Canvas |

## 推荐页面模型

### 1. 左侧：项目与会话

- 56–64px 主导航 rail，仅保留项目、生成历史、已采用。
- 展开后显示项目搜索、最近项目和项目状态；不把每个项目永远占据 240px。
- `Cmd/Ctrl+K` Command Menu 搜索项目、跳转批次和执行“新建项目”。

### 2. 中间：生成 Feed

- 当前项目的创意简报摘要位于顶部，但只显示 3–5 个关键字段。
- 每次生成形成一个批次组：时间、定位摘要、3 套方案、任务状态。
- 展示类以大图网格为主，文字说明在选中后展开；叙事类使用可扫描的标题/钩子列表。
- 支持 `网格 / 对比 / 详情` 三种视图，而不是三张重文本卡片固定并排。

### 3. 底部：固定生成栏

- 默认只显示创意目标摘要、类型、画幅、参考文件和生成按钮。
- “调整定位”打开右侧 Sheet；标签不在首页全量铺开。
- 生成期间按钮变为进度与停止条件提示；新结果追加到 Feed，不跳转页面。

### 4. 右侧：按需配置 Sheet

- 使用分组 Combobox + chips 处理主选/辅助标签。
- 产品卖点选择后再显示已过滤的展示内容。
- 风格三级级联分成三个清晰步骤，但不使用原生 `select multiple`。
- Sheet 关闭后配置摘要保留在底部生成栏，用户能知道当前输入是什么。

## 组件选型

### 核心：shadcn/ui

shadcn/ui 已有 Sidebar、Command、Data Table、Drawer、Sheet、Resizable、Scroll Area、Tabs、Attachment 等组件清单（[Components](https://ui.shadcn.com/docs/components)），并提供可复制的 dashboard/sidebar blocks（[Blocks](https://ui.shadcn.com/blocks)、[Sidebar Blocks](https://ui.shadcn.com/blocks/sidebar)）。

本项目直接需要：

- `Sidebar`：可折叠项目导航。
- `Command`：项目与动作搜索；官方定义就是用于搜索和快速动作的 Command Menu（[Command](https://ui.shadcn.com/docs/components/base/command)）。
- `Combobox`：官方支持 multiple + chips，适合替换当前难用的多选框（[Combobox](https://ui.shadcn.com/docs/components/base/combobox)）。
- `Sheet`：右侧创意配置；它被定义为补充主屏内容的侧面面板（[Sheet](https://ui.shadcn.com/docs/components/aria/sheet)）。
- `Resizable`：桌面端可选的结果/详情分栏，并带键盘支持（[Resizable](https://ui.shadcn.com/docs/components/base/resizable)）。
- `Attachment`：参考文件缩略图、元数据、上传状态和错误状态（[Attachment](https://ui.shadcn.com/docs/components/base/attachment)）。
- `Scroll Area`、`Tabs`、`Dialog`、`Tooltip`、`Skeleton`、`Progress`：结果浏览和任务状态。

推荐等级：**A，作为唯一底座。**

### 补充：Origin UI

Origin UI 是 React + Tailwind 的 copy/paste 组件集，遵循 shadcn 约定，支持 Tailwind v4，官方仓库为 MIT（[GitHub](https://github.com/shadcn/originui)）。适合从中挑选更精致的输入组、空状态、选择器和提示组件。

推荐等级：**B，只逐个取组件，不混入第二套 Design System。**

### 可访问性补强：React Aria Components

React Aria 提供无样式、可自定义且覆盖键盘/屏幕阅读器行为的组件；官方仓库为 Apache-2.0（[GitHub](https://github.com/adobe/react-spectrum)）。当 shadcn/Origin 的复杂 TagGroup、拖放或组合框行为不足时才下沉使用。

推荐等级：**B，解决复杂交互，不承担视觉主题。**

### 不作为骨架

- **Magic UI**：MIT、适合少量 Blur Fade 或渐入反馈，但大部分是营销和视觉特效（[GitHub](https://github.com/magicuidesign/magicui)、[Components](https://magicui.design/docs/components)）。最多使用一个轻动效。
- **Cult UI**：MIT、shadcn 兼容，但定位是 motion-rich niche components（[官方文档](https://www.cult-ui.com/docs)、[GitHub](https://github.com/nolly-studio/cult-ui)）。不用于表单和导航骨架。
- **Aceternity UI**：免费组件与付费 blocks/templates 混合，主要面向营销页和视觉展示（[Explore](https://ui.aceternity.com/explore)）。不复制付费模板，不引入作为依赖。
- **Tremor**：Apache-2.0，强项是图表和数据 dashboard（[GitHub](https://github.com/tremorlabs/tremor)）；当前创意工作台不需要 BI 图表，不推荐引入。
- **TanStack Table**：适合大量结构化行的过滤、排序、选择（[官方文档](https://tanstack.com/table/latest)）；当前项目和批次数量有限，先不用，未来多人任务/审计列表再评估。

## 是否迁移 React

建议迁移，但必须把它定义成**前端替换**而不是全栈重写：

1. 新建独立 `frontend/`，使用 Vite + React + TypeScript；开发时请求现有 Python API。
2. 第一阶段只做假数据 UI 和交互状态，不改 `repository.py`、数据库和 AI 调用。
3. 固定现有 API 合同后，按“项目列表 → 项目详情 → 标签配置 → 历史 → 生成/采用 → 图片轮询”的顺序接入。
4. 构建产物由 Python 静态服务托管；保留现有原生页面直到 React 版通过验收。
5. 不引入 Next.js、服务端渲染、账号系统或新的数据库。

迁移的主要收益不是“更潮”，而是当前页面已有动态标签级联、图片任务轮询、历史批次、采用状态和多模式分支，继续在单个约 29KB 的 `static/app.js` 中增加 UI 状态会越来越难验证。React + TypeScript 能把 ProjectNav、GenerationFeed、CreativeComposer、SettingsSheet、ResultGrid 和 CompareView 分成可独立验证的模块。

## 下一版原型验收

- 首屏主角必须是当前项目的生成 Feed，而不是配置表单。
- 不展开设置时，用户仍能看懂当前目标、类型、画幅和已选定位。
- 从任意批次进入 Compare View 不超过一次点击。
- 标签选择必须支持搜索、chips、主选/辅助项上限和键盘操作。
- 展示类新批次固定出现 3 套方案，单图任务状态就地显示。
- 叙事类沿用同一外壳，但使用列表/大纲结果，不受展示类图片布局约束。
- 1280px 宽度下不同时常驻“展开项目栏 + 完整配置栏 + 三列结果卡”。
