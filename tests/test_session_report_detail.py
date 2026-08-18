from fastapi.testclient import TestClient

from app.main import app


def _create_session(client: TestClient) -> str:
    response = client.post(
        "/api/simulations",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {
                "budget": 200000,
                "city": "杭州",
                "industry": "奶茶",
                "span_years": 2,
            },
        },
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    resumed = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "实施稳健方案并记录结果"},
    )
    assert resumed.status_code == 200, resumed.text
    return session_id


def test_report_detail_contains_four_agents_and_chinese_metrics():
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.get(f"/api/sessions/{session_id}/report-detail")

    assert response.status_code == 200
    report = response.json()
    assert report["years"]
    assert {item["agent_id"] for item in report["years"][0]["agent_actions"]} == {
        "market",
        "environment",
        "personal",
        "risk",
    }
    assert report["years"][0]["metrics"][0]["label"] == "现金储备"
    report_text = str(report)
    for raw_metric in (
        "cash_flow",
        "customer_flow",
        "competition_count",
        "monthly_profit",
        "payback_ratio",
    ):
        assert raw_metric not in report_text
