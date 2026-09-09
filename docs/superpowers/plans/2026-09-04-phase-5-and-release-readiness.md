# Phase 5 及后续发布准备实施计划

> 该计划对应 [`2026-09-04-ai-studio-complete-roadmap-design.md`](../specs/2026-09-04-ai-studio-complete-roadmap-design.md)。执行时保持当前工作树已有修改，不回退 `launcher.py`、标签选择或 Phase 5 治理文件。

## 当前执行状态（2026-09-04）

- [x] 任务 1-3：canonical `GenerationRun`/`RunStorePort`、SQLite adapter、三个 production Module 和 retired caller audit。
- [x] 任务 4：参考资料 metadata、受控摘要和公开投影边界。
- [x] 任务 5-7 第一轮：离线 fixture/report schema、脱敏观测、备份恢复 CLI、发布 gate/runbook。
- [x] 评测硬约束 lint、失败分类聚合和 deterministic fake 独立证据输出。
- [x] 备份 manifest 篡改/恢复失败回归以及引用完整性 smoke。
- [x] 参考资料 prompt 注入端到端隐私回归。
- [x] 只读备份 retention plan；自动删除仍需单独授权和变更卡。

以下任务描述既是已完成工作的索引，也是剩余门禁的可执行清单。

## 任务 1：建立 canonical 运行与参考资料类型

- **文件**：`src/creative_studio/generation_models.py`、新测试。
- **先测**：`GenerationRun` fingerprint、`ReferenceAsset` metadata、公开/私有字段边界、协议 fake。
- **实现**：冻结 dataclass、`RunStorePort`、`ReferenceAssetPort`、`ObservabilityPort`；明确 `safe_summary` 和 extraction status。
- **验收**：定向 unittest 通过，类型可被三个 module 导入。

## 任务 2：SQLite RunStore/ReferenceAsset adapter

- **文件**：`repository.py`、迁移 helper、新测试。
- **先测**：run round-trip、失败/过期、request id 幂等、资产 digest/MIME/大小和项目归属。
- **实现**：只做 additive schema；旧行兼容读取；禁止直接返回 raw SQL row。
- **验收**：临时 SQLite 契约测试通过；现有全量测试无回归。

## 任务 3：接入三个 production module 并清理旧 caller

- **文件**：`generation_service.py`、`app.py`、`ai_creative.py`、`schemas.py`、`config/prompts/registry.json`、相关测试。
- **先测**：production composition root 使用 canonical store；轮播不调用 `complete_visual_generation()`；旧 symbol caller audit 为零。
- **实现**：延迟构造/移除 `LegacyCreativeGenerationAdapter`，统一 canonical persistence，收窄旧 mapper 为历史读取；更新 retired inventory。
- **验收**：registry caller audit、production harness、全量测试通过。

## 任务 4：参考资料注入和隐私回归

- **文件**：`prompting.py`、上传/项目 API、`PublicResultMapper`、测试。
- **先测**：受控摘要注入、绝对路径剔除、超限/MIME/提取失败、digest 改变 fingerprint。
- **实现**：在请求边界读取 reference asset metadata/content；只注入 allowlist 摘要。
- **验收**：隐私扫描和 prompt contract 通过；公开 DTO 无私有字段。

## 任务 5：质量评测与 observability harness

- **文件**：`src/creative_studio/evaluation_harness.py`、`observability.py`、`config/evals/`、测试、`docs/ai/quality-evaluation.md`。
- **先测**：报告 schema、硬约束 lint、调用/延迟/失败分类聚合、日志脱敏。
- **实现**：固定脱敏 JSONL、baseline/candidate/repair_failure 模板和 validate-only CLI；真实供应商路径默认拒绝。
- **验收**：至少三份报告 schema 通过；fake 与真实未验证边界清楚。

## 任务 6：备份、恢复和 scrub 临时演练

- **文件**：`src/creative_studio/backup.py`（create/restore CLI）、测试、`docs/project-rules/operations.md`。
- **先测**：manifest/hash、SQLite backup、图片/上传归档、恢复到新目录、坏 manifest 拒绝。
- **实现**：dry-run 默认；显式输出目录；不允许目标为默认运行库；保留策略可配置。
- **验收**：临时副本 backup -> restore -> read smoke -> projection scrub fixed point。

## 任务 7：发布门禁、文档和回滚 runbook

- **文件**：`docs/release/`、README、代码地图、operations、progress、CHANGELOG。
- **先测**：gate 命令在临时目录成功；文档链接和 registry 事实检查。
- **实现**：发布前/发布中/发布后/回滚步骤，明确观察周期和高风险人工动作。
- **验收**：全量命令通过；文档没有把未验证能力写成完成。

## 最终验证

```powershell
python -m unittest discover -s tests -v
node --check static/app.js
python -m compileall -q src chat2api
python -m creative_studio.phase5_governance
python -m creative_studio.evaluation_harness --validate-only
python -m creative_studio.backup --dry-run --output .scratch/backup-smoke
git diff --check
```

完成前必须说明：真实 AI/图片网关、认证浏览器、多进程竞态、真实库 `--apply`、恢复覆盖和网络开放仍未执行的项目，以及对应的单独变更卡入口。
