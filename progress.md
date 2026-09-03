# 当前项目进度（2026-09-01）

## 2026-09-04 Phase 4 轮播后台状态机与 Phase 5 治理收口

### 已完成

- 轮播 v1 采用共享 planner + 图片直出首帧的流程已写入 [`docs/adr/0003-carousel-v1-background-operation.md`](docs/adr/0003-carousel-v1-background-operation.md)，删除 prompt 中独立首帧文字会话的错误承诺。
- 新增 `CarouselVisualGeneration`，把轮播 planner 请求、契约校验和后续图片编排从生成服务中抽出；registry 绑定升级为 `CarouselResult.v1` / `CarouselResultValidator.v1`。
- 继续生成改为持久化 `carousel_operations` 后台 Operation，接口返回 `202` 和 operation id；lease、heartbeat、过期恢复、逐帧 claim、图片/会话游标/operation revision 原子提交和前端轮询均已接线。
- 恢复逻辑会把崩溃 worker 遗留的当前 `generating` 帧重置为 `pending`，保留已成功帧和失败证据；新增 API 归属、202 响应、operation 隐私和恢复回归测试。
- 补齐 `config/evals/carousel.v1.json` 的 10 个脱敏 case，并同步代码地图、运维手册和 CHANGELOG。

### 验证

- 定向轮播、后台 operation、API、生成服务、prompt registry 和叙事评测 fixture 测试通过；最终完整 deterministic unittest 为 `220` 项，Node 语法、Python compileall、JSON 解析和 `git diff --check` 均通过。
- 未修改真实 `data/`、`data/images/`、`data/uploads/`、`chat2api/.env` 或监听配置；保留 `launcher.py` 中用户已有的 `WEB_BIND_HOST = "0.0.0.0"` 未暂存修改。

### 未验证与保留项

- 真实 AI 输出质量、真实图片网关、带认证浏览器、多进程生产竞态和真实运行库升级仍未验证；本阶段测试仅使用 deterministic fake 和临时 SQLite。
- `LegacyCreativeGenerationAdapter`、旧视觉 schema 和 retired prompt 文件继续作为历史/兼容读取 seam，Phase 5 的删除条件是三个 production caller 均为零且完成保留期与回归评估，不能因本次 operation 接线强行删除。
- 2026-09-04 对真实 `data/creative_studio.db` 仅执行只读 projection scrub dry-run：`scanned_rows=3`、`changed_rows=2`、`private_field_occurrences=6`、`invalid_json_rows=0`、`unknown_kind_rows=0`；未执行 `--apply`，真实历史 scrub/备份/恢复演练仍待单独变更卡。
- 新增 [`docs/ai/quality-evaluation.md`](docs/ai/quality-evaluation.md)，集中记录三套 10-case 脱敏评测集、deterministic 证据和真实模型质量评测边界；没有把 fake 测试表述为真实质量通过。
- 本阶段 checkpoint 提交：`32ef2c2`（未包含用户已有的 `launcher.py` 修改）。

## 2026-09-03 Phase 3 静态迁移收尾与 Phase 4 交接

### 已完成

- Task 4 已提交为 `7e74b70`：`static-v1` 成为唯一静态 production，`visual-v2.3` 进入 retired inventory；静态 canonical renderer、10 个脱敏评估 case 和 registry contract 测试已纳入提交。
- Phase 4 handoff docs-only 提交为 `8bb7d54`。
- 修正显式 `model_client=None` 的 legacy adapter 边界：旧视觉结果继续走 `complete_visual_generation()`，不会因 registry 已加载而误写入静态 canonical persistence；新增回归测试覆盖该条件。
- Phase 3 handoff 已标记为实施前历史契约；新增 [`docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md`](docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md)，记录 static-v1 registry、Module、DTO、repository、图片 request、旧 alias caller、状态恢复、隐私边界、回滚和 Phase 4 范围。

### 验证

- `$env:PYTHONPATH='D:\\code\\ai_creative_studio\\src'; python -m unittest discover -s tests -v`：`202` 项通过。
- `node --check static\\app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 测试使用临时 SQLite、隔离图片目录、deterministic fake 和固定输入；未修改真实 `data/`、`data/images/`、`data/uploads/` 或 `chat2api/.env`。
- `launcher.py` 保留用户已有的 `WEB_BIND_HOST = "0.0.0.0"` 修改，未暂存；默认部署和监听边界未因本阶段改变。

### 未验证

- 真实 AI 输出质量、真实图片网关成功率/画质、带认证浏览器流程、真实数据库升级/历史 scrub、Chat2API 真实参数语义、参考文件内容传递和多进程生产竞态仍未验证。

### 下一阶段

- Phase 4 只处理轮播 v1 的 ADR、后续画面 prompt/编排、Operation/lease/heartbeat、逐帧状态查询和轮播前端轮询；不得提前修改 static-v1 或静态 persistence。

## 2026-09-03 正式页面项目删除与标签交互迁移

### 已完成

- 项目列表每行增加删除图标，删除当前项目后按原位置打开下一个或前一个项目；删除非当前项目保持当前工作区，全部删除后才显示空状态。
- 移除标签组展开区重复的已选标签芯片，保留表格高亮、章节摘要和顶部汇总。
- “是否轮播”改为独立的“是/否”单行控件；选择“否”会清理轮播屏数、形式和逐轮配置。
- 展示内容章节始终保留，未选择产品卖点时显示提示；选择卖点后按 `product_display` 关系过滤，并清理失效展示内容。
- 标签达到上限后禁用未选项，已选项仍可取消；普通标签、主副标签、美术风格和轮播轮次不再自动顶替最早选择。
- 轮播第 2 轮起支持继承第 1 轮、首次编辑转为自定义、按上限替换以及重新继承时丢弃覆盖值。

### 验证

- 新增并通过前端契约测试：`python -m unittest tests.test_frontend_tag_reports -q`，19 项通过。
- 全量确定性测试：`python -m unittest discover -s tests -v`，201 项通过。
- `node --check static/app.js`、`git diff --check` 通过。
- 已连接本地页面检查；正式页面需要登录，未使用或索取凭据，因此未完成带认证的 `1280x720` / `390x844` 人工浏览器验收。
- 未调用真实 AI 或图片网关，未修改数据库、上传文件或 `chat2api/.env`。

## 2026-09-03 AI 重构 Phase 3 静态展示类迁移（实现完成）

### 已完成

- `src/creative_studio/static_visual.py` 提供 `StaticVisualPromptInput`、`StaticVisualResult.v1`、严格 validator、一次字段路径 repair 和私有图片指令分离。
- `StudioRepository.complete_static_generation()` 与 `PublicResultMapper.static_visual_item()` 已接入；新静态写入不包含 `subtitle`、`creative_description`、`core_subject`、`layout`、`visual_style`，不创建 `display_frames`，私有图片指令只进入 `visual_items.image_prompt` 和受控图片任务。
- `CreativeGenerationService` 的正式非轮播展示路径进入 `StaticVisualGeneration`；每批 3 个方案、每案 1 个 `StaticVisualImageRequest`，叙事 v6、轮播 prompt/validator/继续生成和逐帧状态机保持原路径。
- `config/prompts/registry.json` 将 `creative.visual.static.generate@static-v1` 设为唯一静态 production；`visual-v2.3` 标记 `retired`，禁止新 caller，并写明 replacement、deprecated_since 和 Phase 5 removal condition。
- `config/evals/static.v1.json` 已建立 10 个脱敏 case，覆盖空白 brief、画幅、仅文件名参考、未确认事实、缺失素材、机制重复、超长文案、URL/Markdown 注入和 repair 失败。
- `static/app.js` 对含 `static_frame` 的结果优先呈现用户张力、产品价值、视觉机制、证据台账、静态画面、素材计划、制作风险和 review；旧 carousel 结果继续使用原渲染逻辑。

### 验证

- 实现提交：`c0d86a0`、`42ebc83`、`08492ca`；Task 4 配置/评估/前端和文档收尾提交见当前分支日志。
- 静态定向测试 23 项通过；完整 deterministic unittest、Node 语法、Python compileall、`git diff --check` 和工作树门禁在本次收尾前重新执行。
- 测试只使用临时 SQLite、fake model/image runner 和隔离路径；未修改真实 `data/`、`data/images/`、`data/uploads/` 或 `chat2api/.env`。
- 未调用真实 AI、图片网关或带认证浏览器；真实数据库升级/历史 scrub 和图片质量仍未验证。

### Phase 4 输入

- Phase 4 只处理轮播 v1 的 ADR、后续画面 prompt/编排、Operation/lease/heartbeat、逐帧状态查询和轮播前端轮询。
- static-v1 的实际路径、旧 alias 读取 caller、首图 typed request、部分成功/人工 retry/重启恢复和隐私边界记录在 `docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-4-handoff.md`。

## 2026-09-03 Phase 3 交接文档深度复核

### 已完成

- 重新核对 Phase 3 直接相关的架构设计、展示画面流程、提示词工程研究、Phase 2 交接、总纲、公开投影 ADR、静态提示词、registry、静态生产 caller、validator、repository、图片任务和公开 DTO。
- 深度完善 [`docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md`](docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md)：以当前 HEAD 为事实基线，写清静态 v2.3 production 与 static-v1 candidate 的差异、旧字段伪造路径、持久化副本、图片入队 seam、StaticVisualResult.v1/StaticVisualPublicDTO.v1 目标、私有图片指令边界、deterministic harness、质量评估、失败/重试/回滚和 Phase 4 启动条件。
- 明确 Phase 3 不修改轮播 prompt、继续生成、逐帧状态机、真实运行数据、网关凭据或真实外部调用；`launcher.py` 接手前已有修改继续保留。
- 本次内容通过独立 docs-only 提交保存；提交后仍需保持 `launcher.py` 为未暂存用户修改。

### 验证

- 已交叉核对当前 registry、代码 caller、持久化字段和测试事实；文档不含未决占位语句。
- 本次仅修改交接文档和本进度记录，未修改业务代码、数据库、图片、上传文件或 `chat2api/.env`，未调用真实 AI、图片网关或浏览器。

## 2026-09-03 Phase 3 交接文档

- Phase 2 实现提交：`1c681cc2b82fcaaee9416111ccd15b96bdf4efe9`。
- 已生成 [`docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md`](docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-3-handoff.md)，下一阶段只允许静态展示类重构；不进入轮播 Phase 4。

# 2026-09-03 AI 重构 Phase 2 叙事类重构（已完成）

### 已完成

- 新增 `src/creative_studio/narrative.py`，建立 `NarrativeGeneration`、`NarrativeInput` 和 `NarrativeResult.v1` canonical contract；固定 5 个故事、每故事 2 个钩子、每钩子 3 个场景，并校验故事/钩子差异、证据台账和风险字段。
- 叙事生产 prompt 升级为 `config/prompts/narrative/v6.txt`，明确注入游戏资料与参考文件名；registry 登记 `creative.narrative.generate@v6`，v5 标记 retired。
- 生产 `CreativeGenerationService` 叙事分支接入新 Module；格式 repair 携带上次校验字段路径，第二批携带上一批摘要和显式去重约束；旧 UI 通过白名单 DTO 保持 `story/hooks` 兼容。
- 新增 deterministic fake 叙事 contract 测试和固定评估样例；更新代码地图、运维边界和 registry contract 映射。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -q`：185 项通过。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 未调用真实 AI、图片网关或浏览器；未修改真实数据库、图片、上传文件或 `chat2api/.env`。

### 保留项

