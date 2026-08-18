"""推演 SSE 流式端点 —— Server-Sent Events 实时推演。

参数校验 + 流式序列化。业务逻辑委托 services/。
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_request_actor,
    get_scenario_service,
    get_simulation_service,
    resolve_user_profile,
)
from app.schemas.api import SimulationRequest
from app.schemas.events import EventType, SimulationEvent, SimulationFailedPayload
from app.services.scenario_service import ScenarioService
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.post("/stream")
def stream_simulation(
    request: SimulationRequest,
    scenario_service: ScenarioService = Depends(get_scenario_service),
    simulation_service: SimulationService = Depends(get_simulation_service),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> EventSourceResponse:
    """SSE 流式推演：逐年返回 Agent 决策事件（自动落库）。

    画像在建立连接时解析并冻结，整场推演使用同一份快照。
    """
    source = scenario_service.load_source(request.scenario_id)
    user_profile = resolve_user_profile(request.user_profile, db, actor.user)

    async def event_generator():
        session_id = str(uuid4())
        sequence = 0

        try:
            async for event in simulation_service.aiter_events(
                source,
                request.decision_vars,
                user_profile=user_profile,
                conversation_history=[
                    message.model_dump(mode="json")
                    for message in request.conversation_history
                ],
                intervention_choices=request.intervention_choices,
                strategy_directives=request.strategy_directives,
                success_definition=request.success_definition,
                db=db,
                user_id=actor.user_id,
                owner_key=actor.anonymous_key,
            ):
                session_id = event.session_id
                outbound = event.model_copy(update={"sequence": sequence})
                yield {
                    "event": outbound.event_type.value,
                    "id": str(outbound.sequence),
                    "data": outbound.model_dump_json(),
                }
                sequence += 1
        except ValueError as exc:
            # 用户输入校验错误 —— 直接回显原因，方便修正参数
            logging.getLogger(__name__).warning("SSE simulation validation failed: %s", exc)
            failed = SimulationEvent(
                sequence=sequence,
                session_id=session_id,
                scenario_id=request.scenario_id,
                event_type=EventType.SIMULATION_FAILED,
                payload=SimulationFailedPayload(
                    code="VALIDATION_ERROR",
                    message=str(exc),
                ),
            )
            yield {
                "event": failed.event_type.value,
                "id": str(failed.sequence),
                "data": failed.model_dump_json(),
            }
        except Exception as exc:
            logging.getLogger(__name__).exception("SSE simulation stream failed")
            failed = SimulationEvent(
                sequence=sequence,
                session_id=session_id,
                scenario_id=request.scenario_id,
                event_type=EventType.SIMULATION_FAILED,
                payload=SimulationFailedPayload(
                    code="SIMULATION_FAILED",
                    message="推演过程中发生错误，请稍后重试",
                ),
            )
            yield {
                "event": failed.event_type.value,
                "id": str(failed.sequence),
                "data": failed.model_dump_json(),
            }

    return EventSourceResponse(event_generator())
