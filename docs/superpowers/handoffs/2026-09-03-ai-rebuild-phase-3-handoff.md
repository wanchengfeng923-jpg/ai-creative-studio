# AI 重构 Phase 3 交接文档：静态展示类

- 日期：2026-09-03
- 状态：Phase 3 实施入口，代码尚未切换
- 项目：`D:\code\ai_creative_studio`
- 当前分支：`codex/tag-accordion-prototype`
- Phase 3 基线 HEAD：`b4110ea27d4690575e023dc37e8969ccc17b31dc`（`docs: close phase 2 change card`）
- 本次交接内容通过独立 docs-only 提交保存。
- 本文性质：给下一次实现会话使用的执行契约，不是静态功能已完成的声明

本文只授权静态展示类迁移。轮播路线、继续生成、逐帧后台 Operation 和轮播 prompt 不属于本阶段；任何需要修改这些内容的发现都必须记录后转交 Phase 4。

## 1. 开始前的读取顺序

开始任何分析或修改前，按下面顺序完整阅读：

1. `AGENTS.md`
2. `progress.md`
3. `项目代码地图.md`
4. `docs/operations.md`
5. `docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-2-handoff.md`
6. `docs/ai-rebuild-master-plan.md`
7. `CODE_STYLE.md`、`CONTEXT.md`
8. `docs/superpowers/specs/2026-09-01-ai-generation-architecture-design.md`
9. `docs/superpowers/specs/2026-09-02-display-frame-flow-design.md`
10. `docs/research/2026-09-02-creative-prompt-engineering-research.md`
11. `docs/adr/0001-public-result-projection.md`
12. 本文及本次涉及目录中的测试、`.scratch` 变更卡和提示词文件

事实优先级为：运行代码和 registry、本文及已批准 ADR、`AGENTS.md`/`CODE_STYLE.md`、运维手册、历史进度记录。若历史文档与代码不一致，以代码和 registry 为准，并在 `.scratch/ai-phase-3/spec.md` 的“当前事实冲突”小节记录，不用新增兼容分支遮盖冲突。

## 2. 祖先和工作树门禁

开始实施前在仓库根目录执行以下检查；四条祖先命令都必须返回成功：

~~~powershell
Set-Location D:\code\ai_creative_studio
git merge-base --is-ancestor e7412bb8fc9eb43e0cb89df58048ac6363c52239 HEAD
git merge-base --is-ancestor 1704bea HEAD
git merge-base --is-ancestor 6dd91ef02a6dbdadccfa593b8c87f8d7570da48e HEAD
git merge-base --is-ancestor 1c681cc2b82fcaaee9416111ccd15b96bdf4efe9 HEAD
git status --short --branch
~~~

已确认的阶段提交：

| 阶段 | 提交 | 事实 |
|---|---|---|
| Phase 0 | `e7412bb8fc9eb43e0cb89df58048ac6363c52239` | 公开投影、模板安全、图片 MIME、失败记录和测试隔离止血 |
| Phase 1 | `1704bea` | PromptRegistry、contract allowlist、model/image port 和生成元数据 |
| Phase 1 fingerprint follow-up | `6dd91ef02a6dbdadccfa593b8c87f8d7570da48e` | prompt/schema/model/provider 纳入生成指纹 |
| Phase 2 implementation | `1c681cc2b82fcaaee9416111ccd15b96bdf4efe9` | NarrativeGeneration、NarrativeResult.v1 和叙事生产切换 |
| Phase 2 handoff | `6e19f198df96a4185a45410c99cdbad035878f7e` | Phase 3 初始交接文档 |
| Phase 2 closeout | `b4110ea27d4690575e023dc37e8969ccc17b31dc` | Phase 2 变更卡收尾和当前 HEAD |

接手时工作树已有用户修改 `launcher.py`。必须保留、不得重置或覆盖，也不得放入本阶段 docs-only 或实现提交。提交前后都要检查：

~~~powershell
git status --short --branch
git diff -- launcher.py
~~~

## 3. Phase 2 已完成事实

Phase 2 只迁移叙事类，静态和轮播生产分支没有切换。

- `src/creative_studio/narrative.py` 提供 `NarrativeGeneration`、`NarrativeInput`、`NarrativeResult` 和 `NarrativeOutputError`。
- 生产叙事 prompt 是 `creative.narrative.generate@v6`，文件为 `config/prompts/narrative/v6.txt`，输出为 `NarrativeResult.v1`，旧 v5 仅保留为 retired inventory。
- 正常 composition root 为 `StudioApplication -> CreativeGenerationService -> NarrativeGeneration -> ModelClient/HttpModelClient -> chat2api`。
- 叙事第二批有显式去重上下文，格式修复携带字段路径；公开历史和采用通过 `PublicResultMapper` 映射。
- `PYTHONPATH=src python -m unittest discover -s tests -q` 已有 185 项通过；`node --check static/app.js`、`python -m compileall -q src chat2api` 和 `git diff --check` 通过。
- 真实 AI、真实图片网关、真实浏览器、真实数据库写入和真实图片质量均未在 Phase 2 验证。

