"""安全响应头中间件 —— 为所有响应添加基础安全头。

生产环境建议在反向代理层（Nginx/Caddy）配置。
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# 安全头配置
_SECURITY_HEADERS: dict[str, str] = {
    # 禁止 MIME 类型嗅探
    "X-Content-Type-Options": "nosniff",
    # 禁止被嵌入 iframe（防点击劫持）
    "X-Frame-Options": "DENY",
    # 启用浏览器 XSS 过滤器
    "X-XSS-Protection": "1; mode=block",
    # 限制 Referrer 信息传递
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # 限制浏览器功能权限
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), "
        "interest-cohort=()"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有 HTTP 响应注入安全头。"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value
        return response
