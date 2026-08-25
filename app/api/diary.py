"""决策日记 API —— 存档/标签/笔记/校准/统计。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Literal

from app.api.dependencies import assert_session_owner, get_db, get_request_actor
from app.db.repository import DiaryRepo
from app.services.report_service import get_scenario_title

router = APIRouter(prefix="/api/diary", tags=["diary"])

# ── 结果码 → 中文标签 ──────────────────────────────────────
RESULT_LABELS: dict[str, str] = {
    "goal_reached": "达成目标",
    "steady": "稳定运营",
    "bankrupt": "破产",
    "timeout": "超时未完成",
    "user_ended": "已结束推演",
    "completed": "已完成",
    "failed": "失败",
    "": "未推演",
}

# 校准分 → 评级
def calibration_grade(score: float | None) -> str:
    if score is None:
        return "未校准"
    if score >= 0.8:
        return "高度准确"
    if score >= 0.5:
        return "部分偏差"
    return "显著偏差"


class DiaryUpdateRequest(BaseModel):
    tags: list[str] | None = Field(None, max_length=20)
    notes: str | None = Field(None, max_length=10000)
    archived: bool | None = None


class CalibrationRequest(BaseModel):
    actual_result: Literal["goal_reached", "steady", "bankrupt", "timeout"] = Field(
        ..., max_length=64, description="实际结果: goal_reached|steady|bankrupt|timeout"
    )
    actual_metrics: dict | None = None


def _result_label(code: str | None) -> str:
    return RESULT_LABELS.get(code or "", code or "未知")


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
    """列出当前登录用户的决策日记条目（含场景中文名/结果标签/校准数据）。"""
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
            "scenario_title": get_scenario_title(r.scenario_id),
            "result": r.result,
            "result_label": _result_label(r.result),
            "score": r.score,
            "diary_tags": r.diary_tags or [],
            "diary_notes": r.diary_notes,
            "diary_archived": r.diary_archived,
            "actual_result": r.actual_result,
            "actual_result_label": _result_label(r.actual_result),
            "calibration_score": r.calibration_score,
            "calibration_grade": calibration_grade(r.calibration_score),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/stats")
def get_diary_stats(
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """决策日记统计概览：总数/已校准/平均校准分/结果分布/标签分布。"""
    repo = DiaryRepo(db)
    rows = repo.list_diary(
        user_id=actor.user_id,
        owner_key=actor.anonymous_key,
    )
    total = len(rows)
    calibrated = [r for r in rows if r.actual_result is not None]
    uncalibrated = total - len(calibrated)
    scores = [r.calibration_score for r in calibrated if r.calibration_score is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    # 结果分布（推演结果）
    result_dist: dict[str, int] = {}
    for r in rows:
        label = _result_label(r.result)
        result_dist[label] = result_dist.get(label, 0) + 1

    # 标签分布
    tag_dist: dict[str, int] = {}
    for r in rows:
        for t in (r.diary_tags or []):
            tag_dist[t] = tag_dist.get(t, 0) + 1

    # 校准等级分布
    grade_dist: dict[str, int] = {"高度准确": 0, "部分偏差": 0, "显著偏差": 0, "未校准": 0}
    for r in rows:
        grade = calibration_grade(r.calibration_score)
        grade_dist[grade] = grade_dist.get(grade, 0) + 1

    return {
        "total_entries": total,
        "calibrated_count": len(calibrated),
        "uncalibrated_count": uncalibrated,
        "avg_calibration_score": avg_score,
        "result_distribution": result_dist,
        "tag_distribution": tag_dist,
        "grade_distribution": grade_dist,
    }


@router.put("/{session_id}/calibration")
def save_calibration(
    session_id: str,
    body: CalibrationRequest,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """保存现实校准数据（实际结果 vs 推演结果），返回校准对比总结。"""
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
        "scenario_title": get_scenario_title(row.scenario_id),
        "simulated_result": row.result,
        "simulated_result_label": _result_label(row.result),
        "actual_result": row.actual_result,
        "actual_result_label": _result_label(row.actual_result),
        "calibration_score": row.calibration_score,
        "calibration_grade": calibration_grade(row.calibration_score),
        "summary": _calibration_summary(row.result, row.actual_result, row.calibration_score),
    }


def _calibration_summary(sim: str | None, actual: str | None, score: float | None) -> str:
    """生成一句话校准总结。"""
    if actual is None:
        return "尚未校准"
    sim_label = _result_label(sim)
    actual_label = _result_label(actual)
    if score is None:
        return f"推演预测「{sim_label}」，现实结果「{actual_label}」，未计算校准分。"
    if score >= 0.8:
        return f"推演预测「{sim_label}」与现实结果「{actual_label}」高度吻合，模型可信度良好。"
    if score >= 0.5:
        return f"推演预测「{sim_label}」与现实结果「{actual_label}」存在偏差，建议复盘关键假设。"
    return f"推演预测「{sim_label}」与现实结果「{actual_label}」显著偏离，模型需重新校准。"


@router.get("/{session_id}/calibration")
def get_calibration(
    session_id: str,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """获取校准对比数据（含中文标签与总结）。"""
    assert_session_owner(session_id, db, actor)
    repo = DiaryRepo(db)
    data = repo.get_calibration(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    sim_r = data.get("simulated_result")
    actual_r = data.get("actual_result")
    score = data.get("calibration_score")
    data["simulated_result_label"] = _result_label(sim_r)
    data["actual_result_label"] = _result_label(actual_r)
    data["calibration_grade"] = calibration_grade(score)
    data["summary"] = _calibration_summary(sim_r, actual_r, score)
    return data
