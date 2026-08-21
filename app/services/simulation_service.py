"""推演业务编排 —— 创建引擎、跑推演、流式输出、持久化。"""

from collections.abc import AsyncIterator
import asyncio
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session as DbSession

from app.core.config import Settings
from app.db.models import SimulationSession as SimulationSessionRow
from app.engine.engine import EngineEvent, SimulationEngine
from app.engine.models import (
    AgentConstraint,
    DecisionPreviewSet,
    PendingIntervention,
    SimulationState,
    WorldState,
)
from app.schemas.decision_source import DecisionSource


def restore_pause_reason(
    phase: str | None,
    agent_states: dict[str, Any],
    pending: PendingIntervention | None,
) -> str | None:
    persisted = agent_states.get("pause_reason")
    if persisted in {
        "year_decision_required",
        "decision_preview_required",
        "intervention_required",
        "horizon_review",
    }:
        return persisted
    if phase == "horizon_review":
        return "horizon_review"
    if pending is not None:
        return "intervention_required"
    if isinstance(agent_states.get("pending_intervention"), dict):
        return "intervention_required"
    if agent_states.get("pending_decision_preview"):
        return "decision_preview_required"
    if phase == "paused":
        return "year_decision_required"
    return None


def _restore_decision_preview(
    agent_states: dict[str, Any],
) -> DecisionPreviewSet | None:
    raw_preview = agent_states.get("pending_decision_preview")
    if not isinstance(raw_preview, dict):
        return None
    try:
        return DecisionPreviewSet.model_validate(raw_preview)
    except (TypeError, ValidationError):
        return None