Phase 3 必须保持叙事 Module、v6 registry、叙事 DTO 和叙事测试行为不变。`LegacyCreativeGenerationAdapter` 仍因轮播和无 model client 兼容场景保留，Phase 3 不删除它。

## 4. Phase 3 目标、非目标和不变量

### 4.1 目标

1. 将 `config/ai_visual_static_creative_prompt_v1.txt` 从 candidate 升级为唯一的静态 production PromptSpec。
2. 建立 `StaticVisualGeneration` 和 `StaticVisualResult.v1`，使 prompt、input、output、validator、persistence、public DTO、图片 caller 和测试来自同一 registry contract。
3. 停止把首帧内容伪造成 `subtitle`、`core_subject`、`layout`、`visual_style` 等旧字段；新数据只写 canonical 静态字段。
4. 公开用户真正需要评审的用户张力、产品价值、视觉机制、证据台账、静态画面、素材计划、制作风险和首轮验证动作。
5. 保持现有 HTTP URL、`success/error` 包络、静态页面基本工作流、每批三案、最多两批和首图异步状态兼容。
6. 让静态首图使用明确的图片 Port seam，文字成功、图片排队、图片成功和图片失败能够独立观察和恢复。

### 4.2 非目标

- 不修改 `creative.visual.carousel.plan@visual-carousel-v1`、`config/ai_visual_carousel_prompt_v1.txt` 或轮播校验规则。
- 不实现独立首帧文字会话，不恢复 `ai_visual_first_frame_prompt_v1.txt`，不接入 `ai_visual_follow_up_prompt_v1.txt`。
- 不实现按 2、3、4、5 帧继续生成，不修改轮播锁、会话游标、逐帧状态机、前端继续按钮或同步长请求。
- 不增加登录、权限、端口、部署、备份、真实数据库迁移或 `chat2api/.env` 修改。
- 不调用真实 AI、图片网关或带认证浏览器，除非另有明确授权和独立变更卡。
- 不将 `frontend/` 原型接入正式 `static/` 页面。

### 4.3 不变量

- 每个静态批次恰好 3 个方案；每个方案恰好 1 个静态首图任务。
- `image_generation_instruction` 只能在内部执行对象、受控图片任务数据或私有存储列中存在，不得出现在历史、状态、采用、导出、日志或浏览器响应。
- 用户标签是 brief 候选，空白允许；不要求模型返回 `resolved_tags`，不把目录关系伪装成模型事实。
- 产品事实只能来自产品资料或用户输入；不确定内容必须进入 `inferred` 或 `to_confirm`，不能写入 `confirmed`。
- 任何新代码从生产 composition root 进入同一 StaticVisualGeneration seam；只测旧函数或手工内部对象不算通过。
- 静态输入快照、prompt 版本/hash、schema 版本、model/provider 和 reference 文件名策略必须持久化可追溯，但供应商游标和完整模型正文不得公开。

## 5. 当前静态生产链路：以代码为准

### 5.1 Composition root 和 caller

`src/creative_studio/app.py:create_application()` 在没有显式注入时：

1. 加载 `PromptRegistry`；
2. 创建 `StudioRepository`、`GptWebImageClient`、`ImageJobRunner`；
3. 通过 `_load_model_client()` 创建 `HttpModelClient`，默认地址为 `http://127.0.0.1:8780/v1/chat/completions`，模型为 `gpt-5-6-mini`；
4. 注入 `CreativeGenerationService`；
5. `POST /api/projects/{id}/generate` 进入 `StudioApplication.generate()`。

当前默认静态文字链路是：

~~~text
static/app.js
  -> POST /api/projects/{id}/generate
  -> StudioApplication.generate
  -> CreativeGenerationService.generate
  -> _generate_with_model_client (snapshot.kind == visual)
  -> load_ai_visual_creative_config(carousel=False)
  -> build_visual_creative_prompt
  -> ModelClient.generate(ModelRequest)
  -> HttpModelClient
  -> chat2api /v1/chat/completions
  -> _request_and_validate
  -> validate_visual_creative_recommendations
  -> repository.complete_visual_generation
  -> ImageJobRunner.enqueue([三个 visual_item id])
~~~

当测试或旧调用者显式传 `model_client=None` 时，服务降级到 `LegacyCreativeGenerationAdapter`，该分支仍会调用旧 `ai_creative.generate_visual_creative_recommendations()`。这不是默认生产链路，也不能被误报为新 Module 已接线。

### 5.2 当前 registry 状态

`config/prompts/registry.json` 当前有 3 个 production、1 个 candidate 和 3 个 retired/历史条目。静态相关项如下：

