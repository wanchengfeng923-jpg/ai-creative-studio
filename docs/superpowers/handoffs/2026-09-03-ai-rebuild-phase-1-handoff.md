# AI 重构 Phase 1 交接文档

## 使用方式

将本文档完整交给一个新的 AI 会话。本文档是用户已经批准的 Phase 1 执行授权；新会话应直接完成 Phase 1 的分析、变更卡、测试先行实现、验证、评审和提交，不要只输出建议或停在计划阶段。只有触发 `AGENTS.md` 的高风险门禁、发现无法保守处理的需求冲突，或连续验证失败且无法定位时，才停止并向用户提问。

Phase 1 完成并提交后，新会话必须生成一份新的 Phase 2 交接文档并把路径交给用户。Phase 1 未通过全部门禁时，继续留在 Phase 1，更新本文档或另写 Phase 1 状态交接，不得生成声称可以进入 Phase 2 的交接。

## 项目和检查点

- 项目：`D:\code\ai_creative_studio`
- 当前工作分支：`codex/tag-accordion-prototype`
- Phase 0 实现提交：`e7412bb8fc9eb43e0cb89df58048ac6363c52239`
- Phase 0 状态：完成，全部门禁通过
- Phase 1 状态：尚未开始
- 唯一实施基线：`docs/ai-rebuild-master-plan.md`

本文档、对应 `progress.md` 记录和 Phase 1 允许范围修正存放在 Phase 0 之后的独立 docs 提交中；用 `git log -1 --oneline` 可取得该提交 hash。接手者不得 amend 该交接提交，也不得把它重复纳入 Phase 1 实现提交；正常接手时工作树预期为干净状态。

交接文档自身会形成 Phase 0 之后的文档提交，因此接手时 `HEAD` 不必等于 Phase 0 提交。必须确认 Phase 0 提交是当前 `HEAD` 的祖先：

```powershell
Set-Location D:\code\ai_creative_studio
git status --short --branch
git branch --show-current
git merge-base --is-ancestor e7412bb8fc9eb43e0cb89df58048ac6363c52239 HEAD
git log -3 --oneline
```

完成标准：当前分支正确，祖先检查退出码为 0，并且接手者已经识别和保留所有既有工作树修改。若工作树不是干净的，先判断变更来源和范围；不得重置、覆盖或删除它们。

## 强制阅读顺序

开始设计或修改前，按顺序完整阅读，不能只读摘要或本交接：

1. `D:\code\ai_creative_studio\AGENTS.md`
2. `D:\code\ai_creative_studio\progress.md`
3. `D:\code\ai_creative_studio\项目代码地图.md`
4. `D:\code\ai_creative_studio\docs\operations.md`
5. `D:\code\ai_creative_studio\docs\ai-rebuild-master-plan.md`
6. `D:\code\ai_creative_studio\CODE_STYLE.md`
7. `D:\code\ai_creative_studio\CONTEXT.md`
8. `D:\code\ai_creative_studio\.scratch\ai-phase-0\spec.md`
9. `D:\code\ai_creative_studio\docs\adr\0001-public-result-projection.md`
10. `D:\code\ai_creative_studio\docs\ai\README.md`
11. 本次实际涉及目录中的测试、ADR、配置和生产调用文件

阅读后用代码搜索重新确认 production/test/dead caller。`progress.md` 是历史时间线，不是当前架构事实；不得把本交接中的文件建议当作代码事实。

完成标准：变更卡中的“当前事实”均能引用当前代码、配置或测试证据，且与总纲 Phase 1 没有冲突。

## Phase 0 已交付边界

Phase 0 已完成以下基础能力，Phase 1 应复用而不是另建平行实现：

- `PublicResultMapper` 对 history、status、adopt、项目采用快照、visual item 和 display frame 做 deny-by-default 公开投影。
- `projection_scrub` 支持只读 dry-run，并只允许在显式非生产副本上带备份 apply。
- prompt compiler 使用 `{{name}}` 单次字面替换，变量集合和模板 hash fail closed。
- JPEG、PNG、WebP 的 bytes、MIME、扩展名和 artifact 元数据保持一致。
- 生成失败记录保留结构化 `error_code`、`phase`、`field_path`、`retryable`、`trace_id` 和内部诊断摘要。
- 轮播非法数量在 reservation 和模型调用之前被拒绝。
- `creative_studio.app` 导入无运行时副作用，`create_application()`/`run()` 是 composition-root seam。
- 叙事游戏资料默认路径指向 `config/ai_creative_game_info_v2.json`。

