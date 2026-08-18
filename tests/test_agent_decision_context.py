from app.agents.inner_graph import AgentCoordinator, build_agents
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


class CapturingRetriever:
    def __init__(self):
        self.where = None
        self.query = ""

    def search(self, query, top_k, where):
        self.query = query
        self.where = where
        return [
            {
                "document": "考研资料",
                "metadata": {"scenario_id": "grad_exam", "source": "教育部"},
            }
        ]


def test_agents_retrieve_knowledge_only_from_the_current_scenario():
    source = ScenarioLoader("scenarios").load("grad_exam")
    state = make_initial_state(source, {"target_school": "清华大学"})
    retriever = CapturingRetriever()
    coordinator = AgentCoordinator(
        build_agents(source, use_stub=True),
        retriever=retriever,
    )

    contexts = coordinator.observe(state)

    assert retriever.where == {"scenario_id": "grad_exam"}
    assert "考研资料" in contexts["market"].rag_context


def test_all_agents_receive_the_latest_decision_and_profile_context():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(
        source,
        {"budget": 200000},
        user_profile={"assets": 500000, "risk_appetite": "balanced"},
    )
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))

    contexts = coordinator.observe(
        state,
        user_profile_summary="可支配资产50万元，风险偏好均衡。",
        latest_decision="请明星代言",
    )

    assert set(contexts) == {"market", "environment", "personal", "risk"}
    assert {context.latest_decision for context in contexts.values()} == {"请明星代言"}
    assert {
        context.user_profile_summary for context in contexts.values()
    } == {"可支配资产50万元，风险偏好均衡。"}


def test_stub_agents_explain_same_decision_in_distinct_plain_chinese_roles():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))
    contexts = coordinator.observe(state, latest_decision="请明星代言")

    actions = coordinator.propose_actions(contexts)
    reasons = {action.agent_id: action.reason for action in actions}

    assert "明星代言" in reasons["market"]
    assert "本地客群" in reasons["environment"]
    assert "创始人" in reasons["personal"]


def test_all_agents_receive_raw_user_message_for_a_shared_decision_review():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))
    state = make_initial_state(source, {"budget": 200000})

    contexts = coordinator.observe(
        state,
        user_message="我想先看看市场，不急着决定",
        latest_decision="尝试和其他奶茶店联名",
    )

    assert contexts["personal"].user_message == "我想先看看市场，不急着决定"
    assert {
        context.user_message for context in contexts.values()
    } == {"我想先看看市场，不急着决定"}
    assert {
        context.latest_decision for context in contexts.values()
    } == {"尝试和其他奶茶店联名"}


def test_rag_query_includes_latest_decision_and_exposes_hit_metadata():
    source = ScenarioLoader("scenarios").load("study_abroad")
    state = make_initial_state(
        source,
        {"target_country": "美国", "target_major": "计算机", "budget": 1000000},
    )
    retriever = CapturingRetriever()
    coordinator = AgentCoordinator(
        build_agents(source, use_stub=True),
        retriever=retriever,
        action_descriptions={
            effect.action_id: effect.reason_template
            for effect in source.action_effects
        },
        scenario_title=source.title,
    )

    contexts = coordinator.observe(state, latest_decision="申请美国计算机硕士")

    assert "申请美国计算机硕士" in retriever.query
    assert "目标国家=美国" in retriever.query
    assert "目标专业=计算机" in retriever.query
    assert contexts["market"].rag_status == "hit"
    assert contexts["market"].rag_sources == ("教育部",)


def test_scenario_fallback_reason_uses_current_action_description():
    source = ScenarioLoader("scenarios").load("study_abroad")
    state = make_initial_state(
        source,
        {"target_country": "美国", "target_major": "计算机", "budget": 1000000},
    )
    coordinator = AgentCoordinator(
        build_agents(source, use_stub=True),
        action_descriptions={
            effect.action_id: effect.reason_template
            for effect in source.action_effects
        },
        scenario_title=source.title,
    )

    contexts = coordinator.observe(state, latest_decision="申请美国计算机硕士")
    actions = coordinator.propose_actions(contexts)

    market_reason = next(item.reason for item in actions if item.agent_id == "market")
    assert "目标院校" in market_reason
    assert "当前经营策略" not in market_reason


def test_fallback_reason_does_not_expose_english_action_template():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    coordinator = AgentCoordinator(
        build_agents(source, use_stub=True),
        action_descriptions={
            effect.action_id: effect.reason_template
            for effect in source.action_effects
        },
        scenario_title=source.title,
    )

    actions = coordinator.propose(state, latest_decision="增加营销预算")

    assert all("Differentiate" not in action.reason for action in actions)
    assert all("Hold" not in action.reason for action in actions)


def test_initial_conversation_history_reaches_first_year_agents():
    from app.engine.engine import SimulationEngine

    source = ScenarioLoader("scenarios").load("study_abroad")
    engine = SimulationEngine(source, use_stub=True)
    captured_decisions = []
    original_propose = engine.coordinator.propose

    def capture_propose(*args, **kwargs):
        captured_decisions.append(kwargs["latest_decision"])
        return original_propose(*args, **kwargs)

    engine.coordinator.propose = capture_propose
    state = engine.run_batch(
        {
            "target_country": "美国",
            "target_major": "计算机",
            "budget": 1000000,
            "span_years": 1,
        },
        conversation_history=[
            {"role": "user", "content": "去美国留学"},
            {"role": "user", "content": "申请美国计算机硕士"},
        ],
    )

    assert state.timeline
    assert captured_decisions[0] == "申请美国计算机硕士"
