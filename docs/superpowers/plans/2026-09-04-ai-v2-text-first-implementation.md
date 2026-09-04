# AI v2 文字优先与按需生图正式实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改写旧 AI 链路的前提下，建立一条独立的 AI v2 生产链路：三字段输入、文字先返回、图片按需生成、轮播按顺序续图，并可在通过评测后从独立入口切换到正式页面。

**Architecture:** AI v2 位于 `src/creative_studio/ai_v2/`，拥有自己的输入标准化、版本化 schema、Prompt registry、三类文字用例、公开投影、会话管理、SQLite 表和图片 worker。它只依赖标准库与明确的中立供应商传输端口，不导入 `ai_creative.py`、`generation_service.py`、`carousel_visual.py`、`static_visual.py`、旧 `prompt_registry.py`、旧 `public_projection.py` 或旧 `image_jobs.py`。正式入口先使用独立 `/api/v2` API 和 `/ai-v2/` 页面；旧入口在整个观察期保持冻结，最终切换只发生在上层入口选择处。

**Tech Stack:** Python 标准库、SQLite、原生 HTML/CSS/JavaScript、`requests` 仅用于 v2 供应商 Adapter；不新增前端框架，不让 v2 依赖旧业务 Module。版本化 JSON Schema 文件由 v2 自有的严格 schema runner 校验，避免为一次结构校验引入未经评估的依赖。

**Spec:** `docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`

## Global Constraints

- 旧 AI 冻结：本计划的 Task 0-17 不修改旧 Prompt 正文、旧 validator、旧结果字典、旧轮播编排或旧图片 worker 的业务行为。
- 新 AI 零引用、零回退、零双写/双读、零兼容串联；新代码不得导入旧 AI 业务模块，也不得在失败时回退旧链路。
- 中立基础设施例外只允许使用标准库、HTTP 传输和无创意语义的供应商协议；若现有模块含业务语义，v2 重新定义自己的 Adapter。
- v2 输入 body 严格只有 `task_description`、`aspect_ratio`、`creative_tags`；产品证据、补充资料、参考文件不进入 v2。
- `creative_tags` 是开放映射，不维护后端标签白名单；空组、空值和重复值在入口清除，未选择的标签组不进入 Prompt。
- 用例类型由已授权的项目状态和 v2 路由决定，不作为第四个模型输入字段；展示类轮播控制仍作为已选标签保留。
- 文字生成同步返回；一批文字只发起一次模型调用，结构错误直接失败，不做隐藏格式修复调用；用户重试才创建新的文字会话。
- 同一定位最多两批；每批创建新文字会话；第二批不复用第一批会话、不注入第一批摘要、不强制声明差异。
- 静态每案最多成功一张图片；轮播每案只有一个图片会话，所有帧在该会话中按顺序生成；一次图片按钮点击最多推进一张，不预取或自动推进后续帧。
- 图片状态只允许 `pending`、`generating`、`success`、`failed`；成功锁定，失败可重试；重试先对账原图片会话，不能盲目创建第二个会话。
- 网页超时、连接断开或 5xx 只能标记本地结果未知，不能直接判定供应商失败；对账返回未知或供应商不可用时不创建新 attempt，只有明确终态失败才在原图片会话内创建同一帧的新 attempt。
- 浏览器只能收到 v2 `PublicResult`；`execution`、Prompt、会话游标、网关 job id、本地路径、完整模型响应和堆栈永不进入公开 DTO。
- v2 使用 `ai_v2_*` 自有表和自有图片目录；不读取旧生成结果来组成 v2 页面，不向旧表双写。
- 每个任务建议使用一个独立会话窗口；一个窗口只修改本任务列出的文件。并行任务不得编辑同一文件。
- 未取得用户单独授权前，不发起真实 AI/图片请求，不修改真实数据库内容，不修改 `chat2api/.env`，不部署，不开放局域网或公网。

## 1. 任务地图与依赖

### 1.1 文件责任地图

| 责任域 | 新文件 | 允许触及的现有文件 | 禁止依赖 |
|---|---|---|---|
| v2 边界 | `src/creative_studio/ai_v2/boundary.py` | 无 | 全部旧 AI 业务模块 |
| 输入契约 | `src/creative_studio/ai_v2/input_contract.py` | 无 | `ai_creative.normalize_creative_tags` |
| Schema | `src/creative_studio/ai_v2/schema.py`、`config/ai_v2/schemas/` | 无 | `schemas.py` |
| Prompt | `src/creative_studio/ai_v2/prompt_registry.py`、`prompting.py`、`config/ai_v2/prompts/` | 无 | 旧 `prompt_registry.py`、旧 loader |
| 模型与会话 | `src/creative_studio/ai_v2/model_ports.py`、`session.py`、`adapters/` | 无 | `model_client.py`、`image_jobs.py` |
| 存储 | `src/creative_studio/ai_v2/store.py`、`migrations.py` | `app.py` 仅在组合根注入 DB 路径 | `repository.py` 的旧 AI 写入方法 |
| 文字用例 | `src/creative_studio/ai_v2/narrative.py`、`static.py`、`carousel.py` | 无 | 旧三类 validator 和 builder |
| 图片状态机 | `src/creative_studio/ai_v2/image_state.py`、`image_worker.py` | 无 | `CarouselOperationCoordinator`、`ImageJobRunner` |
| 公开投影 | `src/creative_studio/ai_v2/projection.py` | 无 | 旧 `PublicResultMapper` |
| API | `src/creative_studio/ai_v2/http_api.py` | `app.py` 只增加 v2 路由挂载 | 旧生成 handler 内联逻辑 |
| 前端 | `static/ai-v2/index.html`、`app.js`、`styles.css` | 最终切换时才触及 `static/index.html` | 旧 `static/app.js` 结果状态 |
| 评测 | `config/evals/ai_v2/`、`tests/test_ai_v2_*.py` | 无 | 真实凭据和真实运行数据 |

### 1.2 并行波次与优先级