| registry key | path | lifecycle | output/validator | caller | 说明 |
|---|---|---|---|---|---|
| `creative.visual.static.generate@visual-v2.3` | `config/ai_visual_creative_prompt_v2.txt` | production | `LegacyStaticVisualResult.v2.3` / `StaticVisualResultValidator.v2.3` | `static` | 当前真实静态 production；hash `cd59f90f16c5cabfde58c45ab34ad82bba85fd3e36a5f1ce5493289040674fa7` |
| `creative.visual.static.generate@static-v1` | `config/ai_visual_static_creative_prompt_v1.txt` | candidate | 未形成 production contract | 空；`new_callers_forbidden=true` | Phase 3 目标；hash `909d6fcf91c5095087f588402ae2f46957a1613acaaa576e5f048ed2e5344198` |
| `creative.visual.carousel.plan@visual-carousel-v1` | `config/ai_visual_carousel_prompt_v1.txt` | production | `LegacyCarouselPlanResult.v1` / `CarouselPlanValidator.v1` | `carousel` | Phase 3 禁止修改 |

当前 `CreativeGenerationService._prompt_spec()` 在静态分支返回 `visual-v2.3`。不能只改 registry lifecycle 而不同时替换 validator、Module、持久化和 DTO；registry 变成 production 但 caller 仍使用旧字段属于 fail-closed 配置错误。

### 5.3 当前输入和 prompt 编译

`CreativeGenerationService._build_snapshot()` 从项目读取并归一化：

- `task_type`：最多 100 个字符的任务类型；
- `task_description`：必须非空，最多 1000 个字符；
- `creative_tags`：按 `VISUAL_TAG_KEYS` 保留展示类标签，顺序在 fingerprint 中排序；
- `product_evidence_summary`：项目产品资料摘要；
- `aspect_ratio`：当前项目值，通常为 `16:9` 或 `9:16`；
- `reference_file_names`：来自 `repository.reference_file_names(project_id)` 的文件名列表。

`build_visual_creative_prompt()` 只向当前 v2.3 prompt 注入上述字段和展示标签文本；静态调用没有 `carousel_context`。当前 reference 文件只以文件名进入文字 prompt，文件内容没有进入文字模型，图片参考图也没有随静态首图任务自动附带。Phase 3 必须在 contract 中明确为“文件名提示，不宣称模型已读取内容”；是否真正发送内容另立 ReferenceAsset 变更，不得顺手扩大范围。

### 5.4 当前输出校验和旧字段伪造

`validate_visual_creative_recommendations()` 在 `ai_creative.py` 中同时兼容两种形状：

- 没有 `carousel_config` 且没有 `first_frame` 时，要求旧 `VISUAL_CREATIVE_ITEM_FIELDS`：`title`、`subtitle`、`creative_description`、`core_subject`、`layout`、`visual_style`、`content_extensions`、`reference_sources`、`keywords`、`image_prompt`。
- 只要三案中任一案包含 `first_frame`，就进入新首帧分支；该分支要求 `creative_summary`、`creative_sources`、`frame_count`、`visual_continuity_rules`、连续 `frame_plan` 和 `first_frame`，随后人为生成：\n  - `subtitle = first_frame.content`\n  - `core_subject = first_frame.content`\n  - `layout = first_frame.content`\n  - `visual_style = 视觉连续性规则拼接`\n  - `content_extensions = 后续 frame_plan 或首帧内容`\n  - `reference_sources = 来源字符串 + 固定说明`\n  - `keywords = [展示类, 连续画面]`\n  - `image_prompt = first_frame.image_generation_instruction`\n\n这段兼容归一化是当前生产静态路径的核心漂移。Phase 3 新 validator 必须拒绝新静态结果依赖这些别名；旧校验器只允许历史读取、旧测试审计或轮播兼容，禁止新增静态 production caller。\n\n当前 `_request_and_validate()` 最多调用模型两次，但第二次复用了相同 `ModelRequest`，没有携带字段路径、错误原因或静态 repair 指令。Phase 3 可以实现有界的静态 format repair，但必须在 `GenerationPolicy` 中显式记录最多调用次数，并让 fake 测试能观察第二次 prompt 与第一次不同；禁止复制无上限循环。

### 5.5 当前持久化事实

`repository._complete_generation()` 的视觉分支目前按以下顺序工作：

1. 将未经公开投影的 `result.items` 整体写入 `generations.items_json`；旧静态结果的 `image_prompt` 和 `first_frame.image_generation_instruction` 可能落库。
2. 对每个方案浅复制后 `pop("image_prompt")`，写入 `visual_items.content_json`；若为空则从 `first_frame.image_generation_instruction` 取值。
3. 将私有图片指令单独写入 `visual_items.image_prompt`。
4. 从 `carousel.frames`、`frame_plan` 或兜底首帧内容创建 `display_frames`；首帧私有指令再写入 `display_frames.image_generation_instruction`，状态为 `pending`。
5. 返回三个 `visual_item` id，生成服务调用 `ImageJobRunner.enqueue()`。

当前数据库存在三处事实副本和不同隐私风险：`generations.items_json` 原始快照、`visual_items.content_json` 方案正文、`visual_items.image_prompt`/`display_frames.image_generation_instruction` 私有执行字段。Phase 3 应先建立 canonical typed persistence mapper，停止新数据写入旧 alias；不要在本阶段重建真实数据库、删除旧列或对 `data/creative_studio.db` 执行 scrub。

### 5.6 当前图片任务 seam

`ImageJobRunner` 是静态首图的真实图片 caller：

