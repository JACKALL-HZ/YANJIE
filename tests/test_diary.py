"""决策日记 + 现实校准 + 统计 测试。"""

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

    def test_list_returns_scenario_title(self, client):
        """list 接口应返回 scenario_title 中文名。"""
        sid = _create_session(client)
        resp = client.get("/api/diary")
        assert resp.status_code == 200
        items = resp.json()
        found = [i for i in items if i["session_id"] == sid]
        assert len(found) == 1
        assert found[0]["scenario_title"] == "奶茶店创业"

    def test_list_returns_result_label(self, client):
        """list 接口应返回 result_label 中文标签。"""
        sid = _create_session(client)
        resp = client.get("/api/diary")
        items = resp.json()
        found = [i for i in items if i["session_id"] == sid][0]
        assert "result_label" in found
        assert "calibration_grade" in found


class TestCalibration:
    """现实校准测试。"""

    def test_save_calibration(self, client):
        sid = _create_completed_session(client)
        resp = client.put(f"/api/diary/{sid}/calibration", json={"actual_result": "steady"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual_result"] == "steady"
        assert "simulated_result_label" in data
        assert "actual_result_label" in data
        assert "calibration_grade" in data
        assert "summary" in data

    def test_get_calibration(self, client):
        sid = _create_completed_session(client)
        client.put(f"/api/diary/{sid}/calibration", json={"actual_result": "bankrupt"})
        resp = client.get(f"/api/diary/{sid}/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert "simulated_result" in data
        assert "actual_result" in data
        assert "calibration_score" in data
        assert "simulated_result_label" in data
        assert "actual_result_label" in data
        assert "calibration_grade" in data
        assert "summary" in data

    def test_calibration_match_perfect(self, client):
        sid = _create_completed_session(client)
        sim = client.get(f"/api/diary/{sid}/calibration").json()
        sim_result = sim.get("simulated_result", "steady")
        # 校准值优先取「与推演结果相同」（若属合法枚举），否则用 steady 验证「不同→低分」
        actual = sim_result if sim_result in ("goal_reached", "steady", "bankrupt", "timeout") else "steady"
        put = client.put(f"/api/diary/{sid}/calibration", json={"actual_result": actual})
        assert put.status_code == 200
        data = client.get(f"/api/diary/{sid}/calibration").json()
        if sim_result == actual:
            assert data["calibration_score"] == 1.0
            assert data["calibration_grade"] == "高度准确"
        else:
            assert data["calibration_score"] in (0.0, 0.5)

    def test_calibration_summary_content(self, client):
        """校准总结应包含推演和现实结果的中文标签。"""
        sid = _create_completed_session(client)
        resp = client.put(f"/api/diary/{sid}/calibration", json={"actual_result": "bankrupt"})
        summary = resp.json()["summary"]
        assert len(summary) > 10
        assert "推演" in summary or "现实" in summary

    def test_nonexistent_calibration_404(self, client):
        resp = client.get("/api/diary/nonexistent/calibration")
        assert resp.status_code == 404


class TestDiaryStats:
    """决策日记统计端点测试。"""

    def test_stats_returns_structure(self, client):
        """stats 端点应返回完整统计结构。"""
        resp = client.get("/api/diary/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data
        assert "calibrated_count" in data
        assert "uncalibrated_count" in data
        assert "avg_calibration_score" in data
        assert "result_distribution" in data
        assert "tag_distribution" in data
        assert "grade_distribution" in data

    def test_stats_counts_after_operations(self, client):
        """创建会话 + 打标签后，stats 应反映增量。"""
        before = client.get("/api/diary/stats").json()
        sid = _create_session(client)
        client.put(f"/api/diary/{sid}", json={"tags": ["统计测试标签"]})
        after = client.get("/api/diary/stats").json()
        assert after["total_entries"] >= before["total_entries"] + 1
        assert "统计测试标签" in after["tag_distribution"]

    def test_stats_grade_distribution_keys(self, client):
        """grade_distribution 应包含四个固定 key。"""
        data = client.get("/api/diary/stats").json()
        gd = data["grade_distribution"]
        assert "高度准确" in gd
        assert "部分偏差" in gd
        assert "显著偏差" in gd
        assert "未校准" in gd
