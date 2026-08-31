# AI 软件项目管理与工程流程：面向 AI 创意工作台的最小实践

- 研究日期：2026-08-31
- 适用对象：第一次维护 AI 软件、主要在 Windows 单机上工作的开发者
- 研究范围：需求和范围、Git 与版本、环境/密钥、测试与 AI 输出评估、可观测性、发布/回滚、备份、依赖与安全、文档和日常节奏
- 资料原则：优先采用标准组织、平台拥有者和项目官方文档；链接均为一手来源。

## 先执行这套最小流程

每次改动都按下面的 8 步走。它适合当前仓库的本地 Python HTTP 服务（`8775`）、独立 `chat2api` 网关（`8780`）、SQLite 和本地图片/上传目录；不要求先引入登录、云端 CI 或新的业务框架。

1. **写一张变更卡**：一句话目标、明确不做什么、验收例子、风险和回滚办法。AI 生成质量不以“看起来不错”作为唯一验收条件。
2. **建分支**：从 `master` 建 `codex/<短名>` 分支；一个分支只解决一张变更卡。完成后自测，再合并回 `master`。这种短分支、可审查的工作流与 GitHub Flow 的建议一致（[GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)）。
3. **锁定输入**：记录提示词文件版本、模型名、关键环境变量（不记录密钥）、参考数据版本和随机性参数。提示词或模型改变时，视为需要重新评估的变更。
4. **先跑确定性检查**：
   ```powershell
   $env:PYTHONPATH = "D:\code\ai_creative_studio\src"
   python -m unittest discover -s tests -v
   node --check static\app.js
   python -m compileall -q src chat2api
   ```
