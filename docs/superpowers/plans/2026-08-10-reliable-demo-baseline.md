# Reliable Demo Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a test-verified simulation baseline suitable for a credible live demonstration.

**Architecture:** Preserve the existing interactive simulation protocol and deterministic scenario rules. Add pure reconciliation at the `general_startup` boundary, strict SSE/tool contracts, and opt-in provider acceptance checks rather than widening the runtime scope.

**Tech Stack:** Python 3.12, FastAPI, sse-starlette, LangGraph, Pydantic, SQLAlchemy, Chroma, pytest, Vue 3/Vite.

## Global Constraints

- Preserve the decision-source rule: LLM output never directly mutates the world state.
- System and user prompts remain separate; user/tool/RAG text stays sanitized and marked untrusted.
- All changed runtime behavior starts with a failing pytest test.
- Ordinary `pytest` must not invoke a paid external provider.
- Do not commit or push; this workspace has no usable Git repository metadata.

---

### Task 1: Reconcile Agent Actions with the Startup Ledger

**Files:**
- Create: `app/engine/startup_decision.py`
- Modify: `app/engine/engine.py`
- Test: `tests/test_startup_decision.py`

**Interfaces:**
- Consumes: `list[AgentAction]`, `str user_message`, `str yearly_strategy`.
- Produces: `StartupDecision(decision_id: str, reason: str, supporting_actions: list[str])`.

- [ ] **Step 1: Write failing tests**

```python
def test_defensive_agent_consensus_selects_defensive():
    selected = select_startup_decision(actions_for("market.hold", "environment.monitor", "personal.defer", "risk.contain"), "继续经营", "steady")
    assert selected.decision_id == "defensive"

def test_growth_consensus_selects_precision_breakthrough():
    selected = select_startup_decision(actions_for("market.differentiate", "environment.localize", "personal.stabilize", "risk.insure"), "验证后扩大", "steady")
    assert selected.decision_id == "precision_breakthrough"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest tests/test_startup_decision.py -q`

Expected: FAIL because `app.engine.startup_decision` does not exist.

- [ ] **Step 3: Implement the pure selector and attach its audit record to the startup ledger/dashboard**

```python
selected = select_startup_decision(actions, decision_text, yearly_strategy)
ledger = engine.advance(ledger, selected.decision_id)
ledger["history"]["rounds"][-1]["决策依据"] = selected.reason
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_startup_decision.py tests/test_yanjie_engine.py -q`

Expected: PASS.

### Task 2: Restore the HTTP SSE Question Contract

**Files:**
- Modify: `app/api/ask.py`
- Modify: `tests/test_ask.py`

**Interfaces:**
- Produces SSE frames named `token`, `done`, or `error`, each with JSON data.

- [ ] **Step 1: Extend the existing failing stream test**

```python
assert tokens
assert done is True
assert response.headers["content-type"].startswith("text/event-stream")
```

- [ ] **Step 2: Run the focused test and verify the existing failure**

Run: `python -m pytest tests/test_ask.py::TestAskStream::test_stream_endpoint_returns_tokens -q`

Expected: FAIL with an empty token collection.

- [ ] **Step 3: Replace the raw response implementation with the project SSE response pattern**

```python
return EventSourceResponse(event_generator())
```

Use events shaped as `{"event": "token", "data": json.dumps({...})}` and a `done` terminal event.

- [ ] **Step 4: Run focused ask tests**

Run: `python -m pytest tests/test_ask.py -q`

Expected: PASS.

### Task 3: Make MCP Failure Semantics Explicit

**Files:**
- Modify: `app/mcp_server/client.py`
- Modify: `app/agents/tool_router.py`
- Test: `tests/test_mcp_client.py`

**Interfaces:**
- Produces: `McpToolResult(status: Literal["ok", "empty", "error"], content: str, error_code: str | None)`.

- [ ] **Step 1: Write failing client/router tests**

