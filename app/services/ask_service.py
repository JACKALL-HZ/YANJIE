"""深度追问服务 —— 基于模拟上下文回答用户问题。"""

import json
from typing import Any

from app.core.config import Settings, get_settings
from app.core.llm import build_llm
from app.core.sanitize import sanitize_rag_content, sanitize_user_input
from app.db.repository import SimulationRepo
from sqlalchemy.orm import Session


_ASK_SYSTEM = """你是衍界推演分析师，仅基于下方提供的模拟上下文数据回答用户问题。如果数据不足以回答，请明确说明。回答要具体——提到哪个智能体、哪一年、做了什么决策。

上下文格式：
- 决策变量：用户的初始参数
- 时间线：逐年的 Agent 决策和世界状态变化
- 最终状态：结局、评分、风险清单

全程使用中文回答，不要输出英文角色名、内部字段名或程序编号。"""


class AskService:
    """深度追问业务逻辑。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._llm = (
            build_llm(self.settings.fast_llm)
            if not self.settings.llm_use_stub
            else None
        )
        # 开启流式：保证 .stream()/.astream() 逐 token 产出（invoke 仍返回整段，不受影响）
        if self._llm is not None:
            self._llm.streaming = True

    def ask(
        self,
        session_id: str,
        question: str,
        year: int | None = None,
        db: Session | None = None,
    ) -> str:
        """基于模拟数据回答用户追问。

        Args:
            session_id: 模拟会话 ID
            question: 用户问题
            year: 限定年份（只使用 ≤year 的 timeline）
            db: 数据库会话

        Returns:
            LLM 生成的答案（中文）
        """
        import logging
        _log = logging.getLogger(__name__)

        context = self._build_context(session_id, year, db)
        _log.info("Ask context built: %d chars, session=%s", len(context), session_id)

        if "not found" in context.lower():
            return "该模拟会话不存在，请检查 session_id 是否正确。"

        if self._llm is None:
            _log.info("Ask using stub (LLM is None)")
            return self._stub_answer(question, context)

        from langchain_core.messages import HumanMessage, SystemMessage

        safe_question = sanitize_user_input(question)
        safe_context = self._localized_context(sanitize_rag_content(context))

        messages = [
            SystemMessage(content=_ASK_SYSTEM),
            HumanMessage(content=f"模拟上下文：\n{safe_context}\n\n用户问题：{safe_question}"),
        ]
        try:
            response = self._llm.invoke(messages)
            text = str(response.content or "").strip()
            _log.info("Ask LLM response: %d chars", len(text))
            if not text:
                return "抱歉，模型返回了空内容，请稍后重试。"
            return text
        except Exception:
            _log.exception("Ask LLM invoke failed")
            return "抱歉，模型暂时不可用，请稍后重试。"

    def _build_context(
        self,
        session_id: str,
        year: int | None = None,
        db: Session | None = None,
    ) -> str:
        """构建完整上下文文本。"""
        parts: list[str] = []

        # 如果有 DB，读取 session 数据
        if db is not None:
            srepo = SimulationRepo(db)
            session = srepo.get(session_id)
            if session is None:
                return f"[Session {session_id} not found]"

            # 决策变量
            dv = session.decision_vars or {}
            if dv:
                parts.append("## Decision Variables")
                parts.append(json.dumps(dv, ensure_ascii=False, indent=2))
                parts.append("")

            # 时间线（按年份过滤）
            timeline = session.timeline or []
            if year is not None:
                timeline = [n for n in timeline if n.get("year", 0) <= year]
            if timeline:
                parts.append("## Timeline")
                parts.append(json.dumps(timeline, ensure_ascii=False, indent=2))
                parts.append("")

            # 最终结果
            result_info = {
                "result": session.result,
                "score": session.score,
                "score_detail": session.score_detail,
                "risks": session.risks,
            }
            parts.append("## Final State")
            parts.append(json.dumps(result_info, ensure_ascii=False, indent=2))
            parts.append("")

            # 行动计划
            if session.action_plan:
                parts.append("## Action Plan")
                parts.append(json.dumps(session.action_plan, ensure_ascii=False, indent=2))
                parts.append("")
        else:
            parts.append(f"[Session ID: {session_id}]")

        return "\n".join(parts) if parts else "No context available."

    @staticmethod
    def _localized_context(context: str) -> str:
        """把内部报告标记翻译成中文后再送入模型，保留内部标记供旧逻辑识别。"""
        replacements = {
            "## Decision Variables": "## 决策变量",
            "## Timeline": "## 时间线",
            "## Final State": "## 最终状态",
            "## Action Plan": "## 行动计划",
            "No context available.": "暂无可用的模拟上下文。",
        }
        localized = context
        for source, target in replacements.items():
            localized = localized.replace(source, target)
        return localized

    @staticmethod
    def _chunk_text(chunk) -> str:
        """从 LangChain AIMessageChunk 抽取文本片段（兼容 content 为 str 或 list）。"""
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(c) for c in content)
        return str(content) if content else ""

    def ask_stream_sync(
        self,
        session_id: str,
        question: str,
        year: int | None = None,
        db: Session | None = None,
    ):
        """同步流式追问生成器 —— 真实逐 token 输出，供 StreamingResponse 直接消费。

        直接调用 LLM 的 stream() 接口，token 一产生就 yield，
        首 token 延迟 = 模型首字延迟（而非等传统 invoke 等整段生成完再逐字拆帧）。
        DeepSeek / 硅基流动等 OpenAI 兼容端点原生支持。
        """
        import logging
        _log = logging.getLogger(__name__)

        context = self._build_context(session_id, year, db)
        _log.info("AskStream context: %d chars, session=%s", len(context), session_id)

        if "not found" in context.lower():
            for char in "该模拟会话不存在，请检查 session_id 是否正确。":
                yield char
            return

        if self._llm is None:
            _log.info("AskStream using stub")
            answer = self._stub_answer(question, context)
            for char in answer:
                yield char
            return

        from langchain_core.messages import HumanMessage, SystemMessage

        safe_question = sanitize_user_input(question)
        safe_context = self._localized_context(sanitize_rag_content(context))
        messages = [
            SystemMessage(content=_ASK_SYSTEM),
            HumanMessage(content=f"模拟上下文：\n{safe_context}\n\n用户问题：{safe_question}"),
        ]
        try:
            collected: list[str] = []
            # 真实流式：ChatOpenAI.stream 逐 chunk 产出
            for chunk in self._llm.stream(messages):
                piece = self._chunk_text(chunk)
                if piece:
                    collected.append(piece)
                    yield piece
            text = "".join(collected).strip()
            _log.info("AskStream LLM streamed: %d chars", len(text))
            if not text:
                text = "抱歉，模型暂时无法生成回复，请稍后重试。"
                for char in text:
                    yield char
        except Exception:
            _log.exception("AskStream LLM stream failed")
            text = "抱歉，模型暂时不可用，请稍后重试。"
            for char in text:
                yield char

    async def ask_stream(
        self,
        session_id: str,
        question: str,
        year: int | None = None,
        db: Session | None = None,
    ):
        """异步流式追问：真实逐 token 返回 LLM 生成的答案（astream）。"""
        import logging
        _log = logging.getLogger(__name__)

        context = self._build_context(session_id, year, db)
        _log.info("AskStream context built: %d chars, session=%s", len(context), session_id)

        if "not found" in context.lower():
            yield "该模拟会话不存在，请检查 session_id 是否正确。"
            return

        if self._llm is None:
            _log.info("AskStream using stub (LLM is None)")
            answer = self._stub_answer(question, context)
            for char in answer:
                yield char
            return

        from langchain_core.messages import HumanMessage, SystemMessage

        safe_question = sanitize_user_input(question)
        safe_context = self._localized_context(sanitize_rag_content(context))
        messages = [
            SystemMessage(content=_ASK_SYSTEM),
            HumanMessage(content=f"模拟上下文：\n{safe_context}\n\n用户问题：{safe_question}"),
        ]
        try:
            collected: list[str] = []
            async for chunk in self._llm.astream(messages):
                piece = self._chunk_text(chunk)
                if piece:
                    collected.append(piece)
                    yield piece
            text = "".join(collected).strip()
            _log.info("AskStream LLM astreamed: %d chars", len(text))
            if not text:
                text = "抱歉，模型暂时无法生成回复，请稍后重试。"
                for char in text:
                    yield char
        except Exception:
            _log.exception("AskStream LLM astream failed")
            text = "抱歉，模型暂时不可用，请稍后重试。"
            for char in text:
                yield char

    def _stub_answer(self, question: str, context: str) -> str:
        """Stub 模式模板回答。"""
        # session 不存在
        if "not found" in context.lower():
            return "该模拟会话不存在，请检查 session_id 是否正确。"

        has_timeline = "## Timeline" in context

        if "market" in question.lower() or "市场" in question:
            return (
                "根据推演数据，市场智能体在第1年建议了差异化策略，"
                "原因是考虑到行业竞争激烈（模拟中竞争数持续较高）。"
                "如需更详细的分析，建议开启真实模型模式。"
            )
        elif "risk" in question.lower() or "风险" in question:
            return (
                "根据推演的最终风险清单，主要风险集中在现金流管理和竞争压力两个维度。"
                "风险智能体在推演中持续监控这些指标，并在达到阈值时触发了干预。"
            )
        elif has_timeline:
            return (
                "根据推演数据，模拟按年度推进，各智能体基于当时的世界状态做出决策。"
                "最终结局和评分已包含在报告中。如需更详细的分析，建议联系系统管理员。"
            )
        else:
            return (
                "当前为 Stub 模式，无法进行深度分析。"
                "建议开启真实模型模式以获得完整的追问体验。"
            )
