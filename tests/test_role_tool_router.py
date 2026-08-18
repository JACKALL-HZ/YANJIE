from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


class RecordingMcp:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def call(self, tool_name: str, arguments: dict) -> str:
        self.calls.append((tool_name, arguments))
        if tool_name == "search_knowledge":
            return "【决策知识库参考】\n1. [测试资料] 角色化检索结果"
        if tool_name == "assess_execution_capacity":
            return "执行能力评估：每周可投入时间有限，应拆分目标。"
        if tool_name == "run_risk_stress_test":
            return "压力测试：现金储备不足以承受连续高投入。"
        raise AssertionError(f"unexpected tool: {tool_name}")


def test_role_tool_router_uses_allowlisted_tools_and_role_specific_queries():
    from app.agents.tool_router import RoleToolRouter

    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    mcp = RecordingMcp()
    evidence = RoleToolRouter(mcp_client=mcp).build_all(
        state,
        decision_brief="请明星代言，加大营销预算",
        profile_summary="可支配资产50万元，每周可投入40小时。",
    )

    assert {agent_id for agent_id in evidence} == {
        "market", "environment", "personal", "risk"
    }
    assert [name for name, _ in mcp.calls] == [
        "search_knowledge",
        "search_knowledge",
        "search_knowledge",
        "assess_execution_capacity",
        "search_knowledge",
        "run_risk_stress_test",
    ]
    assert "需求、竞争" in mcp.calls[0][1]["query"]
    assert "政策、规则" in mcp.calls[1][1]["query"]
    assert evidence["market"][0].sources == ["测试资料"]
    assert evidence["personal"][0].status == "hit"
    assert evidence["personal"][1].status == "local"
    assert evidence["risk"][1].tool_name == "run_risk_stress_test"


def test_role_tool_router_attempts_rag_for_all_four_roles():
    from app.agents.tool_router import RoleToolRouter

    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    mcp = RecordingMcp()

    evidence = RoleToolRouter(mcp_client=mcp).build_all(
        state,
        decision_brief="先验证产品差异化，再决定是否追加投入。",
        profile_summary="可投入时间有限，需要保留现金缓冲。",
    )

    rag_calls = [arguments for name, arguments in mcp.calls if name == "search_knowledge"]

    assert len(rag_calls) == 4
    assert len({call["query"] for call in rag_calls}) == 4
    assert evidence["personal"][0].tool_name == "search_knowledge"
    assert evidence["personal"][0].status == "hit"
    assert evidence["risk"][0].tool_name == "search_knowledge"
    assert evidence["risk"][0].sources == ["测试资料"]


def test_role_tool_router_marks_unavailable_knowledge_as_error():
    from app.agents.tool_router import RoleToolRouter

    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    mcp = RecordingMcp()
    mcp.call = lambda *_args, **_kwargs: "（知识库暂不可用）"

    evidence = RoleToolRouter(mcp_client=mcp).build_all(state, "测试决策", "")

    assert evidence["market"][0].status == "error"


def test_role_tool_router_does_not_retrieve_when_rag_is_disabled():
    from app.agents.tool_router import RoleToolRouter

    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    mcp = RecordingMcp()

    evidence = RoleToolRouter(mcp_client=mcp, rag_enabled=False).build_all(
        state, "测试决策", ""
    )

    assert all(
        evidence[agent_id][0].status == "disabled"
        for agent_id in ("market", "environment", "personal", "risk")
    )
    assert "search_knowledge" not in [name for name, _arguments in mcp.calls]