| 优先级 | 波次 | 可并行任务 | 开始条件 | 说明 |
|---|---|---|---|---|
| P0 | 冻结 | Task 0 | 无 | 先建立变更卡、ADR 和回滚基线 |
| P0.1 | 边界 | Task 1 | Task 0 完成 | 这是所有代码任务的硬前置 |
| P1 | 基础契约 | Task 2、Task 3、Task 6 | Task 1 完成 | 输入、Schema、会话端口文件互不重叠；Task 6 只依赖 Task 0 的 ADR |
| P1.1 | Prompt 设计 | Task 4 | Task 2、Task 3 完成 | 先固定三字段序列化和输出硬约束，再写 Prompt 正文 |
| P2 | Prompt 实现 | Task 5 | Task 4 用户评审通过；Task 3 完成 | registry 与单次编译器独占 v2 Prompt 文件 |
| P2 | 存储实现 | Task 7 | Task 2、Task 6 完成 | 可与 Task 5 并行；只创建 `ai_v2_*` 表并使用 Task 6 的 typed session |
| P2.1 | 公开投影 | Task 8 | Task 3、Task 7 完成 | 只依赖 v2 schema/store，不读取旧 mapper |
| P3 | 三类文字用例 | Task 9A、Task 9B、Task 9C | Task 5/6/7 完成 | 叙事、静态、轮播各自独占文件 |
| P3 | 图片执行 | Task 10、Task 11 | Task 6/7 和至少 Task 9B/9C 完成 | 先状态机，后 worker/供应商对账 |
| P4 | API 组合根 | Task 12 | Task 9、10、11 完成 | 只挂载 `/api/v2`，旧入口保持冻结 |
| P4 | v2 前端 | Task 13 | Task 8 完成 | 先用冻结的 public DTO fixture；不得等待或导入 API 实现内部模块 |
| P4 | 评测与门禁 | Task 14 | Task 9-13 有可运行 seam | 不通过不得切换入口 |
| P5 | 采用与切换 | Task 15、Task 16 | Task 14 通过，用户批准切换 | 只能串行；不能与 API/前端并行 |
| P6 | 观察与清理 | Task 17 | Task 16 完成一个观察周期 | 旧 AI 删除是独立后续变更，不在本计划直接执行 |

推荐执行顺序是 `0 → 1 → (2/3/6) → 4 → (5/7) → 8 → (9A/9B/9C) → 10 → 11 → (12/13) → 14 → [15] → 16 → 17`。Task 13 在 Task 8 后即可用冻结的 public DTO fixture 开工，Task 12 完成后再接真实 API；Task 15 默认延后，不阻塞第一次 v2 切换，只有用户另行确认采用功能时才执行。使用多个会话窗口时，只并行同一波次中明确列出的任务；任何任务失败时，先修复该任务，不提前启动依赖任务。

## 2. 任务详情

### Task 0: 冻结点、变更卡与会话 ADR

**Files:**
- Create: `.scratch/ai-v2-text-first-implementation/spec.md`
- Create: `docs/adr/0005-ai-v2-boundary-and-session-policy.md`
- Modify: `docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`

**Dependencies:** 无。建议优先级 P0，必须单独一个会话完成。

**Interfaces:**
- Consumes: 已批准的 v2 设计稿、当前工作树状态、用户确认的四项边界和会话模型。
- Produces: 可回滚冻结点、正式变更卡、会话与重试 ADR，供所有后续任务引用。

- [ ] **Step 1: 记录当前基线**

在变更卡中记录当前分支、HEAD、工作树脏文件列表，以及不得覆盖的用户改动；不执行 `git reset`、`git checkout` 或批量清理。

- [ ] **Step 2: 写入变更卡边界**

变更卡必须明确目标、非目标、影响目录、三字段输入、同步文字、异步图片、两批限制、旧新零引用、回滚和验收例子。

- [ ] **Step 3: 写入会话 ADR**

ADR 固定以下决定：每批一个新文字会话；每个展示方案最多一个图片会话；轮播所有帧复用该方案图片会话；重试先查本地尝试和供应商会话；只有明确失败才在原方案图片会话内发送新的尝试；不做格式修复调用。

- [ ] **Step 4: 更新设计稿的决策索引**

在设计稿中链接变更卡和 ADR，并保留“Prompt 正文需单独评审”的限制。

- [ ] **Step 5: 验证文档**

运行 `git diff --check`，确认新增文档没有把正式 AI 接入授权误写成已批准。

### Task 1: 建立 v2 命名空间和零引用守卫

**Files:**
- Create: `src/creative_studio/ai_v2/__init__.py`
- Create: `src/creative_studio/ai_v2/boundary.py`
- Create: `tests/test_ai_v2_boundary.py`

**Dependencies:** Task 0。

**Interfaces:**
- Consumes: v2 允许依赖清单和旧模块禁用清单。
- Produces: `assert_ai_v2_boundary(root: Path) -> None`，在测试和发布 gate 中扫描 v2 源码的 AST import、字符串路径和路由引用。

- [ ] **Step 1: 写失败测试**

测试向临时 v2 文件写入 `from creative_studio.ai_creative import ...`、`import generation_service` 和旧 API 字符串，断言守卫报告具体文件和违规模块。

- [ ] **Step 2: 实现扫描器**

只扫描 `src/creative_studio/ai_v2`、`static/ai-v2` 和 `config/ai_v2`；允许 `typing`、`dataclasses`、`json`、`sqlite3`、`requests` 等中立依赖；遇到旧业务模块、旧路由或旧表名立即失败。

- [ ] **Step 3: 加入运行时自检入口**

导出 `assert_ai_v2_boundary`，不在导入时打开数据库或发网络请求。

- [ ] **Step 4: 验证**

运行 `python -m unittest tests.test_ai_v2_boundary -v` 和 `python -m compileall -q src/creative_studio/ai_v2`。

### Task 2: 三字段输入标准化与批次指纹

**Files:**
- Create: `src/creative_studio/ai_v2/input_contract.py`
- Create: `tests/test_ai_v2_input_contract.py`

**Dependencies:** Task 1。

**Interfaces:**
- Consumes: HTTP body和已授权项目的脚本类型/轮播状态。
- Produces:

```python
@dataclass(frozen=True)
class AiV2Input:
    task_description: str
    aspect_ratio: str
    creative_tags: Mapping[str, tuple[str, ...]]

def normalize_input(body: Mapping[str, Any]) -> AiV2Input:
    raise NotImplementedError

def resolve_use_case(project_kind: str, tags: Mapping[str, Sequence[str]]) -> Literal["narrative", "static", "carousel"]:
    raise NotImplementedError

def fingerprint(value: AiV2Input, use_case: str, *, prompt_version: str) -> str:
    raise NotImplementedError
```

