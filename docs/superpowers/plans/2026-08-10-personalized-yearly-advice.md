# Personalized Yearly Advice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every yearly agent a readable, evidence-aware recommendation while making the personal agent respond to the user's actual profile and current state.

**Architecture:** Extend the existing optional AgentAction presentation contract instead of changing decision-source actions or state transitions. RoleToolRouter performs role-specific retrieval for all four agents and reports evidence state; LlmAgent turns the sanitized context into structured annual advice; AgentPanel renders only those structured fields.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, LangGraph, LangChain, Vue 3, TypeScript, pytest, Vite.

## Global Constraints

- Scenario actions and deterministic engine results remain authoritative.
- New API fields are optional and backward compatible.
- RAG is attempted for all four roles every year; retrieval failure never causes invented citations or blocks scenario-rule analysis.
- Use TDD: write and run a failing test before each implementation task.
- Do not commit because this checkout has no Git repository.

---

### Task 1: Extend the annual advice contract

**Files:**
- Modify: `app/schemas/domain_models.py`
- Modify: `app/agents/narration.py`
- Test: `tests/test_agent_output_guard.py`

**Interfaces:**
- Produces optional `AgentAction.key_factors`, `next_actions`, `uncertainty`,
  `evidence_status`, and `evidence_sources` fields.
- Existing consumers can continue reading `reason`, `recommendation`, and
  `stop_condition` unchanged.

- [ ] Write a failing model test that constructs an AgentAction with the new
  fields and asserts a legacy action omitting them receives safe defaults.
- [ ] Run `pytest tests/test_agent_output_guard.py -q`; expect a validation or
  missing-attribute failure.
- [ ] Add typed optional Pydantic fields with defaults:

```python
key_factors: list[str] = Field(default_factory=list, max_length=3)
next_actions: list[str] = Field(default_factory=list, max_length=3)
uncertainty: str | None = None
evidence_status: Literal["hit", "empty", "error", "disabled"] = "disabled"
evidence_sources: list[str] = Field(default_factory=list, max_length=3)
```

- [ ] Add deterministic Chinese fallback factors and next steps in
  `build_action_presentation()` for stub and legacy actions.
- [ ] Re-run the focused test; expect PASS.

### Task 2: Make four role-specific RAG attempts observable

**Files:**
- Modify: `app/agents/tool_router.py`
- Modify: `app/agents/inner_graph.py`
- Test: `tests/test_role_tool_router.py`

**Interfaces:**
- `RoleToolRouter.build_all()` returns one `search_knowledge` evidence item
  plus supplementary local evidence for every role.
- `AgentContext.rag_status` and `rag_sources` describe the knowledge evidence
  for its own role.

- [ ] Write failing tests asserting four `search_knowledge` calls, distinct
  role focus text, source propagation on hits, and an `empty` status without
  sources when the retriever returns no documents.
- [ ] Run `pytest tests/test_role_tool_router.py -q`; expect assertion failure
  because personal and risk currently do not call knowledge search.
- [ ] Add personal and risk focus entries, reuse `_knowledge_evidence()` for
  all roles, and append local execution/risk evidence after the knowledge
  result. Preserve exception-to-`error` conversion.
- [ ] In `observe()`, pass only that role's evidence status and source labels
  into its AgentContext while retaining all evidence summaries for reasoning.
- [ ] Re-run the focused test; expect PASS.

### Task 3: Generate personal, readable, evidence-aware advice

**Files:**
- Modify: `app/agents/llm_agent.py`
- Modify: `app/agents/base.py`
- Test: `tests/test_agents_llm.py`
- Test: `tests/test_agents_stub.py`

**Interfaces:**
- LLM JSON contains `key_factors`, `next_actions`, `uncertainty`, and the
  existing recommendation, reason, stop condition, confidence, and position.
- `LlmAgent._parse()` copies context evidence status/sources into AgentAction
  and safely normalizes at most three readable items per list.

- [ ] Write a failing personal-agent test with profile text describing limited
  time and cash, an aggressive yearly preference, and an LLM response that
  advises staged validation. Assert the prompt includes the profile and calls
  the preference non-binding; assert result factors and next actions survive.
- [ ] Write a failing empty-RAG test that asserts no source is emitted and the
  answer still parses into a valid AgentAction.
- [ ] Run `pytest tests/test_agents_llm.py tests/test_agents_stub.py -q`;
  expect missing fields and prompt assertions to fail.
- [ ] Update the system JSON protocol and personal strategy wording so the
  preference is evaluated against feasibility. Require two profile/state
  factors when information is present, one measurable next action, one stop
  condition, and one uncertainty. Prohibit external claims when
  `rag_status != "hit"`.
- [ ] Parse and normalize new fields; propagate evidence state from context.
  Extend stub narration with deterministic role-specific factors rather than
  template-only prose.
- [ ] Re-run the focused tests; expect PASS.

### Task 4: Validate advice without forcing agreement

**Files:**
- Modify: `app/agents/judge.py`
- Modify: `app/agents/inner_graph.py`
- Test: `tests/test_judge.py`
- Test: `tests/test_judge_revision.py`

**Interfaces:**
- Judge continues rejecting action/constraint violations.
- A support-versus-oppose difference is retained as user-visible disagreement
  unless it violates a declared hard constraint.

- [ ] Write a failing test where market supports a declared action and risk
  opposes it with a valid stop condition; assert the judge reports the
  disagreement without constraining the next round solely for that reason.
- [ ] Run the two judge test files; expect the current conflict revision path
  to fail the new expectation.
- [ ] Narrow revision routing to invalid actions, hard cash/constraint
  violations, or malformed advice. Keep valid disagreement in JudgeResult
  conflicts for presentation and do not rewrite allowed actions.
- [ ] Re-run the two judge test files; expect PASS.

### Task 5: Render annual advice clearly in the simulation UI

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/sim/AgentPanel.vue`
- Test: `frontend` build

**Interfaces:**
- TypeScript `AgentAction` mirrors optional API advice fields.
- AgentPanel conditionally renders judgment, factors, next actions, stop
  condition, uncertainty, and evidence state/source labels.

- [ ] Add TypeScript fields and update fixture/type checks so a missing field
  remains valid.
- [ ] Add compact sections with role color only for populated content. Render
  `hit` as source labels, `empty` as no external material found, and `error`
  as retrieval temporarily unavailable; do not show raw RAG content.
- [ ] Run `cmd.exe /d /c npm run build` in `frontend`; expect PASS.

### Task 6: Run integration regressions

**Files:**
- Verify: `tests/test_all_scene_yearly_protocol.py`
- Verify: `tests/test_api_endpoints.py`
- Verify: `tests/test_stream.py`
- Verify: `tests/test_e2e_role_debate.py`

- [ ] Run the listed backend tests with `pytest -q --tb=short`; expect PASS.
- [ ] Run the full `pytest -q --tb=short` suite and record any runner timeout
  separately from test failures.
- [ ] Run `python -m pip check` and the frontend production build; expect no
  dependency errors and a successful build.
