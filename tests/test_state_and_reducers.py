from app.engine.ending import judge_ending
from app.engine.models import AgentAction
from app.engine.reducers import apply_actions
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader
import pytest


def test_initial_state_uses_source_defaults():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(
        source,
        {"budget": 200000, "city": "hangzhou", "industry": "milk_tea", "span_years": 3},
    )

    assert state.year == 0
    assert state.phase == "input"
    assert state.world_state.cash_flow == 200000
    assert state.timeline == []


def test_initial_state_applies_profile_to_declared_dynamic_metric():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    payload = source.model_dump()
    payload["state_metrics"] = [
        {
            "metric_id": "execution_capacity",
            "label": "执行能力",
            "unit": "分",
            "initial_value": 50,
            "display_order": 1,
        }
    ]
    payload["profile_state_modifiers"] = [
        {
            "metric": "execution_capacity",
            "profile_key": "weekly_hours",
            "multiplier": 0.5,
            "offset": 0,
        }
    ]
    typed_source = source.__class__.model_validate(payload)

    state = make_initial_state(
        typed_source,
        {"budget": 200000},
        user_profile={"weekly_hours": 20},
    )

    assert state.world_state.cash_flow == 200000
    assert state.world_state.metrics == {"execution_capacity": 60}


def test_action_updates_declared_dynamic_metric_without_affecting_legacy_metrics():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    payload = source.model_dump()
    payload["state_metrics"] = [
        {
            "metric_id": "execution_capacity",
            "label": "执行能力",
            "unit": "分",
            "initial_value": 50,
            "display_order": 1,
        }
    ]
    for effect in payload["action_effects"]:
        if effect["action_id"] == "market.differentiate":
            effect["effects"] = {"execution_capacity": 5}
    typed_source = source.__class__.model_validate(payload)
    state = make_initial_state(typed_source, {"budget": 200000})

    result = apply_actions(
        state.world_state,
        [
            AgentAction(
                agent_id="market",
                action_id="market.differentiate",
                reason="验证动态指标更新",
                confidence=1.0,
            )
        ],
        typed_source,
    )

    assert result.world_state.cash_flow == state.world_state.cash_flow
    assert result.world_state.metrics == {"execution_capacity": 55}


def test_initial_state_reports_decision_var_bounds_in_chinese():
    source = ScenarioLoader("scenarios").load("house_purchase")

    with pytest.raises(ValueError, match="当前月收入不能低于 3000"):
        make_initial_state(source, {"income": 0})


def test_apply_actions_is_deterministic_and_records_effects():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    initial = make_initial_state(source, {"budget": 200000})
    actions = [
        AgentAction(
            agent_id="market",
            action_id="market.differentiate",
            reason="test",
            confidence=1.0,
        )
    ]

    result = apply_actions(initial.world_state, actions, source)

    assert result.world_state.cash_flow != initial.world_state.cash_flow
    assert result.effects[0].action_id == "market.differentiate"
    assert result.events[0].agent_id == "market"


def test_bankruptcy_is_pure_rule_based():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    ending = judge_ending(
        world_state={
            "cash_flow": 0,
            "customer_flow": 0,
            "competition_count": 47,
            "monthly_profit": -1000,
            "payback_ratio": 0,
        },
        year=1,
        end_conditions=source.end_conditions,
    )

    assert ending.result == "bankrupt"
    assert ending.reason.metric == "cash_flow"
