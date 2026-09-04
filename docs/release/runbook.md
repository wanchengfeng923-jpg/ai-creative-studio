# 发布 Runbook

## 发布前

1. 阅读 `AGENTS.md`、`progress.md`、代码地图、`docs/operations.md` 和总纲；确认当前工作树中的用户修改。
2. 停止网页/网关后，在临时目录完成数据库、图片、上传文件备份和 restore smoke。
3. 运行 `python -m creative_studio.release_gate`，保存输出和 commit hash。
4. 检查 registry active caller、评测报告 schema/lint、迁移版本和备份 manifest；恢复 smoke 必须返回 `verified=true` 与 `references_verified=true`，并记录只读 retention plan。

## 发布中

1. 只执行 additive migration；先在恢复副本执行，再切换代码。
2. 启动单实例观察一个完整生成周期，确认 run、图片 operation、错误分类和公开投影正常。
3. 保留旧历史读取器和备份，不删除用户数据；观察期内禁止修改监听、防火墙、HTTPS 或凭据。

## 发布后

- 记录测试、健康检查、备份时间、registry 版本、未验证项和负责人。
- 任何真实 AI/图片供应商评测必须使用脱敏输入、独立输出目录和预算；默认不执行。
- 多人内网、服务安装、公网开放需另建高风险变更卡。