- [ ] **Step 1: 写失败测试**

覆盖未知顶层字段、空任务说明、非法画幅、空标签组、重复标签、空字符串标签、未选择标签缺失、轮播标签保留、产品证据/参考文件被拒绝以及同输入稳定 fingerprint。

- [ ] **Step 2: 实现标准化**

只读取三个顶层字段；任务说明裁剪并限制长度；画幅只允许现有 `16:9`、`9:16`；标签组名称保持开放，值只接受字符串序列，去空、去重、排序只用于 fingerprint，不改变发送顺序事实。

- [ ] **Step 3: 实现用例判定**

叙事项目进入 `narrative`；展示类且 `visual_carousel=是` 进入 `carousel`；其他展示类进入 `static`。轮播数量和形式只从已选标签读取，不创建第四个模型输入字段。

- [ ] **Step 4: 验证**

运行定向输入测试；确认测试夹具中没有读取旧 `normalize_creative_tags`，并执行 v2 边界守卫。

### Task 3: 版本化 JSON Schema 与无依赖 schema runner

**Files:**
- Create: `src/creative_studio/ai_v2/schema.py`
- Create: `config/ai_v2/schemas/narrative-text-v1.json`
- Create: `config/ai_v2/schemas/static-text-v1.json`
- Create: `config/ai_v2/schemas/carousel-text-v1.json`
- Create: `tests/test_ai_v2_schema.py`

**Dependencies:** Task 1。

**Interfaces:**
- Consumes: 设计稿中的三类输出轮廓和数量/索引不变量。
- Produces:

```python
class SchemaViolation(ValueError):
    field_path: str
    reason_code: str

def load_schema(schema_id: str, version: str) -> Mapping[str, Any]:
    raise NotImplementedError

def validate_json(value: Any, schema: Mapping[str, Any]) -> None:
    raise NotImplementedError
```

- [ ] **Step 1: 写失败测试**

测试缺字段、额外字段、错误类型、数量不符、轮播索引断裂、execution 缺 Prompt、静态多于一条 Prompt 和叙事钩子/场景数量错误。

- [ ] **Step 2: 实现 schema runner**

实现本项目需要的 `type`、`required`、`properties`、`additionalProperties`、`items`、`minItems`、`maxItems`、`enum` 和 `minLength`；所有失败都返回 JSON path 和稳定 `reason_code`。

- [ ] **Step 3: 写入三份 schema**

叙事固定 `items=5`、每项两个 hooks、每 hook 三个 scenes；静态固定 `items=3` 和一个 `execution.image_prompt`；轮播固定 `items=3`、frames 与 image_prompts 数量/索引一致，帧数按固定标签或 2-5 的 AI 决定范围校验。

- [ ] **Step 4: 验证**

运行 `python -m unittest tests.test_ai_v2_schema -v`；schema 文件只读加载，不执行任何字符串内容。

### Task 4: Prompt 专项设计与评测资产

**Files:**
- Create: `docs/ai/ai-v2-prompt-design.md`
- Create: `config/evals/ai_v2/prompt-cases.jsonl`
- Create: `config/evals/ai_v2/expected-hard-constraints.json`

**Dependencies:** Task 2、Task 3。

**Interfaces:**
- Consumes: 三字段输入、三份 schema、用户明确的公开/内部字段边界。
- Produces: 经过用户确认后才允许进入 registry 的三份 PromptSpec 设计和至少 10 个脱敏评测 case。

- [ ] **Step 1: 定义每个用例的唯一任务**

分别写清叙事 5×2×3、静态 3 案+一条私有 image prompt、轮播 3 案+完整 frames/continuity/image prompts；不引入 evidence、asset_plan、risk 等未批准字段。

- [ ] **Step 2: 定义数据区序列化**

固定 `task_description`、`aspect_ratio`、`creative_tags` 的标签顺序和空对象表达；用户内容只进入数据区，不能再次被模板解析。

- [ ] **Step 3: 定义一致性规则**

写明公开画面描述是创意事实，私有 Prompt 只补充构图、镜头、光照、材质和负面限制，不得增加人物、产品事实或剧情；轮播后续 Prompt 必须实现对应帧描述。

- [ ] **Step 4: 准备评测 case**

每类至少 10 个脱敏输入/输出夹具，覆盖空标签、轮播 2/3/4/5 屏、模型额外字段、私有字段泄露、重复方案、空描述和供应商失败响应。

- [ ] **Step 5: 用户评审门禁**

Prompt 正文在用户确认前保持为候选，不创建 production caller；评测资产通过结构 lint 后，才进入 Task 5。

### Task 5: v2 Prompt registry 与单次编译器

**Files:**
- Create: `src/creative_studio/ai_v2/prompt_registry.py`
- Create: `src/creative_studio/ai_v2/prompting.py`
- Create: `config/ai_v2/prompts/registry.json`
- Create: `config/ai_v2/prompts/narrative-text-v1.txt`
- Create: `config/ai_v2/prompts/static-text-v1.txt`
- Create: `config/ai_v2/prompts/carousel-text-v1.txt`
- Create: `tests/test_ai_v2_prompt_registry.py`

**Dependencies:** Task 4 用户评审通过、Task 3。

**Interfaces:**
- Consumes: Task 4 已确认的 PromptSpec、schema id/version 和三字段输入。
- Produces:

```python
@dataclass(frozen=True)
class AiV2PromptSpec:
    prompt_id: str
    version: str
    template_sha256: str
    input_schema: str
    output_schema: str
    max_model_calls: int

class AiV2PromptRegistry:
    def get(self, prompt_id: str, version: str) -> AiV2PromptSpec:
        raise NotImplementedError

def compile_prompt(spec: AiV2PromptSpec, values: Mapping[str, str]) -> str:
    raise NotImplementedError
```

- [ ] **Step 1: 写失败测试**

覆盖缺文件、hash 不匹配、未知变量、缺变量、插入值包含 `{{x}}`、`${x}`、美元符号、换行和超长输入；插入值中的模板片段必须保持字面文本。

- [ ] **Step 2: 实现独立 registry**

registry 只接受 `config/ai_v2/prompts/registry.json` 中的静态声明，production PromptSpec 必须绑定 v2 schema 和 caller 名称；禁止动态 import 和环境变量覆盖。

- [ ] **Step 3: 实现单次编译**

