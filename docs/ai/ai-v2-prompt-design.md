# AI v2 Prompt 专项设计与评测协议

- 日期：2026-09-04
- 状态：候选设计，等待用户审批后才能创建 production caller
- 依据：`docs/superpowers/specs/2026-09-04-ai-v2-text-first-preview-design.md`、`config/ai_v2/schemas/`
- 评测资产：`config/evals/ai_v2/prompt-cases.jsonl`、`config/evals/ai_v2/expected-hard-constraints.json`

## 1. 范围与不变量

本设计只规定 v2 Prompt 的任务边界、数据区序列化、输出硬约束和评测方法，不复用旧 Prompt 正文，也不授予真实模型调用或正式入口切换权限。候选 Prompt 在用户批准前只能被离线结构检查和 deterministic fake 使用。

v2 输入永远只有 `task_description`、`aspect_ratio`、`creative_tags` 三个字段。用例由已授权项目状态与 v2 路由决定，不序列化为第四个模型输入字段。产品证据、补充资料和参考文件不进入 v2。

## 2. 三个唯一任务

### 叙事文字

一次调用返回 5 套彼此可区分的一句话故事；每套恰好 2 个钩子，每个钩子恰好 3 个画面描述。输出只能包含 `schema_version` 和 `items`，不生成图片执行信息。

### 静态展示文字

一次调用返回 3 套静态创意。每套只公开标题、核心创意、广告文案和画面描述，并在内部 `execution.image_prompt` 提供唯一一条图片执行指令。图片指令只能把同一画面事实翻译为构图、镜头、光照、材质和负面限制，不增加人物、产品事实或剧情。

### 轮播展示文字

一次调用返回 3 套完整路线。每套帧数必须为 2 至 5，`frames[].index` 连续从 1 开始；内部 `execution.image_prompts` 与公开帧数量和索引完全一致，并包含连续性规则。后续图片点击只读取已规划的当前帧，不再次调用文字模型或重新规划。

## 3. 数据区序列化

Prompt 模板只声明三个占位符：`{{task_description}}`、`{{aspect_ratio}}`、`{{creative_tags}}`。编译器执行一次字面替换；注入值中的 `$`、`${...}`、`{{...}}`、换行和 Unicode 都是数据，不会再次解析。

数据区固定按下列顺序出现：

```text
TASK_DESCRIPTION:
<裁剪后的任务说明，允许为空>

ASPECT_RATIO:
<16:9 或 9:16>

CREATIVE_TAGS_JSON:
<按用户选择顺序保留、无选择为 {} 的 JSON 对象>
```

标签组名称开放；空组、空字符串和重复值在输入边界清理。Prompt 不得把 AI 自由补充的方向写成用户已选择标签。

## 4. 输出与执行一致性

- 输出必须匹配对应 `*-text-v1` schema，未知字段拒绝，不做隐藏格式修复调用。
- 公开字段是创意事实；静态/轮播内部图片 Prompt 只能实现相应事实，不能建立第二套剧情。
- `execution` 及其后代永远只在服务端 typed 对象中存在，不能进入公开 DTO、日志、评测导出或浏览器。
- 文字结构错误使本批直接失败；用户主动重试才创建新的文字会话。同一批只调用一次文字模型。
- 一批最多两批定位；第二批使用新文字会话，不注入第一批摘要，也不通过会话 ID推断差异。

## 5. 评测方法

`prompt-cases.jsonl` 固定 30 个脱敏 case，每个用例 10 个，涵盖空标签、画幅、轮播 2/3/4/5 帧、额外字段、私有字段泄露、重复方案、空描述和供应商失败响应。每个 case 的 `expected` 只描述可机器检查的硬约束；人工质量评分不在本文件伪造。

离线顺序固定为：输入契约 -> schema lint -> 私有字段扫描 -> 事实/执行一致性 -> 机制重复信号 -> 调用次数/延迟/预算记录。报告必须区分 `baseline`、`candidate`、`repair_failure`，真实模型质量在未授权前为 `not_run`。

## 6. 审批与回滚

用户确认本设计和评测资产后，才可在 Task 5 创建 v2 Prompt registry；确认前不得把候选 Prompt 接入 production caller。回滚只删除本候选设计和评测目录，不触碰旧 Prompt、旧 registry、数据库、图片、上传文件或凭据。