- `LegacyCreativeGenerationAdapter` 和旧叙事校验函数仍保留为无 model client/历史兼容 caller，删除条件为三个新业务 Module 均切换且 legacy production caller 为零；本阶段不进入 Phase 3。

# 2026-09-03 AI 重构 Phase 1 实现（已完成）

### 已完成

- 新增 `config/prompts/registry.json`，登记三个 production PromptSpec、一个 candidate 和两个 retired inventory；模板 hash 使用规范化 UTF-8 SHA-256。
- 新增 `prompt_registry.py`、`contracts.py`、`model_ports.py` 和 provider capability 声明；registry 对缺文件、越界路径、错 hash、错变量、未知 contract 和生命周期规则 fail closed。
- `create_application()` 启动时加载 registry；生成完成记录以加法迁移保存 prompt id/version/hash、schema 版本、model/provider；新增 deterministic text/image fake。
- registry/port 定向测试和全量确定性测试共 181 项通过。

### 边界

- 未切换用户可见输出，未调用真实 AI、图片网关或浏览器；未写入真实数据库、图片、上传文件或 `chat2api/.env`。
- 工作树接手时已有标签目录同步和启动器局域网配置修改，均已随实现提交保留；未调用真实 AI、图片网关或浏览器。
- Phase 1 实现提交为 `1704bea`；Phase 2 交接文档随后以 docs-only 提交生成。

# 2026-09-03 叙事标签选择上限调整

### 已完成

- 更新 `config/creative_tag_options.json`：副目标人群最多 2 项、美术风格 1 项、内容形式 3 项、产品证据 4 项。
- 增加标签配置契约测试，锁定上述选择上限；展示类上限保持不变。

### 验证

- 待本次改动完成后运行完整单元测试、前端语法检查、Python 编译检查和 `git diff --check`。

# 2026-09-03 叙事与展示标签目录同步

### 已完成

- 以 `C:\Users\admin\Downloads\叙事类标签_重制版.xlsx` 和 `C:\Users\admin\Downloads\展示类标签.xlsx` 为来源，更新 `config/creative_tag_options.json` 至 `tags-2026-09-03-v2`。
- 叙事类新增“美术风格”组并置于“目标人群”之后；叙事目录更新为 6 组、139 个选项，展示目标用户更新为 34 项，展示美术风格按重复参考作品行归并为 35 项。
- 将叙事 `art_style` 接入统一标签规范化、生成指纹、`{{creative_tags}}` prompt 注入和公开项目投影；未修改 `config/ai_creative_prompt_v5.txt`。
- 保留展示类产品卖点→展示内容关系表；旧数据库中的历史标签值未迁移或删除。

### 验证

- 新增标签目录、prompt、指纹和公开投影契约测试；定向标签/投影测试通过。
- 尚未调用真实 AI、图片网关或浏览器；未修改数据库、图片、上传文件或 `chat2api/.env`。

### 未完成

- 尚未在正式页面逐项人工验收新增标签的桌面/移动端显示；需要后续按项目要求检查 `1280x720` 和 `390x844`。

# 2026-09-03 AI 重构 Phase 1 交接准备

### 已完成

- 新增 `docs/superpowers/handoffs/2026-09-03-ai-rebuild-phase-1-handoff.md`，记录 Phase 0 检查点、Phase 1 精确范围、执行顺序、完成门禁和验证/提交要求。
- 交接要求下一会话完整完成并提交 Phase 1 后，生成一份无占位符、包含真实提交和验证证据的 Phase 2 新会话交接文档；Phase 1 未通过时不得宣称可以进入 Phase 2。
- 修正总纲 Phase 1 允许文件，使范围覆盖 registry、port、生成元数据和 production contract harness 的必要接线文件；同时将 Phase 2 开始条件收紧为 Phase 1 全部门禁、实现提交和工作树检查均完成，继续排除提前切换用户可见输出。

### 当前状态

- Phase 1 尚未开始；当前仅准备交接文档，没有实现 PromptRegistry、ContractRegistry、model port 或 contract harness。
- 本次不修改业务代码、UI、数据库、图片、上传文件或 `chat2api/.env`，不调用真实 AI、图片网关或浏览器。

# 2026-09-03 AI 重构 Phase 0 安全止血与事实收口

### 已完成

- 新增统一的 `PublicResultMapper`，history、status、adopt、项目采用快照、visual item 和 display frame 均按稳定顺序的白名单重建公开对象；递归私有字段清单覆盖供应商游标和内部错误详情。仓库当前没有 export 路由，因此本阶段无 export caller 可迁移。
- 新增 dry-run 优先的 projection scrub；工具以 SQLite `mode=ro` 扫描，写入只允许显式指定的非生产副本且强制先备份，遇到无效 JSON 或未知 recommendation kind 会中止，并拒绝直接 apply `data/creative_studio.db`。
- prompt 编译器收敛为 `{{name}}` 单次字面替换；缺失变量、多余变量和 hash 不匹配均 fail closed，不再二次解释用户输入中的 `$` 或 `{{...}}`。
- JPEG、PNG、WebP 参考图与下载 artifact 现在校验 magic bytes、MIME 和规范扩展名，并在 SQLite 中持久化 `image_mime`。
- 生成失败记录不再被同 fingerprint 的后续请求删除；错误增加稳定 `error_code`、阶段、字段路径、可重试性和 trace id，公开响应只返回安全摘要。
- 新旧模型调用路径的 JSON 解析失败统一使用根路径 `$`，`HttpModelClient` 在 transport 边界保留畸形 `choices` 路径，叙事各层 validator、视觉 wrapper 和供应商游标错误使用精确字段路径；公开文本列表拒绝数字和布尔值，仅旧 `carousel_frames` 继续兼容整数索引。
- 轮播数量缺失或不在 2 至 5 时会在 reservation 和模型调用前失败；`none` 保持 1 帧，AI 数量仍允许每套独立返回 2 至 5 帧。
- 移除 `creative_studio.app` 的 import-time composition root；`create_application()` 支持临时 SQLite、fake model/image queue、隔离环境和固定 clock seam。叙事游戏资料默认路径已改为 v2。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：175 项通过。
- `node --check static\app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 对真实默认数据库仅执行只读 dry-run：扫描 8 行，6 行投影会变化，发现 25 处私有字段，0 行无效 JSON，0 行未知 recommendation kind；`applied=false`，未创建备份，执行前后 SHA-256 均为 `F7DA1AA20D5FBAC7A3785C0D81096B1096749DE40025874644F37E1AD461DFA8`，未写入数据库。
- 在临时 SQLite 副本验证 dry-run、强制备份 apply、写后重读和从备份恢复；未对真实数据库执行 `--apply`。

### 边界与后续

- 未调用真实 AI、图片网关或浏览器；未修改真实数据库、图片、上传文件或 `chat2api/.env`。
- `LegacyCreativeGenerationAdapter`、旧 schema，以及 retired 的首帧/后续帧 prompt loader 仍保留，按变更卡中的删除条件留待后续阶段处理。
- Phase 0 门禁完成后才可另开 Phase 1；本条不实现 PromptRegistry、ContractRegistry 或新业务契约。

## 2026-09-03 AI 创意能力重构总纲

### 已完成

- 完成 AI 能力的生产链路审计，记录叙事、静态展示、轮播、图片任务、提示词编译、网关参数、持久化、公开 DTO、测试和文档治理问题。
- 新增 [`docs/ai-rebuild-master-plan.md`](docs/ai-rebuild-master-plan.md)，作为当前 AI 重构的唯一实施基线：包含当前真实事实、P0/P1/P2 问题台账、目标深模块和 port/adapter、PromptRegistry 与契约、公开 DTO、轮播状态机、质量评测、Phase 0 至 Phase 5 迁移门禁、回滚和后续 Agent 执行协议。
- 新增 [`docs/ai/README.md`](docs/ai/README.md) 作为 AI 文档入口，并同步修正 `AGENTS.md`、`项目代码地图.md` 和 `docs/operations.md` 中已确认的登录/项目归属、监听地址和轮播首帧事实冲突。

### 验证

- 已通过静态审计确认真实 production composition root 为 `StudioApplication -> CreativeGenerationService -> HttpModelClient -> chat2api`；轮播首帧当前直接使用共享规划响应，提示词中的独立文字会话描述属于待清理漂移。
- 本次只修改文档和工程治理入口；未修改业务代码、数据库、图片、上传文件或 `chat2api/.env`，未调用真实 AI/图片网关。

### 当时未完成

- 本条记录形成时尚未执行 AI 重构 Phase 0；其完成情况以文件顶部更新的 Phase 0 记录为准。

## 2026-09-02 补充工作树整理与提交要求

### 已完成

- 在 `AGENTS.md` 新增提交与工作树整理约定：单需求单提交、历史堆积时使用明确的 checkpoint 快照、提交前验证、敏感运行数据排除和提交后状态复核。
- 记录测试存在环境依赖失败时的报告要求，避免将部分通过表述为全部通过。

### 验证

- 文档差异通过 `git diff --check`。
- 已确认此前整理快照提交 `73d770a` 后工作树干净；本次只新增代理规范和进度记录。

### 未完成

- 未修改业务代码、数据库、运行数据或 AI 配置；未发起真实 AI 请求。

## 2026-09-02 补齐轮播提示词上下文与图片模式约束

### 已完成

- 展示方案持久化保留核心主体、画面布局、视觉风格、内容延展、参考来源、关键词及任务/产品证据，继续生成时完整注入同一方案上下文。
- 首帧和后续画面提示词明确区分规划 JSON 与图片执行指令；图片指令要求直接生成图片，不返回文字、JSON、Markdown 或解释。
- 图片网关入口统一增加图片模式前缀，降低上游模型将生图请求误判为文字问答的概率。
- 继续生成不再向可见文字会话发送后续 JSON 请求，直接依据锁定路线生成图片提示词并提交图片网关；上一张成功图片继续作为参考图。
- 网页服务在未由启动器注入环境变量时，自动回退到本项目本地 AI 网关和版本化提示词路径；不读取或改写令牌配置。

### 验证

- 轮播继续生成、图片任务、生成服务和仓储回归测试通过。
- 全量确定性测试：127 项中 126 项通过；唯一错误仍为当前环境缺少 `pydantic_settings`，导致既有 `test_auth_refresh` 无法导入。

## 2026-09-02 修正轮播继续生成会话路线

### 已完成

- 将展示类轮播批次固定为一次共享文字会话输出三套方案和完整画面路线。
- 每套方案在独立的新文字会话中重新生成第 1 帧，持久化独立 `conversation_id` / `parent_message_id`，首帧图片再进入该方案任务。
- 继续生成复用方案自己的会话，按帧序串行生成后续画面；旧历史方案缺少会话时也会先补建首帧并等待首图完成。
- 前端继续按钮增加“继续生成中”状态和重复点击保护；隐藏图片指令仍不进入公开响应。

### 验证

- 新增生成服务回归测试：确认 1 次共享方案请求后有 3 次无会话首帧请求，三套方案会话游标各不相同，首帧内容来自独立会话。
- 连续画面会话测试、仓储测试和前端契约测试通过；`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 全量确定性测试：127 项中 126 项通过；唯一错误为当前环境缺少 `pydantic_settings`，导致既有 `test_auth_refresh` 无法导入。

### 未完成

- 未在真实浏览器和有效 AI 凭据下执行轮播首帧/继续生成；真实网关和图片质量仍未验证。

## 2026-09-02 修正竖版画面显示比例

### 已完成

- 将竖版图片容器比例从 `9:12` 修正为 `9:16`，与项目竖版画幅一致。
- 保持图片使用 `object-fit: contain`，完整显示画面内容。

### 验证