只支持 `{{name}}`，一次扫描、一次字面替换；传入未知值或模板声明缺失时 fail closed。

- [ ] **Step 4: 验证**

运行 registry 定向测试、Task 1 边界守卫和 prompt case schema lint；确认新 registry 不读取旧 registry。

### Task 6: 文字/图片端口与会话策略

**Files:**
- Create: `src/creative_studio/ai_v2/model_ports.py`
- Create: `src/creative_studio/ai_v2/session.py`
- Create: `src/creative_studio/ai_v2/fakes.py`
- Create: `tests/test_ai_v2_session.py`

**Dependencies:** Task 0、Task 1。

**Interfaces:**
- Consumes: Task 0 会话 ADR、模型请求输入和供应商能力。
- Produces:

```python
@dataclass(frozen=True)
class TextSession:
    session_id: str
    conversation_id: str
    parent_message_id: str

@dataclass(frozen=True)
class ImageSessionCursor:
    provider: str
    conversation_id: str
    parent_message_id: str
    revision: int

@dataclass(frozen=True)
class ImageArtifact:
    content: bytes
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    sha256: str

@dataclass(frozen=True)
class ReconcileResult:
    state: Literal["success", "working", "terminal_failure", "unknown"]
    provider_job_id: str | None
    cursor: ImageSessionCursor | None
    artifact: ImageArtifact | None
    error_code: str | None

@dataclass(frozen=True)
class TextRequest:
    prompt: str
    prompt_id: str
    schema_version: str
    model: str
    idempotency_key: str

@dataclass(frozen=True)
class TextResponse:
    raw_text: str
    session: TextSession
    usage_source: Literal["exact", "estimated", "unavailable"]

@dataclass(frozen=True)
class ImageRequest:
    scheme_version: str
    frame_index: int
    prompt: str
    image_session_key: str
    request_key: str
    aspect_ratio: str
    reference_artifact: ImageArtifact | None

@dataclass(frozen=True)
class ImageContinuation:
    request: ImageRequest
    cursor: ImageSessionCursor

@dataclass(frozen=True)
class ImageSubmission:
    state: Literal["working", "success", "terminal_failure", "unknown"]
    provider_job_id: str | None
    cursor: ImageSessionCursor | None
    artifact: ImageArtifact | None
    error_code: str | None

@dataclass(frozen=True)
class ReconcileRequest:
    image_session_key: str
    request_key: str
    cursor: ImageSessionCursor | None
    provider_job_id: str | None

class TextModelPort(Protocol):
    def start_text(self, request: TextRequest) -> TextResponse: ...

class ImageModelPort(Protocol):
    def start_image_session(self, request: ImageRequest) -> ImageSubmission: ...
    def continue_image_session(self, request: ImageContinuation) -> ImageSubmission: ...
    def reconcile(self, request: ReconcileRequest) -> ReconcileResult: ...
```

- [ ] **Step 1: 写失败测试**

测试第二批没有旧文字会话；三个展示方案生成图片时只创建 3 个图片会话；轮播同一方案第 2/3 张复用同一图片会话；每次点击只推进一帧；重试先调用 `reconcile`，且对账未知时不创建新 attempt 或新会话。

- [ ] **Step 2: 定义 typed request**

文字请求只含 v2 编译后的 Prompt 和模型参数；图片请求含方案版本、当前帧 Prompt、前一张成功图片 bytes/MIME 和私有会话游标，不暴露给浏览器。为图片端口固定两个键：`image_session_key = (run_id, scheme_id)`，`request_key = (scheme_version, frame_index)`；attempt 序号不参与 request key，只用于区分同一帧的明确失败重试。

- [ ] **Step 3: 实现确定性 fake**

fake 记录会话创建、继续、对账和返回状态，不联网、不读取环境凭据；可编程为成功、工作中、终态失败和供应商已成功但本地未知，以及查询未知/不可用。

- [ ] **Step 4: 验证**

运行 session 定向测试并扫描 fake 的 import；确认没有旧 `ModelClient`、旧 `GptWebImageClient` 或旧 `ImageJobRunner` 依赖。

### Task 7: v2 SQLite 存储与 additive migration

**Files:**
- Create: `src/creative_studio/ai_v2/migrations.py`
- Create: `src/creative_studio/ai_v2/store.py`
- Create: `tests/test_ai_v2_store.py`

**Dependencies:** Task 2、Task 6。

**Interfaces:**
- Consumes: v2 canonical contract、session cursor、image state transitions。
- Produces:

```python
@dataclass(frozen=True)
class RunRecord:
    run_id: int
    project_id: int
    use_case: Literal["narrative", "static", "carousel"]
    batch_index: int
    input_fingerprint: str

@dataclass(frozen=True)
class ImageAttempt:
    attempt_id: int
    scheme_id: int
    frame_index: int
    request_key: str
    attempt_no: int
    status: Literal["pending", "generating", "success", "failed"]
    image_session_id: int
    provider_job_id: str | None

@dataclass(frozen=True)
class ImageAttemptView:
    attempt_id: int
    status: Literal["pending", "generating", "success", "failed"]
    image_url: str | None
    error_code: str | None

@dataclass(frozen=True)
class ImageSessionRecord:
    session_id: int
    scheme_id: int
    session_key: str
    cursor: ImageSessionCursor | None
    provider_job_id: str | None

class AiV2Store(Protocol):
    def reserve_run(self, project_id: int, use_case: str, input_fingerprint: str, batch_index: int) -> RunRecord:
        raise NotImplementedError
    def save_text_result(self, run_id: int, canonical: Mapping[str, Any], text_session: TextSession) -> None:
        raise NotImplementedError
    def read_public_run(self, project_id: int, run_id: int) -> Mapping[str, Any]:
        raise NotImplementedError
    def find_image_session(self, scheme_id: int, session_key: str) -> ImageSessionRecord | None:
        raise NotImplementedError
    def find_image_attempt(self, scheme_id: int, frame_index: int, request_key: str) -> ImageAttempt | None:
        raise NotImplementedError
    def reserve_image_attempt(self, scheme_id: int, frame_index: int, request_key: str) -> ImageAttempt:
        raise NotImplementedError
    def reconcile_image_attempt(self, attempt_id: int, result: ReconcileResult) -> None:
        raise NotImplementedError
    def complete_image_attempt_atomic(self, attempt_id: int, artifact: ImageArtifact, cursor: ImageSessionCursor) -> None:
        raise NotImplementedError
    def fail_image_attempt(self, attempt_id: int, error_code: str, retryable: bool) -> None:
        raise NotImplementedError
```

