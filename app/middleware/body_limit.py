"""请求体大小限制中间件 —— 防止超大 payload 导致内存耗尽。

通过检查 Content-Length 请求头实现，超过上限直接拒绝（413）。
默认 1 MB，可通过 BODY_MAX_BYTES 环境变量调整。
"""

import os

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# 默认 1 MB
_DEFAULT_MAX_BYTES = 1 * 1024 * 1024


class BodyLimitMiddleware:
    """拒绝 Content-Length 超过上限的请求。

    环境变量:
        BODY_MAX_BYTES: 最大请求体字节数（默认 1048576 = 1MB），设为 0 禁用
    """

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self._max_bytes = (
            max_bytes
            if max_bytes is not None
            else int(os.getenv("BODY_MAX_BYTES", str(_DEFAULT_MAX_BYTES)))
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        declared_size = headers.get(b"content-length", b"")
        if declared_size.isdigit() and int(declared_size) > self._max_bytes:
            await self._send_too_large(send)
            return

        body_parts: list[bytes] = []
        received_bytes = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            received_bytes += len(chunk)
            if received_bytes > self._max_bytes:
                await self._send_too_large(send)
                return
            body_parts.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(body_parts)
        delivered = False

        async def replay_receive() -> Message:
            nonlocal delivered
            if delivered:
                # Streaming responses (such as SSE) use receive() to observe a
                # real client disconnect after FastAPI has consumed the body.
                return await receive()
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)

    async def _send_too_large(self, send: Send) -> None:
        body = (
            '{"code":"PAYLOAD_TOO_LARGE",'
            f'"message":"request body exceeds {self._max_bytes} bytes"}}'
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
