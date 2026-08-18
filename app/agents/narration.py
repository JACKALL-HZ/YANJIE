"""Deterministic, role-specific Chinese narration for local agent stubs."""

import re

from app.agents.contracts import AgentContext


_ROLE_REASONS = {
    "market": "市场顾问判断：{decision}有机会带来品牌曝光和新增客流，但要验证新增客流能否转化为复购。",
    "environment": "环境顾问判断：{decision}是否有效取决于本地客群、竞争门店和投放渠道的匹配程度。",
    "personal": "个人顾问判断：{decision}会增加创始人的执行与协调压力，团队承接能力需要提前安排。",
    "risk": "风险顾问判断：{decision}属于较大且难以撤回的投入，必须先设定最坏损失和止损线。",
}

_SCENE_ROLE_REASONS = {
    "market": "市场顾问判断：围绕{decision}，重点核对目标领域的需求、竞争强度和成功门槛。",
    "environment": "环境顾问判断：围绕{decision}，重点关注政策、汇率、行业变化等外部约束。",
    "personal": "个人顾问判断：围绕{decision}，重点评估你的能力、时间、资金和执行负荷。",
    "risk": "风险顾问判断：围绕{decision}，重点测算最坏损失、现金承受力和备选方案。",
}


_BASE_CONFIDENCE = {
    "market": 0.76,
    "environment": 0.7,
    "personal": 0.74,
    "risk": 0.68,
}

_INTERNAL_IDENTIFIER = re.compile(
    r"(?:cash_?flow|customer_?flow|monthly_?profit|competition_?count|"
    r"payback_?ratio|irreversibledownside|steady|aggressive|conservative|"
    r"differentiate|localize|stabilize|contain|insure)",
    re.IGNORECASE,
)
_UNEXPLAINED_ENGLISH = re.compile(r"[A-Za-z_]{4,}")


def requires_chinese_fallback(reason: str) -> bool:
    """Reject model text that would expose implementation vocabulary to users."""
    return bool(
        _INTERNAL_IDENTIFIER.search(reason)
        or _UNEXPLAINED_ENGLISH.search(reason)
    )


_REASON_TRANSLATIONS = {
    "cash_flow": "现金流",
    "cashflow": "现金流",
    "customer_flow": "客流量",
    "customerflow": "客流量",
    "competition_count": "竞争数量",
    "competitioncount": "竞争数量",
    "monthly_profit": "月利润",
    "monthlyprofit": "月利润",
    "payback_ratio": "回本比例",
    "paybackratio": "回本比例",
    "target_country": "目标国家",
    "target_major": "目标专业",
    "prep_months": "备考月数",
    "investment_amount": "投资金额",
    "irreversibledownside": "不可逆损失",
    "Agent": "智能体",
}


def normalize_agent_reason(reason: str) -> str:
    """翻译常见内部字段，避免把实现细节直接展示给用户。"""
    normalized = reason
    for internal, label in _REASON_TRANSLATIONS.items():
        normalized = re.sub(rf"(?<![A-Za-z_]){re.escape(internal)}(?![A-Za-z_])", label, normalized, flags=re.IGNORECASE)
    return normalized.strip()


def build_stub_reason(
    context: AgentContext,
    action_id: str | None = None,
) -> str:
    decision = context.latest_decision or context.scenario_title or "当前决策方案"
    templates = _SCENE_ROLE_REASONS if context.action_descriptions else _ROLE_REASONS
    template = templates.get(context.agent_id, "顾问判断：需要继续核实{decision}的影响。")
    reason = template.format(decision=decision)
    selected_action = action_id or (context.allowed_action_ids[0] if context.allowed_action_ids else "")
    action_description = context.action_descriptions.get(selected_action, "").strip()
    if action_description and not _UNEXPLAINED_ENGLISH.search(action_description):
        reason += f"本轮具体建议：{normalize_agent_reason(action_description)}"
    return reason


def build_action_presentation(
    context: AgentContext,
    action_id: str,
) -> dict[str, object]:
    """为任意 Agent 输出补齐稳定、可读的决策栏目。"""
    action_description = normalize_agent_reason(
        context.action_descriptions.get(action_id, "").strip()
    )
    decision = context.latest_decision or context.user_message or "当前决策"
    recommendation = action_description or f"围绕{decision}先做一项可验证的推进动作。"
    guidance = {
        "market": {
            "alternatives": [
                "保留现有渠道，先跟踪真实转化和复购。",
                "先访谈目标用户，再决定是否扩大触达。",
            ],
            "objection": "不要在目标客群尚未验证前同时铺开多个渠道。",
            "stop_condition": "连续两个复盘周期没有出现有效转化时，暂停扩量并调整方案。",
        },
        "environment": {
            "alternatives": [
                "先跟踪外部条件变化，再调整执行节奏。",
                "选择对政策和成本变化更敏感的低投入方案。",
            ],
            "objection": "不要把短期外部变化直接当作长期趋势。",
            "stop_condition": "政策、成本或平台规则出现明显不利变化时，冻结新增投入。",
        },
        "personal": {
            "alternatives": [
                "缩小本轮目标，只保留最关键的验证任务。",
                "先补齐协作和时间安排，再扩大执行范围。",
            ],
            "objection": "关键任务超过当前可投入时间时，不宜继续增加执行负荷。",
            "stop_condition": "核心任务连续两周无法按计划完成时，缩小目标或补齐协作资源。",
        },
        "risk": {
            "alternatives": [
                "先设定预算上限和最坏损失，再开始执行。",
                "保留更低成本、可随时退出的备选路径。",
            ],
            "objection": "新增不可逆投入前，必须确认剩余资源能够承受最坏情况。",
            "stop_condition": "现金缓冲触及预设下限，或单项试错超过预算时，立即停止追加。",
        },
    }.get(context.agent_id, {})
    return {
        "recommendation": recommendation,
        "key_factors": [
            "已结合本年度策略与推演状态。",
            "需要在执行过程中持续验证关键假设。",
        ],
        "next_actions": [recommendation],
        "uncertainty": (
            None if context.user_profile_summary else "尚未获得完整的个人画像。"
        ),
        "alternatives": list(guidance.get("alternatives", [])),
        "objection": guidance.get("objection"),
        "stop_condition": guidance.get("stop_condition"),
    }


def calculate_stub_confidence(context: AgentContext) -> float:
    """Lower confidence when profile evidence is absent or the proposal is uncertain."""
    confidence = _BASE_CONFIDENCE.get(context.agent_id, 0.65)
    if not context.user_profile_summary:
        confidence -= 0.08
    if any(marker in context.latest_decision for marker in ("明星", "代言", "大额", "重金")):
        confidence -= 0.08
    if context.rag_context or context.search_context:
        confidence += 0.03
    return max(0.45, min(0.9, round(confidence, 2)))