Phase 0 验证基线为 175 项 `unittest` 通过；JavaScript 语法、Python compileall 和 `git diff --check` 通过。真实数据库只做过只读 dry-run，执行前后 SHA-256 均为 `F7DA1AA20D5FBAC7A3785C0D81096B1096749DE40025874644F37E1AD461DFA8`。真实 AI、图片网关和浏览器未验证。

已知非阻塞缺口：`HttpModelClient.response.json()` 自身抛异常和返回非对象时虽然映射到 `$`，但缺少直接 client 单元测试。Phase 1 修改 model adapter 测试时应补齐，不需要为此改变 Phase 0 行为。

## Phase 1 目标

建立 PromptRegistry、ContractRegistry、显式模型 Port 和生产 composition-root contract harness，使 prompt、输入 schema、输出 contract、validator、公开 DTO、持久化元数据和生产 use case 可追溯地关联。Phase 1 只建立唯一事实和验证骨架，不切换用户可见生产输出。

本阶段必须交付：

1. `config/prompts/registry.json` 以及有明确生命周期的 prompt 目录结构。
2. 叙事、静态展示、轮播各有一个当前 production `PromptSpec`；静态候选和 retired prompt 只登记 inventory/deprecation 元数据，不能把“已盘点”写成“已注册 contract”或“已接入生产”。
3. 代码中显式注册的 input schema、output schema、validator 和 public projector 映射；registry 只能引用允许列表中的稳定 ID，不能从 JSON 动态 import 或执行路径。
4. `PromptRegistry` 启动校验：文件存在、路径留在允许目录、模板变量匹配、内容 hash 匹配、引用的 contract/validator/projector ID 存在、生命周期与 caller 状态一致。
5. 生成记录持久化 prompt ID/version/hash、input/output schema 版本、model、provider、input fingerprint、标签/资料版本和真实 usage source；数据库变化必须是幂等的加法迁移，只在临时 SQLite 中验证。
6. `TextModelPort`、`ImageModelPort` 及 deterministic fake；provider capabilities 必须显式表达 `structured_output_enforced`、`token_limit_enforced`、`conversation_resume`、`multimodal_input` 等真实能力，无法翻译的参数报告 unsupported，不能静默假装生效。
7. 从真实 `StudioApplication` composition root 注入 fake text/image port 的 contract harness，穿过生产 caller、validator、repository 和 `PublicResultMapper`。
8. 对旧 schema、旧 prompt loader、环境变量 prompt path 兼容层、独立首帧/后续帧 retired prompt 补齐或核对 `deprecated_since`、replacement、允许读取场景、禁止新调用和删除条件。

完成标准：上述八项都有代码或测试证据，且没有新增第二套长期事实、动态插件加载或用户可见输出变化。

### 当前 prompt 生命周期矩阵

Phase 1 必须以 `(id, version)` 作为复合唯一键，并按下表盘点当前六个文件。路径可以暂时指向现有 `config/` 文件；`config/prompts/` 是 registry 及后续新版本的根目录。不要为了目录整齐复制同一 prompt 内容或改变当前 prompt 字节。

