"""用户画像 → Agent 上下文的转换层（纯函数，不调 LLM、不碰 DB）。

两个职责：
1. `compute_derived`：由原始字段推导二级指标（净资产/现金跑道/月结余/可承受亏损）。
2. `build_profile_summary`：把画像 + 本次决策变量渲染成 Agent 可读的中文摘要，
   其中「投入压力」段落把画像资产与决策预算挂钩，让 Agent 感知
   「这一把压上了多少身家」而不只是一个孤立数字。
"""

from typing import Any

# 决策变量中代表"本次投入金额"的候选键（按优先级）
_BUDGET_KEYS: tuple[str, ...] = (
    "budget",
    "investment_amount",
    "initial_investment",
    "capital",
    "startup_cost",
)

_EDUCATION_LABELS = {
    "high_school": "高中",
    "college": "大专",
    "bachelor": "本科",
    "master": "硕士",
    "phd": "博士",
    "other": "其他学历",
}
_MARITAL_LABELS = {
    "single": "未婚",
    "married": "已婚",
    "divorced": "离异",
    "widowed": "丧偶",
}
_RISK_LABELS = {
    "conservative": "保守型",
    "balanced": "平衡型",
    "aggressive": "激进型",
}
_STABILITY_LABELS = {
    "stable": "收入稳定",
    "fluctuating": "收入有波动",
    "unstable": "收入不稳定",
}
_DECISION_STYLE_LABELS = {
    "analytical": "分析型（重数据）",
    "intuitive": "直觉型（重感觉）",
    "decisive": "果断型（快决策）",
    "consensus": "共识型（重商量）",
}
_TIME_LABELS = {
    "fulltime": "全职投入",
    "parttime": "兼职投入",
    "spare": "业余时间投入",
    "weekend": "仅周末投入",
}

# 计入完成度的字段（不含 id/user_id/时间戳/派生指标）
COMPLETENESS_FIELDS: tuple[str, ...] = (
    "age", "gender", "city", "education", "marital_status", "dependents",
    "occupation", "industry", "years_experience", "skills", "certificates",
    "career_history", "strengths", "weaknesses",
    "assets", "monthly_income", "monthly_expense", "liabilities",
    "income_stability", "insurance",
    "risk_appetite", "loss_tolerance", "decision_style", "past_failures",
    "available_time", "weekly_hours", "support_network",
    "goals", "constraints", "time_horizon", "motivation",
)


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def compute_derived(profile: dict[str, Any]) -> dict[str, Any]:
    """由原始字段推导二级指标。数据不足的指标直接不输出，避免用 0 冒充未填写。"""
    derived: dict[str, Any] = {}
    assets = profile.get("assets")
    liabilities = profile.get("liabilities")
    income = profile.get("monthly_income")
    expense = profile.get("monthly_expense")
    loss_tolerance = profile.get("loss_tolerance")

    if assets is not None:
        derived["net_worth"] = assets - (liabilities or 0)
        if liabilities and assets:
            derived["debt_ratio"] = round(liabilities / assets, 3)
        if loss_tolerance is not None:
            derived["max_affordable_loss"] = int(assets * loss_tolerance / 100)
        if expense:
            derived["runway_months"] = round(assets / expense, 1)

    if income is not None and expense is not None:
        derived["monthly_surplus"] = income - expense

    filled = sum(1 for f in COMPLETENESS_FIELDS if _is_filled(profile.get(f)))
    derived["completeness"] = round(filled / len(COMPLETENESS_FIELDS), 2)
    derived["filled_fields"] = filled
    derived["total_fields"] = len(COMPLETENESS_FIELDS)
    return derived


def extract_budget(decision_vars: dict[str, Any] | None) -> float | None:
    """从决策变量中取出本次投入金额（找不到返回 None）。"""
    if not decision_vars:
        return None
    for key in _BUDGET_KEYS:
        value = decision_vars.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _money(value: float | int) -> str:
    """金额人性化：>= 1 万显示万元，否则显示元。"""
    v = float(value)
    if abs(v) >= 10000:
        text = f"{v / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{text} 万元"
    return f"{int(v)} 元"


