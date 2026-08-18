from dataclasses import replace
from unittest.mock import patch

import pytest

from app.agents.tool_router import RoleToolRouter
from app.core.config import get_settings
from app.engine.engine import SimulationEngine
from app.engine.state import make_initial_state
from app.mcp_server.client import McpToolClient, McpToolResult
from app.scenarios.loader import ScenarioLoader
from app.services.simulation_service import SimulationService


def test_settings_reject_inline_mcp_transport(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "inline")

    with pytest.raises(ValueError, match="MCP_TRANSPORT"):
        get_settings()


def test_settings_require_http_url_when_mcp_is_enabled(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "1")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_HTTP_URL", raising=False)

    with pytest.raises(ValueError, match="MCP_HTTP_URL"):
        get_settings()


def test_unsupported_mcp_transport_fails_fast():
    with pytest.raises(ValueError, match="Unsupported MCP transport"):
        McpToolClient(mode="inline")


def test_http_transport_requires_an_endpoint():
    with pytest.raises(ValueError, match="http_url"):
        McpToolClient(mode="http")


def test_stdio_client_lists_registered_mcp_tools():
    with McpToolClient(mode="stdio", timeout_seconds=10) as client:
        assert {
            "search_knowledge",
            "search_web",
            "assess_execution_capacity",
            "run_risk_stress_test",
        } <= set(client.list_tools())


def test_stdio_unknown_tool_returns_error_result():
    with McpToolClient(mode="stdio", timeout_seconds=10) as client:
        result = client.call("missing", {})

    assert result.status == "error"
    assert result.error_code == "UNKNOWN_TOOL"
    assert result.content == ""


def test_stdio_client_calls_non_network_tool():
    with McpToolClient(mode="stdio", timeout_seconds=10) as client:
        result = client.call(
            "assess_execution_capacity",
            {
                "profile_summary": "每周可投入 20 小时，保留现金缓冲。",
                "decision_vars": {"budget": 200000},
            },
        )

    assert result.status == "ok"
    assert result.content


def test_engine_constructs_mcp_client_from_transport_settings():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    settings = replace(
        get_settings(),
        llm_use_stub=False,
        mcp_enabled=True,
        mcp_transport="stdio",
        mcp_http_url="",
        mcp_http_token="",
        mcp_timeout_seconds=9,
    )

    with patch("app.engine.engine.McpToolClient") as client_factory:
        SimulationEngine(source, use_stub=False, settings=settings)

    client_factory.assert_called_once_with(
        mode="stdio",
        http_url="",
        http_token="",
        stdio_command=settings.mcp_stdio_command,
        timeout_seconds=9,
    )


def test_simulation_service_closes_engine_after_a_run():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    service = SimulationService(get_settings())

    with patch("app.services.simulation_service.SimulationEngine") as engine_factory:
        engine = engine_factory.return_value
        expected = object()
        engine.run.return_value = expected

        assert service.run(source, {"budget": 200000}) is expected

    engine.close.assert_called_once_with()


def test_role_router_exposes_typed_mcp_failure_as_error_evidence():
    class FailingMcp:
        def call(self, _tool_name, _arguments):
            return McpToolResult(status="error", error_code="TOOL_EXECUTION_FAILED")

    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})

    evidence = RoleToolRouter(mcp_client=FailingMcp()).build_all(state, "test", "")

    assert evidence["market"][0].status == "error"
