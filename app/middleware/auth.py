"""API Key 认证中间件 —— 验证 X-API-Key 请求头。

MVP 阶段：简单静态 Key 校验，保护所有 /api/ 端点（/api/health 除外）。
生产期应替换为 JWT/OAuth2。
"""

import os
from fnmatch import fnmatch

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# 无需认证的路径（glob 匹配）
_PUBLIC_PATHS: list[str] = [
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]


def _is_public(path: str) -> bool:
    """判断路径是否为公开端点。"""
    for pattern in _PUBLIC_PATHS:
        if fnmatch(path, pattern):
            return True
    return False


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """验证 X-API-Key 请求头。

    未配置 API_KEY 环境变量时放行所有请求（开发兼容模式）。
    """

    async def dispatch(self, request: Request, call_next):
        # 公开路径放行
        if _is_public(request.url.path):
            return await call_next(request)

        # 未配置 API Key 时放行（开发兼容）
        expected_key = os.getenv("API_KEY", "").strip()
        if not expected_key:
            return await call_next(request)

        # 验证
        provided = request.headers.get("X-API-Key", "").strip()
        if not provided:
            return JSONResponse(
                status_code=401,
                content={
                    "code": "UNAUTHORIZED",
                    "message": "缺少 X-API-Key 请求头",
                },
            )
        if provided != expected_key:
            return JSONResponse(
                status_code=403,
                content={
                    "code": "FORBIDDEN",
                    "message": "API Key 无效",
                },
            )

        return await call_next(request)
