# Phase 5+ 全量实施卡

## 目标

在不覆盖用户数据、不改变网络边界、不调用真实供应商的前提下，完成 AI 生成链路的 canonical run/reference seam，清理无 caller 的旧路径，建立评测、可观测性、备份恢复和发布门禁；把需要人工授权的生产动作整理成可执行 runbook。

## 非目标

- 不执行真实数据库 scrub `--apply`。
- 不恢复或覆盖 `data/`、图片目录、上传目录。
- 不修改 `launcher.py` 的监听地址、防火墙、HTTPS、服务安装或 `chat2api/.env`。
- 不发起真实 AI/图片供应商请求，不把 fake 评测写成真实质量结论。

## 验收例子

1. 三个 active registry 项各只有明确 caller，旧 adapter/schema/loader 无生产调用。
2. 参考资料 metadata 可 round-trip；digest/MIME/大小/提取状态进入运行上下文；路径穿越和私有正文不会进入公开响应。
3. `GenerationRun` 可保存、读取、失败、过期和幂等；轮播旧 `complete_visual_generation()` 不再承担新写入。
4. 评测 harness 能验证固定 10-case 报告结构、硬约束和失败分类。
5. backup/restore 在临时副本通过 manifest/hash/SQLite/image/upload smoke，并能复现 scrub fixed point。
6. 发布 gate 能一次执行 unittest、Node、compileall、registry、eval schema、backup smoke 和 diff check。

## 工作顺序

P5 canonical seam -> P6 reference assets -> P7 evaluation/observability -> P8 backup/restore -> P9 release/docs。每个工作包先补失败测试，再写最小实现，定向验证后才进入下一个。

## 回滚

按工作包提交；失败时回退代码提交或关闭 registry 版本开关。数据库只做 additive migration；任何真实数据写入另建变更卡。

