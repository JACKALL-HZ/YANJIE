import pytest

from app.engine.scoring import compute_score
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


NON_STARTUP_SCENARIOS = {
    "grad_exam": {"备考资源", "学习投入与竞争", "阶段完成度", "录取准备度"},
    "study_abroad": {"留学预算", "材料与竞争", "申请完成度", "申请准备度"},
    "career_advance": {"职业缓冲", "成果与竞争", "发展回报", "晋升准备度"},
    "job_hunting": {"求职储备", "面试与竞争", "薪资匹配", "Offer 准备度"},
    "house_purchase": {"资金缓冲", "房源与市场", "月供承受力", "购房准备度"},
    "investment": {"流动性储备", "分散与波动", "收益表现", "目标达成度"},
}


@pytest.mark.parametrize("scenario_id", NON_STARTUP_SCENARIOS)
def test_non_startup_scenarios_declare_semantic_world_metrics(scenario_id: str):
    source = ScenarioLoader("scenarios").load(scenario_id)

    assert source.state_metrics
    assert all(metric.source_metric for metric in source.state_metrics)


@pytest.mark.parametrize("scenario_id, expected_labels", NON_STARTUP_SCENARIOS.items())
def test_contextual_score_uses_scenario_labels(
    scenario_id: str,
    expected_labels: set[str],
):
    score = compute_score(
        {
            "cash_flow": 100_000,
            "customer_flow": 12,
            "competition_count": 45,
            "monthly_profit": 20_000,
            "payback_ratio": 0.7,
        },
        "user_ended",
        scenario_id=scenario_id,
        decision_vars={"budget": 100_000, "salary_expectation": 20_000},
    )

    assert set(score.detail) == expected_labels


def test_starting_world_state_is_calibrated_from_user_inputs_and_profile():
    loader = ScenarioLoader("scenarios")

    exam = make_initial_state(
        loader.load("grad_exam"),
        {
            "target_school": "北京大学",
            "current_level": "普通本科",
            "prep_months": 9,
            "budget": 30_000,
        },
    )
    assert exam.world_state.customer_flow == 180

    job = make_initial_state(
        loader.load("job_hunting"),
        {"target_industry": "互联网", "city": "杭州", "salary_expectation": 15_000},
        user_profile={"assets": 10_000},
    )
    assert job.world_state.cash_flow == 10_000

    investment = make_initial_state(
        loader.load("investment"),
        {"investment_amount": 200_000, "risk_level": "balanced", "span_years": 3},
    )
    assert investment.world_state.cash_flow == 200_000
