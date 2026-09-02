# AI创意工作台

从 Web ERP 中独立提取的本地创意应用。它使用自己的页面、SQLite 数据库、参考文件目录、AI 图片目录和 Git 历史，不读取或写入 ERP 数据库。

## 使用

双击 `启动AI创意工作台.bat`。首次启动会创建本项目的 `.venv` 并安装依赖，随后打开启动控制台。首次使用时在窗口中填写 Access Token 或 Session Cookie，点击“保存配置”后再点击“启动”，网页会自动打开：

`http://127.0.0.1:8775/`

当前版本只监听 `127.0.0.1`，网页使用 `8775`，本项目自己的 AI 网关使用 `8780`。它不占用原 ERP 的 `8700` 网关。没有登录页，适合单机使用；不要把端口映射到局域网或公网。

启动控制台也提供“停止”“重启”“检测连接”和“打开网页”按钮。配置只保存到本机 `chat2api/.env`，不会显示在运行信息中。只填写 Session Cookie 时，启动后会自动调用会话接口换取并保存新的 Access Token；换取失败会在运行信息中提示。

## 第一版范围

- 新建、搜索、打开和删除创意项目
- 自动保存创意需求、定位、画幅和产品证据
- 叙事类和展示类定位均使用 Excel 配置的单选/多选标签；展示类支持卖点→展示内容过滤、美术风格级联和轮播条件显示
- 保存参考文件，向 AI 提供参考文件名
- 展示类：每批 3 套视觉方案、最多 2 批、3 张异步 AI 参考图、单图重试和原图预览
- 叙事类：每批 5 个故事、10 个钩子和 30 条画面建议，最多 2 批
- 输入改变后保留旧定位历史
- 采用或替换当前方案

不包含 ERP 登录、人员、审核、任务分配、视频库和投放数据。

## 独立数据

- 数据库：`data/creative_studio.db`
- 图片：`data/images/`
- 参考文件：`data/uploads/`
- AI 网关配置：`chat2api/.env`
- 标签配置：`config/creative_tag_options.json`（由叙事类和展示类标签表整理，运行时只读）

这些运行数据和敏感配置均被 Git 忽略。当前 `.env` 是从本机原项目复制的配置，仅用于让这台电脑直接启动；不会进入提交。

## 开发验证

开始修改代码前先阅读根目录的 [`CODE_STYLE.md`](CODE_STYLE.md)。它记录正式原生前端、Python 后端和隔离 React 原型各自适用的技术栈与编码约定。

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m unittest discover -s tests -v
node --check static\app.js
python -m compileall -q src chat2api
```

## 当前技术边界

为快速独立，创意生成核心仍兼容原来的 `WEB_ERP_AI_*` 环境变量名，但变量只由本项目启动脚本设置，不依赖 ERP 进程或 ERP 数据。后续可以在不改变数据合同的情况下逐步重命名。

## 账号登录

网页现在要求登录后使用。首次启动前可通过一次性命令创建管理员（密码从标准输入读取，不回显）：

```powershell
$env:PYTHONPATH = "D:\\code\\ai_creative_studio\\src"
Read-Host -AsSecureString | ConvertFrom-SecureString -AsPlainText | python -m creative_studio.auth_cli init-admin --username admin --password-stdin
```

也可在首次启动时临时设置 `CREATIVE_STUDIO_BOOTSTRAP_USERNAME` 和 `CREATIVE_STUDIO_BOOTSTRAP_PASSWORD`；账号表非空后不会再次使用。密码最少 3 位，但公网部署强烈建议使用更长的随机密码。管理员可在网页中创建、停用、启用和重置普通账号；普通账号只能访问自己创建的项目。当前服务仍默认只监听 `127.0.0.1`，公网部署前还必须配置 HTTPS、反向代理、密钥管理、备份和外部限流。
## 网络代理工作台

启动控制台中的“网络代理工作台”可以独立配置 ChatGPT 网关的出站代理，也可以直接运行：

```powershell
python proxy_workbench.py
```

工作台支持 HTTP、HTTPS、SOCKS5/SOCKS5H 代理，保存到 `chat2api/.env` 的 `PROXY_URL`，并可通过 `api.ipify.org` 测试当前代理出口 IP。代理账号密码只在本机保存并始终脱敏显示；修改后需要重启 AI 网关。
