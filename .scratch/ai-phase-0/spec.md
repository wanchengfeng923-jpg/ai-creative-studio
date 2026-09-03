# AI 重构 Phase 0 变更卡

- 日期：2026-09-03
- 状态：已完成，Phase 0 门禁通过
- 权威基线：`docs/ai-rebuild-master-plan.md` 的 Phase 0

## 目标

- 让历史、状态、采用、项目内采用快照和展示画面只通过一个 `PublicResultMapper` 生成公开对象，递归阻断私有字段。
- 提供旧 `generations.items_json` 与 `adoptions.snapshot_json` 的一次性 projection scrub；默认只读 dry-run，只在临时数据库验证写入、统计和回滚。
- 将 prompt 编译限制为 `{{name}}` 单次字面替换，并对变量集合及模板 hash fail closed。
- 保持 JPEG、PNG、WebP 参考图、下载字节、MIME、扩展名和 SQLite artifact 元数据一致。
- 保留同 fingerprint 的所有失败生成记录，持久化稳定错误代码、阶段、字段路径、可重试性、trace id 和内部诊断摘要。
- 在模型调用前拒绝缺失或非法的轮播数量，并证明模型调用次数为零。
- 移除 `creative_studio.app` 的 import-time 数据库、executor、图片任务和真实 AI client 构造；生产仍只有一个 composition root。
- 将叙事游戏资料默认路径统一为仓库实际存在的 `config/ai_creative_game_info_v2.json`。

## 非目标

- 不进入 PromptRegistry、ContractRegistry 或三个新业务 Module 的 Phase 1 工作。
- 不改变叙事、静态展示或轮播的创意输出目标，不接入静态 v1 prompt，不恢复独立首帧文字会话。
- 不修改正式 UI、网络监听、认证/权限、供应商凭据或 `chat2api/.env`。
- 不调用真实文字 AI、图片网关或浏览器，不修改 `data/creative_studio.db`、`data/images/` 或 `data/uploads/`。
- 不新增 canonical 生成表，不执行生产数据迁移或永久双写。

## 当前事实

- 生产 caller 是 `StudioApplication -> CreativeGenerationService -> _generate_with_model_client -> HttpModelClient`；旧 `LegacyCreativeGenerationAdapter` 仍为无 model client 时的兼容路径。
- `app.py` 当前在模块导入时执行 `APP = StudioApplication()`，从而打开真实 SQLite、创建图片 executor 并构造真实适配器。
- `generation_history()` 和 `public_display_history()` 通过复制后 `pop` 过滤；`adopt_visual()` 原样保存并返回 `content_json`；`select_scheme()` 公开返回 `conversation_id`。
- `reserve_generation()` 会删除同 fingerprint 的全部失败记录；`generation_history()` 只查询成功记录。
- `CompiledPrompt.render()` 在双大括号替换后又调用 `string.Template.substitute()`，会再次解释用户数据中的 `$...`。
- `GptWebImageClient.submit()` 把所有参考图编码成 `data:image/png`；下载只返回扩展名，SQLite 没有 MIME artifact 元数据。
- `CreativeGenerationService._request_and_validate()` 的第二次校验失败被压平为“AI返回结果无法解析”，丢失字段路径和原因。
- 轮播启用但数量缺失时，`_build_snapshot()` 仍产生可进入模型调用的配置。
- 默认游戏资料路径是不存在的 v1；launcher 仅通过环境变量临时指向 v2。

## 设计决策

### 公开投影 Module

在 `src/creative_studio/public_projection.py` 建立一个深 Module：其 Interface 接收内部 mapping 与结果种类，只返回显式白名单构造的新对象。历史、状态、采用、项目 adoption 和逐帧结果共同穿过该 seam。任何未知 key 默认丢弃；`image_error` 等内部诊断只映射为安全摘要。

该边界由 `docs/adr/0001-public-result-projection.md` 固定；ADR 记录替代方案、历史 projection 迁移、公开字段扩展约束和回滚边界。

禁止继续以 `dict.copy()`/`dict.pop()` 作为公开安全机制。数据库仍可保存内部 raw 数据，但任何 HTTP caller 都不得直接序列化 raw row/JSON。

仓库当前没有 export 路由或导出函数。本阶段不凭空新增用户接口；变更卡将其记录为“不适用”，未来新增 export 时必须复用同一 mapper 并补递归隐私测试。

### 历史 projection scrub

新增一次性 scrub Module，扫描 `generations.items_json` 和 `adoptions.snapshot_json`，按 `recommendation_kind` 使用同一 mapper 重建 JSON。默认 dry-run 使用 SQLite 只读连接，只输出检查行数、变化行数、私有 key 命中数和无效 JSON 数。

