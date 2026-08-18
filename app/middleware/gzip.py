"""GZip 压缩中间件 —— 对 JSON/HTML/文本响应启用 gzip 压缩。

体量 > 500 字节才压缩，避免小响应加解压开销。
"""

from starlette.middleware.gzip import GZipMiddleware


def build_gzip_middleware() -> tuple[type[GZipMiddleware], dict]:
    """返回 (middleware_class, kwargs) 供 FastAPI add_middleware 使用。"""
    return (
        GZipMiddleware,
        {"minimum_size": 500},
    )
