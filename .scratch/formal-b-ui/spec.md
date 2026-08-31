# 正式 B UI 迁移变更卡

Status: implemented

## 目标

- 将已确认的旧版 B 三步设计替换正式页面，并继续使用现有 Python API、SQLite、标签配置、图片任务、历史与采用关系。
- 正式流程为：任务说明、创意定位、生成与采用。

## 非目标

- 不修改数据库结构、提示词、模型、AI 网关、登录权限、部署和运行数据。
- 不把 `static/ui-prototype.*` 的假项目或假方案写入正式页面。

## 验收

- 打开正式入口 `/` 时自动载入最近项目；顶部项目入口可打开覆盖式项目栏。
- 前两步显示实时简报，第 3 步显示真实历史与生成操作。
- 展示/叙事分支、标签依赖、两批上限、图片重试和采用替换沿用现有 API 行为。
- 桌面与 390px 移动端无横向溢出，浏览器无 error/warn。

## 回滚

- 代码回滚到本变更前的 Git 提交；`data/` 与 `chat2api/.env` 不参与回滚。
- 若页面接线异常，停止服务后回滚 `static/index.html`、`static/app.js`、`static/styles.css`，再执行最小检查和本地冒烟。

## 验证结果

- `python -m unittest discover -s tests -v`：5 passed。
- `node --check static/app.js`、`python -m compileall -q src chat2api launcher.py`、`git diff --check`：通过。
- 正式服务在独立本地端口加载真实 SQLite 叙事历史成功。
- 390px 视口 `scrollWidth == clientWidth`，正式页面从视口顶部开始，控制台无 error/warn。
- 未执行真实 AI 文字或图片生成请求。
