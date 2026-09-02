"""Small HTTP CONNECT relay for carrying ClipProxy through a local Clash proxy."""

from __future__ import annotations

import select
import socket
import socketserver
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlparse


MAX_HEADER_BYTES = 16 * 1024
SOCKET_TIMEOUT = 15.0


def parse_connect_target(value: str) -> tuple[str, int]:
    """Parse an HTTP CONNECT authority into a hostname and TCP port."""
    value = value.strip()
    if value.startswith("["):
        end = value.find("]")
        if end < 0 or end + 1 >= len(value) or value[end + 1] != ":":
            raise ValueError("CONNECT 目标地址无效")
        host, raw_port = value[1:end], value[end + 2 :]
    else:
        if ":" not in value:
            raise ValueError("CONNECT 目标地址无效")
        host, raw_port = value.rsplit(":", 1)
    if not host or not raw_port.isdigit() or not 1 <= int(raw_port) <= 65535:
        raise ValueError("CONNECT 目标地址无效")
    return host, int(raw_port)


def build_socks5_auth_request(username: str, password: str) -> bytes:
    """Build RFC 1929 username/password authentication payload."""
    user = username.encode("utf-8")
    secret = password.encode("utf-8")
    if not user or len(user) > 255 or len(secret) > 255:
        raise ValueError("ClipProxy 账号或密码长度无效")
    return bytes((1, len(user))) + user + bytes((len(secret),)) + secret


def build_socks5_greeting(username: str, password: str) -> bytes:
    """Build a SOCKS5 method negotiation for an authenticated proxy."""
    return b"\x05\x02\x00\x02" if username or password else b"\x05\x01\x00"


def _read_until(sock: socket.socket, marker: bytes, limit: int = MAX_HEADER_BYTES) -> bytes:
    data = bytearray()
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("上游连接提前关闭")
        data.extend(chunk)
        if len(data) > limit:
            raise ConnectionError("代理响应头过大")
    return bytes(data)


def _read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("代理响应提前结束")
        data.extend(chunk)
    return bytes(data)


def _socks5_connect(sock: socket.socket, host: str, port: int, username: str, password: str) -> None:
    sock.sendall(build_socks5_greeting(username, password))
    greeting = _read_exact(sock, 2)
    if greeting[0] != 5:
        raise ConnectionError("Clash 返回的不是 SOCKS5 响应")
    if greeting[1] == 0xFF:
        raise ConnectionError("Clash 不接受 SOCKS5 无认证连接")
    if greeting[1] == 2:
        sock.sendall(build_socks5_auth_request(username, password))
        auth = _read_exact(sock, 2)
        if auth != b"\x01\x00":
            raise PermissionError("ClipProxy SOCKS5 认证失败")
    elif greeting[1] != 0:
        raise ConnectionError("Clash 返回了不支持的 SOCKS5 认证方式")
    encoded_host = host.encode("idna")
    if len(encoded_host) > 255:
        raise ValueError("CONNECT 主机名过长")
    request = b"\x05\x01\x00\x03" + bytes((len(encoded_host),)) + encoded_host + port.to_bytes(2, "big")
    sock.sendall(request)
    response = _read_exact(sock, 4)
    if response[0] != 5 or response[1] != 0:
        raise ConnectionError(f"SOCKS5 连接目标失败（状态 {response[1] if response[0] == 5 else '未知'}）")
    address_length = 4 if response[3] == 1 else 16 if response[3] == 4 else _read_exact(sock, 1)[0]
    _read_exact(sock, address_length + 2)


class _RelayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        relay: ClipProxyRelay = self.server.relay  # type: ignore[attr-defined]
        client = self.request
        client.settimeout(SOCKET_TIMEOUT)
        try:
            request = _read_until(client, b"\r\n\r\n")
            first_line = request.split(b"\r\n", 1)[0].decode("latin-1")
            method, authority, _ = first_line.split(" ", 2)
            if method.upper() != "CONNECT":
                self._respond(405, "仅支持 HTTPS CONNECT")
                return
            target_host, target_port = parse_connect_target(authority)
            upstream = relay.connect_target(target_host, target_port)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            relay.tunnel(client, upstream)
        except PermissionError as exc:
            self._respond(407, str(exc))
        except (ConnectionError, OSError, ValueError) as exc:
            self._respond(502, str(exc))

    def _respond(self, status: int, message: str) -> None:
        body = message.encode("utf-8", "replace")[:240]
        response = (
            f"HTTP/1.1 {status} Proxy Error\r\nContent-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        ).encode("ascii") + body
        try:
            self.request.sendall(response)
        except OSError:
            pass


class _RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, relay: "ClipProxyRelay", address: tuple[str, int]) -> None:
        self.relay = relay
        super().__init__(address, _RelayHandler)


