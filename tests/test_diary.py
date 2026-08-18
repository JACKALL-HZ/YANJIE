"""决策日记 + 现实校准 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _create_session(client):
    """创建模拟会话并返回 session_id。"""
    resp = client.post("/api/simulations", json={
        "scenario_id": "milktea_startup",
        "decision_vars": {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
    })
    assert resp.status_code == 200
    return resp.json()["session_id"]


def _create_completed_session(client):
    session_id = _create_session(client)
    response = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "结束推演"},
    )
    assert response.status_code == 200
    assert response.json()["phase"] == "completed"
    return session_id


class TestDiaryCRUD:
    """决策日记标签/笔记/归档测试。"""

    def test_update_tags(self, client):
        sid = _create_session(client)
        resp = client.put(f"/api/diary/{sid}", json={"tags": ["创业", "奶茶", "低预算"]})
        assert resp.status_code == 200
        assert "创业" in resp.json()["diary_tags"]

    def test_update_notes(self, client):
        sid = _create_session(client)
        resp = client.put(f"/api/diary/{sid}", json={"notes": "第一次模拟推演"})
        assert resp.status_code == 200
        assert "第一次模拟" in resp.json()["diary_notes"]

    def test_update_archived(self, client):
        sid = _create_session(client)
        resp = client.put(f"/api/diary/{sid}", json={"archived": True})
        assert resp.status_code == 200
        assert resp.json()["diary_archived"] is True

    def test_list_with_tag_filter(self, client):
        sid = _create_session(client)
        client.put(f"/api/diary/{sid}", json={"tags": ["创业"]})
        resp = client.get("/api/diary?tag=创业")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    def test_list_archived_filter(self, client):
        sid = _create_session(client)
        client.put(f"/api/diary/{sid}", json={"archived": True})
        resp = client.get("/api/diary?archived=true")
        assert resp.status_code == 200

    def test_nonexistent_session_404(self, client):
        resp = client.put("/api/diary/nonexistent", json={"notes": "test"})
        assert resp.status_code == 404


class TestCalibration:
    """现实校准测试。"""

    def test_save_calibration(self, client):
        sid = _create_completed_session(client)
        resp = client.put(f"/api/diary/{sid}/calibration", json={"actual_result": "steady"})
        assert resp.status_code == 200
        assert resp.json()["actual_result"] == "steady"

    def test_get_calibration(self, client):
        sid = _create_completed_session(client)
        client.put(f"/api/diary/{sid}/calibration", json={"actual_result": "bankrupt"})
        resp = client.get(f"/api/diary/{sid}/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert "simulated_result" in data
        assert "actual_result" in data
        assert "calibration_score" in data

    def test_calibration_match_perfect(self, client):
        sid = _create_completed_session(client)
        # 先获取 simulated result
        sim_resp = client.get(f"/api/diary/{sid}/calibration")
        if sim_resp.status_code == 200:
            sim_result = sim_resp.json().get("simulated_result", "steady")
        else:
            sim_result = "steady"

        client.put(f"/api/diary/{sid}/calibration", json={"actual_result": sim_result})
        resp = client.get(f"/api/diary/{sid}/calibration")
        assert resp.json()["calibration_score"] == 1.0

    def test_nonexistent_calibration_404(self, client):
        resp = client.get("/api/diary/nonexistent/calibration")
        assert resp.status_code == 404
