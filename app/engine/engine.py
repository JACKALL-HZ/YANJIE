import asyncio
import logging
import os
import random
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.agents.inner_graph import AgentCoordinator, build_agents, build_judge
from app.agents.startup_brief import ScenarioBriefGenerator, StartupBriefGenerator
from app.engine.yanjie_engine import YanJieEngine
from app.core.config import Settings, get_settings
from app.core.llm import build_llm
from app.engine.graph import build_outer_graph
from app.engine.intervention_graph import build_intervention_graph
from app.engine.profile_summary import build_profile_summary
from app.engine.models import (
    InterventionRecord,
    PendingIntervention,
    SimulationState,
    TimelineNode,
)
from app.engine.scoring import build_action_plan, compute_score, extract_risks
from app.engine.startup_decision import select_startup_decision
from app.engine.state import make_initial_state
from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder
from app.kb.retriever import HybridRetriever
from app.mcp_server.client import McpToolClient
from app.schemas.decision_source import DecisionSource
from app.tools.tavily_search import TavilySearchTool
from app.schemas.events import (
    EventType,
    InterventionPendingPayload,
    SimulationCompletedPayload,
    SimulationEvent,
    SimulationPausedPayload,
    SimulationStartedPayload,
    YearCompletedPayload,
    YearStartedPayload,
)
from sqlalchemy.orm import Session as DbSession

from app.db.repository import EventRepo, MessageRepo, ScenarioRepo, SimulationRepo


EngineEvent = SimulationEvent


def _next_or_none(iterator: Iterator) -> Any:
    """从同步生成器安全取下一个元素；耗尽返回 None。

    用于在 asyncio.to_thread 中逐部驱动同步生成器：StopIteration 不能从
    Future 里抛出（Python 3.12+ 会报 RuntimeError），用哨兵值代替。
    """
    try:
        return next(iterator)
    except StopIteration:
        return None