- [ ] **Step 1: 写失败测试**

测试新库首次迁移、重复迁移、事务回滚、失败文字记录保留、两批限制、方案版本锁定、轮播顺序 guard、图片尝试幂等和并发条件更新；同一 request key 重复读取原 attempt，失败 attempt 的 retry 序号递增但不新增 image session；本地 attempt 缺失但 image session 已存在时可以恢复孤儿任务。

- [ ] **Step 2: 定义 v2 表**

创建 `ai_v2_runs`、`ai_v2_schemes`、`ai_v2_frames`、`ai_v2_image_sessions`、`ai_v2_image_attempts`、`ai_v2_artifacts`；所有表只通过 v2 store 访问。`ai_v2_image_sessions` 对 `(scheme_id, session_key)` 唯一，`execution_json`、cursor、job id 和本地路径只在内部表中。`request_key` 是同一逻辑帧跨重试复用的查找键，不做全局唯一；数据库唯一约束使用 `(scheme_id, frame_index, attempt_no)`，并为 `request_key` 建索引。

- [ ] **Step 3: 实现 additive migration**

迁移只执行 `CREATE TABLE IF NOT EXISTS` 和 v2 索引，不改旧表、不删除旧列、不重建旧数据；数据库路径由组合根显式注入。

- [ ] **Step 4: 实现原子方法**

图片成功时在同一事务提交 artifact、frame 状态、attempt 状态、会话 cursor revision 和方案进度；旧 attempt 或旧 cursor revision 不得覆盖新状态。`find_image_attempt` 返回该 request key 的最新 attempt；`reserve_image_attempt` 只有在最新 attempt 为明确 `failed` 且调用方已完成对账时才递增 `attempt_no`，并用条件更新防止并发重复创建。

- [ ] **Step 5: 验证**

所有测试使用临时 SQLite；执行 `python -m unittest tests.test_ai_v2_store -v` 和 v2 表名扫描，确认没有写入 `generations`、`visual_items`、`display_frames` 或 `carousel_operations`。

### Task 8: v2 公开投影

**Files:**
- Create: `src/creative_studio/ai_v2/projection.py`
- Create: `tests/test_ai_v2_projection.py`

**Dependencies:** Task 3、Task 7。

**Interfaces:**
- Consumes: v2 canonical result and image public state。
- Produces:

```python
def public_run(run: Mapping[str, Any]) -> dict[str, Any]:
    raise NotImplementedError

def public_scheme(scheme: Mapping[str, Any]) -> dict[str, Any]:
    raise NotImplementedError

def public_image_state(attempt: Mapping[str, Any]) -> dict[str, Any]:
    raise NotImplementedError
```

- [ ] **Step 1: 写失败测试**

向 canonical 对象注入 `execution`、Prompt、conversation cursor、job id、路径、完整响应、内部错误和未知字段，断言公开对象完全不包含这些键及其递归后代。

- [ ] **Step 2: 实现从空对象构建 DTO**

叙事只复制 `story/hooks/scenes`；静态只复制 `title/core_idea/ad_copy/image_description` 和图片状态；轮播只复制 `title/core_idea/ad_copy/frames` 和图片状态；不使用 `dict.copy()` 后删除私有键。

- [ ] **Step 3: 实现状态公开映射**

公开只返回 `pending/generating/success/failed`、安全错误 code、attempt 和 operation/attempt id；不返回供应商会话或本地路径。

- [ ] **Step 4: 验证**

执行递归私有字段扫描和 schema 对照，确保 DTO 不依赖旧 `PublicResultMapper`。

### Task 9A: 叙事文字用例

**Files:**
- Create: `src/creative_studio/ai_v2/narrative.py`
- Create: `tests/test_ai_v2_narrative.py`

**Dependencies:** Task 2、Task 3、Task 5、Task 6、Task 7、Task 8。

**Interfaces:**
- Consumes: `AiV2Input`、`AiV2PromptRegistry`、`TextModelPort`、`AiV2Store`。
- Produces: `NarrativeTextUseCase.generate(project_id: int, input: AiV2Input, batch_index: int) -> PublicRun`。

- [ ] **Step 1: 写失败测试**

覆盖成功 5×2×3、空任务说明、额外字段拒绝、模型格式错误直接失败、不创建第二次格式修复调用、失败重试新会话和第二批新会话。

- [ ] **Step 2: 实现一次文字调用**

使用 v2 registry 编译 Prompt，调用一次 `start_text`，解析 JSON，运行 narrative schema 和业务 validator；校验失败直接保存失败运行并抛出稳定错误。

- [ ] **Step 3: 实现 canonical 保存与公开投影**

先保存内部 canonical，再通过 Task 8 生成公开结果；叙事永远不创建 image session 或 image attempt。

- [ ] **Step 4: 验证**

通过 deterministic fake 穿过 use case、store、projection；执行 v2 boundary 和定向测试。

### Task 9B: 静态文字用例

**Files:**
- Create: `src/creative_studio/ai_v2/static_visual.py`
- Create: `tests/test_ai_v2_static_visual.py`

**Dependencies:** Task 2、Task 3、Task 5、Task 6、Task 7、Task 8。

**Interfaces:**
- Consumes: `AiV2Input`、`TextModelPort`、`AiV2Store`。
- Produces: `StaticTextUseCase.generate(project_id: int, input: AiV2Input, batch_index: int) -> PublicRun` 和 `StaticTextUseCase.request_image(scheme_id: int) -> ImageAttemptView`。

- [ ] **Step 1: 写失败测试**

覆盖固定 3 案、每案一条内部 image prompt、文字成功后图片仍 pending、重复点击同一方案幂等、一次点击只产生一张图片任务、成功图片不能重新生成、失败可重试且重试不新建 image session。

- [ ] **Step 2: 实现一次文字调用**

只使用 v2 static Prompt 和 schema；内部保存 `execution.image_prompt`，公开结果只显示四个文字字段和图片状态。

- [ ] **Step 3: 实现图片请求入口**

第一次点击在事务中创建该方案唯一 image session 和第一条 attempt；已有 success 返回原结果，generating 返回原 attempt，failed 先进入对账流程。

