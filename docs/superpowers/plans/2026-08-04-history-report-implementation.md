# 历史完整报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a complete, ownership-safe simulation record and render it as a structured Chinese history report.

**Architecture:** `SimulationSession` remains the report aggregate and stores ownership, frozen profile, timeline, and decisions. `SimulationEvent` remains the immutable per-Agent audit trail. A report assembler returns structured data for the frontend and Markdown only for download.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, Pydantic, pytest, Vue 3, Pinia, TypeScript.

## Global Constraints

- Preserve anonymous simulation access without exposing another browser's sessions.
- Keep the deterministic simulation engine as the only writer of world-state transitions.
- All user-visible report labels and metrics must be Chinese; no action IDs or raw metric keys.
- Follow TDD and run focused tests after every task.
- Do not commit or initialize Git.

---

### Task 1: Stable Session Ownership and Frozen Profiles

**Files:**
- Modify: `app/db/models.py`, `app/db/repository.py`, `app/api/dependencies.py`, `app/api/simulation.py`, `app/api/stream.py`, `app/api/sessions.py`, `app/api/diary.py`, `app/api/report.py`
- Modify: `frontend/src/api/client.ts`, `frontend/src/api/sse.ts`
- Test: `tests/test_api_endpoints.py`, `tests/test_profile_injection.py`, `tests/test_diary.py`

**Interfaces:**
- Produce an actor identity that is either the authenticated `user_id` or a stable anonymous browser key.
- Persist the actor key with the session and use the same access check for session, diary, and report endpoints.

- [ ] **Step 1: Write failing ownership and snapshot tests**

```python
def test_anonymous_client_lists_only_its_own_sessions(client):
    sid = _create_simulation(client)
    assert sid in [item["id"] for item in client.get("/api/sessions").json()]

def test_profile_is_frozen_when_starting_a_simulation(client):
    _create_and_update_profile(client, assets=500000)
    sid = _create_simulation(client)
    _create_and_update_profile(client, assets=1)
    assert _session_profile(sid)["assets"] == 500000
```

- [ ] **Step 2: Run the ownership tests and confirm they fail**

Run: `python -m pytest tests/test_api_endpoints.py tests/test_profile_injection.py tests/test_diary.py -v`

- [ ] **Step 3: Add the minimal ownership model and propagation**

```python
class RequestActor(NamedTuple):
    user_id: str | None
    anonymous_key: str | None

def assert_session_access(session, actor: RequestActor):
    if session.user_id:
        return session.user_id == actor.user_id
    return session.owner_key == actor.anonymous_key
```

Add `owner_key` to `SimulationSession`, create it from a stable browser key, pass it through stream/synchronous creation, and query sessions by the matching actor. Preserve `user_profile` when persisting final states.

- [ ] **Step 4: Re-run focused ownership tests**

Run: `python -m pytest tests/test_api_endpoints.py tests/test_profile_injection.py tests/test_diary.py -v`

### Task 2: Persist User Decision and Branch Records

**Files:**
- Modify: `app/db/models.py`, `app/db/repository.py`, `app/api/simulation.py`, `app/engine/engine.py`
- Test: `tests/test_decision_history.py`

**Interfaces:**
- Store records as `{year, raw_text, input_kind, decision_label, selected_branch, created_at}` in `SimulationSession.decision_history`.
- A preview creation records the raw proposal; selecting a branch updates the same record without advancing it twice.

- [ ] **Step 1: Write failing decision-history tests**

```python
def test_preview_and_selected_branch_are_persisted(client, paused_session):
    preview = client.post(f"/api/simulations/{paused_session}/resume", json={"choice": "请明星代言"})
    client.post(f"/api/simulations/{paused_session}/resume", json={"choice": "low_cost_alternative"})
    detail = client.get(f"/api/sessions/{paused_session}").json()
    assert detail["decision_history"][-1]["raw_text"] == "请明星代言"
    assert detail["decision_history"][-1]["selected_branch"] == "low_cost_alternative"
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `python -m pytest tests/test_decision_history.py -v`

- [ ] **Step 3: Implement append/update repository methods and API writes**

Keep `decision_history` JSON-only. Do not add LLM output or transient preview objects to it. Record casual/question inputs only when they are part of a user-visible conversation history; never let them mutate year or state.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_decision_history.py tests/test_decision_preview_api.py tests/test_resume_input_intent.py -v`

### Task 3: Structured Chinese Report Assembler

**Files:**
- Modify: `app/services/report_service.py`, `app/api/sessions.py`, `app/api/report.py`
- Create: `app/schemas/report.py`
- Test: `tests/test_report.py`, `tests/test_session_report_detail.py`

**Interfaces:**
- `build_report(session_id, actor, db) -> SimulationReport` returns metadata, profile, decisions, yearly records, conclusion, risks, and action plan.
- `generate_markdown()` renders `SimulationReport`; it does not independently traverse ORM rows.

- [ ] **Step 1: Write failing report-detail tests**

```python
def test_report_detail_contains_all_four_agents_and_chinese_metrics(client, session_id):
    report = client.get(f"/api/sessions/{session_id}/report-detail").json()
    assert set(item["agent_id"] for item in report["years"][0]["agent_actions"]) == {
        "market", "environment", "personal", "risk"
    }
    assert report["years"][0]["metrics"][0]["label"] == "现金储备"
    assert "customer_flow" not in str(report)
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `python -m pytest tests/test_report.py tests/test_session_report_detail.py -v`

- [ ] **Step 3: Implement typed report mapping**

Map world-state keys and result/status labels to Chinese in one formatter module. Include graceful empty lists for no profile, no decisions, and unfinished sessions. Guard both report endpoints with the same session actor access policy.

- [ ] **Step 4: Run focused report tests**

Run: `python -m pytest tests/test_report.py tests/test_session_report_detail.py tests/test_api_endpoints.py -v`

### Task 4: History Page Structured Rendering

**Files:**
- Modify: `frontend/src/views/HistoryView.vue`, `frontend/src/api/client.ts`, `frontend/src/api/types.ts`
- Test: frontend build

**Interfaces:**
- History list consumes `{id, scenario_title, phase, current_year, score, created_at}`.
- Expanded row fetches `/sessions/{id}/report-detail` and renders report sections; Markdown download remains a separate command.

- [ ] **Step 1: Add typed frontend report contracts**

```ts
export interface SessionReport {
  profile: Record<string, string | number | string[]>
  decisions: DecisionRecord[]
  years: YearReport[]
  conclusion: ReportConclusion
}
```

- [ ] **Step 2: Render sections without JSON stringification**

Render profile, decisions, yearly Chinese metric summaries, four Agent reasons, final score, risks, and action plan as readable bands. Use an icon button for Markdown download and preserve loading/error/empty states.

- [ ] **Step 3: Build the frontend**

Run: `npm.cmd run build`

### Task 5: Module Review and Regression

**Files:**
- Modify: `docs/开发交接清单.md`
- Test: full backend suite and frontend build

- [ ] **Step 1: Run the complete backend suite**

Run: `python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Verify product invariants**

Check that anonymous and authenticated ownership cannot cross-read sessions, profile snapshots survive later edits, decision records retain branch selection, and reports never expose raw field/action identifiers.

- [ ] **Step 3: Update handoff documentation**

Document the ownership mechanism, decision-history record format, report-detail endpoint, and the history-page data source.
