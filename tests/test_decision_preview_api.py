import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _create_year_paused_session(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv("PAUSE_EACH_YEAR", "1")
    response = client.post(
        "/api/simulations",
        json={"scenario_id": "milktea_startup", "decision_vars": {"budget": 200000}},
    )
    assert response.status_code == 200
    assert response.json()["phase"] == "paused"
    return response.json()


def test_business_decision_returns_read_only_preview_before_branch_selection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    paused = _create_year_paused_session(client, monkeypatch)
    response = client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": "请明星代言"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "paused"
    assert body["year"] == paused["year"]
    assert body["timeline"] == paused["timeline"]
    preview = body["pending_decision_preview"]
    assert preview["decision_id"] == "celebrity_endorsement"
    assert [branch["branch_id"] for branch in preview["branches"]] == [
        "user_proposal",
        "expert_recommendation",
        "low_cost_alternative",
    ]


def test_selected_preview_branch_applies_then_advances_one_year(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    paused = _create_year_paused_session(client, monkeypatch)
    preview_response = client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": "请明星代言"},
    )
    assert preview_response.status_code == 200

    response = client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": "user_proposal"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == paused["year"] + 1
    assert body["timeline"][-1]["state_diff"]["cash_flow"] <= -80000
    assert body["pending_decision_preview"] is None
    assert all(
        "明星代言" in action["reason"]
        for action in body["timeline"][-1]["agent_actions"]
    )


def test_selected_preview_branch_is_persisted_for_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    paused = _create_year_paused_session(client, monkeypatch)
    client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": "请明星代言"},
    )
    client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": "low_cost_alternative"},
    )

    detail = client.get(f"/api/sessions/{paused['session_id']}")

    assert detail.status_code == 200
    record = detail.json()["decision_history"][-1]
    assert record["raw_text"] == "请明星代言"
    assert record["selected_branch"] == "low_cost_alternative"
