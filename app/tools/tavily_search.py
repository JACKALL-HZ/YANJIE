"""Tavily Search 工具 —— 实时网络搜索，为 Agent 提供外部市场/政策信息。

API: https://docs.tavily.com/
"""

import httpx


class TavilySearchTool:
    """Tavily Search API 封装。

    用于在推演中实时搜索市场数据、政策变化、竞争对手信息等。
    """

    _API_URL = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        max_results: int = 5,
        search_depth: str = "basic",
    ):
        self._api_key = api_key
        self._max_results = max_results
        self._search_depth = search_depth

    def search(self, query: str) -> str:
        """执行搜索并返回格式化文本。错误时返回兜底文本，不抛异常。"""
        if not self._api_key:
            return ""  # 未配置 API Key 时静默返回

        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": self._search_depth,
            "max_results": self._max_results,
            "include_answer": True,
        }

        try:
            resp = httpx.post(self._API_URL, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return self._format(data)
        except Exception:
            return "（搜索暂时不可用）"

    @staticmethod
    def build_query(
        industry: str = "",
        city: str = "",
        year: int = 1,
        world_state: dict | None = None,
    ) -> str:
        """从推演上下文拼接搜索查询。"""
        parts: list[str] = []
        if industry:
            parts.append(industry.replace("_", " "))
        if city:
            parts.append(city)
        if year:
            parts.append(f"{2025 + year}年")

        ws = world_state or {}
        context_hints = []
        if ws.get("competition_count", 0) > 50:
            context_hints.append("竞争激烈")
        cash = ws.get("cash_flow", 0)
        if cash < 50000 and cash > 0:
            context_hints.append("资金紧张")
        if context_hints:
            parts.append(" ".join(context_hints))

        if not parts:
            return "创业决策 市场趋势"

        return " ".join(parts) + " 市场趋势 政策"

    # ── 内部方法 ──

    def _format(self, data: dict) -> str:
        results = data.get("results", [])
        if not results:
            return "（暂无搜索结果）"

        lines = ["【Tavily 实时搜索】"]
        if data.get("answer"):
            lines.append(f"AI 综述: {data['answer'][:300]}")

        for i, r in enumerate(results[:self._max_results], 1):
            title = r.get("title", "无标题")[:80]
            content = r.get("content", "")[:200]
            url = r.get("url", "")
            lines.append(f"  {i}. {title}")
            if content:
                lines.append(f"     {content}")
            if url:
                lines.append(f"     {url}")

        return "\n".join(lines)
