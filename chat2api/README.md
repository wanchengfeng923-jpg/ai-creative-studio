# ChatGPT Web 网关交付说明

本目录是辅助创意工具使用的本地网关实现。它把本项目 AI v2 的 OpenAI 兼容请求转换为 ChatGPT 网页内部会话请求，并提供真实会话续接、模型列表、任务队列和会话凭据更换接口。

## 重要边界

- 该实现依赖 ChatGPT 网页内部接口，不是稳定的公开 API；上线前必须由负责人评估合规、账号和维护风险。
- `/v1/chat/completions` 本身没有独立业务认证。网页和网关部署在同一台机器时，必须使用 `HOST=127.0.0.1`，不要把 8780 暴露到公网或普通办公网。
- `/v1/session` 和 `/v1/session-info` 使用 `CHATGPT_CONTROL_TOKEN`。未配置控制令牌时，V2 仅允许真实回环来源；生产仍要求配置高强度随机令牌。
- 本交付来源中没有可验证的 `LICENSE` 文件。旧说明里的 MIT 标记不能作为公司分发依据，负责人必须确认代码来源和授权后再使用。

## 安装

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

只在服务器本地编辑 `.env`。至少填写：

```text
CHATGPT_ACCESS_TOKEN=<当前账号的访问令牌>
CHATGPT_CONTROL_TOKEN=<高强度随机控制令牌>
HOST=127.0.0.1
PORT=8780
MAX_CONCURRENT_TASKS=3
TASK_QUEUE_TIMEOUT=90
```

自动续期建议优先填写 `CHATGPT_REFRESH_TOKEN`；没有时可填写完整 `CHATGPT_SESSION_COOKIE`。服务器需要代理才能访问 ChatGPT 时再填写 `PROXY_URL`。

启动器传入的 `CREATIVE_STUDIO_AI_CONTROL_TOKEN` 必须与 `CHATGPT_CONTROL_TOKEN` 完全相同。

## 启动与检查

```powershell
.\.venv\Scripts\python main.py
```

本机检查：

- `GET http://127.0.0.1:8780/health`
- `GET http://127.0.0.1:8780/v1/task-queue`
- `GET http://127.0.0.1:8780/v1/models`

## 主要接口

- `POST /v1/chat/completions`：OpenAI 兼容对话；第二批可传 `conversation_id` 与 `parent_message_id`。
- `GET /v1/models`：探测当前账号可用模型；探测失败时返回候选列表并标记 `detected=false`。
- `GET /v1/task-queue`：最大并发、运行中、排队和可用槽位。
- `GET /v1/session-info`：凭据和自动续期状态，需要控制认证。
- `POST /v1/session`：保存新 Session Cookie 并尝试换取 Access Token，需要控制认证。

## 运行文件

`main.py` 注册路由；`routes_chat.py` 实现对话、续聊和模型探测；`routes_session.py` 保护会话控制；`task_limiter.py` 提供共享并发队列；`auth_refresh.py` 负责凭据续期和本机 `.env` 更新。图片路由依赖 `routes_images.py`、`web_client.py`、`image_utils.py` 和 `web_sse_parser.py`。
