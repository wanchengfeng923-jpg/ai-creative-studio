"""AI 创意工作台本地启动控制台。

只管理本项目的网页服务和 chat2api 网关，配置保存到本机 chat2api/.env。
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / "chat2api" / ".env"
WEB_URL = "http://127.0.0.1:8775/"
GATEWAY_URL = "http://127.0.0.1:8780"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def save_env(updates: dict[str, str]) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI 创意工作台启动控制台")
        self.geometry("760x590")
        self.minsize(680, 520)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.gateway_process: subprocess.Popen[bytes] | None = None
        self.web_process: subprocess.Popen[bytes] | None = None
        self.status_var = tk.StringVar(value="尚未启动")
        self.gateway_var = tk.StringVar(value="未启动")
        self.connection_var = tk.StringVar(value="尚未检测")
        self.expiry_var = tk.StringVar(value="未检测")
        self.token_var = tk.StringVar()
        self.cookie_var = tk.StringVar()
        self.secret_values: dict[str, str] = {"token": "", "cookie": ""}
        self.secret_entries: dict[str, ttk.Entry] = {}
        self.secret_editing: set[str] = set()
        self._build_ui()
        self._load_config()
        self.after(1200, self._poll_processes)

    def _build_ui(self) -> None:
        pad = {"padx": 22, "pady": 8}
        header = ttk.Frame(self)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="AI 创意工作台", font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        ttk.Label(header, text="本机配置与启动控制台 · 网页 8775 · AI 网关 8780", foreground="#52606d").pack(anchor="w", pady=(3, 0))

        state = ttk.LabelFrame(self, text="连接状态")
        state.pack(fill="x", **pad)
        for row, (label, variable) in enumerate((("网页服务", self.status_var), ("AI 网关", self.gateway_var), ("ChatGPT 连接", self.connection_var), ("Token 到期", self.expiry_var))):
            ttk.Label(state, text=label, width=16).grid(row=row, column=0, sticky="w", padx=16, pady=6)
            ttk.Label(state, textvariable=variable, font=("Microsoft YaHei UI", 10, "bold")).grid(row=row, column=1, sticky="w", padx=10, pady=6)

        config = ttk.LabelFrame(self, text="登录配置")
        config.pack(fill="x", **pad)
        self._secret_row(config, 0, "Access Token", "token", self.token_var)
        self._secret_row(config, 1, "Session Cookie", "cookie", self.cookie_var)
        ttk.Label(config, text="配置仅保存在本机 chat2api/.env，不会显示在运行日志中", foreground="#52606d").grid(row=2, column=1, columnspan=2, sticky="w", padx=10, pady=(0, 9))
        config.columnconfigure(1, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.save_button = ttk.Button(actions, text="保存配置", command=self.save_config)
        self.save_button.pack(side="left", padx=(0, 8))
        self.start_button = ttk.Button(actions, text="启动", command=self.start_services)
        self.start_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(actions, text="停止", command=self.stop_services, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        self.restart_button = ttk.Button(actions, text="重启", command=self.restart_services, state="disabled")
        self.restart_button.pack(side="left", padx=4)
        self.test_button = ttk.Button(actions, text="检测连接", command=self.test_connection)
        self.test_button.pack(side="left", padx=4)
        ttk.Button(actions, text="打开网页", command=lambda: webbrowser.open(WEB_URL)).pack(side="right")

        log_frame = ttk.LabelFrame(self, text="运行信息")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=7, state="disabled", wrap="word", bg="#fbfcfd", relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=8)

    def _secret_row(self, parent: ttk.LabelFrame, row: int, label: str, key: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, width=16).grid(row=row, column=0, sticky="w", padx=16, pady=7)
        entry = ttk.Entry(parent, textvariable=variable, show="*")
        entry.grid(row=row, column=1, sticky="ew", padx=10, pady=7)
        self.secret_entries[key] = entry
        entry.bind("<Button-1>", lambda _event: self._edit_secret(key))
        ttk.Button(parent, text="编辑", width=7, command=lambda: self._edit_secret(key)).grid(row=row, column=2, padx=(0, 10), pady=7)

    def _edit_secret(self, key: str) -> None:
        entry = self.secret_entries[key]
        variable = self.token_var if key == "token" else self.cookie_var
        # 不把旧的超长 Token/Cookie 载入 Tk 控件，避免 Entry 重绘卡顿。
        variable.set("")
        self.secret_editing.add(key)
        entry.configure(show="*")
        entry.focus_set()
        entry.selection_range(0, "end")

    def _load_config(self) -> None:
        values = read_env()
        self.secret_values["token"] = values.get("CHATGPT_ACCESS_TOKEN", "")
        self.secret_values["cookie"] = values.get("CHATGPT_SESSION_COOKIE", "")
        self.token_var.set("已配置（点击编辑）" if self.secret_values["token"] else "")
        self.cookie_var.set("已配置（点击编辑）" if self.secret_values["cookie"] else "")
        self._log("已读取本机配置。")

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def save_config(self) -> None:
        token_input = self.token_var.get().strip()
        cookie_input = self.cookie_var.get().strip()
        token = token_input if "token" in self.secret_editing and token_input else self.secret_values["token"]
        cookie = cookie_input if "cookie" in self.secret_editing and cookie_input else self.secret_values["cookie"]
        self.secret_values.update(token=token, cookie=cookie)
        self.secret_editing.clear()
        self.token_var.set("已配置（点击编辑）" if token else "")
        self.cookie_var.set("已配置（点击编辑）" if cookie else "")
        save_env({"CHATGPT_ACCESS_TOKEN": token, "CHATGPT_SESSION_COOKIE": cookie})
        self._log("配置已保存。重新启动网关后生效。")

    def _current_secret(self, key: str) -> str:
        entry = self.secret_entries[key]
        variable = self.token_var if key == "token" else self.cookie_var
        return variable.get().strip() if key in self.secret_editing and variable.get().strip() else self.secret_values[key]

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({"PYTHONPATH": str(ROOT / "src"), "CREATIVE_STUDIO_HOST": "127.0.0.1", "CREATIVE_STUDIO_PORT": "8775", "PORT": "8780", "HOST": "127.0.0.1", "WEB_ERP_AI_PROVIDER": "chatgpt-web", "WEB_ERP_AI_API_URL": f"{GATEWAY_URL}/v1/chat/completions", "WEB_ERP_AI_API_KEY": "local-chatgpt-gateway", "WEB_ERP_AI_MODEL": "gpt-5-6-mini", "WEB_ERP_AI_PROMPT_VERSION": "v5", "WEB_ERP_AI_PROMPT_PATH": str(ROOT / "config" / "ai_creative_prompt_v5.txt"), "WEB_ERP_AI_VISUAL_PROMPT_PATH": str(ROOT / "config" / "ai_visual_creative_prompt_v2.txt"), "WEB_ERP_AI_VISUAL_PROMPT_VERSION": "visual-v2.3", "WEB_ERP_AI_GAME_INFO_PATH": str(ROOT / "config" / "ai_creative_game_info_v2.json"), "WEB_ERP_AI_TIMEOUT_SECONDS": "300", "WEB_ERP_AI_CONTROL_TOKEN": read_env().get("CHATGPT_CONTROL_TOKEN", "")})
        return env

    def start_services(self) -> None:
        self.save_config()
        token = self._current_secret("token")
        cookie = self._current_secret("cookie")
        if not token and not cookie:
            messagebox.showwarning("缺少配置", "请至少填写 Access Token 或 Session Cookie，再点击启动。")
            return
        env = self._environment()
        self._set_running(True)
        self.gateway_var.set("启动中...")
        self.status_var.set("启动中...")
        self._log("正在后台启动本地服务，控制台保持可操作。")
        threading.Thread(target=self._start_processes, args=(env, token, cookie), daemon=True).start()

    def _start_processes(self, env: dict[str, str], token: str, cookie: str) -> None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            gateway = self.gateway_process
            web = self.web_process
            if gateway is None or gateway.poll() is not None:
                gateway = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "main.py"], cwd=ROOT / "chat2api", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            if web is None or web.poll() is not None:
                web = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "creative_studio.app"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            self.gateway_process, self.web_process = gateway, web
            self.after(0, lambda: self._log("服务已启动，正在等待网页就绪。"))
            if cookie and not token:
                self.after(1400, lambda: threading.Thread(target=self._renew_from_cookie, daemon=True).start())
            self.after(1800, lambda: webbrowser.open(WEB_URL))
        except OSError as exc:
            self.after(0, lambda error=exc: (self._set_running(False), self._log(f"启动失败：{error}"), messagebox.showerror("启动失败", "无法启动本地服务，请确认 .venv 已准备完成。")))

    def stop_services(self) -> None:
        for process in (self.web_process, self.gateway_process):
            if process and process.poll() is None:
                process.terminate()
        self.web_process = None
        self.gateway_process = None
        self._set_running(False)
        self._log("服务已停止。")

    def restart_services(self) -> None:
        self.stop_services()
        self.after(400, self.start_services)

    def test_connection(self) -> None:
        # 检测前先保存用户刚粘贴的 Cookie，避免仍使用旧配置。
        self.save_config()
        self.test_button.configure(state="disabled")
        self.connection_var.set("检测中...")
        self._log("正在检测 AI 网关连接（最多等待 8 秒）...")
        def check() -> None:
            try:
                cookie = self._current_secret("cookie")
                if not cookie:
                    raise RuntimeError("请先填写 Session Cookie")
                # 仅检测时也确保网关已启动，便于 Cookie-only 换取 Token。
                if not self.gateway_process or self.gateway_process.poll() is not None:
                    self.gateway_process = subprocess.Popen(
                        [str(ROOT / ".venv" / "Scripts" / "python.exe"), "main.py"],
                        cwd=ROOT / "chat2api", env=self._environment(),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                deadline = time.time() + 8
                while time.time() < deadline:
                    try:
                        with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=1) as response:
                            data = json.loads(response.read().decode("utf-8"))
                        break
                    except OSError:
                        time.sleep(0.25)
                else:
                    raise RuntimeError("AI 网关启动超时")
                # 只要配置了 Cookie，每次检测都强制换取一次新 Token；旧 Token 可能已过期但仍非空。
                if cookie:
                    headers = {"Content-Type": "application/json"}
                    control_token = read_env().get("CHATGPT_CONTROL_TOKEN", "").strip()
                    if control_token:
                        headers["X-Control-Token"] = control_token
                    request = urllib.request.Request(
                        f"{GATEWAY_URL}/v1/session",
                        data=json.dumps({"session_cookie": cookie}).encode("utf-8"),
                        headers=headers, method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=30) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    if not data.get("ok") or not data.get("has_token"):
                        raise RuntimeError(str(data.get("error") or "Cookie 换取 Access Token 失败"))
                    new_token = read_env().get("CHATGPT_ACCESS_TOKEN", "")
                    self.secret_values["token"] = new_token
                    self.after(0, lambda: self.token_var.set("已配置（点击编辑）"))
                with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=8) as response:
                    data = json.loads(response.read().decode("utf-8"))
                text = "已连接，Access Token 已自动填入" if data.get("ok") else "网关已启动，但 Token 未生效"
                expiry = data.get("seconds_to_expire")
                if expiry is None:
                    expiry_text = "未返回"
                elif int(expiry) <= 0:
                    expiry_text = "已过期"
                elif int(expiry) < 86400:
                    expiry_text = f"不足 1 天（约 {max(1, int(expiry / 3600))} 小时）"
                else:
                    expiry_text = f"约 {int(expiry / 86400)} 天后"
            except (OSError, ValueError, urllib.error.URLError, RuntimeError) as exc:
                text, expiry_text = "连接失败", "未检测"
                self.after(0, lambda: self._log(f"连接检测失败：{type(exc).__name__}，请确认已点击启动且 8780 端口可用。"))
            self.after(0, lambda: (self.connection_var.set(text), self.expiry_var.set(expiry_text), self.test_button.configure(state="normal")))
        threading.Thread(target=check, daemon=True).start()

    def _renew_from_cookie(self) -> None:
        """Cookie-only 配置启动后，立即向网关申请一次新的 Access Token。"""
        try:
            headers = {"Content-Type": "application/json"}
            control_token = read_env().get("CHATGPT_CONTROL_TOKEN", "").strip()
            if control_token:
                headers["X-Control-Token"] = control_token
            request = urllib.request.Request(f"{GATEWAY_URL}/v1/session", data=json.dumps({"session_cookie": self._current_secret("cookie")}).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            if data.get("ok") and data.get("has_token"):
                self.secret_values["token"] = read_env().get("CHATGPT_ACCESS_TOKEN", "")
                self.token_var.set("已配置（点击编辑）")
                self.after(0, lambda: (self.connection_var.set("已连接（Cookie 已换取 Token）"), self._log("Session Cookie 已成功换取新的 Access Token。")))
            else:
                error = str(data.get("error") or "Cookie 换取 Token 失败")
                self.after(0, lambda: (self.connection_var.set("Cookie 换取失败"), self._log(f"{error}")))
        except Exception as exc:
            self.after(0, lambda: (self.connection_var.set("Cookie 换取失败"), self._log(f"Cookie 自动换取 Token 失败：{type(exc).__name__}")))

    def _set_running(self, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.restart_button.configure(state="normal" if running else "disabled")

    def _poll_processes(self) -> None:
        gateway_running = bool(self.gateway_process and self.gateway_process.poll() is None)
        web_running = bool(self.web_process and self.web_process.poll() is None)
        self.gateway_var.set("运行中" if gateway_running else "未启动")
        self.status_var.set("运行中" if web_running else "未启动")
        if not gateway_running and not web_running:
            self._set_running(False)
        self.after(1200, self._poll_processes)

    def close(self) -> None:
        self.stop_services()
        self.destroy()


if __name__ == "__main__":
    try:
        Launcher().mainloop()
    except Exception as exc:  # pythonw 没有控制台，必须给出可见的失败信息
        error_text = f"{type(exc).__name__}: {exc}"
        (ROOT / "launcher_error.log").write_text(error_text + "\n", encoding="utf-8")
        try:
            messagebox.showerror("启动控制台失败", f"{error_text}\n\n详细信息已写入 launcher_error.log")
        except Exception:
            pass