5. **再跑 AI 评估集**：用一小组脱敏、固定的输入样例，检查结构完整性、硬性约束、拒答/安全和人工可接受度；把结果和提示词/模型版本一起保存。OpenAI 建议用带人工标准答案的数据集、评分器和可重复评估运行来开发，而非凭单次示例判断（[Working with evals](https://developers.openai.com/api/docs/guides/evals)；旧版说明见 [Evals](https://platform.openai.com/docs/guides/evals)）。
6. **本机冒烟**：双击启动器，确认 `127.0.0.1:8775` 页面、`/health`、一次文本生成、一次图片任务和失败重试；确认没有把服务绑定到局域网地址。当前项目 README 已声明只监听回环地址。
7. **记录与发布**：更新 `CHANGELOG.md`（若尚未建立则在首次发布时创建），使用 `MAJOR.MINOR.PATCH` 版本；提交信息说明“做了什么/为什么”。SemVer 定义了版本号与兼容性规则（[Semantic Versioning 2.0.0](https://semver.org/)），Keep a Changelog 规定按 Added/Changed/Fixed/Removed 组织变更（[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)）。
8. **备份后再升级**：关闭服务或使用 SQLite Online Backup API 导出 `data/creative_studio.db`，同时备份 `data/images/` 与 `data/uploads/`；保留最近 7 份日备份和 4 份周备份，并实际恢复一份验证。SQLite 官方说明 Online Backup API 可在数据库运行时复制快照（[SQLite Online Backup API](https://sqlite.org/backup.html)）。

## 1. 需求与范围：先定义“能证明的结果”

### 面向小白的写法

一张变更卡至少包含：

- **用户和场景**：谁在什么页面、用什么输入、要完成什么决定。
- **范围内/范围外**：例如“本次只改展示类生成，不增加账号、多人协作或 ERP 数据读写”。
- **验收样例**：给出输入、期望字段/数量/错误提示；AI 输出用评分规则表达。
- **风险与负责人**：隐私、提示词注入、成本、超时、图片磁盘占满等。
- **停止条件**：出现什么情况必须暂停发布（例如评估集关键约束通过率下降）。

这种先识别用途、影响和风险，再测量和处理的顺序对应 NIST AI RMF 的 Govern、Map、Measure、Manage 四项功能（[NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework)；[RMF PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)）。NIST Playbook 的 Measure 条目要求定义指标、可接受界限、部署前后测试并记录事件（[Measure](https://airc.nist.gov/airmf-resources/playbook/measure/)）；Manage 条目要求部署后监控、事件响应、恢复和变更管理（[Manage](https://airc.nist.gov/airmf-resources/playbook/manage/)）。生成式 AI 特有的错误、数据泄露和提示词注入风险可参考 NIST 的 GenAI Profile（[NIST AI 600-1 PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)）。

### 当前项目的最小范围基线

- 保留现有范围：创意项目 CRUD、参考文件名、展示/叙事两类生成、图片异步任务、历史和采用/替换。
- 明确边界：无登录、无人员/审核/任务分配、无视频库/投放数据；不读取或写入 ERP 数据库。
- 每张变更卡写出“不改变数据合同”的兼容要求；若修改 SQLite 表或 API 响应，必须提供迁移或回滚步骤。

## 2. Git、版本和变更记录

- `master` 保持可运行；功能、提示词和依赖升级都走短分支和合并审查。GitHub Flow 的核心是从默认分支创建分支、提交小改动、打开合并请求、通过检查后合并（[GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)）。
- 提交应可独立解释，例如 `feat: add visual eval cases`、`fix: reject invalid image job state`。不要在提交中放 `.env`、访问令牌、真实用户上传或数据库文件。
- 版本规则：破坏 API/数据合同为 MAJOR；向后兼容功能或提示词行为变更为 MINOR；错误修复和不改变合同的依赖补丁为 PATCH（[SemVer](https://semver.org/)）。模型、系统提示词或评估标准变化至少记录为 MINOR 级别的行为变更，除非已证明仅修复错误。
- `CHANGELOG.md` 只记录用户/维护者可感知的 Added、Changed、Fixed、Removed，并在发布前把版本、日期、评估结果和已知限制写清楚（[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)）。

## 3. 环境、配置和密钥

当前启动器从 `chat2api/.env` 读取 `CHATGPT_CONTROL_TOKEN`，再设置 `WEB_ERP_AI_*` 环境变量；`.env` 和运行数据已写入 `.gitignore`。这是一种可接受的单机起点，但必须把“配置”和“秘密”分开：

- 可提交：端口、超时、提示词**文件路径**、提示词版本、默认模型名称、示例 `.env.example`（值用占位符）。
- 不可提交：`CHATGPT_ACCESS_TOKEN`、`CHATGPT_REFRESH_TOKEN`、`CHATGPT_SESSION_COOKIE`、控制令牌、真实上传和数据库。GitHub 明确建议把敏感值放入加密 secrets，不要在工作流或日志中硬编码（[Using secrets in GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)）。
- 启动时检查：缺少 `.env`、令牌为空、端口不是 `127.0.0.1` 时直接失败并给出修复提示；日志只显示变量名和布尔状态，不显示值。
- 权限最小化：网关控制接口使用高强度随机令牌；仅在本机回环监听。OWASP 将失效的访问控制、敏感信息泄露和不安全插件/工具调用列为 LLM 应用的核心风险（[OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)）。
- 轮换方式：更换令牌后重启两个进程并做一次 `/health`、文本和图片冒烟；若令牌疑似泄露，先撤销/更换，再检查 Git 历史和日志。

## 4. 测试与 AI 输出评估

### 四层测试

1. **单元测试**：SQLite 仓储、输入校验、批次数上限、图片任务状态机；使用临时数据库，不触碰真实 `data/`。
2. **接口/集成测试**：启动本地服务后测试健康检查、超时、网关不可用、重复提交和重试；网关调用用假服务器或录制夹具，避免消耗真实额度。
3. **AI 评估集**：每类任务至少 20 个固定样例，覆盖正常、空字段、超长文本、恶意指令、敏感内容和模型拒答。评估结果保存 `case_id`、输入摘要、模型/提示词版本、原始响应哈希、各项分数和人工备注。OpenAI 的评估指南建议建立代表性数据集、定义明确的目标指标、持续运行回归并检查评估器与人工判断的一致性（[OpenAI Evals](https://platform.openai.com/docs/guides/evals)）。
4. **人工抽检**：每次发布抽检固定比例，重点看事实性、格式、品牌/受众约束和安全；人工反馈转成新的评估样例，而不是只留在聊天记录里。NIST GenAI Profile 建议对生成内容进行来源、质量和风险评估（[NIST AI 600-1 PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)）。

Anthropic 的 agent 工程总结建议先采用最简单的提示词链或工作流，只有在确有收益时才增加自主 agent、工具和多步循环（[Building effective agents](https://www.anthropic.com/research/building-effective-agents)）。其评估指南进一步建议多轮 agent 保存完整 transcript、工具调用和最终环境结果，并用多次 trial、代码/模型/人工评分器同时覆盖能力与回归（[Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)）。当前工作台因此应把“单次文本生成 + 受控异步图片任务”作为默认架构；新增工具调用或自动循环时，必须在变更卡中说明权限边界、停止条件、超时和额外评估样例。

### 建议的通过门槛（项目自定，可逐步收紧）

- JSON/字段解析成功率 100%；数量和批次硬限制 100%。
- 关键安全用例无高风险输出；提示词注入测试不得越权调用本地文件、网络或控制接口（OWASP 的 Prompt Injection 说明见 [LLM01](https://owasp.org/www-project-top-10-for-large-language-model-applications/)，防护建议见 [Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)）。
- 质量评分低于基线或失败率、延迟、成本明显回归时阻止发布；阈值和样例版本写入变更卡。

## 5. 可观测性：能回答“发生了什么”

当前应用是本机单用户系统，不必立即上复杂监控平台；先写结构化、脱敏的本地日志：

- 每个请求有 `request_id`；记录路由、成功/失败、错误类别、耗时、重试次数、模型、提示词版本、输入/输出 token（如供应商提供）和图片任务 ID。
- 不记录访问令牌、完整提示词中的个人信息、上传文件内容或完整模型响应；需要复现时保存脱敏样例和哈希。
- 每日查看四个信号：请求成功率、P95 延迟、AI 网关错误/超时率、磁盘剩余空间；异常时保留对应 `request_id` 的日志和评估结果。
- 用 DORA 的五项交付指标（变更前置时间、部署频率、部署失败恢复时间、变更失败率、部署返工率）衡量交付是否变快且稳定；DORA 官方要求按单个应用/服务观察，不能混比（[DORA metrics](https://dora.dev/guides/dora-metrics/)）。对本地应用可先按“每周发布次数、从提交到可用耗时、回滚/热修次数、恢复耗时、返工比例”人工记录。
- OpenAI 生产建议强调 staging/production 配置隔离、跟踪数据/模型版本、持续监控性能和 token/成本，并为速率限制、超时和重试设定策略（[Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices)）。若未来引入多步 agent，可使用 traces 记录模型调用、工具、guardrail 和 handoff，再接评估循环（[Agents SDK integrations and observability](https://developers.openai.com/api/docs/guides/agents/integrations-observability)；[Agent evals](https://developers.openai.com/api/docs/guides/agent-evals)）。

## 6. 发布、回滚和数据恢复

### 发布前

- 工作树干净，分支已合并，版本和变更日志已更新。
- 执行四层测试、启动器冒烟和一次备份恢复演练。
- 记录当前 commit、`requirements.txt` 哈希、模型/提示词版本和配置键名。

### 发布

- 本地发布包只包含源码、静态资源、配置模板和启动器；不包含 `.venv`、`.env`、`data/*`、图片和会话凭据。
- 先复制到带日期的备份目录，再替换代码；保留上一可运行 commit/压缩包。SQLite 官方建议使用备份 API 或在数据库不写入时复制文件，以获得一致快照（[SQLite Backup](https://sqlite.org/backup.html)）。
- 启动后依次检查网关健康、应用首页、文本生成、图片任务和历史读取；在日志中记录发布版本。

### 回滚

- **代码/配置回滚**：停止应用，切回上一 commit 或上一发布包，恢复上一份 `.env`（令牌不写进 Git），重启并冒烟。
- **数据回滚**：停止写入，先把现有数据库改名留存，再恢复经过验证的 SQLite 备份；图片目录按同一备份时间点恢复。任何破坏性迁移都必须先有反向迁移或可恢复备份。
- 为恢复设两个简单目标：RPO（最多丢失多少时间的数据）和 RTO（多长时间内恢复可用）；每周演练并记录实际值。NIST SP 800-53 CP-10 要求在中断/故障后按组织定义时限恢复到已知状态（[CP-10/CP-9 原文](https://github.com/usnistgov/oscal-content/blob/v1.4.0/src/nist.gov/SP800-53/rev5/xml/NIST_SP-800-53_rev5_catalog.xml)）。
- 回滚后记录触发原因、影响范围、恢复耗时，并把失败样例加入评估集。

## 7. 数据备份与保留

- 备份对象：`data/creative_studio.db`、`data/images/`、`data/uploads/`、脱敏的评估结果和变更日志；`chat2api/.env` 另用密码管理器或加密介质保存，不能和普通备份同目录明文存放。
- 频率：每日一次增量/快照、每周一次完整副本；保留 7 个日版本和 4 个周版本是本项目的起始建议，重要项目可延长。
- 备份命名包含日期、commit 和 schema 版本；每周随机抽一份执行“新目录恢复 + 启动 + 读取项目 + 打开图片”测试。备份没有经过恢复验证就不能视为可用。
- NIST SP 800-53 的 CP-9 要求同时考虑用户数据、系统数据和系统文档，并保护备份的机密性、完整性和可用性；本项目对应数据库/图片/上传、配置模板和运行手册（[CP-9 原文（NIST 官方仓库）](https://github.com/usnistgov/oscal-content/blob/v1.4.0/src/nist.gov/SP800-53/rev5/xml/NIST_SP-800-53_rev5_catalog.xml)）。
- SQLite 的 [How To Corrupt](https://sqlite.org/howtocorrupt.html) 文档列出了不当复制、并发写入和文件系统问题导致损坏的情形；因此不要在未知写入状态下用普通复制覆盖生产数据库。

## 8. 依赖、供应链和 LLM 安全

- `requirements.txt` 当前只声明 `requests` 和 `chat2api` 依赖。发布前生成并审查锁定版本（例如 `pip freeze` 输出单独保存），升级一次只改一组依赖并重新跑测试。
- 开启 Dependabot 或每月手工检查安全更新；GitHub 的 Dependabot security updates 会依据依赖图发现漏洞并创建含补丁版本的 PR（[Dependabot security updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates)；[version updates](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates)）。
- 把安全实践放进整个软件生命周期：依赖清单、代码审查、构建完整性和发布记录都属于软件供应链控制；NIST SSDF 提供可复用的安全开发基线（[NIST SP 800-218 SSDF](https://csrc.nist.gov/pubs/sp/800/218/final)）。
- 合并依赖更新前查看变更日志、许可证和传递依赖；不要为了“最新”自动升级生产环境。
- 对用户输入、参考文件名和模型输出做长度、类型、路径和内容校验；绝不让模型输出直接执行 Python、PowerShell、SQL 或文件路径操作。OWASP Top 10 将 Prompt Injection、Insecure Output Handling、Sensitive Information Disclosure、Excessive Agency 和 Supply Chain Vulnerabilities 列为 LLM 应用主要风险（[OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)）。
- 为生成内容设置拒答、敏感信息过滤和人工升级路径；生产请求启用超时、重试上限和速率/成本上限。OpenAI 的安全建议要求对不可信输入和输出做约束、监测滥用并保留人工复核通道（[Safety best practices](https://platform.openai.com/docs/guides/safety-best-practices)）。
- 供应商边界：`chat2api` 依赖 ChatGPT 网页内部接口，稳定性、账号合规和维护风险已在其 README 标注；发布前由负责人确认授权和账号政策，不把内部会话令牌当作公开 API 密钥。

## 9. 文档和日常节奏

- 仓库最少维护四份短文档：`README.md`（安装/启动/边界）、`docs/research/`（依据）、`CHANGELOG.md`（发布记录）、`docs/operations.md`（备份/回滚/故障处理）。提示词和评估样例也要有版本号。
- 每次变更卡关闭前补三行记录：做了什么、测试/评估结果、遗留风险。文档与代码同分支提交，避免“代码已变、说明未变”。
- 每日 10 分钟：看失败/超时/磁盘和未处理评估；每周 30 分钟：回顾 DORA 四项趋势、依赖更新、备份恢复抽检和新失败样例；每月一次：轮换令牌、检查监听地址和清理过期数据。DORA 建议用持续改进和小批量交付降低风险（[DORA capabilities](https://dora.dev/capabilities/)）。

## 当前项目差距与优先级

| 优先级 | 现状 | 最小补强动作 |
| --- | --- | --- |
| P0 | `.env` 是本机秘密，启动器会把令牌注入环境 | 保持 `.gitignore`；新增 `.env.example`；启动时拒绝空令牌/非回环地址；日志脱敏 |
| P0 | 有仓储单测，但没有固定 AI 评估集和发布门槛 | 建立 20 个脱敏样例，记录模型/提示词版本，发布前跑回归 |
| P0 | SQLite、图片和上传目录是独立运行数据 | 写一键备份说明；每日/每周保留策略；每周恢复抽检 |
| P1 | 当前只有单个 `master` 提交，暂无变更日志/版本标签 | 采用短分支、语义提交、`CHANGELOG.md` 和 `v0.1.0` 起始标签 |
| P1 | 缺少统一结构化日志和请求关联 ID | 在应用与网关边界记录 `request_id`、耗时、错误类别、模型/提示词版本，禁止记录秘密 |
| P1 | 依赖范围较宽（如 `requests>=...`） | 生成锁定清单；每月审查 Dependabot/安全公告；升级后跑全套检查 |
| P2 | 无登录是设计边界，只适合单机 | 不开放端口；若未来多人/联网，先补认证、授权、审计和威胁建模，再扩展功能 |

## 一页式发布检查单

```text
[ ] 变更卡写清目标、非目标、验收、风险、回滚
[ ] 分支仅包含本次改动；无 .env、令牌、数据库或真实上传
[ ] unittest + node --check + compileall 全部通过
[ ] AI 评估集通过门槛，结果含模型/提示词版本
[ ] 启动器、/health、文本、图片、历史和失败重试冒烟通过
[ ] 备份数据库、图片、上传；验证至少一份可恢复
[ ] 更新版本号和 CHANGELOG，记录 commit/依赖哈希
[ ] 发布后观察成功率、P95、超时、磁盘；异常按预案回滚
```

## 参考资料（官方一手来源）

- [NIST AI Risk Management Framework 1.0](https://www.nist.gov/itl/ai-risk-management-framework) · [PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)
- [NIST AI 600-1: Generative AI Profile (PDF)](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
- [NIST SP 800-218 Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final) · [SP 800-53 CP-9 backup control (NIST OSCAL)](https://github.com/usnistgov/oscal-content/blob/v1.4.0/src/nist.gov/SP800-53/rev5/xml/NIST_SP-800-53_rev5_catalog.xml)
- [OpenAI Working with evals](https://developers.openai.com/api/docs/guides/evals) · [Agent evals](https://developers.openai.com/api/docs/guides/agent-evals) · [Evals](https://platform.openai.com/docs/guides/evals) · [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices) · [Agents SDK observability](https://developers.openai.com/api/docs/guides/agents/integrations-observability) · [Safety best practices](https://platform.openai.com/docs/guides/safety-best-practices)
- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents) · [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) · [Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [DORA metrics](https://dora.dev/guides/dora-metrics/) · [DORA capabilities](https://dora.dev/capabilities/)
- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow) · [Using secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) · [Dependabot version updates](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates)
- [Semantic Versioning 2.0.0](https://semver.org/) · [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- [SQLite Online Backup API](https://sqlite.org/backup.html) · [How To Corrupt An SQLite Database File](https://sqlite.org/howtocorrupt.html)
