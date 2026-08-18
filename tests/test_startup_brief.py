from unittest.mock import MagicMock

from app.agents.startup_brief import StartupBriefGenerator
from app.engine.engine import SimulationEngine
from app.engine.models import SimulationState, WorldState
from app.scenarios.loader import ScenarioLoader


def test_startup_brief_uses_current_user_variables_in_prompt():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="## 本次经营判断\n围绕萧山茶饮小店先验证选址。")
    state = SimulationState(
        scenario_id="general_startup",
        decision_vars={"city": "杭州萧山区", "industry": "奶茶店", "budget": 150000, "span_years": 2},
        world_state=WorldState(cash_flow=150000),
    )

    brief = StartupBriefGenerator(llm).build(state)

    assert "萧山茶饮" in brief
    prompt = llm.invoke.call_args.args[0][1].content
    assert "杭州萧山区" in prompt
    assert "150000" in prompt
    assert "奶茶店" in prompt


def test_startup_brief_fallback_keeps_user_values_dynamic():
    state = SimulationState(
        scenario_id="general_startup",
        decision_vars={"city": "济南", "industry": "牛肉面店", "budget": 300000, "span_years": 2},
        world_state=WorldState(cash_flow=300000),
    )

    brief = StartupBriefGenerator(None).build(state)

    assert "济南" in brief
    assert "牛肉面店" in brief
    assert "300,000" in brief


def test_every_scenario_gets_an_initial_analysis_before_agents_run():
    source = ScenarioLoader("scenarios").load("study_abroad")

    events = list(
        SimulationEngine(source, use_stub=True).iter_events(
            {
                "target_country": "美国",
                "target_major": "计算机科学",
                "budget": 800000,
                "span_years": 1,
            }
        )
    )

    assert events[0].payload.initial_analysis
    assert "美国" in events[0].payload.initial_analysis
