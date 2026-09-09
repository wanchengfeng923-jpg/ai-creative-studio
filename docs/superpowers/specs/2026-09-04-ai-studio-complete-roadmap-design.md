# AI Creative Studio 全量收口与发布路线设计

- 日期：2026-09-04
- 状态：已确认，作为 Phase 5 及后续工作的执行基线
- 适用范围：AI 生成链路、参考资料、持久化、质量评测、备份恢复、多人内网准备、发布与回滚
- 基线：`docs/ai-rebuild-master-plan.md`、当前工作树和 `progress.md`

## 1. 目的

本设计把总纲中尚未完成的 Phase 5 及后续任务拆成可验证的工作包。目标不是只让页面继续工作，而是让每个生产用例都具备唯一契约、唯一 caller、可替换的远程接口、可追溯运行记录、公开/私有边界、质量证据和可回滚的运维路径。

## 2. 当前事实

- 三个生产用例已分别接入 narrative、static、carousel registry/module；Phase 4 的轮播 operation、lease、heartbeat、恢复和前端轮询已有 deterministic fake 测试。
- `LegacyCreativeGenerationAdapter`、旧 `schemas.py`、旧字段 mapper 和 retired prompt inventory 仍作为兼容/历史 seam 保留，但服务构造不会默认实例化 adapter；三个 production caller 均已切换到 canonical Module/RunStore。
- 轮播生产路径已不再调用 `complete_visual_generation()`；该入口仅保留给历史/兼容读取和显式 legacy 测试，生产 caller 审计为零。
- 参考资料目前主要传文件名；没有统一的 `ReferenceAssetPort`、digest、MIME、提取状态和受控摘要模型。
- 生成记录没有独立的 `GenerationRun`/`RunStorePort` seam，`generations`、`visual_items`、`display_frames` 的事实边界仍需收口。
- 备份/恢复工具已支持 SQLite 在线备份、文件 manifest/hash、临时目录恢复和 dry-run；真实运行库仍只做过只读 projection scrub dry-run，不得在本工作中直接写入。真实模型/图片供应商质量报告仍未执行。
- `launcher.py` 的 `WEB_BIND_HOST = "0.0.0.0"` 是用户已有修改，必须保留；本设计不授权修改监听地址、防火墙、HTTPS 或外部暴露。

## 3. 目标架构与不变量

### 3.1 目标模块

```text
HTTP -> StudioApplication -> CreativeGenerationService
                         -> ReferenceAssetPort
                         -> Prompt/Contract registry
                         -> TextModelPort
                         -> RunStorePort
                         -> ImageJobPort
                         -> ObservabilityPort
```

`ReferenceAssetPort` 只负责项目参考资料的受控读取；`RunStorePort` 是生成运行的权威业务 seam；SQLite、文件系统、chat2api 和日志系统均为适配器。业务模块不得依赖 SQL 行结构、网关响应格式或文件绝对路径。

### 3.2 必须保持的不变量

1. 一次正常生成只有一次 planner 模型调用；格式修复最多一次，调用次数由 registry policy 显式声明。
2. 空白参考输入是合法 brief，不触发隐式的 AI 补全流程。
3. `GenerationRun` 保存输入快照、prompt id/version/hash、schema、模型、供应商、参考资料版本和 usage/trace 元数据。
4. 公开 DTO 只从白名单重建，永不直接返回 `image_prompt`、供应商游标、原始错误、上传路径或完整参考文件正文。
5. 轮播每个方案拥有自己的 `frames`；固定屏数必须匹配，AI 屏数为每套方案独立的 2 至 5。
6. 图片任务用稳定 request id 幂等；旧 worker 不能覆盖新 attempt；恢复只处理明确失活的 lease。
7. 备份恢复先在临时副本完成；真实库、真实图片和上传目录的写入/覆盖必须有单独变更卡和用户确认。
8. 生产 registry 中每个 active prompt 恰有一个 validator、一个 DTO 和至少一个可定位 caller；retired 项无运行时 caller。

## 4. 分阶段工作包

### P5：清理和 canonical seam

**范围**：旧 adapter、死 schema、旧 prompt loader、旧字段 mapper、轮播旧 persistence、`GenerationRun` 和 `RunStorePort`。

**交付物**：

- `generation_models.py` 中冻结的 `GenerationRun`、`ReferenceAsset`、`ReferenceAssetContent`、`RunStorePort`/`ReferenceAssetPort` 协议。
- SQLite adapter 以 additive migration 保存 `run_json`/`context_json`/request id；现有历史读取保持兼容。
- 三个 production module 通过 canonical run/store 写入；`complete_visual_generation()` 只保留兼容读取或被删除。
- 旧 adapter/schema/loader/mapper 删除或明确 retired inventory，测试和 registry caller audit 更新。

