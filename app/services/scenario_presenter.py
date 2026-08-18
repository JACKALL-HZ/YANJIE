"""场景 API 的中文展示转换。"""

from typing import Any

from app.schemas.decision_source import AgentDef, DecisionVarDef, StateMetricDef


DECISION_VAR_LABELS: dict[str, str] = {
    "budget": "可用预算",
    "city": "所在城市",
    "industry": "所属行业",
    "span_years": "推演年数",
    "target_school": "目标院校",
    "current_level": "当前基础",
    "prep_months": "备考月数",
    "target_country": "目标国家",
    "target_major": "目标专业",
    "current_position": "当前职位",
    "target_position": "目标职位",
    "years_experience": "工作年限",
    "target_industry": "目标行业",
    "income": "当前月收入",
    "salary_expectation": "期望月薪",
    "investment_amount": "计划投资金额",
    "risk_level": "风险偏好",
}

AGENT_NAMES: dict[str, str] = {
    "market": "市场智能体",
    "environment": "环境智能体",
    "personal": "个人智能体",
    "risk": "风险智能体",
}


def present_decision_var(definition: DecisionVarDef) -> dict[str, Any]:
    """保留提交用字段名，并提供给 UI 的中文名称。"""
    return {
        **definition.model_dump(),
        "label": DECISION_VAR_LABELS.get(definition.name, "决策条件"),
    }


def present_agent(agent: AgentDef) -> dict[str, Any]:
    """统一四个角色的用户可见名称，避免暴露英文配置。"""
    return {
        **agent.model_dump(),
        "name": AGENT_NAMES[agent.agent_id],
    }


def present_state_metric(metric: StateMetricDef) -> dict[str, Any]:
    return metric.model_dump()