class ClipProxyRelay:
    """Relay Chat2API CONNECT requests through Clash and ClipProxy."""

    def __init__(
        self,
        proxy_url: str,
        upstream_port: int,
        upstream_scheme: str = "http",
        listen_port: int = 7896,
        listen_host: str = "127.0.0.1",
    ) -> None:
        parsed = urlparse(proxy_url.strip())
        if parsed.scheme.lower() not in {"socks5", "socks5h", "http", "https"} or not parsed.hostname or not parsed.port:
            raise ValueError("ClipProxy 代理地址无效")
        self.proxy_host = parsed.hostname
        self.proxy_port = parsed.port
        self.username = unquote(parsed.username or "")
        self.password = unquote(parsed.password or "")
        self.upstream_port = upstream_port
        self.upstream_scheme = upstream_scheme.lower()
        if self.upstream_scheme not in {"http", "socks5"}:
            raise ValueError("Clash 代理协议无效")
        self.listen_address = (listen_host, listen_port)
        self.server: _RelayServer | None = None
        self.thread: threading.Thread | None = None
        self._connections: set[socket.socket] = set()
        self._connections_lock = threading.Lock()

    def start(self, timeout: float = 8.0) -> tuple[str, str]:
        if self.server is not None:
            return f"http://{self.listen_address[0]}:{self.listen_address[1]}", "项目代理转发已在运行"
        self.server = _RelayServer(self, self.listen_address)
        self.thread = threading.Thread(target=self.server.serve_forever, name="clipproxy-relay", daemon=True)
        self.thread.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(self.listen_address, timeout=0.25):
                    return (
                        f"http://{self.listen_address[0]}:{self.listen_address[1]}",
                        f"已启动固定出口转发（ClipProxy 经 Clash {self.upstream_scheme.upper()} {self.upstream_port}）",
                    )
            except OSError:
                time.sleep(0.05)
        self.stop()
        raise RuntimeError("固定出口转发启动超时")

    def connect_target(self, host: str, port: int) -> socket.socket:
        upstream = socket.create_connection(("127.0.0.1", self.upstream_port), timeout=SOCKET_TIMEOUT)
        upstream.settimeout(SOCKET_TIMEOUT)
        with self._connections_lock:
            self._connections.add(upstream)
        try:
            if self.upstream_scheme == "http":
                request = f"CONNECT {self.proxy_host}:{self.proxy_port} HTTP/1.1\r\nHost: {self.proxy_host}:{self.proxy_port}\r\n\r\n".encode("ascii")
                upstream.sendall(request)
                response = _read_until(upstream, b"\r\n\r\n")
                status_line = response.split(b"\r\n", 1)[0]
                if not status_line.startswith(b"HTTP/1.1 200") and not status_line.startswith(b"HTTP/1.0 200"):
                    raise ConnectionError("Clash 无法建立到 ClipProxy 的 CONNECT 隧道")
            else:
                _socks5_connect(upstream, self.proxy_host, self.proxy_port, "", "")
            _socks5_connect(upstream, host, port, self.username, self.password)
            return upstream
        except Exception:
            with self._connections_lock:
                self._connections.discard(upstream)
            upstream.close()
            raise

    def tunnel(self, client: socket.socket, upstream: socket.socket) -> None:
        with self._connections_lock:
            self._connections.add(client)
        sockets = [client, upstream]
        try:
            client.settimeout(None)
            upstream.settimeout(None)
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 30.0)
                if exceptional or not readable:
                    if not readable:
                        continue
                    break
                for source in readable:
                    data = source.recv(64 * 1024)
                    if not data:
                        return
                    destination = upstream if source is client else client
                    destination.sendall(data)
        finally:
            with self._connections_lock:
                self._connections.discard(client)
                self._connections.discard(upstream)
            try:
                upstream.close()
            except OSError:
                pass

    def stop(self) -> None:
        server, self.server = self.server, None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread, self.thread = self.thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        with self._connections_lock:
            connections, self._connections = self._connections, set()
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
