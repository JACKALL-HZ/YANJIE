"""Judge Agent — 跨 Agent 回合校验，检测动作冲突。

StubJudge：基于规则（动作组合 + 现金阈值）
JudgeAgent：基于 LLM 评审 4 Agent 的决策一致性
"""

import json
import re

from pydantic import BaseModel, Field

from app.agents.contracts import AgentContext
from app.engine.models import AgentAction


_AGENT_NAMES = {
    "market": "市场智能体",
    "environment": "环境智能体",
    "personal": "个人智能体",
    "risk": "风险智能体",
}


class JudgeResult(BaseModel):
    """Judge 评审结果。"""
    judge_ok: bool = Field(description="回合是否通过校验")
    severity: float = Field(ge=0, le=1, description="冲突严重程度，0=无冲突，1=严重")
    conflicts: list[str] = Field(default_factory=list, description="冲突描述列表")
    recommendations: list[str] = Field(default_factory=list, description="修正建议")


def _chinese_items(items: list[object], fallback: str) -> list[str]:
    """裁判结论会直接展示给用户，无法确认中文可读性时统一降级。"""
    normalized: list[str] = []
    for item in items:
        text = str(item).strip()
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            normalized.append(text)
        else:
            normalized.append(fallback)
    return list(dict.fromkeys(normalized))


# ── 冲突对映射：当两个 Agent 同时选了以下对时，标记为潜在冲突 ──
_CONFLICT_PAIRS: set[tuple[str, str]] = {
    ("market.differentiate", "risk.contain"),   # 激进扩张 vs 收紧防御
    ("market.differentiate", "personal.defer"),  # 扩张 vs 推迟
    ("environment.localize", "risk.contain"),    # 本地化投资 vs 收紧
}

# 单动作总现金消耗 > 此阈值时标记
_CASH_BURN_THRESHOLD = 25000
# 现金 < 此阈值时额外敏感
_LOW_CASH_THRESHOLD = 60000

# 每个动作的估算现金影响（简化，用于 stub 判定）
_ACTION_CASH_IMPACT: dict[str, int] = {
    "market.differentiate": 22000,
    "market.hold": 5000,
    "environment.localize": 8000,
    "environment.monitor": 2000,
    "personal.stabilize": 8000,
    "personal.defer": 2000,
    "risk.contain": 7000,
    "risk.insure": 3000,
}


class StubJudge:
    """基于规则的 Judge，不调 LLM。"""

    def judge(
        self,
        actions: list[AgentAction],
        contexts: dict[str, AgentContext],
    ) -> JudgeResult:
        conflicts: list[str] = []
        recommendations: list[str] = []

        action_map = {a.agent_id: a for a in actions}
        action_ids = [a.action_id for a in actions]

        # 1. 检测冲突对
        for i in range(len(action_ids)):
            for j in range(i + 1, len(action_ids)):
                pair = (action_ids[i], action_ids[j])
                reverse = (action_ids[j], action_ids[i])
                if pair in _CONFLICT_PAIRS or reverse in _CONFLICT_PAIRS:
                    conflicts.append(
                        f"冲突：{_AGENT_NAMES.get(actions[i].agent_id, '专家智能体')}选择了一个动作，"
                        f"与{_AGENT_NAMES.get(actions[j].agent_id, '专家智能体')}的选择存在矛盾"
                    )

        # 2. 检测总现金消耗
        total_cash = sum(
            _ACTION_CASH_IMPACT.get(a.action_id, 0) for a in actions
        )
        # 从任意 context 取 cash_flow
        ws = next(iter(contexts.values())).world_state if contexts else {}
        current_cash = ws.get("cash_flow", 1_000_000)

        if total_cash > _CASH_BURN_THRESHOLD:
            conflicts.append(
                f"总现金消耗 {total_cash} 超过阈值 {_CASH_BURN_THRESHOLD}"
            )
            recommendations.append("考虑减少高消耗动作")

        if current_cash - total_cash < _LOW_CASH_THRESHOLD:
            conflicts.append(
                f"执行后现金 {current_cash - total_cash} 低于安全线 {_LOW_CASH_THRESHOLD}"
            )
            recommendations.append("当前现金紧张，建议选低消耗动作")

        # 3. 检测全体保守 vs 全体激进
        aggressive_actions = {"market.differentiate", "environment.localize",
                              "personal.stabilize", "risk.contain"}
        aggressive_count = sum(1 for aid in action_ids if aid in aggressive_actions)
        if aggressive_count == 4:
            conflicts.append("全部智能体同时采取扩张策略，可能过度消耗资源")
            recommendations.append("建议至少让一个智能体转为保守策略")

        severity = min(1.0, len(conflicts) * 0.25)
        judge_ok = severity < 0.5

        return JudgeResult(
            judge_ok=judge_ok,
            severity=round(severity, 2),
            conflicts=conflicts,
            recommendations=recommendations,
        )


