# AI 重构 Phase 4 交接文档：轮播 v1

- 日期：2026-09-03
- 状态：Phase 3 静态展示迁移已完成，Phase 4 尚未开始
- 项目：`D:\\code\\ai_creative_studio`
- 当前分支：`codex/tag-accordion-prototype`
- Phase 3 实现提交：`c0d86a0`、`42ebc83`、`08492ca`
- Phase 3 收尾提交：`7e74b70`
- 本文件由后续 docs-only 提交保存；该提交的真实哈希同步记录在 `progress.md` 和分支日志。

本文是给 Phase 4 实施会话使用的事实交接，不是“真实 AI 或图片网关已通过”的声明。当前静态生产链路已经切换，下一阶段只允许处理轮播 v1；不得因为静态首图已能排队而顺手重写轮播状态机。

## 1. 当前静态 production 事实

### Registry

当前唯一静态 production PromptSpec 是：

| 字段 | 当前值 |
|---|---|
| registry key | `creative.visual.static.generate@static-v1` |
| prompt | `config/ai_visual_static_creative_prompt_v1.txt` |
| input schema | `StaticVisualPromptInput.v1` |
| output schema | `StaticVisualResult.v1` |
| validator | `StaticVisualResultValidator.v1` |
| public DTO | `StaticVisualPublicDTO.v1` |
| caller | `static` |
| provider/model | `chatgpt-web` / `gpt-5-6-mini` |
| policy | 最多 2 次文字模型调用，`max_output_tokens=5000`，超时 300 秒 |
| evaluation set | `config/evals/static.v1.json`，10 个脱敏 case |

`creative.visual.static.generate@visual-v2.3` 已标为 `retired`，`new_callers_forbidden=true`，replacement 为 `static-v1`，`deprecated_since=phase-3`。它只作为历史 inventory 和旧数据审计依据，不会再执行旧 prompt。删除条件是 Phase 5：静态 legacy caller 为零、历史保留期完成且回归评估通过。

### 真实代码路径

默认 composition root 在 `src/creative_studio/app.py:create_application()`：

```text
POST /api/projects/{id}/generate
  -> StudioApplication.generate
  -> CreativeGenerationService.generate
  -> _generate_with_model_client
  -> _generate_static_with_model_client
  -> StaticVisualGeneration.generate
  -> ModelClient/HttpModelClient
  -> chat2api /v1/chat/completions
  -> StudioRepository.complete_static_generation
  -> _enqueue_static_image_jobs
  -> ImageJobRunner.enqueue_static
```

对应模块和边界：

- `src/creative_studio/static_visual.py`：输入 `StaticVisualPromptInput`、`StaticVisualResult.v1` validator、一次字段路径 repair、私有 `image_generation_instruction` 分离和 `StaticVisualImageRequest`。
- `src/creative_studio/contracts.py`：显式绑定 `StaticVisualPromptInput.v1`、`StaticVisualResult.v1`、`StaticVisualResultValidator.v1`、`StaticVisualPublicDTO.v1` 和 `static` caller。
- `src/creative_studio/repository.py:complete_static_generation()`：事务内把 canonical 正文写入 `generations.items_json` 和 `visual_items.content_json`，把私有图片指令写入 `visual_items.image_prompt`；静态结果不创建 `display_frames`。
- `src/creative_studio/public_projection.py:PublicResultMapper.static_visual_item()`：按白名单生成公开静态 DTO。`history`、`status`、`adopt` 使用该映射，不由 HTTP handler 做字段过滤。
- `src/creative_studio/generation_service.py:_enqueue_static_image_jobs()`：从服务端行构造三个 `StaticVisualImageRequest`，每案一个稳定的 `creative-studio-{item_id}-attempt-1` request id。
- `src/creative_studio/image_jobs.py:ImageJobRunner.enqueue_static()`：接收 typed request 并复用现有 SQLite worker；本阶段没有改变 worker 调度、下载校验或轮播逐帧逻辑。

## 2. 静态 contract 和公开边界

每批静态结果严格为 A/B/C 三案。每案必须有唯一 `concept_id`、`title`、`creative_summary`、`audience_tension`、`product_value`、`visual_mechanism`、创意来源、证据台账、一个 `static_frame`、素材计划、制作风险、review 和私有图片指令。validator 拒绝额外字段、URL、Markdown、换行、超长文本、非法素材状态、重复视觉机制和轮播字段。

公开 DTO 包含 canonical 创意字段、`id/item_index/scheme_id/generation_id`、`aspect_ratio`、图片状态、应用内图片 URL 和安全图片错误摘要。公开 DTO 不包含：

- `image_generation_instruction`、`image_prompt`；
- `conversation_id`、`parent_message_id`、`assistant_message_id`；
- gateway job id、本地图片路径、上传存储名；
- raw model response、完整错误详情、堆栈和私有 context。

静态图片任务使用 `visual_items.image_prompt` 作为服务端事实，成功 artifact 写入 `data/images/{generation_id}/{item_id}/attempt-{n}.<ext>`。浏览器只通过 `/api/visual-items/{id}/image` 获取图片；文件下载仍执行同源、MIME 和 magic-byte 校验。

## 3. 旧 alias 和 legacy caller 保留条件

当前旧字段并没有被当作 static-v1 canonical 字段继续写入，但以下真实兼容路径必须保留：

