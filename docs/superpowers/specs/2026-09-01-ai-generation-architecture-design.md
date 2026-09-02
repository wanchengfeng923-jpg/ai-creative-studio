# AI 创意生成架构重构设计

- 日期：2026-09-01
- 状态：设计已确认，采用 B 路线
- 适用范围：当前单机版本的内部架构整理
- 基线：以 `progress.md` 的 2026-09-01 最新状态为准

## 1. 决策摘要

本次采用“保留外部接口、重建内部生成模块”的路线：不迁移前端框架，不替换 SQLite，不引入 LangChain、Agent 或新的 AI 编排平台，不改变 `chat2api` 的供应商适配职责。

文字创意生成采用一次用户请求对应一次正常文字 AI 调用的工作流。用户选择的标签、轮播形式和轮次提示都是给 AI 的创意 brief，不是要求 AI 回填的完整配置。AI 在一次调用中理解输入、处理空白信息并直接生成最终创意；服务端只负责输入整理、结构和安全校验、持久化以及图片任务创建。

轮播被建模为“单个创意方案内部的一组 frames”，不再把一批中的方案序号与轮次序号混用。第一阶段每个展示类方案只生成一张首帧参考图，轮次内容先作为文字创意输出；按每轮生成图片属于后续独立变更。

## 2. 背景与当前问题

当前真实调用链为：

```text
static/app.js
  -> POST /api/projects/{id}/generate
  -> StudioApplication.generate()
  -> repository.reserve_generation()
  -> ai_creative.generate_*_creative_recommendations()
  -> chat2api /v1/chat/completions
  -> ChatGPT Web 内部接口
  -> ai_creative.py 解析和校验
  -> repository.complete_*_generation()
  -> 展示类 ImageJobRunner
  -> chat2api /v1/images/jobs
```

目前的主要问题不是功能不能运行，而是职责和业务概念混在一起：

1. `ai_creative.py` 同时承担配置、标签、轮播、提示词、JSON 解析、schema 校验、HTTP 请求、重试、token 统计和日志，文件已经成为多个模块的集合。
2. `app.py` 的 `StudioApplication.generate()` 同时决定创意类型、轮播规则、schema 版本、会话续接、数据库写入和图片任务启动。
3. 叙事类和展示类生成函数重复了模型请求、错误转换、重试和用量统计逻辑。
4. `resolved_tags` 把给 AI 的输入提示错误地变成了 AI 必须返回的结构化答案，导致标签目录和关系校验不断扩大。
5. 轮播校验使用 `items` 的序号索引轮次配置。三套方案和三屏轮播时问题被掩盖，2、4、5 屏时语义不成立。
6. 前端的继承编辑状态、提示词中的原始轮次和 AI 输出的轮次没有一个统一的最终模型。
7. 文字生成的 `pending` 记录没有进程重启后的恢复或超时失效策略。
8. 模型、提示词和 schema 的版本信息没有形成一个完整的生成上下文，旧批次可能与新配置混用。

## 3. 目标与非目标

### 3.1 目标

- 让一次创意生成只有一个清晰的应用接口。
- 让用户输入成为 brief，允许空白，不要求 AI 先执行独立的“补全流程”。
- 让轮播方案、轮播轮次和一批中的多个方案拥有明确的层级关系。
- 让模型供应商协议与创意业务规则通过明确的接口隔离。
- 让 SQLite 成为工作台生成状态的唯一事实源。
- 保持现有网页接口、项目数据和 `chat2api` 可以逐阶段迁移。
- 使每个模块都能用假模型、假仓库或假图片适配器独立测试。

### 3.2 非目标

- 本次不增加登录、项目归属、权限、多人访问或公网部署。
- 本次不迁移或删除现有 SQLite 数据，不改变既有项目和历史的读取方式。
- 本次不把轮播扩展为每个轮次一张图片。
- 本次不引入自主 Agent、多轮工具调用或模型自主执行本地操作。
- 本次不把 `chat2api` 改造成创意领域服务。
- 本次不把隔离的 React 原型接入正式页面。

## 4. 领域词汇

这些词是后续代码、测试和文档的共同语言：

