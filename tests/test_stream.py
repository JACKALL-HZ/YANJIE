import json

import pytest
from fastapi.testclient import TestClient
from sse_starlette.sse import AppStatus

from app.engine.engine import SimulationEngine
from app.main import app
from app.scenarios.loader import ScenarioLoader


def _events(response):
    current = {}
    for line in response.iter_lines():
        if not line:
            if current:
                yield current
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line.removeprefix("data:").strip())


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """Prevent sse-starlette process state from leaking across TestClient loops."""
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


def test_stream_is_incremental_and_has_one_terminal_event():
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/simulations/stream",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000},
        },
    ) as response:
        assert response.status_code == 200
        events = list(_events(response))

    names = [item["event"] for item in events]
    assert names[0] == "simulation.started"
    assert names.count("simulation.started") == 1
    assert "year.completed" not in names
    assert names[-1] == "simulation.paused"
    assert sum(
        name in {"simulation.completed", "simulation.paused", "simulation.failed"}
        for name in names
    ) == 1
    assert [item["data"]["sequence"] for item in events] == list(range(len(events)))


def test_general_startup_year_completed_includes_quantitative_dashboard():
    source = ScenarioLoader("scenarios").load("general_startup")
    engine = SimulationEngine(source, use_stub=True)
    initial = list(engine.iter_events({
        "budget": 200000,
        "city": "成都",
        "industry": "咖啡",
        "span_years": 1,
    }))[-1].state_snapshot
    events = list(
        engine.resume_events(
            initial.session_id, initial, "先小范围验证咖啡客群需求",
        )
    )

    completed = next(event for event in events if event.event_type == "year.completed")
    dashboard = completed.payload.business_dashboard
    assert set(dashboard) >= {
        "日均单量", "月营收", "月成本", "月净利润", "剩余现金流", "回本进度",
    }
    assert dashboard["月营收"] > 0


def test_non_startup_sends_year_result_before_intervention_pause():
    """非创业场景的风险节点不能吞掉首年推演结果。"""
    source = ScenarioLoader("scenarios").load("grad_exam")
    forced_rule = source.intervention_rules[0].model_copy(
        update={"operator": "<=", "threshold": 1_000_000}
    )
    source = source.model_copy(update={"intervention_rules": [forced_rule]})

    engine = SimulationEngine(source, use_stub=True)
    initial = list(engine.iter_events(
        {
            "target_school": "北京大学",
            "current_level": "普通本科",
            "prep_months": 8,
            "budget": 30000,
        }
    ))[-1].state_snapshot
    events = list(
        engine.resume_events(
            initial.session_id, initial, "先制定每周复习计划",
        )
    )

    names = [event.event_type for event in events]
    assert names.index("year.completed") < names.index("simulation.paused")


def test_stream_validation_error_is_sent_as_terminal_event():
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/simulations/stream",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": -1},
        },
    ) as response:
        assert response.status_code == 200
        events = list(_events(response))

    assert events[-1]["event"] == "simulation.failed"
    assert events[-1]["data"]["payload"]["code"] == "VALIDATION_ERROR"
    assert sum(item["event"] == "simulation.failed" for item in events) == 1


def test_stream_reports_house_purchase_income_bound_in_chinese():
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/simulations/stream",
        json={
            "scenario_id": "house_purchase",
            "decision_vars": {"income": 0},
        },
    ) as response:
        assert response.status_code == 200
        events = list(_events(response))

    payload = events[-1]["data"]["payload"]
    assert events[-1]["event"] == "simulation.failed"
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "当前月收入不能低于 3000"