class SimulationEngine:
    def __init__(
        self,
        source: DecisionSource,
        use_stub: bool | None = None,
        settings: Settings | None = None,
    ):
        self.source = source
        self.settings = settings or get_settings()
        self.use_stub = (
            self.settings.llm_use_stub if use_stub is None else use_stub
        )
        fast_llm = (
            build_llm(self.settings.fast_llm)
            if not self.use_stub
            else None
        )
        slow_llm = (
            build_llm(self.settings.slow_llm)
            if not self.use_stub
            else None
        )

        # 工具后端：stub 模式下不调外部 API（避免网络超时导致推演失败）
        retriever = None
        tavily = None
        mcp_client = None

        # MCP 是 Agent 的工具通道，不应被 RAG 开关连带关闭。RAG 只控制检索后端。
        if self.settings.mcp_enabled and not self.use_stub:
            try:
                mcp_client = McpToolClient(
                    mode=self.settings.mcp_transport,
                    http_url=self.settings.mcp_http_url,
                    http_token=self.settings.mcp_http_token,
                    stdio_command=self.settings.mcp_stdio_command,
                    timeout_seconds=self.settings.mcp_timeout_seconds,
                )
            except RuntimeError:
                logging.getLogger(__name__).warning(
                    "MCP client is unavailable; falling back to local tools"
                )
        if self.settings.rag_enabled and mcp_client is None:
            retriever = self._build_retriever()
            if not self.use_stub and self.settings.web_search_enabled:
                tavily = self._build_tavily()

        checkpointer, _checkpointer_cm = self._build_checkpointer()

        self.coordinator = AgentCoordinator(
            agents=build_agents(
                source,
                use_stub=self.use_stub,
                fast_llm=fast_llm,
            ),
            judge=build_judge(
                use_stub=self.use_stub,
                fast_llm=fast_llm,
                slow_llm=slow_llm,
            ),
            retriever=retriever,
            tavily=tavily,
            mcp_client=mcp_client,
            checkpointer=checkpointer,
            action_descriptions={
                effect.action_id: effect.reason_template
                for effect in source.action_effects
            },
            scenario_title=source.title,
            rag_enabled=self.settings.rag_enabled,
        )
        self._graph = build_outer_graph(source, checkpointer=checkpointer)
        self._iv_graph = build_intervention_graph(source, checkpointer=checkpointer)
        self._checkpointer = checkpointer
        self._checkpointer_cm = _checkpointer_cm  # 保持 context manager 引用防止 GC
        self._mcp_client = mcp_client

    def close(self) -> None:
        """Release transport and checkpointer resources held by this engine."""
        mcp_client, self._mcp_client = self._mcp_client, None
        if mcp_client is not None:
            mcp_client.close()
        checkpointer_cm, self._checkpointer_cm = self._checkpointer_cm, None
        if checkpointer_cm is not None:
            checkpointer_cm.__exit__(None, None, None)

    def _ensure_scenario_brief(self, state: SimulationState) -> SimulationState:
        if state.scenario_brief:
            return state
        llm = None if self.use_stub else build_llm(self.settings.fast_llm)
        if self.source.scenario_id == "general_startup":
            brief = StartupBriefGenerator(llm).build(state)
        else:
            brief = ScenarioBriefGenerator(llm, self.source.title).build(state)
        return state.model_copy(update={"scenario_brief": brief})

    def _startup_params(self, state: SimulationState) -> dict[str, Any]:
        values = state.decision_vars
        raw_category = str(values.get("industry") or "餐饮")
        category = {"milk_tea": "奶茶", "coffee": "咖啡", "catering": "餐饮"}.get(raw_category, raw_category)
        city = str(values.get("city") or "待确认城市")
        return {"city": city, "district": str(values.get("district") or city), "category": category, "is_franchise": str(values.get("is_franchise", "自营")) in {"加盟", "true", "True", "1"}, "total_budget": float(values.get("budget") or 0), "total_years": int(values.get("span_years") or 1), "granularity": "quarter"}

    def _ensure_startup_ledger(self, state: SimulationState) -> SimulationState:
        if self.source.scenario_id != "general_startup" or state.startup_ledger:
            return state
        ledger = YanJieEngine(self._startup_params(state)).initialize()
        return self._sync_startup_state(state, ledger, {})

    def _sync_startup_state(self, state: SimulationState, ledger: dict[str, Any], dashboard: dict[str, Any]) -> SimulationState:
        operation, finance = ledger["operation"], ledger["finance"]
        world = state.world_state.model_copy(update={"cash_flow": finance["remaining_cash"], "customer_flow": operation["daily_orders"], "monthly_profit": (ledger["history"]["rounds"][-1]["季度利润"] / 3 if ledger["history"]["rounds"] else 0), "payback_ratio": finance["payback_progress"]})
        return state.model_copy(update={"world_state": world, "startup_ledger": ledger, "startup_dashboard": dashboard})

    def _advance_startup_ledger(self, state: SimulationState, decision_text: str, strategy: str, actions: list) -> tuple[SimulationState, list]:
        if self.source.scenario_id != "general_startup":
            return state, actions
        engine = YanJieEngine(self._startup_params(state))
        ledger = state.startup_ledger or engine.initialize()
        # 用户在年限确认页选择续推后，同步延展已有账本的季度上限。
        ledger["base_params"].update(engine.params)
        ledger["stage"]["total_rounds"] = engine.params["total_years"] * 4
        selected_decision = select_startup_decision(
            actions,
            decision_text,
            strategy,
        )
        decision_id = selected_decision.decision_id
        applied_decision_id = decision_id
        before = len(ledger["history"]["rounds"])
        for _ in range(4):
            if ledger["stage"]["is_game_over"]:
                break
            available = [
                item["decision_id"] for item in engine.decision_options(ledger)
            ]
            if not available:
                break
            selected = decision_id if decision_id in available else available[0]
            ledger = engine.advance(ledger, selected)
            ledger["history"]["rounds"][-1]["决策依据"] = selected_decision.reason
            ledger["history"]["rounds"][-1]["角色动作"] = selected_decision.supporting_actions
            applied_decision_id = selected
            if ledger["stage"]["is_game_over"]:
                break
        rows = ledger["history"]["rounds"][before:]
        dashboard = {"日均单量": ledger["operation"]["daily_orders"], "月营收": round((rows[-1]["季度营收"] / 3) if rows else 0, 2), "月成本": round((rows[-1]["季度成本"] / 3) if rows else 0, 2), "月净利润": round((rows[-1]["季度利润"] / 3) if rows else 0, 2), "剩余现金流": ledger["finance"]["remaining_cash"], "回本进度": ledger["finance"]["payback_progress"], "本年决策": self._DECISIONS_LABEL(applied_decision_id), "决策依据": selected_decision.reason, "角色动作": selected_decision.supporting_actions, "风险预警": ledger["history"]["risk_events"][-1]["预警"] if ledger["history"]["risk_events"] else []}
        analyses = engine.agent_analysis(ledger)
        analysis_by_agent = {
            item["智能体"].replace("智能体", "").replace("市场", "market")
            .replace("环境", "environment").replace("个人", "personal")
            .replace("风险", "risk"): item
            for item in analyses
        }
        updated_actions = []
        for action in actions:
            analysis = analysis_by_agent.get(action.agent_id, {})
            confidence_text = str(analysis.get("置信度", ""))
            try:
                confidence = float(confidence_text.rstrip("%")) / 100
            except ValueError:
                confidence = action.confidence
            updated_actions.append(action.model_copy(update={
                # 账本负责可追溯的量化结果，模型负责结合资料解释本角色判断。
                "reason": (
                    f"{analysis.get('量化结论', action.reason)}\n\n"
                    f"结合本轮资料：{action.reason}"
                ),
                "confidence": confidence,
            }))
        updated_state = self._sync_startup_state(state, ledger, dashboard)
        # 通用创业场景的结束条件由量化账本决定，不能被旧的通用 WorldState
        # 现金判定提前截断。只有资金耗尽、主动退出或完成全部季度才结束。
        stage = ledger["stage"]
        if stage["is_game_over"]:
            end_reason = str(stage.get("end_reason") or "完成设定推演周期")
            if "完成设定推演周期" in end_reason:
                # 达到用户选择的年限不是被动结局，必须交由用户确认续推或结算。
                stage.update({"is_game_over": False, "end_reason": None})
                updated_state = updated_state.model_copy(
                    update={"startup_ledger": ledger, "phase": "simulating", "result": None}
                )
            else:
                result = "bankrupt" if "资金" in end_reason else "timeout"
                updated_state = updated_state.model_copy(
                    update={"phase": "completed", "result": result}
                )
        else:
            updated_state = updated_state.model_copy(
                update={"phase": "simulating", "result": None}
            )
        return updated_state, updated_actions

    def _advance_startup_year(
        self,
        state: SimulationState,
        decision_text: str,
        yearly_strategy: str,
        actions: list,
    ) -> tuple[SimulationState, list]:
        """创业场景的唯一年度状态推进：账本，不再调用通用 outer graph。"""
        before = state.world_state
        advanced, actions = self._advance_startup_ledger(
            state, decision_text, yearly_strategy, actions
        )
        current = advanced.world_state
        state_diff = {
            metric: round(getattr(current, metric) - getattr(before, metric), 2)
            for metric in (
                "cash_flow", "customer_flow", "competition_count",
                "monthly_profit", "payback_ratio",
            )
        }
        next_year = state.year + 1
        updated = advanced.model_copy(deep=True)
        updated.year = next_year
        updated.agent_actions = list(actions)
        updated.timeline.append(
            TimelineNode(
                year=next_year,
                world_state=current,
                agent_actions=list(actions),
                state_diff=state_diff,
                business_dashboard=advanced.startup_dashboard,
            )
        )
        return updated, actions

    @staticmethod
    def _DECISIONS_LABEL(decision_id: str) -> str:
        return {"steady_growth": "稳健增长", "precision_breakthrough": "精准突破", "defensive": "收缩防守", "shrink_stop_loss": "收缩止损", "transfer_or_close": "转让闭店"}[decision_id]

    def _build_retriever(self) -> "HybridRetriever | None":
        """构建 RAG 混合检索引擎（Embedding API Key 配置时启用）。"""
        emb_cfg = self.settings.embedding
        try:
            embedder = SiliconFlowEmbedder(emb_cfg) if emb_cfg.api_key else None
            store = ChromaStore(persist_dir=self.settings.chroma_persist_dir)
            return HybridRetriever(store=store, embedder=embedder)
        except Exception as exc:
            # 向量库损坏或目录不可用时，推演仍可使用场景规则继续运行。
            logging.getLogger(__name__).warning(
                "RAG retriever initialization failed: %s", type(exc).__name__
            )
            return None

    def _build_tavily(self) -> "TavilySearchTool | None":
        """构建 Tavily Search 工具（API Key 配置时启用）。"""
        if not self.settings.tavily_api_key:
            return None
        return TavilySearchTool(api_key=self.settings.tavily_api_key)

    def _build_checkpointer(self):
        """构建 LangGraph checkpointer（开发期 SQLite，生产 PostgreSQL）。

        SqliteSaver.from_conn_string() 返回 context manager，
        需保持 context manager 引用防止 GC 回收导致连接关闭。
        返回 (checkpointer, cm) 元组，cm 由 SimulationEngine 持有。
        """
        url = self.settings.checkpointer_url

        if url == "memory" or url == "":
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver(), None

        if url.startswith("sqlite:///"):
            db_path = url.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                from pathlib import Path
                project_root = Path(__file__).resolve().parent.parent.parent
                db_path = str(project_root / db_path)
            from langgraph.checkpoint.sqlite import SqliteSaver

            cm = SqliteSaver.from_conn_string(db_path)
            return cm.__enter__(), cm

        # 生产期 PostgreSQL（需 langgraph-checkpoint-postgres）
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            try:
                from langgraph.checkpoint.postgres import PostgresSaver

                cm = PostgresSaver.from_conn_string(url)
                saver = cm.__enter__()
                saver.setup()  # 建 checkpoints/writes 表，否则首次 resume 报 relation "checkpoints" does not exist
                return saver, cm
            except ImportError as exc:
                raise RuntimeError(
                    "CHECKPOINTER_URL uses PostgreSQL but langgraph-checkpoint-postgres is not installed"
                ) from exc

        # 兜底：MemorySaver
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver(), None

    def _max_years(self, decision_vars: dict[str, Any]) -> int:
        requested = int(
            decision_vars.get(
                "span_years",
                self.source.end_conditions.timeout_years,
            )
        )
        maximum = min(
            requested,
            self.source.end_conditions.timeout_years,
            self.settings.max_years,
        )
        if maximum <= 0:
            raise ValueError("simulation year bound must be positive")
        return maximum

    def maximum_supported_years(self) -> int:
        return min(
            self.source.end_conditions.timeout_years,
            self.settings.max_years,
        )

    def make_horizon_review_state(self, state: SimulationState) -> SimulationState:
        return state.model_copy(
            update={
                "phase": "horizon_review",
                "pause_reason": "horizon_review",
                "pending_intervention": None,
            }
        )

    @staticmethod
    def make_year_decision_state(state: SimulationState) -> SimulationState:
        return state.model_copy(
            update={
                "phase": "paused",
                "pause_reason": "year_decision_required",
                "pending_intervention": None,
            }
        )

    def finalize_horizon_review(self, state: SimulationState) -> SimulationState:
        return self._finalize(
            state.model_copy(
                update={
                    "phase": "completed",
                    "result": "timeout",
                    "pause_reason": None,
                    "pending_intervention": None,
                    "pending_decision_preview": None,
                }
            )
        )

    def finalize_user_ended(self, state: SimulationState) -> SimulationState:
        """End a user-controlled session without advancing another year."""
        return self._finalize(
            state.model_copy(
                update={
                    "phase": "completed",
                    "result": "user_ended",
                    "pause_reason": None,
                    "pending_intervention": None,
                    "pending_decision_preview": None,
                }
            )
        )

    def _finalize(self, state: SimulationState) -> SimulationState:
        if state.result is None or state.score is not None:
            return state
        finalized = state.model_copy(deep=True)
        risks = extract_risks(
            finalized.world_state.model_dump(),
            scenario_id=self.source.scenario_id,
            decision_vars=finalized.decision_vars,
            user_profile=finalized.user_profile,
        )
        score = compute_score(
            finalized.world_state.model_dump(),
            finalized.result,
            success_definition=dict(finalized.success_definition),
            scenario_id=self.source.scenario_id,
            decision_vars=finalized.decision_vars,
        )
        finalized.score = score.total
        finalized.score_detail = score.detail
        finalized.risks = [item.model_dump() for item in risks]
        finalized.action_plan = [
            item.model_dump()
            for item in build_action_plan(risks, scenario_id=self.source.scenario_id)
        ]
        if self.source.scenario_id == "general_startup" and finalized.startup_ledger:
            settlement = YanJieEngine(self._startup_params(finalized)).final_settlement(
                finalized.startup_ledger
            )
            finalized.startup_settlement = settlement
            finalized.score_detail = dict(settlement["scores"])
            finalized.action_plan = [
                {"action": item} for item in settlement["optimal_path"]
            ]
        return finalized

    @staticmethod
    def _build_profile_summary(
        profile: dict[str, Any],
        decision_vars: dict[str, Any] | None = None,
    ) -> str:
        """将用户画像转为 Agent 可读摘要（含投入压力分析）。

        委托 `app.engine.profile_summary.build_profile_summary` 纯函数实现。
        """
        return build_profile_summary(profile, decision_vars)

    @staticmethod
    def _latest_user_message(
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        """从启动对话中提取最后一条有效用户输入，作为首年决策上下文。"""
        if not conversation_history:
            return ""
        ignored = {"开始", "开始推演", "start"}
        for message in reversed(conversation_history):
            if str(message.get("role", "")).strip() != "user":
                continue
            content = str(message.get("content", "")).strip()
            if content and content.lower() not in ignored:
                return content
        return ""

    @staticmethod
    def _state_diff(state: SimulationState) -> dict[str, float]:
        if not state.timeline:
            return {}
        return state.timeline[-1].state_diff

    @staticmethod
    def _event(
        sequence: int,
        session_id: str,
        scenario_id: str,
        event_type: EventType,
        payload: BaseModel,
        state: SimulationState | None = None,
    ) -> SimulationEvent:
        return SimulationEvent(
            sequence=sequence,
            session_id=session_id,
            scenario_id=scenario_id,
            event_type=event_type,
            payload=payload,
            state_snapshot=state,
        )

    # ── 持久化辅助 ─────────────────────────────────────────

    def _persist_scenario(self, screpo: ScenarioRepo) -> None:
        """幂等 upsert 场景元数据。"""
        screpo.upsert(
            scenario_id=self.source.scenario_id,
            title=self.source.title,
            decision_source=self.source.model_dump(mode="json"),
        )

    def _persist_agent_events(
        self,
        erepo: EventRepo,
        session_id: str,
        state: SimulationState,
    ) -> None:
        """把每年 Agent 动作写入 simulation_events 表。"""
        if not state.timeline:
            return
        node = state.timeline[-1]
        for aa in node.agent_actions:
            erepo.save(
                session_id=session_id,
                year=state.year,
                agent=aa.agent_id,
                action=aa.action_id,
                state_diff=node.state_diff,
                payload={
                    "reason": aa.reason,
                    "confidence": aa.confidence,
                },
            )

    def _persist_session_state(
        self,
        srepo: SimulationRepo,
        session_id: str,
        state: SimulationState,
    ) -> None:
        """增量更新 simulation_sessions 行（每年推演后调用）。"""
        srepo.update(
            session_id,
            current_year=state.year,
            phase=state.phase,
            world_state=state.world_state.model_dump(mode="json"),
            timeline=[n.model_dump(mode="json") for n in state.timeline],
            interventions=[
                iv.model_dump(mode="json") for iv in state.interventions
            ],
            result=state.result,
            score=int(state.score) if state.score is not None else None,
            score_detail=state.score_detail or None,
            risks=state.risks,
            action_plan=state.action_plan or None,
            agent_states={
                "startup_ledger": state.startup_ledger,
                "startup_dashboard": state.startup_dashboard,
                "startup_settlement": state.startup_settlement,
                "pending_intervention": (
                    state.pending_intervention.model_dump(mode="json")
                    if state.pending_intervention is not None
                    else None
                ),
                "pending_decision_preview": (
                    state.pending_decision_preview.model_dump(mode="json")
                    if state.pending_decision_preview is not None
                    else None
                ),
                "pause_reason": state.pause_reason,
                "agent_constraints": {
                    agent_id: constraint.model_dump(mode="json")
                    for agent_id, constraint in state.agent_constraints.items()
                },
            },
        )

    def _advance_year(
        self,
        state: SimulationState,
        session_id: str,
        yearly_strategy: str,
        user_profile_summary: str,
        variation_seed: str,
        intervention_choices: dict[int, str] | None,
        srepo: "SimulationRepo | None",
        erepo: "EventRepo | None",
    ) -> tuple[SimulationState, bool]:
        """推进一年推演：Agent 决策 → outer graph → 干预判定。

        Returns (new_state, is_paused).
        若 is_paused=True，调用方应 yield 暂停事件并 return。
        """
        # Agent 决策（单次失败不中断推演，兜底用各 Agent 的第一个合法 action）
        state = self._ensure_startup_ledger(self._ensure_scenario_brief(
            state.model_copy(
                update={"yearly_strategy": yearly_strategy, "pause_reason": None}
            )
        ))
        # 传递用户消息给 Personal Agent（逐年交互模式），消费后立即清除防止泄漏到后续年份
        user_msg = getattr(state, "user_message", "")
        state.user_message = ""
        try:
            actions = self.coordinator.propose(
                state,
                yearly_strategy=yearly_strategy,
                user_profile_summary=user_profile_summary,
                user_message=user_msg,
                latest_decision=user_msg,
                variation_seed=variation_seed,
                max_revisions=self.settings.max_judge_revisions,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Agent propose failed for year %d, using fallback", state.year + 1
            )
            from app.engine.models import AgentAction
            # 从场景定义中取每个 Agent 的第一个合法 action_id
            agent_fallbacks: dict[str, str] = {}
            for agent_def in self.source.agents:
                if agent_def.action_ids:
                    agent_fallbacks[agent_def.agent_id] = agent_def.action_ids[0]
            actions = []
            for aid in ["market", "environment", "personal", "risk"]:
                fallback_id = agent_fallbacks.get(aid, f"{aid}.hold")
                actions.append(AgentAction(
                    agent_id=aid, action_id=fallback_id,
                    reason="当前年度决策暂不可用，保持观望策略。",
                    confidence=0.1, yearly_strategy=yearly_strategy,
                    recommendation="先暂停扩大投入，核实关键条件后再决定下一步。",
                    alternatives=[
                        "保留现有资源并等待下一轮信息。",
                        "缩小验证范围，只处理最关键的问题。",
                    ],
                    objection="当前信息不足，不宜做不可逆的新增承诺。",
                    stop_condition="关键条件仍无法核实或资源继续恶化时，停止追加投入。",
                ))
        actions = [
            action.model_copy(update={"yearly_strategy": yearly_strategy})
            for action in actions
        ]
        state = state.model_copy(
            update={"agent_constraints": self.coordinator.next_round_constraints}
        )

        # 创业由量化账本作为唯一事实状态机。LangGraph 在此前已完成四智能体
        # 的 RAG/MCP 观察、提案和 Judge；不允许通用 world-state 再写一次结果。
        if self.source.scenario_id == "general_startup":
            state, actions = self._advance_startup_year(
                state, user_msg, yearly_strategy, actions
            )
            debate = self.coordinator.build_debate(actions, user_msg)
            if debate is not None and state.timeline:
                state.timeline[-1] = state.timeline[-1].model_copy(
                    update={"debate": debate}
                )
            if state.phase == "completed":
                state = self._finalize(state)
            if srepo is not None and erepo is not None:
                self._persist_agent_events(erepo, session_id, state)
                self._persist_session_state(srepo, session_id, state)
            return state, False

        # 非创业场景继续使用通用外层状态机。
        outer_config = (
            {"configurable": {"thread_id": f"{session_id}-outer-{state.year + 1}"}}
            if self._checkpointer is not None
            else None
        )
        state = self._graph.invoke(
            {"state": state, "actions": actions, "transition": None, "ending": None},
            outer_config,
        )["state"]
        debate = self.coordinator.build_debate(actions, user_msg)
        if debate is not None and state.timeline:
            updated = state.model_copy(deep=True)
            updated.timeline[-1] = updated.timeline[-1].model_copy(
                update={"debate": debate}
            )
            state = updated

        # 干预判定
        choice = (intervention_choices or {}).get(state.year)
        iv_config = (
            {"configurable": {"thread_id": f"{session_id}-iv-{state.year}"}}
            if self._checkpointer is not None
            else None
        )
        iv = self._iv_graph.invoke(
            {"state": state, "choice": choice}, iv_config
        )
        interrupts = (
            iv.get("__interrupt__")
            if isinstance(iv, dict)
            else getattr(iv, "__interrupt__", None)
        )
        if interrupts:
            pending = PendingIntervention.model_validate(interrupts[0].value)
            paused = state.model_copy(deep=True)
            paused.phase = "paused"
            paused.pause_reason = "intervention_required"
            paused.pending_intervention = pending
            if srepo is not None and erepo is not None:
                self._persist_agent_events(erepo, session_id, state)
                self._persist_session_state(srepo, session_id, paused)
            return paused, True

        state = iv["state"]
        if state.timeline:
            state = state.model_copy(deep=True)
            state.timeline[-1] = state.timeline[-1].model_copy(
                update={
                    "world_state": state.world_state,
                    "agent_actions": actions,
                }
            )
        if state.phase == "completed":
            state = self._finalize(state)

        if srepo is not None and erepo is not None:
            self._persist_agent_events(erepo, session_id, state)
            self._persist_session_state(srepo, session_id, state)

        return state, False

    def iter_events(
        self,
        decision_vars: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        intervention_choices: dict[int, str] | None = None,
        strategy_directives: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
        db: "DbSession | None" = None,
        user_id: str | None = None,
        owner_key: str | None = None,
    ) -> Iterator[SimulationEvent]:
        session_id = str(uuid4())
        state = make_initial_state(
            self.source,
            decision_vars,
            user_profile=user_profile,
            success_definition=success_definition,
            session_id=session_id,
        )
        initial_decision = self._latest_user_message(conversation_history)
        if initial_decision:
            state = state.model_copy(update={"user_message": initial_decision})
        # 初步分析必须读取用户刚确认的意图；之后同一份简报传给四个智能体。
        state = self._ensure_scenario_brief(state)
        state = self._ensure_startup_ledger(state)

        # ── 持久化仓库（db 由调用方注入，None 时跳过落库）──
        srepo, erepo, screpo = None, None, None
        if db is not None:
            srepo = SimulationRepo(db)
            erepo = EventRepo(db)
            screpo = ScenarioRepo(db)
            self._persist_scenario(screpo)
            srepo.create(
                session_id=session_id,
                scenario_id=self.source.scenario_id,
                decision_vars=state.decision_vars,
                world_state=state.world_state.model_dump(mode="json"),
                user_id=user_id,
                owner_key=owner_key,
                # 冻结画像快照：用户日后改画像不影响本次推演的可复盘性
                user_profile=state.user_profile or None,
            )
            MessageRepo(db).save_batch(session_id, conversation_history or [])

        sequence = 0
        yield self._event(
            sequence,
            session_id,
            self.source.scenario_id,
            EventType.SIMULATION_STARTED,
            SimulationStartedPayload(
                year=state.year,
                world_state=state.world_state,
                initial_analysis=state.scenario_brief,
            ),
            state,
        )
        sequence += 1

        # 初步分析只建立共同起点，不能在用户提交第 1 年决策前推进时间线。
        paused_state = self.make_year_decision_state(
            state.model_copy(update={"user_message": ""})
        )
        if db is not None and srepo is not None:
            self._persist_session_state(srepo, session_id, paused_state)
            db.commit()
        yield self._event(
            sequence,
            session_id,
            self.source.scenario_id,
            EventType.SIMULATION_PAUSED,
            SimulationPausedPayload(
                year=paused_state.year,
                world_state=paused_state.world_state,
                pause_reason=paused_state.pause_reason,
            ),
            paused_state,
        )
        return

    def resume_events(
        self,
        session_id: str,
        state: SimulationState,
        choice: str,
        db: "DbSession | None" = None,
    ) -> Iterator[SimulationEvent]:
        """从暂停处恢复推演。

        state 应为已持久化的暂停状态（phase='paused'，含 pending_intervention）。
        choice 为用户在此干预点的选择（或逐年交互模式下的用户消息）。
        """
        sequence = 0
        variation_seed = str(random.randint(1000, 9999))

        # 恢复推演同样要带上画像，否则逐年交互模式下 Agent 从第 2 年起就"失忆"
        user_profile_summary = self._build_profile_summary(
            state.user_profile, state.decision_vars
        )

        # ── 持久化仓库 ──
        srepo, erepo = None, None
        if db is not None:
            srepo = SimulationRepo(db)
            erepo = EventRepo(db)

        # 分支 1：干预恢复 — 先应用干预选择，再 yield 更新后的 YEAR_COMPLETED
        if state.pending_intervention is not None:
            iv_config = (
                {"configurable": {"thread_id": f"{session_id}-iv-{state.year}"}}
                if self._checkpointer is not None
                else None
            )
            iv = self._iv_graph.invoke(
                {"state": state, "choice": choice}, iv_config
            )
            state = iv["state"].model_copy(
                update={"pause_reason": None, "user_message": ""}
            )

            if state.phase == "completed":
                state = self._finalize(state)

            if db is not None:
                self._persist_agent_events(erepo, session_id, state)
                self._persist_session_state(srepo, session_id, state)

            timeline = state.timeline[-1] if state.timeline else None
            yield self._event(
                sequence,
                session_id,
                self.source.scenario_id,
                EventType.YEAR_COMPLETED,
                YearCompletedPayload(
                    year=state.year,
                    world_state=state.world_state,
                    state_diff=timeline.state_diff if timeline else {},
                    agent_actions=timeline.agent_actions if timeline else [],
                    ending=timeline.ending if timeline else None,
                    score=state.score,
                    debate=timeline.debate if timeline else None,
                    business_dashboard=state.startup_dashboard,
                ),
                state,
            )
            sequence += 1

            if state.phase == "completed":
                yield self._event(
                    sequence,
                    session_id,
                    self.source.scenario_id,
                    EventType.SIMULATION_COMPLETED,
                    SimulationCompletedPayload(
                        year=state.year,
                        result=state.result or "timeout",
                        world_state=state.world_state,
                        score=state.score,
                        score_detail=state.score_detail,
                        risks=state.risks,
                        action_plan=state.action_plan,
                        startup_settlement=state.startup_settlement,
                    ),
                    state,
                )
                if db is not None:
                    db.commit()
                return

            if state.year >= self._max_years(state.decision_vars):
                paused_state = self.make_horizon_review_state(state)
            else:
                paused_state = self.make_year_decision_state(state)
            if db is not None and srepo is not None:
                self._persist_session_state(srepo, session_id, paused_state)
                db.commit()
            yield self._event(
                sequence,
                session_id,
                self.source.scenario_id,
                EventType.SIMULATION_PAUSED,
                SimulationPausedPayload(
                    year=paused_state.year,
                    world_state=paused_state.world_state,
                    pause_reason=paused_state.pause_reason,
                ),
                paused_state,
            )
            return

        # 分支 2：逐年交互恢复 — 无干预，直接继续后续年份
        # （不再重复 yield 已完成年份的 YEAR_COMPLETED，该事件在 iter_events 中已发送）
        remaining_years = min(
            1,
            self._max_years(dict(state.decision_vars)) - state.year,
        )
        for _ in range(remaining_years):
            yearly_strategy = (
                state.yearly_strategy
                if state.yearly_strategy in {"aggressive", "steady", "conservative"}
                else "steady"
            )
            state = state.model_copy(
                update={
                    "phase": "simulating",
                    "pause_reason": None,
                    "user_message": state.user_message or choice,
                }
            )
            next_year = state.year + 1

            yield self._event(
                sequence, session_id, self.source.scenario_id,
                EventType.YEAR_STARTED,
                YearStartedPayload(
                    year=next_year, world_state=state.world_state,
                    strategy_prompt=f"第{next_year}年开始，请选择策略",
                    available_strategies=["aggressive", "steady", "conservative"],
                    current_strategy=yearly_strategy,
                ),
                state,
            )
            sequence += 1

            state, is_paused = self._advance_year(
                state, session_id, yearly_strategy, user_profile_summary, variation_seed,
                None, srepo, erepo,
            )
            if is_paused:
                if db is not None:
                    db.commit()
                # 与首次推演一致：恢复后触发风险节点，也先展示本年度结果。
                timeline = state.timeline[-1]
                yield self._event(
                    sequence,
                    session_id,
                    self.source.scenario_id,
                    EventType.YEAR_COMPLETED,
                    YearCompletedPayload(
                        year=state.year,
                        world_state=state.world_state,
                        state_diff=timeline.state_diff,
                        agent_actions=timeline.agent_actions,
                        ending=timeline.ending,
                        score=state.score,
                        debate=timeline.debate,
                        business_dashboard=state.startup_dashboard,
                    ),
                    state,
                )
                sequence += 1
                pending = state.pending_intervention
                yield self._event(
                    sequence, session_id, self.source.scenario_id,
                    EventType.INTERVENTION_PENDING,
                    InterventionPendingPayload(
                        year=state.year, world_state=state.world_state,
                        pending_intervention=pending,
                    ),
                    state,
                )
                sequence += 1
                yield self._event(
                    sequence, session_id, self.source.scenario_id,
                    EventType.SIMULATION_PAUSED,
                    SimulationPausedPayload(
                        year=state.year, world_state=state.world_state,
                        pending_intervention=pending,
                        pause_reason=state.pause_reason,
                    ),
                    state,
                )
                return

            tl = state.timeline[-1]
            yield self._event(
                sequence,
                session_id,
                self.source.scenario_id,
                EventType.YEAR_COMPLETED,
                YearCompletedPayload(
                    year=state.year,
                    world_state=state.world_state,
                    state_diff=tl.state_diff,
                    agent_actions=tl.agent_actions,
                    ending=tl.ending,
                    score=state.score,
                    debate=tl.debate,
                    business_dashboard=state.startup_dashboard,
                ),
                state,
            )
            sequence += 1

            # 统一交互协议：每一个已结算年度都把下一步决策权还给用户。
            if state.phase != "completed":
                paused_state = state.model_copy(deep=True)
                if state.year >= self._max_years(state.decision_vars):
                    paused_state = self.make_horizon_review_state(paused_state)
                else:
                    paused_state = self.make_year_decision_state(paused_state)
                if db is not None and srepo is not None:
                    self._persist_session_state(srepo, session_id, paused_state)
                    db.commit()
                yield self._event(
                    sequence, session_id, self.source.scenario_id,
                    EventType.SIMULATION_PAUSED,
                    SimulationPausedPayload(
                        year=state.year, world_state=state.world_state,
                        pending_intervention=None,
                        pause_reason=paused_state.pause_reason,
                    ),
                    paused_state,
                )
                return

            if state.phase == "completed":
                yield self._event(
                    sequence,
                    session_id,
                    self.source.scenario_id,
                    EventType.SIMULATION_COMPLETED,
                    SimulationCompletedPayload(
                        year=state.year,
                        result=state.result or "timeout",
                        world_state=state.world_state,
                        score=state.score,
                        score_detail=state.score_detail,
                        risks=state.risks,
                        action_plan=state.action_plan,
                        startup_settlement=state.startup_settlement,
                    ),
                    state,
                )
                if db is not None:
                    db.commit()
                return

        # 到达用户选择的推演年限时先请求确认，不自动结算。
        state = self.make_horizon_review_state(state)
        if db is not None:
            self._persist_agent_events(erepo, session_id, state)
            self._persist_session_state(srepo, session_id, state)
        yield self._event(
            sequence,
            session_id,
            self.source.scenario_id,
            EventType.SIMULATION_PAUSED,
            SimulationPausedPayload(
                year=state.year,
                world_state=state.world_state,
                pause_reason=state.pause_reason,
            ),
            state,
        )
        if db is not None:
            db.commit()

    async def aiter_events(
        self,
        decision_vars: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        intervention_choices: dict[int, str] | None = None,
        strategy_directives: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
        db: "DbSession | None" = None,
        user_id: str | None = None,
        owner_key: str | None = None,
    ) -> AsyncIterator[SimulationEvent]:
        import os
        delay_ms = float(os.getenv("SIMULATION_EVENT_DELAY_MS", "0"))
        # 同步生成器内部调用 LangGraph / LLM，均为同步阻塞；若在事件循环里直接
        # 迭代会把 uvicorn 事件循环占死，导致并发请求（如登录）全部超时。
        # 因此逐步用 asyncio.to_thread 拉到线程池执行，每次 yield 让出事件循环。
        iterator = self.iter_events(
            decision_vars,
            user_profile=user_profile,
            conversation_history=conversation_history,
            intervention_choices=intervention_choices,
            strategy_directives=strategy_directives,
            success_definition=success_definition,
            db=db,
            user_id=user_id,
            owner_key=owner_key,
        )
        while True:
            # StopIteration 不能从 to_thread 的 Future 里抛出，用哨兵值代替
            event = await asyncio.to_thread(_next_or_none, iterator)
            if event is None:
                break
            yield event
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)
            else:
                await asyncio.sleep(0)

    def persist(
        self,
        state: SimulationState,
        db: "DbSession | None" = None,
        user_id: str | None = None,
    ) -> str:
        """全量快照落库（db 由调用方注入，None 时抛异常）。"""
        if db is None:
            raise ValueError("persist() requires a non-None db session")

        screpo = ScenarioRepo(db)
        srepo = SimulationRepo(db)

        self._persist_scenario(screpo)

        existing = srepo.get(state.session_id)
        if existing is None:
            return srepo.create(
                session_id=state.session_id,
                scenario_id=state.scenario_id,
                decision_vars=state.decision_vars,
                world_state=state.world_state.model_dump(mode="json"),
                user_id=user_id,
            )

        self._persist_session_state(srepo, state.session_id, state)
        db.commit()
        return state.session_id

    def run(
        self,
        decision_vars: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        intervention_choices: dict[int, str] | None = None,
        strategy_directives: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
        db: "DbSession | None" = None,
        user_id: str | None = None,
        owner_key: str | None = None,
    ) -> SimulationState:
        final_state: SimulationState | None = None
        for event in self.iter_events(
            decision_vars,
            user_profile=user_profile,
            conversation_history=conversation_history,
            intervention_choices=intervention_choices,
            strategy_directives=strategy_directives,
            success_definition=success_definition,
            db=db,
            user_id=user_id,
            owner_key=owner_key,
        ):
            if isinstance(event.state_snapshot, SimulationState):
                final_state = event.state_snapshot
        if final_state is None:
            raise RuntimeError("simulation produced no state")
        # 同步 run 是供批量 API/测试使用的无交互入口；流式入口保留年限确认。
        if final_state.phase == "horizon_review":
            final_state = self.finalize_horizon_review(final_state)
            if db is not None:
                self.persist(final_state, db=db, user_id=user_id)
        # iter_events 已在内部完成增量持久化；此处只返回结果
        return final_state

    def run_batch(
        self,
        decision_vars: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        intervention_choices: dict[int, str] | None = None,
        strategy_directives: dict[int, str] | None = None,
        success_definition: dict[str, Any] | None = None,
    ) -> SimulationState:
        """用于 A/B 对比的非交互批量推演。

        用户推演必须逐年确认；比较功能则需要得到两个完整、可比较的结算结果。
        此入口复用同一套年度推进和干预规则，并在调用方没有提供干预选项时选择
        场景声明的首个选项。默认选择是确定性的，且不会写入用户会话。
        """
        initial_events = list(
            self.iter_events(
                decision_vars,
                user_profile=user_profile,
                conversation_history=conversation_history,
                success_definition=success_definition,
            )
        )
        if not initial_events:
            raise RuntimeError("batch simulation produced no initial state")
        state = initial_events[-1].state_snapshot
        strategies = dict(strategy_directives or {})
        initial_decision = self._latest_user_message(conversation_history)
        max_steps = self.maximum_supported_years() * 3 + 3

        for _ in range(max_steps):
            if state.phase == "completed":
                return self._finalize(state)

            if state.pause_reason == "horizon_review":
                return self.finalize_horizon_review(state)

            if state.pause_reason == "year_decision_required":
                strategy = strategies.get(state.year + 1, "steady")
                if strategy not in {"aggressive", "steady", "conservative"}:
                    strategy = "steady"
                decision_text = {
                    "aggressive": "按进取方案扩大验证范围并加快执行。",
                    "conservative": "按稳健方案控制投入并保留现金缓冲。",
                    "steady": "按当前节奏推进，并根据结果调整投入。",
                }[strategy]
                if state.year == 0 and initial_decision:
                    decision_text = initial_decision
                resumed_events = list(
                    self.resume_events(
                        state.session_id,
                        state.model_copy(
                            update={
                                "yearly_strategy": strategy,
                                "user_message": decision_text,
                            }
                        ),
                        decision_text,
                    )
                )
            elif state.pending_intervention is not None:
                choice = (intervention_choices or {}).get(state.year)
                if choice is None:
                    choice = state.pending_intervention.options[0]
                resumed_events = list(
                    self.resume_events(state.session_id, state, choice)
                )
            else:
                raise RuntimeError(
                    "batch simulation reached an unsupported pause state: "
                    f"{state.pause_reason!r}"
                )

            if not resumed_events:
                raise RuntimeError("batch simulation resume produced no state")
            state = resumed_events[-1].state_snapshot

        raise RuntimeError("batch simulation exceeded its step guard")
