from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.engine.interventions import (
    apply_intervention,
    find_pending_intervention,
)
from app.engine.models import InterventionRecord, SimulationState
from app.schemas.decision_source import DecisionSource


class InterventionState(TypedDict):
    """LangGraph 干预状态：推演状态、外部提供的选择、待决干预。

    choice 为 None 且存在待决干预时，节点调用 interrupt() 暂停，
    由 engine 捕获后 yield INTERVENTION_PENDING + SIMULATION_PAUSED 并结束本轮。
    """

    state: SimulationState
    choice: Any  # str | None
    pending: Any  # PendingIntervention | None


def build_intervention_graph(source: DecisionSource, checkpointer=None):
    """编译干预 StateGraph：关键节点干预用 interrupt() 实现暂停/恢复。

    保留现有 interventions.py 纯函数逻辑（find_pending / apply_intervention），
    仅在编排层引入 LangGraph + interrupt。

    checkpointer 可选：启用后支持 Command(resume=...) 原生恢复。
    """

    def _check_and_apply(s: InterventionState) -> dict:
        state: SimulationState = s["state"]
        used_counts: dict[str, int] = {}
        for item in state.interventions:
            used_counts[item.rule_id] = used_counts.get(item.rule_id, 0) + 1
        pending = find_pending_intervention(
            state.world_state,
            state.year,
            source,
            used_counts,
        )
        if pending is None:
            return {"state": state, "pending": None}

        choice = s.get("choice")
        if choice is None:
            # 暂停，等待外部提供选择（MVP-0 由 engine 捕获后结束本轮）
            interrupt(pending.model_dump())

        transition = apply_intervention(
            state.world_state, pending, choice, source
        )
        new_state = state.model_copy(deep=True)
        new_state.world_state = transition.world_state
        new_state.pending_intervention = None
        new_state.phase = "simulating"
        record = InterventionRecord(
            rule_id=pending.rule_id,
            year=pending.year,
            choice=choice,
            effects=transition.effects[0].effects,
        )
        new_state.interventions.append(record)
        if new_state.timeline:
            last = new_state.timeline[-1].model_copy(deep=True)
            last.world_state = new_state.world_state
            last.interventions.append(record)
            for metric, delta in record.effects.items():
                last.state_diff[metric] = last.state_diff.get(metric, 0) + delta
            new_state.timeline[-1] = last
        return {"state": new_state, "pending": None}

    g = StateGraph(InterventionState)
    g.add_node("check_and_apply", _check_and_apply)
    g.set_entry_point("check_and_apply")
    g.add_edge("check_and_apply", END)
    return g.compile(checkpointer=checkpointer)
