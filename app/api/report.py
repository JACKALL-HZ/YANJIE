"""推演报告导出 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.dependencies import assert_session_owner, get_db, get_request_actor
from app.services.report_service import generate_markdown

router = APIRouter(prefix="/api/simulations", tags=["report"])


@router.get("/{session_id}/report")
def get_report(
    session_id: str,
    format: str = Query("md", description="导出格式: md"),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> PlainTextResponse:
    """导出推演报告为 Markdown。"""
    try:
        assert_session_owner(session_id, db, actor)
        md = generate_markdown(session_id, db)
    except ValueError as e:
        if "session not found" in str(e):
            raise HTTPException(status_code=404, detail="session not found")
        raise HTTPException(status_code=500, detail="report generation failed")

    return PlainTextResponse(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=yanjie_{session_id[:8]}.md"},
    )
