from app.engine.ending import judge_ending
from app.engine.engine import SimulationEngine
from app.engine.models import AgentAction
from app.engine.reducers import apply_actions
from app.scenarios.loader import ScenarioLoader


def test_ending_is_independent_of_agent_reason_text():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    world_state = {
        "cash_flow": 100000,
        "customer_flow": 100,
        "competition_count": 47,
        "monthly_profit": 30000,
        "payback_ratio": 0.8,
    }
    actions_a = [
        AgentAction(
            agent_id="market",
            action_id="market.differentiate",
            reason="short reason",
            confidence=1.0,
        )
    ]
    actions_b = [
        AgentAction(
            agent_id="market",
            action_id="market.differentiate",
            reason="a completely different long explanation",
            confidence=0.1,
        )
    ]
    next_a = apply_actions(world_state, actions_a, source).world_state
    next_b = apply_actions(world_state, actions_b, source).world_state
    first = judge_ending(next_a, 1, source.end_conditions)
    second = judge_ending(next_b, 1, source.end_conditions)
    assert (first.result if first else None) == (second.result if second else None)


def test_low_budget_reaches_bankrupt_with_stub_only():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run_batch({"budget": 1})
    assert state.result == "bankrupt"
