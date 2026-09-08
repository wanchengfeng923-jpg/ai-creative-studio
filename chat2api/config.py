"""应用配置，从环境变量 / .env 文件加载。"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ChatGPT Access Token（从 https://chatgpt.com/api/auth/session 获取）
    chatgpt_access_token: str = ""
    chatgpt_base_url: str = "https://chatgpt.com"

    # 可选：ChatGPT 网页会话 Cookie（__Secure-next-auth.session-token 的值）
    # 配置后 access token 到期前会自动续期，无需手动更换。
    chatgpt_session_cookie: str = ""

    # 可选：OpenAI auth0 refresh token。配置后优先用它在到期前换取 access token。
    chatgpt_refresh_token: str = ""

    # 自动续期提前量（小时），默认提前 72 小时尝试续期
    refresh_lead_hours: int = 72

    # 控制令牌：调用 /v1/session（在页面里切换会话 Cookie 用）时需要。
    # 留空则仅限本机直接访问（不推荐暴露控制接口时使用）。
    chatgpt_control_token: str = ""

    # 出站代理（可选，支持 http/https/socks5）
    proxy_url: str = ""

    # 监听地址（默认仅本机，避免向局域网暴露网关）
    host: str = "127.0.0.1"

    # 服务
    port: int = 8780
    timeout: int = 600  # 秒
    max_concurrent_tasks: int = 3
    task_queue_timeout: int = 90  # 秒，需短于创意工作台前端 300 秒请求超时

    # Web 模式图片生成默认模型
    web_image_model: str = "gpt-5-5-thinking"
    # Web 模式 chat 默认模型
    web_chat_model: str = "gpt-4o"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # 允许 .env 里存在本配置之外的变量（如 CHATGPT_COOKIE_UPDATED_AT），避免启动报错
        extra = "ignore"


settings = Settings()
