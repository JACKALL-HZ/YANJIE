import pytest
from pydantic import ValidationError

from app.engine.decision_preview import build_decision_previews
from app.engine.metric_narrator import describe_range_position
from app.engine.state import make_initial_state
from app.schemas.decision_source import DecisionSource
from app.scenarios.loader import ScenarioLoader


def test_milktea_celebrity_endorsement_declares_three_preview_branches():
    source = ScenarioLoader("scenarios").load("milktea_startup")

    decision = next(
        item
        for item in source.decision_catalogue
        if item.decision_id == "celebrity_endorsement"
    )

    assert decision.label == "明星代言"
    assert [branch.branch_id for branch in decision.branches] == [
        "user_proposal",
        "expert_recommendation",
        "low_cost_alternative",
    ]
    assert all(branch.label and branch.description for branch in decision.branches)


@pytest.mark.parametrize(
    ("proposal", "decision_id"),
    [
        ("我想加大投资预算", "increase_marketing_budget"),
        ("跟其他奶茶店联名", "store_collaboration"),
    ],
)
def test_declared_decisions_each_have_their_own_preview(proposal, decision_id):
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})

    previews = build_decision_previews(state, proposal, source)

    assert previews is not None
    assert previews.decision_id == decision_id
    assert len(previews.branches) == 3


def test_decision_source_rejects_action_effect_on_unknown_metric():
    with pytest.raises(ValidationError, match="unknown world-state metric"):
        DecisionSource.model_validate(
            {
                "scenario_id": "invalid_metric",
                "title": "测试",
                "version": 1,
                "decision_vars": [{"name": "budget", "value_type": "integer"}],
                "initial_world_state": {"cash_flow": 100},
                "agents": [
                    {
                        "agent_id": agent_id,
                        "name": agent_id,
                        "stance": "test",
                        "goal": "test",
                        "action_ids": [f"{agent_id}.hold"],
                    }
                    for agent_id in ("market", "environment", "personal", "risk")
                ],
                "action_effects": [
                    {
                        "action_id": "market.hold",
                        "effects": {"unknown_metric": 1},
                        "reason_template": "test",
                    }
                ],
                "end_conditions": {
                    "bankrupt": {
                        "metric": "cash_flow",
                        "operator": "<=",
                        "threshold": 0,
                    },
                    "timeout_years": 1,
                },
            }
        )


def test_celebrity_previews_are_comparable_and_do_not_mutate_main_state():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 120000})
    before = state.model_dump(mode="json")

    previews = build_decision_previews(state, "我想请明星代言", source)

    assert previews is not None
    assert previews.decision_id == "celebrity_endorsement"
    assert [item.branch_id for item in previews.branches] == [
        "user_proposal",
        "expert_recommendation",
        "low_cost_alternative",
    ]
    assert previews.branches[0].world_state.cash_flow < previews.branches[1].world_state.cash_flow
    assert previews.branches[0].worst_case_loss > previews.branches[2].worst_case_loss
    assert state.model_dump(mode="json") == before


def test_customer_flow_just_below_range_uses_precise_chinese_narration():
    assert describe_range_position("customer_flow", 145, 150, 350) == (
        "日客流略低于行业稳态下限 5 杯（参考区间 150-350 杯）"
    )
