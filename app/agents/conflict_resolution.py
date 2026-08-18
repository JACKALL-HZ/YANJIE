"""将裁判识别到的分歧转为下一轮可执行的动作边界。"""

from collections.abc import Mapping

from app.agents.contracts import AgentContext
from app.agents.judge import JudgeResult
from app.engine.models import AgentAction, AgentConstraint


_DEFENSIVE_SUFFIXES = ("hold", "monitor", "defer", "contain", "insure", "pause")

_CONSTRAINT_COPY = {
    "market": (
        "本轮只保留小范围验证，先确认转化效果，不扩大投放或追加高额预算。",
        "市场侧先做小范围验证，暂不扩大投入。",
    ),
    "environment": (
        "本轮优先核实外部条件、成本和合规要求，不新增高成本调整。",
        "环境侧先核实外部条件，不新增高成本调整。",
    ),
    "personal": (
        "本轮只安排现有时间和团队能够承接的动作，不新增超负荷任务。",
        "个人侧先保证执行能力，不增加超负荷安排。",
    ),
    "risk": (
        "继续核验预算上限、止损线和不可逆投入，并保留必要的风险防护动作。",
        "风险侧继续审查预算上限和止损条件。",
    ),
}


def _is_high_conflict(result: JudgeResult, actions: list[AgentAction]) -> bool:
    if not result.conflicts:
        return False
    return result.severity >= 0.5 or any(
        action.agent_id == "risk" and action.position == "oppose"
        for action in actions
    )


def _defensive_actions(allowed_action_ids: tuple[str, ...]) -> list[str]:
    defensive = [
        action_id
        for action_id in allowed_action_ids
        if action_id.rsplit(".", 1)[-1] in _DEFENSIVE_SUFFIXES
    ]
    if defensive:
        return defensive
    # 场景自定义动作没有统一命名时，最后一个动作约定为低投入/延后候选。
    return list(allowed_action_ids[-1:])


def resolve_next_round_constraints(
    result: JudgeResult,
    actions: list[AgentAction],
    contexts: Mapping[str, AgentContext],
) -> dict[str, AgentConstraint]:
    """将严重分歧收敛成下一轮智能体必须遵守的动作白名单。"""
    if not _is_high_conflict(result, actions):
        return {}

    constraints: dict[str, AgentConstraint] = {}
    for agent_id, context in contexts.items():
        instruction, summary = _CONSTRAINT_COPY.get(
            agent_id,
            ("本轮优先采用低投入、可验证且可撤回的动作。", "本轮优先采用低投入验证。"),
        )
        allowed = list(context.allowed_action_ids)
        if agent_id != "risk":
            allowed = _defensive_actions(context.allowed_action_ids)
        constraints[agent_id] = AgentConstraint(
            allowed_action_ids=allowed,
            instruction=instruction,
            summary=summary,
        )
    return constraints
