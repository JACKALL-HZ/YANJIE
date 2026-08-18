from app.engine.ending import judge_ending
from app.engine.models import (
    AgentAction,
    EndingResult,
    SimulationState,
    TransitionResult,
)
from app.engine.reducers import append_timeline, apply_actions
from app.schemas.decision_source import DecisionSource


def prepare_state(state: SimulationState) -> SimulationState:
    next_state = state.model_copy(deep=True)
    next_state.phase = "simulating"
    next_state.pause_reason = None
    next_state.pending_intervention = None
    return next_state


def apply_supplied_actions(
    state: SimulationState,
    actions: list[AgentAction],
    source: DecisionSource,
) -> TransitionResult:
    return apply_actions(state.world_state, actions, source)


def check_ending(
    transition: TransitionResult,
    year: int,
    source: DecisionSource,
    success_definition: dict | None = None,
) -> EndingResult | None:
    return judge_ending(
        transition.world_state,
        year,
        source.end_conditions,
        success_definition=success_definition,
    )


def append_year(
    state: SimulationState,
    year: int,
    actions: list[AgentAction],
    transition: TransitionResult,
    ending: EndingResult | None,
) -> SimulationState:
    return append_timeline(state, year, actions, transition, ending=ending)