- `complete_visual_generation()` 后立即入队 3 个方案；文字接口不会等待图片终态。
- `claim_visual_item()` 将 `queued -> generating`，递增 `image_attempt`，并同步首帧 `display_frames.image_status`。
- `GptWebImageClient.submit()` 使用 `creative-studio-{item_id}-attempt-{attempt}` 幂等键、`n=1`、`size=1K`、目标画幅和图片模式前缀；成功任务才缓存。
- 任务状态最多轮询 600 秒；成功下载只接受同源图片和 JPEG/PNG/WebP magic bytes，写入 `data/images/{generation_id}/{item_id}/attempt-{n}.<ext>`。
- 第一次失败自动把同一 visual item 置回队列并再试一次；第二次失败保留 `failed`。`POST /api/visual-items/{id}/retry` 允许人工重试。
- 图片状态以 SQLite 为事实源；进程启动时 `recover_visual_items()` 回收 `generating` 项。

Phase 3 只需给图片 runner 一个明确的 `StaticVisualImageRequest` 或等价 seam，确保它收到 canonical 静态方案的私有指令和画幅；不改变轮播逐帧 worker、会话游标或继续接口。

### 5.7 当前公开 DTO 和路由

当前主要路由最终通过 `PublicResultMapper`，但静态 mapper 仍只认识旧字段和首帧规划字段：

- `visual_item()` 公开旧 `subtitle`/`creative_description` 等字段、`frame_plan`、`first_frame` 的 `index/content`、图片状态和应用内图片 URL。
- `image_prompt`、`image_generation_instruction`、`conversation_id`、`parent_message_id`、本地 `image_path`、gateway job id、完整错误详情均被排除。
- `display_frame()` 公开逐帧计划、实际内容、状态、图片 URL 和安全错误摘要，不公开私有指令和本地路径。
- `StudioApplication.adopt_visual()` 先调用 mapper 再保存采用快照；`repository.visual_adoption_source()` 仍返回内部 `content_json`，不得把该 raw 对象直接返回 HTTP。

Phase 3 新 DTO 必须继续从对象白名单重建，而不是复制内部字典后删除几个 key。历史、采用、状态和任何新增导出入口都必须复用同一个静态 DTO。

## 6. Phase 3 目标契约

### 6.1 PromptSpec 和输入

将 registry 的静态 production 绑定改为：

~~~text
id: creative.visual.static.generate
version: static-v1
path: config/ai_visual_static_creative_prompt_v1.txt
input_schema: StaticVisualPromptInput.v1
output_schema: StaticVisualResult.v1
validator: StaticVisualResultValidator.v1
public_dto: StaticVisualPublicDTO.v1
caller: static
provider: chatgpt-web
model: gpt-5-6-mini
~~~

`StaticVisualPromptInput.v1` 是内部 typed input，不向浏览器暴露模型字段。最小字段为：

~~~json
{
  "task_type": "任务类型",
  "task_description": "任务说明",
  "creative_tags": {
    "visual_target_audiences": [],
    "visual_player_desires": [],
    "visual_product_selling_points": [],
    "visual_display_contents": [],
    "visual_art_style_relevance": [],
    "visual_art_style": [],
    "visual_art_style_references": [],
    "visual_motif": [],
    "visual_dynamics": [],
    "visual_voice_hook": []
  },
  "aspect_ratio": "16:9",
  "product_evidence_summary": "产品资料摘要或空字符串",
  "reference_file_names": []
}
~~~

输入规则：

- `task_description` 在生成入口仍必须非空；其他 brief 文本可为空，空标签由 prompt 明确写成“未选择标签”。
- `creative_tags` 只保留 `VISUAL_TAG_KEYS`，去重、裁剪、稳定排序；`visual_carousel*` 不参与静态输出 contract 的业务含义。
- `aspect_ratio` 只允许现有项目支持的 `16:9` 或 `9:16`；不要在本阶段添加任意尺寸枚举。
- 用户输入中的 `{{foo}}`、`${task_type}`、URL 和换行按 prompt 编译器及 validator 规则处理；模板变量不能二次解释用户文本。
- reference 文件名只表示“项目中存在这些文件”，除非另有 ReferenceAsset 设计和测试，不得声称模型读取了文件内容。

### 6.2 StaticVisualResult.v1

模型输出根对象只能有 `items`，且恰好 3 个对象；三案 `concept_id` 必须各出现一次且只能为 `A`、`B`、`C`。每个方案的 canonical 字段如下：

