"""Deterministic read-only previews for catalogue-backed user decisions."""

from app.engine.models import DecisionPreview, DecisionPreviewSet, SimulationState
from app.engine.reducers import apply_effect_definitions
from app.engine.metric_narrator import metric_label
from app.schemas.decision_source import DecisionCatalogueEntry, DecisionSource


def match_catalogue_decision(
    proposal_text: str,
    source: DecisionSource,
) -> DecisionCatalogueEntry | None:
    normalized = proposal_text.strip().lower()
    if not normalized:
        return None
    for decision in source.decision_catalogue:
        if any(keyword.lower() in normalized for keyword in decision.keywords):
            return decision
    return None


def _preview_summary(preview: DecisionPreview) -> str:
    state = preview.world_state
    return (
        f"{preview.description} 预计{metric_label('cash_flow')}{state.cash_flow:.0f}元，"
        f"{metric_label('customer_flow')}{state.customer_flow:.0f}杯，"
        f"{metric_label('monthly_profit')}{state.monthly_profit:.0f}元。"
    )


def build_decision_previews(
    state: SimulationState,
    proposal_text: str,
    source: DecisionSource,
) -> DecisionPreviewSet | None:
    """Build comparable previews without mutating or persisting the main timeline."""
    decision = match_catalogue_decision(proposal_text, source)
    if decision is None:
        return None

    action_effects = {effect.action_id: effect for effect in source.action_effects}
    previews: list[DecisionPreview] = []
    for branch in decision.branches:
        effect = action_effects[branch.action_id]
        transition = apply_effect_definitions(state.world_state, [effect])
        preview = DecisionPreview(
            branch_id=branch.branch_id,
            label=branch.label,
            description=branch.description,
            action_id=branch.action_id,
            world_state=transition.world_state,
            state_diff=dict(effect.effects),
            risk_level=branch.risk_level,
            worst_case_loss=branch.worst_case_loss,
            summary="",
        )
        previews.append(preview.model_copy(update={"summary": _preview_summary(preview)}))

    return DecisionPreviewSet(
        decision_id=decision.decision_id,
        decision_label=decision.label,
        proposal_text=proposal_text.strip(),
        branches=previews,
    )
