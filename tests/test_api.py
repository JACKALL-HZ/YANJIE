from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.scenarios.loader import ScenarioLoader
from app.services.scenario_service import ScenarioService


def test_scenario_list_uses_all_local_scenario_files():
    class RepoWithOnlyMilkTea:
        def list_all(self):
            return [
                SimpleNamespace(
                    scenario_id="milktea_startup",
                    title="奶茶店创业推演",
                )
            ]

    loader = ScenarioLoader(Path(__file__).parents[1] / "scenarios")
    scenarios = ScenarioService(loader, repo=RepoWithOnlyMilkTea()).list_all()

    assert {item["scenario_id"] for item in scenarios} == {
        "career_advance",
        "general_startup",
        "grad_exam",
        "house_purchase",
        "investment",
        "job_hunting",
        "milktea_startup",
        "restaurant_startup",
        "retail_store",
        "saas_startup",
        "study_abroad",
    }


def test_scenario_detail_uses_chinese_presentation_names():
    client = TestClient(app)

    response = client.get("/api/scenarios/milktea_startup")

    assert response.status_code == 200
    body = response.json()
    assert body["decision_vars"][0]["label"] == "可用预算"
    assert [agent["name"] for agent in body["agents"]] == [
        "市场智能体",
        "环境智能体",
        "个人智能体",
        "风险智能体",
    ]
    assert body["action_descriptions"]["personal.stabilize"]


def test_create_simulation_returns_initial_year_decision_pause():
    client = TestClient(app)
    response = client.post(
        "/api/simulations",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "milktea_startup"
    assert body["result"] is None
    assert body["timeline"] == []
    assert body["year"] == 0
    assert body["pause_reason"] == "year_decision_required"


def test_unknown_scenario_is_not_a_500():
    client = TestClient(app)
    response = client.post(
        "/api/simulations",
        json={"scenario_id": "missing", "decision_vars": {"budget": 1}},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "SCENARIO_NOT_FOUND"


def test_invalid_decision_vars_are_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/simulations",
        json={"scenario_id": "milktea_startup", "decision_vars": {"budget": -1}},
    )
    assert response.status_code == 422


def test_compare_endpoint_returns_chinese_summary():
    client = TestClient(app)
    response = client.post(
        "/api/simulations/compare",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars_a": {"budget": 200000},
            "decision_vars_b": {"budget": 300000},
        },
    )

    assert response.status_code == 200
    summary = response.json()["comparison"]["summary"]
    assert summary["recommendation"]["winner"] in {"A", "B", "tie"}
    assert summary["metrics"][0]["label"] == "现金储备"
    assert "cash_flow" not in str(summary)
    assert response.json()["a"]["phase"] == "completed"
    assert response.json()["b"]["phase"] == "completed"
    assert response.json()["a"]["result"] in {"goal_reached", "steady", "bankrupt", "timeout"}
    assert response.json()["b"]["result"] in {"goal_reached", "steady", "bankrupt", "timeout"}
    assert client.get("/api/sessions").json() == []


def test_scenario_detail_returns_form_ready_decision_variables():
    client = TestClient(app)
    response = client.get("/api/scenarios/grad_exam")

    assert response.status_code == 200
    fields = response.json()["decision_vars"]
    assert fields[0]["name"] == "target_school"
    assert fields[2]["value_type"] == "integer"
    assert fields[2]["minimum"] == 1


def test_compare_accepts_grad_exam_variables_without_milktea_fields():
    client = TestClient(app)
    response = client.post(
        "/api/simulations/compare",
        json={
            "scenario_id": "grad_exam",
            "decision_vars_a": {
                "target_school": "985院校",
                "current_level": "普通本科",
                "prep_months": 6,
                "budget": 30000,
            },
            "decision_vars_b": {
                "target_school": "211院校",
                "current_level": "普通本科",
                "prep_months": 12,
                "budget": 50000,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["scenario_id"] == "grad_exam"
