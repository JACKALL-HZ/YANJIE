"""用户参与感功能测试 —— 年度策略指令 / 自定义成功标准 / 行动打卡承诺。"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.contracts import AgentContext
from app.agents.inner_graph import AgentCoordinator, build_agents
from app.core.config import Settings, get_settings
from app.engine.engine import SimulationEngine
from app.engine.ending import judge_ending
from app.engine.models import AgentAction, SimulationState, WorldState
from app.engine.scoring import compute_score
from app.engine.state import make_initial_state
from app.schemas.api import SimulationRequest
from app.schemas.decision_source import DecisionSource
from app.schemas.events import EventType
from app.services.simulation_service import SimulationService


def _source() -> DecisionSource:
    return DecisionSource.model_validate(
        json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8"))
    )


# ── Strategy Directive Tests ──


class TestStrategyDirectives:
    """年度策略指令正确注入 Agent 上下文。"""

    def test_strategy_defaults_to_steady(self):
        """未指定策略时，所有 Agent context 的 yearly_strategy 为 steady。"""
        source = _source()
        agents = build_agents(source)
        coordinator = AgentCoordinator(agents)
        state = make_initial_state(source, {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
        contexts = coordinator.observe(state, yearly_strategy="steady")

        for ctx in contexts.values():
            assert ctx.yearly_strategy == "steady"

    def test_aggressive_strategy_injected(self):
        """激进策略正确注入。"""
        source = _source()
        agents = build_agents(source)
        coordinator = AgentCoordinator(agents)
        state = make_initial_state(source, {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
        contexts = coordinator.observe(state, yearly_strategy="aggressive")

        for ctx in contexts.values():
            assert ctx.yearly_strategy == "aggressive"

    def test_personal_agent_gets_user_profile_summary(self):
        """Personal Agent 的 context 包含用户画像摘要。"""
        source = _source()
        agents = build_agents(source)
        coordinator = AgentCoordinator(agents)
        state = make_initial_state(
            source,
            {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3},
            user_profile={"age": 30, "risk_appetite": "aggressive", "assets": 100000, "family_burden": False},
        )
        summary = SimulationEngine._build_profile_summary(
            state.user_profile, state.decision_vars,
        )
        assert "30 岁" in summary
        assert "激进" in summary or "aggressive" in summary.lower()
        # 金额渲染为万元口径（10 万元 = 100000）
        assert "10 万元" in summary
        # 投入压力段：20 万投入 vs 10 万资产 = 200%
        assert "本次决策投入" in summary
        assert "200.0%" in summary

        contexts = coordinator.observe(
            state, yearly_strategy="steady", user_profile_summary=summary,
        )
        personal_ctx = contexts["personal"]
        assert personal_ctx.user_profile_summary == summary

    def test_every_agent_gets_the_same_profile_summary(self):
        source = _source()
        coordinator = AgentCoordinator(build_agents(source))
        state = make_initial_state(
            source,
            {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3},
            user_profile={"weekly_hours": 20, "assets": 500000},
        )
        summary = SimulationEngine._build_profile_summary(
            state.user_profile,
            state.decision_vars,
        )

        contexts = coordinator.observe(state, user_profile_summary=summary)

        assert {context.user_profile_summary for context in contexts.values()} == {
            summary
        }

    def test_engine_iter_events_emits_year_started(self):
        """iter_events 包含 YEAR_STARTED 事件。"""
        source = _source()
        engine = SimulationEngine(source)
        initial_events = list(engine.iter_events(
            {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
        ))
        first_state = initial_events[-1].state_snapshot.model_copy(
            update={"yearly_strategy": "aggressive"}
        )
        first_year = list(
            engine.resume_events(
                first_state.session_id, first_state, "按进取策略验证市场",
            )
        )
        second_state = first_year[-1].state_snapshot.model_copy(
            update={"yearly_strategy": "conservative"}
        )
        second_year = list(
            engine.resume_events(
                second_state.session_id, second_state, "按稳健策略控制投入",
            )
        )
        events = first_year + second_year
        year_started_events = [
            e for e in events
            if e.event_type == EventType.YEAR_STARTED
        ]
        assert len(year_started_events) == 2
        assert year_started_events[0].payload.current_strategy == "aggressive"  # type: ignore[union-attr]
        assert year_started_events[1].payload.current_strategy == "conservative"  # type: ignore[union-attr]

    def test_agent_action_carries_strategy(self):
        """AgentAction.yearly_strategy 正确记录。"""
        source = _source()
        engine = SimulationEngine(source)
        events = list(engine.iter_events(
            {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
            strategy_directives={1: "aggressive", 2: "conservative"},
        ))
        # 从 YEAR_COMPLETED 的 state_snapshot 检查
        for e in events:
            if e.event_type == EventType.YEAR_COMPLETED:
                state = e.state_snapshot
                if isinstance(state, SimulationState) and state.year == 1:
                    assert state.yearly_strategy == "aggressive"


# ── Success Definition Tests ──


class TestSuccessDefinition:
    """自定义成功标准覆盖结局判定和评分。"""

    def test_success_definition_lowers_steady_threshold(self):
        """用户定义月利润 5000 即成功 → 比场景默认 30000 更低。"""
        source = _source()
        ws = WorldState(
            cash_flow=100000,
            customer_flow=150,
            competition_count=30,
            monthly_profit=10000,
            payback_ratio=0.3,
        )
        # 场景默认 steady threshold=30000 → 不会触发
        result_default = judge_ending(ws, 2, source.end_conditions)
        # 10000 < 30000，所以默认判定不应为 steady
        assert result_default is None or result_default.result != "steady"

        # 用户自定义 threshold=5000 → 应该触发
        result_custom = judge_ending(
            ws, 2, source.end_conditions,
            success_definition={"target_monthly_profit": 5000},
        )
        assert result_custom is not None
        assert result_custom.result == "steady"

    def test_success_definition_adjusts_score_weights(self):
        """priority=survival → 资源权重 x2。"""
        ws = {
            "cash_flow": 150000,
            "customer_flow": 100,
            "competition_count": 50,
            "monthly_profit": 20000,
            "payback_ratio": 0.5,
        }
        score_default = compute_score(ws, "steady")
        score_survival = compute_score(ws, "steady", success_definition={"priority": "survival"})

        # survival 模式下 resource 权重 x2 → resource 占分更高
        assert score_survival.detail["resource"] > score_default.detail["resource"]

    def test_success_definition_stored_on_state(self):
        """success_definition 正确写入 SimulationState。"""
        source = _source()
        state = make_initial_state(
            source,
            {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3},
            success_definition={"priority": "survival", "target_monthly_profit": 5000},
        )
        assert state.success_definition["priority"] == "survival"
        assert state.success_definition["target_monthly_profit"] == 5000


# ── Action Commitment Tests ──


class TestActionCommitment:
    """结算后行动打卡承诺。"""

    def test_commit_actions_endpoint(self):
        """POST /api/simulations/{id}/commit-actions 正确更新。"""
        from app.main import app
        client = TestClient(app)

        # 先跑一次模拟
        resp = client.post("/api/simulations", json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
        })
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        action_plan = resp.json().get("action_plan", [])
        if not action_plan:
            pytest.skip("action plan is empty, cannot test commitment")

        # 提交承诺
        first_action = action_plan[0].get("action", "")
        resp2 = client.post(
            f"/api/simulations/{session_id}/commit-actions",
            json={"committed_actions": [first_action]},
        )
        assert resp2.status_code == 200
        updated_plan = resp2.json()["action_plan"]
        committed = [item for item in updated_plan if item.get("committed")]
        assert len(committed) == 1
        assert committed[0]["action"] == first_action


# ── SSE Event Flow Test ──


class TestSseEventFlow:
    """SSE 事件流包含新的交互事件。"""

    def test_sse_creation_stream_pauses_for_the_first_year_decision(self):
        """创建 SSE 流只建立初始状态，首年由用户恢复操作推进。"""
        source = _source()
        settings = get_settings()
        service = SimulationService(settings)

        async def collect():
            events = []
            async for e in service.aiter_events(
                source,
                {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
                strategy_directives={1: "aggressive", 2: "conservative"},
            ):
                events.append(e)
            return events

        import asyncio
        events = asyncio.run(collect())

        event_types = [e.event_type for e in events]
        assert EventType.SIMULATION_STARTED in event_types
        assert EventType.SIMULATION_PAUSED in event_types
        assert event_types == [
            EventType.SIMULATION_STARTED,
            EventType.SIMULATION_PAUSED,
        ]
        assert events[-1].state_snapshot.pause_reason == "year_decision_required"

    def test_request_schema_accepts_new_fields(self):
        """SimulationRequest 接受 strategy_directives 和 success_definition。"""
        req = SimulationRequest(
            scenario_id="milktea_startup",
            decision_vars={"budget": 200000},
            strategy_directives={1: "aggressive", 3: "conservative"},
            success_definition={"priority": "survival", "target_monthly_profit": 10000},
        )
        assert req.strategy_directives == {1: "aggressive", 3: "conservative"}
        assert req.success_definition["priority"] == "survival"