| ID | version | 当前文件 | Phase 1 记录类型/生命周期 | contract 映射或允许 caller |
| --- | --- | --- | --- | --- |
| `creative.narrative.generate` | `v5` | `config/ai_creative_prompt_v5.txt` | `PromptSpec` / `production` | `NarrativePromptInput.v1` -> `LegacyNarrativeResult.v5` -> `NarrativeResultValidator.v5` -> `NarrativePublicDTO.v1`；当前 narrative caller + harness |
| `creative.visual.static.generate` | `visual-v2.3` | `config/ai_visual_creative_prompt_v2.txt` | `PromptSpec` / `production` | `StaticVisualPromptInput.v1` -> `LegacyStaticVisualResult.v2.3` -> `StaticVisualResultValidator.v2.3` -> `StaticVisualPublicDTO.v1`；当前非轮播 visual caller + harness |
| `creative.visual.carousel.plan` | `visual-carousel-v1` | `config/ai_visual_carousel_prompt_v1.txt` | `PromptSpec` / `production` | `CarouselPromptInput.v1` -> `LegacyCarouselPlanResult.v1` -> `CarouselPlanValidator.v1` -> `CarouselPublicDTO.v1`；当前轮播 visual caller + harness |
| `creative.visual.static.generate` | `static-v1` | `config/ai_visual_static_creative_prompt_v1.txt` | inventory / `candidate` | 只校验文件/hash/目标 Phase 3；Phase 3 才建立 `StaticVisualResult.v1` contract 和 caller |
| `creative.visual.first-frame` | `v1` | `config/ai_visual_first_frame_prompt_v1.txt` | inventory / `retired` | deprecation/audit 测试只读，不允许生成 caller |
| `creative.visual.follow-up` | `v1` | `config/ai_visual_follow_up_prompt_v1.txt` | inventory / `retired` | deprecation/audit 测试只读，不允许生成 caller |

生命周期只允许三个值：

- `production`：一个 use case 同时只能选择一个版本，必须有且只有一个 production caller，并通过 production contract harness；只有这种记录要求完整 PromptSpec contract 映射。
- `candidate`：只做 inventory 文件/hash 校验和目标阶段记录；Phase 3 前不能映射 validator/projector，也不能被 composition root 或 contract harness 当成已实现 contract。
- `retired`：只能被 registry 校验、迁移审计或 deprecated 元数据测试读取，任何文字/图片生成 caller 都必须为零。

现有三个 production prompt 的内容和版本是 Phase 1 的兼容基线。`static-v1` 仅为 Phase 3 候选；两个 retired prompt 不得复活。若代码搜索证明表中 caller 事实已变化，先把证据写入 Phase 1 变更卡并同步修订总纲，再按修订后的单一事实实现，不能静默猜测。

完成标准：六个 `(id, version)` 均可查询，同一复合键不可重复，只有前三条返回完整 PromptSpec，后三条返回 inventory/deprecation 记录，三个生命周期的 caller 规则都有自动测试。

### 固定废弃元数据

Phase 1 对下列兼容项使用这些值；若代码已有更早的 `deprecated_since`，保留更早值，不向后改日期：

| 兼容项 | deprecated_since | replacement | 当前允许场景 | 删除条件 |
| --- | --- | --- | --- | --- |
| `LegacyCreativeGenerationAdapter` | `phase-0` | `CreativeGenerationService` 经 `TextModelPort`，最终由三个 use-case Module 替代 | 仅保留现有无 model client 兼容 caller；禁止新增 caller | Narrative/Static/Carousel Module 均切换且该 adapter 的 production caller 为零后，Phase 5 删除 |
| `schemas.py` 的 `NarrativeRecommendationSchema`、`VisualRecommendationSchema`、`CarouselRecommendationSchema` | `phase-1` | 上表三个 production ContractRegistry validator ID | 现有导入兼容和历史/迁移测试只读；禁止成为新 production validator | 三个生产 contract harness 均通过、所有 production caller 为零且历史 importer 不再依赖后，Phase 5 删除 |
| `load_ai_visual_first_frame_prompt` 和对应 prompt | `phase-1` | `creative.visual.carousel.plan@visual-carousel-v1` 直接提供私有首帧图片指令 | inventory/deprecation/audit 只读；生成 caller 为零 | 轮播 v1 在 Phase 4 完成、`rg` 确认除定义和 deprecation/audit 测试外无调用点后，Phase 5 删除 |
| `load_ai_visual_follow_up_prompt` 和对应 prompt | `phase-1` | Phase 4 `CarouselVisualGeneration` 按锁定路线和上一张实际图片编排图片指令 | inventory/deprecation/audit 只读；生成 caller 为零 | Phase 4 状态机和恢复门禁通过、`rg` 确认除定义和 deprecation/audit 测试外无调用点后，Phase 5 删除 |
| `WEB_ERP_AI_*_PROMPT_PATH`、`*_PROMPT_VERSION` 生产选择器 | `phase-1` | `(PromptSpec.id, PromptSpec.version)` registry 选择 | 只允许精确匹配 production path/version/hash 的现有 launcher 兼容输入；禁止任意新路径 | narrative/static/carousel 分别在 Phase 2/3/4 切换后删除对应选择器，Phase 5 清除残留 |
| `WEB_ERP_AI_PROMPT_TEMPLATE` 生产覆盖 | `phase-1` | 注入的测试 registry/template；生产使用 PromptRegistry | 仅旧 adapter 直接测试兼容；不得进入新 production composition root | 新 production registry harness 通过且旧 adapter caller 为零后，Phase 5 删除 |

