from collections.abc import Mapping
from typing import Any


_METRICS = (
    ("cash_flow", "现金储备", "currency", True),
    ("monthly_profit", "月利润", "currency", True),
    ("customer_flow", "每日客流", "count", True),
    ("competition_count", "周边竞争门店", "stores", False),
    ("payback_ratio", "回本进度", "percent", True),
)


def _get(state: Mapping[str, float], metric: str) -> float:
    return float(state.get(metric, 0))


def _risk_index(state: Mapping[str, float]) -> float:
    return (
        max(0, 50000 - _get(state, "cash_flow")) / 50000
        + max(0, _get(state, "competition_count") - 40) / 60
        + max(0, -_get(state, "monthly_profit")) / 30000
    )


def _format_metric(value: float, display_type: str) -> str:
    if display_type == "currency":
        return f"{value:,.0f} 元"
    if display_type == "count":
        return f"{value:,.0f} 人/日"
    if display_type == "stores":
        return f"{value:,.0f} 家"
    return f"{value * 100:.0f}%"


def _better_plan(a: float, b: float, higher_is_better: bool) -> str:
    if a == b:
        return "tie"
    if (a > b) == higher_is_better:
        return "A"
    return "B"


def _choose_winner(
    state_a: Mapping[str, float],
    state_b: Mapping[str, float],
    score_a: float | None,
    score_b: float | None,
) -> str:
    if score_a is not None and score_b is not None and score_a != score_b:
        return "A" if score_a > score_b else "B"

    for metric, _, _, higher_is_better in (
        _METRICS[1], _METRICS[0], ("risk_index", "风险", "", False),
    ):
        a = _risk_index(state_a) if metric == "risk_index" else _get(state_a, metric)
        b = _risk_index(state_b) if metric == "risk_index" else _get(state_b, metric)
        winner = _better_plan(a, b, higher_is_better)
        if winner != "tie":
            return winner
    return "tie"


def _recommendation(
    winner: str,
    state_a: Mapping[str, float],
    state_b: Mapping[str, float],
    score_a: float | None,
    score_b: float | None,
) -> dict[str, str]:
    if winner == "tie":
        return {
            "winner": "tie",
            "title": "两套方案当前表现接近",
            "reason": "综合评分、盈利和现金储备没有形成明显差距，建议用更小的试点继续验证。",
        }
    if score_a is not None and score_b is not None and score_a != score_b:
        return {
            "winner": winner,
            "title": f"建议优先选择方案 {winner}",
            "reason": f"方案 {winner} 的综合评分更高（{max(score_a, score_b):.1f} 分），整体经营表现更占优。",
        }
    metric = "月利润" if _get(state_a, "monthly_profit") != _get(state_b, "monthly_profit") else "现金储备"
    return {
        "winner": winner,
        "title": f"建议优先选择方案 {winner}",
        "reason": f"在评分接近或暂未评分时，方案 {winner} 的{metric}表现更好。",
    }


def _plan_risks(state: Mapping[str, float], plan: str) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if _get(state, "cash_flow") < 60000:
        risks.append({"plan": plan, "level": "高", "message": "现金储备偏低，后续投入需要设置明确上限。"})
    if _get(state, "monthly_profit") <= 0:
        risks.append({"plan": plan, "level": "高", "message": "月利润尚未转正，先验证收入模型再扩大投入。"})
    if _get(state, "competition_count") > 50:
        risks.append({"plan": plan, "level": "中", "message": "周边竞争门店较多，需要避免同质化价格竞争。"})
    if _get(state, "customer_flow") < 150:
        risks.append({"plan": plan, "level": "中", "message": "每日客流仍偏低，应优先验证稳定获客渠道。"})
    if _get(state, "payback_ratio") < 0.3:
        risks.append({"plan": plan, "level": "中", "message": "回本进度较慢，追加预算前需要先验证投入回报。"})
    return risks or [{"plan": plan, "level": "低", "message": "当前没有突出风险，仍需按月追踪经营数据。"}]


def _build_summary(
    state_a: Mapping[str, float],
    state_b: Mapping[str, float],
    score_a: float | None,
    score_b: float | None,
) -> dict[str, Any]:
    metrics = []
    for metric, label, display_type, higher_is_better in _METRICS:
        a = _get(state_a, metric)
        b = _get(state_b, metric)
        delta = a - b
        metrics.append(
            {
                "label": label,
                "a": _format_metric(a, display_type),
                "b": _format_metric(b, display_type),
                "delta": f"{delta:+,.0f}" if display_type != "percent" else f"{delta * 100:+.0f}%",
                "better": _better_plan(a, b, higher_is_better),
            }
        )
    winner = _choose_winner(state_a, state_b, score_a, score_b)
    return {
        "recommendation": _recommendation(winner, state_a, state_b, score_a, score_b),
        "metrics": metrics,
        "risks": _plan_risks(state_a, "A") + _plan_risks(state_b, "B"),
    }


def compare_states(
    state_a: Mapping[str, float],
    result_a: str,
    state_b: Mapping[str, float],
    result_b: str,
    score_a: float | None = None,
    score_b: float | None = None,
) -> dict[str, Any]:
    return {
        "assets": {
            "a": _get(state_a, "cash_flow"),
            "b": _get(state_b, "cash_flow"),
            "delta": _get(state_a, "cash_flow") - _get(state_b, "cash_flow"),
        },
        "risk": {
            "a": round(_risk_index(state_a), 4),
            "b": round(_risk_index(state_b), 4),
            "delta": round(_risk_index(state_a) - _risk_index(state_b), 4),
        },
        "growth": {
            "a": _get(state_a, "monthly_profit"),
            "b": _get(state_b, "monthly_profit"),
            "delta": _get(state_a, "monthly_profit") - _get(state_b, "monthly_profit"),
        },
        "pressure": {
            "a": _get(state_a, "competition_count") - _get(state_a, "customer_flow"),
            "b": _get(state_b, "competition_count") - _get(state_b, "customer_flow"),
        },
        "ending": {"a": result_a, "b": result_b},
        "summary": _build_summary(state_a, state_b, score_a, score_b),
    }
