from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_engine_starts_paused_without_settling_year_one():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run({"budget": 200000})

    assert state.phase == "paused"
    assert state.pause_reason == "year_decision_required"
    assert state.year == 0
    assert state.timeline == []


def test_engine_reports_the_source_timeout_as_the_supported_horizon():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)

    assert engine.maximum_supported_years() <= source.end_conditions.timeout_years


def test_every_scene_produces_initial_analysis_before_year_one():
    """所有场景先输出初步分析，再把第 1 年决策权交还给用户。"""
    loader = ScenarioLoader("scenarios")

    for scenario_id in loader.list_all():
        source = loader.load(scenario_id)
        decision_vars = {
            item.name: item.default
            for item in source.decision_vars
            if item.default is not None
        }
        events = list(
            SimulationEngine(source, use_stub=True).iter_events(decision_vars)
        )

        assert events[0].payload.initial_analysis, scenario_id
        assert [event.event_type.value for event in events] == [
            "simulation.started",
            "simulation.paused",
        ], scenario_id
        assert events[-1].state_snapshot.pause_reason == "year_decision_required"