```python
def test_unknown_inline_tool_returns_error_result():
    result = McpToolClient().call("missing", {})
    assert result.status == "error"
    assert result.error_code == "UNKNOWN_TOOL"

def test_stdio_mode_fails_fast():
    with pytest.raises(ValueError, match="inline"):
        McpToolClient(mode="stdio")
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m pytest tests/test_mcp_client.py -q`

Expected: FAIL because the client returns strings and accepts the unsupported mode.

- [ ] **Step 3: Implement typed results and update RoleToolRouter status translation**

```python
result = self._mcp.call("search_knowledge", arguments)
if result.status == "error":
    return AgentEvidence(tool_name="search_knowledge", status="error", summary="知识库本轮不可用，已按场景规则继续分析。")
```

- [ ] **Step 4: Run MCP and agent-context tests**

Run: `python -m pytest tests/test_mcp.py tests/test_mcp_client.py tests/test_agent_decision_context.py -q`

Expected: PASS.

### Task 4: Enforce Explicit State Persistence Boundaries

**Files:**
- Modify: `app/engine/engine.py`
- Modify: `app/core/config.py`
- Modify: `tests/test_checkpoint.py`
- Modify: `tests/test_stream.py`

**Interfaces:**
- `SimulationEngine._build_checkpointer()` raises a configuration error when a PostgreSQL saver is requested but unavailable.
- `iter_events()` contains only the interactive create-and-pause protocol.

- [ ] **Step 1: Add failing tests for PostgreSQL dependency and the initial event sequence**

```python
def test_postgres_checkpointer_requires_installed_saver(monkeypatch):
    with pytest.raises(RuntimeError, match="langgraph-checkpoint-postgres"):
        SimulationEngine(source, settings=postgres_settings)

def test_initial_event_sequence_stops_after_decision_pause():
    assert [event.event_type for event in engine.iter_events(vars)] == [EventType.SIMULATION_STARTED, EventType.SIMULATION_PAUSED]
```

- [ ] **Step 2: Run focused tests and verify the PostgreSQL test fails**

Run: `python -m pytest tests/test_checkpoint.py tests/test_stream.py -q`

Expected: FAIL because unavailable PostgreSQL currently falls back to memory.

- [ ] **Step 3: Remove unreachable legacy loop and replace silent PostgreSQL fallback with a descriptive error**

```python
except ImportError as exc:
    raise RuntimeError("CHECKPOINTER_URL uses PostgreSQL but langgraph-checkpoint-postgres is not installed") from exc
```

- [ ] **Step 4: Run focused persistence tests**

Run: `python -m pytest tests/test_checkpoint.py tests/test_stream.py tests/test_pause_protocol.py -q`

Expected: PASS.

### Task 5: Add Opt-In Live Acceptance Checks and Final Verification

**Files:**
- Create: `tests/test_live_acceptance.py`
- Modify: `pyproject.toml`
- Modify: `docs/2026-08-10-推演系统技术审查与答辩说明.md`

**Interfaces:**
- Live tests run only when `YANJIE_RUN_LIVE_TESTS=1`; otherwise pytest marks them skipped.

- [ ] **Step 1: Write skipped-by-default live test cases**

```python
@pytest.mark.live
def test_live_rag_and_agent_round_reports_sources():
    pytest.skip("set YANJIE_RUN_LIVE_TESTS=1 to run provider acceptance")
```

- [ ] **Step 2: Run normal pytest and verify live tests do not call providers**

Run: `python -m pytest tests/test_live_acceptance.py -q`

Expected: SKIPPED.

- [ ] **Step 3: Implement opt-in provider checks with request limits and redacted evidence**

```python
if os.getenv("YANJIE_RUN_LIVE_TESTS") != "1":
    pytest.skip("live provider acceptance is disabled")
```

- [ ] **Step 4: Run all local verification and one controlled live suite**

Run: `python -m pytest`

Expected: all local tests pass, live tests skip by default.

Run: `$env:YANJIE_RUN_LIVE_TESTS='1'; python -m pytest tests/test_live_acceptance.py -q`

Expected: provider evidence passes or reports a provider-specific failure without exposing credentials.

Run: `npm run build`

Expected: Vite production build passes.