- [ ] **Step 4: 验证**

确认静态用例不调用 carousel 模块、不创建 display frame 旧记录、不自动生成图片。

### Task 9C: 轮播文字用例

**Files:**
- Create: `src/creative_studio/ai_v2/carousel_visual.py`
- Create: `tests/test_ai_v2_carousel_visual.py`

**Dependencies:** Task 2、Task 3、Task 5、Task 6、Task 7、Task 8。

**Interfaces:**
- Consumes: `AiV2Input` 中的轮播标签、`TextModelPort`、`AiV2Store`。
- Produces: `CarouselTextUseCase.generate(project_id: int, input: AiV2Input, batch_index: int) -> PublicRun` 和 `CarouselTextUseCase.request_frame(scheme_id: int, frame_index: int) -> ImageAttemptView`。

- [ ] **Step 1: 写失败测试**

覆盖 2/3/4/5 屏、固定屏数不匹配、AI 决定屏数超出 2-5、frames 与 image prompts 索引不一致、首帧失败不解锁第二帧、前一帧成功后才能生成下一帧、重复点击和重试不新建方案图片会话。

- [ ] **Step 2: 实现一次完整规划调用**

一次文字响应保存全部 frames、continuity rules 和 image prompts；后续帧不调用文字模型，不重新规划路线；一次点击只提交当前允许的一个 frame。

- [ ] **Step 3: 实现单方案图片 session**

第一次请求某方案首帧时创建一个 image session；后续帧和失败重试都复用该 session，当前帧请求必须携带上一张成功图片和当前 Prompt；不会预取或自动推进下一帧。

- [ ] **Step 4: 验证**

确认三个方案全部生成时是 1 个文字 session + 3 个 image sessions；没有“每帧一个会话”的实现。

### Task 10: 图片状态机与幂等规则

**Files:**
- Create: `src/creative_studio/ai_v2/image_state.py`
- Create: `tests/test_ai_v2_image_state.py`

**Dependencies:** Task 6、Task 7、Task 9B、Task 9C。

**Interfaces:**
- Consumes: v2 frame state、scheme version、image session and attempt records。
- Produces:

```python
def can_start_static(status: str) -> bool:
    raise NotImplementedError

def can_start_frame(states: Sequence[str], frame_index: int) -> bool:
    raise NotImplementedError

def transition(status: str, event: Literal["start", "success", "failure", "retry"]) -> str:
    raise NotImplementedError

def stable_image_key(scheme_version: str, frame_index: int) -> str:
    raise NotImplementedError
```

- [ ] **Step 1: 写失败测试**

覆盖 pending→generating→success、pending→generating→failed→generating、success 再 start 被拒绝、轮播越序被拒绝、前序失败不解锁后序、重复 request key 返回原 attempt。

- [ ] **Step 2: 实现纯函数**

状态机不碰 DOM、SQLite 或网络；所有非法转换返回稳定冲突 code，不通过中文字符串判断。

- [ ] **Step 3: 接入 store 条件更新**

以 scheme version + frame index 作为逻辑帧锁定键，attempt 序号只区分同一逻辑帧的重试；成功后不可覆盖，失败只允许同一 frame 新 attempt，不能重新创建 scheme 的 image session。

- [ ] **Step 4: 验证**

执行状态机测试和并发 fake；确认没有调用旧 carousel operation。

### Task 11: v2 图片 Adapter、worker 与会话对账

**Files:**
- Create: `src/creative_studio/ai_v2/adapters/image_gateway.py`
- Create: `src/creative_studio/ai_v2/image_worker.py`
- Create: `tests/test_ai_v2_image_worker.py`

**Dependencies:** Task 6、Task 7、Task 9B、Task 9C、Task 10。

**Interfaces:**
- Consumes: `ImageModelPort`、private `ImageSessionCursor`、`AiV2Store`、image bytes/MIME。
- Produces: `ImageWorker.submit(attempt_id) -> None`，后台完成/失败/对账并通过公开状态查询。

- [ ] **Step 1: 写失败测试**

覆盖供应商排队、成功、终态失败、网页/网络超时、网页显示失败但供应商已成功、网页显示失败但供应商仍工作、本地 attempt 缺失但方案 image session 已存在的孤儿任务、对账未知/不可用、重复点击、JPEG/PNG/WebP MIME 和轮播前一张图片引用。

- [ ] **Step 2: 实现 v2 gateway adapter**

只实现 v2 typed request 到网关协议的翻译；请求必须透传稳定的 `image_session_key`、`request_key` 和供应商可查询的幂等元数据；不导入 `image_jobs.py`，不传本地路径，不记录完整 Prompt 或图片内容到日志。若供应商不支持按稳定键查询，Adapter 必须返回 `unknown`，禁止静默重发。

- [ ] **Step 3: 实现首次提交与同 session 继续**

首次方案点击创建 image session；轮播后续帧使用该 session 的 cursor、上一张成功 artifact bytes/MIME 和当前帧 Prompt；静态不会继续第二帧。

- [ ] **Step 4: 实现重试前对账**

失败重试先按稳定 request key 查询本地 attempt，再调用供应商 `reconcile`：已成功则下载并原子完成原 attempt，工作中则重新挂接，明确终态失败才产生同一图片 session 下的新 attempt；未知或不可用只返回可重试结果，不创建新 attempt，更不能创建第二个 image session。

实现顺序固定为：

```text
find_image_session(scheme_id, image_session_key)
  -> 已存在: 继续使用该 image session
  -> 不存在: 仅在首帧/首张第一次点击时 start_image_session
find_image_attempt(scheme_id, frame_index, request_key)
  -> success: 直接返回已有 artifact
  -> generating: 返回原 attempt，继续轮询
  -> missing/failed/本地结果未知: reconcile(原 image session + provider job/cursor)
       -> success: 下载并 complete_image_attempt_atomic(原 attempt)
       -> working: 恢复 generating，继续轮询原 attempt
       -> terminal_failure: 在原 image session 内 reserve 新 attempt
       -> unknown/unavailable: 保留当前 attempt，不创建新 attempt，返回 retryable
```

`start_image_session` 只允许在该方案不存在 image session 且确实是首帧/首张第一次点击时调用；重试路径禁止调用它。每个 HTTP 图片请求都必须携带同一 `request_key`，避免网页重复点击在对账完成前再次提交供应商任务。

