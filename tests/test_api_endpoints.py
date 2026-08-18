"""API 端点补全测试 — 场景列表 / 会话历史 / 重放 / 干预提交"""
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestScenarioEndpoints:
    def test_list_scenarios_returns_all(self):
        """GET /api/scenarios 返回至少 4 个场景"""
        resp = client.get("/api/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 4
        # 第二个元素可能是任意场景，至少包含必要字段
        assert "scenario_id" in data[0]
        assert "title" in data[0]

    def test_get_scenario_detail_existing(self):
        """GET /api/scenarios/{id} 返回场景详情"""
        resp = client.get("/api/scenarios/milktea_startup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == "milktea_startup"
        assert data["title"]

    def test_get_scenario_detail_missing(self):
        """GET /api/scenarios/{id} 不存在 → 404"""
        resp = client.get("/api/scenarios/nonexistent")
        assert resp.status_code == 404


class TestSessionEndpoints:
    def test_list_sessions_empty(self):
        """GET /api/sessions 空数据返回 []"""
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_list_sessions_after_run(self):
        """推演后 GET /api/sessions 包含该会话"""
        resp = client.post(
            "/api/simulations",
            json={
                "scenario_id": "milktea_startup",
                "decision_vars": {"budget": 100000},
            },
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        resumed = client.post(
            f"/api/simulations/{session_id}/resume",
            json={"choice": "实施稳健方案并记录结果"},
        )
        assert resumed.status_code == 200

        resumed = client.post(
            f"/api/simulations/{session_id}/resume",
            json={"choice": "实施稳健方案并记录结果"},
        )
        assert resumed.status_code == 200

        # 查列表应包含该 session
        list_resp = client.get("/api/sessions")
        assert list_resp.status_code == 200
        sessions = list_resp.json()
        ids = [s["id"] for s in sessions]
        assert session_id in ids

    def test_get_session_detail(self):
        """GET /api/sessions/{id} 返回完整会话详情"""
        # 先跑一遍
        resp = client.post(
            "/api/simulations",
            json={
                "scenario_id": "milktea_startup",
                "decision_vars": {"budget": 200000, "span_years": 2},
            },
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        resumed = client.post(
            f"/api/simulations/{session_id}/resume",
            json={"choice": "实施稳健方案并记录结果"},
        )
        assert resumed.status_code == 200

        # 查详情
        detail = client.get(f"/api/sessions/{session_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["id"] == session_id
        assert data["scenario_id"] == "milktea_startup"
        assert "events" in data
        assert isinstance(data["events"], list)
        # 推演后至少有个 agent 事件
        assert len(data["events"]) > 0

    def test_get_session_detail_missing(self):
        """GET /api/sessions/{id} 不存在 → 404"""
        resp = client.get("/api/sessions/nonexistent")
        assert resp.status_code == 404
