# AI v2 下一会话交接：生产接入剩余门禁

> 交给下一执行会话的工作文档。当前代码和受控评测已完成部分验证，但尚未获得 production caller、默认 live 或正式发布批准。

## 当前结论

- 根页面 `/` 已接入 AI v2 HTTP、存储、历史、按需图片和采用流程。
- P1 已完成：未启用 live 时正式入口 fail-closed，不再静默返回 candidate；前端能显示 `error_code`、阶段和 `trace_id`；生成、history 刷新和 project 刷新错误分开提示。
- 展示类轮播产品语义已确认保持 carousel-only：展示类选择轮播时只调用 carousel Prompt，不先调用 static Prompt。
- 三份 Prompt 仍未进入 production：registry 仍为 `candidate`，`caller=null`。
- 真实文字评测已完成，但只属于 `controlled_real_text_eval`，不能描述为生产质量通过。
- 真实图片评测已启动但停止于 provider `unknown`：静态首次请求接受过一个供应商 job，之后普通 `failed` 被按契约映射为 `unknown`；轮播图片未执行。
- 当前没有 production caller、默认 live、正式发布或本机正式数据切换。

## 仓库与运行状态

- 仓库：`D:\code\ai_creative_studio`
- 分支：`codex/tag-accordion-prototype`
- 当前工作树包含既有用户和本任务未提交修改，必须保留；不要使用 `reset --hard`、`checkout` 或批量覆盖命令。
- 最近清理旧 AI 的基线提交：`1bb6dd1`
- 当前 8775、8780、8791 均未监听。
- `CREATIVE_STUDIO_AI_V2_LIVE` 未设置。
- 未修改 `chat2api/.env`；没有新增真实数据库、图片或上传目录写入。

## 已完成验证

- deterministic 静态/轮播图片测试：12 项通过。
- AI v2 测试：通过。
- `.venv` 全量 unittest：180 项通过。
- release gate、Node 语法、compileall、AI v2 boundary、`git diff --check`：通过。
- 全量测试曾出现一次 adoption `updated_at` 秒级抖动，定向重跑后全量 180 项通过；这不是已确认的代码回归。

验证命令：

```powershell
Set-Location D:\code\ai_creative_studio
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_ai_v2_*.py" -q
node --check static\app.js
node --check static\ai-v2\app.js
.venv\Scripts\python.exe -m compileall -q src chat2api
.venv\Scripts\python.exe -m creative_studio.ai_v2.release_gate
.venv\Scripts\python.exe -c "from pathlib import Path; from creative_studio.ai_v2.boundary import assert_ai_v2_boundary; assert_ai_v2_boundary(Path('.'))"
git diff --check
```

## 真实评测证据

文字报告：

- `.scratch/ai-v2-real-text-eval/report.json`
- `.scratch/ai-v2-real-text-eval/carousel-rerun-report.json`
- `.scratch/ai-v2-real-text-eval/carousel-ai-count-rerun-report.json`

图片报告：

- `.scratch/ai-v2-real-image-eval/static-real-image-report.json`
- `.scratch/ai-v2-real-image-eval/carousel-real-image-report.json`

图片报告的状态是 `controlled_real_image_eval` / `not_exercised`。报告不构成 production pass，也没有记录 Prompt、Cookie、token、完整供应商响应、job/session 标识或绝对路径。

## 尚未完成的任务

### 1. Prompt 审批与 production caller

- 分别记录 narrative、static、carousel Prompt 的最终审批结论：允许受控评测、需修改后再评或不批准。
- 获得明确批准后，才将对应 registry 项从 `candidate` 变更为 `production`，并为每份 Prompt 指定唯一 caller。
- 同步 Prompt hash、schema、caller、最大调用次数和定向测试。
- 不要把“允许受控真实评测”解释为 production 批准。

### 2. 独立 production readiness gate

保留现有 candidate contract gate，新增独立 production gate，至少检查：

- registry lifecycle 为 `production`；
- 每份 Prompt 恰好一个 caller；
- caller 能从正式 composition root 到达对应 v2 use case；
- Prompt id、schema、hash、caller 和最大调用次数一致；
- candidate evidence 不会被伪装成 production evidence。

### 3. 真实图片链路补测

只有在明确得到图片预算、模型/供应商、临时输出目录和停止条件后才继续：

- static 首次成功、重复点击幂等、artifact/MIME/URL/公开 DTO；
- carousel 最小两帧越序保护、同一 session、参考图、cursor/revision、重复请求幂等；
- provider 明确终态失败时同一 session 内递增 attempt；
- unknown、timeout、断开和 5xx 先对账，不创建第二 session 或盲目重试。

重新验证必须继续使用工作台启动器执行代理桥。不要直接把远程 `socks5://` 交给 `chat2api/main.py`；直接运行会绕过 relay，导致 `curl (97) Failed to receive SOCKS response`。

### 4. 正式切换前门禁

- 对真实数据库、图片和上传目录做备份。
- 在新目录完成 restore smoke，并确认 `verified=true`、`references_verified=true`。
- 显式向 web 子进程传递 live 配置，启动单实例并检查 runtime adapter、registry、caller 和 health。
- 在用户指定项目执行文字和一次按需图片 smoke。
- 做 `1280x720` 与 `390x844` 根页面验收、控制台检查和横向溢出检查。
- 完成关闭 live 后的回滚演练。

## 必须获得的授权

在执行新的真实请求或正式切换前，必须明确记录：

- 具体 use case；
- 模型和供应商；
- 最大供应商提交数和预计成本；
- 脱敏输入样例；
- 临时 SQLite、图片/job/上传目录和清理策略；
- 认证失败、连续 provider unknown、超预算或隐私泄露时的停止条件。

本交接不授权修改 `chat2api/.env`、复制 token/Cookie、设置默认 live、写入真实运行目录、生产发布或提交当前工作树。

## 下一会话首条任务

1. 读取本 handoff、production integration handoff、image final handoff、`AGENTS.md`、`progress.md`、operations、AI 总纲和相关 ADR。
2. 保存 `git status --short --branch`，确认 8775/8780/8791 未监听且 live 未设置。
3. 运行上面的 deterministic、AI v2、release gate 和边界检查。
4. 不启动真实网关、不设置 live；先完成 Prompt 审批状态与 production readiness gate 的设计/测试。
5. 若要继续图片真实评测，先取得新的明确预算和停止条件，再使用工作台代理桥与隔离目录按 static → carousel 顺序执行。

## 禁止事项

- 不要把 controlled real text/image evidence 写成 production quality pass。
- 不要恢复旧 AI、旧路由、旧表写入、fallback、双写或双读。
- 不要修改 carousel-only 调用顺序，除非另开产品语义变更并重新评审。
- 不要在 unknown/timeout/5xx 后盲目创建第二 session。
- 不要写入真实 `data/`、`chat2api/images/`、`chat2api/image_job_state/` 或上传目录。
- 不要提交当前工作树，除非用户明确要求。
