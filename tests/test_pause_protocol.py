from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_annual_pause_exposes_year_decision_reason(monkeypatch):
    monkeypatch.setenv("PAUSE_EACH_YEAR", "1")
    source = ScenarioLoader("scenarios").load("milktea_startup")

    state = SimulationEngine(source, use_stub=True).run({"budget": 200000})

    assert state.phase == "paused"
    assert state.pause_reason == "year_decision_required"


def test_intervention_pause_exposes_intervention_reason():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)
    initial_state = list(engine.iter_events({"budget": 60000}))[-1].state_snapshot

    state = list(
        engine.resume_events(initial_state.session_id, initial_state, "缩减非必要投入")
    )[-1].state_snapshot

    assert state.phase == "paused"
    assert state.pending_intervention is not None
    assert state.pause_reason == "intervention_required"


def test_horizon_review_exposes_horizon_reason(monkeypatch):
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)

    initial_state = list(
        engine.iter_events({"budget": 200000, "span_years": 1})
    )[-1].state_snapshot
    events = list(
        engine.resume_events(initial_state.session_id, initial_state, "先验证客群")
    )
    state = events[-1].state_snapshot

    assert state.phase == "horizon_review"
    assert state.pause_reason == "horizon_review"