每项还必须有 `new_callers_forbidden=true`（或等价的可测试约束）和明确的允许读取场景。`LegacyCreativeGenerationAdapter` 已有 Phase 0 元数据；Phase 1 应核对并把含糊的 removal condition 修正为“legacy adapter production caller 为零”，而不是改变其开始废弃阶段。

完成标准：表中每项都能通过代码元数据、registry inventory 或聚焦测试查询，且 `rg` 结果与声明的 caller 状态一致。

## Phase 1 非目标和硬边界

- 保持正式 UI、HTTP URL、现有 `error` 文本及 422/503/502 状态码不变。
- 保持当前叙事、静态展示和轮播的用户可见结果形状，不在本阶段实现 `NarrativeResult.v1` 或切换高质量静态 prompt。
- 保持批准的轮播 v1：一次共享 planner 文字响应产生每套私有首帧图片指令，后续依据锁定路线和上一张实际图片生成。独立首帧文字会话只可作为未来显式 `GenerationPolicy` 版本。
- 保留 `LegacyCreativeGenerationAdapter`、旧 schema 和 retired loader，直到总纲规定的后续删除条件满足；本阶段的目标是标记和阻断新调用，不是提前清理。
- 所有 model repair、评审或选择阶段必须登记在 `GenerationPolicy`，声明最大调用次数、预算、超时和失败策略。
- 测试只使用临时 SQLite、临时文件、fake model、fake image queue 和固定 clock。
- 本阶段不调用真实 AI、图片网关或浏览器，不打开或修改 `data/creative_studio.db`，不修改 `data/images/`、`data/uploads/` 或 `chat2api/.env`。
- 本阶段不改变认证、权限、监听地址、部署或公网边界。

完成标准：`git diff --name-only` 中没有 UI、真实运行数据、凭据或无关模块；任何范围扩展都有用户明确授权。

## 实施顺序

### 1. 建立 Phase 1 变更卡

创建 `.scratch/ai-phase-1/spec.md`，至少写明目标、非目标、当前 production/test/dead 事实、设计决策、接口、影响文件、风险、回滚、验收例子、旧路径删除条件和完成门禁。先用 `rg` 确认以下事实：

- `StudioApplication -> CreativeGenerationService -> HttpModelClient` 的当前 caller；
- 当前 prompt loader、环境变量覆盖和各 prompt 文件的真实 caller；
- 当前 validator、schema、projector 与 repository 写入位置；
- `response_format`、`max_tokens` 和 usage 在 chat2api 上游的真实处理；
- `LegacyCreativeGenerationAdapter`、`schemas.py` 和 retired prompt 的 caller。

完成标准：变更卡状态为进行中，所有“当前事实”均有搜索或代码证据，且允许修改文件与实际计划一致。

### 2. 先写 registry 和 contract 红测

优先新增聚焦测试，例如 `tests/test_prompt_registry.py`、`tests/test_contract_registry.py` 和 `tests/test_contract_harness.py`。测试至少先证明以下行为在实现前失败：

