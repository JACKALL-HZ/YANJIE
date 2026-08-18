from app.engine.models import AgentAction
from app.engine.startup_decision import select_startup_decision


def _actions(
    market: str,
    environment: str,
    personal: str,
    risk: str,
) -> list[AgentAction]:
    return [
        AgentAction(agent_id="market", action_id=market, reason="市场判断", confidence=0.8),
        AgentAction(agent_id="environment", action_id=environment, reason="环境判断", confidence=0.8),
        AgentAction(agent_id="personal", action_id=personal, reason="个人判断", confidence=0.8),
        AgentAction(agent_id="risk", action_id=risk, reason="风险判断", confidence=0.8),
    ]


def test_defensive_agent_consensus_selects_defensive_ledger_decision():
    selected = select_startup_decision(
        _actions("market.hold", "environment.monitor", "personal.defer", "risk.contain"),
        "继续经营，但必须控制投入",
        "steady",
    )

    assert selected.decision_id == "defensive"
    assert selected.supporting_actions == ["market.hold", "environment.monitor", "personal.defer", "risk.contain"]


def test_growth_agent_consensus_selects_precision_breakthrough_ledger_decision():
    selected = select_startup_decision(
        _actions("market.differentiate", "environment.localize", "personal.stabilize", "risk.insure"),
        "先完成渠道验证后扩大投入",
        "steady",
    )

    assert selected.decision_id == "precision_breakthrough"


def test_explicit_exit_intent_overrides_agent_consensus():
    selected = select_startup_decision(
        _actions("market.differentiate", "environment.localize", "personal.stabilize", "risk.insure"),
        "我决定转让并闭店",
        "aggressive",
    )

    assert selected.decision_id == "transfer_or_close"
