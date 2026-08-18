from app.agents.conflict_resolution import resolve_next_round_constraints
from app.agents.contracts import AgentContext
from app.agents.inner_graph import AgentCoordinator
from app.agents.judge import JudgeResult
from app.engine.models import AgentAction, SimulationState, WorldState
from app.agents.llm_agent import LlmAgent
from unittest.mock import MagicMock


def _contexts() -> dict[str, AgentContext]:
    action_sets = {
        "market": ("market.differentiate", "market.hold"),
        "environment": ("environment.localize", "environment.monitor"),
        "personal": ("personal.stabilize", "personal.defer"),
        "risk": ("risk.contain", "risk.insure"),
    }
    return {
        agent_id: AgentContext(
            agent_id=agent_id,
            year=1,
            world_state={"cash_flow": 100000},
            decision_vars={},
            allowed_action_ids=allowed,
        )
        for agent_id, allowed in action_sets.items()
    }


def _conflicting_actions() -> list[AgentAction]:
    return [
        AgentAction(agent_id="market", action_id="market.differentiate", reason="扩大曝光", confidence=0.7, position="support"),
        AgentAction(agent_id="environment", action_id="environment.localize", reason="调整本地方案", confidence=0.7, position="conditional"),
        AgentAction(agent_id="personal", action_id="personal.stabilize", reason="投入更多精力", confidence=0.7, position="conditional"),
        AgentAction(agent_id="risk", action_id="risk.contain", reason="控制损失", confidence=0.7, position="oppose"),
    ]


def test_high_conflict_narrows_next_round_action_boundaries_in_chinese():
    constraints = resolve_next_round_constraints(
        JudgeResult(
            judge_ok=False,
            severity=0.7,
            conflicts=["市场扩张与风险控制存在冲突"],
            recommendations=["先用小预算验证"],
        ),
        _conflicting_actions(),
        _contexts(),
    )

    assert constraints["market"].allowed_action_ids == ["market.hold"]
    assert constraints["environment"].allowed_action_ids == ["environment.monitor"]
    assert constraints["personal"].allowed_action_ids == ["personal.defer"]
    assert constraints["risk"].allowed_action_ids == ["risk.contain", "risk.insure"]
    assert all("market." not in item.instruction for item in constraints.values())
    assert all("risk." not in item.summary for item in constraints.values())
    assert all(any("\u4e00" <= char <= "\u9fff" for char in item.instruction) for item in constraints.values())


def test_observe_applies_persisted_constraints_to_action_whitelist():
    contexts = _contexts()
    constraints = resolve_next_round_constraints(
        JudgeResult(judge_ok=False, severity=0.7, conflicts=["策略冲突"], recommendations=[]),
        _conflicting_actions(),
        contexts,
    )
    state = SimulationState(
        scenario_id="example",
        world_state=WorldState(cash_flow=100000),
        agent_constraints=constraints,
    )
    coordinator = AgentCoordinator(agents={})

    applied = coordinator.apply_constraints_to_contexts(contexts, state.agent_constraints)

    assert applied["market"].allowed_action_ids == ("market.hold",)
    assert applied["environment"].allowed_action_ids == ("environment.monitor",)
    assert applied["personal"].allowed_action_ids == ("personal.defer",)
    assert "小范围验证" in applied["market"].constraint_note


def test_llm_prompt_contains_chinese_hard_constraint():
    agent = LlmAgent(
        agent_id="market",
        name="市场智能体",
        stance="关注需求验证",
        goal="验证市场需求",
        allowed_action_ids=("market.hold",),
        action_descriptions={"market.hold": "用小范围活动验证转化"},
        llm=MagicMock(),
    )
    context = AgentContext(
        agent_id="market",
        year=2,
        world_state={"cash_flow": 100000},
        decision_vars={},
        allowed_action_ids=("market.hold",),
        constraint_note="本轮只保留小范围验证，暂不扩大投入。",
    )

    messages = agent._build_messages(context)
    prompt = "\n".join(str(message.content) for message in messages)

    assert "本轮硬约束" in prompt
    assert "只保留小范围验证" in prompt
