from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Score(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: float = Field(ge=0, le=100)
    detail: dict[str, float]


class RiskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    severity: float = Field(ge=0, le=1)
    current_value: float
    message: str


class ActionPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    action: str
    quantity: str
    deadline: str


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _value(world_state: Mapping[str, float], metric: str) -> float:
    return float(world_state.get(metric, 0))


def _contextual_score(
    world_state: Mapping[str, float],
    result: str,
    scenario_id: str,
    decision_vars: Mapping[str, Any],
) -> Score:
    cash = _value(world_state, "cash_flow")
    signal = _value(world_state, "customer_flow")
    pressure = _value(world_state, "competition_count")
    outcome = _value(world_state, "monthly_profit")
    readiness = _clamp(_value(world_state, "payback_ratio") * 100)
    budget = float(
        decision_vars.get("budget")
        or decision_vars.get("investment_amount")
        or 1
    )

    resource = _clamp(cash / max(budget, 1) * 100)
    opportunity = _clamp(signal / 100 * 55 + (100 - pressure) / 100 * 45)
    progress = _clamp(outcome)
    labels = {
        "grad_exam": ("备考资源", "学习投入与竞争", "阶段完成度", "录取准备度"),
        "study_abroad": ("留学预算", "材料与竞争", "申请完成度", "申请准备度"),
        "career_advance": ("职业缓冲", "成果与竞争", "发展回报", "晋升准备度"),
        "job_hunting": ("求职储备", "面试与竞争", "薪资匹配", "Offer 准备度"),
        "house_purchase": ("资金缓冲", "房源与市场", "月供承受力", "购房准备度"),
        "investment": ("流动性储备", "分散与波动", "收益表现", "目标达成度"),
    }[scenario_id]

    if scenario_id == "study_abroad":
        progress = _clamp((outcome + 15000) / 30000 * 100)
    elif scenario_id == "career_advance":
        progress = _clamp(outcome / 30000 * 100)
    elif scenario_id == "job_hunting":
        expected = float(decision_vars.get("salary_expectation") or 15000)
        progress = _clamp(outcome / max(expected, 1) * 100)
    elif scenario_id == "house_purchase":
        income = float(decision_vars.get("income") or 30000)
        progress = _clamp(outcome / max(income * 0.4, 1) * 100)
    elif scenario_id == "investment":
        progress = _clamp(outcome / 10000 * 50 + readiness * 0.5)

    detail = {
        labels[0]: round(resource, 2),
        labels[1]: round(opportunity, 2),
        labels[2]: round(progress, 2),
        labels[3]: round(readiness, 2),
    }
    bonus = {
        "goal_reached": 8,
        "steady": 4,
        "bankrupt": -20,
        "timeout": 0,
        "user_ended": 0,
        "paused": -5,
    }.get(result, 0)
    return Score(
        total=round(_clamp(sum(detail.values()) / len(detail) + bonus), 2),
        detail=detail,
    )


def compute_score(
    world_state: Mapping[str, float],
    result: Literal[
        "goal_reached", "steady", "bankrupt", "timeout", "user_ended", "paused"
    ]
    | str,
    success_definition: dict | None = None,
    scenario_id: str = "",
    decision_vars: Mapping[str, Any] | None = None,
) -> Score:
    """计算四维评分。若提供 success_definition.priority，调整维度权重。"""
    if scenario_id in {
        "grad_exam",
        "study_abroad",
        "career_advance",
        "job_hunting",
        "house_purchase",
        "investment",
    }:
        return _contextual_score(
            world_state,
            result,
            scenario_id,
            decision_vars or {},
        )

    cash = _value(world_state, "cash_flow")
    customers = _value(world_state, "customer_flow")
    competition = _value(world_state, "competition_count")
    profit = _value(world_state, "monthly_profit")
    payback = _value(world_state, "payback_ratio")

    market = _clamp(customers / 200 * 70 + (100 - competition) / 100 * 30)
    resource = _clamp(cash / 200000 * 100)
    profitability = _clamp(profit / 50000 * 70 + payback * 30)
    risk_pressure = (
        _clamp((50000 - cash) / 50000 * 45)
        + _clamp((competition - 40) / 60 * 30)
        + _clamp((-profit) / 30000 * 25)
    )
    risk = _clamp(100 - risk_pressure)

    custom = success_definition or {}
    priority = custom.get("priority", "balanced")
    weights = {"market": 1.0, "resource": 1.0, "profitability": 1.0, "risk": 1.0}
    if priority == "survival":
        weights = {"market": 0.5, "resource": 2.0, "profitability": 0.5, "risk": 1.0}
    elif priority == "profit":
        weights = {"market": 0.75, "resource": 0.75, "profitability": 2.0, "risk": 0.75}
    elif priority == "growth":
        weights = {"market": 2.0, "resource": 0.75, "profitability": 0.5, "risk": 0.5}

    detail = {
        "market": round(market * weights["market"], 2),
        "resource": round(resource * weights["resource"], 2),
        "profitability": round(profitability * weights["profitability"], 2),
        "risk": round(risk * weights["risk"], 2),
    }
    bonus = {
        "goal_reached": 8,
        "steady": 4,
        "bankrupt": -20,
        "timeout": 0,
        "user_ended": 0,
        "paused": -5,
    }.get(result, 0)
    total = _clamp(sum(detail.values()) / len(detail) + bonus)
    return Score(total=round(total, 2), detail=detail)


_ACTION_TEMPLATES: dict[str, tuple[str, str, str]] = {
    "cash_flow": (
        "建立现金储备缓冲",
        "储备 50,000 运营资金",
        "14 天内",
    ),
    "competition_count": (
        "开展差异化竞争测试",
        "面向 30 名客户测试 2 种差异化方案",
        "21 天内",
    ),
    "customer_flow": (
        "恢复客户获取渠道",
        "触达 100 名潜在客户",
        "14 天内",
    ),
    "monthly_profit": (
        "恢复正向月度利润",
        "削减 10,000 月度运营成本",
        "30 天内",
    ),
    "payback_ratio": (
        "提升回本效率",
        "将回本率提升 10 个百分点",
        "45 天内",
    ),
    "study_budget": ("补齐备考资金安排", "列出未来 3 个月学习与生活支出", "7 天内"),
    "study_time": ("重排每周备考计划", "保证每周至少 30 小时有效学习", "7 天内"),
    "admission_competition": ("校准目标院校策略", "完成目标院校近 3 年分数与招生数据复盘", "10 天内"),
    "learning_progress": ("建立阶段性测评", "完成 2 次全真模拟并复盘薄弱科目", "14 天内"),
    "admission_readiness": ("推进录取准备", "完成下一阶段复习清单与验收标准", "7 天内"),
    "application_readiness": ("推进申请主线", "完成选校、文书或标化中的下一项关键材料", "14 天内"),
    "application_materials": ("补齐申请材料", "核对成绩、推荐信、文书与语言材料的完成状态", "10 天内"),
    "visa_policy": ("建立签证与政策清单", "确认签证材料、预约节点和备选时间表", "14 天内"),
    "language_preparation": ("补足语言与适应准备", "制定语言提升或行前适应训练计划", "21 天内"),
    "monthly_study_gap": ("压缩留学支出缺口", "核对月度支出并制定奖学金或兼职方案", "14 天内"),
    "career_reserve": ("保留职业转换缓冲", "预留 3 个月基本生活支出", "30 天内"),
    "work_visibility": ("提升工作成果可见度", "沉淀 2 个可量化项目成果并与关键决策者同步", "21 天内"),
    "promotion_competition": ("核对晋升标准与竞争格局", "完成目标职级能力差距清单", "14 天内"),
    "salary_growth": ("验证岗位回报", "与直属负责人确认薪酬与职级的下一次评估节点", "30 天内"),
    "promotion_readiness": ("推进晋升准备", "完成一份目标岗位述职或晋升材料初稿", "21 天内"),
    "job_search_reserve": ("控制求职期现金消耗", "制定未来 2 个月求职预算", "7 天内"),
    "interview_pipeline": ("扩大有效面试机会", "完成 20 个定向投递并争取 3 次内推沟通", "14 天内"),
    "job_market_competition": ("调整求职定位", "针对目标岗位补齐 1 项高频技能或作品案例", "21 天内"),
    "salary_match": ("校准薪酬预期", "收集 5 个同类岗位薪酬样本并确定底线", "10 天内"),
    "offer_readiness": ("推进录用准备", "完善简历、作品集与面试问答清单", "7 天内"),
    "down_payment_reserve": ("保留首付后的现金缓冲", "测算购房后至少 6 个月家庭应急金", "14 天内"),
    "home_selection": ("扩大可选房源范围", "对比至少 3 个符合通勤与预算的区域", "21 天内"),
    "market_heat": ("持续核查房价与政策", "跟踪目标区域挂牌价、成交价与资格政策", "14 天内"),
    "mortgage_pressure": ("做月供压力测试", "按利率上浮和收入下降两种情景重算月供", "7 天内"),
    "purchase_readiness": ("补齐购房决策条件", "确认购房资格、贷款预审和交易税费", "14 天内"),
    "liquidity_reserve": ("保留投资外的流动资金", "预留至少 6 个月生活应急金", "7 天内"),
    "portfolio_diversification": ("检查资产分散度", "盘点单一资产或行业的集中比例", "7 天内"),
    "market_volatility": ("设定波动应对规则", "明确加仓、减仓和观望的触发条件", "14 天内"),
    "drawdown_control": ("落实回撤控制", "为每笔投资设定最大亏损和止损执行规则", "7 天内"),
    "return_progress": ("复核收益目标", "按年度目标检查收益、风险与持有期限是否匹配", "30 天内"),
}


def _risk(metric: str, severity: float, value: float, message: str) -> RiskItem:
    return RiskItem(
        metric=metric,
        severity=round(_clamp(severity, 0, 1), 2),
        current_value=value,
        message=message,
    )


def _business_risks(
    world_state: Mapping[str, float], decision_vars: Mapping[str, Any]
) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    competition = _value(world_state, "competition_count")
    customers = _value(world_state, "customer_flow")
    profit = _value(world_state, "monthly_profit")
    payback = _value(world_state, "payback_ratio")
    budget = float(decision_vars.get("budget", 0) or 0)
    cash_line = max(50000, budget * 0.15)
    industry = str(decision_vars.get("industry") or "当前业务")
    return [
        _risk(
            "cash_flow", (cash_line - cash) / cash_line, cash,
            f"{industry}可用现金低于 {cash_line:,.0f} 元安全线，需防范后续投入挤压日常运营。",
        ),
        _risk(
            "competition_count", (competition - 40) / 60, competition,
            "同类竞争压力偏高，先验证差异化卖点和稳定获客渠道，再扩大投入。",
        ),
        _risk(
            "customer_flow", (100 - customers) / 100, customers,
            "当前客户获取不足，需优先确认目标客群、渠道成本和复购路径。",
        ),
        _risk(
            "monthly_profit", -profit / 30000, profit,
            "经营尚未形成稳定正向利润，应明确减亏节点和验证周期。",
        ),
        _risk(
            "payback_ratio", (0.8 - payback) / 0.8, payback,
            "投入的回收进度仍需验证，避免在商业模型未跑通前增加不可逆成本。",
        ),
    ]


def _education_risks(
    world_state: Mapping[str, float], decision_vars: Mapping[str, Any]
) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    study_time = _value(world_state, "customer_flow")
    competition = _value(world_state, "competition_count")
    progress = _value(world_state, "monthly_profit")
    readiness = _value(world_state, "payback_ratio")
    budget = float(decision_vars.get("budget", 0) or 0)
    school = str(decision_vars.get("target_school") or "目标院校")
    months = int(decision_vars.get("prep_months", 0) or 0)
    return [
        _risk("study_budget", (10000 - cash) / 10000, cash, f"备考资金偏紧，可能影响资料、课程和后续调整；应先为{school}的备考留出基本缓冲。"),
        _risk("study_time", (180 - study_time) / 180, study_time, f"有效学习投入未达到当前阶段要求。距考试约 {months} 个月时，更需要稳定而非临时冲刺。"),
        _risk("admission_competition", (competition - 70) / 30, competition, f"{school}的竞争压力较高，应尽快用真题和模拟成绩校准目标与复习重点。"),
        _risk("learning_progress", (60 - progress) / 60, progress, "阶段性学习成效不足，不能只增加时长，需要定位薄弱科目并完成闭环复盘。"),
        _risk("admission_readiness", (0.9 - readiness) / 0.9, readiness, "录取准备尚未进入可验证状态，建议拆分为周目标并持续检查完成质量。"),
    ]


def _abroad_risks(
    world_state: Mapping[str, float], decision_vars: Mapping[str, Any]
) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    materials = _value(world_state, "customer_flow")
    competition = _value(world_state, "competition_count")
    monthly_gap = _value(world_state, "monthly_profit")
    readiness = _value(world_state, "payback_ratio")
    budget = float(decision_vars.get("budget", 0) or 0)
    country = str(decision_vars.get("target_country") or "目标国家")
    major = str(decision_vars.get("target_major") or "目标专业")
    reserve = max(100000, budget * 0.2)
    return [
        _risk("study_budget", (reserve - cash) / reserve, cash, f"留学资金低于 {reserve:,.0f} 元缓冲线，{country}的学费、生活费和汇率波动会放大资金压力。"),
        _risk("application_materials", (8 - materials) / 8, materials, f"{major}申请材料准备仍不充分，需明确文书、推荐信、语言成绩和时间节点。"),
        _risk("admission_competition", (competition - 60) / 40, competition, "录取竞争和外部不确定性偏高，建议同时准备匹配、冲刺和保底方案。"),
        _risk("monthly_study_gap", -monthly_gap / 15000, monthly_gap, "月度资金缺口仍需控制，奖学金、分期换汇或兼职方案要有明确优先级。"),
        _risk("application_readiness", (0.8 - readiness) / 0.8, readiness, "申请完成度不足，当前不宜只依赖单一学校或单一申请路径。"),
    ]


def _career_risks(world_state: Mapping[str, float], decision_vars: Mapping[str, Any]) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    visibility = _value(world_state, "customer_flow")
    competition = _value(world_state, "competition_count")
    salary = _value(world_state, "monthly_profit")
    readiness = _value(world_state, "payback_ratio")
    target = str(decision_vars.get("target_position") or "目标职级")
    return [
        _risk("career_reserve", (90000 - cash) / 90000, cash, "职业调整缺少足够缓冲，面对岗位变化时的选择空间会被压缩。"),
        _risk("work_visibility", (12 - visibility) / 12, visibility, "关键成果的可见度不足，应让影响范围、业务结果和协作价值被看见。"),
        _risk("promotion_competition", (competition - 45) / 55, competition, f"{target}的竞争较强，需要对照组织标准补齐能力和关键项目经历。"),
        _risk("salary_growth", (30000 - salary) / 30000, salary, "当前岗位回报与目标职级仍有差距，需要核实晋升路径而非只等待机会。"),
        _risk("promotion_readiness", (0.85 - readiness) / 0.85, readiness, f"迈向{target}的准备度不足，应尽早准备可量化的晋升证据。"),
    ]


def _job_risks(world_state: Mapping[str, float], decision_vars: Mapping[str, Any]) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    interviews = _value(world_state, "customer_flow")
    competition = _value(world_state, "competition_count")
    salary = _value(world_state, "monthly_profit")
    readiness = _value(world_state, "payback_ratio")
    industry = str(decision_vars.get("target_industry") or "目标行业")
    expected_salary = float(decision_vars.get("salary_expectation", 0) or 0)
    return [
        _risk("job_search_reserve", (30000 - cash) / 30000, cash, "求职期资金缓冲不足，可能迫使你在机会尚未比较清楚时仓促接受岗位。"),
        _risk("interview_pipeline", (10 - interviews) / 10, interviews, "有效面试机会偏少，应提升定向投递、作品呈现和内推转化。"),
        _risk("job_market_competition", (competition - 60) / 40, competition, f"{industry}岗位竞争压力较大，需要让简历和案例更贴近目标岗位。"),
        _risk("salary_match", (expected_salary - salary) / max(expected_salary, 1), salary, "当前可获得回报与预期仍有差距，需明确薪酬底线和可交换条件。"),
        _risk("offer_readiness", (0.8 - readiness) / 0.8, readiness, "录用准备度不足，建议集中完善简历、作品集与高频面试问题。"),
    ]


def _house_risks(world_state: Mapping[str, float], decision_vars: Mapping[str, Any]) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    options = _value(world_state, "customer_flow")
    heat = _value(world_state, "competition_count")
    monthly_buffer = _value(world_state, "monthly_profit")
    readiness = _value(world_state, "payback_ratio")
    income = float(decision_vars.get("income", 0) or 0)
    city = str(decision_vars.get("city") or "目标城市")
    return [
        _risk("down_payment_reserve", (200000 - cash) / 200000, cash, "首付后的现金缓冲偏薄，应避免把家庭流动资金全部用于购房。"),
        _risk("home_selection", (5 - options) / 5, options, "可比较的房源和区域不足，过早锁定单一选择容易牺牲通勤、总价或流动性。"),
        _risk("market_heat", (heat - 55) / 45, heat, f"{city}市场热度与政策变化需要持续跟踪，避免只依据短期价格波动做决定。"),
        _risk("mortgage_pressure", (income * 0.4 - monthly_buffer) / max(income * 0.4, 1), monthly_buffer, "月供与家庭收入的匹配度不足，需先完成利率上浮和收入下降情景下的压力测试。"),
        _risk("purchase_readiness", (0.9 - readiness) / 0.9, readiness, "购房资格、贷款预审和交易成本尚未全部确认，不宜直接进入签约环节。"),
    ]


def _investment_risks(world_state: Mapping[str, float], decision_vars: Mapping[str, Any]) -> list[RiskItem]:
    cash = _value(world_state, "cash_flow")
    diversification = _value(world_state, "customer_flow")
    volatility = _value(world_state, "competition_count")
    pnl = _value(world_state, "monthly_profit")
    progress = _value(world_state, "payback_ratio")
    amount = float(decision_vars.get("investment_amount", 0) or 0)
    risk_level = str(decision_vars.get("risk_level") or "balanced")
    reserve = max(amount * 0.3, 30000)
    extra_risk = 0.15 if risk_level == "aggressive" else 0
    return [
        _risk("liquidity_reserve", (reserve - cash) / reserve, cash, "投资外的流动资金不足，遇到生活支出或市场剧烈波动时容易被动卖出。"),
        _risk("portfolio_diversification", (8 - diversification) / 8, diversification, "资产分散度不足，应先确认单一行业、单一资产和单笔仓位的上限。"),
        _risk("market_volatility", (volatility - 45) / 55 + extra_risk, volatility, "当前市场波动和不确定性较高，进场节奏应与风险承受能力匹配。"),
        _risk("drawdown_control", -pnl / 5000 + extra_risk, pnl, "回撤控制规则不够明确，不能只依据短期涨跌追加或撤出资金。"),
        _risk("return_progress", (0.8 - progress) / 0.8, progress, "收益目标尚未验证，应定期检查实际收益是否覆盖承担的风险和时间成本。"),
    ]


def extract_risks(
    world_state: Mapping[str, float],
    scenario_id: str = "general_startup",
    decision_vars: Mapping[str, Any] | None = None,
    user_profile: Mapping[str, Any] | None = None,
) -> list[RiskItem]:
    """Return scenario-specific, user-readable risks from the shared simulation state."""
    del user_profile  # Reserved for future profile-weighted thresholds.
    decision_vars = decision_vars or {}
    if scenario_id == "grad_exam":
        return _education_risks(world_state, decision_vars)
    if scenario_id == "study_abroad":
        return _abroad_risks(world_state, decision_vars)
    if scenario_id == "career_advance":
        return _career_risks(world_state, decision_vars)
    if scenario_id == "job_hunting":
        return _job_risks(world_state, decision_vars)
    if scenario_id == "house_purchase":
        return _house_risks(world_state, decision_vars)
    if scenario_id == "investment":
        return _investment_risks(world_state, decision_vars)
    return _business_risks(world_state, decision_vars)


def build_action_plan(
    risks: list[RiskItem], scenario_id: str = "general_startup"
) -> list[ActionPlanItem]:
    del scenario_id
    return [
        ActionPlanItem(
            metric=risk.metric,
            action=_ACTION_TEMPLATES[risk.metric][0],
            quantity=_ACTION_TEMPLATES[risk.metric][1],
            deadline=_ACTION_TEMPLATES[risk.metric][2],
        )
        for risk in risks
    ]
