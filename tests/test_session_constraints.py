from app.services.simulation_service import SimulationService
from app.db.models import SimulationSession
from app.db.session import SessionLocal
from app.main import app
from fastapi.testclient import TestClient


def test_restore_ignores_malformed_legacy_agent_constraint():
    restored = SimulationService._restore_agent_constraints(
        {
            "agent_constraints": {
                "market": {"allowed_action_ids": ["market.hold"]},
                "risk": {
                    "allowed_action_ids": ["risk.contain"],
                    "instruction": "继续核验止损线。",
                    "summary": "风险侧继续审查止损条件。",
                },
            }
        }
    )

    assert set(restored) == {"risk"}
    assert restored["risk"].allowed_action_ids == ["risk.contain"]


def test_legacy_paused_session_restores_yearly_decision_control() -> None:
    """Old sessions without a persisted pause reason must remain operable."""
    client = TestClient(app)
    created = client.post(
        "/api/simulations",
        json={
            "scenario_id": "job_hunting",
            "decision_vars": {},
        },
    )

    assert created.status_code == 200
    session_id = created.json()["session_id"]
    db = SessionLocal()
    try:
        session = db.get(SimulationSession, session_id)
        assert session is not None
        session.phase = "paused"
        session.agent_states = {}
        db.commit()
    finally:
        db.close()

    detail = client.get(f"/api/sessions/{session_id}")
    state = client.get(f"/api/simulations/{session_id}/state")

    assert detail.status_code == 200
    assert detail.json()["pause_reason"] == "year_decision_required"
    assert state.status_code == 200
    assert state.json()["pause_reason"] == "year_decision_required"

    resumed = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "先投递匹配度最高的岗位，并复盘反馈调整方向"},
    )

    assert resumed.status_code == 200
    assert resumed.json()["year"] == 1