- 缺 prompt 文件、越界路径、错误 hash、未知变量、未知 schema/validator/projector ID 会拒绝启动；
- registry JSON 键顺序不改变加载后的语义；prompt 规范化模板内容变化一定改变 `template_sha256`；
- 六个 `(id, version)` 复合键和生命周期有效，三个 production PromptSpec 各有且只有一个 production caller，candidate/retired 不可作为 production contract 解析；
- fake port 不读取环境凭据、不打开真实数据库、不访问网络；
- provider 不支持的 `response_format`/`max_tokens` 能力不会被报告为已执行；
- `response.json()` 抛错或返回非对象保留 `$` 字段路径。
- P0 prompt compiler 对 `$unknown`、`${task_type}`、用户值中的 `{{...}}`、换行、Unicode、超长文本和恶意指令的回归测试继续通过；
- fake text port 覆盖成功、截断/非法 JSON、Markdown wrapper、重复结果、第二批和最大调用数；fake image port 覆盖排队、超时、失败、重试、参考图 MIME 和私有 cursor。

先运行定向测试并记录预期失败原因，再实现最小代码使其通过。测试名称应描述业务行为，不能只断言 mock 被调用。

完成标准：变更卡记录 red 证据，新增测试从预期失败转为通过。

### 3. 实现唯一 registry 和显式映射

使用小而明确的外部接口隐藏加载、hash 和映射细节。`PromptSpec` 至少包含：稳定 ID、版本、相对路径、`template_sha256`、声明变量、input schema ID、output schema ID、validator ID、public DTO/projector ID、provider、model、evaluation set、生命周期和 GenerationPolicy 引用。

`template_sha256` 的唯一算法为：`sha256(Path.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()`，与当前 loader 传给 compiler 的规范化模板一致；它不是整个 registry JSON 的 hash。registry JSON 键顺序不参与该值。若后续要增加 registry 整体 digest，必须另命名并记录 canonical JSON 算法，不能复用 `template_sha256`。

registry JSON 只存数据；Python 代码维护 schema、validator 和 projector 的显式允许列表。允许的 prompt 路径必须 resolve 到仓库 `config/` 内；Phase 1 新建或修改的 prompt 版本放在 `config/prompts/`，现有六个文件保持单一权威位置，不创建内容副本。

生产 composition root 以 registry 的 `(id, version)` 作为唯一选择事实。现有 `WEB_ERP_AI_*_PROMPT_PATH`/`*_PROMPT_VERSION` 环境变量在 Phase 1 仅作为 deprecated 兼容选择器：只有当解析后的路径、版本和 `template_sha256` 精确匹配一个 `production` 条目时才接受，否则在 server bind 前抛出稳定的 `AiCreativeConfigurationError`。`WEB_ERP_AI_PROMPT_TEMPLATE` 不进入新的 production registry 路径；测试通过依赖注入内存 registry/template，旧 adapter 的直接兼容测试可暂时读取它。删除条件固定为 narrative 在 Phase 2、static 在 Phase 3、carousel 在 Phase 4 完成各自切换后删除对应选择器，Phase 5 清除所有残留。

每个 production use case 的 `GenerationPolicy` 必填：有序 `stages`、每个 stage 的 prompt ref、`max_attempts`、全局 `max_model_calls`、`max_output_tokens`、`timeout_seconds`、失败策略和 evaluation set。Phase 1 必须记录当前行为而不提升调用：单一 `draft` stage 最多尝试 2 次，`max_model_calls=2`；narrative `max_output_tokens=10000`，static/carousel `max_output_tokens=5000`；timeout 延续当前 composition-root 配置；两次均失败则以 `model_output_invalid` 结束。不要提前加入 critic、judge、selection 或新的 repair prompt。

`PromptRegistry` 在每次 `create_application()` 构造应用时加载并校验一次，可以作为该 application 内的不可变对象复用；模块 import 不能加载 registry、打开文件或构造 adapter。无效 registry 必须在 HTTP server bind 前以稳定配置异常失败。

每个 production use case 在 `config/` 下登记一个脱敏 deterministic evaluation fixture；Phase 1 只验证 fixture 可加载并满足当前 contract，不进行真实模型质量打分。candidate/retired prompt 在对应后续阶段建立 contract 前不需要 evaluation fixture。

不要为了未来阶段创建通用插件框架、动态导入器或浅层透传模块。

完成标准：registry 的有效 fixture 可稳定加载，所有无效 fixture fail closed，三类 use case 的关联可从一个 registry API 查询。

### 4. 接入生成元数据和 model ports

