from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine.engine import SimulationEngine
from app.main import app
from app.scenarios.loader import ScenarioLoader
from app.schemas.events import EventType


def _all_scenario_ids() -> list[str]:
    return sorted(path.stem for path in Path("scenarios").glob("*.json"))


def _default_decision_vars(scenario_id: str) -> dict[str, object]:
    source = ScenarioLoader("scenarios").load(scenario_id)
    return {
        definition.name: definition.default
        for definition in source.decision_vars
        if definition.default is not None
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("scenario_id", _all_scenario_ids())
def test_every_scene_waits_for_year_one_decision_and_advances_one_year(
    scenario_id: str,
) -> None:
    source = ScenarioLoader("scenarios").load(scenario_id)
    engine = SimulationEngine(source, use_stub=True)

    initial_events = list(engine.iter_events(_default_decision_vars(scenario_id)))

    assert [event.event_type for event in initial_events] == [
        EventType.SIMULATION_STARTED,
        EventType.SIMULATION_PAUSED,
    ]
    initial_state = initial_events[-1].state_snapshot
    assert initial_state.year == 0
    assert initial_state.pause_reason == "year_decision_required"

    resumed_events = list(
        engine.resume_events(
            initial_state.session_id,
            initial_state,
            "先小范围验证，再根据结果调整下一步投入。",
        )
    )

    assert resumed_events[0].event_type == EventType.YEAR_STARTED
    completed = [
        event for event in resumed_events
        if event.event_type == EventType.YEAR_COMPLETED
    ]
    assert len(completed) == 1
    assert completed[0].payload.year == 1
    assert resumed_events[-1].state_snapshot.year == 1


@pytest.mark.parametrize("scenario_id", _all_scenario_ids())
def test_every_scene_exposes_the_same_protocol_through_the_http_api(
    client: TestClient,
    scenario_id: str,
) -> None:
    initial = client.post(
        "/api/simulations",
        json={
            "scenario_id": scenario_id,
            "decision_vars": _default_decision_vars(scenario_id),
        },
    )

    assert initial.status_code == 200, initial.text
    initial_body = initial.json()
    assert initial_body["year"] == 0
    assert initial_body["pause_reason"] == "year_decision_required"

    resumed = client.post(
        f"/api/simulations/{initial_body['session_id']}/resume",
        json={"choice": "我会控制节奏，先小范围执行并记录结果。"},
    )

    assert resumed.status_code == 200, resumed.text
    body = resumed.json()
    assert body["year"] == 1
    assert body["phase"] in {"paused", "horizon_review", "completed"}


def test_extended_startup_simulation_accepts_a_stop_loss_decision(
    client: TestClient,
) -> None:
    initial = client.post(
        "/api/simulations",
        json={
            "scenario_id": "general_startup",
            "decision_vars": {
                "budget": 300000,
                "city": "杭州",
                "industry": "餐饮",
                "span_years": 1,
            },
        },
    ).json()
    first_year = client.post(
        f"/api/simulations/{initial['session_id']}/resume",
        json={"choice": "先控制投入，验证目标客群。"},
    )

    assert first_year.status_code == 200
    assert first_year.json()["pause_reason"] == "horizon_review"

    extended = client.post(
        f"/api/simulations/{initial['session_id']}/resume",
        json={"choice": "extend_1_year"},
    )
    assert extended.status_code == 200
    assert extended.json()["pause_reason"] == "year_decision_required"

    stop_loss = client.post(
        f"/api/simulations/{initial['session_id']}/resume",
        json={"choice": "收缩止损"},
    )

    assert stop_loss.status_code == 200
    assert stop_loss.json()["year"] == 2
    assert stop_loss.json()["input_kind"] == "business_decision"
