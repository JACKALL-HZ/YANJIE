from typing import Any

from pydantic import Field

from app.schemas.domain_models import AgentEvidence, DebateRecord, DomainModel


class ReportMetric(DomainModel):
    label: str
    value: str
    change: str | None = None


class ReportAgentAction(DomainModel):
    agent_id: str
    agent_name: str
    reason: str
    confidence: str | None = None
    generation_source: str | None = None
    llm_called: bool | None = None
    rag_status: str | None = None
    rag_sources: list[str] = Field(default_factory=list)
    position: str | None = None
    evidence: list[AgentEvidence] = Field(default_factory=list)
    recommendation: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    objection: str | None = None
    stop_condition: str | None = None


class ReportDecision(DomainModel):
    year: int
    proposal: str
    decision_label: str | None = None
    selected_branch_label: str | None = None
    created_at: str | None = None


class ReportYear(DomainModel):
    year: int
    metrics: list[ReportMetric] = Field(default_factory=list)
    agent_actions: list[ReportAgentAction] = Field(default_factory=list)
    ending: str | None = None
    debate: DebateRecord | None = None


class ReportScore(DomainModel):
    label: str
    value: str


class ReportRisk(DomainModel):
    level: str
    title: str
    message: str


class ReportActionPlanItem(DomainModel):
    title: str
    committed: bool = False


class ReportMessage(DomainModel):
    role: str
    agent_id: str | None = None
    content: str
    year: int | None = None
    created_at: str | None = None


class ReportConclusion(DomainModel):
    phase: str
    phase_label: str
    result_label: str
    score: str | None = None
    score_details: list[ReportScore] = Field(default_factory=list)


class SimulationReport(DomainModel):
    session_id: str
    scenario_id: str
    scenario_title: str
    created_at: str | None = None
    profile: list[ReportMetric] = Field(default_factory=list)
    initial_conditions: list[ReportMetric] = Field(default_factory=list)
    decisions: list[ReportDecision] = Field(default_factory=list)
    messages: list[ReportMessage] = Field(default_factory=list)
    years: list[ReportYear] = Field(default_factory=list)
    conclusion: ReportConclusion
    risks: list[ReportRisk] = Field(default_factory=list)
    action_plan: list[ReportActionPlanItem] = Field(default_factory=list)
