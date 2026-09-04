# AI 创意能力重构总纲

> 文档状态：ACTIVE，重构基线（唯一权威）
> 编写日期：2026-09-03
> 适用对象：负责本项目 AI 能力、提示词、网关、图片任务、前端结果和测试的后续 Agent 及维护者
> Supersedes：`docs/superpowers/specs/2026-09-01-ai-generation-architecture-design.md` 和 `docs/superpowers/specs/2026-09-02-display-frame-flow-design.md` 中与本文“当前真实事实”和“目标决策”冲突的段落；旧文档保留为历史背景，不再作为实施依据。

本文严格区分两类内容：第 1、2 节是已由代码/配置/测试证据确认的当前事实和问题；第 3 至第 10 节是本次批准的重构目标、接口和迁移门禁。特别地，“一次共享 planner + 图片直出”的轮播 v1 是批准的目标决策，不是对当前所有实现细节的宣称；当前代码与提示词之间的首帧会话漂移必须按 Phase 3/4 收口。独立文字首帧会话只作为未来 v2 `GenerationPolicy` 的评测候选。

## 0. 先读这里：执行协议

这份文档不是历史记录，也不是愿望清单。它定义当前问题、目标架构、迁移顺序和完成门禁。后续 Agent 开始任何 AI 相关工作前，必须按以下顺序读取：

1. `AGENTS.md`
2. `progress.md`（只用于了解历史，不作为当前事实）
3. `项目代码地图.md`
4. `docs/operations.md`
5. 本文档
6. `CODE_STYLE.md`、`CONTEXT.md`，以及本次涉及目录中的 ADR

然后必须完成一次“事实确认”：从 `src/creative_studio/app.py` 的 composition root 追到实际生产调用者，确认当前代码、配置文件、数据库结构和测试是否一致。任何文档与运行代码冲突时，先在变更卡中记录冲突；不得通过新增兼容分支掩盖冲突。

### 0.1 工作规则

- 一个变更只负责一个可验收的迁移切片，但一个切片必须完整覆盖 prompt、输入、输出、校验、持久化、公开 DTO、调用者和测试。
- 新实现替换旧实现时，必须在同一个变更或紧随其后的明确清理变更中删除旧生产路径、旧 schema、旧提示词和误导性测试。兼容层必须有删除版本和负责人。
- 测试从生产 interface 进入。只测试死代码、旧 adapter 或手工构造的内部对象，不算生产验证。
- 任何真实 AI 请求前，先用确定性 fake adapter 完成 red-capable 测试；真实请求必须使用固定、脱敏、低成本评估样例，并明确标记“已验证”或“未验证”。
- 不把模型正文、私有提示词、令牌、完整参考图片、内部路径或会话游标写入日志、公开 API、评审导出或文档。
- 不修改真实数据库、图片、上传文件、`chat2api/.env` 或网络绑定配置，除非变更卡得到用户明确授权，并具备备份、迁移和回滚方案。
- 后续 Agent 只执行本文档已批准的阶段和门禁，不自行把模型变成“自主 Agent”、增加工具调用或扩大业务范围；任何多轮生成、评审、修复都必须是 registry 可见、调用次数有上限且预算可测的 `GenerationPolicy` stage。

### 0.2 每个切片的交付物

每个 Agent 完成前必须交付：

- 变更卡：目标、非目标、当前事实、设计决策、影响文件、风险、回滚和验收例子；
- 代码与配置；
- 失败优先的定向测试；
- 生产入口验证结果；
- 删除/废弃清单；
- `progress.md` 的一条简洁记录；用户可见行为变化时更新 `CHANGELOG.md`；
- `git diff --check`、必要的单测、语法检查和未验证项。

## 1. 当前真实事实

### 1.1 生产组合根

`StudioApplication` 在 `src/creative_studio/app.py` 中创建 `StudioRepository`、`ImageJobRunner`、`GptWebImageClient`，设置默认环境，然后注入 `HttpModelClient` 到 `CreativeGenerationService`。因此当前正常启动时走的是：

```text
正式前端
  -> POST /api/projects/{id}/generate
  -> StudioApplication.generate
  -> CreativeGenerationService.generate
  -> _generate_with_model_client
  -> HttpModelClient
  -> chat2api /v1/chat/completions
  -> ChatGPT Web
```

展示图片走另一条远程 seam：

```text
CreativeGenerationService
  -> repository.complete_visual_generation
  -> ImageJobRunner
  -> chat2api /v1/images/jobs
  -> ChatGPT Web 图片会话
```

`LegacyCreativeGenerationAdapter`、`schemas.py` 的 `VisualRecommendationSchema`、`DisplayScheme` 的部分保存路径和若干独立提示词加载函数并不是当前完整生产链路。后续 Agent 不得因为它们存在就假设它们已接线。

### 1.2 三类当前功能

#### 叙事类

- 生产提示词：`config/ai_creative_prompt_v5.txt`；
- 一次文字模型调用；
- 固定 5 个故事，每个 2 个钩子，每个钩子 3 个场景；
- `validate_creative_recommendations()` 手写校验；
- 不验证故事之间的差异，也不验证同一故事两个钩子的“明显不同”；
- 游戏资料被代码读取，但当前 v5 提示词没有 `{{game_info}}`，实际不会进入 prompt；
- 默认代码路径寻找 v1 游戏资料，而仓库实际只有 v2，启动器环境变量暂时绕过了这个问题。

#### 静态展示类

- 生产提示词：`config/ai_visual_creative_prompt_v2.txt`；
- 一次返回 3 套首帧方案；
- 新输出结构是 `creative_summary/frame_plan/first_frame`；
- 校验器随后伪造旧 UI 字段：`subtitle`、`core_subject`、`layout` 都取首帧内容，`visual_style` 取连续性规则，关键词和参考说明是固定值；
- 3 个图片任务异步入队。

#### 轮播展示类

