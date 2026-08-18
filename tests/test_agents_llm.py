"""LlmAgent 单元测试 — 仅测 prompt 构建和响应解析，不调真实 API"""

import json
import threading
import time
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from app.agents.contracts import AgentContext
from app.agents.llm_agent import LlmAgent
from app.engine.models import AgentAction


def make_context(agent_id="market", year=1, allowed=("market.differentiate", "market.hold")):
    return AgentContext(
        agent_id=agent_id,
        year=year,
        world_state={"cash_flow": 180000, "customer_flow": 100, "competition_count": 47, "monthly_profit": 0, "payback_ratio": 0},
        decision_vars={"budget": 200000, "city": "hangzhou", "industry": "milk_tea"},
        allowed_action_ids=allowed,
    )


def test_llm_agent_parses_valid_json_response():
    """LLM 返回合法 JSON → 正确解析为 AgentAction"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.differentiate", "reason": "need growth"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow customers",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate to grow demand",
            "market.hold": "Hold and collect data",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.agent_id == "market"
    assert result.action_id == "market.differentiate"
    assert result.reason == "need growth"
    # mock 未返回 confidence 时走默认 0.7（LLM 自评缺失的保守值）
    assert result.confidence == 0.7


def test_llm_agent_parses_user_readable_decision_sections():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content=json.dumps({
            "action_id": "market.hold",
            "recommendation": "先用一个渠道验证目标客群。",
            "reason": "当前转化基础仍需验证，过早铺开会稀释预算。",
            "alternatives": ["保留现有渠道并跟踪复购", "先做小规模用户访谈"],
            "objection": "不建议在验证前追加大额投放。",
            "stop_condition": "连续两个复盘周期没有有效转化时暂停扩量。",
            "confidence": 82,
            "position": "有条件支持",
        }, ensure_ascii=False)
    )
    agent = LlmAgent(
        agent_id="market", name="市场智能体",
        stance="关注需求", goal="验证市场",
        allowed_action_ids=("market.hold",),
        action_descriptions={"market.hold": "控制投入"},
        llm=mock_llm,
    )

    result = agent.propose(make_context(allowed=("market.hold",)))

    assert result.recommendation == "先用一个渠道验证目标客群。"
    assert result.alternatives == ["保留现有渠道并跟踪复购", "先做小规模用户访谈"]
    assert result.objection == "不建议在验证前追加大额投放。"
    assert result.stop_condition == "连续两个复盘周期没有有效转化时暂停扩量。"
    assert result.position == "conditional"


def test_personal_agent_treats_strategy_as_preference_and_returns_clear_advice():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content=json.dumps({
            "action_id": "personal.stabilize",
            "recommendation": "先用三个月验证副业，再决定是否扩大投入。",
            "reason": "你的现金缓冲有限且每周可投入时间不足，直接扩大计划会挤压现有收入。",
            "key_factors": ["现金缓冲有限", "每周可投入时间不足"],
            "next_actions": ["本周确定每周 10 小时的验证时段", "三个月后复盘收入和投入"],
            "stop_condition": "连续两周无法完成计划时，缩小验证范围。",
            "uncertainty": "尚未确认现有收入是否稳定。",
            "confidence": 78,
            "position": "有条件支持",
        }, ensure_ascii=False)
    )
    agent = LlmAgent(
        agent_id="personal",
        name="个人智能体",
        stance="关注个人资源",
        goal="让计划可持续",
        allowed_action_ids=("personal.stabilize",),
        action_descriptions={"personal.stabilize": "控制执行负荷"},
        llm=mock_llm,
    )
    context = AgentContext(
        agent_id="personal",
        year=1,
        world_state={"cash_flow": 80000, "customer_flow": 30, "competition_count": 40, "monthly_profit": -3000, "payback_ratio": 0.1},
        decision_vars={"budget": 200000},
        allowed_action_ids=("personal.stabilize",),
        yearly_strategy="aggressive",
        user_profile_summary="可用现金 8 万元；每周只能投入 10 小时；现有收入尚未稳定。",
        rag_status="empty",
    )

    result = agent.propose(context)
    prompt = "\n".join(
        str(message.content) for message in mock_llm.invoke.call_args[0][0]
    )

    assert "可用现金 8 万元" in prompt
    assert "偏好" in prompt
    assert result.key_factors == ["现金缓冲有限", "每周可投入时间不足"]
    assert result.next_actions[0].startswith("本周")
    assert result.uncertainty == "尚未确认现有收入是否稳定。"
    assert result.rag_status == "empty"
    assert result.rag_sources == []


def test_llm_agent_rejects_undeclared_action():
    """LLM 返回不在 allowed 里的 action → 降级为第一个 allowed action"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.destroy", "reason": "burn it all"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.differentiate"  # fallback