- `Project`：用户正在编辑的项目，保存可继续修改的输入。
- `CreativeInputSnapshot`：某一次生成实际使用的不可变输入快照。
- `CarouselInput`：轮播是否开启、屏数提示、轮播形式提示和可选的逐轮提示。
- `GenerationContext`：输入快照、模型、提示词、schema、标签目录和游戏信息版本的完整生成上下文。
- `GenerationBatch`：一次文字 AI 请求产生的一批叙事或展示方案。
- `Recommendation`：通过结构校验、可供用户查看的叙事或展示创意。
- `CarouselPlan`：一个展示创意方案内部的轮播计划。
- `Frame`：轮播计划中的一个屏幕内容，使用独立的 `index`。
- `VisualItem`：一个展示创意方案对应的首帧图片任务和持久化状态。
- `ImageJobAttempt`：一个 `VisualItem` 的一次图片生成尝试。
- `Adoption`：用户当前采用的方案快照。
- `ModelClient`：文字模型调用接口。
- `ImageProvider`：图片模型或图片网关调用接口。
- `Repository`：持久化适配器，不向上层泄露 SQL 和行结构。

## 5. 目标架构

```text
浏览器
  |
  v
HTTP Adapter: app.py
  |
  v
Application Module: CreativeGenerationService
  |
  +--> CreativeInputNormalizer
  +--> CarouselInputRules
  +--> PromptCompiler
  +--> ModelClient --------------------> chat2api /v1/chat/completions
  +--> RecommendationSchema
  +--> GenerationRepository -----------> SQLite
  |
  +--> ImageJobCoordinator
          |
          +--> ImageProvider ----------> chat2api /v1/images/jobs
```

依赖方向必须保持为：

```text
HTTP -> 应用用例 -> 领域纯模块 -> 接口
                                      ^
                                      |
                    SQLite / 网关 / 图片实现适配器
```

`chat2api` 属于供应商适配器。它可以继续通过 ChatGPT Web 内部接口工作，但不得知道 `展示类`、`叙事类`、`轮播`、`标签` 或 `方案` 这些创意业务词汇。

## 6. 模块设计

### 6.1 `app.py`：HTTP 适配器

职责：

- 解析路径、请求体和文件上传。
- 调用应用模块。
- 把领域错误映射为 HTTP 状态码和现有 JSON 包络。
- 不拼接提示词，不执行 SQL，不解析 AI 返回结构。

保留现有外部接口：

```http
POST /api/projects/{project_id}/generate
GET  /api/projects/{project_id}/history
GET  /api/visual-items/{item_id}/status
POST /api/visual-items/{item_id}/retry
```

### 6.2 `generation_service.py`：生成应用模块

对外只暴露一个主要接口：

```python
class CreativeGenerationService:
    def generate(self, request: CreativeGenerationRequest) -> GenerationOutcome:
        ...
```

它按以下顺序工作：

1. 从项目输入构造 `CreativeInputSnapshot`。
2. 调用输入规范化模块，整理标签和轮播提示。
3. 选择叙事类或展示类的提示词和结果 schema。
4. 生成 `GenerationContext` 和 fingerprint。
5. 向仓库预留一批生成记录。
6. 通过 `ModelClient` 发起一次正常文字调用。
7. 通过对应的 `RecommendationSchema` 校验最终输出。
8. 将成功结果或失败原因写回仓库。
9. 展示类成功后交给 `ImageJobCoordinator` 创建首帧图片任务。
10. 返回公开结果和任务状态。

这个模块拥有流程编排，但不拥有 HTTP、SQL、ChatGPT Web 细节或 HTML 结构。

### 6.3 `generation_models.py`：内部数据类型

建议使用 dataclass 表达应用模块的接口：

```python
@dataclass(frozen=True)
class CreativeGenerationRequest:
    project_id: int
    script_type: str
    task_type: str
    task_description: str
    creative_tags: dict[str, list[str]]
    aspect_ratio: str
    product_evidence_summary: str
    reference_file_names: list[str]
    carousel: "CarouselInput | None"


@dataclass(frozen=True)
class GenerationContext:
    input_snapshot: dict[str, object]
    model: str
    provider: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_version: str
    tag_catalog_version: str
    game_info_version: str
    input_fingerprint: str
```

`GenerationOutcome` 至少包含生成批次、公开创意项、图片任务引用和用量信息。`image_prompt` 只保留在服务端内部对象，不进入公开历史响应。

### 6.4 `carousel.py`：轮播输入规则

轮播模块只处理用户输入，不负责生成 AI 的答案。

输入模型：

```python
@dataclass(frozen=True)
class CarouselInput:
    enabled: bool
    count: int | None
    count_mode: str
    form_hint: str
    frame_hints: tuple[dict[str, object], ...]
```

它负责：