- 生产提示词：`config/ai_visual_carousel_prompt_v1.txt`；
- 一次共享文字调用返回 3 套完整路线和首帧草稿；
- 代码直接使用共享草稿生首帧，并没有提示词声称的“三套方案各自新建文字会话并重新生成首帧”；
- 后续画面不调用 `ai_visual_follow_up_prompt_v1.txt`，而是使用 `generation_service.py` 中硬编码的图片提示词；
- 后续画面串行提交、等待、重试一次，并把上一张图片作为图片模型参考图；
- `count_mode=ai` 允许每套方案不同数量；旧设计和旧文档仍有统一数量表述。

### 1.3 当前数据和公开接口事实

- `generations` 保存原始 `items_json`、批次、指纹、错误和会话标识；
- `visual_items` 重复保存视觉正文、图片提示词、图片状态和图片路径；
- `display_frames` 再保存逐帧正文、私有图片指令、状态和路径；
- `generation_history()` 大部分情况下过滤私有字段，但 `StudioApplication.history()` 调用的是它而不是专门的公开 wrapper；
- `repository.adopt_visual()` 直接返回原始视觉 `content_json`，已确认会泄露 `image_generation_instruction`、`conversation_id` 和 `parent_message_id`；
- 失败批次在下一次同指纹预约时被删除，诊断证据会消失；
- 旧的 `generations.items_json`、`adoptions.snapshot_json` 等历史 raw 数据可能已经包含私有图片指令或供应商游标；未来公开 mapper 不能自动修复已落库数据，必须通过备份、临时库验证和可回滚的一次性 projection scrub/重建处理；
- 前端生成请求和连续画面继续请求都是同步 HTTP 操作。连续多帧可能超过单次请求和方案锁的合理时长；
- 测试导入 `creative_studio.app` 会实例化全局 `APP`，可能打开并迁移真实 `data/creative_studio.db`，破坏测试隔离。

## 2. 完整问题台账

问题必须按下面类别处理；“已有测试通过”不能关闭问题，只有满足对应验收门禁才能关闭。

### P0：数据和用户安全

1. 采用视觉方案返回私有提示词和会话游标。
2. 公开历史、采用、状态和导出没有统一使用一个公开 DTO；不同路径的过滤规则不一致。
3. 图片参考图 MIME 被写死为 PNG，JPEG/WebP 字节可能被错误标记。
4. 失败记录被删除，错误上下文不可追溯。
5. 测试可能触碰真实数据库；真实 AI 凭据和运行数据必须与 fake 测试隔离。

### P1：契约和功能正确性

1. 生产 prompt、validator、UI 字段不是同一套契约。
2. `schemas.py` 的抽取 schema 与当前生产输出不兼容，属于死 schema。
3. 静态高质量提示词 `ai_visual_static_creative_prompt_v1.txt` 没有生产调用者。
4. 首帧/后续提示词文件存在但没有生产调用者；后续提示词被硬编码替代。
5. 第二批复用会话但发送与第一批相同的业务指令，没有“新一批/避免重复”约束。
6. 格式重试原样发送同一 request，不携带校验错误或修复指令；最终错误丢失具体字段。
7. “轮播=是但没数量”没有在模型调用前拒绝，可能白花两次请求。
8. 用户输入中的 `$unknown` 会触发模板错误，`${task_type}` 会被静默替换；提示词编译器存在二次解释。
9. 游戏资料读取但没有进叙事 prompt；游戏资料默认版本路径错误。
10. 上传的参考文件只把文件名传给文字模型，文件内容没有按设计进入文字或图片模型。
11. `response_format` 和 `max_tokens` 从工作台发到网关后没有进入 ChatGPT Web body；上层配置是虚假的控制面。
12. 网关粗略估算 token，但生成服务标记为 `exact`，用量数据不可信。
13. 首帧图片成功与会话游标分两次写入，存在继续流程读取旧游标的竞态。
14. 方案继续锁的过期时间可能短于合法的多帧生成时间，恢复逻辑可能释放仍在执行的锁。
15. 前端只轮询首图/顶层状态，继续生成是长同步请求，用户无法可靠看到逐帧状态或恢复操作。

### P2：架构、治理和可维护性

1. `CreativeGenerationService` 同时负责输入规范化、fingerprint、prompt 选择、模型调用、校验、数据库写入、图片编排、锁和恢复，模块过浅、职责过多。
2. `repository.py` 同时维护项目、用户、生成、视觉项、逐帧状态、采用和恢复；私有/公开转换分散。
3. 旧 adapter、新 model client、旧 schema、新 schema 长期并存，没有迁移完成标准。
4. `progress.md` 是追加式历史，不提供当前事实优先级；代码地图、运维手册、README 与最新代码存在冲突。
5. launcher、app、ai_creative、chat2api 各自拥有配置默认值，缺少配置注册表和版本指纹。
6. fingerprint 不包含提示词版本/hash、schema 版本、模型/供应商、标签目录版本、游戏资料版本、参考资料版本，无法证明两批输入真的是同一定位。
7. 测试覆盖局部行为和死路径，缺少生产 composition root、prompt-contract、隐私、质量评测和恢复竞态测试。

## 3. 重构目标：深模块和唯一事实

目标不是把所有文件拆得更细，而是建立三个真正有深度的业务 Module。每个 Module 用小 Interface 隐藏 prompt、schema、模型策略、持久化和错误细节。

### 3.1 三个业务 Module

```text
NarrativeGeneration
StaticVisualGeneration
CarouselVisualGeneration
```

它们共享基础设施 port，但不共享会改变业务契约的 validator 或 prompt。叙事和展示必须保持明确分支；静态展示和轮播展示可以共享基础事实和图片任务基础设施，但输出 schema 必须分别声明。

### 3.2 推荐外部 Interface

AI 领域对应用调用者只暴露以下三个入口。项目 CRUD、采用和账号管理属于其他应用 Module，不把它们塞进 AI Interface：

