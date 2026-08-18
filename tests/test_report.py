"""推演报告导出测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _create_session(client):
    resp = client.post("/api/simulations", json={
        "scenario_id": "milktea_startup",
        "decision_vars": {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
    })
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    resumed = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "实施稳健方案并记录结果"},
    )
    assert resumed.status_code == 200, resumed.text
    return session_id


class TestReportService:
    """Markdown 报告生成器单元测试。"""

    def test_generate_contains_header(self, client):
        """报告包含标题。"""
        from app.services.report_service import generate_markdown
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            md = generate_markdown(sid, db)
            assert "推演报告" in md
            assert sid[:8] in md
        finally:
            db.close()

    def test_generate_contains_timeline(self, client):
        """报告包含逐年推演。"""
        from app.services.report_service import generate_markdown
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            md = generate_markdown(sid, db)
            assert "逐年推演" in md
            assert "第" in md
        finally:
            db.close()

    def test_generate_contains_scoring(self, client):
        """报告包含评分明细。"""
        from app.services.report_service import generate_markdown
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            md = generate_markdown(sid, db)
            assert "评分明细" in md
        finally:
            db.close()

    def test_generate_session_not_found(self):
        """不存在的 session 抛出 ValueError。"""
        from app.services.report_service import generate_markdown
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            with pytest.raises(ValueError, match="session not found"):
                generate_markdown("nonexistent-id", db)
        finally:
            db.close()


class TestReportAPI:
    """报告导出 API 端点。"""

    def test_endpoint_returns_markdown(self, client):
        sid = _create_session(client)
        resp = client.get(f"/api/simulations/{sid}/report")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")

    def test_endpoint_session_not_found(self, client):
        resp = client.get("/api/simulations/nonexistent/report")
        assert resp.status_code == 404
