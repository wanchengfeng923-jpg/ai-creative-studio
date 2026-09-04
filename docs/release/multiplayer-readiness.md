# 多人内网准备边界

当前代码已有账号、角色、会话、CSRF 和项目 `owner_user_id` 隔离；SQLite 写入使用事务和 busy timeout，图片 operation 使用 lease/attempt 防止旧 worker 覆盖新状态。它仍是单机工作台，不等同于多人生产就绪。

正式内网变更前必须另建变更卡，至少完成：

- 反向代理/HTTPS、可信代理头和登录 cookie 安全属性；
- 账号初始化、管理员审计、密码重置和登录限流的带认证浏览器验收；
- 并发生成、项目权限、SQLite 锁竞争和 worker 重启压力测试；
- 数据库、图片和上传目录定时备份、失败告警、跨目录恢复演练；
- 端口、防火墙、服务安装和凭据存储的审批与回滚。

本路线只提供 `backup`、`restore`、`release_gate` 和可注入 port，未修改监听地址、防火墙、HTTPS、Windows 服务或 `chat2api/.env`。`launcher.py` 的现有监听地址修改属于用户工作树，发布前应由负责人单独确认。