- `tests.test_frontend_tag_reports.FrontendTagReportTests.test_portrait_image_frame_uses_full_9_by_16_ratio`：通过。
- `node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 生成成功后自动刷新结果

### 已完成

- 生成接口成功返回后，前端自动重新读取规范化历史数据并渲染最新方案。
- 修复 POST 生成响应缺少类型字段时误用叙事卡片渲染展示类方案的问题。
- 保留图片后台生成和状态轮询，不需要用户手动刷新浏览器。

### 验证

- `tests.test_generation_service` 与 `tests.test_frontend_tag_reports`：28 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 展示类文字结果优先返回

### 已完成

- 展示类文字方案完成校验和图片任务入队后立即返回，不再等待全部图片进入终态。
- 前端先渲染方案文字与图片占位，图片继续由后台任务和已有轮询更新。
- 叙事类生成和连续画面继续生成逻辑保持不变。

### 验证

- `tests.test_generation_service` 与 `tests.test_frontend_tag_reports`：26 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 方案细节状态中文化

### 已完成

- 方案细节中的画面状态由内部英文值转换为中文：排队中、等待中、生成中、已完成、生成失败。
- 未知状态统一显示为“处理中”，避免内部枚举直接泄漏到界面。

### 验证

- `tests.test_frontend_tag_reports.FrontendTagReportTests.test_frame_statuses_are_translated_for_scheme_details`：通过。
- `node --check static/app.js`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 展示方案操作收敛

### 已完成

- 移除展示类轮播方案卡上独立的“选择方案”按钮及其前端监听器。
- 每套方案只保留“继续生成”和“采用此方案”；继续生成直接调用对应方案接口，由后端自动建立/复用该方案独立会话并按序推进后续画面。
- 保持多套方案可同时点击继续生成，各方案使用独立会话和状态锁，任务不会互相串线。

### 验证

- 新增前端契约测试，确认不存在选择方案入口且继续/采用动作仍存在。
- `tests.test_frontend_tag_reports`：10 项通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 全量确定性测试：122 项中 121 项通过；唯一错误为当前环境缺少 `pydantic_settings`，导致既有 `test_auth_refresh` 无法导入。

### 未完成

- 未在真实浏览器会话中点击多套方案的并行继续生成。
- 未发起真实 AI 文字或图片请求。

## 2026-09-02 生成阶段显示等待时长

### 已完成

- 最终生成按钮从点击开始显示已等待时长，并每秒刷新一次。
- 等待时长支持持续累计（超过 1 小时显示小时），不增加超时、重试或生成次数限制。
- 请求成功、失败后清理计时器，避免页面残留后台定时任务。

### 验证

- `tests.test_frontend_tag_reports.FrontendTagReportTests.test_generation_button_shows_unlimited_elapsed_wait_time`：通过。
- `node --check static/app.js`：通过。

### 未完成

- 未发起真实 AI 文字或图片请求；未进行带认证的浏览器人工验收。

## 2026-09-02 移除实时创意简报并改为单列工作区

### 已完成

- 删除创意定位页面右侧“实时创意简报”栏及其前端状态绑定。
- 桌面和移动端统一使用单列主工作区，释放横向空间并保留任务描述、标签、画幅、历史、生成与采用功能。
- 清理桌面媒体查询中遗留的双列和简报定位规则，避免空侧栏占位。

### 验证

- `tests.test_frontend_tag_reports`：前端契约测试通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 浏览器静态检查确认简报 DOM 不存在、桌面实际计算为单列且 1280x720/390x844 无横向溢出。

### 未完成

- 未发起真实 AI 文字或图片请求。

## 2026-09-02 最新 Session Cookie 验证与连接检测修复

### 已完成

- 确认用户新填的 Session Cookie 能换出与旧 Token 不同的新 Token，并通过真实 `chat-requirements` 认证探测。
- 定位启动器问题：旧 Token 只要 JWT 未到期，检测就跳过 Cookie 换 Token，导致新 Cookie 未被当前网关使用。
- 修正检测流程：先验证 `/v1/models`；仅当上游未验证且存在 Cookie 时，才用 Cookie 更新 Token 并重新验证。
- 当前网关通过新 Cookie 更新后，`/v1/models` 返回 `detected=true`、模型列表非空；最小真实 `/v1/chat/completions` 返回 `OK`，会话标识正常。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_launcher_proxy tests.test_auth_refresh -v`：28 项全部通过。
- 全量确定性测试：121 项中 120 项通过；唯一失败为既有前端契约测试 `test_workspace_drops_realtime_brief_sidebar`，与本次认证/启动器修复无关。
- `python -m compileall -q src chat2api launcher.py`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 当前启动控制台进程仍是旧代码；需重启启动控制台后，点击“检测连接”才能使用新的 Cookie 回退验证逻辑。
- 三条业务路径的真实文字/图片生成尚未在本次复测中展开；网关认证和最小文字调用已恢复。

## 2026-09-02 标签满额后可继续选择

### 已完成

- 对照展示类、叙事类标签 Excel 规则，修正单选、主+辅选择和多选达到上限后的交互。
- 取消未选项的满额禁用；再次选择会自动替换最早选中的标签，主选/副选槽位同步重排；美术参考作品和逐轮定位字段也遵循同一规则。
- 保留取消已选项、选项上限、级联清理和服务端字段结构。

### 验证

- `tests.test_frontend_tag_reports`：新增满额替换契约测试并通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 已核对两份 Excel 的交互形式与选择规则，未修改 Excel 原文件或标签配置 JSON。

### 未完成

- 未在带认证的正式页面中逐项人工点击验收；未发起真实 AI 请求。

## 2026-09-02 修复启动器连接状态误报

### 已完成

- 修复“检测连接”只检查本地 `/health` 的 Token 存在和到期时间、却不验证上游可用性的逻辑。
- 现在检测会额外检查 `/v1/models` 的 `detected=true` 和非空模型列表；上游返回 `token_revoked` 或探测失败时显示连接失败并保留错误原因。
- 区分“已通过上游验证”和“Access Token 已自动填入”，不再在未刷新 Token 时误称已自动填入。
- 新增启动器连接验证回归测试。

### 验证

- 当前真实网关 `/v1/models` 返回 `detected=false` 时，`gateway_upstream_verified()` 返回 `False`，与上游 Token 已撤销的真实状态一致。
- `PYTHONPATH=src python -m unittest tests.test_launcher_proxy tests.test_auth_refresh -v`：28 项全部通过。
- 全量确定性测试：121 项中 120 项通过；唯一失败为既有前端契约测试 `test_workspace_drops_realtime_brief_sidebar`，与本次启动器/认证修复无关，保留用户现有前端改动。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 账号 Access Token 仍被上游撤销；更新有效凭据并重启网关后，检测才会显示“已通过上游验证”。

## 2026-09-02 真实 AI 请求认证问题修复与复测

### 已完成

- 定位并修复 ChatGPT Session Cookie 头组装问题：旧的未分片值与 NextAuth `.0/.1` 分片同时存在时，服务端可能优先读取已失效的旧值；现在分片值优先，Cookie 轮换后也保持同一规则。
- 新增脱敏回归测试，覆盖 Cookie 规范化和轮换场景；未记录任何令牌、Cookie 或完整模型响应。
- 通过项目专用 ClipProxy 中转真实调用 `/api/auth/session`，修复后返回 `200` 且拿到 access token。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：117 项全部通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。
- 修复后的真实 `/v1/chat/completions` 最小请求仍返回上游 `401 token_revoked`；说明代理、Cookie 头和网关链路可达，但当前 Access Token 已被 ChatGPT 撤销，Session Cookie 返回的 token 也仍是该失效 token。
- 临时真实测试网关和中转已停止；现有本地网页/网关进程未被停止。

### 未完成

- 当前账号凭据不可用于真实文字或图片生成，叙事类、展示类首帧和连续画面三条业务路径均在网关认证层之前被同一 `token_revoked` 阻断，未继续重复请求消耗额度。
- 需要用户在启动控制台重新登录并提供有效 Session Cookie、Access Token 或可用的 Auth0 refresh token 后，再做三条业务路径的真实冒烟。

## 2026-09-02 任务描述输入框收紧

### 已完成

- 将“创意定位”顶部任务描述从多行文本框改为单行输入框，限制最大长度为 500 字符。
- 保持 `taskDescription`、自动保存和后端 `task_description` 字段不变。

### 验证

- `tests.test_frontend_tag_reports`：6 项通过。
- `node --check static/app.js`、`git diff --check`：通过。
- 静态页面结构检查确认输入元素为 `INPUT`，桌面和移动端页面宽度无溢出。

### 未完成

- 未发起真实 AI 请求；未在带认证的正式服务中执行完整生成流程。

## 2026-09-02 任务描述并入创意定位

### 已完成

- 删除独立的“任务说明”步骤和“任务类型”输入框。
- 将唯一的任务描述输入框放到“创意定位”流程顶部，画幅控件同步保留在该标题区域。
- 工作流步骤调整为“创意定位 → 生成与采用”，后端仍兼容发送空 `task_type` 字段。

### 验证

- `tests.test_frontend_tag_reports`：5 项通过。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 浏览器结构冒烟：`1280x720`、`390x844` 均无横向溢出，步骤条为两步，任务描述位于标签控件之前。

### 未完成

- 未发起真实 AI 请求；未在带认证的正式服务中执行完整生成流程。

## 2026-09-02 修正固定出口被普通节点替换

### 已完成

- 定位到启动器把已配置的 ClipProxy `38.248.239.46` 替换成普通 Clash `127.0.0.1:7897`，导致出口 IP 错误。
- 已修正为：有 `PROXY_URL` 时始终使用已配置的 ClipProxy 固定出口；仅在没有固定代理时才探测 Clash 入口。
- 不再把普通 Clash 节点冒充固定出口；固定代理场景由轻量转发器占用 `7896`，最终出口仍由 ClipProxy 决定。
- 新增只监听 `127.0.0.1:7896` 的轻量转发器：Clash HTTP 隧道 -> ClipProxy SOCKS5 认证 -> 目标连接；替代旧 Mihomo 链式实现。

### 验证

- `tests.test_launcher_proxy`：修正后定向测试通过。
- 当前机器真实出口测试成功：返回固定 IP `38.248.239.46`；停止后 `7896` 无监听进程。
- 尚未进行真实 Chat2API AI 生成请求验证；公网出口和代理链路已验证。

## 2026-09-02 展示类连续画面生成流程实现

### 已完成

- 新增展示类画面领域模型，支持不轮播 1 张、固定 2～5 张和每套方案独立 AI 决定 2～5 张。
- SQLite 增加画面级状态表和方案级继续操作锁，兼容旧 `visual_items` 首图历史；服务端公开历史过滤图片生成隐藏字段和本地路径。
- 首次展示生成保留三套方案和三张首图并行任务，并等待首图分别进入成功/失败终态后返回；单套失败不影响其他方案。
- 新增方案选择、独立会话游标、按序继续生成和上一张实际图片参考输入；一次继续操作在后端逐画面串行执行。
- 图片网关参考图以受控 data URL 传递；首图失败自动重试一次，连续画面失败后可从失败序号恢复；新增服务端选择/继续接口。
- 同步修正展示类 AI 输出校验，允许 AI 模式三套方案独立锁定不同画面数量。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：106 项全部通过。
- 定向连续画面、仓储、图片任务和 API 测试通过。
- `python -m compileall -q src chat2api`、`node --check static\\app.js`、`git diff --check`：通过。
- 未发起真实 AI 文字/图片请求；未验证真实网关对连续参考图的实际生成质量。

### 未完成

