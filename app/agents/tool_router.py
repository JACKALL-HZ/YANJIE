from typing import Any

from app.engine.models import SimulationState
from app.mcp_server.client import McpToolResult
from app.schemas.domain_models import AgentEvidence
from app.services.scenario_presenter import DECISION_VAR_LABELS


_ROLE_FOCUS = {
    "market": "需求、竞争、客群与机会",
    "environment": "政策、规则、宏观环境与外部约束",
}


_ROLE_FOCUS.update({
    "personal": "个人资源、时间投入、能力准备与执行节奏",
    "risk": "现金缓冲、不可逆投入、止损边界与下行损失",
})


class RoleToolRouter:
    """按角色白名单生成可审计的推演证据。"""

    def __init__(
        self,
        mcp_client: Any | None = None,
        retriever: Any | None = None,
        rag_enabled: bool = True,
    ):
        self._mcp = mcp_client
        self._retriever = retriever
        self._rag_enabled = rag_enabled

    def build_all(
        self,
        state: SimulationState,
        decision_brief: str,
        profile_summary: str,
    ) -> dict[str, list[AgentEvidence]]:
        return {
            "market": [self._knowledge_evidence("market", state, decision_brief)],
            "environment": [self._knowledge_evidence("environment", state, decision_brief)],
            "personal": [
                self._knowledge_evidence("personal", state, decision_brief),
                self._personal_evidence(state, decision_brief, profile_summary),
            ],
            "risk": [
                self._knowledge_evidence("risk", state, decision_brief),
                self._risk_evidence(state, decision_brief),
            ],
        }

    def _knowledge_evidence(
        self,
        agent_id: str,
        state: SimulationState,
        decision_brief: str,
    ) -> AgentEvidence:
        if not self._rag_enabled:
            return AgentEvidence(
                tool_name="search_knowledge",
                summary="知识库已禁用，本轮仅依据用户输入、当前状态和场景规则分析。",
                status="disabled",
            )

        query = self._query(_ROLE_FOCUS[agent_id], state, decision_brief)
        try:
            if self._mcp is not None:
                result = self._mcp.call(
                    "search_knowledge",
                    {"query": query, "scenario_id": state.scenario_id},
                )
                if isinstance(result, McpToolResult):
                    if result.status == "error":
                        return AgentEvidence(
                            tool_name="search_knowledge",
                            summary="Knowledge retrieval is unavailable for this round; scenario rules remain in effect.",
                            status="error",
                        )
                    text = result.content
                else:
                    # Keep compatibility with injected test doubles and legacy adapters.
                    text = result or ""
            elif self._retriever is not None:
                hits = self._retriever.search(
                    query, top_k=3, where={"scenario_id": state.scenario_id}
                )
                text = "\n".join(
                    f"[{item.get('metadata', {}).get('source', '?')}] "
                    f"{item.get('document', '')[:180]}"
                    for item in hits
                )
            else:
                return AgentEvidence(
                    tool_name="search_knowledge",
                    summary="知识库未启用，本轮仅依据场景规则推演。",
                    status="empty",
                )
        except Exception:
            return AgentEvidence(
                tool_name="search_knowledge",
                summary="知识库本轮不可用，已按场景规则继续推演。",
                status="error",
            )

        if "知识库已禁用" in text:
            return AgentEvidence(
                tool_name="search_knowledge",
                summary="知识库已禁用，本轮仅依据用户输入、当前状态和场景规则分析。",
                status="disabled",
            )
        if "知识库暂不可用" in text:
            return AgentEvidence(
                tool_name="search_knowledge",
                summary="知识库本轮不可用，已按用户输入、当前状态和场景规则继续分析。",
                status="error",
            )
        if not text.strip() or "知识库暂无相关记录" in text:
            return AgentEvidence(
                tool_name="search_knowledge",
                summary="未检索到与当前决策直接相关的资料。",
                status="empty",
            )
        return AgentEvidence(
            tool_name="search_knowledge",
            summary=text[:600],
            sources=self._sources(text),
            status="hit",
        )

    def _personal_evidence(
        self,
        state: SimulationState,
        decision_brief: str,
        profile_summary: str,
    ) -> AgentEvidence:
        try:
            text = self._call_or_local(
                "assess_execution_capacity",
                {
                    "profile_summary": profile_summary,
                    "decision_vars": state.decision_vars,
                    "decision_brief": decision_brief,
                },
                "执行能力评估：已结合用户画像、可用时间和资源约束进行判断。",
            )
            return AgentEvidence(
                tool_name="assess_execution_capacity",
                summary=text[:600],
                status="local",
            )
        except Exception:
            return AgentEvidence(
                tool_name="assess_execution_capacity",
                summary="执行能力评估暂不可用。",
                status="error",
            )

    def _risk_evidence(
        self, state: SimulationState, decision_brief: str
    ) -> AgentEvidence:
        try:
            text = self._call_or_local(
                "run_risk_stress_test",
                {
                    "world_state": state.world_state.model_dump(),
                    "scenario_id": state.scenario_id,
                    "decision_brief": decision_brief,
                },
                self._local_risk_summary(state),
            )
            return AgentEvidence(
                tool_name="run_risk_stress_test",
                summary=text[:600],
                status="local",
            )
        except Exception:
            return AgentEvidence(
                tool_name="run_risk_stress_test",
                summary="压力测试暂不可用。",
                status="error",
            )

    def _call_or_local(self, tool_name: str, arguments: dict[str, Any], fallback: str) -> str:
        if self._mcp is None:
            return fallback
        result = self._mcp.call(tool_name, arguments)
        if isinstance(result, McpToolResult):
            return result.content if result.status == "ok" else fallback
        return result or fallback

    @staticmethod
    def _query(focus: str, state: SimulationState, decision_brief: str) -> str:
        values = " ".join(
            f"{DECISION_VAR_LABELS.get(name, name)}={value}"
            for name, value in state.decision_vars.items()
            if value is not None and name != "span_years"
        )
        return (
            f"场景={state.scenario_id} 第{state.year}年 {focus} "
            f"{values} 用户决策={decision_brief or '尚未提出具体决策'}"
        )

    @staticmethod
    def _sources(text: str) -> list[str]:
        sources: list[str] = []
        for line in text.splitlines():
            if "[" not in line or "]" not in line:
                continue
            source = line.split("[", 1)[1].split("]", 1)[0].strip()
            if source and source not in sources:
                sources.append(source)
        return sources

    @staticmethod
    def _local_risk_summary(state: SimulationState) -> str:
        ws = state.world_state
        return (
            f"压力测试：当前可用资源为{ws.cash_flow:.0f}，"
            f"目标进度为{ws.payback_ratio:.0%}，"
            "应先明确可承受损失和停止条件。"
        )
