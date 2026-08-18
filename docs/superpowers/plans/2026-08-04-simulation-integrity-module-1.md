# Simulation Input Integrity Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent questions and casual Chinese replies from advancing a paused simulation, and make the SSE stream emit one strictly increasing, terminally well-formed event sequence.

**Architecture:** Add a deterministic, server-side input classifier at the API boundary. Keep the existing deterministic engine unchanged for an accepted business action; casual/question/ambiguous text returns the persisted paused state with Chinese feedback. Reserve stream sequence zero for the HTTP connection event and renumber engine events at the stream adapter, while always yielding and serializing validation failures.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, httpx TestClient, Vue 3 and TypeScript.

**Completion (2026-08-04):** Tasks 1-4 are complete. The module regression suite passed (`27 passed`). The complete backend suite has four pre-existing failures in session ownership/listing, diary filtering, and frozen profile persistence; these belong to the later history and anonymous-identity module and are not caused by this module.

## Global Constraints

- Test commands use `python -m pytest`; do not use bare `pytest`.
- Tests run with `LLM_USE_STUB=1` and do not call Qwen, Tavily or embedding APIs.
- User-visible copy is Chinese; no internal field names or English classification labels are rendered in the UI.
- `scenarios/*.json` remains the sole source of simulation facts; this module introduces no LLM-driven state mutation.
- No Git operations are performed because this workspace has no Git repository.
- Each completed task requires its listed focused tests, a diff review, and the full backend suite before the module review gate.

## File Structure

- Create `app/services/input_intent.py`: deterministic classification of raw user text into a constrained `InputIntent` result.
- Modify `app/schemas/api.py`: typed response metadata for non-advancing input.
- Modify `app/api/simulation.py`: classify `/resume` input before calling `SimulationService.resume`.
- Modify `app/api/stream.py`: reserve stream sequence zero, renumber engine events, and yield validation failures.
- Modify `frontend/src/views/SimView.vue`: remove the client-only question classifier and render server acknowledgement without falsely showing a yearly advance.
- Modify `tests/conftest.py`: isolate tests from the developer `.env` and reset cached settings.
- Create `tests/test_input_intent.py`: unit tests for Chinese question, casual, business, and ambiguous text.
- Create `tests/test_resume_input_intent.py`: API tests proving casual/question text does not advance a paused session.
- Modify `tests/test_stream.py`: assert strictly increasing SSE sequences and validation failure delivery.

---

### Task 1: Isolate Tests From Local Runtime Settings

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_config_and_loader.py`

**Interfaces:**
- Sets `LLM_USE_STUB=1` and `PAUSE_EACH_YEAR=0` at `conftest.py` module import time, before any `app.*` import can read `.env`.
- Tests that exercise pause behavior explicitly override `PAUSE_EACH_YEAR` with `monkeypatch` before constructing an engine or service.

- [ ] **Step 1: Write the failing test**

```python
def test_test_settings_default_to_stub():
    assert get_settings().llm_use_stub is True
```

- [ ] **Step 2: Run test to verify it fails outside the isolated fixture**

Run: `python -m pytest tests/test_config_and_loader.py::test_test_settings_default_to_stub -v`

Expected: FAIL because the checked-in `.env` sets `LLM_USE_STUB=0`.

- [ ] **Step 3: Add the autouse fixture and keep production settings untouched**

```python
os.environ["LLM_USE_STUB"] = "1"
os.environ["PAUSE_EACH_YEAR"] = "0"
```

- [ ] **Step 4: Run focused config tests**

Run: `python -m pytest tests/test_config_and_loader.py -v`

Expected: PASS with no outbound HTTP log lines.

- [ ] **Step 5: Review this task**

Inspect: `git diff -- tests/conftest.py tests/test_config_and_loader.py` is unavailable in this workspace; instead inspect the two files and verify the fixture modifies only process-local environment variables and always clears the cache.

### Task 2: Add a Deterministic Server-Side Input Classifier

**Files:**
- Create: `app/services/input_intent.py`
- Create: `tests/test_input_intent.py`

**Interfaces:**
- Produces `InputKind = Literal["question", "casual", "business_decision", "clarify"]`.
- Produces `InputIntent(kind: InputKind, feedback: str)`.
- Exposes `classify_input(text: str) -> InputIntent`.
- Whitespace-only input raises `ValueError("请输入具体问题或经营决策")`.

- [ ] **Step 1: Write failing classifier tests**

```python
@pytest.mark.parametrize(("text", "kind"), [
    ("怎么才能盈利？", "question"),
    ("好吧", "casual"),
    ("我再想想", "casual"),
    ("请明星代言", "business_decision"),
    ("说得更激进一点", "clarify"),
])
def test_classify_input(text, kind):
    assert classify_input(text).kind == kind

