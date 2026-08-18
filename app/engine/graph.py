from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.engine.models import AgentAction, SimulationState
from app.engine.nodes import (
    append_year,
    apply_supplied_actions,
    check_ending,
    prepare_state,
)
from app.schemas.decision_source import DecisionSource


class OuterState(TypedDict):
    """LangGraph 外层状态：承载推演状态、Agent 动作与中间转换结果。

    SimulationState 是 pydantic 对象，LangGraph 在此不挂 checkpointer，
    直接持有 Python 对象（与现有 engine 行为一致）。
    """

    state: SimulationState
    actions: list[AgentAction]
    transition: Any
    ending: Any


def build_outer_graph(source: DecisionSource, checkpointer=None):
    """编译外层 StateGraph：prepare → apply_actions → check_ending → append_year。

    节点直接调用 nodes.py 的纯函数，不重写业务逻辑。

    checkpointer 可选：传入 LangGraph checkpointer（SqliteSaver/PostgresSaver/MemorySaver）
    启用后支持断点续推、状态查询与增量快照。
    """

    def _prepare(s: OuterState) -> dict:
        return {"state": prepare_state(s["state"])}

    def _apply(s: OuterState) -> dict:
        return {
            "transition": apply_supplied_actions(
                s["state"], s["actions"], source
            )
        }

    def _check(s: OuterState) -> dict:
        year = s["state"].year + 1
        return {
            "ending": check_ending(
                s["transition"], year, source,
                success_definition=s["state"].success_definition,
            )
        }

    def _append(s: OuterState) -> dict:
        year = s["state"].year + 1
        return {
            "state": append_year(
                s["state"],
                year,
                s["actions"],
                s["transition"],
                s["ending"],
            )
        }

    g = StateGraph(OuterState)
    g.add_node("prepare", _prepare)
    g.add_node("apply_actions", _apply)
    g.add_node("check_ending", _check)
    g.add_node("append_year", _append)
    g.set_entry_point("prepare")
    g.add_edge("prepare", "apply_actions")
    g.add_edge("apply_actions", "check_ending")
    g.add_edge("check_ending", "append_year")
    g.add_edge("append_year", END)
    return g.compile(checkpointer=checkpointer)
