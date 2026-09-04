# ADR-0005：AI v2 边界与会话/重试策略

- 状态：Accepted for implementation; production Prompt/cutover approval remains separate
- 日期：2026-09-04
- 决策范围：AI v2 输入、文字会话、按需图片会话、重试对账和旧 AI 隔离
- Supersedes：AI v2 预览设计稿中与本 ADR 冲突的会话/重试表述；不改变 ADR-0001/0003 对旧链路的既有事实

## 背景

AI v2 采用文字优先和按需生图。必须先锁定会话数量、幂等键和非终态错误语义，避免网页超时或供应商状态未知时盲目重发，或把每张图片拆成独立会话。v2 还必须与旧 AI 完全隔离，不能借兼容层复用旧业务契约。

## 决定

1. v2 HTTP body 只接受 `task_description`、`aspect_ratio`、`creative_tags`；用例类型由已授权项目状态与 v2 路由决定。产品证据、补充资料和参考文件暂不进入 v2。
2. 每批文字请求创建一个新的 `TextSession`，不复用其他批次或旧 AI 会话；一批只做一次模型调用，结构错误直接失败，用户主动重试才创建新文字会话。
3. 每个展示方案第一次点击时最多创建一个 `ImageSessionCursor`。静态方案所有图片工作限一张；轮播方案全部帧共享同一图片会话，后续帧复用已提交 cursor 和上一张成功 artifact。
4. 图片逻辑帧使用稳定的方案版本/帧索引 `request_key`；attempt 序号只区分明确失败后的重试，不参与会话键。重复点击返回已有 attempt，成功状态锁定。
5. 图片重试顺序固定为：读取本地 attempt 与 image session，使用原 `image_session_key`/`request_key` 和供应商游标对账。供应商已成功则原子完成原 attempt；仍在工作则重新挂接；只有明确终态失败才在原图片会话内创建同一帧的新 attempt；未知、不可用、超时或连接断开不创建新 attempt，也不创建第二个会话。
6. 本地 attempt 缺失而方案图片会话存在时视为孤儿任务，先按稳定键对账并恢复本地 attempt；不得新建会话。浏览器永远只收到公开状态和安全错误摘要。
7. v2 只允许依赖中立传输基础设施和自有 v2 模块；不得导入旧 AI builder、validator、mapper、结果字典、轮播编排、旧表或旧生产入口。v2 失败不 fallback，且不与旧链路双写/双读。

## 状态与错误

图片状态只有 `pending`、`generating`、`success`、`failed`。网络超时、断开和 5xx 代表本地结果未知，不能直接映射为供应商终态失败。公开错误只包含稳定 `error_code`、阶段、可重试性、trace id 和安全摘要，不包含 Prompt、cursor、job id、路径、完整响应或堆栈。

## 替代方案

- 每张图片一个会话：拒绝，会放大会话数量并破坏轮播连续性。
- 网页失败即新建 attempt/会话：拒绝，无法区分供应商仍在工作与真正失败，会产生重复图片。
- 复用旧 AI 兼容层：拒绝，会违反 v2 零引用、零回退和零双写/双读不变量。
- 隐藏格式修复调用：拒绝，增加不可见模型调用；结构错误留在本批失败，用户重试才新开文字会话。

## 迁移与验证

先建立 v2 boundary、输入和 schema 测试，再实现 typed session/store、公开投影、用例和图片 worker。全部 deterministic fake 只使用临时 SQLite/目录，不读取真实凭据。Prompt 正文在用户评审前保持候选，不创建 production caller；未获批准不执行入口切换。

## 回滚

代码/配置按任务提交边界回滚；v2 additive 表和图片目录保留但可由禁用入口停止读取。不得覆盖旧表、真实运行数据、图片、上传文件或 `chat2api/.env`。发现旧引用、双写/双读或私有字段泄露时立即停止后续任务并回到 Task 1 边界守卫。

