# AI 重构 Phase 1 变更卡

- 日期：2026-09-03
- 状态：已完成，Phase 1 门禁通过
- 基线：`docs/ai-rebuild-master-plan.md` Phase 1；Phase 0 `e7412bb8fc9eb43e0cb89df58048ac6363c52239`

## 目标

- 建立唯一 `PromptRegistry` 和显式 `ContractRegistry`，追踪三个 production prompt 及 candidate/retired inventory。
- 通过 `TextModelPort`、`ImageModelPort` 和 deterministic fake 固定外部模型能力边界。
- 从 `create_application()` 让 fake 依赖穿过真实生成 caller、validator、公开投影和临时 SQLite。
- 以加法、幂等方式持久化 prompt/contract/model/provider/fingerprint/usage 元数据。

## 非目标

- 不修改正式 UI、HTTP URL、公开 DTO 既有形状或真实运行数据。
- 不切换 `static-v1`，不复活 retired 首帧/后续 prompt，不调用真实 AI、图片网关、浏览器或真实数据库写入。

## 当前事实

- production caller：`StudioApplication -> CreativeGenerationService -> HttpModelClient`，视觉图片走 `ImageJobRunner`。
- prompt 选择仍由 `WEB_ERP_AI_*` 环境变量和旧 loader 完成；`LegacyCreativeGenerationAdapter` 为无 model client 兼容路径。
- `generations` 已有 schema/input fingerprint/usage/error 字段，但没有 prompt/contract/provider 元数据列。

## 设计决策

- registry JSON 只存数据；contract、validator、projector 和 caller 通过 Python allowlist 显式注册。
- prompt hash 使用规范化模板 `strip().encode('utf-8')` 的 SHA-256；路径必须 resolve 到仓库 `config/` 内。
- production 每类只允许一个 `(id, version)`；candidate/retired 只能 inventory/audit 查询。
- 当前单阶段 policy：`draft` 最多 2 次、narrative 10000 tokens、visual 5000 tokens，失败统一 `model_output_invalid`。

## 验收与回滚

- 定向 registry/contract/port/harness 测试覆盖 fail-closed、生命周期、调用次数、私有字段和临时库隔离。
- 全量 unittest、Node 语法、compileall、diff check 通过；真实 AI/图片/浏览器/默认数据库均未验证或修改。
- 回滚以 Phase 1 Git 提交为边界；数据库新增 nullable/default 列可由旧代码忽略，registry 失败时不 bind server。

## 旧路径

- `LegacyCreativeGenerationAdapter`：`deprecated_since=phase-0`，仅现有无 model client caller；三个新 Module production caller 为零后 Phase 5 删除。
- 首帧/后续 loader 与环境 prompt selector：`deprecated_since=phase-1`，仅兼容读取/审计，禁止新 production caller；Phase 2/3/4 切换后分别删除。

## 完成证据

- `PYTHONPATH=src python -m unittest discover -s tests -q`：181 项通过。
- `node --check static\\app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 未调用真实 AI、图片网关或浏览器；未修改真实数据库、图片、上传文件或 `chat2api/.env`。
- Phase 1 实现提交：`1704bea`；当前分支为 `codex/tag-accordion-prototype`。
