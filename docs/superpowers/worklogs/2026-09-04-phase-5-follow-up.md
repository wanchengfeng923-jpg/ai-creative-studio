# Phase 5+ 后续工作记录

日期：2026-09-04  
范围：`D:/code/ai_creative_studio` 当前工作树  
基线：`docs/ai-rebuild-master-plan.md`、`progress.md`、`docs/superpowers/specs/2026-09-04-ai-studio-complete-roadmap-design.md`

## 目标

在已完成的 Phase 5 canonical seam、参考资料 metadata、评测/观测、备份恢复和发布 gate 之上，补齐剩余的可自动验证门禁。重点是让失败状态可诊断、私有边界可回归、备份失败可恢复，同时不把 deterministic fake 证据写成真实模型质量结论。

## 已实施变更

### 1. 评测硬约束与证据分层

文件：`src/creative_studio/evaluation_harness.py`、`tests/test_evaluation_harness.py`、`docs/ai/quality-evaluation.md`

- `lint_evaluation_result()` 对 `complete`/`failed` 结果强制要求 `hard_constraint_pass_rate`、非负 `calls`、非负 `latency_ms`、固定失败分类和 `evidence_type`。
- 报告结果同样递归拒绝 `prompt`、`content`、`path`、`body`、密钥和供应商游标等私有字段；未知质量字段不会被静默当作证据。
- `aggregate_failure_classifications()` 只接受 registry 中的四种失败分类，并将多个结果聚合成固定键集合。
- `lint_case_output()` 先运行 narrative/static/carousel canonical validator，再递归检查图片指令、供应商游标、路径、raw response 和 lease token 等私有字段。
- `evaluate_case_outputs()` 返回 case 数、硬约束通过率和可聚合失败证据。
- `--deterministic-fake-summary` 输出独立的 `deterministic-contract-evidence.v1`，其中 `quality_claim=contract_only`；该输出不占用 baseline/candidate/repair_failure 槽位。
- `validate_evaluation_assets()` 现在会对已生成的非 `not_run` 报告执行严格 lint，防止宽松 schema 放行不完整质量报告。

### 2. 备份恢复完整性

文件：`src/creative_studio/backup.py`、`tests/test_backup.py`、`docs/operations.md`、`docs/release/runbook.md`

- manifest 在恢复前检查相对路径、禁止 `..`、重复路径、非负整数大小和 64 位小写 SHA-256。
- 恢复写入目标同级 staging 目录；manifest/hash/SQLite/引用检查任一失败都会清理 staging，不留下半成品目标。
- `validate_reference_integrity()` 校验 `project_files` 的项目目录归属和文件存在性，并检查成功 `visual_items`/`display_frames` 的图片引用位于 images 根目录且实际存在。
- 成功恢复结果必须同时带 `verified=true` 和 `references_verified=true`。
- `plan_backup_retention(root, keep_latest=N)` 提供只读保留策略计划，列出 `keep`、`eligible_for_removal` 和 `invalid`；没有默认删除动作，避免误删唯一备份。
- 真实运行目录仍禁止直接覆盖；测试只使用临时 SQLite、图片和上传目录。

### 3. 参考资料隐私与路径边界

文件：`src/creative_studio/repository.py`、`src/creative_studio/reference_assets.py`、`src/creative_studio/generation_service.py`、`tests/test_generation_models.py`、`tests/test_reference_prompt_integration.py`

- repository 和 filesystem adapter 都以项目目录为边界解析 `stored_name`，跨项目或路径穿越统一返回 `reference_asset_path_invalid`。
- 生成 prompt 只使用参考文件 basename 和受控摘要；摘要中的 URL、绝对路径以及 `image_prompt`/`stored_name`/会话游标等赋值被替换为安全占位文本。
- 端到端测试从 `CreativeGenerationService.generate()` 记录实际模型请求，确认摘要仍可提供产品证据，但不会携带原始二进制、绝对路径或私有字段；公开项目 projection 同时确认不出现 `safe_summary` 和 `stored_name`。

### 4. 文档事实同步

- 收口设计文档改为描述当前 adapter/轮播 caller 状态。
- 总纲、质量评测、运维手册、发布 runbook 和 `progress.md` 已记录 254 项测试、评测证据分层、恢复引用校验和未授权事项。
- 详细执行计划 [`docs/superpowers/plans/2026-09-04-phase-5-and-release-readiness.md`](../plans/2026-09-04-phase-5-and-release-readiness.md) 增加剩余门禁清单。

## 验证证据

```text
python -m unittest discover -s tests -q
Ran 254 tests; OK

python -m creative_studio.release_gate
unittest: ok
node: ok
compileall: ok
governance: ok
evaluation: ok
backup-dry-run: ok
diff-check: ok

python -m creative_studio.evaluation_harness --validate-only
{"cases": 30, "reports": 3, "use_cases": 3}

python -m creative_studio.evaluation_harness --deterministic-fake-summary
{"evidence_type": "deterministic_fake", "fixture_summary": {"cases": 30, "reports": 3, "use_cases": 3}, "notes": "Deterministic fake validates contracts and privacy only; it is not a model quality result.", "quality_claim": "contract_only", "schema_version": "deterministic-contract-evidence.v1"}
```

本次 backup dry-run 只读扫描默认运行库；没有写入 `data/creative_studio.db`、`data/images/`、`data/uploads/`，没有执行真实库 projection scrub `--apply`，没有修改 `chat2api/.env`，没有调用真实 AI/图片供应商。

## 后续顺序与停止条件

1. 继续保留旧 adapter/schema/prompt 文件，直到三个 production caller 保持为零并完成观察期、历史读取回归和单独删除变更卡。
2. 真实供应商评测必须另用脱敏 fixture、独立输出目录、预算和报告，不得将 deterministic fake summary 改写为 candidate 质量结果。
3. 真实库 scrub、恢复覆盖、定时备份、带认证浏览器和多人内网部署必须各自具备备份、回滚、负责人和用户确认；在此之前只运行本记录中的 dry-run/smoke 命令。
