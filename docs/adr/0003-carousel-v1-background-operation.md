# ADR-0003：轮播 v1 采用共享规划与后台 Operation

- 状态：Accepted
- 日期：2026-09-04
- 决策范围：展示类轮播首帧、后续画面、图片任务和继续生成接口
- Supersedes：`docs/superpowers/specs/2026-09-02-display-frame-flow-design.md` 中关于独立首帧文字会话的流程描述

## 背景

旧设计描述每套方案重新建立文字会话生成首帧，生产代码实际却使用一次共享规划响应中的首帧草稿。继续生成还由同步 HTTP 请求串行执行，长任务会占用连接并让前端无法观察逐帧进度。操作锁过期后，崩溃 worker 可能把当前帧遗留为 `generating`，替代 worker 无法重新领取。

## 决定

轮播 v1 固定为“一次共享 planner 输出三套完整路线和每套私有首帧图片指令；图片 adapter 直接执行首帧；后续帧按锁定路线编排图片指令并携带上一张实际图片”。首帧不再触发独立文字会话。若未来评测证明独立会话有价值，只能注册为有界的 v2 `GenerationPolicy` 阶段。

继续生成创建持久化 `carousel_operations` 后立即返回 `202 Accepted` 和公开 operation 摘要。后台 coordinator 以 lease token 独占 operation，逐帧领取、heartbeat、等待图片终态，并在图片成功时原子提交 artifact、frame 状态、方案会话游标和 operation revision。lease 过期恢复只处理明确失活的 operation，并将其当前遗留 `generating` 帧重置为 `pending`；已成功帧不可重复生成。

公开响应只包含 operation id、状态、进度、错误代码和时间字段，不包含 request key、lease token、供应商游标、网关 job id、本地路径或图片指令。前端轮询 operation 和逐帧公开状态，终态后停止计时器；静态展示和叙事路径不受此流程影响。

## 替代方案

- 保留同步 continue 请求：拒绝。连接时长与图片网关延迟不可控，用户无法可靠观察中间状态。
- 每帧独立文字会话：拒绝作为 v1。当前没有质量评测证明其收益，且与共享规划生产事实冲突。
- 只在内存中维护锁：拒绝。进程重启后无法恢复，也不能阻止旧 worker 覆盖新 attempt。

## 影响

- API 调用者必须处理 `202`、operation 查询和 `blocked` 可重试终态。
- `carousel_operations` 是加法迁移；旧 `continuation_token` 仍作为兼容字段保留，但新 coordinator 的 lease 事实以 operation 表为准。
- 失败的逐帧记录和 operation 错误保留，人工重试通过再次创建 operation 完成，不删除诊断证据。
- 真实 AI、图片网关、带认证浏览器和多进程竞态仍需单独验证，deterministic fake 只证明状态边界。

## 迁移与回滚

迁移顺序为：先注册 `CarouselResult.v1` contract 和共享 planner prompt，再启用 operation coordinator、原子 frame completion、状态 API 和前端轮询。旧同步编排器仅保留兼容方法，默认 composition root 不再调用。若发现私有字段泄露、旧 attempt 覆盖新 attempt 或恢复重复生成，回滚到本 ADR 对应提交；不删除数据库、图片、上传文件或失败记录。
