from app.agents.inner_graph import AgentCoordinator, build_agents
from app.agents.judge import JudgeResult
from app.engine.models import AgentAction
from app.scenarios.loader import ScenarioLoader


class ConflictJudge:
    def judge(self, actions, contexts):
        return JudgeResult(
            judge_ok=True,
            severity=0.3,
            conflicts=["市场 Agent 支持扩大投入，风险 Agent 要求控制损失。"],
            recommendations=["先用小预算验证转化。"],
        )


def _actions():
    return [
        AgentAction(
            agent_id="market", action_id="market.differentiate", reason="支持测试曝光。",
            confidence=0.7, position="support",
        ),
        AgentAction(
            agent_id="environment", action_id="environment.localize", reason="要匹配本地规则。",
            confidence=0.7, position="conditional",
        ),
        AgentAction(
            agent_id="personal", action_id="personal.stabilize", reason="需要评估执行负荷。",
            confidence=0.7, position="conditional",
        ),
        AgentAction(
            agent_id="risk", action_id="risk.contain", reason="反对一次性投入。",
            confidence=0.7, position="oppose",
        ),
    ]


def test_judge_conflict_becomes_visible_debate_record():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    coordinator = AgentCoordinator(
        build_agents(source, use_stub=True), judge=ConflictJudge()
    )
    coordinator.judge_round(_actions(), {})

    debate = coordinator.build_debate(_actions(), "请明星代言，加大预算")

    assert debate is not None
    assert debate.trigger == "judge_conflict"
    assert len(debate.participants) == 4
    assert debate.participants[-1].position == "oppose"
    assert debate.participants[-1].objection
    assert debate.judge_summary


def test_no_decision_and_no_conflict_does_not_create_debate_record():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))
    coordinator.judge_round([], {})

    assert coordinator.build_debate([], "") is None
