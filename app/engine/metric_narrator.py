"""Chinese display names and threshold narration for fixed MVP world-state metrics."""

from decimal import Decimal


METRIC_LABELS = {
    "cash_flow": "现金储备",
    "customer_flow": "日客流",
    "competition_count": "竞争门店数",
    "monthly_profit": "月利润",
    "payback_ratio": "回本进度",
}


def metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def _format_number(value: float) -> str:
    decimal = Decimal(str(value)).normalize()
    formatted = format(decimal, "f")
    if "." in formatted:
        return formatted.rstrip("0").rstrip(".") or "0"
    return formatted


def describe_range_position(
    metric: str,
    value: float,
    lower: float,
    upper: float,
    reference_name: str = "行业稳态",
    unit: str = "杯",
) -> str:
    """Describe a metric against a range without contradictory threshold language."""
    label = metric_label(metric)
    span = upper - lower
    slight_gap = max(1.0, span * 0.1)
    if value < lower:
        gap = lower - value
        qualifier = "略低于" if gap <= slight_gap else "远低于"
        return (
            f"{label}{qualifier}{reference_name}下限 {_format_number(gap)} {unit}"
            f"（参考区间 {_format_number(lower)}-{_format_number(upper)} {unit}）"
        )
    if value > upper:
        gap = value - upper
        qualifier = "略高于" if gap <= slight_gap else "显著高于"
        return (
            f"{label}{qualifier}{reference_name}上限 {_format_number(gap)} {unit}"
            f"（参考区间 {_format_number(lower)}-{_format_number(upper)} {unit}）"
        )
    return (
        f"{label}处于{reference_name}区间"
        f"（参考区间 {_format_number(lower)}-{_format_number(upper)} {unit}）"
    )