def test_llm_agent_handles_markdown_wrapped_json():
    """LLM 返回 markdown 包裹的 JSON → 正确提取"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='```json\n{"action_id": "market.hold", "reason": "play safe"}\n```'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.hold"
    assert result.reason == "play safe"


def test_llm_agent_handles_plain_text_json():
    """LLM 返回带前缀文字的 JSON → 正确提取"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='I choose to differentiate.\n\n{"action_id": "market.differentiate", "reason": "growth needed"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.differentiate"


def test_llm_agent_fallback_on_garbage():
    """LLM 返回完全不可解析的内容 → fallback 到第一个 allowed action"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="I refuse to choose!")
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.differentiate"  # fallback
    # 回退文案为本地化中文（"回退"），不再依赖英文 "fallback"
    assert "回退" in result.reason


def test_llm_agent_prompt_uses_qualitative_state_without_raw_values():
    """模型只收到状态趋势，不能把内部绝对数值复述给用户。"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"action_id": "market.hold", "reason": "ok"}')
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    agent.propose(make_context())
    messages = mock_llm.invoke.call_args[0][0]
    system_text = str(messages[0].content)
    text = str(messages[1].content)

    assert "不得复述世界状态中的原始数值" in system_text
    assert "客流量" in text
    assert "获客仍在爬坡" in text
    assert "180000" not in text
    assert "47" not in text


def test_llm_agent_prompt_separates_scenario_target_from_profile_city():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.hold", "reason": "ok"}'
    )
    agent = LlmAgent(
        agent_id="market",
        name="Market Agent",
        stance="customer focused",
        goal="grow customers",
        allowed_action_ids=("market.hold",),
        action_descriptions={"market.hold": "Hold"},
        llm=mock_llm,
    )
    context = make_context(allowed=("market.hold",))
    context = context.__class__(
        **{
            **context.__dict__,
            "scenario_title": "长沙买房决策推演",
            "decision_vars": {"city": "长沙", "budget": 2000000},
            "latest_decision": "在长沙买房",
            "user_profile_summary": "现居杭州，家庭成员两人",
        }
    )

    agent.propose(context)
    text = str(mock_llm.invoke.call_args[0][0])

    assert "长沙买房决策推演" in text
    assert "长沙" in text
    assert "现居杭州" in text
    assert "不能替换" in text


def test_llm_agent_separates_target_city_from_profile_city():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.hold", "reason": "ok"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.hold",),
        action_descriptions={"market.hold": "Hold"},
        llm=mock_llm,
    )
    context = make_context(allowed=("market.hold",))
    context = context.__class__(
        **{
            **context.__dict__,
            "decision_vars": {**context.decision_vars, "city": "长沙"},
            "user_profile_summary": "基本：现居杭州",
        }
    )

    agent.propose(context)
    text = str(mock_llm.invoke.call_args[0][0])
    assert "长沙" in text
    assert "现居杭州" in text
    assert "推演目标城市" in text


def test_llm_agent_context_mismatch_raises():
    """context.agent_id 不匹配 → ValueError"""
    mock_llm = MagicMock()
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="x", goal="x",
        allowed_action_ids=("market.differentiate",),
        action_descriptions={"market.differentiate": "d"},
        llm=mock_llm,
    )
    ctx = make_context(agent_id="risk")
    try:
        agent.propose(ctx)
        assert False, "should have raised"
    except ValueError as e:
        assert "mismatch" in str(e).lower()


def test_llm_agent_no_allowed_actions_raises():
    """空 allowed_action_ids → ValueError"""
    mock_llm = MagicMock()
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="x", goal="x",
        allowed_action_ids=(),
        action_descriptions={},
        llm=mock_llm,
    )
    ctx = make_context(allowed=())
    try:
        agent.propose(ctx)
        assert False, "should have raised"
    except ValueError as e:
        assert "no allowed" in str(e).lower()