```python
class CreativeAI(Protocol):
    def start(self, command: GenerationCommand, *, idempotency_key: str) -> GenerationHandle: ...
    def read(self, query: GenerationQuery) -> PublicGenerationView: ...
    def continue_carousel(self, command: CarouselContinuation, *, idempotency_key: str) -> OperationHandle: ...
```

`GenerationCommand` 是内部判别联合：`NarrativeInput | StaticVisualInput | CarouselInput`。对 HTTP 调用者，facade 可以只接受已完成授权的 project ref、请求键和服务端归一化输入；不要把模型请求字段或二十个裸字段暴露给浏览器。标签、参考资料、prompt registry、模型、SQLite 和队列都隐藏在 Module 内。`GenerationHandle` 只返回 run id、公开结果投影和可轮询的操作引用；`CarouselContinuation` 只表达项目、方案和幂等键。采用和单图重试由项目/图片应用 Module 处理，不能让浏览器知道 `ModelRequest`、SQL row、`image_prompt` 或会话游标。

每个 Interface 必须定义：

- 参数类型和字段边界；
- 顺序约束和幂等语义；
- pending/queued/generating/success/failed/blocked/completed 状态；
- 可重试错误与不可重试错误；
- 超时是“操作仍可能在后台执行”还是“操作已失败”；
- 公开字段和私有字段；
- 性能特征：生成入口立即返回还是同步等待。

`GenerationHandle` 的文字状态与图片 artifact 状态必须分开表达：文字成功但首图仍排队是 `text_succeeded + artifacts.pending`，不能把“模型响应成功”误称为整个生成完成。公开读取至少能观察 `accepted/planning/text_succeeded/partial/completed/failed`、每个 scheme/frame 的状态和 `operation_id`。

错误必须是稳定类型，而不是依靠中文字符串判断：`InputRejected(code, field_path, message)`、`Conflict(code, current_state, retry_after)`、`DependencyUnavailable(provider, retryable, trace_id)`、`ModelOutputRejected(contract, path, reason_code, attempt)`、`OperationNotFound`、`StorageFailure`。HTTP 适配器统一映射状态码；浏览器只收到 code、message、operation id 和安全摘要。

HTTP 兼容策略：现有前端依赖的 `error` 中文文本和当前 422/503/502 状态码在迁移期间保留；新增稳定的 `error_code/phase/retryable/trace_id` 采用加法方式提供。旧 envelope 只有在前端切换、contract 测试通过且记录删除日期后才能移除，不能为了“统一错误”直接破坏现有 UI。

### 3.3 内部 Port 与 Adapter

外部 ChatGPT Web 是真正的外部依赖，定义 port：

```python
class TextModelPort(Protocol):
    def complete(self, request: TextModelRequest) -> TextModelResponse: ...

class ImageModelPort(Protocol):
    def submit(self, request: ImageModelRequest) -> ImageJobRef: ...
    def status(self, job_id: str) -> ImageJobStatus: ...
    def download(self, result: ImageJobResult) -> LocalImage: ...

class ClockPort(Protocol):
    def now(self) -> datetime: ...

class ReferenceAssetPort(Protocol):
    def list_for_project(self, project_id: int) -> tuple[ReferenceAsset, ...]: ...
    def read(self, asset_id: int) -> ReferenceAssetContent: ...
```

生产 Adapter 是 `HttpModelClient`、`GptWebImageClient`、真实时钟和本地文件适配器；测试 Adapter 是内存模型、可编程图片队列、固定时钟和临时文件系统。SQLite 是本地可替代依赖，业务 Module 通过 repository port 访问，不在 prompt builder 中打开数据库。

`TextModelPort` 必须携带 provider capabilities，例如 `structured_output_enforced`、`token_limit_enforced`、`conversation_resume` 和 `multimodal_input`。ChatGPT Web 不一定能忠实映射 OpenAI 的每个参数；Adapter 能翻译时才发送，不能翻译时必须显式报告 unsupported，让上层依靠 prompt + validator，而不能接收后静默丢弃。usage source 必须如实是 `exact`、`estimated` 或 `unavailable`。

### 3.4 PromptSpec：prompt 的唯一权威

所有生产 prompt 必须注册为 `PromptSpec`，而不是靠环境变量散落选择：

```json
{
  "id": "creative.narrative.generate",
  "version": "v6",
  "path": "config/prompts/narrative/v6.txt",
  "input_schema": "NarrativePromptInput.v1",
  "output_schema": "NarrativeResult.v1",
  "validator": "NarrativeResultValidator.v1",
  "public_dto": "NarrativePublicDTO.v1",
  "private_fields": [],
  "provider": "chatgpt-web",
  "model": "gpt-5-6-mini",
  "max_output_tokens": 10000,
  "retry_policy": "format-repair-v1",
  "evaluation_set": "evals/narrative.v1.jsonl"
}
```

启动时必须检查 registry：文件存在、变量完整、prompt hash 与记录一致、validator 和 DTO 可加载。每次 `GenerationRun` 保存 `prompt_id/version/hash`、schema 版本、模型、供应商、输入快照 hash、标签目录版本、资料版本和实际 usage source。

### 3.5 模板编译规则

只允许一种占位符语法，例如 `{{name}}`。变量替换必须是单次、字面量替换；用户输入永远不能再次作为模板解析。编译器必须有以下 red tests：美元符号、`${...}`、双大括号、换行、超长文本、恶意指令和 Unicode。变量必须放进有界且有明确标签的数据区，不能依赖“请忽略用户指令”这种脆弱否定语句。未知变量、缺变量、hash 不匹配时 fail closed；不得静默 append 未声明输入。

### 3.6 GenerationPolicy：让 AI 能力可升级但不失控

