# Simulation Stability Audit

## Scope

Backend test audit run with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

## Confirmed Product Regression

### ROUTING-001: Specialized entrepreneurship requests use the generic scenario

- Reproduction: `tests/test_scene_routing.py::test_specialized_entrepreneurship_keeps_specific_template`
- Expected: milk-tea and SaaS wording routes to `milktea_startup` and
  `saas_startup`.
- Actual: both route to `general_startup`.
- Impact: users lose scenario-specific variables, rules, and action catalogues.
- Fix: restore specialized-keyword detection before the generic
  entrepreneurship fallback.

### ROUTING-002: Breakdown tests retained the obsolete generic-startup expectation

- Reproduction: `tests/test_breakdown.py` after ROUTING-001.
- Expected: named milk-tea and restaurant businesses retain their specialized
  scenario ids while missing required values remain unfilled.
- Actual: three tests still expected `general_startup`.
- Impact: the regression suite would reject the intended specialized routing.
- Fix: update the expectations to `milktea_startup` and `restaurant_startup`;
  keep the assertions that unspecified budget and city are not fabricated.

### CONTEXT-001: Batch simulation discarded the user's latest conversation decision

- Reproduction: `tests/test_agent_decision_context.py::test_initial_conversation_history_reaches_first_year_agents`.
- Expected: when batch comparison is initialized with conversation history, its
  first simulated year uses the last user decision as Agent context.
- Actual: `run_batch()` always replaced that decision with its generic steady
  strategy text.
- Impact: comparison results could ignore the decision a user had just stated.
- Fix: use the last user message for year zero in `run_batch()` only. The
  interactive API still waits for an explicit yearly `/resume` decision.

## Contract-Drift Failures

The active product contract is:

1. Create a simulation.
2. Receive `simulation.started` and `simulation.paused` at year 0.
3. Submit a yearly decision through `/resume`.
4. Receive the first `year.completed` event and a persisted timeline node.

Older tests bypass step 3 and assert completed state, timeline entries,
interventions, reports, or calibration immediately after creation. They do not
describe the active user flow and must be migrated rather than driving an
engine rollback.

Affected suites include:

- `test_ac7_decoupling.py`
- `test_agent_decision_context.py`
- `test_api_endpoints.py`
- `test_ask.py`
- `test_checkpoint.py`
- `test_db_persistence.py`
- `test_diary.py`
- `test_e2e_milktea.py`
- `test_e2e_role_debate.py`
- `test_engine_persist.py`
- `test_judge_revision.py`
- `test_report.py`
- `test_session_report_detail.py`
- `test_stream.py`
- `test_user_participation.py`
- `test_yanjie_engine.py`

## Intentional Security Change

Anonymous session tests were replaced with a regression check that anonymous
simulation requests return `401`. Authenticated users remain isolated from
each other's sessions.