通过当前 `generation_models.py`、repository migration 和 service seam 保存可追溯元数据。对已有数据库只设计和测试幂等加法迁移；不直接打开或修改真实运行库。旧记录缺少新字段时必须有明确的 legacy/unavailable 表达，不能伪造 hash 或版本。

`TextModelPort`/`ImageModelPort` 应表达领域需要及 provider capabilities；现有 `HttpModelClient` 和图片 client 作为 Adapter 实现或被窄适配。`usage_source` 对 ChatGPT Web 保持 `estimated` 或 `unavailable`，不能改回 `exact`。

完成标准：临时 SQLite 的新旧 schema 均可启动；新生成记录包含真实 registry 元数据；旧记录仍可通过公开 mapper 安全读取。

### 5. 建立三类 production contract harness

从 `create_application()` 注入 deterministic fake text/image port、临时 SQLite、临时文件和固定 clock。叙事、静态展示、轮播每类至少覆盖：

1. 一个成功样例；
2. 一个格式错误样例，断言 `error_code=model_output_invalid`、`phase=validation`、`retryable=false`，并分别使用 narrative `items[0].story`、static `items[0].title`、carousel `items[0].frame_plan[1].description` 作为期望 `field_path`；两次失败后 fake text 调用数必须为 2；
3. 一个植入私有字段的样例，递归公开扫描必须为零；
4. 一个第二批样例，断言相同规范化输入的 `input_fingerprint` 相同、run ID 不同且 batch index 为 1/2，同时不把第二批策略的 Phase 2/4 业务改造提前实现。

harness 必须证明 production caller 选择的 PromptSpec、compiler、validator、public projector 和持久化元数据来自同一 registry 项；经 HTTP route 检查时仍保留现有状态码和 `error` 文本，并以加法字段返回结构化错误。`static-v1` 只验证 candidate inventory 状态、文件 hash 和 production 不可选择，不运行其未来 contract，不得把 candidate 状态写成已上线。

完成标准：三类矩阵全部通过，fake 调用数、registry ID、hash、schema 版本、repository 行和公开 DTO 可以互相核对。

### 6. 废弃边界与文档收尾

通过测试或静态检查阻止新代码调用 retired prompt loader、死 schema 和旧 adapter。保留仍有兼容 caller 的实现，并在代码或 registry 元数据中记录替代项和删除条件。同步更新：

- `.scratch/ai-phase-1/spec.md` 的状态与完成证据；
- `docs/ai-rebuild-master-plan.md` 中仅与新事实直接相关的矩阵/允许文件；
- `项目代码地图.md` 中 registry、contract、port 和 harness 的真实位置；
- `docs/operations.md` 中启动校验和加法迁移边界；
- `progress.md` 顶部 Phase 1 记录；
- `CHANGELOG.md` 仅在确有用户可见变化时更新。

完成标准：文档与代码事实一致，不把未接线 candidate 或未验证真实网关写成已完成生产能力。

## Phase 1 完成门禁

只有同时满足以下条件，才可以把 Phase 1 标为完成：

1. Phase 0 提交仍在当前分支历史中，Phase 0 回归测试继续通过。
2. registry 对缺文件、越界路径、错 hash、错变量和未知映射 fail closed。
3. 叙事、当前静态、轮播各有一个可查询 production PromptSpec；静态候选和两个 retired prompt 只有 inventory/deprecation 记录，并准确标注生命周期。
4. 每个 active production prompt 恰好关联一个 input schema、output schema、validator、public projector 和 production caller。
5. registry JSON 不动态 import、执行代码或接受任意路径。
6. 新生成记录保存真实 prompt/contract/model/provider/fingerprint/version/usage-source 元数据；旧记录不伪造这些值。
7. ChatGPT Web 不支持或未兑现的 capabilities 被明确记录和测试。
8. 三类 contract harness 均覆盖成功、格式错误、私有字段和第二批样例。
9. composition root 的 fake harness 不读取真实凭据、数据库、图片或上传文件，不访问网络。
10. retired/legacy 项具有 `deprecated_since`、replacement、允许读取场景、禁止新调用和删除条件。
11. 现有 UI、HTTP URL、公开 DTO 形状和错误 envelope 没有被破坏。
12. 所有确定性测试、语法/编译检查和 `git diff --check` 通过。
13. 至少执行一次独立的双轴只读 review：规格轴对照 Phase 1 变更卡和总纲，规范轴对照 `AGENTS.md`/`CODE_STYLE.md`；所有 Critical/Important 必须修复并重新验证，最终保留 review 结论。
14. `progress.md`、代码地图、运维手册、总纲和 Phase 1 变更卡已同步当前事实。
15. 真实 AI、图片网关、浏览器和真实数据库写入均明确记录为已验证或未验证，不能含糊推断。

