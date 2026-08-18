"""Synchronous facade for official MCP stdio and Streamable HTTP transports."""

import asyncio
import os
import threading
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


McpTransport = Literal["stdio", "http"]
_SUPPORTED_TRANSPORTS = frozenset({"stdio", "http"})
_SERVER_MODULE = "app.mcp_server.server"


@dataclass(frozen=True)
class McpToolResult:
    """A tool outcome that keeps empty data separate from failed execution."""

    status: Literal["ok", "empty", "error"]
    content: str = ""
    error_code: str | None = None


class McpToolClient:
    """Call allowlisted MCP tools through an official transport session.

    The agent runtime is synchronous, while MCP transports are asynchronous.
    A dedicated worker loop owns the protocol session and provides a bounded
    synchronous facade without importing tool functions directly.
    """

    def __init__(
        self,
        mode: McpTransport = "stdio",
        *,
        http_url: str | None = None,
        http_token: str = "",
        stdio_command: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if mode not in _SUPPORTED_TRANSPORTS:
            raise ValueError(
                "Unsupported MCP transport; use 'stdio' or 'http'."
            )
        if mode == "http" and not http_url:
            raise ValueError("MCP HTTP transport requires http_url.")
        if not 1 <= timeout_seconds <= 120:
            raise ValueError("MCP timeout must be between 1 and 120 seconds.")

        self._mode = mode
        self._http_url = http_url or ""
        self._http_token = http_token
        self._stdio_command = stdio_command or os.sys.executable
        self._timeout_seconds = timeout_seconds
        self._repo_root = Path(__file__).resolve().parents[2]
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown: asyncio.Event | None = None
        self._session: ClientSession | None = None
        self._tool_names: set[str] = set()
        self._startup_error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run_worker,
            name="yanjie-mcp-client",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(timeout_seconds):
            self.close()
            raise RuntimeError("MCP client initialization timed out.")
        if self._startup_error is not None:
            self.close()
            raise RuntimeError("MCP client initialization failed.") from self._startup_error

    def __enter__(self) -> "McpToolClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _run_worker(self) -> None:
        asyncio.run(self._run_session())

    async def _run_session(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._shutdown = asyncio.Event()
        try:
            if self._mode == "stdio":
                environment = dict(os.environ)
                environment["MCP_SERVER_TRANSPORT"] = "stdio"
                params = StdioServerParameters(
                    command=self._stdio_command,
                    args=["-m", _SERVER_MODULE],
                    env=environment,
                    cwd=str(self._repo_root),
                )
                async with stdio_client(params) as (read_stream, write_stream):
                    await self._serve(read_stream, write_stream)
            else:
                headers = (
                    {"Authorization": f"Bearer {self._http_token}"}
                    if self._http_token
                    else None
                )
                timeout = httpx.Timeout(self._timeout_seconds)
                async with create_mcp_http_client(headers=headers, timeout=timeout) as http_client:
                    async with streamable_http_client(
                        self._http_url,
                        http_client=http_client,
                    ) as (read_stream, write_stream, _):
                        await self._serve(read_stream, write_stream)
        except Exception as exc:
            self._startup_error = exc
        finally:
            self._session = None
            self._ready.set()

    async def _serve(self, read_stream: Any, write_stream: Any) -> None:
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=self._timeout_seconds),
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            self._tool_names = {tool.name for tool in tools.tools}
            self._session = session
            self._ready.set()
            await self._shutdown.wait()

    def list_tools(self) -> list[str]:
        return sorted(self._tool_names)

    def call(self, tool_name: str, arguments: dict[str, Any]) -> McpToolResult:
        """Call one discovered MCP tool without exposing provider exceptions."""
        if tool_name not in self._tool_names:
            return McpToolResult(status="error", error_code="UNKNOWN_TOOL")
        if self._loop is None or self._session is None or self._closed.is_set():
            return McpToolResult(status="error", error_code="MCP_UNAVAILABLE")

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._call_tool(tool_name, arguments),
                self._loop,
            )
            return future.result(timeout=self._timeout_seconds)
        except TimeoutError:
            return McpToolResult(status="error", error_code="TOOL_TIMEOUT")
        except Exception:
            return McpToolResult(status="error", error_code="TOOL_EXECUTION_FAILED")

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> McpToolResult:
        if self._session is None:
            return McpToolResult(status="error", error_code="MCP_UNAVAILABLE")

        result = await self._session.call_tool(tool_name, arguments)
        if getattr(result, "isError", False):
            return McpToolResult(status="error", error_code="TOOL_EXECUTION_FAILED")

        content = "\n".join(
            item.text
            for item in result.content
            if hasattr(item, "text") and isinstance(item.text, str)
        )
        return McpToolResult(
            status="ok" if content.strip() else "empty",
            content=content,
        )

    def close(self) -> None:
        """Close the session and wait briefly for the transport to exit."""
        if self._closed.is_set():
            return
        self._closed.set()
        if self._loop is not None and self._shutdown is not None:
            self._loop.call_soon_threadsafe(self._shutdown.set)
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=self._timeout_seconds + 1)
