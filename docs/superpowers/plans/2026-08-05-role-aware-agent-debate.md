# Role-Aware Agent Debate Implementation Plan

> **For agentic workers:** Execute this plan inline with `executing-plans`. The repository has no Git workflow; do not create commits.

**Goal:** Make four scenario-aware Agents independently ground their opinions in role-specific tools, visibly respond to the user's latest decision, and present meaningful disagreements without increasing every simulation round into an uncontrolled debate.

**Architecture:** A role-tool router creates one bounded evidence bundle for each Agent. The inner graph gives every Agent the same decision brief plus its own evidence, records a structured position alongside its action, and persists the Judge's conflict result as a debate record. The UI renders four independent positions and a compact disagreement panel only when the Judge detects a material conflict or the user submits a high-impact decision.

**Tech Stack:** FastAPI, Pydantic, LangGraph, local MCP tools, Chroma/BM25 RAG, Vue 3, TypeScript, Vitest, pytest.

## Global Constraints

- Scenario JSON remains the source of truth for permitted actions and state effects.
- External knowledge is treated as untrusted text, sanitized before LLM input, and retains source metadata.
- Tool access is allowlisted by Agent role; a failed tool returns evidence status instead of blocking simulation.
- One round may issue at most two knowledge retrieval calls and two deterministic local analyses; no web search is added by default.
- A visible debate is generated only for user decisions classified as high impact or a Judge conflict; it must be limited to one summarized exchange record.
- All user-facing labels are Chinese; internal IDs remain stable snake_case values.
- Tests are written before implementation and must pass before proceeding to the next task.

---

### Task 1: Add visible decision, evidence, and debate contracts

**Files:**
- Modify: `app/schemas/domain_models.py`
- Modify: `app/agents/contracts.py`
- Modify: `app/schemas/events.py`
- Modify: `frontend/src/api/types.ts`
- Test: `tests/test_agent_debate_contracts.py`

**Interfaces:**
- `AgentEvidence(tool_name, summary, sources, status)` is attached to exactly one Agent action.
- `AgentAction.position` is one of `support`, `oppose`, `conditional`, or `neutral`.
- `DebateRecord(trigger, conflicts, recommendations, participants)` is stored on the timeline node after Judge evaluation.

- [ ] Write a failing Pydantic round-trip test for an action containing role evidence and a timeline node containing a debate record.
- [ ] Add the strict Pydantic models and optional fields with backwards-compatible defaults.
- [ ] Extend event/API TypeScript contracts so SSE and history preserve the fields.
- [ ] Run `pytest -q tests/test_agent_debate_contracts.py` and the affected schema tests.

### Task 2: Add role-specific MCP tool routing

**Files:**
- Create: `app/agents/tool_router.py`
- Modify: `app/mcp_server/tools.py`
- Modify: `app/mcp_server/client.py`
- Modify: `app/agents/inner_graph.py`
- Test: `tests/test_role_tool_router.py`

**Interfaces:**
- `RoleToolRouter.build_evidence(agent_id, state, decision_brief, profile_summary) -> AgentEvidence`.
- Market and environment use distinct scene-filtered `search_knowledge` queries.
- Personal calls `assess_execution_capacity`; risk calls `run_risk_stress_test`.
- MCP failures return `status="error"` evidence and do not raise into the simulation graph.

- [ ] Write failing tests asserting each of the four roles calls only its allowlisted tool and receives role-specific query/context.
- [ ] Add deterministic personal-capacity and risk-stress MCP tools with concise Chinese output and no external dependency.
- [ ] Add the two tools to the inline MCP client allowlist.
- [ ] Implement the router with a two-retrieval budget and source extraction.
- [ ] Replace the coordinator's shared RAG context construction with per-Agent evidence bundles.
- [ ] Run `pytest -q tests/test_role_tool_router.py tests/test_agent_decision_context.py tests/test_mcp.py`.

### Task 3: Generate distinct positions and persist Judge disagreements

**Files:**
- Modify: `app/agents/llm_agent.py`
- Modify: `app/agents/base.py`
- Modify: `app/agents/judge.py`
- Modify: `app/agents/inner_graph.py`
- Modify: `app/engine/models.py`
- Modify: `app/engine/reducers.py`
- Test: `tests/test_agent_debate.py`

**Interfaces:**
- Every Agent receives the raw `decision_brief`; Personal also receives the profile summary.
- LLM output schema contains `position` in addition to action/reason/confidence.
- Stub output derives a deterministic, role-distinct position for offline tests.
- `AgentCoordinator` creates a `DebateRecord` from Judge conflicts and the final actions, then the reducer stores it on the completed year.

- [ ] Write failing tests proving all four contexts receive the latest decision, a risk-versus-market conflict yields one visible debate record, and no conflict yields no record.
- [ ] Extend structured LLM parsing and prompts to require a position tied to the latest decision and evidence.
- [ ] Update stub generation and Judge result handling without changing action-effect selection.
- [ ] Persist the debate record through timeline snapshots, sessions, reports, and API responses.
- [ ] Run `pytest -q tests/test_agent_debate.py tests/test_judge.py tests/test_judge_revision.py tests/test_engine_persist.py`.

### Task 4: Render role evidence and visible disagreement

**Files:**
- Create: `frontend/src/components/sim/DebatePanel.vue`
- Modify: `frontend/src/components/sim/AgentPanel.vue`
- Modify: `frontend/src/views/SimView.vue`
- Modify: `frontend/src/api/types.ts`
- Test: `frontend/src/components/sim/__tests__/AgentPanel.spec.ts`
- Test: `frontend/src/components/sim/__tests__/DebatePanel.spec.ts`

**Interfaces:**
- Agent cards show Chinese position, role evidence status, and cited sources.
- `DebatePanel` receives a `DebateRecord | null` and renders nothing when absent.
- The chat timeline adds a concise disagreement summary once per yearly record; it never fabricates a dialogue not present in the debate record.

- [ ] Write failing component tests for role-specific labels, source display, and conditional debate rendering.
- [ ] Add the compact debate panel with conflict/recommendation summaries and participant positions.
- [ ] Replace startup-only focus metric labels with domain-aware Chinese metric mappings.
- [ ] Wire the latest timeline node into the panel and chat message flow.
- [ ] Run `npm.cmd run test -- --run` for the component tests and `npm.cmd run build`.

### Task 5: Enable the configured MCP path and verify end-to-end behavior

**Files:**
- Modify: `.env` (only `MCP_ENABLED`)
- Modify: `tests/test_graph_and_engine.py`
- Modify: `tests/test_session_report_detail.py`
- Test: `tests/test_e2e_role_debate.py`

**Interfaces:**
- Development runtime uses the inline MCP client when RAG is enabled.
- An end-to-end simulation retains four role-specific actions, evidence, and a debate record when a conflict is triggered.

- [ ] Write a failing end-to-end test with a deterministic conflict and assert role tool evidence survives in the returned timeline and session report.
- [ ] Set `MCP_ENABLED=true` without changing credentials or enabling web search.
- [ ] Run the focused end-to-end test, then `pytest -q` and `npm.cmd run build`.
- [ ] Verify `GET /api/health` on the running development backend after reload.

## Self-Review

- The plan covers tool routing, Agent reasoning contracts, Judge persistence, frontend visibility, runtime configuration, and regression coverage.
- No task adds unconstrained external browsing or allows an LLM to alter scenario effects.
- Tool records are evidence, not prompt instructions, and all UI strings remain Chinese.
