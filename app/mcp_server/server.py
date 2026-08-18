"""YanJie MCP server for stdio and Streamable HTTP transports.

Run with: python -m app.mcp_server.server

The parent process is responsible for launching this server locally and
controlling access to its standard input/output streams.
"""

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools import assess_execution_capacity as _assess_execution_capacity_fn
from app.mcp_server.tools import run_risk_stress_test as _run_risk_stress_test_fn
from app.mcp_server.tools import search_knowledge as _search_knowledge_fn
from app.mcp_server.tools import search_web as _search_web_fn


mcp = FastMCP(name="yanjie-mcp")


def resolve_transport(raw: str | None) -> Literal["stdio", "streamable-http"]:
    """Map the public transport setting to FastMCP's transport name."""
    transport = (raw or "stdio").strip().lower()
    if transport == "stdio":
        return "stdio"
    if transport == "http":
        return "streamable-http"
    raise ValueError(
        "MCP_SERVER_TRANSPORT must be either 'stdio' or 'http'"
    )


@mcp.tool(
    name="search_knowledge",
    description=(
        "Search the YanJie decision knowledge base for evidence relevant to a "
        "decision. Use query for the user's question and optional scenario_id "
        "to narrow results."
    ),
)
def search_knowledge(query: str, scenario_id: str | None = None) -> str:
    return _search_knowledge_fn(query, scenario_id=scenario_id)


@mcp.tool(
    name="search_web",
    description=(
        "Search current public market information. Use only when fresh "
        "external evidence is needed. query is a natural-language search."
    ),
)
def search_web(query: str) -> str:
    return _search_web_fn(query)


@mcp.tool(
    name="assess_execution_capacity",
    description=(
        "Assess the user's available time, resources, and execution "
        "constraints. profile_summary is text, decision_vars is structured "
        "data, and decision_brief is optional context."
    ),
)
def assess_execution_capacity(
    profile_summary: str,
    decision_vars: dict,
    decision_brief: str = "",
) -> str:
    return _assess_execution_capacity_fn(
        profile_summary, decision_vars, decision_brief
    )


@mcp.tool(
    name="run_risk_stress_test",
    description=(
        "Evaluate downside risk and stop conditions for a scenario. "
        "world_state and scenario_id are required; decision_brief is optional."
    ),
)
def run_risk_stress_test(
    world_state: dict,
    scenario_id: str,
    decision_brief: str = "",
) -> str:
    return _run_risk_stress_test_fn(world_state, scenario_id, decision_brief)


if __name__ == "__main__":
    mcp.run(transport=resolve_transport(os.getenv("MCP_SERVER_TRANSPORT")))
