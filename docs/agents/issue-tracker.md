# Issue tracker: Local Markdown（本地 Markdown）

本仓库的 issue 和 spec 以 Markdown 文件形式存放在 `.scratch/` 中。

## 约定

- 每个功能一个目录：`.scratch/<feature-slug>/`
- Spec 位于 `.scratch/<feature-slug>/spec.md`
- 实现 ticket 位于 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 开始编号
- 分类状态在每个 ticket 文件顶部附近通过 `Status:` 行记录，角色字符串参见 `triage-labels.md`
- 评论和对话历史追加到文件末尾，位于 `## Comments` 标题下

## 当技能要求“发布到 issue tracker”

在 `.scratch/<feature-slug>/` 下创建新文件，按需创建目录。

## 当技能要求“获取相关 ticket”

读取引用路径下的文件。用户通常会直接提供路径或 issue 编号。

## Wayfinding 操作

由 `/wayfinder` 使用。地图是一个文件，每个 ticket 对应一个子文件。

- 地图：`.scratch/<effort>/map.md`，保存 Notes、Decisions-so-far 和 Fog
- 子 ticket：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 开始编号
- `Type:` 记录 ticket 类型：`research`、`prototype`、`grilling` 或 `task`
- `Status:` 记录 `claimed` 或 `resolved`
- 阻塞关系通过靠近文件顶部的 `Blocked by: NN, NN` 记录
- 当前沿 ticket 的所有阻塞项均为 `resolved` 时，该 ticket 解除阻塞
- 扫描 `.scratch/<effort>/issues/`，按编号选择第一个打开、未阻塞且未认领的 ticket
- 开始工作前将其设置为 `Status: claimed`
- 完成后在 `## Answer` 下追加答案，将状态设置为 `resolved`，并在 `map.md` 的 Decisions-so-far 后追加摘要和链接