模型调用阶段必须在 `PromptSpec`/`UseCaseDefinition` 中显式声明：`stages`、`max_model_calls`、预算、超时、失败策略和评测集。v1 可以是一轮 `draft -> deterministic_lint -> optional_repair -> finalize`；质量评测证明需要提升后，v2 才能注册有界的 `diverge -> critic -> select` 或 `plan -> verify -> finalize`。每个内部阶段有自己的 PromptSpec、内部 schema、调用计数和 trace，但不新增用户可见业务契约。禁止在旧函数中偷偷增加循环、无上限 repair 或隐藏 judge。

## 4. AI 创意能力设计

重构不是只修 JSON，而是让模型输出能支持创意评审、制作判断和后续图片执行。

### 4.1 叙事类 Result v1

保留当前 5×2×3 的用户可理解形状，但补足质量契约：

```json
{
  "items": [
    {
      "concept_id": "A",
      "story": "一句话故事机制",
      "audience_tension": "一个具体欲望或矛盾",
      "product_value": "一个真实产品价值",
      "hooks": [
        {"text": "钩子", "scenes": ["画面", "画面", "画面"]},
        {"text": "不同钩子", "scenes": ["画面", "画面", "画面"]}
      ],
      "evidence": {"confirmed": [], "inferred": [], "to_confirm": []},
      "risks": ["最可能失真的点"]
    }
  ]
}
```

如果必须保留旧 UI，做一次明确的 `NarrativePublicDTO` 映射；不把新字段偷偷塞进旧字典，不复制字段冒充语义。校验器至少检查数量、类型、长度、URL/Markdown/思维链、concept id 唯一、故事差异和钩子差异。差异检查可以是确定性规则加评估模型，不要只依靠提示词。

### 4.2 静态展示 Result v1

正式采用 `ai_visual_static_creative_prompt_v1.txt` 的方向，但必须与业务 schema 一起落地。每案要回答：看到了什么、证明了什么、为什么停留、如何制作、什么事实还未确认。

建议字段：`concept_id/title/creative_summary/audience_tension/product_value/visual_mechanism/creative_sources/evidence_ledger/static_frame/asset_plan/production_risks/review/image_generation_instruction`。`image_generation_instruction` 永远是私有字段，公开 DTO 在类型层面不存在它。

### 4.3 轮播 Result v1

轮播是一个方案内部的 `frames`，不是把批次方案序号和轮次混用：

```json
{
  "concept_id": "A",
  "title": "方案标题",
  "creative_summary": "方案机制",
  "creative_sources": ["来源"],
  "frame_count": 3,
  "visual_continuity_rules": ["连续性规则"],
  "frame_plan": [
    {"index": 1, "description": "首帧路线"},
    {"index": 2, "description": "第二帧路线"},
    {"index": 3, "description": "第三帧路线"}
  ],
  "first_frame": {
    "index": 1,
    "content": "静态首帧内容",
    "image_generation_instruction": "私有图片指令"
  }
}
```

`none` 为 1 帧；`fixed` 必须等于用户选择的 2 至 5；`ai` 每套独立决定 2 至 5。输入缺数量时在模型调用前返回 `GenerationInputError`。共享规划、独立首帧和后续图片到底采用哪种流程，必须由 ADR 决定并与 prompt 文案一致；不得一半执行旧设计、一半执行新设计。

重构 v1 的批准方向是：一次共享 planner 文字响应直接产出每套方案的私有首帧图片指令，图片 Adapter 直接执行；后续帧按已锁定路线编排图片指令并携带上一张实际图片。当前代码已经接近该方向，提示词中“每套方案另开文字会话生成首帧”的描述必须在切换前删除或明确标成历史。若评测证明独立文字会话有价值，只能作为后续版本显式登记的 `GenerationPolicy` stage，不能在旧函数里隐式恢复。

### 4.4 第二批策略

第二批必须使用同一输入快照的 `input_fingerprint`，但使用显式的 `batch_strategy`：

```text
生成下一批，保留任务事实和输出结构；读取上一批摘要用于去重；
每个方案必须改变核心创意机制，不得只替换角色、颜色、文案或材质；
避免复用上一批的故事、钩子、画面路线和视觉关系；只返回当前 schema。
```

第二批请求、上一批摘要、去重策略和结果差异必须可在 fake adapter 测试中观察。不能仅依赖会话 ID 推断模型会自动创新。

### 4.5 参考资料策略

文件名不是文件内容。ReferenceAssetPort 必须明确每个用例是否：

- 读取文本资料并摘要后进入文字 prompt；
- 将图片作为图片模型 `ref_assets`；
- 只作为用户标记而不发送给模型。

选择“不发送”时必须在 UI 和文档中明确，不得提示词暗示模型已经看过文件。`ReferenceMaterial` 应保存 digest、mime、size 和 extraction_status；PromptContext 只接收受控的摘要或图片资产，不接收任意本地路径和未解析 binary。

## 5. 状态、持久化和公开 DTO

### 5.1 单一生成运行记录

引入 `GenerationRun` 作为一次生成的权威记录；`visual_items` 和 `display_frames` 只保存各自状态，不重复保存同一份 prompt/会话事实。每个运行记录包含：

- `run_id/project_id/kind/batch_index`；
- 输入快照 hash、prompt id/version/hash、schema version；
- provider/model、标签目录版本、游戏资料版本、参考资料版本；
- 状态、开始/结束时间、错误 code/message、attempt；
- usage 数值和 `exact/estimated/unavailable` 来源；
- 供应商会话游标仅存内部表或加密/摘要引用，不出现在公开对象。

失败记录保留。清理必须是独立的保留策略，不得在新请求中删除诊断证据。

最低风险迁移方式不是一开始新建大量表并永久双写，而是先引入 `RunStorePort`，让现有 `generations/visual_items/display_frames` 只作为 Adapter 内部实现；业务 Module 只接触 typed Run/Scheme/Frame。若后续确需 canonical 表，执行“旧表只读 importer -> 校验 hash/计数 -> 切读 -> 停止旧写 -> 到期删除”，不允许无限双读双写。

### 5.2 连续画面状态机

每帧状态只允许定义的迁移：