~~~json
{
  "concept_id": "A",
  "title": "方案标题",
  "creative_summary": "画面发生了什么以及证明了什么",
  "audience_tension": "一个具体用户欲望或矛盾",
  "product_value": "一个真实产品价值",
  "visual_mechanism": "第一眼成立的替换、缺失、对照或其他观看关系",
  "creative_sources": ["参考结构、媒介机制或原创依据"],
  "evidence_ledger": {
    "confirmed": ["输入或产品资料确认的事实"],
    "inferred": ["合理创意表现假设"],
    "to_confirm": ["制作前必须确认的内容"]
  },
  "static_frame": {
    "visual_event": "静态画面中最值得停留的事件",
    "hero_subject": "第一视觉主体及其产品关系",
    "composition": "主体、对照物、留白和信息区域",
    "attention_order": ["第一眼", "第二眼", "第三眼"],
    "medium_and_art_direction": "媒介、材质、色彩、线条、明暗和字体规则",
    "copy": {
      "headline": "主文案",
      "supporting_line": "辅助文案或空字符串",
      "brand_line": "品牌名或 Logo 文案",
      "cta": null
    },
    "product_proof": ["可见的产品价值证据"],
    "legibility_notes": "缩小后保留的识别和阅读条件"
  },
  "asset_plan": [
    {"asset": "所需素材", "status": "existing", "fallback": "素材缺失时的替代方案"}
  ],
  "production_risks": [
    {"risk": "最可能失真的风险", "mitigation": "具体缓解方式"}
  ],
  "review": {
    "stop_reason": "第一眼停留理由",
    "why_make_next": "进入制作或测试的理由",
    "first_validation": "制作完成后最早检查的一件事"
  },
  "image_generation_instruction": "仅供服务端图片模型使用的静态执行指令"
}
~~~

validator 必须至少执行以下硬约束：

- 根对象和每个对象字段集合精确匹配；禁止额外字段、Markdown、URL、思维链和供应商响应包装。
- 三个 `concept_id` 唯一；每个方案的 `creative_sources`、证据列表、`attention_order`、`product_proof`、`asset_plan`、`production_risks` 非空且元素类型正确。
- `asset_plan.status` 只能为 `existing`、`needs_capture`、`needs_design`、`to_confirm`；`copy.cta` 只能是字符串或 `null`。
- 所有文本字段非空规则、单行规则、长度边界和 URL 拒绝规则由 validator 明确声明；空字符串只允许 supporting line、cta 等明确字段。
- `confirmed` 必须是输入或产品资料可追溯事实；事实绑定由 deterministic fixture 和评审集检查，不能凭模型口吻认定。
- `image_generation_instruction` 必须非空但只作为内部字段；它不得被 public DTO 或前端历史对象看到。
- 三案的 `visual_mechanism` 必须存在可观察差异。硬 validator 可做文本签名/重复检查，质量差异还必须由固定评估集和人工抽查确认。

`StaticVisualResult.v1` 不包含 `frame_count`、`frame_plan`、`first_frame` 或 `visual_continuity_rules`。这些属于轮播 contract；静态方案只有一张 `static_frame`。历史兼容必须在 adapter 边界转换为 canonical 对象，新生产结果不能再写回这些字段。

### 6.3 私有图片指令边界

私有 `image_generation_instruction` 只能描述：目标画幅、媒介、主体、空间关系、产品证据、文案留白、颜色/材质和负面限制。不得包含动态镜头、时间线、音效、下一帧、投放效果、供应商密钥、文件系统路径或模型思维链。

图片 Port 接收 typed request，至少包含：

~~~text
scheme_id / generation_id
aspect_ratio
prompt (private instruction)
request_id (stable per scheme attempt)
reference_assets (当前版本为空或明确的受控资产列表)
~~~

图片 Adapter 不把本地路径传给网关；未来加入参考图时只传 bytes、真实 MIME 和受控资产引用，并由独立测试证明 JPEG/PNG/WebP 均正确。

### 6.4 StaticVisualPublicDTO.v1

公开 DTO 包含：

~~~text
concept_id, title, creative_summary, audience_tension, product_value,
visual_mechanism, creative_sources, evidence_ledger, static_frame,
asset_plan, production_risks, review,
id, item_index, scheme_id, generation_id, aspect_ratio,
image_status, image_url, image_error
~~~

`static_frame` 公开除 `image_generation_instruction` 之外的字段；该私有字段不在 DTO 类型定义中。DTO 不公开 `image_prompt`、会话游标、assistant message id、gateway job id、本地图片路径、上传存储名、完整模型正文、`error_detail` 或堆栈。历史、采用、状态和图片 URL 路由都必须从该 DTO 或明确的状态子投影构造。

旧 UI 若仍读取 `subtitle` 或 `creative_description`，只能使用一次明确的读取兼容映射；兼容映射不能写入新 `content_json`，也不能让 canonical DTO 永久携带伪造字段。若本阶段不改 UI，测试必须证明新字段已公开且旧页面不会因缺少字段崩溃，并把旧字段读取的删除条件写进 Phase 5 清理项。

## 7. 目标模块和允许修改面

### 7.1 推荐模块边界

建议新增 `src/creative_studio/static_visual.py`（名称由变更卡固定），由 `StaticVisualGeneration` 隐藏：

- `StaticVisualPromptInput` 归一化和输入长度边界；
- registry PromptSpec 解析和模板编译；
- 静态模型请求、有限 format repair、`StaticVisualResult.v1` validator；
- 私有图片指令与方案对象的分离；
- `StaticVisualPublicDTO.v1` 映射；
- 静态结果交给 repository/image Port 的 typed 调用。

`CreativeGenerationService` 保留项目访问、reservation、失败/成功包络和批次限制，但不再在视觉分支内拼接静态 prompt 或调用旧视觉 validator。`app.py` 仍只处理 HTTP、权限和错误映射。`repository.py` 负责事务和行映射；私有字段不能由 HTTP handler 过滤。