- 需要在真实 AI 网关可用时验证三套首图部分失败、后续串行图片参考和人工恢复链路。
- 前端尚未接入选择/继续接口，当前仅完成后端业务流程。

## 2026-09-02 Clash 端口自动发现

### 已完成

- 代理中转启动前自动读取 `CLASH_CONFIG_PATH`、`CLASH_HOME` 和 Clash Verge 常见配置文件。
- 支持从配置识别 `mixed-port`/`port` 的 HTTP 入口和 `socks-port` 的 SOCKS5 入口，不再固定依赖 `7897`。
- 保留 `CHAT2API_CLASH_PORT` 覆盖；可用 `CHAT2API_CLASH_PROTOCOL=http|socks5` 指定覆盖端口协议。
- 中转日志现在显示实际使用的协议和端口。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：19 项通过。
- `python -m py_compile launcher.py`、`python -m compileall -q src chat2api launcher.py`、`node --check static\\app.js`、`git diff --check`：通过。

### 未完成

- 未发起真实 AI 请求；不同电脑的实际 Clash 配置需在对应机器上首次启动时确认日志。

## 2026-09-02 展示类连续画面流程设计复审修订

### 已完成

- 根据已确认业务逻辑补充展示类连续画面设计：三套首图部分成功返回、后续逐画面调用和串行等待、方案级继续操作幂等、独立 GPT 会话持久化、上一张实际图片输入、图片/文字失败恢复和服务端隐藏字段过滤。
- 明确方案路线锁定、首图/后续画面数据结构、方案状态和画面状态，并补充选择、继续、首图重试、失败恢复和状态查询接口边界。
- 修正整体 AI 架构设计中“AI 决定后统一数量”的冲突，统一为每套方案独立决定并锁定 2～5 张。

### 验证

- 设计文档和相关研究笔记已按项目要求完整阅读。
- `git diff --check`：通过（仅有 Windows 换行转换提示）。
- 未修改业务代码、数据库、运行数据或 `.env`；未发起真实 AI 请求。

### 未完成

- 等待用户确认修订后的设计；确认后再使用 `writing-plans` skill 编写实现计划。

## 2026-09-02 连接检测避免无条件刷新 Cookie

### 已完成

- 连接检测现在先依据网关健康状态和 Token 到期时间判断是否需要刷新会话。
- 已有明确有效的 Access Token 时直接完成检测，不再因失效 Cookie 刷新失败误报连接失败。
- Token 缺失、过期或到期时间无法判断时，仍会使用 Session Cookie 尝试换取新 Token。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：17 项通过。
- `python -m py_compile launcher.py`、`git diff --check`：通过。

### 未完成

- 需要重启当前启动控制台后重新检测；未发起真实 AI 生成请求。

## 2026-09-02 检测失败显示真实原因

### 已完成

- 修复启动器连接检测只显示 `RuntimeError` 的问题。
- 现在日志会显示异常正文的脱敏前 240 个字符，保留 HTTP 状态或会话刷新失败原因，同时隐藏 Cookie/Token。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：15 项通过。
- `python -m py_compile launcher.py`、`git diff --check`：通过。

### 未完成

- 需要重启当前启动控制台后再点击“检测连接”，才能加载新的错误显示逻辑；未发起真实 AI 请求。

## 2026-09-02 项目代理中转孤儿进程清理

### 已完成

- 定位 `7896` 端口被遗留 `verge-mihomo.exe` 占用的原因；确认其命令行指向本项目 `.runtime/proxy-bridge.yaml`。
- 启动项目代理中转前读取端口 PID 和进程命令行，仅对明确属于本项目的旧中转执行 `taskkill /T /F` 回收。
- 其他程序或 Clash Verge 主进程占用 `7896` 时保持失败并提示确认，不自动误杀。
- 已清理本机现场孤儿进程 PID `23276`，确认 `7896` 释放。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：13 项通过。
- `python -m py_compile launcher.py`、`python -m compileall -q src chat2api launcher.py`、`node --check static\\app.js`、`git diff --check`：通过。
- 当前 `7896` 无监听；未发起真实 AI 请求。

### 未完成

- 尚未在带桌面的真实 Windows 会话中完整验证“关闭后再启动”的人工流程。

## 2026-09-02 整体架构复审问题修复

### 已完成

- 服务端对 `must_change_password` 用户强制阻止业务 API，仅允许改密和登出。
- 图片任务在旧 worker 仍处于调度集合时记录重排请求，避免快速重试被吞掉。
- 新模型客户端路径对格式/结构错误执行一次有限重试；网络超时仍映射为 503。
- 新增认证门禁和模型修复重试回归测试。
- 稳定 pending 冲突回归测试的时间夹具，避免随系统日期过期。

### 验证

- 定向生成、认证、图片测试 8 项通过。
- Python 编译、JavaScript 语法和 `git diff --check` 通过。
- 全量确定性测试：`python -m unittest discover -s tests -v`，92 项全部通过；未发起真实 AI 请求。
- 修复提交：`80ee1ea`。

## 2026-09-02 启动控制台关闭释放端口

### 已完成

- 修复关闭启动控制台时，后台启动线程可能在关闭后继续拉起网页或 AI 网关的竞态。
- 统一停止子进程并等待退出；正常终止超时后升级为强制结束，避免 8775/8780 端口残留。
- 新增回归测试覆盖终止等待和强制结束路径。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_launcher_proxy -v`：11 项通过。
- `python -m py_compile launcher.py`、`python -m compileall -q src chat2api launcher.py`、`node --check static\\app.js`、`git diff --check`：通过。

### 未完成

- 尚未在带桌面的真实 Windows 会话中逐按钮验证；未发起真实 AI 请求。
- 关闭浏览器页面不会停止服务，仍需关闭启动控制台或点击“停止”。

## 2026-09-02 项目专用 ClipProxy 链式中转

### 已完成

- 启动器新增项目专用 Mihomo 链式中转：chat2api 使用 `127.0.0.1:7896`，ClipProxy 经本机 Clash 出站，不修改系统代理、TUN 或主 Clash 订阅。
- 代理工作台和网关启动共用同一条中转路径；无本机 Clash 时明确降级为 ClipProxy 直连，不再把普通 Clash 节点显示为固定 ISP 出口。
- 默认发现 Clash 常见 HTTP 端口 `7897/7890/7891`；非标准端口可通过 `CHAT2API_CLASH_PORT` 指定，避免迁移时复制旧订阅。

### 验证

- Mihomo 配置检查通过；真实启动中转并探测出口成功，返回 ClipProxy 固定 IP `38.248.239.46`。
- 代理定向测试 10 项、全量确定性测试 87 项、Python 编译、JavaScript 语法检查和 `git diff --check` 均通过。

## 2026-09-02 ClipProxy 静态 IP 多浏览器范围研究

### 已完成

- 核对 ClipProxy 官方静态 IP 购买、提取、白名单、指纹浏览器和多设备计费文档。
- 确认官方未给出“一个静态 IP 支持几个指纹浏览器/并发会话”的固定数字，也未承诺无限并发。
- 研究笔记已保存为 `docs/research/2026-09-02-clipproxy-static-ip-multi-browser.md`。

## 2026-09-02 代理跨电脑自动路由

### 已完成

- 复现确认：当前远程 ClipProxy 端点在 Python 进程中超时，而本机 Clash `127.0.0.1:7897` 可成功返回出口 IP。
- 启动器新增自动选择逻辑：优先已保存的远程代理，失败后探测本机 Clash 常用端口并仅对本次网关进程切换，不修改系统 VPN/TUN 或 `.env` 原配置。
- 代理工作台“测试出口 IP”同步使用自动路由，避免远程端点在 Python 分流下超时却误显示失败。
- 实测自动回退可连通，但出口会随 Clash 节点变化（本轮为 `67.159.48.146`），已在提示中明确不等于 ClipProxy 固定 IP。
- 追加诊断：运行中的旧网关 `/health` 正常但 `/v1/models` 超时，需完全重启启动器/网关后才能加载自动回退环境；仅点击“检测连接”不会替换已有网关进程。

### 验证

- 代理工作台定向测试 6 项通过。
- 当前机器真实运行选择结果为 `http://127.0.0.1:7897`，出口 IP `203.27.106.146`。
- Python 编译、`compileall` 与 `git diff --check` 通过。

## 2026-09-02 AI 生成架构任务 3 修复

### 已完成

- 将创意生成服务接到可注入的 `ModelClient`，并在环境变量齐全时由 `StudioApplication` 注入 `HttpModelClient`。
- `ai_creative.py` 的提示词组装改为通过 `CompiledPrompt` 渲染，保留原有提示词内容和兼容出口。
- `schemas.py` 补上了展示类文本 URL 拦截、`content_extensions` / `keywords` 非空校验，以及三套视觉方案轮播屏数一致性检查。
- 新增回归测试，覆盖 generic model client 运行路径和展示类 schema 的收紧规则。

### 验证

- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest tests.test_schemas tests.test_generation_service -v`
- `PYTHONPATH=D:\code\ai_creative_studio\src python -m unittest discover -s tests -v`
- `python -m compileall -q src chat2api`
- `node --check static\app.js`
- `git diff --check`

### 未完成

- 真实 AI 网关调用未执行；当前验证全部基于确定性测试和本地编译检查。

## 2026-09-02 已选标签保留并高亮

### 已完成

- 修正报表选择行为：已选标签不再从表格移除，而是继续显示在原分类位置并使用高亮/勾选状态。
- 保留顶部摘要、确认后整组收起、点击“修改”重新展开及点击已选项取消选择。

### 验证

- 前端专项测试、JavaScript 语法检查和差异检查通过。
- 浏览器交互确认已选项保留在表格中并高亮；未发起真实 AI 请求。

## 2026-09-01 ClipProxy 与 VPN 路由研究

### 已完成

- 核对 ClipProxy 官方帮助中心、静态 ISP 使用/白名单、协议 FAQ 与 Mihomo 官方 TUN 文档。
- 补充 Mihomo GitHub issue 的 TUN+外部 SOCKS5、Mihomo+WARP 叠加故障案例，以及论坛个案边界。
- 结论：官方未要求或建议额外开启 VPN；VPN 只在改善到 ClipProxy 的可达性/路径时可能有帮助，叠加会增加路径和回环风险。
- 研究笔记已保存为 `docs/research/2026-09-01-clipproxy-vpn-routing.md`。

### 验证

- 官方静态 IP 文档示例支持直接使用 IP+端口（账号密码或白名单）连接，并提供 SOCKS5 `curl` 验证方式。
- Mihomo 官方文档确认 TUN `auto-route` 会把全局流量导入虚拟网卡；未发现商业 VPN 必须开启的要求。

## 2026-09-01 代理工作台复核修复

### 已完成

- 修复代理工作台 SOCKS5/SOCKS5H 出口测试原先误用标准库 `urllib` 的问题，改用与 `chat2api` 一致的 `curl_cffi` 客户端。
- 增加无效端口和无效代理 URL 的容错，避免保存/测试时窗口异常。

### 验证

- `tests.test_launcher_proxy`：5 项通过。
- 使用项目 `.venv` 通过本机 `127.0.0.1:7897` 代理实测出口 IP 返回成功。
- Python 编译、`compileall` 和 `git diff --check` 通过。

## 2026-09-01 独立网络代理工作台

### 已完成

- 新增独立 `proxy_workbench.py` 入口，也可从启动控制台打开独立窗口；代理配置不再混入登录配置。
- 支持 HTTP、HTTPS、SOCKS5/SOCKS5H、地址、端口、可选账号密码的可视化编辑。
- 支持代理 URL 构造、解析、密码脱敏、保存/清除 `PROXY_URL` 和通过公网回显服务测试出口 IP。
- 新增 `tests/test_launcher_proxy.py`，覆盖凭据编码、解析和脱敏。

### 验证

- 代理定向测试 3 项通过；`python -m py_compile launcher.py proxy_workbench.py`、`python -m compileall -q src chat2api launcher.py proxy_workbench.py` 通过。
- 全量测试仍受工作树既有 `creative_studio.generation_models` 缺失、认证仓储接口缺失及 SQLite Windows 文件锁测试失败影响，与本次代理功能无关。
- 未修改当前 `.env` 的代理值，未发起 ClipProxy 真实代理测试。

## 2026-09-01 报表式标签编辑器

### 已完成

- 将正式第 2 步从章节折叠改为图 1 的报表式标签布局；分类作为表格列，选项使用紧凑选择按钮。
- 展示类和叙事类所有现有标签组统一支持独立“确认 → 上方摘要/收起 → 修改展开”状态；目标人群保留主/副选择。
- 保留现有标签配置、`creative_tags` 字段、自动保存、卖点过滤、美术级联和轮播条件逻辑。
- 编辑报表时，已选选项从可选列表逐项消失，并可通过已选标签移除后重新选择。
- 新增 `.scratch/report-tag-editor/spec.md` 变更卡及前端结构契约测试。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_frontend_tag_reports -v`：2 项通过；全量测试受工作树中既有 `creative_studio.carousel` 导入缺失和轮播校验失败影响，未通过（与本次前端改动无关）。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 浏览器实测桌面和移动端：报表确认后收起、修改后展开，`390px` 无横向溢出；未发起真实 AI 请求。