- [ ] **Step 5: 验证**

只用 fake image gateway 和临时图片目录；运行定向测试、MIME 检查、v2 boundary 和 `git diff --check`。

### Task 12: v2 文字 Facade、组合根和 API

**Files:**
- Create: `src/creative_studio/ai_v2/application.py`
- Create: `src/creative_studio/ai_v2/http_api.py`
- Create: `tests/test_ai_v2_api.py`
- Modify: `src/creative_studio/app.py`（只增加 v2 路由挂载和依赖注入）

**Dependencies:** Task 7、Task 8、Task 9A、Task 9B、Task 9C、Task 11。

**Interfaces:**
- Consumes: 三类 use case、v2 store、v2 adapters、现有认证/项目归属检查。
- Produces:

```text
POST /api/v2/projects/{project_id}/generate
GET  /api/v2/projects/{project_id}/history
GET  /api/v2/runs/{run_id}
POST /api/v2/schemes/{scheme_id}/image
POST /api/v2/schemes/{scheme_id}/frames/{frame_index}/image
GET  /api/v2/image-attempts/{attempt_id}
```

图片 POST 的响应语义固定为：首次接受或仍在工作返回 `202`；已有成功 artifact 直接返回 `200`；轮播越序或成功后再次生成返回 `409`；对账未知/供应商不可用返回带 `retryable=true` 的 `503`，但不创建新 attempt 或新 image session。前端只根据公开状态轮询，不接触会话游标。

- [ ] **Step 1: 写失败 API 测试**

覆盖未登录、项目越权、未知输入字段、三字段缺失、成功文字返回、文字输出失败、静态图片 202、轮播越序 409、一次点击只推进一张、重复请求幂等、网络超时后重试先对账和 v2 公开响应私有字段扫描。

- [ ] **Step 2: 实现应用 Facade**

应用层只根据 v2 use case 和 project snapshot 选择 narrative/static/carousel；不调用旧 `CreativeGenerationService`，不读旧生成历史来组成 v2 响应。

- [ ] **Step 3: 实现 HTTP 适配**

路由只解析请求、执行认证/项目归属、调用 Facade 和映射稳定错误；错误响应包含 `error_code/phase/retryable/trace_id`，不返回堆栈或供应商详情。

- [ ] **Step 4: 接入组合根**

在 `app.py` 中只增加 v2 依赖构造和 `/api/v2` 分发；旧路由保持原代码和行为不变。v2 DB migration 使用同一数据库路径但只创建 `ai_v2_*` 表。

- [ ] **Step 5: 验证**

运行 API 定向测试、旧路由回归测试、v2 boundary、Python compileall；确认没有旧 AI 双写。

### Task 13: 独立 v2 正式前端

**Files:**
- Create: `static/ai-v2/index.html`
- Create: `static/ai-v2/app.js`
- Create: `static/ai-v2/styles.css`
- Create: `tests/test_ai_v2_frontend_contract.py`

**Dependencies:** Task 8；可与 Task 12 并行，先使用冻结的 v2 public DTO fixture，接线时再验证 Task 12 的 API contract；不得修改 `static/index.html` 或 `static/app.js`。

**Interfaces:**
- Consumes: v2 API public DTO；开发阶段可使用脱敏 contract fixture。
- Produces: `/ai-v2/` 页面，展示三字段输入、三类文字结果、图片状态和轮播逐张按钮。

- [ ] **Step 1: 写前端契约测试**

测试 v2 页面引用只属于 `static/ai-v2/` 的资源，调用路径只包含 `/api/v2/`，不出现旧 API、旧字段、Prompt 或内部执行字段。

- [ ] **Step 2: 实现输入界面**

只展示任务说明、画面比例和创意标签；产品证据/参考文件不以“会影响 v2”的形式出现。展示类仍在展示类内部切换静态/轮播，不新增顶层类型。

- [ ] **Step 3: 实现文字结果渲染**

叙事显示 5 套故事、钩子和场景；静态显示 3 套标题/核心创意/广告文案/画面描述；轮播显示 3 套完整 frames 路线；不读取 execution。

- [ ] **Step 4: 实现图片交互**

静态默认 pending，点击一次请求一张；轮播只显示当前可执行的下一张且不自动推进；success 按钮锁定，failed 显示重试；轮询 attempt 状态不重建输入状态，重试由服务端先对账而不是由前端新建会话。

- [ ] **Step 5: 验证**

运行 `node --check static/ai-v2/app.js`、前端 contract test，并在获得本地浏览器条件后检查 `1280x720`、`390x844`、控制台错误和横向溢出。

### Task 14: 端到端契约、隔离与质量评测门禁

**Files:**
- Create: `src/creative_studio/ai_v2/release_gate.py`
- Create: `tests/test_ai_v2_integration.py`
- Create: `tests/test_ai_v2_privacy.py`
- Create: `config/evals/ai_v2/reports/README.md`

**Dependencies:** Task 9A、Task 9B、Task 9C、Task 11、Task 12、Task 13。

**Interfaces:**
- Consumes: 生产 composition root、deterministic text/image fake、v2 public DTO、评测 fixtures。
- Produces: 可重复执行的 v2 contract/privacy/release gate，报告 `evidence_type=deterministic_fake`、`quality_claim=contract_only`，不把 fake 结果表述为模型质量通过。

- [ ] **Step 1: 写失败集成测试**

从 v2 HTTP 入口穿过 input → prompt registry → text fake → schema → store → projection；图片入口穿过 session → worker → artifact → public status。测试断言旧表写入次数为零。

- [ ] **Step 2: 写隐私测试**

递归扫描 history/run/status/adopt（如已启用）响应，拒绝 Prompt、execution、cursor、job id、路径、完整模型响应和堆栈；扫描日志也不得出现这些值。

- [ ] **Step 3: 写会话计数测试**

证明每批一个文字 session；三个方案都生成图片时恰好三个 image sessions；轮播同一方案所有帧只有一个 image session；每次点击最多一张；供应商已成功或仍在工作但本地失败、本地 attempt 缺失但方案 image session 已存在时都不重复创建 session；对账未知时也不创建新 attempt。

- [ ] **Step 4: 写质量报告格式**

报告硬约束包括 schema 通过率、私有字段泄露数、模型调用数、失败分类、重试次数和预算；真实模型质量在未授权前标记 not-run。