### 7.2 允许修改

- `config/ai_visual_static_creative_prompt_v1.txt`（仅在与 schema 不一致时做最小修改）；
- `config/prompts/registry.json`、`src/creative_studio/contracts.py`、`prompt_registry.py`；
- 新静态 Module、typed contract、public projection 和静态生产接线；
- 静态结果所需的 repository mapper、图片 Port/runner 的最小适配；
- 静态生产入口、registry、prompt、validator、DTO、persistence、图片状态的 deterministic tests；
- `config/evals/static.v1.json`、`.scratch/ai-phase-3/spec.md`、`progress.md`、代码地图、运维手册和必要 ADR。

### 7.3 禁止修改

- `config/ai_visual_carousel_prompt_v1.txt`、轮播 registry contract、轮播后续提示词、`continue_scheme()` 的业务顺序；
- 叙事 v6 prompt、NarrativeGeneration contract 和叙事 UI 语义；
- 真实 `data/creative_studio.db`、`data/images/`、`data/uploads/` 和 `chat2api/.env`；
- 监听地址、登录权限、部署方式和网络代理；
- 为兼容旧 UI 给 canonical 结果继续新增 `subtitle/core_subject/layout/visual_style` 别名；
- 直接把 `dict.copy()` + `pop()` 当成新的公开投影；
- 通过环境变量把 candidate prompt 隐式切成 production，或保留没有删除日期的永久双轨。

## 8. 状态、失败、重试和幂等

静态生成必须把文字运行和图片 artifact 分开表达：

~~~text
文字：reserved -> generating -> text_succeeded
                         -> failed

首图：queued -> generating -> success
                         -> retrying -> success
                                      -> failed
~~~

- 文字 contract 校验失败最多执行一次显式 repair；两次失败记录 `model_output_invalid`、精确字段路径、attempt 和安全 trace id，保留 generation 失败记录，不删除旧失败证据。
- 文字成功后即持久化三套 canonical 方案并入队三张首图；一套首图失败不影响其他两套，公开历史必须能显示部分成功。
- 图片任务每个 attempt 使用稳定 request id；同一 attempt 重复提交只能复用同一 gateway job，旧 worker 不能覆盖新 attempt。
- 自动图片重试最多一次；人工 `/retry` 只允许失败项，递增 attempt 并清除旧 artifact 引用。成功项不重复生成。
- 图片下载、保存和数据库状态更新按现有同源/MIME 校验执行；保存失败仍将 attempt 标为失败。
- 进程重启只恢复 SQLite 中明确为 queued 或失活 generating 的静态首图；不要在本阶段改变轮播 lease 或继续操作恢复规则。
- `text_succeeded + image_status=queued/generating` 是合法公开状态，不得误报为全部生成完成。

HTTP 兼容：输入错误沿用 422，资源不存在沿用 404，状态冲突沿用 409，AI 排队超时沿用 503，AI/模型输出失败沿用 502；继续提供中文 `error`，并加法保留 `error_code/phase/field_path/retryable/trace_id`。不要用中文错误字符串作为内部状态判定。

## 9. Deterministic contract harness 和验收矩阵

实现前先创建 `.scratch/ai-phase-3/spec.md`，再写能失败的定向测试。所有 harness 必须从 `create_application()` 或等价正式 composition root 进入，并注入：

- 可编程 `FakeModelClient`/`TextModelPort`，记录每次 request 的 prompt、模型、会话字段和调用次数；
- 可编程 `FakeImageRunner`/`ImageModelPort`，记录 scheme、attempt、画幅、私有指令和重试；
- 临时 SQLite 路径；
- 固定 `clock`；
- 隔离 environment，不读取默认真实凭据、真实数据库或真实图片目录。

最小验收矩阵：

| 类别 | 固定场景 | 必须观察到的结果 |
|---|---|---|
| registry | static-v1 升级后加载 | production 静态项唯一；path/hash/variables/contract/caller 全匹配；v2.3 retired |
| 正常生成 | 完整脱敏展示输入 | fake model 只收到静态输入；返回 A/B/C canonical 方案；每案一个首图任务；图片指令不在公开 history |
| 空白 brief | 标签、产品摘要、参考文件名为空 | prompt 使用明确空白表示；仍可生成；不伪造事实；不产生 resolved_tags |
| 输入安全 | 输入含 `{{foo}}`、`${task_type}`、URL、换行和超长文本 | 变量只替换声明变量；用户文本不二次解释；边界错误有精确 field path |
| 结构错误 | 少一案、重复 concept_id、额外字段、缺 evidence、错误 asset status | policy 次数受限；最终 `model_output_invalid`；失败记录保留 |
| 质量边界 | 三案只换颜色/角色/文案 | 机制签名或评估门禁失败，不能仅因字段完整通过 |
| 公开投影 | history/status/adopt/图片状态 | 递归扫描无私有指令、cursor、path、job id、raw response 或内部 error |
| 持久化 | 临时 SQLite 读取 generation、visual item、frame | canonical 字段可重建；新写入无旧 alias；私有指令只在内部列/任务对象；事务失败无半个方案 |
| 图片成功 | fake runner 立即 success | 三项各自成功；image URL 由应用路由生成；文字和图片状态分开可见 |
| 图片部分失败 | 第二方案两次失败，第一/第三成功 | 第一/第三不受影响；第二可 retry；成功项不重复提交 |
| 图片恢复 | 首图 generating 后重建 runner | 只恢复未完成项；attempt 递增；旧 attempt completion 被拒绝 |
| 生产 caller | `create_application(model_client=fake, image_runner=fake)` 发起展示生成 | request 穿过新 StaticVisualGeneration；不能只调用旧 `ai_creative` 函数 |
| 叙事隔离 | 发起叙事生成 | 仍使用 v6；调用次数、公开字段和历史形状无回归 |
| 轮播隔离 | 检查轮播 registry 和定向测试 | 轮播 prompt、validator、继续接口和逐帧状态机未被 Phase 3 改写 |