def test_blank_input_is_rejected():
    with pytest.raises(ValueError, match="请输入具体问题或经营决策"):
        classify_input("  ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_input_intent.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.input_intent'`.

- [ ] **Step 3: Implement ordered deterministic rules**

```python
CASUAL_PHRASES = frozenset({"好吧", "我想想", "我再想想", "再看看", "知道了"})
QUESTION_MARKERS = ("?", "？", "什么", "为什么", "怎么", "如何", "多少")
DECISION_VERBS = ("请", "投", "加", "减少", "开", "选", "买", "卖", "代言")

def classify_input(text: str) -> InputIntent:
    normalized = text.strip()
    if not normalized:
        raise ValueError("请输入具体问题或经营决策")
    if normalized in CASUAL_PHRASES:
        return InputIntent(kind="casual", feedback="当前推演保持暂停，等你准备好再提交下一步决策。")
    if normalized.endswith(("?", "？")) or any(marker in normalized for marker in QUESTION_MARKERS[2:]):
        return InputIntent(kind="question", feedback="这是一个问题，不会推进经营年度。")
    if any(marker in normalized for marker in DECISION_VERBS):
        return InputIntent(kind="business_decision", feedback="已收到你的经营决策，正在进入推演。")
    return InputIntent(kind="clarify", feedback="我还不确定这是否是经营决策，请补充你准备采取的具体动作。")
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_input_intent.py -v`

Expected: PASS.

- [ ] **Step 5: Review this task**

Inspect classifier ordering: exact casual matching must run before question markers; no rule may call an LLM or mutate `SimulationState`.

### Task 3: Gate Resume Before the Engine Advances

**Files:**
- Modify: `app/schemas/api.py`
- Modify: `app/api/simulation.py`
- Modify: `frontend/src/views/SimView.vue`
- Create: `tests/test_resume_input_intent.py`

**Interfaces:**
- `SimulationResponse` gains optional `input_kind: str | None = None` and `input_feedback: str | None = None`.
- `_to_response(state, *, input_kind=None, input_feedback=None) -> SimulationResponse` serializes this metadata.
- `POST /api/simulations/{session_id}/resume` returns a paused response without calling `SimulationService.resume` for `casual`, `question`, or `clarify` input.

- [ ] **Step 1: Write failing API tests**

```python
@pytest.mark.parametrize("message", ["好吧", "怎么才能盈利？", "我再想想"])
def test_non_decision_resume_keeps_session_paused(client, message):
    paused = create_year_paused_session(client)
    before_year = paused["year"]
    response = client.post(
        f"/api/simulations/{paused['session_id']}/resume",
        json={"choice": message},
    )
    assert response.status_code == 200
    assert response.json()["phase"] == "paused"
    assert response.json()["year"] == before_year
    assert response.json()["input_kind"] in {"casual", "question", "clarify"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_resume_input_intent.py -v`

Expected: FAIL because the existing endpoint advances `resume_events` for every `choice`.

- [ ] **Step 3: Implement the pause-preserving response path**

```python
intent = classify_input(body.choice)
if intent.kind != "business_decision":
    state = simulation_service.restore_state(source, session, pending)
    return _to_response(
        state,
        input_kind=intent.kind,
        input_feedback=intent.feedback,
    )
```

Extract `restore_state(source, session, pending) -> SimulationState` from the existing `SimulationService.resume` state reconstruction so the API does not recreate Pydantic state itself. For an intervention with listed options, exact option matches remain explicit business choices; non-matching text follows the non-advancing path.

- [ ] **Step 4: Update the Vue input handler**

Remove `isQuestion()`. All paused input posts once to `/resume`; after a response with `input_feedback`, append that Chinese feedback as a guide message and do not show “正在将你的决策传达给 Agent”. Keep `/ask/stream` only for completed-session follow-up questions in this module.

- [ ] **Step 5: Run focused API and frontend type checks**

Run: `python -m pytest tests/test_resume_input_intent.py tests/test_checkpoint.py -v`

Expected: PASS with pause-specific tests explicitly setting `PAUSE_EACH_YEAR=1`.

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 6: Review this task**

Verify that non-decision text never invokes `SimulationService.resume`, `SimulationEngine.resume_events`, or an Agent. Verify the frontend no longer owns business intent classification.

### Task 4: Make the SSE Adapter Well-Formed

**Files:**
- Modify: `app/api/stream.py`
- Modify: `tests/test_stream.py`

**Interfaces:**
- HTTP connection placeholder remains `simulation.started` with sequence `0`.
- Every engine event sent through this endpoint is copied with `sequence=event.sequence + 1`.
- Both `ValueError` and unexpected exceptions yield exactly one `simulation.failed` SSE frame.

- [ ] **Step 1: Extend failing stream tests**

```python
def test_stream_validation_error_is_sent_as_terminal_event():
    client = TestClient(app)
    with client.stream("POST", "/api/simulations/stream", json={
        "scenario_id": "milktea_startup",
        "decision_vars": {"budget": -1},
    }) as response:
        events = list(_events(response))
    assert events[-1]["event"] == "simulation.failed"
    assert events[-1]["data"]["payload"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stream.py -v`

Expected: FAIL because the `ValueError` branch constructs `failed` but does not yield it, and the normal stream has duplicate sequence zero.

- [ ] **Step 3: Implement one serialization helper and use it in every branch**

```python
def sse_frame(event: SimulationEvent) -> dict[str, str]:
    return {"event": event.event_type.value, "id": str(event.sequence), "data": event.model_dump_json()}

# Inside the normal loop:
outbound = event.model_copy(update={"sequence": event.sequence + 1})
yield sse_frame(outbound)

# After either exception branch:
yield sse_frame(failed)
```

Set the failed sequence to the next un-emitted sequence, not the last emitted sequence.

- [ ] **Step 4: Run focused stream tests**

Run: `python -m pytest tests/test_stream.py -v`

Expected: PASS; normal event sequences equal `range(len(events))` and invalid input terminates with one failed event.

- [ ] **Step 5: Review this task**

Inspect every `except` branch in `event_generator`; each must yield a frame and no branch may send more than one terminal event.

### Task 5: Module Review Gate

**Files:**
- Modify only files from Tasks 1-4 when fixing review findings.

- [ ] **Step 1: Run the module regression suite**

Run: `python -m pytest tests/test_config_and_loader.py tests/test_input_intent.py tests/test_resume_input_intent.py tests/test_stream.py tests/test_checkpoint.py -v`

Expected: PASS with no external HTTP calls.

- [ ] **Step 2: Run the complete backend suite**

Run: `python -m pytest -q`

Expected: PASS. If a legacy test assumes `PAUSE_EACH_YEAR=1` or `0` implicitly, make the setting explicit in that test; do not change production `.env` to satisfy a test.

- [ ] **Step 3: Review for behavioral defects**

Check these invariants against the implementation and focused test output:

1. A casual/question/ambiguous reply preserves `session_id`, `year`, `world_state`, `timeline`, `phase="paused"`, and never calls an Agent.
2. An exact intervention option remains selectable and continues the engine.
3. The stream has exactly one terminal event and strictly increasing sequences.
4. No test makes network calls while the fixture is active.

- [ ] **Step 4: Fix every confirmed review finding and rerun Steps 1-3**

Run: `python -m pytest -q`

Expected: PASS before marking Module 1 complete.
