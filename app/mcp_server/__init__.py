"""衍界 MCP Server 包。

对外暴露 FastMCP 实例、工具函数和 MCP 客户端，供测试和引擎使用。
"""

from app.mcp_server.client import McpToolClient
from app.mcp_server.server import mcp, search_knowledge, search_web

__all__ = ["mcp", "search_knowledge", "search_web", "McpToolClient"]
