"""Judge 回合校验测试 — 跨 Agent 冲突检测"""
import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.agents.contracts import AgentContext
from app.agents.inner_graph import build_judge
from app.agents.judge import JudgeAgent, JudgeResult, StubJudge
from app.engine.models import AgentAction


# ========================================================================== JudgeResult

def test_judge_result_ok_default():
    r = JudgeResult(judge_ok=True, severity=0.0, conflicts=[], recommendations=[])
    assert r.judge_ok is True
    assert r.severity == 0.0
    assert r.conflicts == []


def test_judge_result_has_conflict():
    r = JudgeResult(
        judge_ok=False,
        severity=0.7,
        conflicts=["market expands but risk contains"],
        recommendations=["reduce aggression or increase protection"],
    )
    assert not r.judge_ok
    assert r.severity > 0.5
    assert len(r.conflicts) == 1


# ========================================================================== StubJudge（规则判定）

@pytest.fixture
def sample_actions():
    return [
        AgentAction(agent_id="market", action_id="market.differentiate", reason="need growth", confidence=0.8),
        AgentAction(agent_id="environment", action_id="environment.localize", reason="adapt to city", confidence=0.8),
        AgentAction(agent_id="personal", action_id="personal.stabilize", reason="stay stable", confidence=0.8),
        AgentAction(agent_id="risk", action_id="risk.contain", reason="protect base", confidence=0.8),
    ]


@pytest.fixture
def sample_contexts():
    return {
        "market": AgentContext(
            agent_id="market", year=1,
            world_state={"cash_flow": 180000, "customer_flow": 100},
            decision_vars={}, allowed_action_ids=("market.differentiate", "market.hold"),
        ),
        "environment": AgentContext(
            agent_id="environment", year=1,
            world_state={"cash_flow": 180000, "customer_flow": 100},
            decision_vars={}, allowed_action_ids=("environment.localize", "environment.monitor"),
        ),
        "personal": AgentContext(
            agent_id="personal", year=1,
            world_state={"cash_flow": 180000, "customer_flow": 100},
            decision_vars={}, allowed_action_ids=("personal.stabilize", "personal.defer"),
        ),
        "risk": AgentContext(
            agent_id="risk", year=1,
            world_state={"cash_flow": 180000, "customer_flow": 100},
            decision_vars={}, allowed_action_ids=("risk.contain", "risk.insure"),
        ),
    }


def test_stub_judge_passes_normal_round(sample_contexts):
    """正常回合 — 无明显冲突，judge_ok=True"""
    # 避免冲突对：market.hold + environment.monitor + personal.stabilize + risk.insure
    actions = [
        AgentAction(agent_id="market", action_id="market.hold", reason="safe", confidence=0.6),
        AgentAction(agent_id="environment", action_id="environment.monitor", reason="wait", confidence=0.6),
        AgentAction(agent_id="personal", action_id="personal.stabilize", reason="commit", confidence=0.6),
        AgentAction(agent_id="risk", action_id="risk.insure", reason="passive", confidence=0.6),
    ]
    judge = StubJudge()
    result = judge.judge(actions, sample_contexts)
    assert result.judge_ok
    assert result.severity < 0.5


def test_stub_judge_all_conservative_ok(sample_contexts):
    """全员保守 — 无冲突"""
    actions = [
        AgentAction(agent_id="market", action_id="market.hold", reason="play safe", confidence=0.5),
        AgentAction(agent_id="environment", action_id="environment.monitor", reason="wait", confidence=0.5),
        AgentAction(agent_id="personal", action_id="personal.defer", reason="delay", confidence=0.5),
        AgentAction(agent_id="risk", action_id="risk.insure", reason="passive", confidence=0.5),
    ]
    judge = StubJudge()
    result = judge.judge(actions, sample_contexts)
    assert result.judge_ok


