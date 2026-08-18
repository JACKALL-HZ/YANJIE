"""会话相关 API 端点"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import assert_session_owner, get_db, get_request_actor
from app.db.repository import EventRepo, MessageRepo, SimulationRepo
from app.services.report_service import build_report, get_scenario_title
from app.services.simulation_service import restore_pause_reason


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_to_dict(s) -> dict:
    return {
        "id": s.id,
        "scenario_id": s.scenario_id,
        "scenario_title": get_scenario_title(s.scenario_id),
        "phase": s.phase,
        "current_year": s.current_year,
        "result": getattr(s, "result", None),
        "score": s.score,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
def list_sessions(
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
    scenario_id: str | None = None,
) -> list[dict]:
    """返回当前登录用户的历史会话列表，可按场景筛选。"""
    repo = SimulationRepo(db)
    if scenario_id:
        scenario_sessions = repo.list_by_scenario(scenario_id)
        if actor.user_id is not None:
            sessions = [s for s in scenario_sessions if s.user_id == actor.user_id]
        else:
            sessions = [
                s
                for s in scenario_sessions
                if actor.anonymous_key is not None
                and s.owner_key == actor.anonymous_key
            ]
    else:
        sessions = (
            repo.list_by_user(actor.user_id)
            if actor.user_id is not None
            else repo.list_by_owner_key(actor.anonymous_key or "")
        )
    return [_session_to_dict(s) for s in sessions]


@router.get("/{session_id}/report-detail")
def get_session_report_detail(
    session_id: str,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """返回历史页渲染用的结构化中文报告。"""
    assert_session_owner(session_id, db, actor)
    return build_report(session_id, db).model_dump(mode="json")


@router.get("/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """返回单个会话的完整详情（含事件列表）。"""
    srepo = SimulationRepo(db)
    erepo = EventRepo(db)
    mrepo = MessageRepo(db)

    session = assert_session_owner(session_id, db, actor)
    agent_states = dict(session.agent_states or {})
    pause_reason = restore_pause_reason(session.phase, agent_states, None)

    events = erepo.get_by_session(session_id)
    messages = mrepo.list_by_session(session_id)
    return {
        "id": session.id,
        "scenario_id": session.scenario_id,
        "phase": session.phase,
        "pause_reason": pause_reason,
        "current_year": session.current_year,
        "decision_vars": session.decision_vars,
        "user_profile": session.user_profile or {},
        "decision_history": session.decision_history or [],
        "world_state": session.world_state,
        "timeline": session.timeline,
        "result": getattr(session, "result", None),
        "score": session.score,
        "score_detail": session.score_detail,
        "risks": session.risks,
        "action_plan": session.action_plan,
        "startup_settlement": agent_states.get(
            "startup_settlement", {}
        ),
        "pending_intervention": agent_states.get(
            "pending_intervention"
        ),
        "pending_decision_preview": agent_states.get(
            "pending_decision_preview"
        ),
        "messages": [
            {
                "role": MessageRepo.decode_role(message.role)[0],
                "agent_id": MessageRepo.decode_role(message.role)[1],
                "content": message.content,
                "year": message.year,
            }
            for message in messages
        ],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "events": [
            {
                "event_type": f"agent.{e.agent}.{e.action}",
                "year": e.year,
                "agent": e.agent,
                "action": e.action,
                "state_diff": e.state_diff,
                "payload": e.payload,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
