# Phase 3 静态展示类分层迁移变更卡

## 目标

- 变更名称：静态展示类 canonical contract 与生产入口迁移
- 谁使用：展示类创意生成、方案评审和首图异步任务
- 要解决的问题：当前静态生产结果使用首帧字段伪造 `subtitle`、`core_subject`、`layout` 等旧字段，prompt、validator、持久化和公开 DTO 不是同一套业务契约；静态持久化还复用了会创建 `display_frames` 的视觉通用路径。
- 期望结果：静态展示类使用 `StaticVisualResult.v1`，每批恰好三案、每案一张首图，公开结果直接呈现 canonical 字段，私有图片指令只进入受控图片任务和私有存储列；叙事 v6 和轮播路径不变。

## 范围

- 本次要做：
  - 新增 `StaticVisualGeneration`、`StaticVisualPromptInput`、`StaticVisualResult.v1` 和确定性 validator/repair。
  - 将 `config/ai_visual_static_creative_prompt_v1.txt` 与 registry contract 对齐，并在全部门禁通过后切换为唯一静态 production prompt。
  - 新增静态专用 repository 完成入口和 canonical persistence mapper；新静态结果不写旧 alias，不创建 `display_frames`。
  - 新增静态公开 DTO 白名单投影，history/status/adopt 继续复用 `PublicResultMapper`。
  - 为静态首图提供轻量 typed request seam，复用现有 `ImageJobRunner` 状态机。
  - 增加 deterministic composition-root、结构校验、隐私、持久化、图片状态和至少 10 个脱敏评估样例测试。
  - 更新 `progress.md`、项目代码地图、运维手册和 Phase 4 交接文档，记录真实提交与未验证项。
- 本次明确不做：
  - 不修改 `creative.visual.carousel.plan@visual-carousel-v1`、轮播 prompt、轮播 validator、继续生成、逐帧状态机或轮播前端行为。
  - 不修改叙事 v6、`NarrativeGeneration` 或叙事 UI 语义。
  - 不执行真实 AI、图片网关、浏览器、真实数据库迁移或历史 scrub。
  - 不修改 `launcher.py`、监听地址、权限、部署、代理和 `chat2api/.env`。
  - 不恢复独立首帧/后续文字 prompt，不新增动态轮播字段。
- 是否改变数据库、API、提示词、模型、端口或权限：改变静态 prompt、内部 contract 和静态公开字段；复用现有表和 HTTP 包络，不增加必须迁移的表，不改变端口、权限或外部 URL。

## 当前事实冲突

- Phase 3 交接文档的基线 HEAD 是 `b4110ea`，当前 HEAD 是其后的 docs-only 提交 `c4e3624`；差异仅为静态 Phase 3 交接文档加深，不改变实现基线。
- 交接文档和运维手册描述默认回环监听，但工作树保留用户对 `launcher.py` 的未暂存 `WEB_BIND_HOST = "0.0.0.0"` 修改。本变更不触碰该文件，也不把它纳入提交。
- 当前静态生产 caller 仍是 `CreativeGenerationService._generate_with_model_client()` 的旧视觉分支，registry 使用 `visual-v2.3`；`static-v1` 仍是 candidate。切换前必须由 composition-root fake harness 证明新 Module 已接线。

## 设计决策

1. 静态结果使用独立 `StaticVisualResult.v1`；不再把 `first_frame` 或 `carousel` 字段转换成静态别名。
2. 静态持久化使用独立 `complete_static_generation()`，保留现有 `complete_visual_generation()` 供轮播/兼容路径使用，降低轮播回归风险。
3. `generations.items_json` 和 `visual_items.content_json` 只保存 canonical 静态正文；`image_generation_instruction` 只写入 `visual_items.image_prompt` 和受控图片请求，静态方案不创建 `display_frames`。
4. 静态公开投影增加明确 DTO 分支；旧历史只允许读取兼容，canonical 新写入不携带 `subtitle`、`core_subject`、`layout`、`visual_style` 等伪造字段。
5. 图片 worker 和幂等/恢复状态机保持原实现；只增加静态 typed request 到现有 item 队列的转换和测试。
6. registry lifecycle 最后切换；若 contract、隐私或轮播隔离任一门禁失败，保持 candidate 并回滚静态 caller，不修改运行数据。

## 验收

- 给定输入：完整或空白展示类标签、产品摘要、参考文件名、`16:9`/`9:16` 画幅和含特殊模板字符/URL/换行的任务描述。
- 应出现的页面或接口结果：静态历史和状态返回三套 canonical 方案、每案一个首图状态；旧历史仍可读取；图片成功时 URL 由应用生成。
- 数量/字段/状态要求：根对象只含 `items` 且恰好三案，concept id 为 A/B/C；每案字段集合精确匹配；图片状态与文字状态分离；新静态行没有 `display_frames`。
- AI 输出质量检查：confirmed 事实可追溯；evidence、asset plan、risk、review 非空；三案 visual mechanism 有可观察差异；评估集至少 10 个 case，硬约束与隐私门禁 100% 通过。
- 失败时应看到的提示：格式失败最多一次 repair，最终记录 `model_output_invalid`、阶段、字段路径、attempt 和 trace id；首图单项失败不影响其他方案，失败项可人工 retry。

## 风险和回滚

- 可能影响的数据或用户：新静态生成的公开字段和结果卡片；旧历史保留兼容读取。不会修改真实运行数据库或图片目录。
- 是否需要备份：本次 deterministic 测试只使用临时 SQLite；不对真实库执行写操作，因此不需要生产备份。
- 回滚方式：回滚静态 caller/registry 提交到 `visual-v2.3`；保留新 canonical 行和图片文件，由 canonical mapper 继续读取，不覆盖或删除运行数据。
- 必须暂停的情况：发现公开响应含私有图片指令/游标/路径/job id，静态测试触碰真实 `data/`，或轮播 prompt、validator、`display_frames`/继续生成行为发生变化。

## 实施记录

- 分支：`codex/tag-accordion-prototype`
- 提交：待实施
- 修改文件：待实施
- 做了什么：待实施
- 验证命令和结果：待实施
- 尚未验证：真实 AI、真实图片网关、认证浏览器、真实数据库写入和图片质量。
- 遗留风险：旧静态 alias 读取兼容和 `LegacyCreativeGenerationAdapter` 按 Phase 5 删除条件保留；用户 `launcher.py` 未暂存修改必须持续保留。