- [ ] **Step 5: 验证**

运行 v2 全套定向测试、既有 unittest、Node syntax、compileall、边界扫描和 `git diff --check`；任何 gate 失败都阻止 Task 15。

### Task 15: v2 采用关系（可独立延后）

**Files:**
- Create: `src/creative_studio/ai_v2/adoption.py`
- Create: `tests/test_ai_v2_adoption.py`
- Modify: `src/creative_studio/ai_v2/http_api.py`

**Dependencies:** Task 8、Task 12、Task 14；本任务默认不进入第一次 v2 切换，不修改旧 `adoptions` 业务路径。

**Interfaces:**
- Consumes: v2 public scheme DTO 和项目归属检查。
- Produces: `POST /api/v2/projects/{project_id}/adopt`、`GET /api/v2/projects/{project_id}/adoption`，写入 `ai_v2_adoptions` 自有表；旧页面继续读取旧采用关系。

- [ ] **Step 1: 写失败测试**

覆盖越权、采用不存在方案、采用对象不含私有字段、重复采用幂等和旧 `adoptions` 表写入次数为零。

- [ ] **Step 2: 创建 v2 采用存储**

采用快照只保存 v2 Public DTO 和 source scheme version；不复制 execution、Prompt、cursor 或内部路径。

- [ ] **Step 3: 接入 API 和页面**

v2 页面只显示 v2 adoption；不把新旧采用结果合并成一个列表。

- [ ] **Step 4: 验证**

只有用户另行确认把采用功能纳入 v2 切换时才执行本步骤；执行后通过 adoption 定向测试和隐私扫描。未确认时，Task 16 明确不包含 adoption，不能在旧路径中临时双写。

### Task 16: 独立入口切换与回滚演练

**Files:**
- Modify: `src/creative_studio/app.py`（仅增加显式入口选择）
- Modify: `static/index.html`、`static/app.js`、`static/styles.css`（用户批准切换后才修改）
- Create: `.scratch/ai-v2-cutover/spec.md`

**Dependencies:** Task 14 通过；Task 15 若纳入正式页面则必须通过。

**Interfaces:**
- Consumes: v2 API、v2 页面、旧入口健康状态和 release gate。
- Produces: 上层入口的单向选择：一次请求明确走旧链路或 v2，不合并结果、不双写、不 fallback。

- [ ] **Step 1: 写切换变更卡**

记录用户可见影响、备份、回滚、观察指标、旧路径零调用证据和明确的禁用方式；切换前不改生产页面。

- [ ] **Step 2: 增加显式 v2 入口**

先以独立链接或独立页面入口提供 v2，不覆盖旧页面；验证同一项目可分别读取旧历史和 v2 历史但不会合并。

- [ ] **Step 3: 执行回滚演练**

禁用 v2 入口后旧页面仍可运行；v2 表、图片和失败记录保留，不删除、不覆盖、不回写旧表。

- [ ] **Step 4: 用户批准后切换**

只在用户明确批准且 Task 14 gate 通过后，把正式页面上层入口切到 `/api/v2`；旧生产代码保持冻结，切换失败不自动降级旧 AI。

- [ ] **Step 5: 验证**

执行旧/新入口隔离测试、浏览器桌面/移动检查、控制台和网络请求检查；真实 AI/图片未授权时继续标记未验证。

### Task 17: 观察、废弃登记与后续清理

**Files:**
- Modify: `docs/ai-rebuild-master-plan.md`
- Modify: `docs/operations.md`
- Modify: `项目代码地图.md`
- Modify: `progress.md`
- Create: `docs/superpowers/handoffs/2026-09-04-ai-v2-release.md`

**Dependencies:** Task 16 完成并经过一个完整观察周期。

**Interfaces:**
- Consumes: v2 运行指标、旧 caller 扫描、回滚演练和评测报告。
- Produces: 当前事实文档、旧实现废弃清单、删除条件和交接记录。

- [ ] **Step 1: 记录观察指标**

记录 v2 文字成功率、图片成功率、会话重复创建数、对账恢复数、失败重试次数、延迟、预算和私有字段扫描结果；不记录 Prompt 正文、用户原文、图片内容或凭据。

- [ ] **Step 2: 登记旧实现**

为旧 adapter、旧 schema、旧 prompt loader、旧字段 mapper 写清 `deprecated_since`、替代项、禁止新调用、保留读取场景和删除条件；观察期内不删除旧代码。

- [ ] **Step 3: 同步当前事实**

只把已经通过 gate 的 v2 路由、表、worker 和回滚命令写入运维和代码地图；历史 progress 只追加链接，不覆盖旧事实。

- [ ] **Step 4: 生成最终交接记录**

交接记录列出已完成任务、未验证项、失败分类、回滚入口、下一步 Prompt 质量评测和真实供应商冒烟授权，不宣称“AI 质量已通过”。

- [ ] **Step 5: 单独提出删除变更**

旧 AI 的删除、旧数据归档和历史 scrub 不属于本计划自动动作；必须在观察期后另开变更卡，完成备份、恢复演练和用户确认。

## 3. 每个会话窗口的固定交接格式

每个执行窗口结束时，在对应变更卡或 handoff 中追加以下内容：

```text
任务：Task N / 子任务名
修改文件：完整路径列表
未修改的关键边界：旧 AI、旧表、真实凭据、生产数据
测试：执行的命令与结果
未验证：真实 AI、图片供应商、浏览器或多进程项
下一任务：仅列出已满足前置条件的任务
回滚：本任务提交或删除哪些新增文件即可恢复
```

并行窗口之间只通过文件和上述交接记录传递状态，不通过共享未提交修改猜测彼此进度。任何发现旧新链路发生引用、双写、双读或 fallback，立即停止后续任务，回到 Task 1 边界守卫修复。

## 4. 总体验收命令

在 Task 14、Task 16 和 Task 17 收尾分别执行与影响范围相称的检查；最终最低检查为：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_ai_v2_*.py" -v
node --check static\ai-v2\app.js
python -m compileall -q src chat2api
python -m creative_studio.ai_v2.release_gate
git diff --check
```

真实 AI、图片网关、认证浏览器、多进程竞态、真实运行库写入、历史 scrub、备份覆盖和正式部署均必须单独标记为“已验证”或“未验证”，不能用 deterministic fake 或静态页面结果代替。