# ── LLM Judge ──

_JUDGE_SYSTEM = """你是衍界决策推演的裁判智能体，负责审核四个智能体的年度决策。

你的任务：检测当前回合中 Agent 动作之间的冲突。

冲突示例：
- 市场智能体激进扩张，而风险智能体同时收紧防御 → 策略矛盾
- 四个智能体在现金流紧张时全部选择高成本动作 → 难以持续
- 个人智能体推迟行动，而市场智能体大举扩张 → 战略不一致

请用中文回复一个 JSON 对象：
{
  "judge_ok": true/false,
  "severity": 0.0 到 1.0,
  "conflicts": ["每条冲突的描述"],
  "recommendations": ["修正建议"]
}

只标记真正的冲突——不是每种混合策略都有问题。
severity < 0.5 → judge_ok = true。"""


_JUDGE_USER = """推演年份：{year}
世界状态：{world_state_json}

四个智能体的决策（含立场）：
{actions_text}

请审核这些决策是否与各自立场一致："""


def _extract_balanced_json(text: str) -> str | None:
    """从文本中提取第一个平衡的 { ... } JSON 字符串（支持嵌套）。"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _json_from_text(text: str) -> dict | None:
    """从 LLM 响应中提取 JSON。"""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    balanced = _extract_balanced_json(text)
    if balanced:
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass
    return None


class JudgeAgent:
    """基于 LLM 的 Judge Agent。"""

    def __init__(self, llm: "BaseChatModel"):  # type: ignore[name-defined]
        self.llm = llm

    def judge(
        self,
        actions: list[AgentAction],
        contexts: dict[str, AgentContext],
    ) -> JudgeResult:
        if not actions:
            return JudgeResult(judge_ok=True, severity=0, conflicts=[], recommendations=[])

        year = contexts[actions[0].agent_id].year if contexts else 1
        ws = next(iter(contexts.values())).world_state if contexts else {}

        # 构建 LLM prompt
        from langchain_core.messages import HumanMessage, SystemMessage

        action_lines = []
        for a in actions:
            ctx = contexts.get(a.agent_id)
            stance = getattr(ctx, "agent_stance", "") if ctx else ""
            parts = [_AGENT_NAMES.get(a.agent_id, "专家智能体")]
            if stance:
                parts.append(f"({stance})")
            parts.append(
                f"：选择内部动作编号“{a.action_id}”，理由：“{a.reason}”"
            )
            action_lines.append("  - " + " ".join(parts))
        actions_text = "\n".join(action_lines)

        messages = [
            SystemMessage(content=_JUDGE_SYSTEM),
            HumanMessage(content=_JUDGE_USER.format(
                year=year,
                world_state_json=json.dumps(ws, ensure_ascii=False, indent=2),
                actions_text=actions_text,
            )),
        ]

        try:
            response = self.llm.invoke(messages)
            data = _json_from_text(response.content)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Judge LLM call failed, passing through")
            return JudgeResult(
                judge_ok=True,
                severity=0.0,
                conflicts=[],
                recommendations=[],
            )

        if data is None:
            return JudgeResult(
                judge_ok=True,  # 保守策略
                severity=0.0,
                conflicts=[],
                recommendations=["裁判模型返回内容无法解析，本轮按无冲突处理。"],
            )

        return JudgeResult(
            judge_ok=bool(data.get("judge_ok", True)),
            severity=min(1.0, max(0.0, float(data.get("severity", 0)) or 0)),
            conflicts=_chinese_items(
                list(data.get("conflicts", [])),
                "当前策略在投入节奏与风险承受范围上存在分歧。",
            ),
            recommendations=_chinese_items(
                list(data.get("recommendations", [])),
                "先用小范围、可撤回的方式验证，再决定是否扩大执行。",
            ),
        )
