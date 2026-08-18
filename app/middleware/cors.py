"""CORS 中间件 —— 从环境变量 ALLOWED_ORIGINS 读取允许的源。

开发期默认允许所有源（"*"），生产期必须显式配置逗号分隔的域名列表。

注意：allow_credentials=True 与 allow_origins=["*"] 不兼容（浏览器 CORS 规范禁止）。
当 origins 为通配符时自动禁用 credentials，生产期配置具体域名后才启用。
"""

import os

from starlette.middleware.cors import CORSMiddleware

# 允许的 HTTP 方法（最小化原则）
_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
# 允许的请求头
_ALLOWED_HEADERS = [
    "Content-Type",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
    "Accept",
    "Accept-Language",
]
_LOCAL_DEVELOPMENT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_DEVELOPMENT_ENVS = {"development", "dev", "test"}


def build_cors_middleware() -> tuple[type[CORSMiddleware], dict]:
    """返回 (middleware_class, kwargs) 供 FastAPI add_middleware 使用。"""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    origins_raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    if not origins:
        origins = list(_LOCAL_DEVELOPMENT_ORIGINS)
    if "*" in origins and app_env not in _DEVELOPMENT_ENVS:
        raise ValueError(
            "ALLOWED_ORIGINS cannot contain '*' outside local development"
        )

    # 通配符 origin 与 credentials 不兼容
    is_wildcard = origins == ["*"]
    allow_credentials = not is_wildcard

    return (
        CORSMiddleware,
        {
            "allow_origins": origins,
            "allow_credentials": allow_credentials,
            "allow_methods": _ALLOWED_METHODS,
            "allow_headers": _ALLOWED_HEADERS,
        },
    )