`--apply` 只用于显式指定的非生产数据库，并要求先生成 SQLite backup；写入放在单一事务中，写后重新读取、再次投影并核对行数/hash。工具拒绝直接 apply 仓库默认 `data/creative_studio.db`。本轮只在临时库执行 dry-run、apply、验证和 rollback 演练。

### PromptCompiler

`CompiledPrompt` 先从模板提取唯一的 `{{name}}` 集合，再要求提供变量集合完全一致；缺失和多余变量都失败。渲染按原模板位置一次拼接字面值，不再使用 `string.Template`。`$unknown`、`${task_type}` 以及用户值中的 `{{...}}` 不参与第二次解析。可选 expected template hash 与模板 SHA-256 不一致时失败。

现有 prompt builder 只把模板实际声明的受支持变量传给 compiler；当前兼容性的附加上下文保持不变，本阶段不重写业务提示词。

### 图片 artifact

以图片 magic bytes 识别 JPEG/PNG/WebP，并校验声明 MIME；参考图 data URL 使用实际 MIME。下载结果返回 typed artifact（bytes、mime、canonical extension），写入后把 MIME 保存到 `visual_items`/`display_frames` 的加法列。旧调用者可省略 MIME，已有历史路径继续可读。

### 失败契约

生成异常统一转换为结构化 `GenerationError`：`error_code`、`phase`、`field_path`、`retryable`、`trace_id`、安全 `message` 和仅持久化的内部摘要。HTTP 保留 `success=false`、`error` 文本及现有 422/503/502 映射，并加法返回结构化字段。

失败记录不参与“两批成功/pending”限额，也不被后续预约删除；新预约的 `batch_index` 继续单调递增。历史新增 `failed_generations`，只公开白名单诊断字段。

### Composition root

`StudioApplication` 改为接收 repository、auth、model/image adapter 等依赖；`create_application()` 是唯一生产构造函数，`run()` 才调用它。Handler 从 server 注入的 application 取依赖。测试用临时 SQLite、fake model、fake image queue 和固定 clock 走同一应用 Interface，不读取真实凭据。

## 配置事实

| 所在位置 | 当前默认/传递 | Adapter 实际支持 |
| --- | --- | --- |
| `app.py` | 网页 `127.0.0.1:8775`；网关 URL `127.0.0.1:8780/v1/chat/completions`；model `gpt-5-6-mini`；provider `chatgpt-web`；timeout 300；叙事 v5、展示 v2 | app 只构造配置与 HTTP adapter |
| `launcher.py` | 显式覆盖网页 8775、网关 8780、model/provider/prompt path，并把游戏资料指向 v2 | 与 app 默认一致；control token 只给图片网关 |
| `ai_creative.py` | 原始 loader 的 timeout 默认 30、prompt version 默认 v1；视觉 loader另选静态/轮播 prompt | prompt path/version 只在工作台生效；provider 仅记录，不改变网关实现 |
| `model_client.py` | 发送 model、messages、response_format、max_tokens、conversation cursor | transport 会发送全部字段，但不能证明供应商执行 |
| `chat2api/routes_chat.py` | model 进入 prepare/conversation body；messages 合并为 prompt | model 与会话 cursor 支持；`response_format`、`max_tokens` 未进入 ChatGPT Web body，因此不受支持；usage 是字符长度估算，不是 exact |
| `chat2api/config.py` | 单独启动 port 默认 8700、chat model 默认 `gpt-4o`、timeout 600；launcher 覆盖 port 为 8780 | provider 固定 ChatGPT Web；prompt path 不属于网关配置 |

本阶段将工作台经该网关得到的 usage source 标为 `estimated`，不建立第二套配置 registry。

## 影响文件

- 新增：`src/creative_studio/public_projection.py`、`src/creative_studio/projection_scrub.py`。
- 修改：`app.py`、`repository.py`、`prompting.py`、`image_jobs.py`、`model_client.py`、`generation_models.py`、`generation_service.py`、`ai_creative.py`。
- 测试：`test_prompting.py`、`test_public_projection.py`、`test_projection_scrub.py`、`test_image_jobs.py`、`test_model_client.py`、`test_repository.py`、`test_generation_service.py`、`test_app_api.py` 及受现有接口影响的定向测试。
- 文档：本变更卡、公开投影 ADR、`progress.md`、`CHANGELOG.md`、`项目代码地图.md`、`docs/operations.md` 和总纲 Phase 0 允许文件清单；不修改 UI。

## 风险

- 白名单漏掉现有前端字段会造成历史卡片信息缺失；以 `static/app.js` 的实际字段消费和旧/新 fixture 双向测试防止。
- 失败记录保留后 batch index 不再等同成功次数；限额继续只计算 pending/success，并通过回归测试固定。
- SQLite 加法列迁移若中断必须保持幂等；只用存在性检查和事务执行。
- MIME 校验会拒绝 header、扩展名与 bytes 冲突的上游结果；这是 fail-closed 行为，错误留在内部任务记录，公开只显示安全摘要。
- composition root 改造触及所有 handler caller；以真实 `run` 构造函数测试和注入应用的 handler/API 测试覆盖。

