"""Dynamic, user-facing startup analysis prepared before the annual simulation."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.engine.models import SimulationState
from app.services.scenario_presenter import DECISION_VAR_LABELS


_SYSTEM = """你是衍界的创业决策分析师。只基于用户明确提供的条件和已检索到的资料，生成一份简洁的中文推演前简报。
禁止虚构城市政策、行业比例、协会统计、租金和竞争数量；没有可靠资料时必须写“待核实假设”。禁止输出英文变量名。
严格按以下格式输出，每段最多 2 条，每条不超过 45 个字，总长度不超过 380 字：
**经营判断**
• ...
**资金与盈亏**
• ...
**推演分歧**
• 市场/环境/个人/风险分别最关注什么
**开业前核实**
• ...
不要写开场白、结尾总结或大段背景介绍。"""


class StartupBriefGenerator:
    def __init__(self, llm: BaseChatModel | None):
        self.llm = llm

    def build(self, state: SimulationState) -> str:
        variables = dict(state.decision_vars)
        if self.llm is None:
            return self._fallback(variables)
        values = "\n".join(
            f"- {DECISION_VAR_LABELS.get(name, name)}：{value}"
            for name, value in variables.items()
        )
        try:
            response = self.llm.invoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=f"本次创业条件：\n{values}"),
            ])
            content = str(response.content).strip()
            return self._format_content(content, variables) if content else self._fallback(variables)
        except Exception:
            return self._fallback(variables)

    @staticmethod
    def _format_content(content: str, variables: dict[str, Any]) -> str:
        """将模型可能生成的长段落压缩成聊天窗口可读的四段简报。"""
        section_names = {
            "经营判断": ("经营判断", "本次经营判断"),
            "资金与盈亏": ("资金与盈亏", "资金与盈亏关注"),
            "推演分歧": ("推演分歧", "两年情景"),
            "开业前核实": ("开业前核实", "开业前必须核实"),
        }
        sections: dict[str, list[str]] = {name: [] for name in section_names}
        current: str | None = None
        for raw_line in content.replace("```markdown", "").replace("```", "").splitlines():
            line = raw_line.strip().lstrip("> ")
            if not line:
                continue
            heading = next(
                (name for name, aliases in section_names.items()
                 if any(alias in line.replace("*", "") for alias in aliases)),
                None,
            )
            if heading:
                current = heading
                continue
            if current is None:
                continue
            line = line.lstrip("-•● ")
            if not line or line.startswith("|"):
                continue
            sections[current].append(line[:100])

        if not any(sections.values()):
            return content[:1200]
        parts: list[str] = []
        for name, lines in sections.items():
            if not lines:
                continue
            parts.append(f"**{name}**\n" + "\n".join(f"• {line}" for line in lines[:2]))
        return "\n\n".join(parts)

    @staticmethod
    def _fallback(variables: dict[str, Any]) -> str:
        city = str(variables.get("city") or "目标城市")
        industry = str(variables.get("industry") or "当前业态")
        budget = float(variables.get("budget") or 0)
        years = int(variables.get("span_years") or 1)
        return (
            "## 本次经营判断\n"
            f"计划在{city}开展{industry}，可用预算约 {budget:,.0f} 元，推演周期 {years} 年。"
            "当前应先验证目标客群、选址与产品是否能形成稳定成交。\n\n"
            "## 资金与盈亏关注\n"
            "预算需拆分为开业投入、首月经营成本和不可动用的现金缓冲；具体租金、人工和平台成本均为待核实假设。\n\n"
            "## 两年情景\n"
            "保守情景先控制试错；中性情景以复购和单位利润改善为前提；悲观情景触及现金止损线时及时调整。\n\n"
            "## 开业前必须核实\n"
            "连续观察目标点位客流、同类竞品、租约和转让费，再决定是否签约。"
        )


_GENERIC_SYSTEM = """你是衍界智能向导，负责为用户的决策推演写启动前简报。
只依据用户提供的条件生成中文结论，不得编造政策、统计、价格或外部事实。
严格输出三段，每段最多两条：
**本次判断**：说明这次推演真正要验证的目标。
**关键约束**：指出用户条件中最影响结果的约束。
**四方关注点**：分别说明市场、环境、个人、风险智能体接下来各自核实什么。
不要开场白、不要英文变量名、不要重复原始字段。"""


class ScenarioBriefGenerator:
    """为非创业场景生成可传递给四个智能体的统一初步分析。"""

    def __init__(self, llm: BaseChatModel | None, scenario_title: str):
        self.llm = llm
        self.scenario_title = scenario_title

    def build(self, state: SimulationState) -> str:
        variables = dict(state.decision_vars)
        if self.llm is None:
            return self._fallback(state, variables)
        values = "\n".join(
            f"- {DECISION_VAR_LABELS.get(name, name)}：{value}"
            for name, value in variables.items()
            if value is not None
        )
        user_message = state.user_message or "用户已确认以上推演条件。"
        try:
            response = self.llm.invoke([
                SystemMessage(content=_GENERIC_SYSTEM),
                HumanMessage(
                    content=(
                        f"推演场景：{self.scenario_title}\n"
                        f"用户描述：{user_message}\n"
                        f"已确认条件：\n{values}"
                    )
                ),
            ])
            content = str(response.content).strip()
            return content[:1200] if content else self._fallback(state, variables)
        except Exception:
            return self._fallback(state, variables)

    def _fallback(
        self,
        state: SimulationState,
        variables: dict[str, Any],
    ) -> str:
        values = "、".join(
            f"{DECISION_VAR_LABELS.get(name, name)}：{value}"
            for name, value in variables.items()
            if value is not None and name != "span_years"
        ) or "尚待用户补充的条件"
        user_message = state.user_message or "已确认的推演目标"
        return (
            "**本次判断**\n"
            f"- 围绕「{self.scenario_title}」评估：{user_message}\n"
            f"- 本次已确认条件：{values}\n\n"
            "**关键约束**\n"
            "- 结果会随目标、预算、时间和个人资源的变化而调整；缺失条件仅按保守假设处理。\n\n"
            "**四方关注点**\n"
            "- 市场智能体看机会与竞争；环境智能体看规则与外部条件；个人智能体看执行路径；风险智能体看最坏结果与止损条件。"
        )
