import logging
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.base import StubAgent
from app.agents.conflict_resolution import resolve_next_round_constraints
from app.agents.contracts import AgentContext, AgentProtocol
from app.agents.environment import EnvironmentAgent
from app.agents.judge import JudgeResult, StubJudge
from app.agents.llm_agent import LlmAgent
from app.agents.narration import (
    build_action_presentation,
    build_stub_reason,
    calculate_stub_confidence,
    normalize_agent_reason,
    requires_chinese_fallback,
)
from app.agents.market import MarketAgent
from app.agents.personal import PersonalAgent
from app.agents.risk import RiskAgent
from app.agents.tool_router import RoleToolRouter
from app.engine.models import AgentAction, SimulationState
from app.schemas.domain_models import DebateParticipant, DebateRecord
from app.schemas.decision_source import DecisionSource
from app.services.scenario_presenter import DECISION_VAR_LABELS
from app.tools.tavily_search import TavilySearchTool

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.kb.retriever import HybridRetriever
    from app.mcp_server.client import McpToolClient

    try:
        from app.agents.judge import JudgeAgent as _JudgeAgent
    except ImportError:
        _JudgeAgent = object


class InnerState(TypedDict):
    """LangGraph 内层状态：推演状态、各 Agent 上下文、动作列表、Judge 结果。"""

    state: SimulationState
    contexts: dict[str, AgentContext]
    actions: list[AgentAction]
    judge_result: JudgeResult
    yearly_strategy: str
    user_profile_summary: str
    user_message: str
    latest_decision: str
    variation_seed: str
    revision_count: int
    max_revisions: int


def build_inner_graph(coordinator: "AgentCoordinator", checkpointer=None):
    """编译内层 StateGraph：observe → propose → judge → [revise ⇄ judge] → validate → emit。

    judge 节点后加条件边：
    - judge_ok=true → validate（正常通过）
    - judge_ok=false 且 revision_count < max_revisions → revise（注入反馈回退重生成）
    - judge_ok=false 且 revision_count >= max_revisions → validate（强制放行）

    checkpointer 可选：传入 LangGraph checkpointer 启用快照/恢复。
    """

    def _observe(s: InnerState) -> dict:
        return {"contexts": coordinator.observe(
            s["state"],
            yearly_strategy=s.get("yearly_strategy", "steady"),
            user_profile_summary=s.get("user_profile_summary", ""),
            user_message=s.get("user_message", ""),
            latest_decision=s.get("latest_decision", ""),
            variation_seed=s.get("variation_seed", ""),
        )}

    def _propose(s: InnerState) -> dict:
        return {"actions": coordinator.propose_actions(s["contexts"])}

    def _judge(s: InnerState) -> dict:
        return {
            "judge_result": coordinator.judge_round(s["actions"], s["contexts"])
        }

    def _revise(s: InnerState) -> dict:
        """把裁判结论变成中文反馈和受限动作，供本轮重新提案使用。"""
        import dataclasses
        result = s["judge_result"]
        feedback_parts = ["本轮存在需要协调的分歧："]
        if result.conflicts:
            for c in result.conflicts:
                feedback_parts.append(f"  - {c}")
        if result.recommendations:
            feedback_parts.append("协调要求：")
            for r in result.recommendations:
                feedback_parts.append(f"  - {r}")
        feedback_text = "\n".join(feedback_parts)
        constraints = coordinator.register_conflict_constraints(
            result, s["actions"], s["contexts"]
        )
        constrained_contexts = coordinator.apply_constraints_to_contexts(
            s["contexts"], constraints
        )

        new_contexts = {}
        for agent_id, ctx in constrained_contexts.items():
            new_contexts[agent_id] = dataclasses.replace(
                ctx, judge_feedback=feedback_text
            )
        return {
            "contexts": new_contexts,
            "revision_count": s["revision_count"] + 1,
        }

    def _route_after_judge(s: InnerState) -> str:
        result = s["judge_result"]
        if result.judge_ok:
            return "validate"
        if s["revision_count"] < s["max_revisions"]:
            return "revise"
        return "validate"

    def _validate(s: InnerState) -> dict:
        return {"actions": coordinator.validate(s["actions"], s["contexts"])}

    def _emit(s: InnerState) -> dict:
        return {"actions": coordinator.emit(s["actions"])}

    g = StateGraph(InnerState)
    g.add_node("observe", _observe)
    g.add_node("propose", _propose)
    g.add_node("judge", _judge)
    g.add_node("revise", _revise)
    g.add_node("validate", _validate)
    g.add_node("emit", _emit)
    g.set_entry_point("observe")
    g.add_edge("observe", "propose")
    g.add_edge("propose", "judge")
    g.add_conditional_edges("judge", _route_after_judge, {
        "validate": "validate",
        "revise": "revise",
    })
    g.add_edge("revise", "propose")
    g.add_edge("validate", "emit")
    g.add_edge("emit", END)
    return g.compile(checkpointer=checkpointer)


