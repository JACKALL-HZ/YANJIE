"""Deterministically reconcile validated agent actions into a startup ledger decision."""

from dataclasses import dataclass

from app.engine.models import AgentAction


_EXIT_KEYWORDS = ("闭店", "转让", "退出", "关店", "清算")


@dataclass(frozen=True)
class StartupDecision:
    decision_id: str
    reason: str
    supporting_actions: list[str]


def select_startup_decision(
    actions: list[AgentAction],
    user_message: str,
    yearly_strategy: str,
) -> StartupDecision:
    """Choose a ledger action from validated multi-agent recommendations.

    A direct user exit decision remains authoritative. Otherwise the selector
    only considers declared AgentAction identifiers and uses strategy as a
    deterministic tie-breaker rather than as a replacement for agent input.
    """
    supporting_actions = [action.action_id for action in actions]
    message = user_message.strip()
    if any(keyword in message for keyword in _EXIT_KEYWORDS):
        return StartupDecision(
            decision_id="transfer_or_close",
            reason="用户明确提出退出经营，账本进入转让或闭店分支。",
            supporting_actions=supporting_actions,
        )

    action_ids = set(supporting_actions)
    defensive_score = sum(
        action_id in action_ids
        for action_id in (
            "market.hold",
            "environment.monitor",
            "personal.defer",
            "risk.contain",
        )
    )
    growth_score = sum(
        action_id in action_ids
        for action_id in (
            "market.differentiate",
            "environment.localize",
            "personal.stabilize",
            "risk.insure",
        )
    )

    if defensive_score >= 3 and defensive_score > growth_score:
        return StartupDecision(
            decision_id="defensive",
            reason="多角色共识优先控制投入和执行负荷，采用控速推进。",
            supporting_actions=supporting_actions,
        )
    if growth_score >= 3 and growth_score > defensive_score:
        return StartupDecision(
            decision_id="precision_breakthrough",
            reason="多角色共识支持在可验证条件下集中突破，采用精准突破。",
            supporting_actions=supporting_actions,
        )

    strategy_decision = {
        "aggressive": "precision_breakthrough",
        "conservative": "defensive",
    }.get(yearly_strategy, "steady_growth")
    return StartupDecision(
        decision_id=strategy_decision,
        reason="角色建议未形成单向多数，按用户年度策略作为可复盘的同票裁决。",
        supporting_actions=supporting_actions,
    )
