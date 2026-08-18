"""速率限制中间件 —— 基于滑动窗口的内存限流。

生产期应替换为 Redis 后端（fastapi-limiter + Redis）。
当前 MVP 阶段：内存字典，按 IP 限流，进程重启后计数清零。
"""

import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def _trusted_proxy_ips() -> set[str]:
    return {
        ip.strip()
        for ip in os.getenv("TRUSTED_PROXY_IPS", "").split(",")
        if ip.strip()
    }


def _client_ip(request: Request) -> str:
    """获取客户端 IP（优先 X-Forwarded-For）。"""
    direct_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded and direct_ip in _trusted_proxy_ips():
        return forwarded.split(",")[0].strip()
    return direct_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 IP 的滑动窗口限流。

    环境变量:
        RATE_LIMIT_REQUESTS: 窗口内最大请求数（默认 60）
        RATE_LIMIT_WINDOW_SECONDS: 窗口秒数（默认 60）
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._max_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
        self._window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        # {ip: [timestamp, ...]}
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # 禁用限流（RATE_LIMIT_REQUESTS=0）
        if self._max_requests <= 0:
            return await call_next(request)

        ip = _client_ip(request)
        now = time.time()
        cutoff = now - self._window

        # 清理过期记录
        window_hits = [t for t in self._hits.get(ip, []) if t > cutoff]
        self._hits[ip] = window_hits

        if len(window_hits) >= self._max_requests:
            retry_after = int(self._window - (now - window_hits[0]))
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "message": f"请求过于频繁，请 {retry_after}s 后重试",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        self._hits[ip].append(now)
        return await call_next(request)
