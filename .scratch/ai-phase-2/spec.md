# AI 重构 Phase 2 变更卡

- 日期：2026-09-03
- 状态：已完成，Phase 2 门禁通过
- 范围：叙事类生成 contract、module、生产调用、公开投影和测试

## 目标

- 建立 `NarrativeGeneration` 生产 Module 和 `NarrativeResult.v1` canonical contract。
- 让游戏资料和项目参考资料以明确、有界的输入进入叙事 prompt，并纳入生成指纹。
- 格式修复请求必须携带上一次校验错误及字段路径；第二批请求必须携带上一批摘要和显式去重约束。
- 叙事历史、采用和 HTTP 结果只通过 canonical public DTO 投影，保持现有 UI 字段形状兼容。
- 通过 deterministic fake、临时 SQLite 和固定输入验证 prompt、validator、DTO、持久化 metadata 来自同一 registry 项。

## 非目标

- 不修改静态展示、轮播、图片任务、认证、监听地址、真实数据库或 `chat2api/.env`。
- 不接入真实 AI、真实图片网关或浏览器，不删除视觉 legacy/retired 路径。
- 不改变现有 HTTP URL、成功包络、错误状态码和 UI 的基本字段形状。

## 当前事实

- 生产入口为 `StudioApplication.generate -> CreativeGenerationService.generate -> _generate_with_model_client`。
- 叙事 prompt 为 `config/ai_creative_prompt_v5.txt`，当前未声明 `game_info`；`load_ai_creative_game_info()` 已可读取 v2 游戏资料。
- 叙事校验为 `validate_creative_recommendations()`，当前只返回 `story/hooks/scenes`，未检查故事和钩子差异。
- 现有 registry 叙事项为 `creative.narrative.generate@v5`，输出 contract 为 `LegacyNarrativeResult.v5`。
- repository 的叙事历史和采用已经经过 `PublicResultMapper`，但 canonical 字段需要由叙事 Module 明确映射。

## 设计决策

- 新增 `narrative.py`，由 `NarrativeGeneration` 负责输入编译、模型调用策略、canonical validator 和 public DTO 映射；生成服务只负责 reservation、持久化和调用。
- `NarrativeResult.v1` 保留 5 个故事、每故事 2 个钩子、每钩子 3 个场景，并增加 `concept_id`、`audience_tension`、`product_value`、`evidence`、`risks`；旧 UI 通过显式 DTO 读取 `story/hooks`。
- 第一批 prompt 使用游戏资料、参考文件名和归一化标签；第二批 prompt 使用上一批公开摘要、故事/钩子去重约束，仍最多 2 次模型调用。
- registry 的叙事 production 项升级为 `v6`，旧 `v5` 保留为 retired inventory；validator/projector/caller 使用显式 allowlist，不动态导入。
- 真实 ChatGPT Web usage 继续标记为 `estimated` 或 `unavailable`；测试只使用 fake port、临时文件和临时 SQLite。

## 验收例子

- 固定样例返回 5 个 canonical 故事，每个 2 个明显不同钩子和 3 个场景；旧 UI DTO 仍只包含既有可见字段。
- prompt 中可见游戏资料和参考文件名；用户值中的模板符号按字面保留。
- 第一次格式错误后，第二次请求包含错误字段路径和修复指令；两次失败后错误为 `model_output_invalid`，字段路径精确到 canonical 字段。
- 第二批请求与第一批 prompt 不同，包含上一批摘要和“不得重复”约束；同一输入 fingerprint 不变但 batch index 和 run id 不同。
- 递归扫描 history/adopt/status DTO 不出现 prompt、会话游标、内部错误或本地路径。

## 风险与回滚

- canonical 字段扩展可能影响旧 UI；保留显式旧 DTO 映射和兼容读取，发现缺字段时回滚本次叙事 caller 到旧 adapter，不覆盖数据库。
- registry 版本切换失败时应用在 bind 前 fail closed；旧 prompt 仅保留 inventory，不作为新生产 caller。
- 数据库仅使用已有加法 metadata 列和临时 SQLite 测试，不执行真实库迁移；代码回滚不删除运行数据。

## 完成门禁

1. Narrative production PromptSpec 恰好一个 caller，contract、validator、DTO、persistence 可追溯。
2. `NarrativeResult.v1`、format repair、第二批去重和参考资料输入的生产入口 harness 通过。
3. 视觉分支和 retired loader 无新增 caller。
4. 全量 unittest、Node 语法、compileall、diff check 通过；真实 AI/图片/浏览器/真实数据库写入明确未验证。
5. 本卡、`progress.md`、代码地图、运维手册和 Phase 3 交接文档同步事实。

## 复核结论

- 规格轴：PASS。叙事 production caller、v6 registry、canonical contract、repair、第二批去重、公开 DTO 和保留条件与总纲一致；未进入静态/轮播迁移。
- 规范轴：PASS。修改集中在叙事责任域，使用临时 fake/确定性测试，未写入凭据或运行数据；`node --check`、`compileall` 和 `git diff --check` 通过。
- Critical/Important：无。真实 AI、图片网关、浏览器和真实数据库写入均未验证。
