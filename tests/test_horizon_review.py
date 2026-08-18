import json

from fastapi.testclient import TestClient
import pytest
from sse_starlette.sse import AppStatus

from app.main import app
from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader
from app.schemas.events import EventType


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


def test_requested_span_pauses_for_horizon_review_instead_of_timing_out(
    monkeypatch,
):
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)

    initial = list(engine.iter_events({"budget": 200000, "span_years": 1}))[-1]
    assert initial.state_snapshot.pause_reason == "year_decision_required"
    events = list(
        engine.resume_events(
            initial.state_snapshot.session_id,
            initial.state_snapshot,
            "先小范围验证需求",
        )
    )

    assert events[-1].event_type == EventType.SIMULATION_PAUSED
    assert events[-1].state_snapshot.phase == "horizon_review"
    assert not any(
        event.event_type == EventType.SIMULATION_COMPLETED for event in events
    )


def test_startup_requested_span_pauses_for_user_confirmation(monkeypatch):
    source = ScenarioLoader("scenarios").load("general_startup")
    engine = SimulationEngine(source, use_stub=True)

    initial = list(
        engine.iter_events(
            {
                "city": "杭州",
                "industry": "奶茶",
                "budget": 200000,
                "span_years": 1,
            }
        )
    )[-1]
    events = list(
        engine.resume_events(
            initial.state_snapshot.session_id,
            initial.state_snapshot,
            "先验证核心客群",
        )
    )

    assert events[-1].event_type == EventType.SIMULATION_PAUSED
    assert events[-1].state_snapshot.phase == "horizon_review"
    assert events[-1].state_snapshot.year == 1


def _read_events(response):
    current = {}
    for line in response.iter_lines():
        if not line:
            if current:
                yield current
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line.removeprefix("event:").strip()
        if line.startswith("data:"):
            current["data"] = json.loads(line.removeprefix("data:").strip())


def _start_at_horizon(
    monkeypatch,
    scenario_id: str = "milktea_startup",
    decision_vars: dict | None = None,
) -> str:
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    client = TestClient(app)
    decision_vars = decision_vars or {"budget": 200000, "span_years": 1}
    with client.stream(
        "POST",
        "/api/simulations/stream",
        json={
            "scenario_id": scenario_id,
            "decision_vars": decision_vars,
        },
    ) as response:
        events = list(_read_events(response))
    assert events[-1]["event"] == "simulation.paused"
    session_id = events[-1]["data"]["session_id"]
    advanced = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "先小范围验证，再根据结果调整投入"},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["phase"] == "horizon_review"
    return session_id


def test_horizon_controls_extend_without_advancing_or_finalize(monkeypatch):
    client = TestClient(app)
    session_id = _start_at_horizon(monkeypatch)

    extend = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "extend_1_year"},
    )

    assert extend.status_code == 200
    assert extend.json()["phase"] == "paused"
    assert extend.json()["year"] == 1
    assert len(extend.json()["timeline"]) == 1

    final_session_id = _start_at_horizon(monkeypatch)
    final = client.post(
        f"/api/simulations/{final_session_id}/resume",
        json={"choice": "finalize_simulation"},
    )

    assert final.status_code == 200
    assert final.json()["phase"] == "completed"
    assert final.json()["result"] == "user_ended"
    assert final.json()["score"] is not None


def test_user_can_end_from_an_annual_decision_pause_and_receive_settlement():
    client = TestClient(app)
    created = client.post(
        "/api/simulations",
        json={
            "scenario_id": "grad_exam",
            "decision_vars": {
                "target_school": "北京大学",
                "current_level": "普通本科",
                "prep_months": 9,
                "budget": 30000,
            },
        },
    )
    assert created.status_code == 200
    assert created.json()["pause_reason"] == "year_decision_required"

    ended = client.post(
        f"/api/simulations/{created.json()['session_id']}/resume",
        json={"choice": "结束推演"},
    )

    assert ended.status_code == 200
    body = ended.json()
    assert body["phase"] == "completed"
    assert body["result"] == "user_ended"
    assert body["pause_reason"] is None
    assert body["year"] == 0
    assert body["timeline"] == []
    assert body["score"] is not None
    assert body["risks"]
    assert body["action_plan"]


def test_extended_startup_accepts_stop_loss_decision_and_advances(monkeypatch):
    client = TestClient(app)
    session_id = _start_at_horizon(
        monkeypatch,
        scenario_id="general_startup",
        decision_vars={
            "city": "杭州",
            "industry": "奶茶",
            "budget": 200000,
            "span_years": 1,
        },
    )

    extended = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "继续推演一年"},
    )
    assert extended.status_code == 200
    assert extended.json()["phase"] == "paused"

    decision = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "收缩止损"},
    )

    assert decision.status_code == 200
    assert decision.json()["year"] == 2
    assert decision.json()["phase"] == "horizon_review"
    assert "已执行" in decision.json()["input_feedback"]


@pytest.mark.parametrize(
    ("choice", "expected_phase", "expected_result"),
    [
        ("结束", "completed", "user_ended"),
        ("完成结算", "completed", "user_ended"),
        ("我想结束了", "completed", "user_ended"),
        ("继续推演一年", "paused", None),
        ("再推一年", "paused", None),
    ],
)
def test_horizon_controls_accept_natural_language(
    monkeypatch,
    choice,
    expected_phase,
    expected_result,
):
    client = TestClient(app)
    session_id = _start_at_horizon(monkeypatch)

    response = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": choice},
    )

    assert response.status_code == 200
    assert response.json()["phase"] == expected_phase
    assert response.json()["result"] == expected_result