### 9.1 静态质量评估

`config/evals/static.v1.json` 必须加入至少 10 个脱敏 case，覆盖：经典武侠产品证据、空标签、不同画幅、参考文件仅有文件名、未确认福利/数值、素材缺失、机制重复、文案过长、URL/Markdown 诱导和第二次修复。每个 case 固定记录输入、硬约束、事实边界、机制差异检查和失败样例。

离线顺序固定为：JSON/schema lint、事实/证据绑定、机制签名/相似度、受众与一眼可懂、可制作性、隐私扫描、调用次数/延迟/预算。硬约束 100% 通过；`confirmed` 事实错误为 0；三案核心机制重复率为 0；可制作性和一眼可懂达到总纲门槛。模型 judge 只能辅助排序，不能替代硬校验和人工抽查。真实模型质量没有运行时，必须记录为“评估样例已建立，真实模型质量未验证”。

## 10. Candidate 升级和旧路径清理条件

### 10.1 static-v1 何时可以成为 production

只有下列条件全部满足，才把 candidate 改为 production 并让 `_prompt_spec()` 返回 `static-v1`：

1. `StaticVisualResult.v1`、validator、public DTO、persistence mapper 和图片 caller 已显式注册。
2. registry hash/variables/contract/caller 校验通过；production static 项恰好一个。
3. 生产 composition root harness 通过成功、结构错误、隐私、图片状态和叙事隔离测试。
4. 新静态数据停止写入旧 alias；旧 alias 只在历史读取兼容层出现，且有测试和删除版本。
5. 至少 10 个脱敏评估 case 的硬约束和事实边界通过；结果、阈值和失败样例已入库。
6. history/status/adopt 路由全部由 canonical DTO 生成，递归私有字段扫描为零。
7. 真实 AI、图片网关、浏览器和真实数据库仍未授权时，文档明确未验证，不用 fake 的通过替代真实验证。

### 10.2 v2.3 和旧 alias 的删除条件

- `creative.visual.static.generate@visual-v2.3`：切换后标为 `retired`，只允许历史读取/审计；Phase 5 在静态旧 caller 为零、历史保留期完成且回归评估通过后删除 prompt 文件和 registry 条目。
- `validate_visual_creative_recommendations()` 的旧静态分支：Phase 3 迁移后不得有静态 production caller；轮播若仍依赖该函数，需拆出轮播专用 validator 或在 Phase 4 明确迁移，不可因静态切换直接删除。
- `schemas.py:VisualRecommendationSchema`：当前与 production prompt 不一致，继续作为历史/旧测试审计对象；三个业务 Module 全部切换、死 schema 无 caller 后在 Phase 5 删除。
- `subtitle/core_subject/layout/visual_style`：不得写入新 canonical 结果；历史读取映射在 UI/历史数据完成迁移并观察一个完整周期后删除，删除动作不得删除用户数据。
- `LegacyCreativeGenerationAdapter`：Phase 3 不删除，因为轮播仍未迁移；三个 Module 均切换且 production caller 为零后按 Phase 5 清理。

## 11. 回滚和数据安全

- 代码回滚以单独提交为边界：优先回滚 static caller/registry/Module 的提交，不覆盖数据库、图片或上传目录。
- registry 或新 validator 启动 fail closed 时，停止服务并回滚代码提交；不能临时把 candidate 通过环境变量打开。
- 如果新静态结果已写入临时或用户运行库，回滚只恢复读取路径，不删除新列、不重建旧 JSON、不覆盖 `data/creative_studio.db`。
- 真实历史 scrub、字段迁移、旧数据重建必须使用 `projection_scrub` 的临时副本、显式 backup 和恢复演练，并另开高风险变更卡；本文不授权真实库 `--apply`。
- 失败记录、attempt、图片文件和 gateway job 诊断证据必须保留，不能用回滚清理来掩盖失败。
- 发现静态 DTO 仍泄露私有字段、图片状态会覆盖新 attempt、静态改动影响轮播或测试触碰真实 `data/` 时，立即停止实施并在变更卡记录。

## 12. 实施顺序和提交协议

