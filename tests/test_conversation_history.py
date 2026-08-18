import json

from fastapi.testclient import TestClient

from app.db.models import SimulationMessage
from app.db.session import SessionLocal
from app.db.repository import MessageRepo
from app.main import app


def test_onboarding_conversation_is_persisted_and_returned_in_report():
    client = TestClient(app)
    history = [
        {
            "role": "agent",
            "agent_id": "guide",
            "content": "你好，我是衍界 AI 向导。",
        },
        {
            "role": "user",
            "agent_id": "",
            "content": "我要考研，北京大学。",
        },
    ]

    response = client.post(
        "/api/simulations",
        json={
            "scenario_id": "grad_exam",
            "decision_vars": {
                "target_school": "北京大学",
                "current_level": "本科",
                "prep_months": 8,
                "budget": 3000,
            },
            "conversation_history": history,
        },
    )

    assert response.status_code == 200
    session_id = response.json()["session_id"]

    db = SessionLocal()
    try:
        messages = (
            db.query(SimulationMessage)
            .filter(SimulationMessage.session_id == session_id)
            .order_by(SimulationMessage.created_at.asc())
            .all()
        )
        assert [
            (*MessageRepo.decode_role(message.role), message.content)
            for message in messages
        ] == [
            ("agent", "guide", "你好，我是衍界 AI 向导。"),
            ("user", None, "我要考研，北京大学。"),
        ]
    finally:
        db.close()

    report = client.get(f"/api/sessions/{session_id}/report-detail")
    assert report.status_code == 200
    assert report.json()["messages"] == [
            {
                "role": "agent",
                "agent_id": "guide",
            "content": "你好，我是衍界 AI 向导。",
            "year": None,
            "created_at": messages[0].created_at.isoformat(),
        },
        {
            "role": "user",
            "agent_id": None,
            "content": "我要考研，北京大学。",
            "year": None,
            "created_at": messages[1].created_at.isoformat(),
        },
    ]


def test_stream_persists_onboarding_conversation_for_history_page():
    client = TestClient(app)
    history = [
        {
            "role": "agent",
            "agent_id": "guide",
            "content": "请告诉我你的目标。",
        },
        {
            "role": "user",
            "agent_id": "",
            "content": "我准备考研。",
        },
    ]
    events = []
    with client.stream(
        "POST",
        "/api/simulations/stream",
        json={
            "scenario_id": "grad_exam",
            "decision_vars": {
                "target_school": "北京大学",
                "current_level": "本科",
                "prep_months": 8,
                "budget": 3000,
            },
            "conversation_history": history,
        },
    ) as response:
        assert response.status_code == 200
        current = {}
        for line in response.iter_lines():
            if not line:
                if current:
                    events.append(current)
                    current = {}
                continue
            if line.startswith("data:"):
                current["data"] = json.loads(line.split(":", 1)[1].strip())
        if current:
            events.append(current)

    session_id = events[-1]["data"]["session_id"]
    db = SessionLocal()
    try:
        messages = (
            db.query(SimulationMessage)
            .filter(SimulationMessage.session_id == session_id)
            .order_by(SimulationMessage.created_at.asc())
            .all()
        )
        assert [message.content for message in messages] == [
            "请告诉我你的目标。",
            "我准备考研。",
        ]
    finally:
        db.close()
