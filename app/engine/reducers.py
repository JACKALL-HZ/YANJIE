from collections.abc import Mapping

from app.engine.models import (
    AgentAction,
    EventRecord,
    SimulationState,
    StateEffect,
    TimelineNode,
    TransitionResult,
    WorldState,
)
from app.schemas.decision_source import ActionEffectDef, DecisionSource


_LEGACY_METRICS = frozenset(WorldState.model_fields) - {"metrics"}


def read_world_metric(world_state: WorldState, metric: str) -> float:
    if metric in _LEGACY_METRICS:
        return float(getattr(world_state, metric))
    if metric in world_state.metrics:
        return float(world_state.metrics[metric])
    raise ValueError(f"unknown world-state metric: {metric}")


def add_world_metric(world_state: WorldState, metric: str, delta: float) -> None:
    if metric in _LEGACY_METRICS:
        setattr(world_state, metric, read_world_metric(world_state, metric) + delta)
        return
    if metric in world_state.metrics:
        world_state.metrics[metric] = read_world_metric(world_state, metric) + delta
        return
    raise ValueError(f"unknown world-state metric: {metric}")


def apply_effect_definitions(
    world_state: WorldState | Mapping[str, float],
    definitions: list[ActionEffectDef],
) -> TransitionResult:
    next_state = WorldState.model_validate(world_state).model_copy(deep=True)
    effects: list[StateEffect] = []
    for definition in definitions:
        for metric, delta in definition.effects.items():
            add_world_metric(next_state, metric, delta)
        effects.append(
            StateEffect(action_id=definition.action_id, effects=dict(definition.effects))
        )

    return TransitionResult(
        world_state=WorldState.model_validate(next_state),
        effects=effects,
        events=[],
    )


def apply_actions(
    world_state: WorldState | Mapping[str, float],
    actions: list[AgentAction],
    source: DecisionSource,
) -> TransitionResult:
    effect_by_action = {item.action_id: item for item in source.action_effects}
    declared_by_agent = {
        agent.agent_id: set(agent.action_ids) for agent in source.agents
    }
    definitions: list[ActionEffectDef] = []
    events: list[EventRecord] = []

    for action in actions:
        if action.action_id not in declared_by_agent[action.agent_id]:
            raise ValueError(
                f"action {action.action_id} is not declared for agent {action.agent_id}"
            )
        definition = effect_by_action.get(action.action_id)
        if definition is None:
            raise ValueError(f"action effect is not declared: {action.action_id}")
        definitions.append(definition)
        events.append(
            EventRecord(
                agent_id=action.agent_id,
                action_id=action.action_id,
                reason=action.reason,
                state_diff=dict(definition.effects),
            )
        )

    transition = apply_effect_definitions(world_state, definitions)
    return TransitionResult(
        world_state=transition.world_state,
        effects=transition.effects,
        events=events,
    )


def append_timeline(
    state: SimulationState,
    year: int,
    actions: list[AgentAction],
    transition: TransitionResult,
    ending=None,
    interventions=None,
) -> SimulationState:
    next_state = state.model_copy(deep=True)
    next_state.year = year
    next_state.phase = "completed" if ending is not None else "simulating"
    next_state.world_state = transition.world_state
    next_state.agent_actions = [item.model_copy(deep=True) for item in actions]
    applied_interventions = list(interventions or [])
    next_state.interventions.extend(applied_interventions)
    state_diff: dict[str, float] = {}
    for effect in transition.effects:
        for metric, delta in effect.effects.items():
            state_diff[metric] = state_diff.get(metric, 0) + delta
    next_state.timeline.append(
        TimelineNode(
            year=year,
            world_state=transition.world_state,
            agent_actions=list(actions),
            state_diff=state_diff,
            interventions=applied_interventions,
            ending=ending,
        )
    )
    if ending is not None:
        next_state.result = ending.result
    return next_state