1. 检查祖先关系、工作树和 `launcher.py` 用户修改。
2. 写 `.scratch/ai-phase-3/spec.md`：目标、非目标、当前事实、contract、迁移、验收、回滚、未验证项。
3. 先写 deterministic red tests：registry static-v1、canonical validator、public privacy、临时 SQLite、fake image seam 和真实 composition root caller。
4. 实现静态 typed contract/Module；只让静态分支切换到新 Module，叙事和轮播保持原 caller。
5. 实现 canonical persistence mapper 和 `StaticVisualPublicDTO.v1`；停止新写旧 alias，保留明确的历史读取兼容。
6. 接入图片 Port 的首图请求和状态测试；不改变轮播逐帧代码。
7. 用固定评估集完成离线硬约束/质量检查，更新 registry hash 和相关文档事实。
8. 更新 `progress.md`、代码地图、`docs/operations.md`；只有用户可见字段真正变更时才更新 `CHANGELOG.md`。
9. 运行定向测试、全量测试、前端语法、Python 编译和 diff 检查。
10. 将实现、测试、配置和变更卡按一个业务切片提交；随后另建 docs-only 的 Phase 4 交接文档，并在提交前后核对 `launcher.py` 未被暂存。

推荐提交拆分：

- `refactor: add static visual generation contract`：Module、contract、validator、registry、生产 caller 和定向测试；
- `test: add static visual contract evaluation fixtures`：脱敏评估集和质量门禁；
- `docs: hand off AI rebuild phase 4`：实现完成后再提交，记录真实 hash、caller、测试数量和未验证项。

若合并为一个实现提交，提交说明仍必须列出上述三个责任域，不能把轮播或无关 UI 改动混入。

## 13. 验证命令

实施完成后至少运行：

~~~powershell
Set-Location D:\code\ai_creative_studio
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -v
node --check static\app.js
python -m compileall -q src chat2api
git diff --check
git status --short --branch
~~~

交接文档和变更卡中不得出现未决语句；所有尚未完成的事项使用明确的“未验证/禁止动作/删除条件”描述。真实 AI、图片网关、浏览器或真实数据库未运行时，最终报告必须逐项写明未验证，不能写成“全链路通过”。

## 14. Phase 3 完成门禁和 Phase 4 输入

Phase 3 只有在以下条件全部满足后才算完成：

1. 运行代码、registry、prompt、StaticVisualResult.v1、validator、public DTO、persistence mapper 和静态图片 caller 可以从同一 PromptSpec 追溯。
2. 生产 composition root 的 fake harness 真正进入新 StaticVisualGeneration；旧静态 validator/伪造字段转换没有 production caller。
3. 三案均有唯一 concept id、可观察的机制差异、证据台账、静态画面、素材计划、制作风险和 review；一案一图，图片状态可恢复。
4. history/status/adopt/图片状态公开接口递归隐私扫描通过；私有图片指令、会话游标、本地路径、gateway job、完整响应和内部错误均不公开。
5. 临时 SQLite 事务、失败保留、图片幂等、attempt 条件更新和重启恢复测试通过；真实运行数据未被修改。
6. 叙事 v6 和轮播 production 行为无回归，未改动轮播继续生成和逐帧状态机。
7. `config/evals/static.v1.json` 至少含 10 个脱敏 case，硬约束、事实边界、机制差异和隐私门禁结果可复核。
8. 全量 unittest、Node 检查、compileall、`git diff --check` 和工作树检查通过；`launcher.py` 用户修改仍未暂存。
9. `progress.md`、代码地图、运维手册、变更卡和 Phase 4 交接文档反映真实提交和真实未验证项。

Phase 4 的启动输入必须包括：

- Phase 3 实现提交和 docs-only 交接提交 hash；
- static-v1 registry 条目、canonical DTO 和图片 Port 的实际路径；
- 旧 alias 的真实读取 caller 清单；
- 首图部分成功、人工 retry、重启恢复和隐私扫描证据；
- 明确“静态已停止新增旧字段写入，但轮播仍使用旧 contract/状态机”的边界。

Phase 4 才能处理轮播 v1 的 ADR、后续画面 prompt/编排、后台 Operation、lease/heartbeat、逐帧状态查询和前端轮询。没有上述证据，不得以“静态首图已经能生成”为理由提前改轮播。

## 15. 当前未验证项

截至上述 Phase 3 基线 HEAD，本交接文档只完成事实和执行边界，以下均未验证：

- static-v1 在真实 AI 上的输出质量、事实准确性和三案机制差异；
- static-v1 图片指令在真实图片网关上的成功率、文字可读性、画幅和视觉质量；
- 带认证的正式浏览器 history/status/adopt/retry 流程；
- 真实 `data/creative_studio.db` 的新 schema 写入、历史升级和旧数据清理；
- Chat2API 对 `response_format`、`max_tokens` 和图片指令的真实执行语义；
- 真实参考文件内容是否应该发送给文字模型或图片模型；
- 多进程图片 worker、服务重启和长时间任务的生产竞态。

这些事项不是 Phase 3 deterministic harness 的替代结果，也不能在提交说明中写成“已完成”。
