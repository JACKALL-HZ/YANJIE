import pytest

from app.engine.yanjie_engine import YanJieEngine


BASE_PARAMS = {
    "city": "成都",
    "district": "武侯区",
    "category": "咖啡",
    "is_franchise": False,
    "total_budget": 200000,
    "total_years": 2,
    "granularity": "quarter",
}


def test_initialization_requires_all_business_parameters():
    with pytest.raises(ValueError, match="缺少必要参数"):
        YanJieEngine({"city": "成都", "total_budget": 200000})


def test_two_year_startup_simulation_produces_traceable_financial_ledger():
    engine = YanJieEngine(BASE_PARAMS)
    state = engine.initialize()

    assert state["finance"]["remaining_cash"] >= BASE_PARAMS["total_budget"] * 0.2
    assert state["operation"]["breakeven_daily_orders"] > 0
    assert len(state["budget_breakdown"]) >= 5

    while not state["stage"]["is_game_over"]:
        option = engine.decision_options(state)[0]
        state = engine.advance(state, option["decision_id"])

    report = engine.final_settlement(state)
    assert 1 <= len(state["history"]["rounds"]) <= 8
    assert report["financial_table"]["累计总营收"] > 0
    assert report["financial_table"]["最终剩余现金流"] == state["finance"]["remaining_cash"]
    assert len(report["key_attributions"]) >= 3
    assert set(report["scores"]) == {"风险管控", "盈利能力", "资源效率", "市场响应"}


def test_stop_loss_forces_defensive_or_exit_options():
    engine = YanJieEngine(BASE_PARAMS)
    state = engine.initialize()
    state["finance"]["remaining_cash"] = 20000

    options = engine.decision_options(state)

    assert {"shrink_stop_loss", "transfer_or_close"} <= {item["decision_id"] for item in options}


def test_user_can_choose_stop_loss_before_alert_threshold():
    engine = YanJieEngine(BASE_PARAMS)
    state = engine.initialize()

    option_ids = {item["decision_id"] for item in engine.decision_options(state)}
    assert "shrink_stop_loss" in option_ids

    next_state = engine.advance(state, "shrink_stop_loss")

    assert next_state["stage"]["current_round"] == 1
    assert next_state["history"]["rounds"][-1]["决策"] == "收缩止损"


def test_loss_does_not_report_full_payback_or_negative_cash():
    engine = YanJieEngine(BASE_PARAMS)
    state = engine.initialize()
    state = engine.advance(state, "steady_growth")

    assert state["finance"]["remaining_cash"] >= 0
    assert state["finance"]["payback_progress"] == 0


def test_startup_integration_uses_ledger_end_condition():
    from app.engine.engine import SimulationEngine
    from app.scenarios.loader import ScenarioLoader

    source = ScenarioLoader("scenarios").load("general_startup")
    state = SimulationEngine(source, use_stub=True).run_batch(
        {"budget": 200000, "city": "长沙", "industry": "coffee", "span_years": 2}
    )

    assert state.timeline
    assert state.timeline[0].world_state.cash_flow >= 0
    assert state.startup_dashboard["回本进度"] == 0
    assert state.timeline[0].business_dashboard["剩余现金流"] >= 0


def test_strategy_directives_produce_distinct_viable_startup_paths():
    """保守经营不能退化为持续收缩至现金清零。"""
    from app.engine.engine import SimulationEngine
    from app.scenarios.loader import ScenarioLoader

    source = ScenarioLoader("scenarios").load("general_startup")
    decision_vars = {
        "budget": 300000,
        "city": "成都",
        "industry": "catering",
        "span_years": 3,
    }

    steady = SimulationEngine(source, use_stub=True).run_batch(decision_vars)
    aggressive = SimulationEngine(source, use_stub=True).run_batch(
        decision_vars,
        strategy_directives={1: "aggressive", 2: "aggressive", 3: "aggressive"},
    )
    conservative = SimulationEngine(source, use_stub=True).run_batch(
        decision_vars,
        strategy_directives={1: "conservative", 2: "conservative", 3: "conservative"},
    )

    steady_cash = steady.startup_settlement["financial_table"]["最终剩余现金流"]
    aggressive_cash = aggressive.startup_settlement["financial_table"]["最终剩余现金流"]
    conservative_cash = conservative.startup_settlement["financial_table"]["最终剩余现金流"]

    assert conservative_cash > 0
    assert len({steady_cash, aggressive_cash, conservative_cash}) == 3