- 将“是/否”规范化为布尔值。
- 将 `2屏` 至 `5屏` 规范化为整数。
- 保留 `AI决定` 作为 `count_mode="ai"`。
- 保留用户填写的轮播形式和逐轮提示。
- 对用户输入做长度、类型和数量限制。

它不负责：

- 要求 AI 返回 `resolved_tags`。
- 让 AI 选择并回填标签目录中的值。
- 把方案序号映射成轮次序号。

前端的 `inherit` 可以继续作为编辑便利，但在发送给模型前只转换成每轮实际提供给 AI 的提示。空白仍然是合法输入。

### 6.5 `prompting.py`：提示词编译

该模块负责：

- 加载版本化提示词模板。
- 检查模板变量是否满足定义。
- 注入任务描述、用户标签、轮播提示、画幅和参考文件名。
- 生成 prompt hash。
- 返回 `CompiledPrompt`。

轮播提示词应表达：

```text
以下内容是用户提供的创意参考，不要求逐项复述或回填。
请直接基于这些参考生成完整轮播方案。
空白项由你根据整体创意自行决定。
```

不能再要求：

```text
空白标签必须由 AI 补全
必须返回 resolved_tags
```

### 6.6 `schemas.py`：结果契约

结果校验按创意类型拆分：

```text
NarrativeRecommendationSchema
VisualRecommendationSchema
CarouselRecommendationSchema
```

校验只关注最终结果是否满足硬性合同。

叙事类：

- 5 个故事。
- 每个故事 2 个钩子。
- 每个钩子 3 个画面建议。

展示类静态方案：

- 3 个方案。
- 字段完整。
- 文本非空且不包含网址。
- `image_prompt` 存在但只留在服务端。

展示类轮播方案：

- 3 个方案。
- 每个方案拥有自己的 `frames`。
- `frames` 的数量为 2 至 5；`count_mode="ai"` 时每个方案独立决定并锁定自己的数量，不要求三套方案统一。
- `frames[].index` 从 1 连续递增。
- 每个 frame 有可展示的创意描述。

不再把 `resolved_tags` 作为输出必填字段，也不再把 AI 选择的标签当成数据库事实。

### 6.7 `model_client.py`：文字模型接口

统一接口：

```python
@dataclass(frozen=True)
class ModelRequest:
    model: str
    messages: list[dict[str, str]]
    response_format: dict[str, str] | None
    max_tokens: int
    conversation_id: str
    parent_message_id: str


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    conversation_id: str
    assistant_message_id: str
    latency_ms: int
```

接口只描述通用模型能力，不描述创意类型。

运行策略：

- 正常生成：一次文字模型调用。
- 返回无法解析：允许一次格式修复重试，但不增加独立的“AI 补全”步骤。
- 上游会话失效：由供应商适配器最多刷新一次会话并重试。
- 语义不满足时不进行无上限自动循环，直接记录失败并返回可操作错误。

### 6.8 `repository.py`：SQLite 适配器

仓库接口表达业务动作，不暴露 SQL：

```python
reserve_generation(context) -> ReservedGeneration
complete_generation(generation_id, result) -> PersistedGeneration
fail_generation(generation_id, failure) -> None
generation_history(query) -> GenerationHistory
```

SQLite 仍然是当前实现，但它是接口的一个适配器。

第一阶段继续使用现有的 `generations`、`visual_items` 和 `adoptions` 表。后续可以为 `generations` 增加 `context_json` 和 `request_id`，这是向后兼容的加法迁移，不覆盖现有数据。

### 6.9 `image_jobs.py`：图片任务协调器

文字结果成功之后，展示类每个方案创建一个首帧图片任务：

```text
VisualItemCreated
  -> submit
  -> queued
  -> generating
  -> success | failed
```

图片模块只消费服务端的 `image_prompt`，不参与文字创意和轮播标签判断。

工作台 SQLite 是图片业务状态的唯一事实源；网关侧任务文件只作为供应商任务适配状态，并通过 `request_id` 实现幂等。

### 6.10 `chat2api`：供应商适配器

`chat2api` 保持自己的职责：

- `/v1/chat/completions` 转换为 ChatGPT Web 请求。
- `/v1/images/jobs` 管理异步图片供应商任务。
- `/v1/session` 管理会话凭据。

它不读取项目数据库，也不解析工作台的创意 schema。工作台和网关之间使用 OpenAI 兼容的通用接口。

## 7. 轮播最终数据模型

一批生成 3 个方案；每个方案内部包含自己的轮次：

