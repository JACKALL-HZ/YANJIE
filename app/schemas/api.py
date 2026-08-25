from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.engine.models import DecisionPreviewSet
from app.schemas.domain_models import PauseReason, PendingIntervention, TimelineNode


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationMessage(RequestModel):
    """用户启动推演前与向导的对话消息。"""

    role: Literal["user", "agent", "system"]
    agent_id: str | None = Field(default=None, max_length=64)
    content: str = Field(min_length=1, max_length=10000)
    year: int | None = Field(default=None, ge=0)


class SimulationRequest(RequestModel):
    scenario_id: str = Field(max_length=255)
    decision_vars: dict[str, Any] = Field(default_factory=dict)
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=200,
        description="启动推演前的用户与向导对话记录",
    )
    user_profile: dict[str, Any] | None = None
    intervention_choices: dict[int, str] | None = None
    strategy_directives: dict[int, str] | None = Field(
        default=None,
        max_length=50,
        description="年度策略指令: {1: 'aggressive', 2: 'steady', 3: 'conservative'}",
    )
    success_definition: dict[str, Any] | None = Field(
        default=None,
        description="自定义成功标准: {target_monthly_profit: 10000, priority: 'survival'}",
    )


class SimulationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    scenario_id: str
    phase: str
    year: int
    result: str | None
    timeline: list[TimelineNode]
    score: float | None
    score_detail: dict[str, float]
    risks: list[dict[str, Any]]
    action_plan: list[dict[str, Any]]
    startup_settlement: dict[str, Any] = Field(default_factory=dict)
    pending_intervention: PendingIntervention | None
    pending_decision_preview: DecisionPreviewSet | None = None
    pause_reason: PauseReason | None = None
    input_kind: str | None = None
    input_feedback: str | None = None


class CompareRequest(RequestModel):
    scenario_id: str = Field(max_length=255)
    decision_vars_a: dict[str, Any] = Field(default_factory=dict)
    decision_vars_b: dict[str, Any] = Field(default_factory=dict)
    user_profile: dict[str, Any] | None = None
    intervention_choices_a: dict[int, str] | None = None
    intervention_choices_b: dict[int, str] | None = None
    strategy_directives_a: dict[int, str] | None = None
    strategy_directives_b: dict[int, str] | None = None
    success_definition: dict[str, Any] | None = None


class CompareSessionsRequest(BaseModel):
    """从两个已有 session 重建对比结果，不重跑推演。"""

    session_id_a: str = Field(..., max_length=36)
    session_id_b: str = Field(..., max_length=36)


class CompareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    a: SimulationResponse
    b: SimulationResponse
    comparison: dict[str, Any]