```text
pending -> generating -> success
pending -> generating -> failed -> pending (retry)
failed -> blocked (达到策略上限)
```

方案继续是后台 Operation：提交后立即返回 operation id；worker 逐帧执行，当前帧图片和新会话游标在同一事务提交；锁采用 lease + heartbeat；重启只恢复明确超时且没有活动心跳的 operation。下一帧只能读取上一帧已提交的成功图片和游标。

会话游标必须是不可分割的 `ConversationCursor(conversation_id, parent_message_id, provider, revision)`。图片完成、artifact、frame 状态、scheme cursor 和 operation revision 必须一次提交；旧 worker 的条件更新不匹配时返回 stale，不能覆盖新 attempt。图片成功但供应商游标缺失时，结果是 `provider_protocol_invalid`，不是成功。

### 5.3 公开 DTO

所有浏览器可见结果只能由 `PublicResultMapper` 生成。它从内部对象构造新对象，而不是 `dict.copy()` 后删几个 key。公开对象不得出现：

- `image_prompt`、`image_generation_instruction`；
- `conversation_id`、`parent_message_id`；
- 本地图片路径、上传存储名、网关 job id；
- 内部错误堆栈、完整模型正文和私有上下文。

历史、状态、采用、导出四种接口必须共同调用该 mapper，并有反射式隐私测试。

## 6. 分阶段迁移路线

迁移按“先止血、再立契约、再替换功能、最后清理”执行。每阶段完成前不能进入下一阶段。

每一阶段都必须有开始条件、允许修改的目录、禁止动作、定向命令、验收例子、失败回滚和旧实现删除条件。以下是最低要求。`AGENTS.md`、代码地图、`docs/operations.md` 和本总纲只能在阶段收尾同步当前事实；实现中发现冲突先记录证据，不在多个文档里追加互相矛盾的临时解释。

### Phase 0：冻结事实和安全止血

范围：只修确定的安全/数据边界，不改创意输出目标。

允许修改：`docs/`、`AGENTS.md`、`progress.md`、`CHANGELOG.md`、`项目代码地图.md`、`.scratch/ai-phase-0/spec.md`，以及 `src/creative_studio/` 下与止血边界直接相关的 `app.py`、`repository.py`、`prompting.py`、`image_jobs.py`、`model_client.py`、`ai_creative.py`、`carousel.py`、`generation_models.py`、`generation_service.py`、`public_projection.py`、`projection_scrub.py` 和对应测试。禁止新增 AI 业务字段或改变创意输出目标。

动作：

1. 公开 DTO 统一修复采用、历史、状态和导出泄露；对历史 `items_json`/`snapshot_json` 执行 deny-by-default projection，必要时在临时数据库中 scrub 后再按备份和回滚方案更新正式数据，旧 raw 永不直接公开。
2. 修复模板单次字面替换。
3. 修复 JPEG/WebP MIME 传递。
4. 保留失败记录，增加 error code 和 validation detail。
5. 测试隔离 `APP` 和真实数据库；fake adapter 不读取真实凭据。
6. 叙事默认游戏资料路径统一到实际版本。

完成门禁：隐私扫描对所有公开路由通过；提示词特殊字符 red test 通过；失败两次后历史仍有两条记录；空轮播数量的模型调用计数为零；全套代码检查通过；无真实 AI 请求。

回滚：Phase 0 文档/止血、Phase 1 registry/元数据、Phase 2 叙事、Phase 3 静态、Phase 4 轮播/图片状态机、Phase 5 清理分别形成可回滚提交或开关；数据库 additive migration 与功能切换分开，先在临时库验证并备份，禁止用回滚覆盖用户运行数据。

### Phase 1：建立 PromptRegistry 和 Contract Harness

范围：先不替换 UI，建立唯一事实和生产契约测试。

开始条件：Phase 0 全部通过。允许修改：`config/`、`.scratch/ai-phase-1/spec.md`、新增 contract/registry/port 模块，以及接入 registry、port、生成元数据和 production contract harness 所必需的 `app.py`、`generation_service.py`、`generation_models.py`、`repository.py`、`model_client.py`、`image_jobs.py`、`ai_creative.py`、`prompting.py` 和对应测试；阶段收尾可同步 `docs/`、`progress.md` 与 `项目代码地图.md`。不修改正式 UI，不切换用户可见生产输出。

动作：

1. 建立 `config/prompts/registry.json` 和 prompt 目录。
2. 为叙事、静态、轮播各登记一个 PromptSpec。
3. 将 prompt compiler、input schema、output validator、public DTO 通过 registry 关联。
4. 把 prompt hash/schema/version/input fingerprint 写入生成记录。
5. 从真实 `StudioApplication` composition root 注入 fake TextModelPort/ImageModelPort，写端到端 contract harness。
6. 将当前死 schema、旧加载函数以及未接线的独立首帧/后续 prompt 标记 deprecated，禁止新代码调用；它们只允许被历史审计读取。

完成门禁：registry 能在启动时拒绝缺文件/错 hash/错 validator；每个生产 use case 有至少一个成功、一个格式错误、一个私有字段、一个第二批样例；测试不触碰真实 `data/`。

回滚：registry 读取失败时保留旧路径只作为临时 feature flag；feature flag 必须有删除日期，不能作为默认永久双轨。registry 只引用代码中显式注册的 contract/validator/projector，不动态 import 任意路径，不执行 prompt 中的 Python、SQL、工具或网络动作。

### Phase 2：重构叙事类

开始条件：Phase 1 全部完成门禁通过，Phase 1 实现已提交且工作树状态已检查；叙事 contract harness 通过是其中的必要子条件。允许修改：叙事 prompt/contract/module、生成服务的叙事分支、叙事 UI renderer 和对应测试。禁止修改视觉生产分支。

