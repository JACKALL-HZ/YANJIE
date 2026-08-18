from app.schemas.domain_models import AgentAction, TimelineNode, WorldState


def test_timeline_round_trips_agent_evidence_and_debate_record():
    action = AgentAction(
        agent_id="market",
        action_id="market.differentiate",
        reason="用户计划加大曝光，当前竞争压力高，需要先验证转化。",
        confidence=0.74,
        position="conditional",
        evidence=[
            {
                "tool_name": "search_knowledge",
                "summary": "检索到本场景的竞争与客群资料。",
                "sources": ["杭州奶茶市场竞争与客群特征"],
                "status": "hit",
            }
        ],
    )
    node = TimelineNode.model_validate(
        {
            "year": 1,
            "world_state": WorldState().model_dump(),
            "agent_actions": [action.model_dump()],
            "state_diff": {},
            "interventions": [],
            "ending": None,
            "debate": {
                "trigger": "judge_conflict",
                "conflicts": ["市场 Agent 支持投入，风险 Agent 要求控制现金消耗。"],
                "recommendations": ["先用小预算验证转化。"],
                "participants": [
                    {
                        "agent_id": "market",
                        "position": "conditional",
                        "reason": action.reason,
                    }
                ],
            },
        }
    )

    restored = TimelineNode.model_validate(node.model_dump(mode="json"))
    assert restored.agent_actions[0].position == "conditional"
    assert restored.agent_actions[0].evidence[0].tool_name == "search_knowledge"
    assert restored.debate is not None
    assert restored.debate.trigger == "judge_conflict"