### 未完成

- 尚未人工验收真实 AI 文字/图片生成质量。

## 2026-09-01 AI 创意生成架构重构设计

### 已完成

- 基于轮播功能引入后的实际调用链，重新梳理整体 AI 架构并确认采用 B 路线：保留现有页面、工作台 API、SQLite 和 `chat2api`，重建内部生成模块接口。
- 明确文字创意采用“一次用户请求、一次正常文字 AI 调用、直接返回最终创意”；标签和轮次是给 AI 的 brief，不要求 AI 回填 `resolved_tags`。
- 将轮播建模为单个创意方案内部的 `frames`，与一批中的 3 个方案分离；第一阶段保持每个展示类方案一张首帧参考图。
- 新增并提交设计文档：`docs/superpowers/specs/2026-09-01-ai-generation-architecture-design.md`，提交 `267e4b1`。

### 验证

- 已完成设计文档自检和 `git diff --check`；本次未修改业务代码、数据库、AI 网关或运行数据。

### 未完成

- 等待用户审阅设计文档；尚未编写实现计划或开始代码重构。

## 2026-09-01 撤回临时内网访问

### 已完成

- 用户确认同事使用结束，撤回临时内网共享。
- 启动器网页服务绑定恢复为 `127.0.0.1:8775`。
- 删除 Windows 防火墙规则 `AI创意工作台网页 8775（局域网）`。
- AI 网关继续保持 `127.0.0.1:8780`。

### 验证

- 网页进程已重启并确认只监听回环地址；防火墙规则查询为空。
- 已验证本机健康接口可访问，内网地址请求失败；当前未检测到 8780 网关监听，未发起真实 AI 请求。

## 2026-09-01 临时开放网页内网访问

### 已完成

- 用户明确确认同事需要从内网访问，启用临时共享模式。
- 启动器网页服务绑定改为 `0.0.0.0:8775`。
- 防火墙仅放行 TCP 8775 的 `LocalSubnet` 入站访问；AI 网关继续保持 `127.0.0.1:8780`。
- 本机内网地址为 `192.168.1.135`，同事可访问 `http://192.168.1.135:8775/`。

### 风险和回滚

- 当前应用无登录、权限和项目隔离；临时共享期间同事可访问和修改本机全部项目数据。
- 使用结束后将 `WEB_BIND_HOST` 恢复为 `127.0.0.1`，删除规则 `AI创意工作台网页 8775（局域网）`，再重启网页服务。

## 2026-09-01 撤回网页内网开放

### 已完成

- 按用户要求撤回刚才的内网访问配置。
- 启动器网页服务绑定恢复为 `127.0.0.1:8775`。
- 删除 Windows 防火墙规则 `AI创意工作台网页 8775（局域网）`。
- AI 网关继续保持 `127.0.0.1:8780`，未对内网开放。

### 验证

- 已检查启动器配置和防火墙规则状态；当前网页与网关进程仍在运行，但均只监听回环地址。
- 已执行 Python/JavaScript 语法、仓储单测和差异检查；未发起真实 AI 请求。

### 未完成

- 当前仍为本机单用户版本；如需再次开放内网，必须重新确认并先补认证、权限和数据隔离方案。

## 2026-09-01 章节标题显示已选标签

### 已完成

- 将章节标题下的“x 项已选”替换为实际已选标签名称，展示类和叙事类均适用；多项选择以顿号分隔，长文本按标题区域截断显示。
- 美术表现风格章节同时显示已选相关度、具体风格和参考作品摘要，保持级联选择结果可见。
- 修正章节推进：确认最后一个可见章节后不再循环打开第一个章节，而是将所有章节收起。
- 保留选项点击取消、主选/辅助递补、条件章节过滤、自动保存和生成逻辑。

### 验证

- 浏览器实测展示类标题显示“全静态”等实际选项；叙事类 5 个章节均可显示已选名称。
- 最后一个可见章节确认后展开章节数为 `0`；`1280x720` 和 `390x844` 无横向溢出，浏览器控制台 error/warn 为空。
- 已恢复当前项目为展示类；未发起真实 AI 文字或图片请求。

## 2026-09-01 叙事类标签交互与展示类统一

### 已完成

- 将叙事类从“按 category 拆成多个章节”调整为与展示类一致的“一个标签组一个章节”。
- 叙事类每个章节内部仍按 category 分组展示选项，保留 5 个标签组和全部 125 个选项。
- 叙事类复用展示类相同的主选/辅助顺序、选项上限、选中摘要、章节折叠和确认继续逻辑；未修改标签 key、数据结构、API 或生成逻辑。

### 验证

- 浏览器实测叙事类显示 5 个章节；“目标人群”展开后显示 5 个分类、25 个选项，主选摘要正常。
- `1280x720` 和 `390x844` 下章节及选项无横向溢出；浏览器控制台 error/warn 为空。
- 已恢复当前项目为展示类；未发起真实 AI 文字或图片请求。

## 2026-09-01 创意类型切换固定对齐

### 已完成

- 修正“02 创意定位”标题右侧的展示类/叙事类切换布局，将工具组明确固定为占据剩余空间并靠右对齐。
- 展示类与叙事类选中状态使用同一位置和宽度，不再因模式切换出现控件跑到左侧的视觉跳动。
- 移动端继续使用整行模式切换，保留原有画幅显隐和项目保存逻辑。

### 验证

- 浏览器实测 `1280x720` 和 `390x844`：展示类、叙事类切换位置稳定，无横向溢出。
- 已恢复当前项目为展示类；浏览器控制台 error/warn 为空，未发起真实 AI 文字或图片请求。

## 2026-09-01 画幅控件移至任务说明

### 已完成

- 将横版/竖版画幅控件从“02 创意定位”标题工具组移至“01 任务说明”标题右侧，保留原有 `#aspectField`、画幅值和自动保存逻辑。
- “02 创意定位”标题右侧仅保留展示类/叙事类切换，并在桌面端保持靠右对齐。
- 移动端将画幅控件和类型切换分别整理为整行布局，避免标题挤压和横向溢出。

### 验证

- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：画幅位置、类型切换位置及展示/叙事显隐正确，无横向溢出。
- 浏览器控制台 error/warn 为空；未发起真实 AI 文字或图片请求。

## 2026-09-01 标签选项密度收紧

### 已完成

- 桌面端标签选项改为约 `190px` 的紧凑列宽，按可用空间自动排列，避免少量选项被 `1fr` 拉伸到整行。
- 选项间距收紧到 `6px`，单项高度调整为 `34px`；移动端恢复 `38px` 触控高度并保持单列。
- 保留选项选择、禁用、提示、主/辅助芯片和章节交互，不修改标签配置或数据合同。

### 验证

- `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：四项可在桌面同排、宽屏自动增列、移动端单列，无横向溢出；控制台 error/warn 为空。
- 未发起真实 AI 文字或图片请求。

## 2026-09-01 定位工具组对齐微调

### 已完成

- 移除“目标画幅”四字标签，仅保留横版/竖版分段按钮。
- 将画幅按钮贴近“创意定位”标题右侧，展示类/叙事类切换固定在同一工具组最右端。
- 移动端保持类型切换与画幅上下排列，桌面/移动端现有交互和自动保存不变。

### 验证

- `node --check static/app.js`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：标题旁控件顺序、尺寸、类型切换和画幅显隐正确，无横向溢出；控制台 error/warn 为空。
- 当前项目设置保持为展示类；未发起真实 AI 文字或图片请求。

## 2026-09-01 创意定位工具组重排

### 已完成

- 将展示类/叙事类切换从页面顶部介绍区移至“02 创意定位”标题右侧。
- 将目标画幅从高级生成设置移至同一标题工具组；叙事类仍自动隐藏画幅控件，展示类恢复显示。
- 桌面端工具组采用紧凑分段控件，移动端自动换行，保留原有模式切换、画幅选择、自动保存和生成行为。

### 验证

- `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：标题旁工具组尺寸稳定、展示/叙事切换和画幅显隐正确、无横向溢出。
- 浏览器控制台 error/warn 为空；当前项目设置已恢复为展示类；未发起真实 AI 文字或图片请求。

### 未完成

- 仍需人工验收真实 AI 生成质量和图片任务链路；当前应用仍只适合本机单用户使用。

## 2026-09-01 标签章节文案精简

### 已完成

- 移除第 2 步章节列表上方的“展示类/叙事类创意定位”摘要、流程说明和总选计数。
- 移除展开章节中重复的模块名、通用说明、`按顺序选择`提示、额外计数条以及必填未完成状态的“需要完成”文案。
- 保留章节标题、已完成数量、分类标题、已选标签芯片、选项上限和确认章节行为；未修改标签规则、API、数据库和生成链路。

### 验证

- `python -m unittest discover -s tests -v`、`node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check` 通过。
- 浏览器实测展示类展开章节：摘要块、重复标题、顺序提示和计数条均未渲染，11 个选项正常显示；`390x844` 无横向溢出。
- 未发起真实 AI 文字或图片请求。

## 2026-09-01 桌面工作区排版密度重设计

### 已完成

- 将正式页面的介绍区、步骤条、编辑区和结果区从固定 `1120px` 窄栏扩展为带安全边距的宽屏工作区，宽屏最多使用 `1720px`。
- 第 2 步章节闭合时使用两列排列，展开章节横跨编辑区整行；展示/叙事标签选项按桌面宽度使用三列/四列网格，减少长列表滚动。
- 右侧实时创意简报扩大到 `320px` 并在桌面滚动时吸附；第 3 步结果区改为直接占满步骤列，消除旧居中偏移造成的右侧空白。
- 移动端继续使用单列章节、固定底部操作栏和项目抽屉，不修改 API、数据库、标签规则或生成链路。

### 验证

- `node --check static/app.js`、`git diff --check` 通过。
- 浏览器实测 `1280x720`、`2048x1050` 和 `390x844`：展示类/叙事类章节单开、展开章节横跨整行、结果区宽度正确，三种视口无横向溢出。
- 浏览器控制台 error/warn 为空；未发起真实 AI 文字或图片请求。

