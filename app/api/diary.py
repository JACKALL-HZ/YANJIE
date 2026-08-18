"""决策日记 API —— 存档/标签/笔记/校准。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import assert_session_owner, get_db, get_request_actor
from app.db.repository import DiaryRepo

router = APIRouter(prefix="/api/diary", tags=["diary"])


class DiaryUpdateRequest(BaseModel):
    tags: list[str] | None = Field(None, max_length=20)
    notes: str | None = Field(None, max_length=10000)
    archived: bool | None = None


class CalibrationRequest(BaseModel):
    actual_result: str = Field(..., max_length=64, description="实际结果: goal_reached|steady|bankrupt|timeout")
    actual_metrics: dict | None = None


@router.put("/{session_id}")
def update_diary(
    session_id: str,
    body: DiaryUpdateRequest,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """更新决策日记（标签/笔记/归档）。"""
    if body.tags is None and body.notes is None and body.archived is None:
        raise HTTPException(status_code=422, detail="at least one field required: tags, notes, or archived")
    assert_session_owner(session_id, db, actor)
    repo = DiaryRepo(db)
    row = repo.update_diary(
        session_id,
        tags=body.tags,
        notes=body.notes,
        archived=body.archived,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    db.commit()
    return {
        "session_id": session_id,
        "diary_tags": row.diary_tags,
        "diary_notes": row.diary_notes,
        "diary_archived": row.diary_archived,
    }


@router.get("")
def list_diary(
    tag: str | None = Query(None),
    archived: bool | None = Query(None),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> list[dict]:
    """列出当前登录用户的决策日记条目。"""
    repo = DiaryRepo(db)
    rows = repo.list_diary(
        tag=tag,
        archived=archived,
        user_id=actor.user_id,
        owner_key=actor.anonymous_key,
    )
    return [
        {
            "session_id": r.id,
            "scenario_id": r.scenario_id,
            "result": r.result,
            "score": r.score,
            "diary_tags": r.diary_tags or [],
            "diary_notes": r.diary_notes,
            "diary_archived": r.diary_archived,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.put("/{session_id}/calibration")
def save_calibration(
    session_id: str,
    body: CalibrationRequest,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """保存现实校准数据（实际结果 vs 推演结果）。"""
    assert_session_owner(session_id, db, actor)
    repo = DiaryRepo(db)
    row = repo.save_calibration(
        session_id,
        actual_result=body.actual_result,
        actual_metrics=body.actual_metrics,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    db.commit()
    return {
        "session_id": session_id,
        "simulated_result": row.result,
        "actual_result": row.actual_result,
        "calibration_score": row.calibration_score,
    }


@router.get("/{session_id}/calibration")
def get_calibration(
    session_id: str,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """获取校准对比数据。"""
    assert_session_owner(session_id, db, actor)
    repo = DiaryRepo(db)
    data = repo.get_calibration(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data