def _clip(text: Any, limit: int) -> str:
    s = str(text or "").strip().replace("\n", " ")
    return s if len(s) <= limit else s[:limit] + "…"


def _label(mapping: dict[str, str], value: Any) -> str:
    return mapping.get(str(value), str(value))


def build_profile_summary(
    profile: dict[str, Any] | None,
    decision_vars: dict[str, Any] | None = None,
) -> str:
    """把画像渲染为 Agent 上下文摘要。空画像返回空串（推演照常进行）。"""
    if not profile:
        return ""

    derived = profile.get("derived") or compute_derived(profile)
    lines: list[str] = []

    # ── 1. 基本信息 ──
    basics: list[str] = []
    if profile.get("age") is not None:
        basics.append(f"{profile['age']} 岁")
    if profile.get("gender"):
        basics.append(str(profile["gender"]))
    if profile.get("city"):
        basics.append(f"现居{profile['city']}")
    if profile.get("education"):
        basics.append(_label(_EDUCATION_LABELS, profile["education"]))
    if profile.get("marital_status"):
        basics.append(_label(_MARITAL_LABELS, profile["marital_status"]))
    dependents = profile.get("dependents")
    if dependents:
        basics.append(f"需抚养 {dependents} 人")
    elif profile.get("family_burden"):
        basics.append("有家庭负担")
    if basics:
        lines.append("· 基本：" + " · ".join(basics))

    # ── 2. 职业与能力 ──
    career: list[str] = []
    if profile.get("occupation"):
        occ = str(profile["occupation"])
        if profile.get("industry"):
            occ += f"（{profile['industry']}行业）"
        career.append(occ)
    elif profile.get("industry"):
        career.append(f"{profile['industry']}行业")
    if profile.get("years_experience") is not None:
        career.append(f"{profile['years_experience']} 年从业经验")
    skills = profile.get("skills") or []
    if skills:
        career.append("技能：" + "、".join(map(str, skills[:12])))
    certificates = profile.get("certificates") or []
    if certificates:
        career.append("资质：" + "、".join(map(str, certificates[:8])))
    if career:
        lines.append("· 职业：" + "；".join(career))

    # ── 3. 财务状况（Agent 风险判断的主要依据）──
    finance: list[str] = []
    if profile.get("assets") is not None:
        finance.append(f"可支配资产 {_money(profile['assets'])}")
    if profile.get("liabilities"):
        finance.append(f"负债 {_money(profile['liabilities'])}")
    if "net_worth" in derived and profile.get("liabilities"):
        finance.append(f"净资产 {_money(derived['net_worth'])}")
    if profile.get("monthly_income") is not None:
        finance.append(f"月收入 {_money(profile['monthly_income'])}")
    if profile.get("monthly_expense") is not None:
        finance.append(f"月支出 {_money(profile['monthly_expense'])}")
    if "monthly_surplus" in derived:
        surplus = derived["monthly_surplus"]
        word = "月结余" if surplus >= 0 else "月缺口"
        finance.append(f"{word} {_money(abs(surplus))}")
    if profile.get("income_stability"):
        finance.append(_label(_STABILITY_LABELS, profile["income_stability"]))
    if "runway_months" in derived:
        finance.append(f"零收入可支撑约 {derived['runway_months']} 个月")
    insurance = profile.get("insurance") or []
    if insurance:
        finance.append("已有保障：" + "、".join(map(str, insurance[:6])))
    if finance:
        lines.append("· 财务：" + "；".join(finance))

    # ── 4. 风险与决策 ──
    risk: list[str] = []
    if profile.get("risk_appetite"):
        risk.append(f"风险偏好{_label(_RISK_LABELS, profile['risk_appetite'])}")
    if profile.get("loss_tolerance") is not None:
        text = f"最多可承受亏损 {profile['loss_tolerance']}%"
        if "max_affordable_loss" in derived:
            text += f"（约 {_money(derived['max_affordable_loss'])}）"
        risk.append(text)
    if profile.get("decision_style"):
        risk.append(
            f"决策风格{_label(_DECISION_STYLE_LABELS, profile['decision_style'])}"
        )
    if risk:
        lines.append("· 风险：" + "；".join(risk))

    # ── 5. 时间与资源 ──
    resources: list[str] = []
    if profile.get("available_time"):
        resources.append(_label(_TIME_LABELS, profile["available_time"]))
    if profile.get("weekly_hours") is not None:
        resources.append(f"每周可投入约 {profile['weekly_hours']} 小时")
    if profile.get("support_network"):
        resources.append(f"可动用资源：{_clip(profile['support_network'], 120)}")
    if resources:
        lines.append("· 时间与资源：" + "；".join(resources))

    # ── 6. 目标与约束 ──
    goals = profile.get("goals") or []
    goal_parts: list[str] = []
    if goals:
        goal_parts.append("核心目标：" + "、".join(map(str, goals[:8])))
    if profile.get("time_horizon") is not None:
        goal_parts.append(f"时间视野 {profile['time_horizon']} 年")
    if profile.get("motivation"):
        goal_parts.append(f"动机：{_clip(profile['motivation'], 120)}")
    if goal_parts:
        lines.append("· 目标：" + "；".join(goal_parts))
    if profile.get("constraints"):
        lines.append(f"· 硬性约束（不可妥协）：{_clip(profile['constraints'], 200)}")

    # ── 7. 自陈优劣势与历史 ──
    if profile.get("strengths"):
        lines.append(f"· 自陈优势：{_clip(profile['strengths'], 150)}")
    if profile.get("weaknesses"):
        lines.append(f"· 已知短板：{_clip(profile['weaknesses'], 150)}")
    if profile.get("past_failures"):
        lines.append(f"· 过往失败经历：{_clip(profile['past_failures'], 200)}")
    if profile.get("career_history"):
        lines.append(f"· 职业经历：{_clip(profile['career_history'], 200)}")

    if not lines:
        return ""

    pressure = _build_pressure_line(profile, derived, decision_vars)
    if pressure:
        lines.append(pressure)

    return "\n".join(lines)


