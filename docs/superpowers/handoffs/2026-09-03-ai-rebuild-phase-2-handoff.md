# AI 重构 Phase 2 交接文档

## 起点

- 项目：`D:\code\ai_creative_studio`
- 分支：`codex/tag-accordion-prototype`
- Phase 0：`e7412bb8fc9eb43e0cb89df58048ac6363c52239`
- Phase 1：`1704bea`
- 本文件提交后，以 `git log -1 --format=%H` 获取 docs-only 提交 hash。
- 祖先检查：`git merge-base --is-ancestor e7412bb8fc9eb43e0cb89df58048ac6363c52239 HEAD` 与 `git merge-base --is-ancestor 1704bea HEAD` 均须退出 0。

## Phase 1 事实

`config/prompts/registry.json` 登记六个 `(id, version)`：叙事 `creative.narrative.generate@v5`、当前静态 `creative.visual.static.generate@visual-v2.3`、轮播 `creative.visual.carousel.plan@visual-carousel-v1` 为 production；静态 `static-v1` 为 candidate；首帧/后续 `v1` 为 retired。模板 hash 算法是 `sha256(Path.read_text(encoding='utf-8').strip().encode('utf-8'))`。

`src/creative_studio/prompt_registry.py` 负责 PromptSpec/GenerationPolicy 与路径、文件、变量、hash、生命周期校验；`contracts.py` 维护显式 schema/validator/projector/caller allowlist；`model_ports.py`、`provider_capabilities.py`、`ports.py` 提供 Text/Image Port 和 deterministic fake。`create_application()` 在构造应用时一次加载 registry，并将 registry 注入 `CreativeGenerationService`。`repository.py` 以幂等加法列保存 prompt id/version/hash、input/output schema version、model/provider；旧记录保留空值。

真实 caller 仍是 `StudioApplication.generate -> CreativeGenerationService -> HttpModelClient -> chat2api`，图片仍由 `ImageJobRunner` 进入网关。Phase 1 未切换 UI 或用户可见输出。`LegacyCreativeGenerationAdapter` 保留为兼容 caller，`deprecated_since=phase-0`，三个替代 Module active 且 legacy production caller 为零后在 Phase 5 删除。首帧/后续 loader 与环境 prompt selector 为 `phase-1`，仅 inventory/deprecation/audit 读取，禁止新 caller。

验证：`PYTHONPATH=src python -m unittest discover -s tests -q` 为 181 项通过；`node --check static\\app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。未调用真实 AI、图片网关或浏览器；未写入真实数据库、图片、上传文件或 `chat2api/.env`。

## Phase 2 任务和边界

只执行总纲 Phase 2 叙事类重构，不进入 Phase 3。建立 `NarrativeGeneration` Module 和 `NarrativeResult.v1`；明确注入游戏资料/参考资料；format repair 必须携带校验错误；第二批必须有显式去重上下文；公开 DTO 只消费 canonical narrative contract；prompt、validator、DTO、persistence 必须来自同一 registry 项。保持现有 UI 基本形状、HTTP URL、错误状态码和视觉 production 分支不变；不接入静态 candidate、轮播重构、真实 AI、真实数据库迁移或删除 legacy adapter。

开始前完整阅读 `AGENTS.md`、`progress.md`、`项目代码地图.md`、`docs/operations.md`、`docs/ai-rebuild-master-plan.md`、`CODE_STYLE.md`、`CONTEXT.md`、Phase 1 变更卡和本文件。先建立 `.scratch/ai-phase-2/spec.md`，再从 `create_application()` 用 deterministic fake 写 red tests。至少覆盖 5 个故事、每个 2 个不同钩子、每钩子 3 个场景、游戏资料进入 prompt、第二批去重、错误字段路径、递归私有字段扫描和元数据持久化。质量评测使用固定脱敏集；真实 AI 未授权时明确未验证。

## Phase 2 门禁

1. Narrative production PromptSpec 恰好一个 caller，contract、validator、public DTO、persistence 可追溯。
2. `NarrativeResult.v1` 硬约束和旧 UI 映射通过 production harness。
3. 第二批 prompt/context 与第一批不同，调用次数和 repair 上限由 GenerationPolicy 控制。
4. history/adopt/status 无私有字段，错误保留稳定 code/phase/field_path/retryable/trace_id。
5. 视觉分支、静态 candidate、retired loader 没有新增 caller。
6. 全量 unittest、Node 语法、compileall、diff check 通过，且测试只使用临时 SQLite/fake/fixed clock。
7. Phase 2 提交后生成 Phase 3 交接文档；本阶段不得进入 Phase 3。
