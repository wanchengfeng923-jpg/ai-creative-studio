"""Injectable HTTP health checks for local and public deployment endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from .models import CheckLevel, CheckResult


HttpOpener = Callable[[str, float], Any]


class HealthChecker:
    """Run bounded, content-agnostic health checks."""

    def __init__(
        self,
        *,
        web_url: str,
        gateway_url: str,
        public_url: str | None = None,
        opener: HttpOpener | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.web_url = web_url
        self.gateway_url = gateway_url
        self.public_url = public_url
        self.timeout = timeout
        self._opener = opener or _open_url

    def check_local_web(self) -> CheckResult:
        return self._check_url("web_local", "本机 Web", self.web_url)

    def check_gateway(self) -> CheckResult:
        return self._check_url("gateway_local", "本机 AI 网关", self.gateway_url)

    def check_public_web(self) -> CheckResult:
        if not self.public_url:
            return CheckResult(
                check_id="web_public",
                level=CheckLevel.WARNING,
                summary="未配置公网健康地址",
                evidence={},
                recommendation="配置公网健康地址后再执行公网检查",
            )
        return self._check_url("web_public", "公网 Web", self.public_url)

    def check_all(self) -> list[CheckResult]:
        """Check local Web, gateway, and configured public Web in that order."""
        results = [self.check_local_web(), self.check_gateway()]
        if self.public_url is not None:
            results.append(self.check_public_web())
        return results

    def _check_url(self, check_id: str, label: str, url: str) -> CheckResult:
        try:
            response = self._opener(url, self.timeout)
            status = _response_status(response)
            if 200 <= status < 300:
                return CheckResult(
                    check_id=check_id,
                    level=CheckLevel.PASS,
                    summary=f"{label}健康检查通过",
                    evidence={"url": _safe_url_summary(url), "status": status},
                )
            return CheckResult(
                check_id=check_id,
                level=CheckLevel.FAIL,
                summary=f"{label}返回 HTTP {status}",
                evidence={"url": _safe_url_summary(url), "status": status},
                recommendation="检查对应服务日志和监听状态",
            )
        except Exception as error:
            return CheckResult(
                check_id=check_id,
                level=CheckLevel.FAIL,
                summary=f"{label}连接失败：{type(error).__name__}",
                evidence={"url": _safe_url_summary(url), "error_type": type(error).__name__},
                recommendation="检查服务是否启动以及端口是否符合边界",
            )


def _open_url(url: str, timeout: float) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    return urlopen(request, timeout=timeout)


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    return int(status)


def _safe_url_summary(url: str) -> str:
    # URLs supplied by the panel are fixed endpoints; never include query content.
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.hostname or ''}:{parsed.port or ''}{parsed.path}"