1. `CreativeGenerationService` 在显式 `model_client=None` 时使用 `LegacyCreativeGenerationAdapter`，调用 `ai_creative.generate_visual_creative_recommendations()` 和 `complete_visual_generation()`。该路径是历史/测试兼容 seam，不是默认 composition root 的 production caller；`7e74b70` 增加回归测试，防止旧结果误走静态 canonical 持久化。
2. 轮播 production 仍由 `CreativeGenerationService._generate_with_model_client()` 调用旧视觉 validator，并通过 `complete_visual_generation()` 保存轮播方案。`subtitle`、`creative_description`、`core_subject`、`layout`、`visual_style` 等字段在这条轮播/历史路径中暂时仍有意义，不能在 Phase 4 开始时直接删除。
3. `PublicResultMapper.visual_item()` 继续读取旧视觉/轮播历史字段；`static_visual_item()` 是独立 canonical 分支。历史读取兼容不能反向写入新 `content_json`。
4. `src/creative_studio/schemas.py:VisualRecommendationSchema`、`ai_creative.py:validate_visual_creative_recommendations()` 和旧 prompt loader 仍作为轮播或历史审计对象保留。三个新业务 Module 全部切换、旧 production caller 为零、历史保留期和回归评估完成后，才进入 Phase 5 清理。

不得通过新增 alias、永久双写或环境变量切换把 `visual-v2.3` 重新变成 production。

## 4. 图片状态、部分失败、重试和恢复

静态文字和图片是两条独立状态线：

```text
文字：pending -> success
              -> failed

首图：queued -> generating -> success
                         -> failed
```

- 文字 contract 校验失败最多执行一次 repair。第二次失败保留 `model_output_invalid`、阶段、精确字段路径、attempt 和 trace id；不会持久化半个静态批次。
- 文字成功后先事务提交三套 canonical 方案，再分别创建三个首图任务。某一项图片失败不改变另外两项的状态，历史可显示 `success/failed/queued` 的混合结果。
- 图片 worker 为第一次失败自动重新排队一次；第二次失败保持 `failed`。`POST /api/visual-items/{id}/retry` 只允许失败项递增 attempt，成功项不会重复提交。
- request id 按方案和 attempt 稳定生成；同一 attempt 的重复提交复用成功 gateway job，旧 attempt 的完成回调不能覆盖新 attempt。
- 进程初始化复用现有 `recover_visual_items()`，将失活的 `generating` 项重新排队。该恢复逻辑属于共享 visual worker；Phase 3 没有改变轮播 lease、会话游标或继续生成顺序。
- `text success + image queued/generating` 是合法中间状态，不能被公开层误报为全部完成。

## 5. Phase 3 验证证据

在 `7e74b70` 收尾前，以下命令均通过：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
python -m unittest discover -s tests -v
node --check static\\app.js
python -m compileall -q src chat2api
git diff --check
```

完整 unittest 共 `202` 项通过。静态定向覆盖包括 canonical validator、一次 repair、临时 SQLite canonical persistence、history/status/adopt 隐私投影、composition root fake model/image runner、registry 生命周期、10-case fixture、前端 canonical-first renderer，以及 legacy adapter fallback。测试使用临时数据库、隔离图片目录、deterministic fake 和固定输入，没有写入真实 `data/`。

当前工作树中 `launcher.py` 仍保留用户已有的 `WEB_BIND_HOST = "0.0.0.0"` 修改，未被 `7e74b70` 暂存；默认文档和代码约定仍是回环监听，不能把这项用户修改误记为 Phase 3 的部署决策。

## 6. Phase 4 唯一允许范围

Phase 4 只处理轮播 v1：

- 轮播 ADR、`supersedes` 关系和当前共享 planner 的事实收口；
- 后续画面 prompt 与编排 policy；
- 后台 Operation、lease、heartbeat、超时和恢复；
- 逐帧状态查询、图片 artifact 状态和轮播前端轮询。

Phase 4 不得修改：

- `StaticVisualResult.v1`、static-v1 registry、静态 DTO 或静态 canonical persistence；
- 叙事 v6、NarrativeGeneration、叙事 UI 语义；
- `launcher.py`、监听地址、登录权限、真实数据库、图片目录或 `chat2api/.env`；
- 静态图片质量或真实参考文件传递策略。

任何需要改变共享图片 worker 的修改，都必须先证明不会改变静态 attempt、幂等、恢复和隐私边界，并另写轮播变更卡。

## 7. 未验证项和回滚

以下事项仍明确为“未验证”，不能用 fake 测试替代：

- static-v1 在真实 AI 上的事实准确性、文案质量和三案机制差异；
- 真实图片网关的成功率、文字可读性、目标画幅和视觉质量；
- 带认证浏览器的 history/status/adopt/retry 人工流程；
- 真实 `data/creative_studio.db` 的新静态行写入、历史升级和 scrub；
- Chat2API 对 `response_format`、`max_tokens`、图片指令和会话字段的真实执行语义；
- 真实参考文件内容是否应该进入文字模型或图片模型；
- 多进程 worker、长任务和重启竞态的生产行为。

回滚以代码提交为边界：优先回滚 `7e74b70` 中的 static-v1 registry/前端/测试接线，再按需要回滚 `08492ca`、`42ebc83`、`c0d86a0`。回滚不删除数据库、图片、上传文件或失败证据；新 canonical 行继续由读取映射处理。若发现公开 DTO 泄露私有指令、旧 attempt 覆盖新 attempt、测试触碰真实运行数据或轮播行为受到静态改动影响，应停止 Phase 4 并保留诊断证据。
