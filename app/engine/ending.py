from collections.abc import Mapping

from app.engine.models import EndingReason, EndingResult, WorldState
from app.engine.reducers import read_world_metric
from app.schemas.decision_source import EndConditions, MetricCondition


def _matches(actual: float, condition: MetricCondition) -> bool:
    if condition.operator == "<":
        return actual < condition.threshold
    if condition.operator == "<=":
        return actual <= condition.threshold
    if condition.operator == ">":
        return actual > condition.threshold
    if condition.operator == ">=":
        return actual >= condition.threshold
    if condition.operator == "==":
        return actual == condition.threshold
    raise ValueError(f"unsupported operator: {condition.operator}")


def _ending_for_condition(
    result: str,
    condition: MetricCondition,
    world_state: WorldState,
) -> EndingResult | None:
    actual = read_world_metric(world_state, condition.metric)
    if not _matches(actual, condition):
        return None
    return EndingResult(
        result=result,
        reason=EndingReason(
            metric=condition.metric,
            operator=condition.operator,
            threshold=condition.threshold,
            actual=actual,
        ),
    )


def judge_ending(
    world_state: WorldState | Mapping[str, float],
    year: int,
    end_conditions: EndConditions,
    success_definition: dict | None = None,
) -> EndingResult | None:
    """判定结局。若提供 success_definition，用户自定义阈值覆盖场景默认值。

    success_definition 支持的键：
    - target_monthly_profit: 月度利润目标（覆盖 steady_state.threshold）
    - target_payback_ratio: 回本率目标（覆盖 goal_reached.threshold）
    """
    normalized = WorldState.model_validate(world_state)

    bankrupt = _ending_for_condition(
        "bankrupt",
        end_conditions.bankrupt,
        normalized,
    )
    if bankrupt is not None:
        return bankrupt

    # 用户自定义成功标准：覆盖 goal_reached 和 steady_state 阈值
    custom = success_definition or {}
    if end_conditions.goal_reached is not None:
        goal_condition = end_conditions.goal_reached
        if custom.get("target_payback_ratio") is not None:
            goal_condition = goal_condition.model_copy(
                update={"threshold": float(custom["target_payback_ratio"])}
            )
        goal = _ending_for_condition("goal_reached", goal_condition, normalized)
        if goal is not None:
            return goal

    if end_conditions.steady_state is not None:
        steady_condition = end_conditions.steady_state
        if custom.get("target_monthly_profit") is not None:
            steady_condition = steady_condition.model_copy(
                update={"threshold": float(custom["target_monthly_profit"])}
            )
        steady = _ending_for_condition("steady", steady_condition, normalized)
        if steady is not None:
            return steady

    if year >= end_conditions.timeout_years:
        return EndingResult(
            result="timeout",
            reason=EndingReason(
                metric="year",
                operator=">=",
                threshold=end_conditions.timeout_years,
                actual=year,
            ),
        )
    return None
