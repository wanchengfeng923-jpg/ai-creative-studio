# 固定开发、发布和服务器更新流程

适用项目：AI 创意工作台
开发仓库：`D:\code\ai_creative_studio`
GitHub：`wanchengfeng923-jpg/ai-creative-studio`（私有）
服务器目录：`E:\AI-Creative-Studio`

## 一、长期不变的边界

- GitHub `master` 是准备发布代码的唯一来源；服务器代码不得反向覆盖开发仓库。
- 服务器的 `data\creative_studio.db`、`data\images`、`data\uploads` 和 `chat2api\.env` 是生产数据与配置，不进入 Git，也不进入程序更新包。
- `8780` 只监听服务器本机；公网只使用现有 `8775`。本流程不修改防火墙、域名、HTTPS或端口。
- 发布包只来自一个已提交的 Git ref。工作树未提交、测试失败、Prompt registry/hash 不一致时不生成发布包。
- 服务器更新分为 `Inspect` 和 `Apply`。必须先检查成功，再停止服务并显式执行应用。

## 二、日常开发

每个需求从最新 `master` 建立独立分支：

```powershell
Set-Location "D:\code\ai_creative_studio"
git switch master
git pull --ff-only
git switch -c "codex/需求短名称"
```

完成修改后运行与影响范围相符的测试。代码改动的基础检查是：

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -q
& ".\.venv\Scripts\python.exe" -m creative_studio.ai_v2.release_gate
```

然后提交并推送分支：

```powershell
git add <本次修改的文件>
git diff --cached --check
git commit -m "feat: 说明这次改动"
git push -u origin HEAD
```

代码评审和检查通过后，再将需求分支合并到 `master`。不要直接在服务器修改代码。

## 三、制作发布包

先确认 `master` 干净并与 GitHub 同步：

```powershell
git switch master
git pull --ff-only
git status --short --branch
```

只有输出不包含修改或未跟踪文件时才制作发布包：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\build_release.ps1" -Ref "master"
```

脚本会在隔离的 Git checkout 中运行全量 unittest 和 release gate。全部通过后才在 `.release\` 生成：

- `ai-creative-studio-<发布编号>.zip`
- 同名 `.zip.sha256`
- 同名 `.manifest.json`

发布记录必须保存 Git commit、ZIP SHA-256 和规范化代码 SHA-256。ZIP 哈希用于确认上传文件没有损坏；代码哈希用于确认程序内容。

当前 `master` 在发布基准后已有新的 Prompt 提交，而且当前事实记录存在 Prompt hash 不一致。修复并重新通过门禁之前，发布脚本应失败，这是正常保护。

流程脚本首次验证记录（2026-09-09）：`production-baseline-20260908` 在隔离 checkout 中通过 200 项全量 unittest 和 124 项 release gate 检查；同一脚本针对当前 `master` 会因 Prompt registry/hash 不一致而中止，且不会生成发布包。因此当前可验证的生产基准仍是 `production-baseline-20260908`，当前 `master` 暂不可发布。

服务器脚本也已在本机临时安装目录完成 `Inspect -> Apply -> Rollback` 演练：代码在 Apply 时被替换，Rollback 后恢复；模拟 SQLite 文件和 `chat2api\.env` 在全过程中的 SHA-256 均保持不变。该演练验证的是脚本行为，不代表已经更新真实服务器。

## 四、上传和只读检查

通过 RDP 把三个发布文件上传到：

```text
E:\AI-Creative-Studio\staging\incoming\<发布编号>\
```

先读取 `.zip.sha256` 中的 64 位哈希，再执行只读检查。以下命令不会替换代码：

```powershell
Set-Location "E:\AI-Creative-Studio"

powershell -ExecutionPolicy Bypass -File ".\scripts\server_release.ps1" `
  -Mode Inspect `
  -PackagePath ".\staging\incoming\<发布编号>\ai-creative-studio-<发布编号>.zip" `
  -ExpectedSHA256 "<64位ZIP哈希>"
```

只有输出 `Status : verified`，并且 Git commit、代码文件数和代码 SHA-256 与开发机发布结果一致时，才进入更新。

## 五、服务器更新

### 1. 更新前备份生产数据

先按 `docs/operations.md` 使用 SQLite backup 工具生成一致性备份，并在新目录执行恢复 smoke。必须看到：

```text
verified=true
references_verified=true
```

### 2. 停止服务

在启动器中点击“停止”并关闭启动器，然后确认两个端口均无监听：

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 8775,8780 } |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

没有输出才继续。更新期间公网网页会暂时不可访问。

### 3. 应用代码

重新执行服务器脚本，把模式改成 `Apply`：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\server_release.ps1" `
  -Mode Apply `
  -PackagePath ".\staging\incoming\<发布编号>\ai-creative-studio-<发布编号>.zip" `
  -ExpectedSHA256 "<64位ZIP哈希>"
```

脚本会再次校验 ZIP 和每个文件，保存代码回滚副本，只替换发布清单内的程序文件，并运行依赖安装。它拒绝处理 `.env`、`.venv`、`data`、图片、上传、日志、暂存和私有配置路径。

记录输出中的 `ReleaseId`、`GitCommit` 和 `RollbackId`。

### 4. 重新启动和验收

按 `docs/deployment/public-startup-guide.md` 启动 AI 网关和公网网页，然后检查：

```powershell
Invoke-WebRequest "http://127.0.0.1:8780/health" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8775/api/health" -UseBasicParsing
```

再用浏览器依次验证登录、打开已有项目、文字生成和图片生成。真实 AI/图片验收需控制调用次数并记录结果。

## 六、失败回滚

更新或启动验收失败时，保持 `8775`、`8780` 停止，使用刚才记录的 `RollbackId`：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\server_release.ps1" `
  -Mode Rollback `
  -RollbackId "<RollbackId>"
```

回滚只恢复程序文件。生产数据没有被程序更新脚本覆盖；若问题属于数据库迁移，必须按单独的数据恢复门禁处理，不能用代码回滚代替数据库恢复。

回滚后按原公网启动步骤重新启动，并再次检查两个 health 接口和登录。

## 七、每次发布必须记录

| 项目 | 内容 |
|---|---|
| 发布编号 | 构建脚本输出的 `ReleaseId` |
| Git commit | 构建和服务器检查输出必须一致 |
| ZIP SHA-256 | 开发机、服务器必须一致 |
| 代码 SHA-256 | 构建和服务器检查必须一致 |
| 生产备份 | 路径、manifest、恢复 smoke 结果 |
| 回滚编号 | `Apply` 输出的 `RollbackId` |
| 验收 | 网关 health、网页 health、登录、文字、图片 |
| 未验证项 | 明确记录没有执行的检查 |