def test_stub_judge_detects_low_cash_aggression(sample_contexts):
    """低现金 + 扩张 → 应标记冲突"""
    low_cash_contexts = {
        k: AgentContext(
            agent_id=v.agent_id, year=1,
            world_state={"cash_flow": 20000, "customer_flow": 50},  # 仅剩2万
            decision_vars={}, allowed_action_ids=v.allowed_action_ids,
        )
        for k, v in sample_contexts.items()
    }
    actions = [
        AgentAction(agent_id="market", action_id="market.differentiate", reason="go big", confidence=0.8),
        AgentAction(agent_id="environment", action_id="environment.localize", reason="expand", confidence=0.8),
        AgentAction(agent_id="personal", action_id="personal.stabilize", reason="commit", confidence=0.8),
        AgentAction(agent_id="risk", action_id="risk.contain", reason="contain", confidence=0.8),
    ]
    judge = StubJudge()
    result = judge.judge(actions, low_cash_contexts)
    assert not result.judge_ok or result.severity >= 0.3, (
        f"low cash should at least raise severity, got {result}"
    )


# ========================================================================== JudgeAgent（LLM 模式）

@pytest.fixture
def mock_llm_judge():
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=json.dumps({
        "judge_ok": True,
        "severity": 0.2,
        "conflicts": [],
        "recommendations": [],
    }))
    return llm


def test_llm_judge_parses_valid_response(mock_llm_judge, sample_actions, sample_contexts):
    """LLM Judge 正确解析合法 JSON"""
    judge = JudgeAgent(llm=mock_llm_judge)
    result = judge.judge(sample_actions, sample_contexts)
    assert result.judge_ok
    assert isinstance(result, JudgeResult)


def test_llm_judge_handles_markdown_json(mock_llm_judge, sample_actions, sample_contexts):
    """LLM Judge 解析 markdown 包裹的 JSON"""
    mock_llm_judge.invoke.return_value = AIMessage(content='''```json
{"judge_ok": false, "severity": 0.8, "conflicts": ["market vs risk tension"], "recommendations": ["tone down market"]}
```''')
    judge = JudgeAgent(llm=mock_llm_judge)
    result = judge.judge(sample_actions, sample_contexts)
    assert not result.judge_ok
    assert result.severity == 0.8
    assert result.conflicts == ["当前策略在投入节奏与风险承受范围上存在分歧。"]


def test_llm_judge_fallback_on_garbage(mock_llm_judge, sample_actions, sample_contexts):
    """LLM 返回不可解析内容 → fallback judge_ok=True（不阻塞）"""
    mock_llm_judge.invoke.return_value = AIMessage(content="I'm not sure about this...")
    judge = JudgeAgent(llm=mock_llm_judge)
    result = judge.judge(sample_actions, sample_contexts)
    assert result.judge_ok  # 保守策略：解析失败不阻塞
    assert result.recommendations


# ========================================================================== build_judge 慢模型连线

def test_build_judge_stub_mode():
    """stub 模式返回 StubJudge"""
    result = build_judge(use_stub=True)
    assert isinstance(result, StubJudge)


def test_build_judge_requires_llm_when_not_stub():
    """非 stub 模式且无 LLM → 抛错"""
    with pytest.raises(ValueError, match="fast_llm") as exc:
        build_judge(use_stub=False, fast_llm=None, slow_llm=None)


def test_build_judge_uses_slow_llm_when_provided():
    """有 slow_llm 时，JudgeAgent 用慢模型"""
    mock_fast = MagicMock()
    mock_slow = MagicMock()
    result = build_judge(use_stub=False, fast_llm=mock_fast, slow_llm=mock_slow)
    assert isinstance(result, JudgeAgent)
    assert result.llm is mock_slow, "Judge should use slow_llm when available"


def test_build_judge_falls_back_to_fast_llm():
    """无 slow_llm 时，fallback 到 fast_llm"""
    mock_fast = MagicMock()
    result = build_judge(use_stub=False, fast_llm=mock_fast, slow_llm=None)
    assert isinstance(result, JudgeAgent)
    assert result.llm is mock_fast, "Judge should fall back to fast_llm"


def test_llm_judge_prompt_contains_actions(mock_llm_judge, sample_actions, sample_contexts):
    """验证 Judge prompt 包含所有 Agent 的动作和理由"""
    judge = JudgeAgent(llm=mock_llm_judge)
    judge.judge(sample_actions, sample_contexts)
    call_args = mock_llm_judge.invoke.call_args[0][0]
    text = str(call_args)
    for action in sample_actions:
        assert action.agent_id in text
        assert action.action_id in text
        assert action.reason in text