def build_agents(
    source: DecisionSource,
    use_stub: bool = True,
    fast_llm: "BaseChatModel | None" = None,  # type: ignore[name-defined]
) -> dict[str, AgentProtocol]:
    declared = {agent.agent_id: agent for agent in source.agents}
    expected = {"market", "environment", "personal", "risk"}
    if set(declared) != expected:
        raise ValueError("source must declare exactly four supported agents")

    # 构建 action_id → reason_template 映射（给 LlmAgent 用）
    action_descriptions: dict[str, str] = {
        effect.action_id: effect.reason_template
        for effect in source.action_effects
    }

    if use_stub:
        agents: dict[str, AgentProtocol] = {
            "market": MarketAgent(),
            "environment": EnvironmentAgent(),
            "personal": PersonalAgent(),
            "risk": RiskAgent(),
        }
        for agent_id, agent in agents.items():
            if not declared[agent_id].action_ids:
                raise ValueError(f"agent has no declared actions: {agent_id}")
            setattr(agent, "allowed_action_ids", tuple(declared[agent_id].action_ids))
        return agents

    # --- LLM 模式 ---
    if fast_llm is None:
        raise ValueError("fast_llm is required when use_stub=False")

    agents: dict[str, AgentProtocol] = {}
    for agent_def in source.agents:
        allowed = tuple(agent_def.action_ids)
        if not allowed:
            raise ValueError(f"agent has no declared actions: {agent_def.agent_id}")
        agent = LlmAgent(
            agent_id=agent_def.agent_id,
            name=agent_def.name,
            stance=agent_def.stance,
            goal=agent_def.goal,
            allowed_action_ids=allowed,
            action_descriptions=action_descriptions,
            llm=fast_llm,
        )
        agents[agent_def.agent_id] = agent
    return agents


def build_judge(
    use_stub: bool = True,
    fast_llm: "BaseChatModel | None" = None,  # type: ignore[name-defined]
    slow_llm: "BaseChatModel | None" = None,  # type: ignore[name-defined]
) -> "StubJudge | _JudgeAgent":
    """创建 Judge 实例：stub 模式用 StubJudge，LLM 模式用 JudgeAgent。

    slow_llm 优先级高于 fast_llm — Judge 评审需要更深推理，适合慢模型。
    """
    if use_stub:
        return StubJudge()
    llm = slow_llm or fast_llm
    if llm is None:
        raise ValueError("fast_llm or slow_llm is required for LLM judge when use_stub=False")
    from app.agents.judge import JudgeAgent

    return JudgeAgent(llm=llm)


