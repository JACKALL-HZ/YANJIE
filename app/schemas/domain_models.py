"""共享领域模型 —— 跨层引用的纯数据 Pydantic 模型。

放在 schemas/ 下作为底层契约，engine/models.py、schemas/events.py、schemas/api.py
均从此处引用，消除 schemas → engine.models 的依赖倒置。
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


PauseReason = Literal[
    "year_decision_required",
    "decision_preview_required",
    "intervention_required",
    "horizon_review",
]


class DomainModel(BaseModel):
    """严格模式基类，禁止额外字段。"""
    model_config = ConfigDict(extra="forbid")


# ── 世界状态 ──────────────────────────────────────────────


class WorldState(DomainModel):
    cash_flow: float = 0
    customer_flow: float = 0
    competition_count: float = 0
    monthly_profit: float = 0
    payback_ratio: float = 0
    metrics: dict[str, float] = Field(default_factory=dict)


# ── Agent 决策 ────────────────────────────────────────────


class AgentEvidence(DomainModel):
    tool_name: str
    summary: str
    sources: list[str] = Field(default_factory=list)
    status: Literal["disabled", "hit", "empty", "error", "local"] = "empty"


class DebateParticipant(DomainModel):
    agent_id: Literal["market", "environment", "personal", "risk"]
    position: Literal["support", "oppose", "conditional", "neutral"]
    reason: str
    recommendation: str = ""
    objection: str | None = None


class DebateRecord(DomainModel):
    trigger: Literal["judge_conflict", "high_impact_decision"]
    conflicts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    participants: list[DebateParticipant] = Field(default_factory=list)
    judge_summary: str = ""


class AgentAction(DomainModel):
    agent_id: Literal["market", "environment", "personal", "risk"]
    action_id: str
    reason: str
    confidence: float = Field(ge=0, le=1)
    # 运行来源用于区分真实模型、离线 stub 与异常降级。
    generation_source: Literal["llm", "stub", "fallback"] = "stub"
    llm_called: bool = False
    rag_status: Literal["disabled", "hit", "empty", "error"] = "disabled"
    rag_sources: list[str] = Field(default_factory=list)
    yearly_strategy: str = "steady"  # 该年度用户策略指令
    position: Literal["support", "oppose", "conditional", "neutral"] = "neutral"
    evidence: list[AgentEvidence] = Field(default_factory=list)
    recommendation: str = ""
    key_factors: list[str] = Field(default_factory=list, max_length=3)
    next_actions: list[str] = Field(default_factory=list, max_length=3)
    uncertainty: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    objection: str | None = None
    stop_condition: str | None = None


# ── 推演结局 ──────────────────────────────────────────────


class EndingReason(DomainModel):
    metric: str
    operator: str
    threshold: float
    actual: float


class EndingResult(DomainModel):
    result: Literal["goal_reached", "steady", "bankrupt", "timeout"]
    reason: EndingReason


# ── 干预 ──────────────────────────────────────────────────


class InterventionRecord(DomainModel):
    rule_id: str
    year: int = Field(ge=1)
    choice: str
    effects: dict[str, float] = Field(default_factory=dict)


class PendingIntervention(DomainModel):
    rule_id: str
    year: int = Field(ge=1)
    event: str
    options: list[str] = Field(min_length=1)
    metric_snapshot: dict[str, Any] = Field(default_factory=dict)


# ── 时间线 ────────────────────────────────────────────────


class TimelineNode(DomainModel):
    year: int = Field(ge=1)
    world_state: WorldState
    agent_actions: list[AgentAction] = Field(default_factory=list)
    state_diff: dict[str, float] = Field(default_factory=dict)
    interventions: list[InterventionRecord] = Field(default_factory=list)
    ending: EndingResult | None = None
    debate: DebateRecord | None = None
    business_dashboard: dict[str, Any] = Field(default_factory=dict)
