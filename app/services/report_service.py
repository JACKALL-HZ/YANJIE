"""历史推演报告服务。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repository import MessageRepo, SimulationRepo
from app.scenarios.loader import ScenarioLoader
from app.schemas.report import (
    ReportActionPlanItem,
    ReportAgentAction,
    ReportConclusion,
    ReportDecision,
    ReportMetric,
    ReportMessage,
    ReportRisk,
    ReportScore,
    ReportYear,
    SimulationReport,
)


_METRIC_LABELS = {
    "cash_flow": "现金储备",
    "customer_flow": "每日客流",
    "competition_count": "周边竞争门店",
    "monthly_profit": "月利润",
    "payback_ratio": "回本进度",
    "study_budget": "备考资金",
    "study_time": "有效学习投入",
    "admission_competition": "录取竞争压力",
    "learning_progress": "阶段学习成效",
    "admission_readiness": "录取准备度",
    "application_readiness": "申请完成度",
    "application_materials": "申请材料准备",
    "visa_policy": "签证与政策准备",
    "language_preparation": "语言与适应准备",
    "monthly_study_gap": "月度留学支出缺口",
    "career_reserve": "职业调整缓冲",
    "work_visibility": "工作成果可见度",
    "promotion_competition": "晋升竞争压力",
    "salary_growth": "岗位回报匹配度",
    "promotion_readiness": "晋升准备度",
    "job_search_reserve": "求职资金缓冲",
    "interview_pipeline": "有效面试机会",
    "job_market_competition": "岗位竞争压力",
    "salary_match": "薪酬预期匹配度",
    "offer_readiness": "录用准备度",
    "down_payment_reserve": "首付后现金缓冲",
    "home_selection": "可选房源范围",
    "market_heat": "市场热度与政策变化",
    "mortgage_pressure": "月供压力",
    "purchase_readiness": "购房决策准备度",
    "liquidity_reserve": "投资外流动资金",
    "portfolio_diversification": "资产分散度",
    "market_volatility": "市场波动风险",
    "drawdown_control": "回撤控制",
    "return_progress": "收益目标进度",
}
_AGENT_LABELS = {
    "market": "市场智能体",
    "environment": "环境智能体",
    "personal": "个人智能体",
    "risk": "风险智能体",
}
_RESULT_LABELS = {
    "goal_reached": "达成目标",
    "steady": "稳步经营",
    "bankrupt": "经营失败",
    "timeout": "推演期结束",
    "user_ended": "用户主动结束",
}
_PHASE_LABELS = {
    "input": "等待开始",
    "simulating": "推演中",
    "paused": "等待你的决策",
    "horizon_review": "等待是否延长推演",
    "scoring": "正在生成结论",
    "completed": "推演已完成",
}
_PROFILE_LABELS = {
    "age": "年龄",
    "gender": "性别",
    "city": "所在城市",
    "education": "学历",
    "marital_status": "婚姻状况",
    "dependents": "需要照顾的人数",
    "family_burden": "家庭负担",
    "occupation": "职业",
    "industry": "所在行业",
    "years_experience": "工作年限",
    "skills": "技能",
    "certificates": "证书",
    "career_history": "职业经历",
    "strengths": "个人优势",
    "weaknesses": "需要提升的地方",
    "assets": "可用资产",
    "monthly_income": "月收入",
    "monthly_expense": "月支出",
    "liabilities": "负债",
    "income_stability": "收入稳定性",
    "insurance": "保险保障",
    "risk_appetite": "风险偏好",
    "loss_tolerance": "可承受损失",
    "decision_style": "决策风格",
    "past_failures": "过往经验",
    "available_time": "可投入时间",
    "weekly_hours": "每周可投入时间",
    "support_network": "支持资源",
    "goals": "目标",
    "constraints": "约束条件",
    "time_horizon": "计划周期",
    "motivation": "行动动机",
}
_PROFILE_VALUE_LABELS = {
    "aggressive": "积极进取",
    "balanced": "平衡",
    "conservative": "谨慎",
    "fulltime": "全职",
    "parttime": "兼职",
    "stable": "稳定",
    "unstable": "不稳定",
    "true": "是",
    "false": "否",
}
_SCORE_LABELS = {
    "market": "市场可行性",
    "resource": "资源充足度",
    "profitability": "盈利能力",
    "risk": "风险抵御能力",
}
_RISK_LEVEL_LABELS = {"high": "高", "medium": "中", "low": "低"}


def _risk_level_label(value: Any) -> str:
    if isinstance(value, (int, float)):
        if value >= 0.6:
            return "高"
        if value >= 0.25:
            return "中"
        return "低"
    return _RISK_LEVEL_LABELS.get(str(value), "待关注")


def _load_scenario(scenario_id: str | None) -> Any | None:
    if not scenario_id:
        return None
    try:
        return ScenarioLoader(get_settings().scenario_dir).load(scenario_id)
    except (OSError, ValueError):
        return None


def get_scenario_title(scenario_id: str | None) -> str:
    source = _load_scenario(scenario_id)
    return source.title if source is not None else scenario_id or "未命名场景"


def _format_number(value: Any, metric: str | None = None) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if metric in {"cash_flow", "monthly_profit"} and isinstance(value, (int, float)):
        return f"{value:,.0f} 元"
    if metric == "customer_flow" and isinstance(value, (int, float)):
        return f"{value:,.0f} 人/日"
    if metric == "competition_count" and isinstance(value, (int, float)):
        return f"{value:,.0f} 家"
    if metric == "payback_ratio" and isinstance(value, (int, float)):
        return f"{value * 100:.0f}%"
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "、".join(_format_profile_value(item) for item in value)
    return _format_profile_value(value)


def _format_profile_value(value: Any) -> str:
    if isinstance(value, str):
        return _PROFILE_VALUE_LABELS.get(value, value)
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _metric_items(world_state: dict[str, Any], state_diff: dict[str, Any] | None = None) -> list[ReportMetric]:
    items: list[ReportMetric] = []
    for key, label in _METRIC_LABELS.items():
        if key not in world_state:
            continue
        change = None
        if state_diff and key in state_diff:
            delta = state_diff[key]
            prefix = "+" if isinstance(delta, (int, float)) and delta > 0 else ""
            change = f"较本年初 {prefix}{_format_number(delta, key)}"
        items.append(ReportMetric(label=label, value=_format_number(world_state[key], key), change=change))
    return items


def _clean_reason(reason: Any) -> str:
    text = str(reason or "暂无说明")
    for raw, label in _METRIC_LABELS.items():
        text = text.replace(raw, label)
    text = text.replace("paybackratio", "回本进度")
    text = text.replace("competitioncount", "周边竞争门店数")
    return text


def _branch_labels(source: Any | None) -> dict[str, str]:
    if source is None:
        return {}
    return {
        branch.branch_id: branch.label
        for decision in source.decision_catalogue
        for branch in decision.branches
    }


def _profile_items(profile: dict[str, Any] | None) -> list[ReportMetric]:
    if not profile:
        return []
    return [
        ReportMetric(label=label, value=_format_number(profile[key], key))
        for key, label in _PROFILE_LABELS.items()
        if key in profile and profile[key] not in (None, "", [], {})
    ]


def build_report(session_id: str, db: Session) -> SimulationReport:
    """从持久化会话快照组装供页面和下载共用的报告。"""
    session = SimulationRepo(db).get(session_id)
    if session is None:
        raise ValueError(f"session not found: {session_id}")

    source = _load_scenario(session.scenario_id)
    branch_labels = _branch_labels(source)
    timeline = session.timeline or []
    initial_world = source.initial_world_state if source is not None else {}
    years = [
        ReportYear(
            year=int(node.get("year", 0)),
            metrics=_metric_items(node.get("world_state", {}), node.get("state_diff", {})),
            agent_actions=[
                ReportAgentAction(
                    agent_id=str(action.get("agent_id", "")),
                    agent_name=_AGENT_LABELS.get(str(action.get("agent_id", "")), "专家智能体"),
                    reason=_clean_reason(action.get("reason")),
                    generation_source=action.get("generation_source"),
                    llm_called=action.get("llm_called"),
                    rag_status=action.get("rag_status"),
                    rag_sources=list(action.get("rag_sources") or []),
                    position=action.get("position"),
                    evidence=list(action.get("evidence") or []),
                    recommendation=action.get("recommendation"),
                    alternatives=list(action.get("alternatives") or []),
                    objection=action.get("objection"),
                    stop_condition=action.get("stop_condition"),
                    confidence=(
                        f"{float(action['confidence']) * 100:.0f}%"
                        if action.get("confidence") is not None else None
                    ),
                )
                for action in node.get("agent_actions", [])
            ],
            ending=(
                _RESULT_LABELS.get(node["ending"].get("result"), "本年结算完成")
                if isinstance(node.get("ending"), dict) else None
            ),
            debate=node.get("debate"),
        )
        for node in timeline
    ]
    decisions = [
        ReportDecision(
            year=int(record.get("year", 0)),
            proposal=str(record.get("raw_text", "")),
            decision_label=record.get("decision_label"),
            selected_branch_label=branch_labels.get(record.get("selected_branch")),
            created_at=record.get("created_at"),
        )
        for record in (session.decision_history or [])
        if record.get("input_kind") == "business_decision"
    ]
    messages = []
    for message in MessageRepo(db).list_by_session(session_id):
        role, agent_id = MessageRepo.decode_role(message.role)
        messages.append(
            ReportMessage(
                role=role,
                agent_id=agent_id,
                content=message.content or "",
                year=message.year,
                created_at=(
                    message.created_at.isoformat()
                    if message.created_at else None
                ),
            )
        )
    score_details = [
        ReportScore(label=_SCORE_LABELS.get(key, "综合表现"), value=f"{float(value):.1f}")
        for key, value in (session.score_detail or {}).items()
    ]
    stored_risks = list(session.risks or [])
    stored_action_plan = list(session.action_plan or [])
    business_scenarios = {
        "milktea_startup",
        "restaurant_startup",
        "retail_store",
        "saas_startup",
        "general_startup",
    }
    legacy_business_metrics = {
        "cash_flow",
        "customer_flow",
        "competition_count",
        "monthly_profit",
        "payback_ratio",
    }
    # 旧版本把所有场景都按经营指标结算。报告读取时按原始会话重算，
    # 让历史的升学、留学、职场、买房和投资记录也能显示正确语义。
    if (
        session.scenario_id not in business_scenarios
        and {str(item.get("metric", "")) for item in stored_risks}
        & legacy_business_metrics
    ):
        from app.engine.scoring import build_action_plan, extract_risks

        recalculated_risks = extract_risks(
            session.world_state or {},
            scenario_id=session.scenario_id or "general_startup",
            decision_vars=session.decision_vars or {},
            user_profile=session.user_profile or {},
        )
        stored_risks = [item.model_dump() for item in recalculated_risks]
        stored_action_plan = [
            item.model_dump()
            for item in build_action_plan(
                recalculated_risks,
                scenario_id=session.scenario_id or "general_startup",
            )
        ]

    risks = [
        ReportRisk(
            level=_risk_level_label(item.get("severity")),
            title=_METRIC_LABELS.get(str(item.get("metric", "")), "经营风险"),
            message=_clean_reason(item.get("message")),
        )
        for item in stored_risks
    ]
    action_plan = [
        ReportActionPlanItem(
            title=_clean_reason(item.get("action") or item.get("message") or item.get("metric")),
            committed=bool(item.get("committed", False)),
        )
        for item in stored_action_plan
    ]

    return SimulationReport(
        session_id=session.id,
        scenario_id=session.scenario_id or "",
        scenario_title=get_scenario_title(session.scenario_id),
        created_at=session.created_at.isoformat() if session.created_at else None,
        profile=_profile_items(session.user_profile),
        initial_conditions=_metric_items(initial_world),
        decisions=decisions,
        messages=messages,
        years=years,
        conclusion=ReportConclusion(
            phase=session.phase,
            phase_label=_PHASE_LABELS.get(session.phase, "推演状态未知"),
            result_label=_RESULT_LABELS.get(session.result or "", "尚未得出最终结论"),
            score=f"{float(session.score):.1f}" if session.score is not None else None,
            score_details=score_details,
        ),
        risks=risks,
        action_plan=action_plan,
    )


def generate_markdown(session_id: str, db: Session) -> str:
    """将结构化报告渲染为可下载的 Markdown。"""
    report = build_report(session_id, db)
    lines = [f"# 推演报告: {report.scenario_title}", "", "## 概览", ""]
    lines.extend([
        "| 项目 | 内容 |", "|---|---|",
        f"| 会话编号 | {report.session_id} |",
        f"| 推演状态 | {report.conclusion.phase_label} |",
        f"| 结论 | {report.conclusion.result_label} |",
        f"| 综合评分 | {report.conclusion.score or '暂未评分'} |", "",
        "## 逐年推演", "",
    ])
    for year in report.years:
        lines.extend([f"### 第 {year.year} 年", ""])
        lines.extend(f"- {metric.label}: {metric.value}" for metric in year.metrics)
        lines.append("")
        lines.extend(f"- **{action.agent_name}**: {action.reason}" for action in year.agent_actions)
        lines.append("")
    lines.extend(["## 评分明细", ""])
    if report.conclusion.score_details:
        lines.extend(["| 维度 | 分数 |", "|---|---|"])
        lines.extend(
            f"| {item.label} | {item.value} |"
            for item in report.conclusion.score_details
        )
    else:
        lines.append("本次推演暂未生成评分明细。")
    lines.append("")
    lines.extend(["---", f"*报告生成时间: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}*"])
    return "\n".join(lines)
