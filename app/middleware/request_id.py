"""Request-ID 中间件 —— 为每个请求注入唯一追踪 ID。

从请求头 X-Request-ID 读取（若客户端传入）；否则生成 UUID4。
同时在响应头 X-Request-ID 返回，方便日志关联和问题排查。
"""

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """注入 X-Request-ID 到请求状态和响应头。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
