# Phase 4：轮播 v1 后台操作与逐帧状态

## 目标

把展示类轮播继续生成收敛为可恢复的后台 Operation：一次请求立即返回 operation id，worker 按锁定路线逐帧执行，lease 通过 heartbeat 保持，重启只恢复明确失活的操作；前端通过公开 operation/逐帧状态轮询观察进度。

## 非目标

- 不修改 `StaticVisualResult.v1`、静态 registry、静态 DTO 或静态 canonical persistence。
- 不修改叙事 v6、登录权限、监听地址、`chat2api/.env`、真实运行库和运行图片。
- 不恢复独立首帧文字会话，不把旧 `ai_visual_first_frame_prompt_v1.txt` 或 `ai_visual_follow_up_prompt_v1.txt` 重新接入生产。
- 不改变共享图片 worker 的静态首图 attempt、幂等和 MIME 行为。
- 不允许用户编辑已锁定的 frame plan，也不增加并行后续帧。

## 当前事实与决策

1. 轮播首帧来自共享 planner 的 `first_frame.image_generation_instruction`，后续图片指令由编排器生成；该 v1 方向固定为“一次共享规划 + 图片直出”。
2. `display_frames` 继续保存逐帧私有执行事实；新增 `carousel_operations` 保存一次 continue 操作的权威状态和 lease，不创建第二套 frame 事实。
3. operation 状态为 `queued -> running -> completed|failed|blocked`，超时 worker 只能在 lease 失活后被恢复；旧 token/operation revision 的写入必须条件失败。
4. frame 状态保持 `pending -> generating -> success|failed`，失败帧由同一 operation 最多自动重试一次，人工重新 continue 从第一个未成功帧开始。
5. 图片成功、frame 状态、方案 cursor 和 operation revision 在同一 SQLite 事务中提交；若供应商返回图片成功但缺少 cursor，不更新成功状态并记录 `provider_protocol_invalid`。
6. 旧 `/api/visual-items/{id}/continue` URL 保留兼容，但响应改为 `202` 风格 success envelope，包含 `operation` 和公开 `scheme`；重复请求返回现有 operation，不启动第二个 worker。

## 数据流

```text
POST /api/visual-items/{id}/continue
  -> 认证/归属检查
  -> repository.get_or_create_carousel_operation (事务 lease)
  -> 立即返回 operation_id + public operation + public scheme
  -> CarouselOperationWorker
       -> heartbeat lease
       -> claim next frame (条件 attempt)
       -> enqueue image task / wait
       -> atomic complete frame + cursor + operation revision
       -> next frame
GET /api/visual-items/{id}/operation/{operation_id}
GET /api/visual-items/{id}/frames/status
  -> PublicResultMapper
  -> 前端 2 秒轮询，直到 operation terminal
```

## 公开边界

operation 只公开 `operation_id`、`scheme_id`、`status`、`current_frame_index`、`completed_frame_count`、`total_frame_count`、`retryable`、`error_code`、`error`、`created_at`、`updated_at`、`lease_expires_at`。禁止公开 token、revision、图片指令、会话游标、gateway job id、本地路径和 worker 异常详情。

## 回滚

回滚以本阶段代码提交为边界；新增表和列是加法迁移，旧代码可忽略。不得删除 `carousel_operations`、`display_frames` 或图片文件。若发现静态 attempt/幂等、私有字段投影、旧 worker 覆盖新 attempt 或叙事路径变化，停止迁移并回滚代码提交，保留诊断数据。

## 验收例子

- 2、3、4、5 帧均能创建一个 operation，重复 continue 只返回同一个 operation。
- 首帧失败时 operation 不提交后续帧；首帧重试成功后才能继续。
- 第 2 帧成功提交后才允许第 3 帧 claim；第 2 帧失败最多自动重试一次，人工 continue 可恢复。
- lease 过期且无 heartbeat 的 running operation 重启后回到 queued；有新 heartbeat 的 operation 不被回收。
- 旧 worker 使用过期 token 完成时返回 stale，不覆盖新 attempt、cursor 或 operation。
- operation/status/history/continue 的公开 JSON 递归扫描均不存在私有字段。
- 前端桌面和移动端都能看到“排队/生成/完成/失败/可继续”，无同步长请求依赖和横向溢出。
