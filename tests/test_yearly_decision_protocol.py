from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader
from app.schemas.events import EventType


def _engine() -> SimulationEngine:
    source = ScenarioLoader("scenarios").load("milktea_startup")
    return SimulationEngine(source, use_stub=True)


def test_initial_analysis_waits_for_a_first_year_decision():
    events = list(_engine().iter_events({"budget": 200000, "span_years": 2}))

    assert [event.event_type for event in events] == [
        EventType.SIMULATION_STARTED,
        EventType.SIMULATION_PAUSED,
    ]
    assert events[-1].payload.year == 0
    assert events[-1].state_snapshot.pause_reason == "year_decision_required"
    assert events[-1].state_snapshot.timeline == []


def test_a_yearly_decision_advances_exactly_one_year_then_waits_again():
    engine = _engine()
    initial_state = list(
        engine.iter_events({"budget": 200000, "span_years": 3})
    )[-1].state_snapshot

    events = list(
        engine.resume_events(
            initial_state.session_id,
            initial_state.model_copy(
                update={"user_message": "先保留现金缓冲，再小范围验证客群"}
            ),
            "先保留现金缓冲，再小范围验证客群",
        )
    )

    assert events[0].event_type == EventType.YEAR_STARTED
    assert events[0].payload.year == 1
    assert any(event.event_type == EventType.YEAR_COMPLETED for event in events)
    assert events[-1].event_type == EventType.SIMULATION_PAUSED
    assert events[-1].state_snapshot.year == 1
    assert events[-1].state_snapshot.pause_reason == "year_decision_required"
