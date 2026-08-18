from app.engine.compare import compare_states
from app.engine.scoring import build_action_plan, compute_score, extract_risks
import pytest


def test_score_is_bounded_and_dimensioned():
    score = compute_score(
        world_state={
            "cash_flow": 100000,
            "customer_flow": 100,
            "competition_count": 50,
            "monthly_profit": 30000,
            "payback_ratio": 0.8,
        },
        result="steady",
    )
    assert 0 <= score.total <= 100
    assert {"market", "resource", "profitability", "risk"} <= set(score.detail)


def test_risk_and_action_plan_are_specific():
    risks = extract_risks(
        {
            "cash_flow": 20000,
            "competition_count": 70,
            "customer_flow": 20,
            "monthly_profit": -1000,
            "payback_ratio": 0,
        }
    )
    plan = build_action_plan(risks)
    assert any(item.metric == "cash_flow" for item in risks)
    assert len(plan) >= 5
    assert all(item.quantity and item.deadline for item in plan)


@pytest.mark.parametrize(
    ("scenario_id", "decision_vars", "expected_metric"),
    [
        ("grad_exam", {"target_school": "清华大学", "prep_months": 8, "budget": 3000}, "study_time"),
        ("study_abroad", {"target_country": "美国", "budget": 100000}, "application_readiness"),
        ("career_advance", {"target_position": "技术经理"}, "promotion_readiness"),
        ("job_hunting", {"target_industry": "互联网"}, "interview_pipeline"),
        ("house_purchase", {"city": "长沙", "budget": 1200000, "income": 10000}, "mortgage_pressure"),
        ("investment", {"investment_amount": 100000, "risk_level": "aggressive"}, "drawdown_control"),
    ],
)
def test_non_business_risks_and_actions_follow_the_selected_scenario(
    scenario_id, decision_vars, expected_metric
):
    risks = extract_risks(
        {
            "cash_flow": 10000,
            "customer_flow": 2,
            "competition_count": 90,
            "monthly_profit": -5000,
            "payback_ratio": 0.1,
        },
        scenario_id=scenario_id,
        decision_vars=decision_vars,
    )
    plan = build_action_plan(risks, scenario_id=scenario_id)

    metrics = {risk.metric for risk in risks}
    assert expected_metric in metrics
    assert not metrics & {"cash_flow", "customer_flow", "competition_count", "monthly_profit", "payback_ratio"}
    assert all(item.action and item.quantity and item.deadline for item in plan)
    assert all(item.metric in metrics for item in plan)


def test_business_risks_keep_business_specific_metrics():
    risks = extract_risks(
        {
            "cash_flow": 20000,
            "customer_flow": 20,
            "competition_count": 70,
            "monthly_profit": -1000,
            "payback_ratio": 0,
        },
        scenario_id="restaurant_startup",
        decision_vars={"industry": "铁锅炖"},
    )

    assert {"cash_flow", "customer_flow", "competition_count", "monthly_profit", "payback_ratio"} == {
        risk.metric for risk in risks
    }


def test_compare_contains_stable_dimensions():
    result = compare_states(
        {"cash_flow": 100000, "monthly_profit": 30000},
        "steady",
        {"cash_flow": 50000, "monthly_profit": 10000},
        "timeout",
    )
    assert set(result) == {"assets", "risk", "growth", "pressure", "ending", "summary"}
    assert result["ending"]["a"] == "steady"


def test_compare_summary_uses_chinese_metrics_and_recommends_better_plan():
    result = compare_states(
        {
            "cash_flow": 100000,
            "customer_flow": 180,
            "competition_count": 30,
            "monthly_profit": 30000,
            "payback_ratio": 0.8,
        },
        "steady",
        {
            "cash_flow": 50000,
            "customer_flow": 100,
            "competition_count": 55,
            "monthly_profit": 10000,
            "payback_ratio": 0.3,
        },
        "timeout",
        score_a=80,
        score_b=55,
    )

    summary = result["summary"]
    assert summary["recommendation"]["winner"] == "A"
    assert summary["metrics"][0]["label"] == "现金储备"
    assert summary["risks"]
    assert "cash_flow" not in str(summary)
