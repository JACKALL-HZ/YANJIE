from app.agents.inner_graph import AgentCoordinator, build_agents
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


def test_build_agents_returns_exactly_four_declared_agents():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    agents = build_agents(source, use_stub=True)
    assert set(agents) == {"market", "environment", "personal", "risk"}


def test_stub_actions_are_declared_and_stable():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))

    actions_a = coordinator.propose(state)
    actions_b = coordinator.propose(state)

    assert [item.action_id for item in actions_a] == [item.action_id for item in actions_b]
    assert {item.agent_id for item in actions_a} == {
        "market",
        "environment",
        "personal",
        "risk",
    }
    assert all(item.reason for item in actions_a)
    assert all(item.recommendation for item in actions_a)
    assert all(item.alternatives for item in actions_a)
    assert all(item.stop_condition for item in actions_a)
