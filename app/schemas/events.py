from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain_models import (
    AgentAction,
    DebateRecord,
    EndingResult,
    PauseReason,
    PendingIntervention,
    WorldState,
)


class EventType(str, Enum):
    SIMULATION_STARTED = "simulation.started"
    YEAR_STARTED = "year.started"           # 新年度开始，可设策略指令
    YEAR_COMPLETED = "year.completed"
    INTERVENTION_PENDING = "intervention.pending"
    SIMULATION_COMPLETED = "simulation.completed"
    SIMULATION_PAUSED = "simulation.paused"
    SIMULATION_FAILED = "simulation.failed"


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimulationStartedPayload(EventPayload):
    year: int
    world_state: WorldState
    strategy_prompt: str = ""
    available_strategies: list[str] = Field(default_factory=lambda: ["aggressive", "steady", "conservative"])
    initial_analysis: str = ""


class YearStartedPayload(EventPayload):
    """每年开始时发出，前端可展示策略选择界面。"""
    year: int
    world_state: WorldState
    strategy_prompt: str = ""
    available_strategies: list[str] = Field(default_factory=lambda: ["aggressive", "steady", "conservative"])
    current_strategy: str = "steady"


class YearCompletedPayload(EventPayload):
    year: int
    world_state: WorldState
    state_diff: dict[str, float] = Field(default_factory=dict)
    agent_actions: list[AgentAction] = Field(default_factory=list)
    ending: EndingResult | None = None
    score: float | None = None
    debate: DebateRecord | None = None
    business_dashboard: dict[str, Any] = Field(default_factory=dict)


class InterventionPendingPayload(EventPayload):
    year: int
    world_state: WorldState
    pending_intervention: PendingIntervention


class SimulationCompletedPayload(EventPayload):
    year: int
    result: str
    world_state: WorldState
    score: float | None = None
    score_detail: dict[str, float] = Field(default_factory=dict)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    action_plan: list[dict[str, Any]] = Field(default_factory=list)
    startup_settlement: dict[str, Any] = Field(default_factory=dict)


class SimulationPausedPayload(EventPayload):
    year: int
    world_state: WorldState
    pending_intervention: PendingIntervention | None = None
    pause_reason: PauseReason | None = None


class SimulationFailedPayload(EventPayload):
    code: str
    message: str


class SimulationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=0)
    session_id: str
    scenario_id: str
    event_type: EventType
    payload: (
        SimulationStartedPayload
        | YearStartedPayload
        | YearCompletedPayload
        | InterventionPendingPayload
        | SimulationCompletedPayload
        | SimulationPausedPayload
        | SimulationFailedPayload
    )
    state_snapshot: Any = Field(default=None, exclude=True, repr=False)
