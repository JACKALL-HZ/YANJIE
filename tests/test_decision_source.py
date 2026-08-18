import pytest

from app.scenarios.loader import ScenarioLoader


def test_milktea_source_is_typed_and_complete():
    source = ScenarioLoader("scenarios").load("milktea_startup")

    assert source.scenario_id == "milktea_startup"
    assert {agent.agent_id for agent in source.agents} == {
        "market",
        "environment",
        "personal",
        "risk",
    }
    assert source.end_conditions.bankrupt.metric == "cash_flow"
    assert source.end_conditions.timeout_years == 3
    assert source.intervention_rules[0].max_uses == 1
    assert any(
        effect.action_id == "market.differentiate"
        for effect in source.action_effects
    )


def test_source_rejects_unknown_operator():
    from pydantic import ValidationError

    from app.schemas.decision_source import InterventionRule

    try:
        InterventionRule(
            rule_id="bad",
            metric="cash_flow",
            operator="between",
            threshold=1,
            event="bad",
            options=["a"],
        )
    except ValidationError:
        return
    raise AssertionError("unknown operator must be rejected")


def test_source_rejects_intervention_option_without_declared_effect():
    from pydantic import ValidationError

    from app.schemas.decision_source import DecisionSource

    source = ScenarioLoader("scenarios").load("milktea_startup")
    payload = source.model_dump()
    payload["intervention_rules"][0]["options"][0] = "未映射选项"

    with pytest.raises(ValidationError, match="intervention option has no declared effect"):
        DecisionSource.model_validate(payload)