### 未完成

- 仍需人工验收真实 AI 生成质量和图片任务链路；当前应用仍只适合本机单用户使用。

## 2026-09-01 章节收起交互调整

### 已完成

- 移除章节底部左侧“完成本章/跳过本章”按钮，仅保留“确认本章并继续”。
- 进入第 2 步“创意定位”时自动将所有章节设为收起；当前章节即使没有选择，也可点击标题正常收起。

### 验证

- `node --check static/app.js`、`git diff --check` 通过；页面章节标题折叠逻辑保持可用。

## 2026-09-01 主辅标签顺序选取优化

### 已完成

- 将主选/辅助从两套重复选项改为统一选择池：第一次选择自动成为主选并带星标，后续选择自动成为辅助。
- 删除主选后，最早的辅助标签自动递补为主选；底层 `creative_tags` 仍按原主选字段和辅助字段保存，兼容现有接口。

### 验证

- 浏览器实测首选、后续选择、移除主选递补均符合顺序规则；单元测试、JavaScript 语法和差异检查通过。

## 2026-09-01 正式版接入方案 C 标签章节流程

### 已完成

- 将方案 C 的章节式标签选择接入正式第 2 步“创意定位”，保留现有项目、自动保存和 `creative_tags` 字段结构。
- 展示类按配置模块形成章节；叙事类按大模块下的分类拆分章节，左侧分组标题、章节序号和完成状态保持清晰。
- 主选/辅助选择、单选限制、美术风格三级级联、卖点→展示内容事实过滤、轮播条件字段和标签定义提示均改为章节内交互。
- 点击其他章节自动折叠当前章节；支持确认本章并继续和跳过本章；叙事类标签末尾问号仅在显示层移除。
- 增加依赖清理：卖点、轮播或美术相关度变化后，自动清理不再适用的临时标签，避免保存失配值。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、`git diff --check`：通过。
- 正式页面 `127.0.0.1:8775` 实测叙事类章节、主/辅助选择、完成状态和问号显示；展示类及条件联动沿用前轮验证。
- 1280×720 与 390×844 检查无横向溢出；浏览器 error/warn 日志为空。

### 未完成

- 未发起真实 AI 文字或图片生成请求，仍需人工验收生成质量。
- 当前页面仍只适合本机单用户使用，未涉及内网部署、认证或权限。

## 2026-09-01 标签折叠流程视觉原型

### 已完成

- 根据展示类与叙事类 Excel 的模块定义、选择规则和条件关系，新增隔离原型 `static/tag-flow-prototype.*`；没有修改两份 Excel 或正式标签配置。
- 完成 A“聚焦卡片”、B“清单工作台”、C“章节轨道”三个结构差异明显的方案，通过 `?variant=A|B|C` 和底部切换器比较。
- 三个方案都支持单模块展开、返回编辑、完成并继续、必填校验、可选项明确跳过、全部配置抽屉和展示/叙事模式切换。
- 根据 C 方案补齐展示类模块专属展示逻辑：主目标用户与附目标用户拆分为独立模块；主选/辅助角色位分离；产品卖点实时过滤展示内容；美术风格按相关度、具体风格、参考对象三级展示；动态方案使用主体×背景九宫格；语音钩子、视觉母题和轮播形式按分组呈现。
- 选择多画面轮播时动态插入轮播数量和轮播形式，进度分母同步变化；切回单画面时清除条件配置并提示。
- 新增 `.scratch/tag-accordion-prototype/spec.md`，记录设计问题、非目标、验收和回滚。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`node --check static/tag-flow-prototype.js`、`python -m compileall -q src chat2api` 和 `git diff --check`：通过。
- 浏览器实测 A/B/C 均只有一个展开模块；完成继续、明确跳过、条件模块、摘要抽屉和叙事模式切换可用，控制台无 error/warn。
- 1280px 下 A/B/C 均无横向溢出；390×844 下为单列、吸顶摘要、固定底部主操作，页面无横向溢出。
- 原型只使用内存中的代表性标签样例，未连接真实 API、SQLite 或 AI；正式页面尚未修改，等待用户选择方向。
- 本轮浏览器检查：C 方案初始展示类为 `9/12`，默认展开“动态方案”；卖点变更会清理失配展示内容；九宫格渲染 9 个组合；390px 视口 `scrollWidth=clientWidth=375`，控制台无 error/warn。

## 2026-09-01 代码规范文档

### 已完成

- 新增根目录 `CODE_STYLE.md`，按真实代码区分正式原生前端、Python 后端和隔离 React 原型的技术栈与边界。
- 统一组件职责、领域命名、文件组织、导入顺序、格式、CSS、API/数据安全和提交前检查规则。
- 明确复杂注释应解释原因与约束；JavaScript/TypeScript 对公共和复杂边界使用 JSDoc，Python 使用文档字符串。
- 在 `AGENTS.md`、README 和项目代码地图中增加规范入口；新增 `.scratch/code-style/spec.md` 记录目标、非目标、验收和回滚。

### 验证

- 本次只修改工程文档，没有修改业务代码、依赖、数据库、AI 网关或运行数据。
- 已核对规范与当前正式 `static/`、Python `src/`、测试以及 `frontend/` 原型配置一致。
- `git diff --check` 通过（仅有既有 Windows 换行转换提示）；独立读者能够准确识别正式技术栈、原型边界、注释规则、结构变更要求和最小检查。
- 根据独立读者反馈补清公共函数、上下文编码、ARIA、临时状态、依赖锁定、API 包络、秘密注入和测试夹具的适用边界。

## 当前结论

- 已从原 Web ERP 快速提取出独立项目 `D:\code\ai_creative_studio`。
- 当前独立项目是单机网页原型：网页 `8775`，AI 网关 `8780`，数据保存在自己的 `data/`。
- 展示类和叙事类生成入口、项目 CRUD、历史、采用关系、参考文件和展示类异步图片任务已经具备。
- 原 ERP 代码、数据库、账号令牌和服务端口未被本项目接管；原项目保持原样。
- 未来目标是公司内网多人使用；认证、项目归属、权限、自动备份和服务器部署尚未开始。

## 本轮文档整理

### 已完成

- 新增项目级 `AGENTS.md`，定义智能体阅读顺序、修改门禁、数据边界和验证规则。
- 新增 `项目代码地图.md`，记录真实入口、调用链、API、数据表和已知缺口。
- 新增 `docs/operations.md`，记录当前单机启停、数据、备份和恢复边界。
- 新增 `docs/变更卡模板.md`，统一后续需求和验收记录。
- 新增 `CHANGELOG.md`，建立用户可见变更记录入口。
- 新增 `docs/research/2026-08-31-ai-software-engineering-process.md`，收录 NIST、OpenAI、Anthropic、OWASP、DORA、GitHub、SQLite、SemVer 等一手资料及当前项目差距。

### 验证

- 文档路径和相互引用已检查。
- 文档整理未修改业务代码。
- 独立项目此前已通过仓储定向测试 `3 passed`、Python 编译、JavaScript 语法和本地 API 冒烟。

## 2026-08-31 启动控制台

### 已完成

- 新增 `launcher.py` 本地 Tk 启动控制台，支持保存脱敏编辑的 Access Token 和 Session Cookie。
- 支持启动、停止、重启、连接检测和打开网页；启动后自动打开 `127.0.0.1:8775`。
- 将 `启动AI创意工作台.bat` 调整为环境准备和打开控制台，不再直接占用命令行窗口。
- README 和运维手册已补充控制台用法。

### 验证

- 已完成 `python -m py_compile launcher.py`、`node --check static/app.js`、`python -m compileall -q src chat2api launcher.py`、`git diff --check`；仓储测试 `3 passed`。
- 已定位并修复 Windows 批处理仅 LF 换行导致的 `cmd.exe` 解析失败；已通过批处理级启动验证，成功拉起 `launcher.py`。

### 未完成

- 尚未在带桌面交互的真实 Windows 会话中逐按钮验证视觉效果和进程停止行为。
- 代理地址不再在控制台显示；检测连接增加等待状态和超时失败提示；Cookie-only 启动会自动换取 Access Token。
- 启动按钮改为后台拉起服务并立即反馈“启动中”，避免进程初始化阻塞控制台操作。
- 修复 Token/Cookie 超长文本导致 Tk Entry 点击卡顿：默认仅显示固定长度占位，点击输入框后直接粘贴新值，不载入旧长文本。
- “检测连接”在仅有 Session Cookie 时会自动启动网关、换取 Access Token 并回填为已配置状态。
- 修复检测流程跳过“已过期但非空”的旧 Token：存在 Cookie 时每次检测都会强制换取新 Token。

## 2026-08-31 标签选择控件

### 已完成

- 根据用户提供的叙事类和《剑侠传奇》展示类 Excel 配置，整理出 `config/creative_tag_options.json`；包含叙事类 125 个选项和展示类 11 个输入模块。
- 新增 `GET /api/tag-options` 只读配置接口；扩展服务端标签规范化和 AI 提示词分组，保留已有项目标签兼容性。
- 前端改为按叙事类/展示类动态渲染单选、多选和美术风格三级级联控件。
- 展示类支持产品卖点→展示内容事实过滤、轮播数量/形式条件显示、辅助标签和三级参考最多选择 2 项。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api`、标签 JSON 校验和 `git diff --check` 已通过。
- 本地页面已实际检查叙事/展示模式切换、展示内容过滤、轮播条件显示和叙事类选项选择。
- 未验证真实 AI 文字/图片生成质量；未在带桌面的真实启动器会话中逐按钮验证。

## 2026-08-31 工程协作文档配置

### 已完成

- 建立本仓库的工程协作文档约定。
- Issue tracker 采用 `.scratch/<feature-slug>/` 下的本地 Markdown。
- 变更卡和研究笔记按需保存在仓库文档目录中。

### 验证

- 已检查新增文档路径、相互引用和 Markdown 差异。
- 本次仅修改工程协作文档，未修改业务代码。

## 2026-09-01 清理旧工程技能影响

### 已完成

- 移除旧工程技能专属的导航文档和 `AGENTS.md` 中对应入口。
- 清理旧工程技能专名及安装脚本名称，保留既有变更卡、原型和研究资料。

### 验证

- 已搜索仓库文本，未发现旧技能专名或路径引用。
- 未修改业务代码、依赖、数据库、AI 网关或运行数据。

## 下一步（按优先级）

1. 用户先阅读并确认这套文档结构和边界。
2. 建立第一批固定 AI 评估样例，先验证展示类/叙事类输出质量。
3. 补齐当前单机应用的日志、配置模板和一键备份说明。
4. 另开变更卡设计多人内网版本：账号、项目归属、管理员和审计。
5. 多人版本通过内网验收后，再讨论 Windows 服务化、HTTPS 和公网门禁。

## 尚未完成

- 未把当前版本部署到公司内网。
- 未实现登录、权限、数据隔离、自动备份或公网访问。
- 未执行真实 AI 文字/图片生成验收。
- 未迁移原 ERP 历史项目、图片或数据库数据。

## 决策记录

- 2026-08-31：用户要求先整理 `AGENTS.md`、代码地图和项目管理文件，暂停直接落地多人登录/部署设计。
- 2026-08-31：研究文档完成，后续按“变更卡 → 定向验证 → 备份/回滚 → 记录进度”的小批量流程推进。

## 2026-08-31 UI 重设计原型

### 已完成

- 新增独立假数据页面 `static/ui-prototype.html`，通过 `?variant=A|B|C` 比较三栏工作台、分步创作流和结果优先画板三种信息架构。
- 新增统一原型设计系统、假项目和固定 3 套假方案；支持项目/模式/步骤/配置抽屉/方案选择/采用等内存交互。
- 原型与当前生产页面隔离，没有修改现有 `static/index.html`、`static/app.js`、`static/styles.css`，没有连接真实 API、数据库或 AI。

### 验证

- `node --check static/ui-prototype.js` 通过，本地静态服务返回 HTTP 200。
- A/B/C 桌面渲染和关键交互已检查；浏览器没有 error/warn 日志。
- 390px 宽度下三个变体均无横向溢出；展示类固定显示 3 套假方案。

### 未完成

- 尚未由用户选择最终布局或混搭方向，未把任何原型提升为正式页面。
- 尚未接入真实项目、标签、历史、图片任务或生成 API；未执行真实 AI 请求。

## 2026-08-31 UI 组件与产品参考调研

### 已完成

- 新增 `docs/research/2026-08-31-ui-component-and-app-inspiration.md`，对照 Midjourney、Runway、Adobe Firefly、Lightroom、Linear、InvokeAI 和主流 React 组件库整理下一版方向。
- 明确下一版不再采用传统 dashboard 或全量表单首屏，改为“生成 Feed + 视觉选片网格 + 紧凑项目导航 + 按需配置 Sheet”。
- 推荐组件底座为 shadcn/ui；Origin UI 只挑选少量输入组件；Magic UI、Cult UI、Aceternity 和 Tremor 不作为应用骨架。
- 建议后续以隔离的 Vite + React + TypeScript + Tailwind CSS 前端做假数据原型，保留现有 Python API、SQLite 和原生页面直到新 UI 验收。

### 未完成

- 尚未得到用户对 React/Vite 隔离原型范围的明确确认，因此没有新增依赖、脚手架或正式前端迁移代码。
- 尚未确定最终 Design System、组件版本、构建产物路径和 Python 静态托管切换方案。

## 2026-08-31 React UI 假数据原型（第二版）

### 已完成

- 用户已确认用隔离的 React/Vite 原型继续探索；新增 `frontend/`，采用 React 19、TypeScript、Tailwind CSS 和 shadcn/ui 组合方式。
- 完成三个信息架构差异明显的可点击方案：A“会话流”、B“素材审阅”、C“专注对比”，入口为 `http://127.0.0.1:8796/?variant=A|B|C`。
- 实现假项目切换、创意方向选择、采用/收藏反馈、生成模拟、参数摘要和右侧创意配置 Sheet；多选项使用可搜索的 Command/Popover 交互。
- 新增 `.scratch/ui-redesign-v2/spec.md` 记录范围与验收；旧 `static/ui-prototype.*` 保留用于对照，当前正式 `static/` 页面和 Python 后端未切换。

