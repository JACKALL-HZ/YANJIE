"""深度追问测试。"""

import pytest
from fastapi.testclient import TestClient
from sse_starlette.sse import AppStatus

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """Prevent sse-starlette process state from leaking across TestClient loops."""
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


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


class TestAskService:
    """深度追问服务单元测试。"""

    def test_stub_answers_market_question(self, client):
        """Stub 模式回答市场相关问题。"""
        from app.services.ask_service import AskService
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            service = AskService()
            answer = service.ask(sid, "市场 agent 为什么选差异化？", db=db)
            assert len(answer) > 0
        finally:
            db.close()

    def test_stub_answers_risk_question(self, client):
        """Stub 模式回答风险相关问题。"""
        from app.services.ask_service import AskService
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            service = AskService()
            answer = service.ask(sid, "有哪些风险？", db=db)
            assert len(answer) > 0
        finally:
            db.close()

    def test_stub_answers_generic_question(self, client):
        """Stub 模式回答通用问题。"""
        from app.services.ask_service import AskService
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            service = AskService()
            answer = service.ask(sid, "推演结果怎么样？", db=db)
            assert len(answer) > 0
        finally:
            db.close()

    def test_year_scoping(self, client):
        """年份限定过滤 timeline。"""
        from app.services.ask_service import AskService
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            service = AskService()
            context = service._build_context(sid, year=1, db=db)
            assert "Timeline" in context
        finally:
            db.close()

    def test_session_not_found(self):
        """不存在的 session 返回提示。"""
        from app.services.ask_service import AskService
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            service = AskService()
            answer = service.ask("nonexistent", "问题", db=db)
            assert "不存在" in answer or "not found" in answer.lower()
        finally:
            db.close()

    def test_llm_failure_does_not_expose_internal_exception(self):
        from app.services.ask_service import AskService

        class ExplodingLlm:
            def invoke(self, messages):
                raise RuntimeError("provider credential rejected: secret-value")

        service = AskService()
        service._llm = ExplodingLlm()

        answer = service.ask("session-id", "为什么会失败？")

        assert "secret-value" not in answer
        assert "provider credential" not in answer


class TestAskAPI:
    """深度追问 API 端点。"""

    def test_endpoint_returns_answer(self, client):
        sid = _create_session(client)
        resp = client.post(f"/api/simulations/{sid}/ask", json={
            "question": "市场 agent 为什么选择了差异化？",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_endpoint_with_year_param(self, client):
        sid = _create_session(client)
        resp = client.post(f"/api/simulations/{sid}/ask?year=1", json={
            "question": "第一年发生了什么？",
        })
        assert resp.status_code == 200
        assert "answer" in resp.json()

    def test_endpoint_empty_question_rejected(self, client):
        sid = _create_session(client)
        resp = client.post(f"/api/simulations/{sid}/ask", json={"question": ""})
        assert resp.status_code == 422


class TestAskStream:
    """流式追问（SSE）测试 —— 验证流式生成器与端点都能产出 token。"""

    def test_stream_sync_yields_full_answer(self, client):
        """ask_stream_sync 在 stub 模式下逐字符产出完整答案。"""
        from app.services.ask_service import AskService
        from app.db.session import SessionLocal

        sid = _create_session(client)
        db = SessionLocal()
        try:
            service = AskService()
            tokens = list(service.ask_stream_sync(sid, "市场 agent 为什么选差异化？", db=db))
            assert "".join(tokens)  # 非空
        finally:
            db.close()

    def test_stream_endpoint_emits_sse_token_frame(self, client):
        """The HTTP boundary must preserve a parseable SSE token frame."""
        sid = _create_session(client)
        with client.stream(
            "POST",
            f"/api/simulations/{sid}/ask/stream",
            json={"question": "Why did the market agent choose differentiation?"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            lines = list(response.iter_lines())

        assert any(line.startswith("event: token") for line in lines), repr(lines)

    def test_stream_endpoint_returns_tokens(self, client):
        """SSE 端点 /ask/stream 产出 token 事件。"""
        import json as _json

        sid = _create_session(client)
        tokens: list[str] = []
        buf = ""
        with client.stream(
            "POST",
            f"/api/simulations/{sid}/ask/stream",
            json={"question": "市场 agent 为什么选差异化？"},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            lines = list(resp.iter_lines())
            for line in lines:
                if line.startswith("event:"):
                    buf = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    payload = _json.loads(line.split(":", 1)[1].strip())
                    if buf == "token" and "token" in payload:
                        tokens.append(payload["token"])
                    buf = ""
        assert "".join(tokens)  # 收到至少一个 token
