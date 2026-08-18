from typing import Any, Literal

from pydantic import Field

# 从 schemas 契约层导入共享领域模型（消除倒置依赖）
from app.schemas.domain_models import (  # noqa: F401  re-export
    AgentAction,
    DomainModel,
    EndingReason,
    EndingResult,
    InterventionRecord,
    PauseReason,
    PendingIntervention,
    TimelineNode,
    WorldState,
)

# ── 引擎专用类型（依赖上述共享模型） ──────────────────────


Phase = Literal[
    "input", "simulating", "paused", "horizon_review", "scoring", "completed"
]
ResultType = Literal[
    "goal_reached", "steady", "bankrupt", "timeout", "user_ended", "paused"
]


class StateEffect(DomainModel):
    action_id: str
    effects: dict[str, float] = Field(default_factory=dict)


class EventRecord(DomainModel):
    agent_id: Literal["market", "environment", "personal", "risk"]
    action_id: str
    reason: str
    state_diff: dict[str, float] = Field(default_factory=dict)


class TransitionResult(DomainModel):
    world_state: WorldState
    effects: list[StateEffect] = Field(default_factory=list)
    events: list[EventRecord] = Field(default_factory=list)


class AgentConstraint(DomainModel):
    """由智能体分歧产生、仅在下一轮生效的动作边界。"""

    allowed_action_ids: list[str] = Field(default_factory=list)
    instruction: str
    summary: str


class SimulationState(DomainModel):
    session_id: str = ""
    scenario_id: str
    decision_vars: dict[str, Any] = Field(default_factory=dict)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    success_definition: dict[str, Any] = Field(default_factory=dict)
    scenario_brief: str = ""
    startup_ledger: dict[str, Any] = Field(default_factory=dict)
    startup_dashboard: dict[str, Any] = Field(default_factory=dict)
    startup_settlement: dict[str, Any] = Field(default_factory=dict)
    agent_constraints: dict[str, AgentConstraint] = Field(default_factory=dict)
    phase: Phase = "input"
    pause_reason: PauseReason | None = None
    year: int = 0
    yearly_strategy: str = "steady"
    world_state: WorldState
    agent_actions: list[AgentAction] = Field(default_factory=list)
    timeline: list[TimelineNode] = Field(default_factory=list)
    interventions: list[InterventionRecord] = Field(default_factory=list)
    pending_intervention: PendingIntervention | None = None
    user_message: str = ""  # 逐年交互模式下用户输入的消息
    result: ResultType | None = None
    score: float | None = None
    score_detail: dict[str, float] = Field(default_factory=dict)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    action_plan: list[dict[str, Any]] = Field(default_factory=list)
    pending_decision_preview: "DecisionPreviewSet | None" = None


class DecisionPreview(DomainModel):
    branch_id: Literal[
        "user_proposal", "expert_recommendation", "low_cost_alternative"
    ]
    label: str
    description: str
    action_id: str
    world_state: WorldState
    state_diff: dict[str, float]
    risk_level: Literal["low", "medium", "high"]
    worst_case_loss: float
    summary: str


class DecisionPreviewSet(DomainModel):
    decision_id: str
    decision_label: str
    proposal_text: str
    branches: list[DecisionPreview] = Field(min_length=3, max_length=3)