任一条件未满足时，状态仍是 Phase 1 进行中。

## 验证和提交

至少执行：

```powershell
Set-Location D:\code\ai_creative_studio
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -v
node --check static\app.js
python -m compileall -q src chat2api
git diff --check
git status --short --branch
```

根据 registry、repository migration 和 contract harness 的实际文件再增加定向测试。测试失败时报告具体失败项和环境原因，不得伪造全部通过。提交前显式核对暂存清单，排除 `chat2api/.env`、`data/creative_studio.db`、`data/images/`、`data/uploads/` 和生成产物。

Phase 1 通过全部门禁后创建一个边界清楚的提交，建议提交信息：

```text
refactor: add phase 1 AI contract registry
```

提交后重新运行 `git status --short --branch`，记录完整 commit hash。保留当前分支，不自动合并或推送。

完成标准：Phase 1 提交存在、工作树状态已记录、验证证据与实际命令输出一致。

## Phase 2 交接生成规则

Phase 1 实现提交且工作树检查完成后，新建：

```text
docs/superpowers/handoffs/<执行日期>-ai-rebuild-phase-2-handoff.md
```

文件名中的日期使用执行当天的 `YYYY-MM-DD`。Phase 2 交接必须是可以整段交给另一个新会话的执行文档，并至少包含：

- 项目、分支、Phase 0 和 Phase 1 的完整提交 hash，以及祖先检查命令；
- Phase 1 实际修改文件和每个文件的职责；
- registry 的实际路径、PromptSpec ID、生命周期、hash 算法和显式映射入口；
- production composition root、Text/Image port、fake 和 contract harness 的真实 caller；
- 数据库加法迁移、旧记录兼容和回滚事实；
- 全量及定向测试数量、命令和结果；
- 真实 AI、图片网关、浏览器、真实数据库是否验证或修改；
- 仍保留的 legacy/retired 路径、实际 caller 和删除条件；
- 总纲 Phase 2 的目标、非目标、允许范围、叙事 contract 要求、质量评测门槛和完成门禁；
- 明确指令：只完成 Phase 2，不进入 Phase 3；Phase 2 完成后再生成 Phase 3 交接。

Phase 2 交接中不得保留 `TBD`、`TODO`、未知 commit hash 或“参照上文自行处理”之类占位内容。用当前代码和提交结果替换所有事实。生成后执行 Markdown、路径和 commit 自检，再将 Phase 2 交接文档及对应 `progress.md` 记录创建为第二个 docs-only 提交；不要 amend Phase 1 实现提交。最终把可点击路径、Phase 1 实现提交 hash 和 Phase 2 交接文档提交 hash 一并交给用户。

完成标准：一个没有本会话上下文的新 AI 能仅凭 Phase 2 交接及其强制阅读文件，准确说明从哪里开始、只做什么、如何证明完成、何时停止。

## 最终报告格式

向用户报告：

1. Phase 1 是否全部通过；
2. Phase 1 commit hash 和分支状态；
3. 实际修改文件及职责；
4. 新增 contract/registry/port/harness 和测试；
5. 全量与定向验证结果及失败项；
6. 是否调用真实 AI、图片网关或浏览器；
7. 是否修改真实数据库、图片、上传文件或 `.env`；
8. 仍保留的旧路径及删除条件；
9. 回滚方法；
10. 最新 Phase 2 交接文档的可点击路径及其提交 hash。

如果 Phase 1 未完成，第 10 项改为 Phase 1 阻塞交接路径，并明确不能进入 Phase 2。
