"""MCP 工具纯函数 —— 知识库检索 + 网络搜索。

从 server.py 中提取纯业务工具函数，便于单独测试和复用。
server.py 只保留 FastMCP 实例创建 + @mcp.tool 注册。
"""

import os

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── 知识库检索 ──


def search_knowledge(query: str, scenario_id: str | None = None) -> str:
    """混合检索 RAG 知识库：bge-m3 向量 + BM25 → RRF → reranker 重排。

    故障时静默返回空字符串，不阻断推演流程。
    """
    if not query or not query.strip():
        return ""
    from app.core.config import get_settings

    if not get_settings().rag_enabled:
        return "（知识库已禁用）"
    try:
        retriever = _get_retriever()
        where = {"scenario_id": scenario_id} if scenario_id else None
        hits = retriever.search(query.strip(), top_k=5, where=where)
        if not hits:
            return "（知识库暂无相关记录）"
        return _format_knowledge_results(hits)
    except Exception:
        logger.exception("search_knowledge failed")
        return "（知识库暂不可用）"


def _format_knowledge_results(hits: list[dict]) -> str:
    lines = ["【决策知识库参考】"]
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata", {})
        src = meta.get("source", "?")
        score = h.get("score", 0)
        lines.append(f"{i}. [{src}] (score={score:.3f}) {h['document'][:300]}")
    return "\n".join(lines)


# ── 网络搜索 ──


def search_web(query: str) -> str:
    """Tavily 网络搜索，API 故障或未配置 Key 时静默兜底。"""
    if not query or not query.strip():
        return ""
    try:
        tool = _get_tavily()
        if tool is None:
            return ""
        return tool.search(query.strip())
    except Exception:
        logger.exception("search_web failed")
        return "（搜索暂不可用）"


def assess_execution_capacity(
    profile_summary: str,
    decision_vars: dict,
    decision_brief: str = "",
) -> str:
    """基于用户画像评估时间、资源与执行约束，不调用外部服务。"""
    details = profile_summary.strip() or "画像信息有限"
    target = decision_brief.strip() or "当前计划"
    budget = decision_vars.get("budget")
    budget_text = f"可用预算为{budget}。" if budget is not None else "预算未明确。"
    return f"执行能力评估：{details[:240]}。针对“{target}”，{budget_text}建议拆分为可验证的小步骤。"


def run_risk_stress_test(
    world_state: dict,
    scenario_id: str,
    decision_brief: str = "",
) -> str:
    """依据世界状态做确定性压力测试，输出可承受损失与停止条件提示。"""
    cash = float(world_state.get("cash_flow", 0) or 0)
    progress = float(world_state.get("payback_ratio", 0) or 0)
    target = decision_brief.strip() or "当前计划"
    risk_level = "较高" if cash < 60_000 or progress < 0.3 else "可控"
    return (
        f"压力测试（{scenario_id}）：针对“{target}”，当前资源{cash:.0f}、"
        f"目标进度{progress:.0%}，下行风险{risk_level}；"
        "执行前应设定可承受损失和停止条件。"
    )


# ── 懒加载单例（MCP server 生命周期内复用） ──

_retriever = None
_tavily = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        from app.core.config import get_settings
        from app.kb.chroma_store import ChromaStore
        from app.kb.embedder import SiliconFlowEmbedder
        from app.kb.retriever import HybridRetriever

        settings = get_settings()
        embedder = (
            SiliconFlowEmbedder(settings.embedding)
            if settings.embedding.api_key
            else None
        )
        store = ChromaStore(persist_dir=settings.chroma_persist_dir)
        _retriever = HybridRetriever(store=store, embedder=embedder)
    return _retriever


def _get_tavily():
    global _tavily
    if _tavily is None:
        from app.tools.tavily_search import TavilySearchTool

        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            return None
        _tavily = TavilySearchTool(api_key=api_key)
    return _tavily
