from typing import Any

from app.engine.models import SimulationState, WorldState
from app.schemas.decision_source import DecisionSource, StateMetricModifier
from app.services.scenario_presenter import DECISION_VAR_LABELS


def _field_label(name: str) -> str:
    return DECISION_VAR_LABELS.get(name, name)


def _format_bound(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _validate_decision_vars(
    source: DecisionSource,
    supplied: dict[str, Any],
) -> dict[str, Any]:
    definitions = {item.name: item for item in source.decision_vars}
    unknown = set(supplied) - set(definitions)
    if unknown:
        raise ValueError(f"存在未定义的推演参数：{', '.join(sorted(unknown))}")

    values: dict[str, Any] = {}
    for name, definition in definitions.items():
        if name in supplied:
            value = supplied[name]
        elif definition.default is not None:
            value = definition.default
        elif definition.required:
            raise ValueError(f"缺少必填参数：{_field_label(name)}")
        else:
            continue

        if definition.value_type == "integer" and (
            isinstance(value, bool) or not isinstance(value, int)
        ):
            raise ValueError(f"{_field_label(name)}必须是整数")
        if definition.value_type == "number" and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise ValueError(f"{_field_label(name)}必须是数字")
        if definition.value_type == "string" and not isinstance(value, str):
            raise ValueError(f"{_field_label(name)}必须是文本")
        if definition.minimum is not None and value < definition.minimum:
            raise ValueError(
                f"{_field_label(name)}不能低于 {_format_bound(definition.minimum)}"
            )
        if definition.maximum is not None and value > definition.maximum:
            raise ValueError(
                f"{_field_label(name)}不能高于 {_format_bound(definition.maximum)}"
            )
        values[name] = value
    return values


def make_initial_state(
    source: DecisionSource,
    decision_vars: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
    success_definition: dict[str, Any] | None = None,
    session_id: str = "",
) -> SimulationState:
    values = _validate_decision_vars(source, decision_vars)
    initial_world = dict(source.initial_world_state)
    initial_world["metrics"] = {
        definition.metric_id: float(definition.initial_value)
        for definition in source.state_metrics
    }
    if "budget" in values:
        initial_world["cash_flow"] = float(values["budget"])

    world_state = WorldState.model_validate(initial_world)
    _apply_state_modifiers(
        world_state,
        source.decision_var_state_modifiers,
        values,
    )
    _apply_state_modifiers(
        world_state,
        source.profile_state_modifiers,
        user_profile or {},
    )
    _calibrate_initial_world_state(source.scenario_id, world_state, values, user_profile or {})

    return SimulationState(
        session_id=session_id,
        scenario_id=source.scenario_id,
        decision_vars=values,
        user_profile=dict(user_profile or {}),
        success_definition=dict(success_definition or {}),
        world_state=world_state,
    )


def _calibrate_initial_world_state(
    scenario_id: str,
    world_state: WorldState,
    decision_vars: dict[str, Any],
    user_profile: dict[str, Any],
) -> None:
    """Map confirmed numeric inputs to the scenario's opening conditions."""
    if scenario_id == "grad_exam":
        months = float(decision_vars.get("prep_months", 0) or 0)
        world_state.customer_flow = months * 20
        world_state.monthly_profit = months * 10
        world_state.payback_ratio = 0
    elif scenario_id == "study_abroad":
        budget = float(decision_vars.get("budget", 0) or 0)
        world_state.customer_flow = 0
        world_state.monthly_profit = -budget * 0.03
        world_state.payback_ratio = 0
    elif scenario_id == "career_advance":
        years = float(decision_vars.get("years_experience", 0) or 0)
        world_state.customer_flow = years * 2
        world_state.monthly_profit = years * 5000
    elif scenario_id == "job_hunting":
        world_state.customer_flow = 0
        world_state.monthly_profit = 0
    elif scenario_id == "house_purchase":
        income = float(decision_vars.get("income", 0) or 0)
        world_state.monthly_profit = income * 0.4
    elif scenario_id == "investment":
        amount = float(decision_vars.get("investment_amount", 0) or 0)
        if amount > 0:
            world_state.cash_flow = amount
        risk_level = str(decision_vars.get("risk_level") or "balanced")
        world_state.competition_count = {
            "conservative": 30,
            "balanced": 50,
            "aggressive": 70,
        }.get(risk_level, 50)

    if (
        "budget" not in decision_vars
        and "investment_amount" not in decision_vars
        and isinstance(user_profile.get("assets"), (int, float))
    ):
        world_state.cash_flow = float(user_profile["assets"])


def _apply_state_modifiers(
    world_state: WorldState,
    modifiers: list[StateMetricModifier],
    values: dict[str, Any],
) -> None:
    from app.engine.reducers import add_world_metric

    for modifier in modifiers:
        value = values.get(modifier.input_key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        add_world_metric(
            world_state,
            modifier.metric,
            float(value) * modifier.multiplier + modifier.offset,
        )