当前状态（2026-09-03）：Phase 2 已完成。生产叙事 caller 为 `NarrativeGeneration`，使用 registry 的 `creative.narrative.generate@v6` 和 `NarrativeResult.v1`；旧 v5 仅保留 retired inventory，旧 adapter 仅保留兼容 caller。真实 AI、图片网关、浏览器和真实数据库写入仍未验证。

范围：叙事输入、输出和第二批先收口，保持 UI 基本形状。

动作：

1. 实现 `NarrativeGeneration` Module 和 `NarrativeResult.v1`。
2. 加入游戏资料和参考资料的明确输入策略。
3. 实现带校验错误的 format repair；第二批使用显式去重指令和上一批摘要。
4. 实现公开 DTO 映射，UI 只消费 DTO。
5. 迁移叙事历史和采用，不再读取旧 raw dictionary。

完成门禁：生产入口测试能证明 prompt、validator、DTO 是同一 registry 项；第二批 prompt 与第一批不同且包含去重约束；模型错误能定位字段；质量评估集达到预先记录的最低分；旧叙事 adapter 无调用者后删除。

### Phase 3：重构静态展示类

开始条件：Phase 2 完成或明确隔离。允许修改：静态 prompt/contract/module、视觉公开 DTO、静态 UI renderer、对应图片任务适配器和测试。禁止向旧视觉字典继续加别名字段。

范围：上线高质量静态创意契约，停止伪造旧字段。

动作：

1. 将 `ai_visual_static_creative_prompt_v1.txt` 正式注册并与 schema 实现对齐。
2. UI 结果卡直接展示 `audience_tension/product_value/visual_mechanism/evidence/static_frame/asset_plan/review`。
3. 生图指令只在内部 `ImageModelPort` 使用。
4. 旧 `subtitle/core_subject/layout/visual_style` 映射只保留迁移读取，不再写入新数据。

完成门禁：三案有可观察的机制差异；每案有 confirmed/inferred/to_confirm；公开接口无私有字段；首图状态可恢复；旧视觉 validator 和伪造字段转换无生产调用者后删除。

### Phase 4：重构轮播和图片后台状态机

开始条件：Phase 3 的静态公开 DTO 和图片 seam 通过。允许修改：轮播 contract/module、图片 worker/store、状态查询 API、前端轮询。禁止保留同步长请求作为默认生产路径。

范围：轮播路线、首帧、后续帧和操作状态。

动作：

1. 通过 ADR 固定 v1 为“一次共享规划响应直接产出每套 private first-frame instruction，图片 Adapter 直接执行；后续按锁定路线编排图片指令并使用上一张实际图”。删除提示词中“独立文字会话重新生成首帧”的假承诺。若评测证明独立会话有价值，只能注册为 v2 的显式 `GenerationPolicy` stage。
2. 实现 `CarouselVisualGeneration` Module，统一 `none/fixed/ai` 输入与每方案帧数。
3. 把继续生成改为后台 Operation，前端轮询 operation 和逐帧公开状态。
4. 图片完成与会话游标原子提交；lease 有心跳；恢复只处理明确失活任务。
5. 参考图保留真实 MIME 和来源元数据。
6. 删除硬编码后续提示词，生产只从 registry 取 prompt 或明确的图片指令编排器。

完成门禁：2、3、4、5 帧均有 fake 测试；首帧部分成功不影响其他方案；后续帧只在上一帧成功后提交；重试幂等；重启恢复不重复生成；前端移动/桌面都能观察状态；真实 AI 冒烟若未授权则明确未验证。

当前状态（2026-09-04）：Phase 4 实现已完成。`CarouselVisualGeneration`、共享 planner prompt、后台
`carousel_operations`、lease/heartbeat/过期恢复、逐帧公开状态、202 continue API 和前端 operation
轮询均已接线；决策记录见 [`docs/adr/0003-carousel-v1-background-operation.md`](adr/0003-carousel-v1-background-operation.md)。
轮播 deterministic fake 覆盖 2、3、4、5 帧、部分失败、重试幂等和恢复；真实 AI、图片网关、认证浏览器
和多进程生产竞态仍未验证。

### Phase 5：清理和发布准备

开始条件：三个用例均已切换且至少一个完整观察周期无旧路径写入。允许修改：清理旧代码、迁移脚本、文档和评测；禁止删除用户数据或直接覆盖运行库。

动作：

1. 删除旧 adapter、死 schema、旧 prompt loader、旧字段 mapper 和误导性测试。
2. 更新代码地图、README、operations；历史 progress 只保留迁移链接，不再作为现状说明。
3. 完成数据库迁移、备份、恢复演练和数据保留策略。
4. 增加质量评测报告和供应商失败分类。

完成门禁：`rg` 找不到旧生产调用者；每个 prompt registry 项有唯一 caller；文档互相不矛盾；全套测试、编译、前端检查和 `git diff --check` 通过。

当前状态（2026-09-04）：Phase 5+ 已完成 canonical seam、参考资料 metadata、脱敏评测/观测、临时备份恢复工具和发布 gate。`GenerationRun`/`RunStorePort` 已接入三个生成分支，轮播旧完成入口无生产 caller；registry governance、254 项 deterministic unittest、Node/compileall/diff gate 均通过。评测 harness 已增加结果硬约束 lint、失败分类聚合和 deterministic fake 独立证据输出；备份恢复已增加 manifest 严格校验、失败清理、项目文件/成功图片引用 smoke 和只读 retention plan。旧 adapter、旧 schema 和 retired prompt 文件仍按保留期和历史读取条件保留；真实历史 scrub、自动调度备份、真实质量报告、认证浏览器和多人生产竞态仍未验证。默认运行库只读 scrub dry-run 发现 `changed_rows=2`、`private_field_occurrences=6`，不得在没有独立备份/恢复变更卡和用户确认时直接 apply。

## 7. 测试和评测体系

### 7.1 必须测试的 seam

