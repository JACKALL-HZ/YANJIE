"""推演 API 端点 —— 同步创建模拟 + A/B 对比 + 行动承诺。

参数校验 + 响应序列化。业务逻辑委托 services/。
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.dependencies import (
    assert_session_owner,
    get_db,
    get_request_actor,
    get_scenario_service,
    get_simulation_service,
    resolve_user_profile,
)
from app.db.repository import SimulationRepo
from app.engine.compare import compare_states
from app.engine.decision_preview import build_decision_previews
from app.engine.engine import SimulationEngine
from app.engine.models import DecisionPreviewSet, PendingIntervention, SimulationState
from app.engine.reducers import apply_effect_definitions
from app.engine.risk_graph import build_risk_dag
from app.schemas.api import (
    CompareRequest,
    CompareResponse,
    SimulationRequest,
    SimulationResponse,
)
from app.services.scenario_service import ScenarioService
from app.services.simulation_service import SimulationService, restore_pause_reason
from app.services.input_intent import classify_input
from app.services.ask_service import AskService

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


def _to_response(
    state: SimulationState,
    *,
    input_kind: str | None = None,
    input_feedback: str | None = None,
) -> SimulationResponse:
    return SimulationResponse(
        session_id=state.session_id,
        scenario_id=state.scenario_id,
        phase=state.phase,
        year=state.year,
        result=state.result,
        timeline=state.timeline,
        score=state.score,
        score_detail=state.score_detail,
        risks=state.risks,
        action_plan=state.action_plan,
        startup_settlement=state.startup_settlement,
        pending_intervention=state.pending_intervention,
        pending_decision_preview=state.pending_decision_preview,
        pause_reason=state.pause_reason,
        input_kind=input_kind,
        input_feedback=input_feedback,
    )


@router.post("", response_model=SimulationResponse)
def create_simulation(
    request: SimulationRequest,
    scenario_service: ScenarioService = Depends(get_scenario_service),
    simulation_service: SimulationService = Depends(get_simulation_service),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> SimulationResponse:
    """创建并运行一次模拟推演。

    用户画像由服务端按登录态自动注入（请求体传入的字段作为临时覆盖），
    四个 Agent 因此始终知道"决策者是谁"。
    """
    source = scenario_service.load_source(request.scenario_id)
    user_profile = resolve_user_profile(request.user_profile, db, actor.user)
    state = simulation_service.run(
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
    )
    return _to_response(state)


class CommitActionsRequest(BaseModel):
    committed_actions: list[str] = Field(min_length=1)


@router.post("/{session_id}/commit-actions")
def commit_actions(
    session_id: str,
    body: CommitActionsRequest,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """提交行动承诺——结算后用户勾选要执行的行动。"""
    srepo = SimulationRepo(db)
    session = assert_session_owner(session_id, db, actor)
    if not session.action_plan:
        raise HTTPException(status_code=400, detail="no action plan available")

    committed_set = set(body.committed_actions)
    if "" in committed_set:
        raise HTTPException(status_code=422, detail="committed_actions contains empty string")
    updated = []
    for item in session.action_plan:
        action_text = item.get("action", "")
        item["committed"] = bool(action_text) and action_text in committed_set
        updated.append(item)
    session.action_plan = updated
    srepo.update(session_id, action_plan=updated)
    db.commit()
    return {"committed_count": len(committed_set), "action_plan": updated}


@router.post("/compare", response_model=CompareResponse)
def compare_simulations(
    request: CompareRequest,
    scenario_service: ScenarioService = Depends(get_scenario_service),
    simulation_service: SimulationService = Depends(get_simulation_service),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> CompareResponse:
    """跑两个方案并返回 A/B 对比结果（对比不落库，故不产生会话记录）。"""
    source = scenario_service.load_source(request.scenario_id)
    user_profile = resolve_user_profile(request.user_profile, db, actor.user)
    state_a, state_b = simulation_service.compare(
        source,
        request.decision_vars_a,
        request.decision_vars_b,
        user_profile=user_profile,
        intervention_choices_a=request.intervention_choices_a,
        intervention_choices_b=request.intervention_choices_b,
        strategy_directives_a=request.strategy_directives_a,
        strategy_directives_b=request.strategy_directives_b,
        success_definition=request.success_definition,
    )
    comparison = compare_states(
        state_a.world_state.model_dump(),
        state_a.result or "paused",
        state_b.world_state.model_dump(),
        state_b.result or "paused",
        state_a.score,
        state_b.score,
    )
    return CompareResponse(
        scenario_id=request.scenario_id,
        a=_to_response(state_a),
        b=_to_response(state_b),
        comparison=comparison,
    )


class ResumeRequest(BaseModel):
    choice: str = Field(..., description="干预选项: A/B/C 对应的 choice 值")


def _normalize_horizon_choice(choice: str) -> str | None:
    """将年限确认的常用自然语言表达转为内部控制值。"""
    normalized = re.sub(r"[\s，。！？!?、,.]+", "", choice).lower()
    if normalized in {
        "finalize_simulation",
        "结束",
        "结束推演",
        "完成结算",
        "结束并结算",
        "结算",
    }:
        return "finalize_simulation"
    if normalized in {
        "extend_1_year",
        "继续推演一年",
        "继续推演1年",
        "再推演一年",
        "再推演1年",
    }:
        return "extend_1_year"
    if normalized in {
        "extend_3_years",
        "继续推演三年",
        "继续推演3年",
        "再推演三年",
        "再推演3年",
    }:
        return "extend_3_years"

    if (
        any(keyword in normalized for keyword in ("结束", "结算"))
        and not any(keyword in normalized for keyword in ("不结束", "不结算"))
    ):
        return "finalize_simulation"

    wants_extension = any(
        keyword in normalized for keyword in ("继续", "再推", "延长")
    )
    if wants_extension and any(year in normalized for year in ("一年", "1年")):
        return "extend_1_year"
    if wants_extension and any(year in normalized for year in ("三年", "3年")):
        return "extend_3_years"
    return None


@router.post("/{session_id}/resume", response_model=SimulationResponse)
def resume_simulation(
    session_id: str,
    body: ResumeRequest,
    scenario_service: ScenarioService = Depends(get_scenario_service),
    simulation_service: SimulationService = Depends(get_simulation_service),
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> SimulationResponse:
    """恢复暂停的推演（用户提交干预选择后）。"""
    srepo = SimulationRepo(db)
    session = assert_session_owner(session_id, db, actor)
    if session.phase not in {"paused", "horizon_review"}:
        raise HTTPException(
            status_code=409,
            detail=f"session is not paused, current phase: {session.phase}",
        )

    source = scenario_service.load_source(session.scenario_id)
    safety_intent = classify_input(body.choice)
    if safety_intent.kind == "sensitive":
        state = simulation_service.restore_state(session_id, session, None)
        return _to_response(
            state,
            input_kind="sensitive",
            input_feedback=safety_intent.feedback,
        )

    if _normalize_horizon_choice(body.choice) == "finalize_simulation":
        state = simulation_service.restore_state(session_id, session, None)
        engine = SimulationEngine(source, settings=simulation_service.settings)
        final_state = engine.finalize_user_ended(state)
        engine.persist(final_state, db=db)
        return _to_response(
            final_state,
            input_kind="simulation_control",
            input_feedback="已按你的要求结束推演，并生成当前进度的最终结算。",
        )

    if session.phase == "horizon_review":
        state = simulation_service.restore_state(session_id, session, None)
        engine = SimulationEngine(source, settings=simulation_service.settings)
        horizon_choice = _normalize_horizon_choice(body.choice)
        if horizon_choice == "finalize_simulation":
            final_state = engine.finalize_horizon_review(state)
            engine.persist(final_state, db=db)
            return _to_response(
                final_state,
                input_kind="horizon_control",
                input_feedback="已按当前推演结果完成结算。",
            )

        extensions = {
            "extend_1_year": 1,
            "extend_3_years": 3,
        }
        requested_extension = extensions.get(horizon_choice)
        if requested_extension is None:
            answer = AskService().ask(session_id, body.choice, year=state.year, db=db)
            return _to_response(
                state,
                input_kind=safety_intent.kind,
                input_feedback=(
                    f"{answer}\n\n当前已完成既定年限。你可以继续推演一年、继续推演三年，或完成结算。"
                ),
            )

        next_horizon = min(
            state.year + requested_extension,
            engine.maximum_supported_years(),
        )
        if next_horizon <= state.year:
            return _to_response(
                state,
                input_kind="clarify",
                input_feedback="已达到该场景支持的最长推演年限，请完成结算。",
            )

        decision_vars = dict(state.decision_vars)
        decision_vars["span_years"] = next_horizon
        resumed_state = state.model_copy(
            update={
                "phase": "paused",
                "pause_reason": "year_decision_required",
                "decision_vars": decision_vars,
            }
        )
        srepo.update(
            session_id,
            phase="paused",
            decision_vars=decision_vars,
            agent_states={
                **dict(session.agent_states or {}),
                "pause_reason": "year_decision_required",
            },
        )
        db.commit()
        return _to_response(
            resumed_state,
            input_kind="horizon_control",
            input_feedback=(
                f"推演年限已延长至第 {next_horizon} 年。"
                "请告诉个人智能体下一步经营决策，再继续推演。"
            ),
        )

    # 从世界状态重新计算待决干预
    from app.engine.interventions import find_pending_intervention
    from app.engine.models import WorldState

    ws = WorldState.model_validate(session.world_state or {})
    agent_states = dict(session.agent_states or {})
    pending_data = agent_states.get("pending_intervention")
    pending = (
        PendingIntervention.model_validate(pending_data)
        if isinstance(pending_data, dict)
        else None
    )
    preview_data = agent_states.get("pending_decision_preview")
    pending_preview = (
        DecisionPreviewSet.model_validate(preview_data) if preview_data else None
    )

    if pending_preview is not None:
        selected_branch = next(
            (
                branch
                for branch in pending_preview.branches
                if branch.branch_id == body.choice
            ),
            None,
        )
        if selected_branch is None:
            state = simulation_service.restore_state(session_id, session, pending).model_copy(
                update={
                    "pending_decision_preview": pending_preview,
                    "pause_reason": "decision_preview_required",
                }
            )
            answer = AskService().ask(session_id, body.choice, year=state.year, db=db)
            return _to_response(
                state,
                input_kind=safety_intent.kind,
                input_feedback=(
                    f"{answer}\n\n三种可比较方案仍为你保留；确定后可直接选择其中一种继续推演。"
                ),
            )

        effect_by_action = {item.action_id: item for item in source.action_effects}
        transition = apply_effect_definitions(
            ws,
            [effect_by_action[selected_branch.action_id]],
        )
        state = simulation_service.restore_state(session_id, session, pending).model_copy(
            update={
                "world_state": transition.world_state,
                "user_message": pending_preview.proposal_text,
                "pending_decision_preview": None,
                "pause_reason": None,
            }
        )
        agent_states.pop("pending_decision_preview", None)
        agent_states["pause_reason"] = None
        srepo.update(session_id, agent_states=agent_states)
        srepo.select_decision_branch(session_id, selected_branch.branch_id)
        result = simulation_service.resume_from_state(
            source,
            session_id,
            state,
            body.choice,
            db,
            initial_effects=selected_branch.state_diff,
        )
        return _to_response(result)

    catalogue_keywords = tuple(
        keyword
        for decision in source.decision_catalogue
        for keyword in decision.keywords
    )
    intent = classify_input(body.choice, catalogue_keywords)
    if pending is not None and body.choice in pending.options:
        intent = intent.model_copy(update={"kind": "business_decision"})
    if intent.kind == "question":
        state = simulation_service.restore_state(session_id, session, pending)
        answer = AskService().ask(session_id, body.choice, year=state.year, db=db)
        return _to_response(
            state,
            input_kind="question",
            input_feedback=answer,
        )
    if intent.kind == "casual":
        state = simulation_service.restore_state(session_id, session, pending)
        return _to_response(
            state,
            input_kind=intent.kind,
            input_feedback=intent.feedback,
        )

    if pending is not None and body.choice not in pending.options:
        state = simulation_service.restore_state(session_id, session, pending)
        answer = AskService().ask(session_id, body.choice, year=state.year, db=db)
        return _to_response(
            state,
            input_kind="business_decision",
            input_feedback=(
                f"{answer}\n\n当前还有一项需要处理的风险节点：{pending.event}。"
                "我会保留你的想法；你可以继续说明倾向，或从给出的方案中选择。"
            ),
        )

    state = simulation_service.restore_state(session_id, session, pending)
    preview = build_decision_previews(state, body.choice, source)
    if preview is not None:
        agent_states["pending_decision_preview"] = preview.model_dump(mode="json")
        agent_states["pause_reason"] = "decision_preview_required"
        srepo.update(session_id, agent_states=agent_states)
        srepo.append_decision(
            session_id,
            {
                "year": state.year,
                "raw_text": body.choice,
                "input_kind": "business_decision",
                "decision_label": preview.decision_label,
                "selected_branch": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.commit()
        return _to_response(
            state.model_copy(
                update={
                    "pending_decision_preview": preview,
                    "pause_reason": "decision_preview_required",
                }
            ),
            input_kind="business_decision",
            input_feedback="已生成三种可比较方案，请选择后再推进下一年。",
        )

    # 逐年交互模式：无具体干预事件，直接将用户消息传给 Personal Agent 继续
    state = simulation_service.resume(
        source,
        session_id,
        session,
        pending,  # 可为 None（逐年模式）
        body.choice,
        db=db,
    )
    if state.phase == "completed":
        feedback = "已执行你的决策，推演已结束，最终结算已生成。"
    elif state.phase == "horizon_review":
        feedback = (
            f"已执行你的决策并完成第 {state.year} 年推演。"
            "你可以继续推演，或按当前结果完成结算。"
        )
    else:
        feedback = (
            f"已执行你的决策，第 {state.year} 年结果已更新。"
            "请查看四个智能体的分析和个人智能体给出的下一步建议。"
        )
    return _to_response(
        state,
        input_kind="business_decision",
        input_feedback=feedback,
    )


@router.get("/{session_id}/state")
def get_session_state(
    session_id: str,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """查询推演当前状态（含阶段、年份、待决干预）。"""
    srepo = SimulationRepo(db)
    session = assert_session_owner(session_id, db, actor)
    pause_reason = restore_pause_reason(
        session.phase,
        dict(session.agent_states or {}),
        None,
    )
    return {
        "session_id": session.id,
        "scenario_id": session.scenario_id,
        "phase": session.phase,
        "current_year": session.current_year,
        "result": session.result,
        "score": session.score,
        "pause_reason": pause_reason,
        "has_pending_intervention": pause_reason == "intervention_required",
    }


@router.get("/{session_id}/risk-graph")
def get_risk_graph(
    session_id: str,
    db: Session = Depends(get_db),
    actor = Depends(get_request_actor),
) -> dict:
    """获取风险传导图谱（DAG）。"""
    srepo = SimulationRepo(db)
    session = assert_session_owner(session_id, db, actor)

    from app.engine.models import WorldState
    ws = WorldState.model_validate(session.world_state or {})
    state = SimulationState(
        session_id=session_id,
        scenario_id=session.scenario_id or "",
        decision_vars=session.decision_vars or {},
        world_state=ws,
        phase=session.phase or "completed",
        year=session.current_year or 0,
        result=session.result,
    )

    dag = build_risk_dag(state)
    return dag.model_dump()