class SimulationService:
    """推演业务编排服务。

    职责：创建引擎 → 驱动推演 → 持久化 → 返回结果。
    不调 LLM、不做结局判定。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _restore_agent_constraints(agent_states: dict[str, Any]) -> dict[str, AgentConstraint]:
        """兼容旧会话：单条约束损坏不应阻断整场推演恢复。"""
        restored: dict[str, AgentConstraint] = {}
        raw_constraints = agent_states.get("agent_constraints", {})
        if not isinstance(raw_constraints, dict):
            return restored
        for agent_id, raw_constraint in raw_constraints.items():
            try:
                restored[str(agent_id)] = AgentConstraint.model_validate(raw_constraint)
            except (TypeError, ValidationError):
                logging.getLogger(__name__).warning(
                    "ignoring invalid persisted agent constraint: agent=%s",
                    agent_id,
                )
        return restored

    def run(
        self,
        source: DecisionSource,
        decision_vars: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        intervention_choices: dict[int, str] | None = None,
        strategy_directives: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
        db: DbSession | None = None,
        user_id: str | None = None,
        owner_key: str | None = None,
    ) -> SimulationState:
        """同步跑推演并返回最终状态。"""
        engine = SimulationEngine(source, settings=self.settings)
        try:
            return engine.run(
                decision_vars,
                user_profile=user_profile,
                conversation_history=conversation_history,
                intervention_choices=intervention_choices,
                strategy_directives=strategy_directives,
                success_definition=success_definition,
                db=db,
                user_id=user_id,
                owner_key=owner_key,
            )
        finally:
            engine.close()

    async def aiter_events(
        self,
        source: DecisionSource,
        decision_vars: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        intervention_choices: dict[int, str] | None = None,
        strategy_directives: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
        db: DbSession | None = None,
        user_id: str | None = None,
        owner_key: str | None = None,
    ) -> AsyncIterator[EngineEvent]:
        """异步流式推演，逐个返回 SimulationEvent（可选持久化）。

        引擎构造（含 MCP 握手、Chroma、checkpointer、graph 构建）较重，
        必须在 asyncio.to_thread 中执行，避免阻塞事件循环导致
        SSE 推演期间其他 HTTP 请求（如登录）全部挂起。
        """
        engine = await asyncio.to_thread(
            lambda: SimulationEngine(source, settings=self.settings)
        )
        try:
            async for event in engine.aiter_events(
                decision_vars,
                user_profile=user_profile,
                conversation_history=conversation_history,
                intervention_choices=intervention_choices,
                strategy_directives=strategy_directives,
                success_definition=success_definition,
                db=db,
                user_id=user_id,
                owner_key=owner_key,
            ):
                yield event
        finally:
            engine.close()

    def resume(
        self,
        source: DecisionSource,
        session_id: str,
        session_row: SimulationSessionRow,
        pending: PendingIntervention | None,
        choice: str,
        db: DbSession,
    ) -> SimulationState:
        """恢复暂停的推演（干预恢复 或 逐年交互恢复）。"""
        state = self.restore_state(session_id, session_row, pending).model_copy(
            update={"user_message": choice}
        )
        return self.resume_from_state(source, session_id, state, choice, db)

    def resume_from_state(
        self,
        source: DecisionSource,
        session_id: str,
        state: SimulationState,
        choice: str,
        db: DbSession,
        initial_effects: dict[str, float] | None = None,
    ) -> SimulationState:
        """Resume from a prepared state, optionally including a selected preview effect."""
        engine = SimulationEngine(source, settings=self.settings)
        try:
            final_state: SimulationState | None = None
            for event in engine.resume_events(session_id, state, choice, db=db):
                if isinstance(event.state_snapshot, SimulationState):
                    final_state = event.state_snapshot
            if final_state is None:
                raise RuntimeError("resume produced no state")
            if initial_effects and final_state.timeline:
                updated = final_state.model_copy(deep=True)
                latest = updated.timeline[-1]
                state_diff = dict(latest.state_diff)
                for metric, delta in initial_effects.items():
                    state_diff[metric] = state_diff.get(metric, 0) + delta
                updated.timeline[-1] = latest.model_copy(update={"state_diff": state_diff})
                final_state = updated
                engine.persist(final_state, db=db)
            return final_state
        finally:
            engine.close()

    def restore_state(
        self,
        session_id: str,
        session_row: SimulationSessionRow,
        pending: PendingIntervention | None,
    ) -> SimulationState:
        """Rebuild a paused state without advancing the simulation."""
        ws = WorldState.model_validate(session_row.world_state or {})
        agent_states = dict(session_row.agent_states or {})
        if pending is None:
            pending_data = agent_states.get("pending_intervention")
            if isinstance(pending_data, dict):
                try:
                    pending = PendingIntervention.model_validate(pending_data)
                except (TypeError, ValidationError):
                    pending = None
        # 画像从冻结快照列读取；旧会话（快照列为空）回落到 decision_vars 内的历史写法
        frozen_profile = session_row.user_profile
        if not isinstance(frozen_profile, dict) or not frozen_profile:
            legacy = session_row.decision_vars
            frozen_profile = (
                legacy.get("user_profile", {}) if isinstance(legacy, dict) else {}
            )
        state = SimulationState(
            session_id=session_id,
            scenario_id=session_row.scenario_id or "",
            decision_vars=session_row.decision_vars or {},
            world_state=ws,
            phase=session_row.phase or "paused",
            pause_reason=restore_pause_reason(session_row.phase, agent_states, pending),
            year=session_row.current_year or 0,
            result=session_row.result,
            timeline=[],
            user_profile=frozen_profile or {},
            pending_intervention=pending,
            user_message="",
            startup_ledger=agent_states.get("startup_ledger", {}),
            startup_dashboard=agent_states.get("startup_dashboard", {}),
            startup_settlement=agent_states.get("startup_settlement", {}),
            agent_constraints=self._restore_agent_constraints(agent_states),
            pending_decision_preview=_restore_decision_preview(agent_states),
        )

        # 从 timeline 重建（如果 DB 有存）
        from app.engine.models import TimelineNode
        db_timeline = session_row.timeline or []
        for node_data in db_timeline:
            state.timeline.append(TimelineNode.model_validate(node_data))

        return state

    def compare(
        self,
        source: DecisionSource,
        decision_vars_a: dict[str, Any],
        decision_vars_b: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        intervention_choices_a: dict[int, str] | None = None,
        intervention_choices_b: dict[int, str] | None = None,
        strategy_directives_a: dict[int, str] | None = None,
        strategy_directives_b: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
    ) -> tuple[SimulationState, SimulationState]:
        """跑两个推演，返回 (state_a, state_b)。"""
        engine = SimulationEngine(source, settings=self.settings)
        try:
            state_a = engine.run_batch(
                decision_vars_a,
                user_profile=user_profile,
                intervention_choices=intervention_choices_a,
                strategy_directives=strategy_directives_a,
                success_definition=success_definition,
            )
            state_b = engine.run_batch(
                decision_vars_b,
                user_profile=user_profile,
                intervention_choices=intervention_choices_b,
                strategy_directives=strategy_directives_b,
                success_definition=success_definition,
            )
            return state_a, state_b
        finally:
            engine.close()