- `PromptCompilerPort`：字面替换、缺变量、特殊字符和长度边界；
- `PromptRegistry`：路径、hash、schema、validator、DTO 一致；
- 三个生成 Module 的公开 interface：输入规范化、模型请求、校验、修复、失败分类、持久化结果；
- `TextModelPort` fake：成功、截断、Markdown、错误字段、重复结果、第二批；
- `ImageModelPort` fake：排队、超时、失败、重试、参考图 MIME、会话游标；
- `PublicResultMapper`：递归扫描私有 key；
- SQLite 临时 repository：事务、恢复、幂等、lease 和迁移；
- `StudioApplication` composition root：确认真实路由调用新 Module。

### 7.2 质量评测，而不是只验格式

为每个用例建立固定 JSONL 评测集，字段包括脱敏输入、期望硬约束、质量维度和人工/模型评语。至少评估：

- 任务理解；
- 产品事实与证据；
- 创意机制差异；
- 一眼可懂；
- 可制作性；
- 风险和不确定性标记；
- 第二批相对第一批的真实差异；
- 私有字段不泄露。

提示词改动必须先跑离线评测，再决定是否接入生产。质量阈值和失败样例要进版本控制。

每个生产用例的最小评测协议固定为至少 10 个脱敏 case：schema、数量、事实引用和私有字段硬约束必须 100% 通过；确认事实不得出现编造（0 个 `confirmed` 事实错误）；创意机制差异由两名人工独立评分，平均至少 4/5，明显重复为 0；可制作性和一眼可懂各至少 3/5；第二批与第一批的核心机制重复率必须为 0。成本、延迟和实际模型调用数必须与版本化 baseline/预算比较。模型 judge 只能辅助排序，不能替代硬规则、人工抽查或失败样例复核。

### 7.3 推荐评测流水线

每个用例至少保留一组脱敏固定输入和三组结果：`baseline`、`candidate`、`repair/failure`。评测顺序为：

1. 解析和硬约束 lint；
2. 事实/证据绑定检查；
3. 机制签名和文本相似度检查；
4. 可制作性、受众和清晰度评审；
5. 第二批相对第一批的差异评审；
6. 私有字段和安全扫描；
7. 成本、延迟和实际调用次数统计。

若质量必须增加模型调用，新增 `GenerationPolicy` 版本并对比预算、延迟和失败率；不得直接把调用次数写进旧流程。

## 8. 后续 Agent 的强制检查清单

开始前：

- [ ] 已读本项目要求的四份基础文档和本文档。
- [ ] 已找到真实 composition root 和生产 caller。
- [ ] 已写目标、非目标、验收例子和回滚。
- [ ] 已检查本次变更是否触及现有用户改动。

设计时：

- [ ] 明确 Module、Interface、Seam、Adapter、公开 DTO。
- [ ] 明确新契约替换哪个旧契约，以及删除日期/条件。
- [ ] prompt、input schema、output schema、validator、DTO、persistence 和 UI 已成套设计。
- [ ] 远程依赖使用可替换 port；SQLite 使用临时替身。
- [ ] 失败状态、超时、重试、幂等和恢复已写成可验证规则。

实现后：

- [ ] 先有能变红的定向测试，再写实现。
- [ ] 至少一个测试从生产入口穿过真实 seam。
- [ ] 所有公开接口通过私有字段扫描。
- [ ] 所有提示词文件都有 registry caller；无调用者文件必须删除或标记废弃。
- [ ] 运行 `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`。
- [ ] 明确真实 AI、图片质量、网关和浏览器验证哪些未做。
- [ ] 更新 `progress.md`，必要时更新 `CHANGELOG.md` 和代码地图。

## 9. 文档治理

### 当前事实的优先级

1. 运行代码和 registry；
2. 本文档的“当前真实事实”和已批准 ADR；
3. `CODE_STYLE.md` 与 `AGENTS.md` 的工程规则；
4. `docs/operations.md` 的可执行运维步骤；
5. `progress.md`、`CHANGELOG.md` 的历史记录。

若前两级冲突，停止实现并记录冲突；若历史文档与当前代码冲突，更新历史文档的指针或标记，不新增解释性兼容代码。

建议把本总纲逐步拆为 `docs/ai/00-current-facts.md`、`01-problem-register.md`、`02-target-architecture.md`、`03-migration-plan.md`、`04-prompt-registry.md`、`05-test-and-eval.md`、`06-agent-runbook.md`。拆分时只能通过索引指针引用本文相应章节，不复制同一事实；在拆分完成前，本文件仍是唯一权威。

### ADR 规则

所有会改变业务流程的决定必须写 ADR，并包含：背景、决定、替代方案、影响、迁移、回滚、被替代 ADR。尤其是：

- 文字模型是否参与首帧/后续帧；
- 第二批是否复用会话及如何去重；
- 参考文件是否发送给哪个模型；
- 公开/私有字段边界；
- schema/prompt 版本升级和旧数据读取策略。

### 废弃规则

废弃项必须写清：`deprecated_since`、替代项、仍允许的读取场景、禁止的新调用、删除版本。没有删除条件的“兼容”不允许合入。

## 10. 立即执行顺序

后续实现会话应严格按以下顺序推进：

1. Phase 0 安全止血；
2. Phase 1 PromptRegistry 与 Contract Harness；
3. Phase 2 叙事类；
4. Phase 3 静态展示类；
5. Phase 4 轮播状态机；
6. Phase 5 清理、文档和发布准备。

任何 Agent 如果想跳过阶段，必须在变更卡写出理由、替代验证和风险，不得只在聊天中口头决定。

本总纲的成功标准不是“页面还能生成”，而是：每个 AI 用例都有一个可追溯的契约、一个生产 caller、一个公开 DTO、一个可替换的远程 seam、一套质量评测和一条可以回滚的迁移路径。

## 11. 现状问题矩阵

