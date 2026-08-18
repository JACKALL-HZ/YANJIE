from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_high_impact_user_decision_persists_role_evidence_and_debate():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run_batch(
        {"budget": 200000, "span_years": 1},
        conversation_history=[
            {"role": "user", "content": "请明星代言，加大预算"},
        ],
    )

    node = state.timeline[0]
    assert len(node.agent_actions) == 4
    assert all(action.evidence for action in node.agent_actions)
    assert node.debate is not None
    assert node.debate.trigger in {"high_impact_decision", "judge_conflict"}