**门禁**：`rg` 生产源码无旧 caller；registry audit 通过；canonical run round-trip、失败/过期/幂等测试通过。

### P6：参考资料和数据边界

**范围**：上传资料 metadata、digest、MIME、大小、提取状态、摘要、权限边界和提示词注入。

**交付物**：

- `ReferenceAssetPort` SQLite/filesystem adapter；只允许项目内资产被读取。
- `ReferenceAssetContent` 采用 `asset_id`, `sha256`, `mime_type`, `size_bytes`, `extraction_status`, `safe_summary`，正文按用例 allowlist 截断。
- prompt compiler 只注入文件名和受控摘要；不把绝对路径、原始二进制或私有字段放入模型响应/公开 DTO。
- digest 变化会改变 input fingerprint；不支持的 MIME、超长内容和提取失败有稳定错误分类。

**门禁**：metadata/隐私/指纹测试、路径穿越测试、大小/MIME 限制测试通过。

### P7：质量评测与可观测性

**范围**：固定脱敏评测集、硬约束 lint、质量维度、失败分类、trace 和 metrics。

**交付物**：

- 每个生产用例至少 10 个 JSONL case，版本化 baseline/candidate/repair_failure 报告。
- `evaluation_harness` 输出解析、数量、事实、重复、私有字段、调用次数、延迟和 token/cost 统计。
- `ObservabilityPort`/结构化日志只记录 request/run/operation id、阶段、状态、错误分类、usage 和延迟，不记录 prompt、正文、密钥或路径。
- 真实供应商评测命令默认 dry-run/显式授权；deterministic fake 证据不得冒充真实质量结论。

**门禁**：硬约束 100%；确认事实错误为 0；差异、可制作性和清晰度达到总纲阈值；失败分类可聚合查询。

### P8：备份、恢复和多人内网准备

**范围**：数据库、图片、上传文件的一致性备份与临时恢复；配置模板、健康检查、单机到内网的准备性工作。

**交付物**：

- `tools/backup.py`（或项目等价 CLI）支持 manifest、SHA-256、SQLite 在线备份、图片/上传目录归档、保留策略和 dry-run。
- `tools/restore.py` 只恢复到显式指定的临时目录；校验 manifest、数据库可读、项目/图片/上传引用完整。
- 启动/发布检查命令验证 registry、迁移、目录权限、端口冲突、凭据存在性和备份新鲜度。
- 多人内网只做配置/认证/项目归属设计文档和测试 seam；不自动开放端口、不安装服务、不修改凭据。

**门禁**：临时副本 backup -> restore -> scrub/read smoke 固定点通过；真实库仍保持只读，除非另有变更卡。

### P9：发布、回滚和文档门禁

**范围**：发布清单、迁移顺序、回滚演练、文档事实优先级、版本化变更记录。

**交付物**：

- `docs/release/` 发布 runbook、回滚 runbook、变更卡和验收记录模板。
- CI/local gate：全量 unittest、Node syntax、compileall、diff check、registry audit、evaluation schema、backup smoke。
- `README.md`、`docs/project-rules/项目代码地图.md`、`docs/project-rules/operations.md`、`progress.md` 只引用当前事实；历史内容转为链接。
- 发布步骤明确 additive migration、切读/停旧写、观察周期、失败分类、回滚点和数据不可覆盖边界。

**门禁**：文档互相不矛盾；所有检查命令可在干净临时环境复现；未验证的真实外部能力明确列出。

## 5. 回滚策略

- 代码：按 P5-P9 工作包分提交；功能切换使用显式配置/registry 版本，旧历史读取器在保留期内只读。
- 数据库：只允许 additive migration；任何 scrub/restore 先复制并 hash，真实库恢复必须停止服务、独立备份并取得确认。
- 备份：恢复到新目录后先做只读 smoke，禁止直接覆盖运行目录。
- 网络与凭据：本路线不修改监听、防火墙、HTTPS、服务安装或 `chat2api/.env`；如需执行，另建高风险变更卡。

## 6. 验收命令

```text
python -m unittest discover -s tests -v
node --check static/app.js
python -m compileall -q src chat2api
python -m creative_studio.phase5_governance
python -m creative_studio.evaluation_harness --validate-only
python -m creative_studio.backup --dry-run --output .scratch/backup-smoke
git diff --check
```

真实 AI、真实图片网关、认证浏览器、多进程压力、真实数据库 `--apply` 和网络开放不属于默认验收，必须单独记录授权、备份、回滚和结果。