class AgentCoordinator:
    def __init__(
        self,
        agents: Mapping[str, AgentProtocol],
        retriever: "HybridRetriever | None" = None,
        judge: "StubJudge | _JudgeAgent | None" = None,
        tavily: "TavilySearchTool | None" = None,
        mcp_client: "McpToolClient | None" = None,
        checkpointer=None,
        action_descriptions: Mapping[str, str] | None = None,
        scenario_title: str = "",
        rag_enabled: bool = True,
    ):
        self.agents = dict(agents)
        self.validation_warnings: list[str] = []
        self._graph = build_inner_graph(self, checkpointer=checkpointer)
        self._retriever = retriever
        self._judge = judge or StubJudge()
        self._tavily = tavily
        self._mcp = mcp_client
        self._tool_router = RoleToolRouter(
            mcp_client=mcp_client,
            retriever=retriever,
            rag_enabled=rag_enabled,
        )
        self._checkpointer = checkpointer
        self._action_descriptions = dict(action_descriptions or {})
        self._scenario_title = scenario_title
        self._last_judge_result = JudgeResult(
            judge_ok=True, severity=0.0, conflicts=[], recommendations=[]
        )
        self._last_conflict_result: JudgeResult | None = None
        self._next_round_constraints: dict[str, object] = {}

    def _build_rag_query(
        self,
        state: SimulationState,
        latest_decision: str = "",
    ) -> str:
        """从推演状态拼自然语言检索查询。"""
        parts: list[str] = []
        dv = dict(state.decision_vars)
        if self._scenario_title:
            parts.append(f"场景：{self._scenario_title}")
        value_labels = {
            "milk_tea": "奶茶",
            "coffee": "咖啡",
            "catering": "餐饮",
            "retail": "零售",
            "balanced": "均衡",
            "conservative": "保守",
            "aggressive": "激进",
        }
        for name, value in dv.items():
            if value is None or name == "span_years":
                continue
            label = DECISION_VAR_LABELS.get(name, name)
            display_value = value_labels.get(str(value), str(value))
            parts.append(f"{label}={display_value}")
        parts.append(f"第{state.year}年")
        ws = state.world_state
        indicators = []
        for name, val in [
            ("客流量", getattr(ws, "customer_flow", None)),
            ("月利润", getattr(ws, "monthly_profit", None)),
            ("竞争数量", getattr(ws, "competition_count", None)),
        ]:
            if val is not None:
                indicators.append(f"{name}={val:.2f}")
        if indicators:
            parts.append(" ".join(indicators))
        if latest_decision.strip():
            parts.append(f"用户最新决策：{latest_decision.strip()}")
        return " ".join(parts) if parts else "当前场景决策参考"

    def _format_rag_results(self, hits: list[dict]) -> str:
        if not hits:
            return ""
        lines = ["【决策知识库参考】"]
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata", {})
            src = meta.get("source", "?")
            lines.append(f"{i}. [{src}] {h['document'][:200]}")
        return "\n".join(lines)

    @staticmethod
    def _rag_sources(hits: list[dict]) -> tuple[str, ...]:
        sources: list[str] = []
        for hit in hits:
            source = str((hit.get("metadata") or {}).get("source", "")).strip()
            if source and source not in sources:
                sources.append(source)
        return tuple(sources)

    @staticmethod
    def _text_rag_sources(text: str) -> tuple[str, ...]:
        """从 MCP 已格式化的结果中提取来源，统一前端状态展示。"""
        sources: list[str] = []
        for line in text.splitlines():
            if not line.startswith(tuple(f"{i}." for i in range(1, 10))):
                continue
            if "[" not in line or "]" not in line:
                continue
            source = line.split("[", 1)[1].split("]", 1)[0].strip()
            if source and source not in sources:
                sources.append(source)
        return tuple(sources)

    def observe(
        self,
        state: SimulationState,
        yearly_strategy: str = "steady",
        user_profile_summary: str = "",
        user_message: str = "",
        latest_decision: str = "",
        variation_seed: str = "",
    ) -> dict[str, AgentContext]:
        """为四个角色构造同一决策摘要和不同的工具证据。"""
        decision_brief = latest_decision or user_message
        evidence_by_agent = self._tool_router.build_all(
            state,
            decision_brief=decision_brief,
            profile_summary=user_profile_summary,
        )
        contexts: dict[str, AgentContext] = {}
        for agent_id, agent in self.agents.items():
            allowed = tuple(getattr(agent, "allowed_action_ids", ())) or tuple(
                getattr(agent, "action_ids", ())
            )
            constraint = state.agent_constraints.get(agent_id)
            if constraint is not None and constraint.allowed_action_ids:
                allowed = tuple(
                    action_id for action_id in constraint.allowed_action_ids
                    if action_id in allowed
                ) or allowed
            evidence = evidence_by_agent[agent_id]
            rag_evidence = next(
                (item for item in evidence if item.tool_name == "search_knowledge"),
                None,
            )
            contexts[agent_id] = AgentContext(
                agent_id=agent_id,
                agent_stance=getattr(agent, "stance", ""),
                year=state.year,
                world_state=state.world_state.model_dump(),
                decision_vars=dict(state.decision_vars),
                allowed_action_ids=allowed,
                constraint_note=(constraint.instruction if constraint is not None else ""),
                rag_context="\n".join(item.summary for item in evidence),
                yearly_strategy=yearly_strategy,
                user_profile_summary=user_profile_summary,
                user_message=user_message,
                latest_decision=latest_decision,
                variation_seed=variation_seed,
                scenario_id=state.scenario_id,
                scenario_title=self._scenario_title,
                scenario_brief=state.scenario_brief,
                action_descriptions=dict(self._action_descriptions),
                rag_status=(rag_evidence.status if rag_evidence else "disabled"),
                rag_sources=tuple(rag_evidence.sources) if rag_evidence else (),
                evidence=evidence,
            )
        return contexts

    @staticmethod
    def apply_constraints_to_contexts(
        contexts: Mapping[str, AgentContext],
        constraints: Mapping[str, object],
    ) -> dict[str, AgentContext]:
        """把结构化约束收窄为本轮真实可用的动作白名单。"""
        import dataclasses

        constrained: dict[str, AgentContext] = {}
        for agent_id, context in contexts.items():
            constraint = constraints.get(agent_id)
            allowed = context.allowed_action_ids
            note = context.constraint_note
            constraint_actions = getattr(constraint, "allowed_action_ids", ())
            if constraint_actions:
                allowed = tuple(
                    action_id for action_id in constraint_actions
                    if action_id in context.allowed_action_ids
                ) or allowed
            instruction = getattr(constraint, "instruction", "")
            if instruction:
                note = instruction
            constrained[agent_id] = dataclasses.replace(
                context,
                allowed_action_ids=allowed,
                constraint_note=note,
            )
        return constrained

    def register_conflict_constraints(
        self,
        result: JudgeResult,
        actions: list[AgentAction],
        contexts: Mapping[str, AgentContext],
    ) -> dict[str, object]:
        """记录本轮分歧产生的下一轮约束；多次修订时保留最严边界。"""
        constraints = resolve_next_round_constraints(result, actions, contexts)
        if constraints:
            self._next_round_constraints.update(constraints)
            self._last_conflict_result = result
        return constraints

    @property
    def next_round_constraints(self) -> dict[str, object]:
        return dict(self._next_round_constraints)

    def _legacy_observe(
        self, state: SimulationState,
        yearly_strategy: str = "steady",
        user_profile_summary: str = "",
        user_message: str = "",
        latest_decision: str = "",
        variation_seed: str = "",
    ) -> dict[str, AgentContext]:
        rag_text = ""
        rag_status = "disabled"
        rag_sources: tuple[str, ...] = ()
        query = self._build_rag_query(state, latest_decision)
        if self._mcp is not None:
            rag_status = "empty"
            try:
                rag_text = self._mcp.call(
                    "search_knowledge",
                    {"query": query, "scenario_id": state.scenario_id},
                ) or ""
                unavailable = "知识库暂不可用" in rag_text
                empty = "知识库暂无相关记录" in rag_text
                rag_status = "error" if unavailable else ("empty" if empty or not rag_text.strip() else "hit")
                rag_sources = self._text_rag_sources(rag_text)
            except Exception as exc:
                rag_status = "error"
                logger.warning(
                    "RAG lookup failed: scenario_id=%s error=%s",
                    state.scenario_id,
                    type(exc).__name__,
                )
                rag_text = ""
        elif self._retriever is not None:
            rag_status = "empty"
            try:
                hits = self._retriever.search(
                    query,
                    top_k=5,
                    where={"scenario_id": state.scenario_id},
                )
                rag_text = self._format_rag_results(hits)
                rag_sources = self._rag_sources(hits)
                rag_status = "hit" if hits else "empty"
            except Exception as exc:
                rag_status = "error"
                logger.warning(
                    "RAG lookup failed: scenario_id=%s error=%s",
                    state.scenario_id,
                    type(exc).__name__,
                )
                rag_text = ""

        search_text = ""
        if self._mcp is not None:
            try:
                dv = dict(state.decision_vars)
                tq = TavilySearchTool.build_query(
                    industry=str(dv.get("industry", "")),
                    city=str(dv.get("city", "")),
                    year=state.year,
                    world_state=state.world_state.model_dump(),
                )
                search_text = self._mcp.call("search_web", {"query": tq})
            except Exception:
                search_text = ""
        elif self._tavily is not None:
            try:
                dv = dict(state.decision_vars)
                tq = self._tavily.build_query(
                    industry=str(dv.get("industry", "")),
                    city=str(dv.get("city", "")),
                    year=state.year,
                    world_state=state.world_state.model_dump(),
                )
                search_text = self._tavily.search(tq)
            except Exception:
                search_text = ""

        contexts: dict[str, AgentContext] = {}
        declared_actions = {
            agent_id: tuple(
                action_id
                for action_id in getattr(agent, "allowed_action_ids", ())
            )
            for agent_id, agent in self.agents.items()
        }
        for agent_id, agent in self.agents.items():
            allowed = declared_actions[agent_id]
            if not allowed:
                allowed = tuple(
                    action_id
                    for action_id in getattr(agent, "action_ids", ())
                )
            # 用户消息仅传递给 Personal Agent
            contexts[agent_id] = AgentContext(
                agent_id=agent_id,
                agent_stance=getattr(agent, "stance", ""),
                year=state.year,
                world_state=state.world_state.model_dump(),
                decision_vars=dict(state.decision_vars),
                allowed_action_ids=allowed,
                rag_context=rag_text,
                search_context=search_text,
                yearly_strategy=yearly_strategy,
                user_profile_summary=user_profile_summary,
                user_message=user_message if agent_id == "personal" else "",
                latest_decision=latest_decision,
                variation_seed=variation_seed,
                scenario_id=state.scenario_id,
                scenario_title=self._scenario_title,
                scenario_brief=state.scenario_brief,
                action_descriptions=dict(self._action_descriptions),
                rag_status=rag_status,
                rag_sources=rag_sources,
            )
        return contexts

    def propose_actions(
        self,
        contexts: Mapping[str, AgentContext],
    ) -> list[AgentAction]:
        """并行请求四个独立 Agent，并按原有角色顺序返回结果。"""
        items = list(contexts.items())

        def propose_one(item: tuple[str, AgentContext]) -> AgentAction:
            agent_id, context = item
            action = self.agents[agent_id].propose(context)
            return action.model_copy(
                update={
                    "rag_status": context.rag_status,
                    "rag_sources": list(context.rag_sources),
                    "evidence": context.evidence,
                }
            )

        if len(items) <= 1:
            return [propose_one(item) for item in items]

        with ThreadPoolExecutor(max_workers=len(items), thread_name_prefix="yanjie-agent") as pool:
            futures = [pool.submit(propose_one, item) for item in items]
            return [future.result() for future in futures]

    def judge_round(
        self,
        actions: list[AgentAction],
        contexts: Mapping[str, AgentContext],
    ) -> JudgeResult:
        """Judge 评审所有 Agent 动作，检测跨 Agent 冲突。"""
        result = self._judge.judge(actions, dict(contexts))
        self._last_judge_result = result
        self.register_conflict_constraints(result, actions, contexts)
        if not result.judge_ok:
            for conflict in result.conflicts:
                self.validation_warnings.append(f"[Judge] {conflict}")
            for rec in result.recommendations:
                self.validation_warnings.append(f"[Judge] 建议: {rec}")
        return result

    def build_debate(
        self, actions: list[AgentAction], decision_brief: str
    ) -> DebateRecord | None:
        """将真实 Judge 冲突和 Agent 立场转成用户可见的讨论记录。"""
        result = self._last_conflict_result or self._last_judge_result
        high_impact = bool(decision_brief.strip()) and any(
            keyword in decision_brief
            for keyword in ("加大", "明星", "代言", "投资", "贷款", "买房", "辞职", "跳槽", "加仓")
        )
        if not actions or (not result.conflicts and not high_impact):
            return None
        trigger = "judge_conflict" if result.conflicts else "high_impact_decision"
        conflicts = list(result.conflicts)
        if not conflicts:
            conflicts = ["这是一项影响较大的决策，四位顾问从不同约束条件进行评估。"]
        recommendations = list(result.recommendations)
        if not recommendations:
            recommendations = ["先明确投入上限和验证指标，再决定是否扩大执行。"]
        constraint_summaries = [
            getattr(constraint, "summary", "")
            for constraint in self._next_round_constraints.values()
        ]
        if constraint_summaries:
            recommendations.append(
                "本轮协调结果：" + "；".join(
                    summary for summary in constraint_summaries if summary
                )
            )
        return DebateRecord(
            trigger=trigger,
            conflicts=conflicts,
            recommendations=recommendations,
            participants=[
                DebateParticipant(
                    agent_id=action.agent_id,
                    position=action.position,
                    reason=action.reason,
                    recommendation=action.recommendation or action.reason,
                    objection=(
                        action.objection
                        or (
                            "该角色要求先验证关键前提，再扩大执行。"
                            if action.position in {"oppose", "conditional"}
                            else None
                        )
                    ),
                )
                for action in actions
            ],
            judge_summary="；".join(recommendations),
        )

    def validate(
        self,
        actions: list[AgentAction],
        contexts: Mapping[str, AgentContext],
    ) -> list[AgentAction]:
        self.validation_warnings = []  # 每轮重置
        validated: list[AgentAction] = []
        for action in actions:
            context = contexts.get(action.agent_id)
            if context is None:
                raise ValueError(f"unknown agent output: {action.agent_id}")
            if not action.reason.strip():
                raise ValueError(f"agent reason is empty: {action.agent_id}")
            if action.action_id not in context.allowed_action_ids:
                fallback = context.allowed_action_ids[0]
                self.validation_warnings.append(
                    f"replaced undeclared action {action.action_id} "
                    f"for {action.agent_id} with {fallback}"
                )
                action = action.model_copy(update={"action_id": fallback})
            normalized_reason = normalize_agent_reason(action.reason)
            if normalized_reason != action.reason:
                action = action.model_copy(update={"reason": normalized_reason})
            if requires_chinese_fallback(normalized_reason):
                self.validation_warnings.append(
                    f"replaced unreadable agent reason for {action.agent_id}"
                )
                action = action.model_copy(
                    update={
                        "reason": build_stub_reason(context, action.action_id),
                        "confidence": calculate_stub_confidence(context),
                        "generation_source": "fallback",
                        **build_action_presentation(context, action.action_id),
                    }
                )
            else:
                presentation = build_action_presentation(context, action.action_id)
                action = action.model_copy(
                    update={
                        "recommendation": (
                            normalize_agent_reason(action.recommendation)
                            if action.recommendation.strip()
                            else presentation["recommendation"]
                        ),
                        "alternatives": (
                            [
                                normalize_agent_reason(item)
                                for item in action.alternatives
                                if item.strip()
                            ][:2]
                            or presentation["alternatives"]
                        ),
                        "objection": (
                            normalize_agent_reason(action.objection)
                            if action.objection and action.objection.strip()
                            else presentation["objection"]
                        ),
                        "stop_condition": (
                            normalize_agent_reason(action.stop_condition)
                            if action.stop_condition and action.stop_condition.strip()
                            else presentation["stop_condition"]
                        ),
                    }
                )
            validated.append(action)
        return validated

    def emit(self, actions: list[AgentAction]) -> list[AgentAction]:
        return [action.model_copy(deep=True) for action in actions]

    def propose(
        self, state: SimulationState,
        yearly_strategy: str = "steady",
        user_profile_summary: str = "",
        user_message: str = "",
        latest_decision: str = "",
        variation_seed: str = "",
        max_revisions: int = 2,
    ) -> list[AgentAction]:
        self._next_round_constraints = {}
        self._last_conflict_result = None
        initial: InnerState = {
            "state": state,
            "contexts": {},
            "actions": [],
            "judge_result": JudgeResult(judge_ok=True, severity=0.0, conflicts=[], recommendations=[]),
            "yearly_strategy": yearly_strategy,
            "user_profile_summary": user_profile_summary,
            "user_message": user_message,
            "latest_decision": latest_decision,
            "variation_seed": variation_seed,
            "revision_count": 0,
            "max_revisions": max_revisions,
        }
        config = None
        if self._checkpointer is not None:
            config = {"configurable": {"thread_id": f"{state.session_id}-inner-{state.year}"}}
        return self._graph.invoke(initial, config)["actions"]