# --- build_agents 集成测试 ---


from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from app.agents.contracts import AgentProtocol
from app.agents.inner_graph import AgentCoordinator, build_agents
from app.agents.llm_agent import LlmAgent
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


class _DelayedAgentLlm:
    def __init__(self):
        self._lock = threading.Lock()
        self._active = 0
        self.max_active = 0

    def invoke(self, messages):
        system_prompt = str(messages[0].content)
        responses = {
            "market": "market.differentiate",
            "environment": "environment.localize",
            "personal": "personal.stabilize",
            "risk": "risk.insure",
        }
        agent_id = next(agent_id for agent_id in responses if agent_id in system_prompt)
        with self._lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            time.sleep(0.05)
            return AIMessage(
                content=(
                    '{"action_id": "'
                    + responses[agent_id]
                    + '", "reason": "当前决策需要结合本角色职责评估", "confidence": 80}'
                )
            )
        finally:
            with self._lock:
                self._active -= 1


def test_build_agents_with_llm_returns_llm_agents():
    """use_stub=False + mock LLM → 返回 4 个 LlmAgent 实例"""
    source = ScenarioLoader("scenarios").load("milktea_startup")
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.differentiate", "reason": "test"}'
    )
    agents = build_agents(source, use_stub=False, fast_llm=mock_llm)
    assert set(agents) == {"market", "environment", "personal", "risk"}
    assert all(isinstance(a, LlmAgent) for a in agents.values())
    assert agents["market"].llm is mock_llm


def test_coordinator_proposes_four_agents_concurrently():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    delayed_llm = _DelayedAgentLlm()
    coordinator = AgentCoordinator(
        build_agents(source, use_stub=False, fast_llm=delayed_llm)
    )
    state = make_initial_state(source, {"budget": 200000})

    contexts = coordinator.observe(state)
    actions = coordinator.propose_actions(contexts)

    assert len(actions) == 4
    assert delayed_llm.max_active >= 2


def test_llm_agent_coordinator_integration():
    """LlmAgent 可通过 AgentCoordinator.propose 正常调用"""
    source = ScenarioLoader("scenarios").load("milktea_startup")

    mock_llm = MagicMock()
    responses = {
        "market": '{"action_id": "market.differentiate", "reason": "grow"}',
        "environment": '{"action_id": "environment.localize", "reason": "adapt"}',
        "personal": '{"action_id": "personal.stabilize", "reason": "stable"}',
        "risk": '{"action_id": "risk.contain", "reason": "contain"}',
    }

    def side_effect(messages):
        sys_text = str(messages[0].content)
        for aid in responses:
            if aid in sys_text:
                return AIMessage(content=responses[aid])
        return AIMessage(content='{"action_id": "market.hold", "reason": "default"}')

    mock_llm.invoke.side_effect = side_effect

    agents = build_agents(source, use_stub=False, fast_llm=mock_llm)
    coordinator = AgentCoordinator(agents)
    state = make_initial_state(source, {"budget": 200000})
    actions = coordinator.propose(state)

    assert len(actions) == 4
    assert {a.agent_id for a in actions} == {"market", "environment", "personal", "risk"}
    action_map = {a.agent_id: a.action_id for a in actions}
    for agent_def in source.agents:
        assert action_map[agent_def.agent_id] in agent_def.action_ids


def test_build_agents_without_llm_raises():
    """use_stub=False 但不传 fast_llm → ValueError"""
    source = ScenarioLoader("scenarios").load("milktea_startup")
    try:
        build_agents(source, use_stub=False, fast_llm=None)
        assert False, "should have raised"
    except ValueError as e:
        assert "fast_llm" in str(e).lower()


def test_llm_action_records_model_generation():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.hold", "reason": "围绕当前目标控制投入", "confidence": 80}'
    )
    agent = LlmAgent(
        agent_id="market",
        name="市场顾问",
        stance="分析机会",
        goal="提高成功概率",
        allowed_action_ids=("market.hold",),
        action_descriptions={"market.hold": "控制投入"},
        llm=mock_llm,
    )

    result = agent.propose(make_context(allowed=("market.hold",)))

    assert result.generation_source == "llm"
    assert result.llm_called is True
