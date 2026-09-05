# 旧 AI 实现退役设计

## 目标

删除 `creative_studio.ai_v2` 之外的旧 AI 可执行实现、Prompt、评测资产和对应测试，使正式应用只保留 AI v2 业务链路。认证、项目、项目文件、备份和 `chat2api` 继续作为中立基础设施存在。

## 非目标

- 不删除、迁移或覆盖现有 SQLite 数据库中的旧表和旧记录。
- 不删除真实图片、上传文件、`.env` 或其他运行数据。
- 不改变 AI v2 的输入、会话、重试、公开 DTO、Prompt lifecycle 或 live opt-in 行为。
- 不删除历史 ADR、handoff、实施计划、研究文档或 progress 时间线中的旧 AI 记录。
- 不启用真实 AI，不部署，不推送或合并分支。

## 当前问题

旧 AI 已无正式 HTTP 入口，但仍有两个运行时残留：

1. `app.py` 通过旧 `PublicResultMapper` 输出项目 DTO。
2. `StudioRepository` 初始化并迁移旧 `generations`、`visual_items`、`display_frames`、`adoptions`、`carousel_operations` 表，同时保留整套旧生成、图片、轮播和采用方法。

因此，仅删除表面上的旧模块会破坏项目 API，且新数据库仍会继续携带已经退役的数据结构。

## 设计

### 中立项目投影

新增 `project_projection.py`，提供 `ProjectProjection.project()` 和 `ProjectProjection.summary()`。它从空对象按白名单构造项目详情与列表 DTO，继续过滤项目文件的内部 `stored_name` 和 `safe_summary`。

项目详情中的采用状态不再读取旧 `adoptions`。正式前端已通过 `/api/v2/projects/{id}/adoption` 读取 AI v2 采用状态，因此项目 DTO 保留 `adoption: null` 作为加载前的稳定初值；项目列表保留空的 `adopted_kind` 与 `adopted_title`，避免无关 UI 结构变化。

### 中立仓储

`StudioRepository` 只负责：

- 用户、会话、登录失败窗口和审计日志；
- 项目 CRUD、所有权和标签；
- 项目文件 metadata 与上传记录。

新建数据库只创建上述中立表和索引。初始化已有数据库时，只补齐中立表/列；对已存在的旧 AI 表不执行 `DROP`、`DELETE`、`ALTER` 或内容读取。旧生成、视觉、轮播、采用和旧 reference-asset adapter 方法全部删除。

`backup.py` 保留对 `visual_items` 和 `display_frames` 的只读完整性检查。这是已有数据库的备份兼容能力，不是旧 AI 生产运行时。

### 删除范围

删除根包下旧 AI builder、provider、prompt、contract、model port、generation、image、carousel、projection、evaluation、observability 和 governance 模块。删除 `config/ai_*.txt/json` 旧 Prompt、`config/prompts/`、`config/evals/` 的 v1 资产与旧报告；完整保留 `config/ai_v2/` 与 `config/evals/ai_v2/`。

删除只验证旧实现的测试。保留并调整仓储、标签配置、AI v2 boundary/gateway 测试，新增退役守卫验证：旧模块/配置路径不存在，新 `StudioRepository` 不创建旧 AI 表，已有旧表和记录在初始化后保持不变。

## 数据与安全不变量

- 所有测试只使用临时目录和临时 SQLite。
- 不连接真实网关，不读取或修改 `chat2api/.env`。
- Git 暂存区不得包含 `.env`、`data/`、数据库、图片或上传文件。
- 旧表只是不再创建和使用，绝不从现有数据库中删除。
- 历史文档允许继续提及旧模块和旧表，作为审计证据。

## 验收

1. 全量测试和 AI v2 定向测试通过。
2. 新建 `StudioRepository` 数据库不含五类旧 AI 表。
3. 含旧表和哨兵记录的数据库初始化后，旧表与记录仍存在且内容不变。
4. 项目列表、详情、创建、更新、文件上传和认证行为保持可用。
5. 旧 AI Python 模块、Prompt、v1 评测资产和对应测试不再存在。
6. AI v2 release gate、Node 语法、Python compileall、boundary 和 `git diff --check` 通过。
7. 三份 AI v2 Prompt 仍为 `candidate` 且 `caller=null`。

## 回滚

通过回滚本次清理提交恢复旧代码和旧配置。由于本次不删除或迁移真实数据库内容，回滚无需数据库恢复；已有旧表在清理期间始终保留。若验证发现中立项目/认证能力退化、旧表被修改、AI v2 引用旧模块或运行数据进入 Git，停止提交并修正。
