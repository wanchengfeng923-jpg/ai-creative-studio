"""AI 创意工作台本地启动控制台。

只管理本项目的网页服务和 chat2api 网关，配置保存到本机 chat2api/.env。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import quote, unquote, urlparse, urlunparse

from proxy_relay import ClipProxyRelay


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / "chat2api" / ".env"
WEB_URL = "http://127.0.0.1:8775/"
GATEWAY_URL = "http://127.0.0.1:8780"
WEB_BIND_HOST = "127.0.0.1"


def _terminate_process(process: subprocess.Popen[bytes], timeout: float = 3.0) -> None:
    """终止子进程并等待；正常终止超时后再强制结束，避免端口残留。"""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass


def format_connection_error(error: BaseException, secrets: tuple[str, ...] = ()) -> str:
    """生成可显示的脱敏连接错误，保留上游返回的排查线索。"""
    detail = str(error).strip() or "未提供错误详情"
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "[已隐藏]")
    return f"{type(error).__name__}：{detail[:240]}"


def should_refresh_session(health: dict[str, object]) -> bool:
    """仅在网关没有明确有效的 Access Token 时刷新 Cookie 会话。"""
    if health.get("ok") is not True or health.get("has_token") is not True:
        return True
    seconds_to_expire = health.get("seconds_to_expire")
    return not isinstance(seconds_to_expire, (int, float)) or seconds_to_expire <= 0


def gateway_upstream_verified(models: dict[str, object]) -> bool:
    """只有网关从上游探测到模型列表时，才认为凭据真正可用。"""
    entries = models.get("data")
    return models.get("detected") is True and isinstance(entries, list) and bool(entries)


def should_refresh_from_cookie(models: dict[str, object], has_cookie: bool) -> bool:
    """上游验证失败且有会话 Cookie 时，允许用 Cookie 更新网关 Token。"""
    return bool(has_cookie) and not gateway_upstream_verified(models)


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


def parse_proxy_url(value: str) -> dict[str, str]:
    parsed = urlparse(value.strip())
    try:
        port = parsed.port
    except ValueError:
        port = None
    if parsed.scheme.lower() not in {"http", "https", "socks5", "socks5h"} or not parsed.hostname or not port:
        return {"scheme": "http", "host": "", "port": "", "username": "", "password": ""}
    return {
        "scheme": parsed.scheme.lower(),
        "host": parsed.hostname,
        "port": str(port),
        "username": parsed.username or "",
        "password": parsed.password or "",
    }


def build_proxy_url(scheme: str, host: str, port: str, username: str = "", password: str = "") -> str:
    scheme = scheme.strip().lower()
    host = host.strip()
    port = port.strip()
    if not host or not port or not port.isdigit() or not 1 <= int(port) <= 65535:
        return ""
    auth = ""
    if username:
        auth = quote(username, safe="")
        if password:
            auth += ":" + quote(password, safe="")
        auth += "@"
    return urlunparse((scheme, f"{auth}{host}:{port}", "", "", "", ""))


def mask_proxy_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if not parsed.hostname:
        return "未配置"
    try:
        port = parsed.port
    except ValueError:
        return "配置无效"
    auth = ""
    if parsed.username:
        auth = quote(parsed.username, safe="") + ":***@"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{auth}{host}{':' + str(port) if port else ''}"
    return urlunparse((parsed.scheme, netloc, "", "", "", ""))


def probe_proxy_ip(proxy_url: str) -> str:
    """通过与网关相同的 curl_cffi 客户端探测代理出口，兼容 SOCKS5。"""
    from curl_cffi import requests as curl_requests

    response = curl_requests.get(
        "https://api.ipify.org?format=json",
        proxy=proxy_url,
        impersonate="chrome",
        verify=False,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    ip = str(payload.get("ip") or "").strip()
    if not ip:
        raise RuntimeError("出口服务未返回 IP")
    return ip


def select_runtime_proxy(configured: str, probe=probe_proxy_ip) -> tuple[str, str]:
    """选择可用出站代理；直连端点失败时自动尝试本机 Clash 入口。"""
    configured = configured.strip()
    if not configured:
        return "", "未配置代理"
    candidates = [configured]
    for port in (7897, 7890, 7891, 1080):
        local = f"http://127.0.0.1:{port}"
        if local not in candidates:
            candidates.append(local)
    errors: list[str] = []
    for index, candidate in enumerate(candidates):
        try:
            ip = probe(candidate)
            if index == 0:
                return candidate, f"已使用配置代理，出口 IP {ip}"
            return candidate, f"配置代理不可达，已自动切换本机 Clash ({candidate.rsplit(':', 1)[-1]})，出口 IP {ip}；请确认 Clash 节点就是 ClipProxy 固定 IP"
        except Exception as exc:
            errors.append(f"{candidate.rsplit(':', 1)[-1]}:{type(exc).__name__}")
    return configured, "代理探测失败，保留原配置（启动后可能报错）：" + ", ".join(errors)


BRIDGE_PORT = 7896
BRIDGE_RUNTIME_DIR = ROOT / ".runtime"
CLASH_PORTS = (7897, 7890, 7891)


def _clash_config_paths() -> list[Path]:
    configured = os.environ.get("CLASH_CONFIG_PATH", "").strip()
    paths = [Path(configured)] if configured else []
    clash_home = os.environ.get("CLASH_HOME", "").strip()
    if clash_home:
        paths.extend([Path(clash_home) / "config.yaml", Path(clash_home) / "clash-verge.yaml"])
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    roaming = Path(os.environ.get("APPDATA", "").strip()) if os.environ.get("APPDATA") else None
    for base in (Path(local_app_data) / "Clash Verge", roaming / "io.github.clash-verge-rev.clash-verge-rev" if roaming else None):
        if base:
            paths.extend([base / "config.yaml", base / "clash-verge.yaml"])
    return list(dict.fromkeys(path for path in paths if path.is_file()))


def _configured_clash_endpoints() -> list[tuple[int, str]]:
    endpoints: list[tuple[int, str]] = []
    pattern = re.compile(r"^\s*(mixed-port|socks-port|port)\s*:\s*(\d+)\s*(?:#.*)?$")
    for path in _clash_config_paths():
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            match = pattern.match(line)
            if not match:
                continue
            key, raw_port = match.groups()
            port = int(raw_port)
            scheme = "socks5" if key == "socks-port" else "http"
            if 1 <= port <= 65535 and (port, scheme) not in endpoints:
                endpoints.append((port, scheme))
    return endpoints


def build_mihomo_config(proxy_url: str, upstream_port: int, listen_port: int = BRIDGE_PORT, upstream_scheme: str = "http") -> dict[str, object]:
    """生成项目专用 Mihomo 配置，令 ClipProxy 通过本机 Clash 出站。"""
    fields = parse_proxy_url(proxy_url)
    if not fields["host"] or not fields["port"]:
        raise ValueError("ClipProxy 代理地址无效")
    proxy_type = "socks5" if fields["scheme"].startswith("socks5") else "http"
    clipproxy: dict[str, object] = {
        "name": "clipproxy",
        "type": proxy_type,
        "server": fields["host"],
        "port": int(fields["port"]),
        "dialer-proxy": "clash-upstream",
    }
    if fields["username"]:
        clipproxy["username"] = unquote(fields["username"])
    if fields["password"]:
        clipproxy["password"] = unquote(fields["password"])
    if fields["scheme"] == "https":
        clipproxy["tls"] = True
    upstream_type = "socks5" if upstream_scheme == "socks5" else "http"
    return {
        "mixed-port": listen_port,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "proxies": [
            {
                "name": "clash-upstream",
                "type": upstream_type,
                "server": "127.0.0.1",
                "port": upstream_port,
            },
            clipproxy,
        ],
        "proxy-groups": [{"name": "chat2api-chain", "type": "select", "proxies": ["clipproxy"]}],
        "rules": ["MATCH,chat2api-chain"],
    }


def find_mihomo_executable() -> Path | None:
    """查找本机 Mihomo；不读取或修改 Clash 的订阅配置。"""
    configured = os.environ.get("MIHOMO_PATH", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Program Files\Clash Verge\verge-mihomo.exe"),
        Path(r"C:\Program Files\Clash Verge\verge-mihomo-alpha.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Clash Verge" / "verge-mihomo.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return Path(shutil.which("mihomo")) if shutil.which("mihomo") else None


def find_local_clash_port() -> int | None:
    """兼容旧调用方，返回自动发现的 Clash 入口端口。"""
    endpoint = find_local_clash_endpoint()
    return endpoint[0] if endpoint else None


def find_local_clash_endpoint() -> tuple[int, str] | None:
    """自动发现本机 Clash 监听端口及协议，支持不同电脑的自定义端口。"""
    endpoints = _configured_clash_endpoints()
    configured = os.environ.get("CHAT2API_CLASH_PORT", "").strip()
    if configured.isdigit() and 1 <= int(configured) <= 65535:
        protocol = os.environ.get("CHAT2API_CLASH_PROTOCOL", "http").strip().lower()
        endpoints.insert(0, (int(configured), protocol if protocol in {"http", "socks5"} else "http"))
    endpoints.extend((port, "http") for port in CLASH_PORTS)
    for port, scheme in dict.fromkeys(endpoints):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.35):
                return port, scheme
        except OSError:
            continue
    return None


def select_chat2api_proxy(
    configured: str,
    endpoint_finder=find_local_clash_endpoint,
) -> tuple[str, str]:
    """选择 Chat2API 使用的单层代理入口，优先复用当前 Clash。"""
    configured = configured.strip()
    if configured:
        return configured, "chat2api 使用已配置的 ClipProxy 固定出口"
    endpoint = endpoint_finder()
    if endpoint is None:
        return "", "未配置出站代理，chat2api 使用直连"
    port, scheme = endpoint
    local_proxy = f"{scheme}://127.0.0.1:{port}"
    return local_proxy, f"chat2api 使用本机 Clash {scheme.upper()} {port}（跟随 Clash 当前节点）"


def find_port_owner(port: int) -> int | None:
    """读取本机 TCP 监听端口的 PID；查询失败时返回 None。"""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return None
    suffix = f":{port}"
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[0].upper() == "TCP" and fields[1].endswith(suffix) and fields[3].upper() == "LISTENING":
            try:
                return int(fields[4])
            except ValueError:
                return None
    return None


def get_process_command_line(pid: int) -> str:
    """读取指定 PID 的命令行；失败时返回空字符串。"""
    query = f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}').CommandLine"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", query],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return ""
    return result.stdout.strip()


def is_owned_bridge_process(pid: int, command_line: str, runtime_dir: str | Path) -> bool:
    """仅识别命令行明确使用本项目中转配置的 Mihomo 进程。"""
    if pid <= 0 or "mihomo" not in command_line.lower():
        return False
    runtime = str(Path(runtime_dir).resolve()).replace("\\", "/").rstrip("/").lower()
    command = command_line.replace("\\", "/").lower()
    return f"{runtime}/proxy-bridge.yaml" in command


def terminate_process_tree(pid: int) -> None:
    """结束已确认归属本项目的 Windows 进程树。"""
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class ProxyBridge:
    """管理只供 chat2api 使用的 Mihomo 链式代理进程。"""

    def __init__(
        self,
        proxy_url: str,
        *,
        executable: str | Path | None = None,
        runtime_dir: str | Path = BRIDGE_RUNTIME_DIR,
        listen_port: int = BRIDGE_PORT,
    ) -> None:
        self.proxy_url = proxy_url.strip()
        self.executable = Path(executable) if executable else None
        self.runtime_dir = Path(runtime_dir).resolve()
        self.listen_port = listen_port
        self.process: subprocess.Popen[bytes] | None = None

    def describe(self) -> str:
        return mask_proxy_url(self.proxy_url)

    def start(self) -> tuple[str, str]:
        """启动链式实例；没有本机 Clash 时保留直连 ClipProxy。"""
        fields = parse_proxy_url(self.proxy_url)
        if not fields["host"] or not fields["port"]:
            raise ValueError("ClipProxy 代理地址无效")
        upstream_endpoint = find_local_clash_endpoint()
        executable = self.executable or find_mihomo_executable()
        if upstream_endpoint is None or executable is None:
            return self.proxy_url, "未找到可用本机 Clash/Mihomo，chat2api 将直接使用已配置 ClipProxy"
        upstream_port, upstream_scheme = upstream_endpoint
        if self._port_is_open():
            owner = find_port_owner(self.listen_port)
            command_line = get_process_command_line(owner) if owner else ""
            if owner and is_owned_bridge_process(owner, command_line, self.runtime_dir):
                terminate_process_tree(owner)
                if not self._wait_for_port_closed():
                    raise RuntimeError(f"项目专用代理端口 {self.listen_port} 的旧中转未能退出，请手动关闭后重试")
            else:
                raise RuntimeError(f"项目专用代理端口 {self.listen_port} 已被其他进程占用，请确认后重试")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        config = build_mihomo_config(self.proxy_url, upstream_port, self.listen_port, upstream_scheme)
        config_path = self.runtime_dir / "proxy-bridge.yaml"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [str(executable), "-f", str(config_path)],
            cwd=self.runtime_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        if not self._wait_for_port():
            self.stop()
            raise RuntimeError("项目专用代理中转启动超时，请确认 Clash 正在运行且端口未被占用")
        return f"http://127.0.0.1:{self.listen_port}", f"已启动项目专用代理中转（ClipProxy {self.describe()} 经本机 Clash {upstream_scheme.upper()} {upstream_port}）"

    def _wait_for_port(self, timeout: float = 8.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process and self.process.poll() is not None:
                return False
            try:
                with socket.create_connection(("127.0.0.1", self.listen_port), timeout=0.35):
                    return True
            except OSError:
                time.sleep(0.2)
        return False

    def _port_is_open(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.listen_port), timeout=0.2):
                return True
        except OSError:
            return False

    def _wait_for_port_closed(self, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._port_is_open():
                return True
            time.sleep(0.1)
        return False

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        config_path = self.runtime_dir / "proxy-bridge.yaml"
        try:
            config_path.unlink()
        except FileNotFoundError:
            pass


class ProxyWorkbench(tk.Toplevel):
    """独立的出站代理配置与出口检查工作台。"""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("网络代理工作台")
        self.geometry("680x560")
        self.minsize(620, 500)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.scheme_var = tk.StringVar(value="http")
        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.status_var = tk.StringVar(value="尚未检测")
        self.endpoint_var = tk.StringVar(value="未配置")
        self.runtime_var = tk.StringVar(value="启动时自动选择")
        self.ip_var = tk.StringVar(value="未检测")
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        pad = {"padx": 22, "pady": 8}
        header = ttk.Frame(self)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="网络代理工作台", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(header, text="为 ChatGPT 网关配置固定 ISP 代理并验证公网出口", foreground="#52606d").pack(anchor="w", pady=(3, 0))

        state = ttk.LabelFrame(self, text="当前链路")
        state.pack(fill="x", **pad)
        for row, (label, variable) in enumerate((("代理端点", self.endpoint_var), ("chat2api 中转", self.runtime_var), ("出口 IP", self.ip_var), ("检测状态", self.status_var))):
            ttk.Label(state, text=label, width=14).grid(row=row, column=0, sticky="w", padx=16, pady=6)
            ttk.Label(state, textvariable=variable, font=("Microsoft YaHei UI", 10, "bold")).grid(row=row, column=1, sticky="w", padx=10, pady=6)

        form = ttk.LabelFrame(self, text="代理接入")
        form.pack(fill="x", **pad)
        ttk.Label(form, text="协议", width=14).grid(row=0, column=0, sticky="w", padx=16, pady=7)
        ttk.Combobox(form, textvariable=self.scheme_var, values=("http", "https", "socks5", "socks5h"), state="readonly", width=14).grid(row=0, column=1, sticky="w", padx=10, pady=7)
        for row, label, variable in ((1, "代理地址", self.host_var), (2, "端口", self.port_var), (3, "用户名（可选）", self.username_var), (4, "密码（可选）", self.password_var)):
            ttk.Label(form, text=label, width=14).grid(row=row, column=0, sticky="w", padx=16, pady=7)
            entry = ttk.Entry(form, textvariable=variable, show="*" if row == 4 else "")
            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=7)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="支持 ClipProxy 提供的 HTTP/HTTPS/SOCKS5 代理；凭据只保存在本机 .env", foreground="#52606d").grid(row=5, column=1, sticky="w", padx=10, pady=(0, 9))

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="保存代理", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="测试出口 IP", command=self.test).pack(side="left", padx=4)
        ttk.Button(actions, text="清除代理", command=self.clear).pack(side="left", padx=4)

        self.log_text = tk.Text(self, height=6, state="disabled", wrap="word", bg="#fbfcfd", relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=22, pady=(0, 16))

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _load_config(self) -> None:
        fields = parse_proxy_url(read_env().get("PROXY_URL", ""))
        for variable, key in ((self.scheme_var, "scheme"), (self.host_var, "host"), (self.port_var, "port"), (self.username_var, "username"), (self.password_var, "password")):
            variable.set(fields[key])
        self._refresh_endpoint()
        self._log("已读取代理配置。")

    def _refresh_endpoint(self) -> str:
        value = build_proxy_url(self.scheme_var.get(), self.host_var.get(), self.port_var.get(), self.username_var.get(), self.password_var.get())
        self.endpoint_var.set(mask_proxy_url(value))
        return value

    def save(self) -> None:
        value = self._refresh_endpoint()
        if not value:
            messagebox.showwarning("配置不完整", "请填写有效的代理地址和 1-65535 端口，或点击“清除代理”关闭代理。", parent=self)
            return
        save_env({"PROXY_URL": value})
        self._log(f"代理配置已保存：{mask_proxy_url(value)}。重启网关后生效。")
        self.status_var.set("已保存，待重启生效")

    def clear(self) -> None:
        save_env({"PROXY_URL": ""})
        self.host_var.set("")
        self.port_var.set("")
        self.username_var.set("")
        self.password_var.set("")
        self._refresh_endpoint()
        self.status_var.set("已关闭代理，待重启生效")
        self._log("已清除 PROXY_URL；重启网关后将恢复直连。")

    def test(self) -> None:
        value = self._refresh_endpoint()
        if not value:
            messagebox.showwarning("代理地址无效", "请填写有效的代理地址和 1-65535 端口。", parent=self)
            return
        self.status_var.set("检测中...")
        self._log(f"正在通过 {mask_proxy_url(value)} 检测公网出口...")

        def check() -> None:
            relay: ClipProxyRelay | None = None
            try:
                endpoint = find_local_clash_endpoint()
                if endpoint:
                    relay = ClipProxyRelay(value, endpoint[0], endpoint[1], listen_port=BRIDGE_PORT)
                    selected, routing_message = relay.start()
                else:
                    selected, routing_message = value, "未找到可用本机 Clash，直接使用已配置的 ClipProxy 固定出口"
                ip = probe_proxy_ip(selected)
                self.after(0, lambda: (self.runtime_var.set(f"临时测试 {selected}"), self.ip_var.set(ip), self.status_var.set("测试成功"), self._log(routing_message), self._log(f"代理出口 IP：{ip}")))
            except Exception as exc:
                self.after(0, lambda error=exc: (self.status_var.set("测试失败"), self._log(f"代理测试失败：{format_connection_error(error, (value,))}")))
            finally:
                if relay:
                    relay.stop()

        threading.Thread(target=check, daemon=True).start()


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI 创意工作台启动控制台")
        self.geometry("760x590")
        self.minsize(680, 520)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.gateway_process: subprocess.Popen[bytes] | None = None
        self.web_process: subprocess.Popen[bytes] | None = None
        self.proxy_bridge: ProxyBridge | None = None
        self._lifecycle_lock = threading.Lock()
        self._closing = False
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
        ttk.Button(header, text="网络代理工作台", command=self.open_proxy_workbench).pack(anchor="e", pady=(6, 0))

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

    def open_proxy_workbench(self) -> None:
        """打开独立代理配置窗口，避免与登录凭据混在一起。"""
        ProxyWorkbench(self)

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
        env.update({"PYTHONPATH": str(ROOT / "src"), "CREATIVE_STUDIO_HOST": WEB_BIND_HOST, "CREATIVE_STUDIO_PORT": "8775", "PORT": "8780", "HOST": "127.0.0.1", "WEB_ERP_AI_PROVIDER": "chatgpt-web", "WEB_ERP_AI_API_URL": f"{GATEWAY_URL}/v1/chat/completions", "WEB_ERP_AI_API_KEY": "local-chatgpt-gateway", "WEB_ERP_AI_MODEL": "gpt-5-6-mini", "WEB_ERP_AI_PROMPT_VERSION": "v5", "WEB_ERP_AI_PROMPT_PATH": str(ROOT / "config" / "ai_creative_prompt_v5.txt"), "WEB_ERP_AI_VISUAL_PROMPT_PATH": str(ROOT / "config" / "ai_visual_creative_prompt_v2.txt"), "WEB_ERP_AI_VISUAL_PROMPT_VERSION": "visual-v2.3", "WEB_ERP_AI_GAME_INFO_PATH": str(ROOT / "config" / "ai_creative_game_info_v2.json"), "WEB_ERP_AI_TIMEOUT_SECONDS": "300", "WEB_ERP_AI_CONTROL_TOKEN": read_env().get("CHATGPT_CONTROL_TOKEN", "")})
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
            proxy_message = self._prepare_proxy_environment(env)
            if self._closing:
                if self.proxy_bridge:
                    self.proxy_bridge.stop()
                    self.proxy_bridge = None
                return
            self.after(0, lambda message=proxy_message: self._log(message))
            with self._lifecycle_lock:
                if self._closing:
                    return
                gateway = self.gateway_process
                web = self.web_process
                if gateway is None or gateway.poll() is not None:
                    gateway = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "main.py"], cwd=ROOT / "chat2api", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
                    self.gateway_process = gateway
                if self._closing:
                    _terminate_process(gateway)
                    self.gateway_process = None
                    return
                if web is None or web.poll() is not None:
                    web = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "creative_studio.app"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
                    self.web_process = web
                if self._closing:
                    _terminate_process(web)
                    _terminate_process(gateway)
                    self.web_process = None
                    self.gateway_process = None
                    return
            self.after(0, lambda: self._log("服务已启动，正在等待网页就绪。"))
            if cookie and not token:
                self.after(1400, lambda: threading.Thread(target=self._renew_from_cookie, daemon=True).start())
            self.after(1800, lambda: webbrowser.open(WEB_URL))
        except OSError as exc:
            self.proxy_bridge.stop() if self.proxy_bridge else None
            self.proxy_bridge = None
            self.after(0, lambda error=exc: (self._set_running(False), self._log(f"启动失败：{error}"), messagebox.showerror("启动失败", "无法启动本地服务，请确认 .venv 已准备完成。")))
        except (RuntimeError, ValueError) as exc:
            self.proxy_bridge.stop() if self.proxy_bridge else None
            self.proxy_bridge = None
            self.after(0, lambda error=exc: (self._set_running(False), self._log(f"启动失败：{error}"), messagebox.showerror("代理启动失败", str(error))))

    def _prepare_proxy_environment(self, env: dict[str, str]) -> str:
        """为网关建立固定出口转发，令 ClipProxy 经当前 Clash 出站。"""
        proxy_url = read_env().get("PROXY_URL", "").strip()
        if not proxy_url:
            env.pop("PROXY_URL", None)
            self.proxy_bridge = None
            return "未配置出站代理，chat2api 使用直连"
        endpoint = find_local_clash_endpoint()
        if endpoint is None:
            env["PROXY_URL"] = proxy_url
            self.proxy_bridge = None
            return "未找到可用本机 Clash，chat2api 直接使用已配置的 ClipProxy 固定出口"
        relay = ClipProxyRelay(proxy_url, endpoint[0], endpoint[1], listen_port=BRIDGE_PORT)
        selected_proxy, message = relay.start()
        env["PROXY_URL"] = selected_proxy
        self.proxy_bridge = relay
        return message

    def stop_services(self) -> None:
        with self._lifecycle_lock:
            for process in (self.web_process, self.gateway_process):
                if process:
                    _terminate_process(process)
            if self.proxy_bridge:
                self.proxy_bridge.stop()
            self.proxy_bridge = None
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
                # 若 8780 已有健康网关，直接复用，避免重复启动导致控制令牌不一致。
                gateway_ready = False
                try:
                    with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=1) as response:
                        gateway_ready = response.status == 200
                except OSError:
                    gateway_ready = False
                if not gateway_ready and (not self.gateway_process or self.gateway_process.poll() is not None):
                    gateway_env = self._environment()
                    proxy_message = self._prepare_proxy_environment(gateway_env)
                    self.after(0, lambda message=proxy_message: self._log(message))
                    self.gateway_process = subprocess.Popen(
                        [str(ROOT / ".venv" / "Scripts" / "python.exe"), "main.py"],
                        cwd=ROOT / "chat2api", env=gateway_env,
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
                refreshed_token = False
                if cookie and should_refresh_session(data):
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
                    refreshed_token = True
                    self.after(0, lambda: self.token_var.set("已配置（点击编辑）"))
                # /health 只能证明本地网关有 Token；/v1/models 的 detected 标记才证明上游接受它。
                with urllib.request.urlopen(f"{GATEWAY_URL}/v1/models", timeout=8) as response:
                    models_data = json.loads(response.read().decode("utf-8"))
                if should_refresh_from_cookie(models_data, bool(cookie)) and not refreshed_token:
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
                    refreshed_token = True
                    self.after(0, lambda: self.token_var.set("已配置（点击编辑）"))
                    with urllib.request.urlopen(f"{GATEWAY_URL}/v1/models", timeout=8) as response:
                        models_data = json.loads(response.read().decode("utf-8"))
                if not gateway_upstream_verified(models_data):
                    detail = str(models_data.get("error") or "上游会话未通过验证")
                    raise RuntimeError(f"AI 网关已启动，但 {detail}")
                with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=8) as response:
                    data = json.loads(response.read().decode("utf-8"))
                text = "已连接，Access Token 已自动填入" if refreshed_token else "已连接，已通过上游验证"
                expiry = data.get("seconds_to_expire")
                if expiry is None:
                    expiry_text = "未返回"
                elif int(expiry) <= 0:
                    expiry_text = "已过期"
                elif int(expiry) < 86400:
                    expiry_text = f"不足 1 天（约 {max(1, int(expiry / 3600))} 小时）"
                else:
                    expiry_text = f"约 {int(expiry / 86400)} 天后"
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read(240).decode("utf-8", errors="replace").replace("\n", " ").replace("\r", " ")
                except OSError:
                    pass
                text, expiry_text = "连接失败", "未检测"
                self.after(0, lambda code=exc.code, message=detail[:160]: self._log(f"连接检测失败：HTTP {code} {message}"))
            except (OSError, ValueError, urllib.error.URLError, RuntimeError) as exc:
                text, expiry_text = "连接失败", "未检测"
                detail = format_connection_error(exc, (cookie, self.secret_values.get("token", "")))
                self.after(0, lambda detail=detail: self._log(f"连接检测失败：{detail}"))
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
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(240).decode("utf-8", errors="replace").replace("\n", " ").replace("\r", " ")
            except OSError:
                pass
            self.after(0, lambda code=exc.code, message=detail[:160]: (self.connection_var.set("Cookie 换取失败"), self._log(f"Cookie 自动换取 Token 失败：HTTP {code} {message}")))
        except Exception as exc:
            error_type = type(exc).__name__
            self.after(0, lambda error_type=error_type: (self.connection_var.set("Cookie 换取失败"), self._log(f"Cookie 自动换取 Token 失败：{error_type}")))

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
        self._closing = True
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
