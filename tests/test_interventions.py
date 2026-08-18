from app.engine.engine import SimulationEngine
from app.engine.interventions import apply_intervention
from app.engine.models import PendingIntervention, WorldState
from app.scenarios.loader import ScenarioLoader


def test_missing_intervention_choice_pauses_simulation():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)
    initial = list(engine.iter_events({"budget": 60000}))[-1].state_snapshot
    state = list(
        engine.resume_events(initial.session_id, initial, "先压缩非必要投入")
    )[-1].state_snapshot
    assert state.phase == "paused"
    assert state.pending_intervention is not None


def test_explicit_intervention_choice_changes_state_and_is_recorded():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)
    initial = list(engine.iter_events({"budget": 60000}))[-1].state_snapshot
    pending = list(
        engine.resume_events(initial.session_id, initial, "先压缩非必要投入")
    )[-1].state_snapshot
    state = list(
        engine.resume_events(pending.session_id, pending, "cut_costs")
    )[-1].state_snapshot

    assert state.pending_intervention is None
    assert state.pause_reason in {"year_decision_required", "horizon_review"}
    assert state.phase in {"paused", "horizon_review"}
    assert all(item.choice == "cut_costs" for item in state.interventions)


def test_invalid_intervention_choice_is_rejected():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)
    initial = list(engine.iter_events({"budget": 60000}))[-1].state_snapshot
    pending = list(
        engine.resume_events(initial.session_id, initial, "先压缩非必要投入")
    )[-1].state_snapshot

    try:
        list(engine.resume_events(pending.session_id, pending, "not_declared"))
    except ValueError:
        return
    raise AssertionError("undeclared intervention choice must fail")


def test_localized_intervention_choice_resolves_to_declared_effect():
    source = ScenarioLoader("scenarios").load("grad_exam")
    pending = PendingIntervention(
        rule_id="financial_pressure",
        year=1,
        event="备考资金紧张",
        options=["继续冲刺", "边工作边备考"],
        metric_snapshot=source.initial_world_state,
    )

    transition = apply_intervention(
        WorldState.model_validate(source.initial_world_state),
        pending,
        "继续冲刺",
        source,
    )

    assert transition.effects[0].action_id == "intervention.increase_hours"


def test_every_scenario_intervention_option_has_a_resolvable_effect():
    loader = ScenarioLoader("scenarios")

    for scenario_id in loader.list_all():
        source = loader.load(scenario_id)
        for rule in source.intervention_rules:
            pending = PendingIntervention(
                rule_id=rule.rule_id,
                year=1,
                event=rule.event,
                options=rule.options,
                metric_snapshot=source.initial_world_state,
            )
            for choice in rule.options:
                apply_intervention(
                    WorldState.model_validate(source.initial_world_state),
                    pending,
                    choice,
                    source,
                )
