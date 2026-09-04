# AI v2 Release Handoff

## 总体状态

代码、契约测试和本地浏览器登录/项目流程验收已完成。真实模型质量和真实图片供应商冒烟保持未运行；当前浏览器驱动不支持强制 viewport，因此 390x844 仅由响应式 CSS 与静态检查覆盖。

## 当前入口

- 根页面 `/`：认证、项目列表/创建/重命名/删除、三字段 v2 生成、历史、按需图片、轮播逐帧和 v2 采用。
- 诊断页面 `/ai-v2/`：独立 v2 输入与结果页面。
- 旧生成和视觉路由：返回 404；不再构造旧模型客户端、旧图片 runner 或旧生成服务。

## 数据与回滚

v2 只写 `ai_v2_*` 表和 v2 artifact；不会写旧 `generations`、`visual_items`、`adoptions`。回滚代码使用 `git revert` 对应 v2 提交即可，运行数据库和图片目录不删除。

## 未验证与门禁

发布门禁证据为 deterministic fake / contract only，真实模型质量为 `not-run`。任何正式 Prompt 正文接入或供应商冒烟都应另开审批变更，不在本次收尾中自动执行。

## 收尾并发与隔离修复

- `creative_studio` 包初始化已移除旧 AI eager import；v2 子包导入不会加载旧 builder、model client 或 registry。
- v2 批次保留、图片会话首建、图片 attempt claim、过期 attempt 和游标更新均有 SQLite 原子边界；并发回归覆盖重复批次、重复供应商会话、重复 worker 提交和旧响应覆盖。
- 首次图片供应商状态未知时只保留稳定 request key，不落本地 session/attempt；后续点击仍需先做供应商对账。
- 叙事历史和轮播逐帧状态公开投影已修正；重复生成自动进入第二批。

## 既有高风险配置

`launcher.py` 当前提交中的 `WEB_BIND_HOST="0.0.0.0"` 会让网页监听所有接口。项目安全文档要求默认回环且网络绑定需单独审批；本次没有擅自回退或改写该既有配置，验收前需负责人明确批准或另开回滚变更。