## 回滚

- 代码与文档可按本轮 Git diff 逐文件反向撤销；不覆盖运行库。
- SQLite 的新增 nullable/default 列为加法迁移，回滚代码时保留列，旧代码会忽略它们。
- 临时库 scrub 回滚使用工具创建的 SQLite backup 还原；真实库本轮不会执行 apply。
- 若公开白名单遗漏字段，可仅回滚 mapper caller 或补充明确允许字段，不能恢复 raw JSON 直出。

## 验收例子

- 在 raw 历史、adoption 和嵌套 frame 中植入 `image_prompt`、游标、路径、gateway job、raw response 和私有上下文，所有公开投影递归扫描均为零。
- 连续失败两次后数据库仍有两条失败记录，history 返回两个安全失败摘要；第三次仍可预约且不删除前两条。
- `Hello {{name}}` 注入值 `$unknown ${task_type} {{user_input}}\n中文` 后逐字保留；恶意长文本也只被当成数据。
- JPEG/PNG/WebP 的参考 data URL、下载 artifact、文件后缀和持久化 MIME 一致；冲突组合失败。
- 轮播为“是”但数量为空/1/6 时抛出 `carousel_count_required` 或 `carousel_count_invalid`，fake model 调用为 0；none 为 1 帧，AI 模式每套仍可独立 2 至 5。
- 新进程只执行 `import creative_studio.app` 时，不创建/open 默认数据库、executor 或 AI/image client。
- 生产 composition root 使用临时 SQLite + fake model/image queue + fixed clock 完成一次生成。

## 旧路径删除条件

- `public_visual_creative_item()`、`public_display_history()` 中的删除式过滤：所有生产 caller 和测试切到 `PublicResultMapper` 后禁止新调用；Phase 1/5 在 `rg` 无 caller 后删除。
- `LegacyCreativeGenerationAdapter`：本阶段保留，标记 `deprecated_since=phase-0`；三个新业务 Module 完成并证明生产调用数为零后删除。
- `ai_visual_first_frame_prompt_v1.txt` 与 `ai_visual_follow_up_prompt_v1.txt`：保持 retired，禁止新增 caller；只有独立 ADR 批准 v2 policy 后才能以新版本重新注册。
- 旧 raw `items_json`/`snapshot_json`：只允许内部诊断和一次性 importer 读取，任何公开 caller 为零后，Phase 5 决定保留期限或删除策略。

## 实施顺序

1. 先为 prompt compiler、公开投影/scrub、MIME、失败保留/错误详情、轮播前置校验、composition root 和 v2 路径分别写能变红的测试并运行确认。
2. 分责任域写最小实现，每一组转绿后再进入下一组；不以 mock 自身调用作为唯一断言。
3. 在临时数据库运行 projection scrub dry-run、apply、统计、重读验证和 backup 回滚。
4. 运行定向测试，再运行全量确定性测试、JavaScript 语法、Python compileall、`git diff --check` 和最终状态检查。
5. 更新 `progress.md`，记录通过项、环境失败和真实 AI/图片/浏览器未验证项；Phase 0 任一门禁未满足时保持状态为未完成。

## 完成证据

- 全量确定性测试：`PYTHONPATH=src python -m unittest discover -s tests -v`，175 项通过；新增新旧调用路径的 JSON 根路径、transport `choices` 路径、叙事各层精确路径、视觉 wrapper、供应商游标、失败路径持久化和公开文本列表严格类型回归。
- 静态门禁：`node --check static\app.js`、`python -m compileall -q src chat2api` 和 `git diff --check` 均通过。
- 真实默认数据库仅通过 SQLite `mode=ro` dry-run 扫描：`scanned_rows=8`、`changed_rows=6`、`private_field_occurrences=25`、`invalid_json_rows=0`、`unknown_kind_rows=0`、`applied=false`、`backup_path=""`；执行前后数据库 SHA-256 均为 `F7DA1AA20D5FBAC7A3785C0D81096B1096749DE40025874644F37E1AD461DFA8`。
- `--apply`、写后重读验证和 backup 恢复只在临时 SQLite 副本执行；没有对 `data/creative_studio.db` 执行 apply。
- 未调用真实 AI、图片网关或浏览器；未修改真实图片、上传文件或 `chat2api/.env`。
- 仓库没有 export 路由或导出函数，export mapper 在 Phase 0 不适用；未来新增 export 必须复用 `PublicResultMapper` 并加入递归私有字段扫描。
- 最终双轴规格/规范复核为 PASS，无 Critical 或 Important；`HttpModelClient.response.json()` 自身抛错的 `$` 分支缺少直接单元测试，但行为已实现，且不阻塞本阶段门禁。
