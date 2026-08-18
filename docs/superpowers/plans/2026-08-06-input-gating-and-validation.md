# Input Gating And Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. The repository has no Git workflow; do not create commits.

**Goal:** Prevent invalid LLM-extracted decision variables from starting a simulation, and require a user-recognized input before showing any start control.

**Architecture:** The backend treats LLM extraction as untrusted data and removes values that violate the selected scenario schema before returning them to the UI. The onboarding flow separates scenario defaults from recognized user input; defaults remain visible as examples but cannot independently enable simulation startup.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, Vue 3, TypeScript, Vite.

## Global Constraints

- Scenario JSON is the source of truth for types, bounds, required fields, and defaults.
- LLM output is untrusted and must be schema-filtered before it reaches simulation state.
- No simulation starts until user input has yielded at least one valid field for the selected scenario and all required fields are present.
- User-facing copy must be Chinese; internal field IDs remain snake_case.
- Do not create commits or change credentials.

---

### Task 1: Filter invalid extracted values before onboarding merges them

**Files:**
- Modify: `app/services/breakdown_service.py`
- Modify: `tests/test_breakdown.py`

**Interfaces:**
- `BreakdownService._filter_extracted_vars(source, values) -> tuple[dict[str, Any], dict[str, str]]` returns valid values plus user-facing invalid-field messages.
- `BreakdownResult.missing_required` is calculated from filtered values.

- [x] Write a failing test where the LLM returns `{"income": 0}` for `house_purchase`; assert `income` is absent and remains missing.
- [x] Run the isolated pytest test and observe failure.
- [x] Add the minimal schema-aware filter; apply it to LLM and fallback extraction results before missing-field calculation.
- [x] Run `pytest -q tests/test_breakdown.py`.

### Task 2: Make sample defaults non-startable until user input is recognized

**Files:**
- Modify: `frontend/src/components/chat/OnboardingChat.vue`
- Modify: `frontend/src/views/SimView.vue`

**Interfaces:**
- `OnboardingChat` emits `readiness-change` with `{ hasRecognizedInput, ready }` whenever its state changes.
- `ready` means at least one valid user-recognized field exists and all required fields are available.
- `SimView` shows sample parameters while `hasRecognizedInput` is false, and only renders a start control after `ready` is true.

- [x] Add the readiness state and emit it after initialization and each successful extraction.
- [x] Keep scenario defaults in the parameter panel but label them as examples before user input is recognized.
- [x] Remove the idle-state header start button and route starts through the confirmed onboarding event only.
- [x] Run `npm.cmd run build`.

### Task 3: Guard the API boundary and verify the full flow

**Files:**
- Modify: `app/engine/state.py`
- Modify: `tests/test_stream.py`
- Modify: `tests/test_state_and_reducers.py`

**Interfaces:**
- Invalid direct requests still terminate safely, with Chinese validation feedback that includes the field and bound.

- [x] Write a failing stream test for `house_purchase` with `income=0` and assert Chinese validation feedback.
- [x] Convert state validation messages to Chinese, retaining field/bound information.
- [x] Run focused backend tests and `npm.cmd run build`.
- [ ] Complete full `pytest -q` in an environment where the suite does not hang.

## Self-Review

- Backend filtering prevents an invalid LLM value from overwriting a sample/default value.
- Frontend examples cannot make `ready` true by themselves.
- The normal confirmed-input flow and direct API validation both remain covered.
