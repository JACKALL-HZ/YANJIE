from app.agents.inner_graph import AgentCoordinator, build_agents
from app.engine.models import AgentAction
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


def test_agent_output_guard_replaces_internal_metrics_and_english_jargon():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))
    contexts = coordinator.observe(state, latest_decision="请明星代言")

    action = AgentAction(
        agent_id="risk",
        action_id="risk.contain",
        reason=(
            "cashflow is limited and paybackratio is low; "
            "use insure to control irreversibledownside."
        ),
        confidence=0.92,
    )

    guarded = coordinator.validate([action], contexts)[0]

    assert "明星代言" in guarded.reason
    assert "最坏损失" in guarded.reason
    assert "cashflow" not in guarded.reason
    assert "paybackratio" not in guarded.reason
    assert "irreversibledownside" not in guarded.reason
    assert guarded.confidence < 0.92


def test_agent_action_keeps_personalized_advice_fields_optional():
    legacy = AgentAction(
        agent_id="personal",
        action_id="personal.stabilize",
        reason="先确认本年度可投入的时间与现金缓冲。",
        confidence=0.7,
    )
    personalized = AgentAction(
        agent_id="personal",
        action_id="personal.stabilize",
        reason="先缩小验证范围，避免当前资源被过度拉扯。",
        confidence=0.7,
        key_factors=["每周可投入时间有限", "现金缓冲不足以承受连续追加投入"],
        next_actions=["在 7 天内列出每周可投入时间并锁定一个验证目标"],
        uncertainty="尚未确认现有收入的稳定性。",
    )

    assert legacy.key_factors == []
    assert legacy.next_actions == []
    assert legacy.uncertainty is None
    assert personalized.key_factors[0] == "每周可投入时间有限"
    assert personalized.next_actions[0].startswith("在 7 天内")