```json
{
  "items": [
    {
      "title": "方案一",
      "creative_description": "整体创意说明",
      "carousel": {
        "count": 3,
        "form": "行为 → 结果",
        "frames": [
          {"index": 1, "description": "第一屏画面"},
          {"index": 2, "description": "第二屏画面"},
          {"index": 3, "description": "第三屏画面"}
        ]
      },
      "image_prompt": "只用于首帧参考图"
    }
  ]
}
```

`carousel.count` 是 AI 最终决定或用户输入的屏数；`frames` 的长度必须与它一致。`carousel.form` 可以沿用用户提示，也可以由 AI 在用户未填写时选择，但不需要再产生标签回填对象。

如果用户没有填写某轮提示，AI 可以直接根据整体创意设计该轮内容。服务端不需要把空白改成某个标签。

第一阶段的图片模型为：

```text
一个方案 = 一张首帧参考图
```

如果未来需要每轮一张图，新增 `frame_index` 和轮次图片任务即可，不改变文字生成接口的基本结构。

## 8. 对外 API 契约

### 8.1 工作台 API

保留现有：

```http
POST /api/projects/{id}/generate
```

请求体可以继续为空，因为服务器从项目读取已保存输入。响应建议逐步增加生成元信息：

```json
{
  "success": true,
  "generation": {
    "id": 123,
    "kind": "visual",
    "batch_index": 1,
    "status": "success",
    "input_fingerprint": "...",
    "schema_version": "visual.carousel.v2"
  },
  "items": [],
  "image_jobs": []
}
```

历史接口继续返回当前批次、旧定位批次、剩余批次数和采用关系。`image_prompt` 不进入浏览器响应。

### 8.2 网关 API

网关继续使用 OpenAI 兼容响应，不加入创意业务字段。错误逐步统一为：

```json
{
  "error": {
    "code": "upstream_auth_failed",
    "message": "AI 会话已失效，请重新检测连接",
    "retryable": true
  }
}
```

### 8.3 图片任务幂等

提交图片任务时使用稳定的请求标识：

```text
creative-studio-{visual_item_id}-attempt-{attempt}
```

网关重复收到相同标识时返回原任务，不创建新的供应商任务。

## 9. 状态机与恢复

### 9.1 文字生成

```text
reserved/pending -> success
                  -> failed
                  -> expired
```

`expired` 用于进程重启后或超过明确超时时间的 pending 记录。它不与成功批次混淆，也不会永久阻塞下一次生成。

### 9.2 图片任务

```text
queued -> generating -> success
                   \-> failed -> queued  (用户重试)
```

每次状态改变都带 `attempt` 条件，避免旧线程覆盖新尝试的结果。

## 10. 版本与指纹

一次生成的 fingerprint 必须同时受到以下信息影响：

```json
{
  "script_type": "展示类",
  "creative_input": "规范化后的输入快照",
  "model": "gpt-5-6-mini",
  "provider": "chatgpt-web",
  "prompt_id": "visual-carousel",
  "prompt_version": "visual-carousel-v1",
  "prompt_hash": "...",
  "schema_version": "visual.carousel.v2",
  "tag_catalog_version": "tags-2026-08-31-v1",
  "game_info_version": "game-v2"
}
```

这样提示词、模型或结果合同改变时，会自然形成新的生成上下文。旧历史仍可读取，但不会错误地与新输入共享两批限制和续聊状态。

## 11. 错误处理

错误必须区分输入、状态、配置和上游依赖：

| 错误类别 | HTTP 状态 | 说明 |
|---|---:|---|
| 输入字段不合法 | 422 | 用户需要修改输入 |
| 资源不存在 | 404 | 项目或图片任务不存在 |
| 当前状态冲突 | 409 | 已有 pending 或已达到批次限制 |
| AI 配置错误 | 500 | 本机配置需要修复 |
| AI 网关不可用 | 502 | 上游请求失败 |
| AI 排队超时 | 503 | 稍后重试 |
| AI 输出结构无效 | 502 | 记录脱敏诊断，不暴露完整模型响应 |

前端仍使用现有 `{"success": false, "error": "..."}` 包络；内部可以先使用异常类型，再由 `app.py` 统一映射。

## 12. 测试设计

### 12.1 纯模块单测

- 输入规范化：空字段、长度、枚举和旧项目标签兼容。
- 轮播输入：2、3、4、5 屏，AI 决定，空白轮次提示，继承提示展开。
- 提示词编译：所有占位符、空提示、轮播 hint 注入和 prompt hash。
- schema：叙事类、静态展示类、轮播展示类的数量和字段校验。
- fingerprint：模型、提示词、schema 和输入变化都会改变指纹。