### 验证

- `npm run build` 通过：TypeScript 编译和 Vite 生产构建均成功。
- 在 1280×720 下检查 A/B/C 首屏、图片加载、选择状态和配置 Sheet；浏览器控制台无 error。
- 在 390×844 下检查 A/B/C，页面宽度均为 390px，无横向溢出。
- 所有项目、方案、评分和动作仍为前端内存假数据，没有发出真实 AI、API 或数据库请求。

### 未完成

- 尚未由用户确定主方案，以及是否把 A 的生成流、B 的选片网格和 C 的对比视图合并为正式产品结构。
- 尚未接入真实项目/API/SQLite/图片任务，未确定构建产物如何由 Python 服务托管，也未替换正式页面。
- 尚未实现登录、权限、数据隔离、内网/公网部署、自动备份或数据库迁移。

## 2026-08-31 旧版 B UI 最终优化

### 已完成

- 按最终设计交接优化隔离的 `static/ui-prototype.*` 旧版 B 假数据原型，未修改正式原生页面、`frontend/` React 原型或后端。
- 将流程从四步收为三步：任务说明、创意定位、生成与采用；对比视图改为第 3 步原位切换。
- 第 1 步改为展示类/叙事类两级任务类型与单一任务描述；项目名移至顶部并随项目切换更新。
- 第 3 步实现 3 个稳定方案位、完整正文展开、单项排队/生成/完成/失败/重试假状态，以及直接采用/替换。
- 增加左侧覆盖式项目栏、结果阶段简报摘要、移动端固定操作栏和炭灰 × 青绿 B 专属视觉系统。
- 更新 `.scratch/ui-redesign/spec.md`，记录最终实现边界和验证结果。

### 验证

- `node --check static\\ui-prototype.js`：通过。
- `git diff --check`：通过（仅有既有换行格式提示）。
- 本地 `127.0.0.1:8795` 浏览器检查：三步流程、两级任务类型、项目栏、定位控件、方案网格/对比、采用、失败重试均可交互。
- 390px 视口检查：底部操作栏存在，`scrollWidth` 与 `clientWidth` 均为 375，无横向溢出；浏览器 `error/warn` 日志为空。

### 未完成

- 仅验证假数据 UI，未验证真实 API、数据库、AI 文字或图片生成。
- 尚未由用户验收最终视觉，也未将原型接入正式页面。

## 2026-08-31 正式页面迁移到 B 三步工作流

### 已完成

- 用户确认将旧版 B 设计提升为正式页面；创建 `codex/formal-b-ui` 分支并建立 `.scratch/formal-b-ui/spec.md` 变更卡。
- 正式 `static/index.html`、`static/app.js`、`static/styles.css` 替换为炭灰 × 青绿三步工作流，同时继续连接真实项目、SQLite、标签配置、历史、采用和图片任务接口。
- 正式页面支持顶部项目入口与覆盖式项目栏、可编辑项目名、自动保存状态、前两步实时简报、第 3 步真实历史和移动端底部操作区。
- 保留展示/叙事分支、标签依赖过滤、两批上限、图片单项重试、旧定位历史和采用替换行为。
- `AGENTS.md` 已记录正式前端入口、原型边界、回滚方式和桌面/移动端验证要求；代码地图和变更日志同步更新。
- `.gitignore` 补充网关任务状态、生成图片和运行数据子目录，防止运行产物进入 Git。

