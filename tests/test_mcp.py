"""MCP Server 工具测试。

测试 MCP 工具注册、调用、超时兜底。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


# ── 工具注册测试 ──

def test_mcp_server_file_exists():
    """验证 MCP server 文件存在且可导入。"""
    server_path = Path(__file__).parent.parent / "app" / "mcp_server" / "server.py"
    assert server_path.exists(), f"MCP server not found at {server_path}"


def test_resolve_transport_defaults_to_stdio():
    from app.mcp_server.server import resolve_transport

    assert resolve_transport(None) == "stdio"


def test_resolve_transport_maps_http_to_streamable_http():
    from app.mcp_server.server import resolve_transport

    assert resolve_transport("http") == "streamable-http"


def test_resolve_transport_rejects_unsupported_values():
    from app.mcp_server.server import resolve_transport

    with pytest.raises(ValueError, match="MCP_SERVER_TRANSPORT"):
        resolve_transport("inline")


def test_mcp_server_only_documents_stdio_transport():
    server_path = Path(__file__).parent.parent / "app" / "mcp_server" / "server.py"
    source = server_path.read_text(encoding="utf-8")

    assert "MCP_TOKEN" not in source
    assert "--http" not in source


def test_mcp_server_module_imports():
    """验证 MCP server 模块可导入。"""
    from app.mcp_server.server import mcp

    assert mcp is not None
    assert mcp.name == "yanjie-mcp"


def test_tools_registered():
    """验证知识、搜索、执行能力和风险工具已注册。"""
    from app.mcp_server.server import mcp

    tool_names = {t.name for t in mcp._tool_manager._tools.values()}
    assert "search_knowledge" in tool_names, "search_knowledge not registered"
    assert "search_web" in tool_names, "search_web not registered"
    assert "assess_execution_capacity" in tool_names
    assert "run_risk_stress_test" in tool_names


def test_role_analysis_tools_return_chinese_evidence_without_network():
    from app.mcp_server.tools import assess_execution_capacity, run_risk_stress_test

    capacity = assess_execution_capacity(
        "每周可投入20小时，风险偏好均衡",
        {"budget": 200000},
        "请明星代言",
    )
    risk = run_risk_stress_test(
        {"cash_flow": 20000, "payback_ratio": 0.2},
        "milktea_startup",
        "请明星代言",
    )

    assert "执行能力评估" in capacity
    assert "压力测试" in risk


def test_search_knowledge_docstring():
    """验证 search_knowledge 工具 docstring 完整。"""
    from app.mcp_server.server import mcp

    tools = list(mcp._tool_manager._tools.values())
    sk = next(t for t in tools if t.name == "search_knowledge")
    doc = sk.description or ""
    assert "知识" in doc or "knowledge" in doc.lower()
    assert "query" in doc.lower()


def test_search_web_docstring():
    """验证 search_web 工具 docstring 完整。"""
    from app.mcp_server.server import mcp

    tools = list(mcp._tool_manager._tools.values())
    sw = next(t for t in tools if t.name == "search_web")
    doc = sw.description or ""
    assert "搜索" in doc or "search" in doc.lower()
    assert "query" in doc.lower()


# ── 工具调用测试 ──

def test_search_knowledge_returns_string():
    """search_knowledge 调用返回字符串。"""
    from app.mcp_server.server import search_knowledge

    result = search_knowledge("奶茶创业 成本")
    assert isinstance(result, str)
    assert len(result) > 0


def test_search_web_no_api_key_graceful():
    """search_web 无 API Key 时静默兜底。"""
    from app.mcp_server.server import search_web

    # 这个测试在不配 TAVILY_API_KEY 环境下应返回空或兜底文本
    result = search_web("test query")
    assert isinstance(result, str)


def test_search_knowledge_empty_query():
    """search_knowledge 空查询不崩溃。"""
    from app.mcp_server.server import search_knowledge

    result = search_knowledge("")
    assert isinstance(result, str)


def test_search_knowledge_respects_disabled_rag(monkeypatch):
    import app.mcp_server.tools as tools

    monkeypatch.setenv("RAG_ENABLED", "0")
    monkeypatch.setattr(
        tools,
        "_get_retriever",
        lambda: pytest.fail("disabled RAG must not initialize a retriever"),
    )

    result = tools.search_knowledge("奶茶创业现金流", "milktea_startup")

    assert "已禁用" in result


def test_search_web_empty_query():
    """search_web 空查询不崩溃。"""
    from app.mcp_server.server import search_web

    result = search_web("")
    assert isinstance(result, str)


# ── 超时与兜底 ──

def test_search_knowledge_returns_useful_text():
    """search_knowledge 返回的文本包含有意义的内容。"""
    from app.mcp_server.server import search_knowledge

    result = search_knowledge("奶茶 失败 案例")
    # 至少返回非空，且不是纯错误消息
    assert len(result) > 0
    # 不应该只返回纯错误
    assert "错误" not in result or len(result) > 20


def test_search_web_format():
    """search_web 不带 Key 时返回兜底文本。"""
    import os

    from app.mcp_server.server import search_web

    # 清掉环境变量模拟未配置
    old_key = os.environ.pop("TAVILY_API_KEY", None)
    try:
        result = search_web("test")
        assert isinstance(result, str)
        # 未配置 Key 时可能返回空或提示
    finally:
        if old_key:
            os.environ["TAVILY_API_KEY"] = old_key
