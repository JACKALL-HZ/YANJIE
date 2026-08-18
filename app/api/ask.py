"""深度追问 API —— 基于模拟上下文追问 Agent 决策原因（支持流式）。"""

import json
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import assert_session_owner, get_db, get_request_actor
from app.services.ask_service import AskService

router = APIRouter(prefix="/api/simulations", tags=["ask"])
_log = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(..., description="提问内容", min_length=1, max_length=2000)


@router.post("/{session_id}/ask")
def ask_question(
    session_id: str,
    body: AskRequest,
    year: int | None = Query(None, description="限定年份范围"),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """基于模拟数据追问（同步全量返回）。"""
    assert_session_owner(session_id, db, actor)
    service = AskService()
    answer = service.ask(session_id, body.question, year=year, db=db)
    return {"session_id": session_id, "question": body.question, "answer": answer}


@router.post("/{session_id}/ask/stream")
def ask_question_stream(
    session_id: str,
    body: AskRequest,
    year: int | None = Query(None, description="限定年份范围"),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> EventSourceResponse:
    """基于模拟数据追问（SSE 流式逐字返回）。

    使用与推演端点一致的 EventSourceResponse，保证浏览器和测试客户端
    都能以标准 SSE event/data 帧消费 token。
    """
    assert_session_owner(session_id, db, actor)
    service = AskService()

    def generate():
        """同步 SSE 生成器 —— 逐字 yield 结构化 SSE 事件。"""
        try:
            for char in service.ask_stream_sync(session_id, body.question, year=year, db=db):
                yield {
                    "event": "token",
                    "data": json.dumps({"token": char}, ensure_ascii=False),
                }
            yield {"event": "done", "data": json.dumps({"done": True})}
        except Exception:
            _log.exception("SSE ask stream failed")
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "服务暂时不可用，请稍后重试。"},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(
        generate(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
