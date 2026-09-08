# AI 创意工作台公网使用手册

适用服务器：Windows 公网服务器
公网地址：`http://42.194.220.18:8775/`
程序目录：`E:\AI-Creative-Studio`
网页端口：`8775`
AI 网关端口：`8780`（只允许服务器本机访问）

本文按小白操作编写。每次开机后照着“启动公网”执行；停止使用时照着“下线公网”执行。

## 启动公网

### 1. 登录服务器

在自己的电脑打开 Windows“远程桌面连接”，连接服务器公网 IP，使用已有 Windows 账号登录。

### 2. 启动网关和代理

打开服务器上的：

```text
E:\AI-Creative-Studio\启动AI创意工作台.bat
```

在启动器中点击“启动”。启动器负责读取 `chat2api\.env`、启动 AI 网关和代理桥。

不要同时在 PowerShell 里再启动第二个 `main.py`，否则会发生端口冲突。

### 3. 检查网关

打开 PowerShell，执行：

```powershell
Invoke-WebRequest "http://127.0.0.1:8780/health" -UseBasicParsing
```

看到 `StatusCode : 200` 才继续。响应中应有 `"has_token":true`。

如果这里失败，先回到启动器检查网关状态，不要重复点击多个启动器。

### 4. 启动公网网页

启动器可能已经启动网页，但为了确保网页拿到图片功能需要的控制令牌，使用下面命令重启网页进程。它不会修改 `.env`，也不会打印 Token。

```powershell
Set-Location "E:\AI-Creative-Studio"

$envFile = "E:\AI-Creative-Studio\chat2api\.env"
$controlLine = Get-Content $envFile |
  Where-Object { $_ -match "^CHATGPT_CONTROL_TOKEN=" } |
  Select-Object -First 1
if (-not $controlLine) { throw "没有找到 CHATGPT_CONTROL_TOKEN" }
$env:CREATIVE_STUDIO_AI_CONTROL_TOKEN =
  ($controlLine -replace "^CHATGPT_CONTROL_TOKEN=", "").Trim()

$env:PYTHONPATH = "E:\AI-Creative-Studio\src"
$env:CREATIVE_STUDIO_HOST = "0.0.0.0"
$env:CREATIVE_STUDIO_PORT = "8775"
$env:CREATIVE_STUDIO_AI_GATEWAY_URL = "http://127.0.0.1:8780"
$env:CREATIVE_STUDIO_AI_API_KEY = "local-chatgpt-gateway"
$env:CREATIVE_STUDIO_AI_MODEL = "gpt-5-6-mini"
$env:CREATIVE_STUDIO_AI_V2_LIVE = "1"
$env:CREATIVE_STUDIO_DATA_DIR = "E:\AI-Creative-Studio\data"
$env:CHATGPT_IMAGES_DIR = "E:\AI-Creative-Studio\data\images"
$env:CHATGPT_IMAGE_JOB_DIR = "E:\AI-Creative-Studio\data\image_job_state"

Get-NetTCPConnection -State Listen -LocalPort 8775 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

Start-Process `
  -FilePath "E:\AI-Creative-Studio\.venv\Scripts\python.exe" `
  -ArgumentList "-m creative_studio.app" `
  -WorkingDirectory "E:\AI-Creative-Studio" `
  -RedirectStandardOutput "E:\AI-Creative-Studio\logs\web.out.log" `
  -RedirectStandardError "E:\AI-Creative-Studio\logs\web.err.log" `
  -WindowStyle Hidden
```

### 5. 检查网页

```powershell
Invoke-WebRequest "http://127.0.0.1:8775/api/health" -UseBasicParsing
```

看到 `StatusCode : 200` 后，在自己的电脑浏览器打开：

```text
http://42.194.220.18:8775/
```

登录工作台后，先测试文字生成，再测试一张图片。图片失败时先看服务器日志，不要连续重复点击。

## 下线公网

在服务器 PowerShell 执行：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8775 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

Remove-NetFirewallRule -DisplayName "AI Creative Studio Web 8775" -ErrorAction SilentlyContinue
```

然后在启动器中点击“停止”，关闭 AI 网关和代理桥。下线后公网地址应无法访问。

## 常见问题

### 网页能打开，文字能生成，图片失败

确认网页进程启动前执行了读取 `CHATGPT_CONTROL_TOKEN` 的命令。图片接口需要网页控制令牌，文字成功不能证明图片控制令牌已注入。

### 网关提示端口 8700 被占用

说明手动启动时没有设置 `PORT=8780`，或已有旧网关进程。停止旧网关后，优先使用启动器启动代理桥和网关。

### 网关健康检查 200，但 AI 请求报 SOCKS response

说明本地网关活着，但代理桥没有正确运行。停止 Shell 启动的网关，只通过启动器启动网关和代理桥。

### 网页打不开

在服务器检查：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8775
Get-NetFirewallRule -DisplayName "AI Creative Studio Web 8775" -ErrorAction SilentlyContinue
```

网页必须监听 `0.0.0.0:8775`，防火墙规则必须存在。

## 重要注意

- 不要把 `8780` 加入公网防火墙规则。
- 不要把 `.env` 发到聊天、Git 或普通压缩包中。
- 不要删除 `E:\AI-Creative-Studio\data`、图片、上传文件或备份目录。
- 不要同时启动多个启动器、多个网关或多个网页进程。
- 当前入口使用公网 IP 和 HTTP，没有 HTTPS；只适合受控使用，正式长期使用前应增加 HTTPS 和访问限制。
