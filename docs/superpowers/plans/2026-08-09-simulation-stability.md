# Simulation Stability Implementation Plan

> **For agentic workers:** Execute inline with a review checkpoint after each task. No commit is created because this checkout has no Git repository.

**Goal:** Make simulation tests exercise the active yearly-decision protocol and repair independently failing scene routing.

**Architecture:** The runtime contract remains unchanged: simulation creation pauses at year zero, and one resume decision advances one year. Test helpers will explicitly perform that transition before asserting timeline, report, persistence, or completion data. The classifier will choose a specialized entrepreneurship scenario before generic fallback.

**Tech Stack:** Python 3.12, FastAPI, pytest, Pydantic.

## Global Constraints

- Do not restore anonymous simulation access.
- Do not change the active year-zero pause behavior to satisfy obsolete tests.
- Write or update a failing regression test before each runtime fix.
- Run targeted tests after each task and the full suite at the end.

---

### Task 1: Record and Protect the Active Simulation Contract

**Files:**
- Create: `docs/bug-reports/2026-08-09-simulation-stability-audit.md`
- Modify: `tests/test_session_isolation.py`
- Test: `tests/test_all_scene_yearly_protocol.py`, `tests/test_session_isolation.py`

- [x] Document the reproduction, impact, and classification of each observed failure group.
- [x] Replace the obsolete guest-session isolation assertion with a `401` anonymous-request assertion.
- [x] Verify authenticated users cannot list or retrieve another user's session.

### Task 2: Migrate Lifecycle Assertions to One-Year Progress

**Files:**
- Modify: `tests/test_ask.py`, `tests/test_stream.py`, `tests/test_report.py`, `tests/test_session_report_detail.py`
- Test: the same files plus `tests/test_all_scene_yearly_protocol.py`

- [x] Update each setup helper to create a session, submit a valid yearly decision, and retain the returned session id.
- [x] Assert timeline, stream, report, and ask-context details only after a year has completed.
- [x] Keep tests that intentionally verify the year-zero pause unchanged.

### Task 3: Repair Specialized Scenario Routing

**Files:**
- Modify: `app/kb/classify_scene.py`
- Test: `tests/test_scene_routing.py`

- [x] Run the specialized entrepreneurship routing test to confirm failure.
- [x] Match specialized business keywords before returning `general_startup`.
- [x] Run all scenario routing tests.

### Task 4: Migrate Remaining Engine Persistence Tests

**Files:**
- Modify: `tests/test_ac7_decoupling.py`, `tests/test_agent_decision_context.py`, `tests/test_api_endpoints.py`, `tests/test_checkpoint.py`, `tests/test_db_persistence.py`, `tests/test_diary.py`, `tests/test_e2e_milktea.py`, `tests/test_e2e_role_debate.py`, `tests/test_engine_persist.py`, `tests/test_judge_revision.py`, `tests/test_user_participation.py`, `tests/test_yanjie_engine.py`
- Test: the same files

- [x] Replace direct completion assumptions with explicit `resume_events` or API `/resume` calls.
- [x] Keep assertions about intervention, persistence, calibration, and ending conditions after the relevant state exists.
- [x] Run each migrated suite before proceeding.

### Task 5: Final Verification

**Files:**
- Verify: `app/`, `tests/`, `frontend/`

- [x] Run `.\.venv\Scripts\python.exe -m pytest -q --tb=short`.
- [x] Run `.\.venv\Scripts\python.exe -m pip check`.
- [x] Run `cmd.exe /d /c npm run build` from `frontend/`.
