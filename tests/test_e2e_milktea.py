from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_milktea_full_flow_is_replayable():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)

    first = engine.run_batch({"budget": 200000, "span_years": 3})
    second = engine.run_batch({"budget": 200000, "span_years": 3})

    assert first.model_dump(exclude={"session_id"}) == second.model_dump(
        exclude={"session_id"}
    )
    assert first.timeline
    assert first.score is not None
    assert first.risks is not None
    assert first.action_plan
