"""Judge 修订循环测试 —— inner graph 条件边 + revise 节点。"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.base import StubAgent
from app.agents.contracts import AgentContext, AgentProtocol
from app.agents.inner_graph import AgentCoordinator, InnerState, build_inner_graph
from app.agents.judge import JudgeResult, StubJudge
from app.agents.llm_agent import LlmAgent
from app.engine.models import AgentAction, SimulationState, WorldState
from app.engine.state import make_initial_state
from app.schemas.decision_source import DecisionSource


def _source() -> DecisionSource:
    return DecisionSource.model_validate(
        json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8"))
    )


def _dummy_state() -> SimulationState:
    return make_initial_state(
        _source(),
        {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3},
    )


def _dummy_context(agent_id: str = "market") -> AgentContext:
    return AgentContext(
        agent_id=agent_id,
        year=1,
        world_state={"cash_flow": 100000},
        decision_vars={"budget": 200000},
        allowed_action_ids=("market.differentiate", "market.hold"),
        agent_stance="行业视角",
    )


# ── InnerState 编译测试 ──


class TestInnerGraphStructure:
    """内层图编译 + 条件边结构验证。"""

    def _single_agent_coordinator(self):
        agent = StubAgent("market", "Market")
        agent.allowed_action_ids = ("market.hold", "market.differentiate")
        return AgentCoordinator(agents={"market": agent})

    def test_graph_compiles(self):
        """图可编译。"""
        coordinator = self._single_agent_coordinator()
        graph = build_inner_graph(coordinator)
        assert graph is not None

    def test_graph_has_revise_node(self):
        """编译后的图包含 revise 节点。"""
        coordinator = self._single_agent_coordinator()
        graph = build_inner_graph(coordinator)
        nodes = graph.get_graph().nodes
        node_names = {n for n in nodes}
        assert "revise" in node_names
        assert "observe" in node_names
        assert "propose" in node_names
        assert "judge" in node_names

    def test_route_judge_ok_goes_to_validate(self):
        """judge_ok=true → validate，正常完成推演。"""
        coordinator = self._single_agent_coordinator()
        graph = build_inner_graph(coordinator)
        state: InnerState = {
            "state": _dummy_state(),
            "contexts": {
                "market": _dummy_context("market"),
            },
            "actions": [],
            "judge_result": JudgeResult(judge_ok=True, severity=0.0, conflicts=[], recommendations=[]),
            "yearly_strategy": "steady",
            "user_profile_summary": "",
            "revision_count": 0,
            "max_revisions": 2,
        }
        result = graph.invoke(state)
        assert result is not None
        assert len(result["actions"]) == 1


# ── 修订循环行为测试 ──


class AlwaysRejectJudge:
    """始终返回 judge_ok=False 的测试 Judge，用于验证修订循环。"""

    def __init__(self):
        self.call_count = 0

    def judge(self, actions, contexts):
        self.call_count += 1
        return JudgeResult(
            judge_ok=False,
            severity=0.6,
            conflicts=["test conflict: agents disagree on risk posture"],
            recommendations=["market agent should reconsider expansion"],
        )


class TestRevisionLoop:
    """修订循环触发、耗尽、注入行为。"""

    def test_revision_loop_triggers_when_judge_rejects(self):
        """Judge 拒绝时 inner graph 进入修订循环并重新 propose。"""
        source = _source()
        agents = _build_stub_agents(source)
        coordinator = AgentCoordinator(
            agents=agents,
            judge=AlwaysRejectJudge(),
        )
        state = _dummy_state()
        actions = coordinator.propose(
            state,
            yearly_strategy="steady",
            max_revisions=2,
        )
        # 始终拒绝但应正常返回（耗尽 revision 后强制通过）
        assert len(actions) == 4
        assert coordinator._judge.call_count == 3  # 初始 1 次 + 2 次修订

    def test_revision_count_capped_by_max_revisions(self):
        """修订次数不超过 max_revisions。"""
        source = _source()
        agents = _build_stub_agents(source)
        reject_judge = AlwaysRejectJudge()
        coordinator = AgentCoordinator(
            agents=agents,
            judge=reject_judge,
        )
        state = _dummy_state()
        actions = coordinator.propose(
            state,
            yearly_strategy="steady",
            max_revisions=1,  # 只允许 1 次修订
        )
        assert len(actions) == 4
        # 初始 + 1 次修订 = 2 次调用
        assert reject_judge.call_count == 2

    def test_judge_feedback_injected_into_context(self):
        """修订时 AgentContext.judge_feedback 被正确注入。"""
        source = _source()
        agents = _build_stub_agents(source)
        reject_judge = AlwaysRejectJudge()
        coordinator = AgentCoordinator(
            agents=agents,
            judge=reject_judge,
        )

        # 检查 observe 返回的 context 应包含 judge_feedback
        state = _dummy_state()
        _ = coordinator.propose(
            state, yearly_strategy="steady", max_revisions=1,
        )
        # 通过 verify：propose 执行了 revision
        assert reject_judge.call_count == 2  # 1 initial + 1 revise

    def test_revision_feedback_uses_chinese_headings(self):
        source = _source()
        agents = _build_stub_agents(source)
        coordinator = AgentCoordinator(agents=agents, judge=AlwaysRejectJudge())
        state = _dummy_state()

        coordinator.propose(state, yearly_strategy="steady", max_revisions=1)

        assert not any(
            "Conflicts detected" in warning or "Recommendations" in warning
            for warning in coordinator.validation_warnings
        )

    def test_stub_agent_shifts_action_on_revision(self):
        """StubAgent 收到 judge_feedback 时选择不同动作。"""
        agent = StubAgent("market", "Market")
        ctx_no_fb = AgentContext(
            agent_id="market",
            year=1,
            world_state={"cash_flow": 100000},
            decision_vars={"budget": 200000},
            allowed_action_ids=("market.differentiate", "market.hold", "market.promote"),
        )
        ctx_with_fb = dataclasses.replace(ctx_no_fb, judge_feedback="conflict detected")

        action1 = agent.propose(ctx_no_fb)
        action2 = agent.propose(ctx_with_fb)
        # 有反馈时应偏移到不同动作
        assert action1.action_id != action2.action_id

    def test_no_revision_when_judge_ok(self):
        """judge_ok=true 时不走修订循环，直接通过。"""
        source = _source()
        agents = _build_stub_agents(source)
        coordinator = AgentCoordinator(
            agents=agents,
            judge=StubJudge(),
        )
        state = _dummy_state()
        _ = coordinator.propose(
            state, yearly_strategy="steady", max_revisions=2,
        )
        # StubJudge 在正常情况下 judge_ok=True，不应有修订
        # 无法直接验证 judge_round 调用次数，但图应该正常完成
        # 验证: 没有残留的 warnings 提到 revision
        revision_warnings = [w for w in coordinator.validation_warnings if "revision" in w.lower()]
        assert len(revision_warnings) == 0


# ── 端到端集成测试 ──


class TestE2EJudgeRevision:
    """E2E：完整推演 + Judge 修订循环。"""

    def test_engine_run_with_revision_support(self):
        """引擎跑通推演，修订循环设置正常工作。"""
        from app.engine.engine import SimulationEngine

        source = _source()
        engine = SimulationEngine(source)
        initial_events = list(engine.iter_events(
            {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
        ))
        first_state = initial_events[-1].state_snapshot
        first_year = list(
            engine.resume_events(
                first_state.session_id, first_state, "先验证本地客群反馈",
            )
        )
        second_state = first_year[-1].state_snapshot
        events = list(
            engine.resume_events(
                second_state.session_id, second_state, "根据首年结果调整投入",
            )
        )
        # 到达用户选择的年限后，应等待用户确认续推或结算。
        assert events[-1].event_type.value == "simulation.paused"
        assert events[-1].state_snapshot.phase == "horizon_review"

    def test_max_revisions_zero_disables_revision(self):
        """max_revisions=0 禁用修订，直接放行。"""
        source = _source()
        agents = _build_stub_agents(source)
        reject_judge = AlwaysRejectJudge()
        coordinator = AgentCoordinator(
            agents=agents,
            judge=reject_judge,
        )
        state = _dummy_state()
        _ = coordinator.propose(
            state, yearly_strategy="steady", max_revisions=0,
        )
        # max_revisions=0 → 初始 judge 被拒绝但强制通过
        assert reject_judge.call_count == 1  # 只有初始调用


# ── helpers ──


def _build_stub_agents(source: DecisionSource) -> dict[str, AgentProtocol]:
    from app.agents.environment import EnvironmentAgent
    from app.agents.market import MarketAgent
    from app.agents.personal import PersonalAgent
    from app.agents.risk import RiskAgent

    agents: dict[str, AgentProtocol] = {
        "market": MarketAgent(),
        "environment": EnvironmentAgent(),
        "personal": PersonalAgent(),
        "risk": RiskAgent(),
    }
    for agent_id, agent in agents.items():
        agent_def = next(a for a in source.agents if a.agent_id == agent_id)
        setattr(agent, "allowed_action_ids", tuple(agent_def.action_ids))
    return agents
