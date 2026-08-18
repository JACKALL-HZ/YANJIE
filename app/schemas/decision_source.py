from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


_WORLD_STATE_METRICS = frozenset(
    {"cash_flow", "customer_flow", "competition_count", "monthly_profit", "payback_ratio"}
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DecisionVarDef(StrictModel):
    name: str
    value_type: Literal["integer", "number", "string"]
    required: bool = True
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None


class StateMetricDef(StrictModel):
    metric_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    initial_value: float = 0
    display_order: int = Field(ge=0)
    source_metric: str | None = None


class StateMetricModifier(StrictModel):
    metric: str = Field(min_length=1)
    input_key: str = Field(
        min_length=1,
        validation_alias=AliasChoices("input_key", "profile_key", "decision_var"),
    )
    multiplier: float = 1
    offset: float = 0


class AgentDef(StrictModel):
    agent_id: Literal["market", "environment", "personal", "risk"]
    name: str
    stance: str
    goal: str
    action_ids: list[str] = Field(min_length=1)


class ActionEffectDef(StrictModel):
    action_id: str
    effects: dict[str, float] = Field(default_factory=dict)
    reason_template: str


PreviewBranchId = Literal[
    "user_proposal",
    "expert_recommendation",
    "low_cost_alternative",
]


class DecisionPreviewBranchDef(StrictModel):
    branch_id: PreviewBranchId
    label: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["low", "medium", "high"]
    worst_case_loss: float = Field(ge=0)


class DecisionCatalogueEntry(StrictModel):
    decision_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    branches: list[DecisionPreviewBranchDef] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_required_branches(self) -> "DecisionCatalogueEntry":
        expected = {"user_proposal", "expert_recommendation", "low_cost_alternative"}
        actual = {branch.branch_id for branch in self.branches}
        if actual != expected:
            raise ValueError("decision catalogue must declare exactly three preview branches")
        return self


class MetricCondition(StrictModel):
    metric: str
    operator: Literal["<", "<=", ">", ">=", "=="] = Field(
        validation_alias=AliasChoices("operator", "op")
    )
    threshold: float


class EndConditions(StrictModel):
    bankrupt: MetricCondition
    goal_reached: MetricCondition | None = None
    steady_state: MetricCondition | None = None
    timeout_years: int = Field(gt=0, le=10)


class InterventionRule(StrictModel):
    rule_id: str
    metric: str
    operator: Literal["<", "<=", ">", ">=", "=="] = Field(
        validation_alias=AliasChoices("operator", "op")
    )
    threshold: float
    event: str
    options: list[str] = Field(min_length=1)
    option_actions: dict[str, str] = Field(default_factory=dict)
    max_uses: int = Field(default=1, ge=1)


class DecisionSource(StrictModel):
    scenario_id: str
    title: str
    version: int = Field(ge=1)
    decision_vars: list[DecisionVarDef] = Field(min_length=1)
    initial_world_state: dict[str, float] = Field(default_factory=dict)
    state_metrics: list[StateMetricDef] = Field(default_factory=list)
    profile_state_modifiers: list[StateMetricModifier] = Field(default_factory=list)
    decision_var_state_modifiers: list[StateMetricModifier] = Field(default_factory=list)
    agents: list[AgentDef] = Field(min_length=4, max_length=4)
    action_effects: list[ActionEffectDef] = Field(min_length=1)
    intervention_effects: list[ActionEffectDef] = Field(default_factory=list)
    end_conditions: EndConditions
    intervention_rules: list[InterventionRule] = Field(default_factory=list)
    decision_catalogue: list[DecisionCatalogueEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metric_and_preview_references(self) -> "DecisionSource":
        dynamic_metrics = [item.metric_id for item in self.state_metrics]
        if len(dynamic_metrics) != len(set(dynamic_metrics)):
            raise ValueError("state metric ids must be unique")
        if set(dynamic_metrics) & _WORLD_STATE_METRICS:
            raise ValueError("state metric id duplicates a legacy world-state metric")

        allowed_metrics = _WORLD_STATE_METRICS | set(dynamic_metrics)
        for effect in [*self.action_effects, *self.intervention_effects]:
            unknown_metrics = set(effect.effects) - allowed_metrics
            if unknown_metrics:
                names = ", ".join(sorted(unknown_metrics))
                raise ValueError(f"unknown world-state metric: {names}")

        for modifier in [
            *self.profile_state_modifiers,
            *self.decision_var_state_modifiers,
        ]:
            if modifier.metric not in allowed_metrics:
                raise ValueError(
                    f"state modifier references unknown metric: {modifier.metric}"
                )

        decision_var_names = {item.name for item in self.decision_vars}
        unknown_decision_modifier_keys = {
            modifier.input_key
            for modifier in self.decision_var_state_modifiers
            if modifier.input_key not in decision_var_names
        }
        if unknown_decision_modifier_keys:
            names = ", ".join(sorted(unknown_decision_modifier_keys))
            raise ValueError(
                f"state modifier references unknown decision var: {names}"
            )

        for condition in [
            self.end_conditions.bankrupt,
            self.end_conditions.goal_reached,
            self.end_conditions.steady_state,
            *(rule for rule in self.intervention_rules),
        ]:
            if condition is not None and condition.metric not in allowed_metrics:
                raise ValueError(
                    f"unknown world-state metric: {condition.metric}"
                )

        action_ids = {effect.action_id for effect in self.action_effects}
        for decision in self.decision_catalogue:
            for branch in decision.branches:
                if branch.action_id not in action_ids:
                    raise ValueError(
                        f"decision preview action is not declared: {branch.action_id}"
                    )

        intervention_action_ids = {
            effect.action_id for effect in self.intervention_effects
        }
        for rule in self.intervention_rules:
            unknown_options = set(rule.option_actions) - set(rule.options)
            if unknown_options:
                names = ", ".join(sorted(unknown_options))
                raise ValueError(
                    f"intervention option mapping is not declared in options: "
                    f"{rule.rule_id}: {names}"
                )

            for option in rule.options:
                action_id = rule.option_actions.get(
                    option,
                    option
                    if option.startswith("intervention.")
                    else f"intervention.{option}",
                )
                if action_id not in intervention_action_ids:
                    raise ValueError(
                        f"intervention option has no declared effect: "
                        f"{rule.rule_id}/{option} -> {action_id}"
                    )
        return self
