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
    body = response.json()
    assert body["phase"] == "paused"
    return body


@pytest.mark.parametrize("message", ["好吧", "怎么才能盈利？", "我再想想"])
def test_non_decision_resume_keeps_session_paused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, message: str,
):
    paused = _create_year_paused_session(client, monkeypatch)
    response = client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": message},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "paused"
    assert body["pause_reason"] == "year_decision_required"
    assert body["year"] == paused["year"]
    assert body["input_kind"] in {"casual", "question", "clarify"}