### 12.2 应用模块契约测试

使用假 `ModelClient`、假 `GenerationRepository` 和假 `ImageProvider` 验证：

- 一次正常请求只有一次文字调用。
- 空白输入不会触发独立的 AI 补全调用。
- 格式失败最多一次修复重试。
- 展示类成功后创建 3 个首帧图片任务。
- 叙事类不会创建图片任务。
- 生成失败会释放 pending 状态。

### 12.3 接口和恢复测试

- API 成功、输入错误、资源不存在、状态冲突和网关不可用。
- 进程重启后 pending 文字记录不会永久阻塞生成。
- 图片任务重复提交保持幂等。
- 失败图片单项重试不会覆盖其他图片。

### 12.4 AI 评估

真实 AI 评估仍使用脱敏、固定样例。至少检查：

- JSON 解析成功率。
- 叙事类和展示类数量约束。
- 轮播 frames 连续性、每套方案独立的 2 至 5 屏数量和统一屏数模式下的固定数量。
- 用户已填输入是否被正确参考。
- 未填输入是否可以自然补足，而不是输出空结果。

## 13. 分阶段迁移

### 阶段 0：冻结合同

- 建立本设计对应的变更卡。
- 固定当前 API、数据库表和现有页面行为。
- 补充轮播输入与输出的失败样例。

回滚：不修改代码，删除设计变更卡即可。

### 阶段 1：修正轮播模型

- 在 `carousel.py` 中形成唯一的 `CarouselInput` 规范化实现。
- 移除 AI 输出必须包含 `resolved_tags` 的要求。
- 将轮播结果改为每个方案自己的 `frames`。
- 修正提示词使用展开后的用户提示，空白保持为空。
- 保持现有 API 和旧结果读取兼容。

回滚：保留兼容读取器，恢复旧 schema 版本的生成路径；不删除旧历史。

### 阶段 2：引入生成应用模块

- 新增 `generation_models.py` 和 `generation_service.py`。
- 让 `app.py` 通过新模块生成，暂时保留旧函数作为适配器。
- 把 fingerprint 统一到一个实现。

回滚：将 `app.py` 切回旧生成入口，数据库无需恢复。

### 阶段 3：抽出提示词、schema 和模型适配器

- 从 `ai_creative.py` 抽出 `prompting.py`、`schemas.py`、`model_client.py`。
- 叙事类和展示类共用模型请求实现。
- 保持提示词版本和输出字段的兼容适配。

回滚：保留旧 `ai_creative.py` 入口和旧 schema 读取，不切换新应用模块即可。

### 阶段 4：增强生成上下文和恢复

- 为 `generations` 增加可选 `context_json`、`request_id` 或等价记录。
- 增加 pending 超时和重启恢复。
- 统一错误类别、request_id 和脱敏日志。

回滚：新增字段是加法迁移，停止读取新字段即可；不执行删除或覆盖数据的回滚。

### 阶段 5：整理图片适配器

- 保持一个方案一张首帧图片。
- 统一图片任务幂等键和网关状态映射。
- 只有经过单独需求确认后，才评估按轮次生成图片。

回滚：恢复旧图片调度器，保留已经完成的图片文件和数据库状态。

## 14. 验收标准

设计落地后应满足：

1. 用户点击一次生成即可得到最终文字创意，不需要先执行 AI 补全接口。
2. 正常情况下，一次生成只调用一次文字 AI。
3. 轮播输入可以为空或部分填写，AI 仍能输出完整方案。
4. 3 个方案和 2～5 个轮次在数据结构上完全分离。
5. 轮播 AI 结果不再要求 `resolved_tags`。
6. 展示类每个方案默认只有一个首帧图片任务。
7. `chat2api` 不包含任何创意业务判断。
8. 输入变化、提示词变化、模型变化或 schema 变化会形成不同生成上下文。
9. 文字生成和图片任务的失败、重试、恢复状态可被单独解释。
10. 现有工作台 API、项目数据和历史读取不会因内部拆分而失效。

## 15. 当前明确不做的决策

- 不把 AI 的隐式推理过程写入数据库或返回浏览器。
- 不把 AI 自己选出的标签当作用户已确认的标签。
- 不让前端维护第二套生成事实状态。
- 不为了“看起来更智能”增加默认多轮 AI 链式调用。
- 不在本次重构中处理认证、权限、多人协作、内网部署和公网安全。