| 事实证据 | 根因 | 目标 Module/Seam | 修复阶段 | 必须证明 |
|---|---|---|---|---|
| `app.py` 顶层 `APP = StudioApplication()` | composition root 与 import 混在一起 | `create_application(deps)` + 测试 SQLite seam | 0-1 | 导入模块不打开真实 DB；生产仍只有一个 composition root |
| `generation_service.py` 同时有 model client 和 Legacy adapter | 生产路径没有唯一 caller | 三个 use-case Module + `TextModelPort` | 1-2/3/4 | 旧生成函数生产调用数为零后删除 |
| `ai_creative.py` 同时有旧 validator、新 builder、死 first/follow loader | 新旧契约只增不替换 | `ContractRegistry` + `PromptRegistry` | 1 | 每个 active prompt 恰好一个 validator/DTO/caller |
| `schemas.py` 与 v2 prompt 字段不匹配 | schema 没有从生产入口验证 | typed canonical contracts | 1 | production fixture 由同一 validator 通过 |
| `visual_items`、`display_frames`、`generations.items_json` 重复事实 | repository 太浅且双事实 | `RunStorePort` + canonical typed projection | 1/4 | 停止旧写入；迁移有 hash/计数和删除期限 |
| `adopt_visual()` 返回 raw content | 公开 DTO 不在统一 seam | `PublicProjection` | 0 | history/status/adopt/export 私有字段扫描为零 |
| 继续生成同步长请求、15 分钟恢复、无 heartbeat | 操作状态不是 durable operation | `OperationStore` + worker lease | 4 | 202/operation id、重启恢复、旧 worker 不覆盖新 attempt |
| 第二批只复用 cursor、prompt 不变 | 把会话游标误当创新策略 | `VariationContext` + GenerationPolicy | 2/4 | batch 2 prompt/context 可观察且不同 |
| `$unknown` 触发错误，`${task_type}` 被替换 | 编译器二次解释用户数据 | 单次字面 `PromptCompiler` | 0-1 | 特殊字符原样保留 |
| `response_format/max_tokens` 在 chat2api 丢失 | transport seam 没有完整 interface | `TextModelPort` + Chat2Api adapter | 0-1 | adapter 测试检查上游 body，不能只检查工作台 body |
| 参考文件只传名称，游戏资料不进 prompt | ReferenceMaterial seam 缺失，变量契约不全 | `ReferenceMaterialPort` + PromptContext | 1-2/3 | 明确文件是否发送；内容 digest 纳入 fingerprint |
| JPEG 参考图固定标 PNG | 图片 adapter 没有 MIME 事实 | `ImageModelPort`/`ReferenceAsset` | 0/4 | bytes、mime、artifact 原子保存 |
| 生产提示词写“独立首帧会话”，代码却直接用共享草稿 | ADR、prompt、测试三者漂移 | 一次 planner + 图片直出 v1；未来 v2 显式 policy | 3/4 | prompt 文案、测试名称、调用次数一致 |
| 高质量静态 prompt 无 caller | 文档/配置没有 registry 接线 | `visual.static.v1` | 3 | 生产 composition root 只走新静态 contract |

该表不是新的历史日志；发现新问题时补充证据和目标 seam，同时更新对应阶段门禁。不得只在 `progress.md` 追加“已完成”而不更新矩阵。

## 12. Retired 清单和术语

以下项目在迁移完成前不得作为新代码依赖，完成后按 Phase 5 删除或只保留一次性历史读取：

- `LegacyCreativeGenerationAdapter` 及其生产调用；
- `schemas.py` 中与 active production contract 不匹配的 validator；
- 旧视觉字段伪造转换（`subtitle/core_subject/layout/visual_style`）；
- 未登记 registry 的 prompt 文件和任意环境变量 prompt path 覆盖；
- `ai_visual_first_frame_prompt_v1.txt`、`ai_visual_follow_up_prompt_v1.txt` 已按 v1 共享 planner + 图片直出方向列为 retired：只允许历史审计读取，禁止新增 caller；只有单独 ADR 批准 v2 `GenerationPolicy`、完成评测和迁移门禁后才能重新注册新版本，不能原地复活旧文件；
- 误导性测试名称、只测死模块的测试和永久双写/双读分支。

术语固定如下：`GenerationRun` 是一次生成操作；`Batch` 是同一输入定位的第几批；`Scheme` 是一个用户可评审的方案；`FramePlan` 是路线；`FrameAttempt` 是具体图片尝试；`ConversationCursor` 是私有供应商游标；`InternalPlan` 含私有执行信息；`PublicPlan` 不含任何私有字段；`PromptSpec` 是可追溯的 prompt 版本声明；`GenerationPolicy` 是有界调用阶段和预算。

## 13. 旧模块到目标模块映射

| 当前实现 | 目标实现 | 迁移规则 |
|---|---|---|
| `app.py` HTTP handler + 全局 `APP` | `http_api.py`（解析、认证、错误包络）+ `bootstrap.py`（唯一 composition root） | 保留 URL 兼容，不保留全局 import 副作用 |
| `generation_service.py` + `ai_creative.py` | `generation/application.py`、三个 use-case Module、`contracts.py`、`policies.py` | 一个 active use case 只有一个 caller；旧函数只读/导入 |
| `model_client.py` | `TextModelPort` + `Chat2ApiTextAdapter` | provider 能力显式化，测试 fake 穿同一 seam |
| `image_jobs.py` | `ImageModelPort` + `ImageJobCoordinator` + `Chat2ApiImageAdapter` | 不传本地路径；bytes、mime、cursor 由 typed request 表达 |
| `repository.py` | `RunStorePort` + `SqliteRunStore` | row/JSON 映射只在 Adapter；先停止双事实再迁移表 |
| `generations/visual_items/display_frames` 重复事实 | canonical Run/Scheme/Frame/Attempt/Artifact projection | legacy importer 只读，设硬删除日期 |
| 各处 `dict.pop()` 过滤 | `PublicProjector` | history/status/adopt/export 统一使用 deny-by-default projection |

该映射是方向，不要求一次性改名。每个迁移切片必须指出正在替换哪一行旧路径，以及何时证明旧路径生产调用数为零。
