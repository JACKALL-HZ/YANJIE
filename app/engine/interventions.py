from collections.abc import Mapping

from app.engine.models import PendingIntervention, TransitionResult, WorldState
from app.engine.reducers import apply_effect_definitions, read_world_metric
from app.schemas.decision_source import DecisionSource, InterventionRule


def _matches(actual: float, rule: InterventionRule) -> bool:
    if rule.operator == "<":
        return actual < rule.threshold
    if rule.operator == "<=":
        return actual <= rule.threshold
    if rule.operator == ">":
        return actual > rule.threshold
    if rule.operator == ">=":
        return actual >= rule.threshold
    if rule.operator == "==":
        return actual == rule.threshold
    raise ValueError(f"unsupported operator: {rule.operator}")


def find_pending_intervention(
    world_state: WorldState | Mapping[str, float],
    year: int,
    source: DecisionSource,
    used_counts: Mapping[str, int] | None = None,
) -> PendingIntervention | None:
    normalized = WorldState.model_validate(world_state)
    counts = used_counts or {}
    for rule in source.intervention_rules:
        if counts.get(rule.rule_id, 0) >= rule.max_uses:
            continue
        actual = read_world_metric(normalized, rule.metric)
        if _matches(actual, rule):
            return PendingIntervention(
                rule_id=rule.rule_id,
                year=year,
                event=rule.event,
                options=list(rule.options),
                metric_snapshot=normalized.model_dump(),
            )
    return None


def validate_intervention_choice(
    pending: PendingIntervention,
    choice: str,
) -> str:
    if choice not in pending.options:
        raise ValueError(
            f"intervention choice {choice} is not declared for {pending.rule_id}"
        )
    return choice


def _resolve_intervention_action_id(
    pending: PendingIntervention,
    choice: str,
    source: DecisionSource,
) -> str:
    rule = next(
        (item for item in source.intervention_rules if item.rule_id == pending.rule_id),
        None,
    )
    if rule is None:
        raise ValueError(f"intervention rule is not declared: {pending.rule_id}")

    mapped_action_id = rule.option_actions.get(choice)
    if mapped_action_id:
        return mapped_action_id
    if choice.startswith("intervention."):
        return choice
    return f"intervention.{choice}"


def apply_intervention(
    world_state: WorldState | Mapping[str, float],
    pending: PendingIntervention,
    choice: str,
    source: DecisionSource,
) -> TransitionResult:
    validate_intervention_choice(pending, choice)
    action_id = _resolve_intervention_action_id(pending, choice, source)
    definition = next(
        (
            item
            for item in source.intervention_effects
            if item.action_id == action_id
        ),
        None,
    )
    if definition is None:
        raise ValueError(f"intervention effect is not declared: {action_id}")
    return apply_effect_definitions(world_state, [definition])