### 验证

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api launcher.py`、`git diff --check`：通过。
- 正式服务在 `127.0.0.1:8797` 加载真实 SQLite 叙事项目和历史成功；三步切换、项目入口和真实结果渲染可用。
- 390px 视口无横向溢出，修复旧移动端侧栏规则造成的顶部空白；浏览器控制台无 error/warn。
- 收尾复核：默认正式端口 `127.0.0.1:8775` 已启动并加载正式页面；临时验证端口 `8797` 已停止。
- Git 检查点为分支 `codex/formal-b-ui`、提交 `e39b571`；提交后的全量 `git diff --check` 通过。

### 未完成

- 本次未发起真实 AI 文字或图片生成请求；AI 质量和真实图片任务链路仍未验证。
- 正式页面尚未部署到内网或公网，仍只适合本机单用户使用。

## 2026-09-01 顶部品牌与项目入口

### 已完成

- 将正式页面和项目抽屉中的 `AI` 文字方块替换为原创“轨道＋闪光点”矢量标识，品牌名称统一为“辅助创意工具”。
- 将原页面中部的“当前项目”入口重做为品牌右侧的“项目列表”按钮；根据后续反馈移除顶部和左栏独立命名框，改为选中项目卡内联编辑名称。
- 左侧项目栏使用真实遮罩按钮，点击右侧空白区域即可关闭；移动端顶部栏收敛为品牌图标、项目列表图标和保存状态。
- 在 `AGENTS.md` 固化顶部导航的短操作路径约定，并新增 `.scratch/header-brand-project-menu/spec.md` 变更卡。

### 验证

- `1280x720` 下项目列表按钮位于品牌右侧（约 `x=198px`），项目卡可内联改名并自动保存，切换项目不收栏，点击右侧遮罩可收回；页面无横向溢出。
- `390x844` 下项目列表按钮约位于 `x=68px`，遮罩点击区准确覆盖侧栏右侧 90px 空白；页面宽度与视口一致，无横向溢出。
- 未调用真实 AI、未修改数据库结构、AI 网关或生成链路。

## 2026-09-01 展示类轮播逐轮创意定位

### 已完成

- 展示类轮播支持用户先选择“是/否”；第 1、2 步不调用 AI，仅在最终生成请求时执行一次 AI 流程。
- 固定选择 2～5 屏后显示逐轮定位面板，提供产品卖点、展示内容、视觉母题三个选填字段；第 2 轮起默认继承第 1 轮，可切换为自定义并恢复继承。
- 选择“AI决定”时不预先生成轮次或询问屏数，三套方案在一次 AI 输出中使用统一的 2～5 屏数量。
- AI 轮播返回结构补充 `carousel_frames` 与 `resolved_tags`，空白适用标签必须从配置目录补全；结果卡片展示轮次和最终标签。
- 固定屏数校验放宽为 2～5 屏；未改变既有数据库结构和图片任务链路。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：15 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。
- 本地页面检查：固定屏数轮次页、继承/自定义切换、AI决定隐藏逻辑均正常；未发起真实 AI 请求。

### 未完成

- 尚未进行真实 AI 质量评估和真实图片生成验收；当前仅验证功能链路。

## 2026-09-01 AI接口失败诊断与会话重试

### 已完成

- 根据页面失败截图、生成失败记录和网关状态复现并定位：旧 Access Token 被上游拒绝时，网关此前只返回通用 502，未主动刷新 Session Cookie。
- `chat2api/routes_chat.py` 在 requirements/prepare/对话返回 401 或 403 时最多触发一次 Cookie 会话刷新并重试，避免重复生成请求。
- `src/creative_studio/ai_creative.py` 的接口异常提示增加 HTTP 状态和网关检查方向，不暴露令牌或完整上游响应。
- 当前网关状态已恢复：`/health` 显示令牌有效，`/v1/models` 显示 `detected=true`。

### 验证

- `.venv` 下重试判定辅助函数检查通过。
- `PYTHONPATH=src python -m unittest discover -s tests -v`：15 项通过。
- `python -m compileall -q src chat2api`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 未再次主动调用真实 AI 生成，避免重复消耗额度；需要重启网页/网关服务后由用户重新点击生成确认完整链路。

## 2026-09-01 启动器连接检测修复

### 已完成

- 修复启动器在 8780 已有健康网关时重复拉起新网关的问题，检测流程现在优先复用现有健康实例。
- 连接检测和 Cookie 换 Token 失败时记录脱敏后的 HTTP 状态/错误片段，不再只显示“连接失败”。
- 修复检测线程异常回调对局部异常变量的延迟引用，确保错误日志能稳定写入界面。

### 验证

- `PYTHONPATH=src python -m unittest discover -s tests -v`：15 项通过。
- `python -m compileall -q src chat2api launcher.py`、`node --check static/app.js`、`git diff --check`：通过。

### 未完成

- 启动器进程需要重启后加载本次修改；未再次发起真实 AI 请求。

## 2026-09-01 轮播输出契约迁移（任务1）

### 已完成

- 新增 `src/creative_studio/carousel.py` 中的 `normalize_visual_carousel_frames()`，把展示类轮播输出收敛为 `count`、可选 `form` 和连续 `frames` 的嵌套结构。
- `src/creative_studio/ai_creative.py` 的 `validate_visual_creative_recommendations()` 已切到新的轮播输出契约：三项方案、每项 `carousel` 对象、固定屏数一致、AI 屏数统一，且不再要求 `resolved_tags` 作为生成时必填用户事实。
- 新增/更新 `tests/test_carousel.py` 与 `tests/test_tag_options.py`，覆盖新嵌套形状、AI 屏数不一致、固定屏数长度/连续性错误，以及旧历史数据兼容路径。
- 代码已提交，首个实现提交为 `2672c4d`。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_carousel -v`
- `PYTHONPATH=src python -m unittest tests.test_tag_options -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `git diff --check -- src/creative_studio/carousel.py src/creative_studio/ai_creative.py tests/test_carousel.py tests/test_tag_options.py`

### 未完成

- 未发起真实 AI 请求，按任务要求也未修改 `chat2api`、数据库结构或前端。

### 追加修复

- 按复核意见补回生成结果中的顶层 `carousel_frames` 兼容字段，保持 `carousel` 作为新契约的唯一权威来源。
- 新增回归测试，确认新生成结果可经由现有历史路径继续渲染，且 `resolved_tags` 仍不作为生成时必填用户事实。
- 最新代码提交为 `9142923`，验证覆盖 `31` 项测试全部通过。

# 2026-09-02 图片任务幂等修复（review follow-up）

### 已完成

- 修正图片提交失败缓存：现在只缓存成功的 gateway 任务，同一 `request_id` 的后续重试可以重新提交，不会被本地失败结果毒化。
- 保留稳定提交键 `creative-studio-{visual_item_id}-attempt-{attempt}`、成功复用和恢复/重试隔离行为。
- 新增回归测试，覆盖“首次超时后同键重试成功”的路径。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_image_jobs tests.test_repository -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `node --check static\app.js`
- `python -m compileall -q src chat2api`
- `git diff --check`

### 说明

- 修复提交为 `0e9e5ab`。
- 未发起真实图片请求。

# 2026-09-02 图片任务幂等（任务5）

### 已完成

- 图片网关提交增加按 `creative-studio-{visual_item_id}-attempt-{attempt}` 的稳定键去重，重复提交同键会复用同一任务。
- `visual_items` 恢复与重试改为事务化，保持失败/成功/恢复边界稳定，旧 worker 不能覆盖新尝试。
- 生成服务把首帧图片派发封装成独立步骤，`image_prompt` 仍只保留在服务端。
- 新增 `tests/test_image_jobs.py`，补上重复提交、恢复重排和重试隔离回归。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_image_jobs tests.test_repository tests.test_generation_service -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `node --check static\app.js`
- `python -m compileall -q src chat2api`
- `git diff --check`

### 说明

- 代码实现提交为 `4aa9ed4`。
- 未发起真实图片生成请求。

## 2026-09-01 生成服务拆分（任务2）

### 已完成

- 新增 `src/creative_studio/generation_models.py`，把生成请求、归一化输入快照、生成上下文和生成结果收敛为冻结数据类。
- 新增 `src/creative_studio/generation_service.py`，把项目加载、输入归一化、指纹、schema 选择、预留、完成、失败回填和视觉队列派发从 `app.py` 中移出。
- `StudioApplication.generate(project_id)` 已改为 HTTP 入口薄封装，保留历史返回包络和现有 API 行为。
- 新增 `tests/test_generation_service.py`，用 fake 适配器和 fake 图片队列验证单次模型调用、空白轮播提示词可通过、叙事类不入队、展示类只入队 3 个首帧任务、异常会回填 `fail_generation`。

### 验证

- `PYTHONPATH=src python -m unittest tests.test_generation_service -v`
- `PYTHONPATH=src python -m unittest tests.test_generation_service tests.test_repository.RepositoryTests.test_project_round_trip_and_search tests.test_repository.RepositoryTests.test_visual_history_hides_image_prompt_and_exposes_carousel_frames tests.test_repository.RepositoryTests.test_new_visual_generation_remains_renderable_through_history_path tests.test_tag_options -v`
- `python -m compileall -q src chat2api`
- `git diff --check`

### 未完成

- `python -m unittest discover -s tests -v` 仍存在与本任务无关的既有仓库失败：`create_bootstrap_admin` 缺失，以及两项旧迁移测试在 Windows 上清理临时 SQLite 文件时的锁定问题。
- 未发起真实 AI 文字或图片生成调用。

## 2026-09-02 权限登录（进行中）

### 已完成

- 已加入 PBKDF2 密码哈希、会话/CSRF 令牌摘要存储、登录限流、审计、管理员普通账号管理和项目所有者隔离。
- 已接入登录、登出、强制改密、管理员账号 API 与前端登录/账号管理界面；支持一次性 CLI 或首次启动环境变量创建管理员。

### 验证

- 认证与仓储测试 25 项通过；全量确定性测试 66 项中 65 项通过。
- 全量测试唯一失败为既有 AI 配置测试，因当前环境缺少 AI 网关地址、密钥、模型和提示词变量；未发起真实 AI 请求。
- `node --check static/app.js`、Python 语法检查和 `git diff --check` 通过。

### 未完成

- 公网 HTTPS、反向代理、外部限流、生产备份和真实公网冒烟尚未配置；当前仍默认绑定 `127.0.0.1`。
# 2026-09-02 展示类提示词输出契约统一

### 已完成

- 首帧展示提示词改为输出 `creative_summary`、`creative_sources`、锁定的 `frame_count`、`visual_continuity_rules`、完整 `frame_plan` 和 `first_frame`。
- 明确 `none`、`fixed`、`ai` 三种数量规则；AI 决定数量时三套方案可独立返回 2 至 5 张。
- 轮播提示词删除旧的 `carousel`、`carousel_frames`、`resolved_tags` 和“三套方案统一屏数”要求。
- 新增版本化后续画面提示词，单次只输出一个 `frame`，包含承接和收束字段。
- 校验器、展示画面入库和公开历史过滤同步支持新结构；服务端隐藏 `image_generation_instruction` 不进入公开数据。

### 验证

- `python -m pytest -q`：107 项通过。
- `python -m compileall -q src chat2api`
- `node --check static\\app.js`
- `git diff --check`

### 说明

- 未发起真实 AI 文字或图片请求。
# 2026-09-02 展示类连续画面架构复审与 P0/P1 修复

### 已完成

- 继续接口改为返回公开逐帧 DTO，过滤 `image_generation_instruction`、本地 `image_path` 和内部会话字段。
- 新增展示方案逐帧状态查询接口 `/api/visual-items/{id}/frames/status` 和逐帧图片接口 `/api/visual-items/{id}/frames/{frame_index}/image`。
- 首帧 `first_frame.content` 写入 `display_frames.actual_content`，后续规划可读取首帧实际画面信息。
- 进程恢复时回收过期的方案继续锁和连续画面生成状态；首图失败时继续操作返回可操作冲突，不错误调用后续画面提示词。
- 新增继续接口脱敏回归断言。
- 选择方案时通过文字模型创建独立 GPT 会话，持久化供应商返回的 `conversation_id` 和 `assistant_message_id`，后续画面复用该游标。
- 历史响应补充逐帧公开状态，新增逐帧图片接口；正式页面已接入方案选择、继续生成和画面路线展示。

### 验证

- `python -m pytest -q`：109 项通过。
- `python -m compileall -q src chat2api`
- `node --check static\\app.js`
- `git diff --check`

### 未完成风险

- 后续文字模型请求仍未通过现有 Chat2API 多模态链路传递上一张实际图片；目前上一张图片只传给图片生成网关。
- 正式前端已接入新的选择、继续和逐帧状态接口，但未进行真实浏览器流程验证。
- 经确认，本阶段采用降级连续性方案：GPT 只依据上一张画面信息和已完成记录规划；图片模型继续接收上一张实际图片作为 `ref_assets`。暂不改造 Chat2API 多模态文字链路。
- 未发起真实 AI 文字或图片请求。

# 2026-09-02 创意类提示词工程研究（进行中）

### 已完成

- 收集并核对 OpenAI、Anthropic、Google、Microsoft 的官方提示词工程与评测指南，以及 Promptfoo、DSPy、DAIR.AI Prompt Engineering Guide、prompts.chat 等社区/开源实践信号。
- 新增研究笔记 `docs/research/2026-09-02-creative-prompt-engineering-research.md`，记录来源、日期、可执行结论和社区证据边界。
- 初步形成创意提示词设计方向：将创意机制与执行细节分离；先发散生成候选，再按事实、受众、差异化、可执行性和风险收敛；用固定评估集验证提示词迭代。

### 验证

- 已通过浏览器读取官方文档和公开论文摘要；未发起真实 AI 生成请求。

### 未完成

- 尚未确定第一版优先优化展示类还是叙事类提示词。
- 尚未把研究结论改写为正式配置提示词或新增评估样例。
# 2026-09-02 AI 辅助功能三路径全链路验证

### 真实请求补充验证

- 已使用当前 `chat2api/.env` 启动临时网关并发起真实 `/v1/chat/completions` 请求。
- 通过现有 SOCKS 代理请求失败：代理握手被关闭，网关返回 `502`。
- 临时绕过代理再次请求失败：无法连接 `chatgpt.com:443`，网关返回 `502`。
- 两个临时网关进程均已停止；未修改 `.env`。

### 验证结果

- 叙事类：假模型生成、结果落库、无图片任务，`2 passed`。
- 展示类不轮播/首帧：假模型生成三套方案、三张首图任务，`2 passed`。
- 展示类连续画面：方案选择、独立会话游标、按序继续、上一张图片引用、状态恢复，`4 passed`。

### 限制

- 本机 `127.0.0.1:8775` 和 `127.0.0.1:8780` 当前未启动。
- 当前进程环境未配置 AI 网关变量；未读取或修改 `chat2api/.env`，因此未发起真实 AI 文字/图片请求。

# 2026-09-02 第一套展示类静态创意提示词

### 已完成

- 新增单文件 `config/ai_visual_static_creative_prompt_v1.txt`，目标为非轮播、单核心静态画面的展示类广告创意。
- 在同一个提示词文件内用模块标题分隔接口契约、字段语义、业务上下文、创意生成引擎、候选筛选和执行约束；接口区块可单独抽取给接口层。
- 输出结构面向创意和制作评审：三套机制不同的方案、用户张力、产品价值、证据台账、静态首帧、素材计划、制作风险、首轮验证动作和服务端私有图片指令。
- 该文件可直接作为单一提示词发送；其余模块只需在不同系统中按区块手动复制，不要求拆成多个附件。

### 验证

- 已完成文本结构和字段边界的人工复核，确认单文件内接口层与业务规则层分离。
- 未修改现有业务代码、数据库、API、前端或旧提示词；未发起真实 AI 文字/图片请求。

### 未完成

- 尚未用固定脱敏业务样例进行真实模型质量评审。
- 尚未决定是否将该新结构迁移到现有 `ai_creative.py` 校验器和展示历史；后续迁移需另行评审兼容性。
# 2026-09-02 临时开放局域网访问

### 已完成

- 网页启动器改为绑定 `0.0.0.0:8775`，启动链接为 `http://192.168.1.135:8775/`。
- Windows 防火墙新增仅允许 `LocalSubnet` 的 TCP 8775 入站规则；AI 网关 8780 仍只监听回环地址。
- 本机验证首页和 `/api/health` 的回环及局域网地址均返回 200。

### 风险与回滚

- 当前内网用户可访问网页并按账号权限操作项目；不应将端口暴露到公网。
- 结束共享时，将 `launcher.py` 的 `WEB_BIND_HOST` 恢复为 `127.0.0.1`、`WEB_URL` 恢复为 `http://127.0.0.1:8775/`，删除防火墙规则 `AI创意工作台网页 8775（局域网）`，再重启网页服务。
# 2026-09-02 撤回局域网访问

### 已完成

- 停止网页服务并释放 `8775` 监听端口。
- 删除 Windows 防火墙规则 `AI创意工作台网页 8775（局域网）`。
- 启动器恢复为 `127.0.0.1:8775`，后续启动不会再次自动开放内网。
