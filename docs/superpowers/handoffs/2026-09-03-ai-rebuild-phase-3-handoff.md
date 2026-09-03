# AI 重构 Phase 3 交接文档

## 起点

- 项目：`D:\code\ai_creative_studio`
- 当前分支：`codex/tag-accordion-prototype`
- Phase 0：`e7412bb8fc9eb43e0cb89df58048ac6363c52239`
- Phase 1 registry/ports：`1704bea`
- Phase 1 fingerprint follow-up：`6dd91ef02a6dbdadccfa593b8c87f8d7570da48e`
- Phase 2 实现提交：`1c681cc2b82fcaaee9416111ccd15b96bdf4efe9`

开始前确认祖先关系：

```powershell
Set-Location D:\code\ai_creative_studio
git merge-base --is-ancestor e7412bb8fc9eb43e0cb89df58048ac6363c52239 HEAD
git merge-base --is-ancestor 1704bea HEAD
git merge-base --is-ancestor 6dd91ef02a6dbdadccfa593b8c87f8d7570da48e HEAD
git merge-base --is-ancestor 1c681cc2b82fcaaee9416111ccd15b96bdf4efe9 HEAD
```

接手时工作树中已有用户修改 `launcher.py`；不得重置、覆盖或把它纳入 Phase 3 提交。

## Phase 2 已完成事实

`src/creative_studio/narrative.py` 新增 `NarrativeGeneration`、`NarrativeInput`、`NarrativeResult` 和 `NarrativeOutputError`。canonical contract 固定 5 个故事、每个 2 个钩子、每个钩子 3 个场景，并校验 `concept_id` 唯一、故事/钩子差异、`evidence` 三个列表和 `risks`。旧形状 `story/hooks` 仅作为历史兼容输入归一化，不是新 prompt 的目标 contract。

生产调用链为：

```text
StudioApplication.generate
  -> CreativeGenerationService.generate
  -> CreativeGenerationService._generate_with_model_client
  -> NarrativeGeneration
  -> TextModelPort/ModelClient
  -> HttpModelClient
  -> chat2api /v1/chat/completions
```

叙事 registry 项为 `creative.narrative.generate@v6`，prompt 文件为 `config/prompts/narrative/v6.txt`，模板 hash 算法仍是规范化 UTF-8 内容 SHA-256。其映射为：`NarrativePromptInput.v1 -> NarrativeResult.v1 -> NarrativeResultValidator.v1 -> NarrativePublicDTO.v1`，caller 为 `narrative`，GenerationPolicy 为单一 `draft` stage、最多 2 次模型调用、`max_output_tokens=10000`。旧 `creative.narrative.generate@v5` 已标记 `retired`，不得新增 caller。

叙事 prompt 明确注入任务类型、任务描述、归一化标签、v2 游戏资料和参考文件名。第二批请求追加上一批故事摘要及“不得重复上一批故事或钩子”约束；format repair 追加上一次校验字段路径。公开投影继续由 `PublicResultMapper` 生成，旧 UI 读取 `story/hooks`，canonical 扩展字段按白名单公开。

## Phase 2 实际修改文件

- `.scratch/ai-phase-2/spec.md`：目标、非目标、设计、验收、回滚和门禁。
- `src/creative_studio/narrative.py`：叙事 Module、canonical validator、有限 repair、第二批上下文和 DTO 映射。
- `src/creative_studio/generation_service.py`：仅叙事分支切换到 Module；视觉分支保持原路径。
- `src/creative_studio/contracts.py`、`config/prompts/registry.json`：v6 contract 显式映射及 v5 retired inventory。
- `config/prompts/narrative/v6.txt`：叙事 v6 prompt。
- `config/evals/narrative.v1.json`：脱敏 deterministic 结构评估样例。
- `src/creative_studio/public_projection.py`：canonical narrative 公共字段白名单。
- `src/creative_studio/__init__.py`：导出叙事 Module 类型。
- `tests/test_narrative_generation.py`、`tests/test_prompt_registry.py`：生产入口和 registry 回归测试。
- `progress.md`、`项目代码地图.md`、`docs/operations.md`、`docs/ai-rebuild-master-plan.md`：同步当前事实。

## 验证证据

- `PYTHONPATH=src python -m unittest discover -s tests -q`：185 项通过。
- `node --check static/app.js`：通过。
- `python -m compileall -q src chat2api`：通过。
- `git diff --check` 及提交前暂存区检查：通过。
- 未调用真实 AI、图片网关或浏览器；未写入真实数据库、图片、上传文件或 `chat2api/.env`。

## 保留和删除条件

- `LegacyCreativeGenerationAdapter`、`validate_creative_recommendations()` 和旧 `schemas.py` 叙事 schema 仍保留给无 model client、历史和兼容测试；只有三个新业务 Module 均切换且 legacy production caller 为零后，才可在 Phase 5 删除。
- 旧 v5 prompt 只允许 registry inventory/deprecation/audit 读取；Phase 5 在无 caller 且迁移保留期结束后删除。
- 静态 candidate `creative.visual.static.generate@static-v1`、轮播 production、retired 首帧/后续 prompt 未修改，Phase 3 不得把轮播逻辑带入静态迁移。

## Phase 3 目标和边界

只完成静态展示类重构，不进入 Phase 4 轮播/图片状态机：

1. 将 `config/ai_visual_static_creative_prompt_v1.txt` 升级为 production PromptSpec，并建立 `StaticVisualGeneration` 与 `StaticVisualResult.v1`。
2. 统一静态输入、输出、validator、public DTO、持久化 mapper、图片任务 caller 和 contract harness；停止新数据伪造 `subtitle/core_subject/layout/visual_style` 别名。
3. 公开静态结果展示 `audience_tension/product_value/visual_mechanism/evidence/static_frame/asset_plan/review`，`image_generation_instruction` 只允许服务端图片 Port 使用。
4. 保持现有 UI 基本形状、HTTP URL、错误状态码和叙事/轮播生产分支不变。

开始 Phase 3 前必须重新阅读项目强制阅读清单、Phase 2 变更卡和本交接，并从 `create_application()` 追踪静态 production caller。先建立 `.scratch/ai-phase-3/spec.md`，再用 deterministic fake 和临时 SQLite 写 red tests；真实 AI、图片网关、浏览器和真实数据库写入仍需明确授权后才可验证。

Phase 3 完成后生成 Phase 4 交接文档；本交接不授权提前修改轮播或删除 legacy adapter。