def _build_pressure_line(
    profile: dict[str, Any],
    derived: dict[str, Any],
    decision_vars: dict[str, Any] | None,
) -> str:
    """把本次投入与用户身家挂钩 —— 让 Agent 感知这一把压上了多少。"""
    budget = extract_budget(decision_vars)
    assets = profile.get("assets")
    if budget is None or not assets:
        return ""

    ratio = budget / assets
    parts = [
        f"本次决策投入 {_money(budget)}，占其可支配资产的 {ratio * 100:.1f}%"
    ]

    net_worth = derived.get("net_worth")
    if net_worth and net_worth != assets and net_worth > 0:
        parts.append(f"占净资产的 {budget / net_worth * 100:.1f}%")

    max_loss = derived.get("max_affordable_loss")
    if max_loss is not None and budget > max_loss:
        parts.append(
            f"已超出其自述的最大可承受亏损（{_money(max_loss)}），"
            f"属于超额风险敞口，决策与措辞需体现这一压力"
        )
    elif ratio >= 0.5:
        parts.append("超过半数身家押注，属于高压决策")
    elif ratio <= 0.1:
        parts.append("投入占比较低，试错成本可控")

    runway = derived.get("runway_months")
    if runway is not None:
        expense = profile.get("monthly_expense") or 0
        if expense:
            remaining = (assets - budget) / expense
            parts.append(
                f"投入后剩余现金仅能支撑约 {max(remaining, 0):.1f} 个月生活开支"
            )

    return "· 投入压力：" + "；".join(parts) + "。"
