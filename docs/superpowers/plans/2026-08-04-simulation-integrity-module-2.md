# Decision Preview and Agent Diversity Module Plan

**Goal:** Turn a business decision into three deterministic, read-only previews before the timeline advances, while ensuring all four agents analyse the same latest decision with role-specific, plain-Chinese reasoning and confidence that reflects uncertainty.

**Architecture:** Scenarios remain the source of truth for action effects. A new decision catalogue in the milk-tea scenario maps a normalized decision to its user proposal, expert recommendation, and low-cost alternative. Pure engine functions derive comparable next-year preview metrics without persisting or mutating `SimulationState`. Agent contexts receive the normalized proposal plus frozen profile data; a deterministic stub narrator enforces role-specific Chinese output for tests and local development. The API exposes a pending preview, then applies only the user-selected branch on resume.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, LangGraph, pytest, Vue 3, TypeScript.

**Completion (2026-08-04):** Tasks 1-5 are complete. Module regression passed (`24 passed`) and the frontend production build passed. The complete backend suite still has the same four pre-existing failures in session ownership/listing, diary filtering, and frozen-profile persistence; they are intentionally deferred to the history and anonymous-identity module.

## Constraints

- Use `python -m pytest`, with `LLM_USE_STUB=1` under tests.
- Add failing tests before each implementation change.
- No action effect, branch metric, or scenario fact may come from the LLM.
- Agent-visible text is plain Chinese. It may not expose snake_case fields, English action IDs, trailing underscores, or unexplained shorthand.
- A preview is read-only. The current year, world state, timeline, and persisted session must remain unchanged until a branch is selected.
- Four agents must receive the same latest proposal, but their output must use distinct role dimensions.

## Task 1: Decision Catalogue and Preview Contracts

**Files:**
- Modify: `app/schemas/decision_source.py`
- Modify: `app/engine/models.py`
- Modify: `scenarios/milktea_startup.json`
- Create: `tests/test_decision_preview.py`

1. Write failing tests that load `milktea_startup` and validate a `celebrity_endorsement` decision catalogue entry with exactly three declared branches: `user_proposal`, `expert_recommendation`, and `low_cost_alternative`.
2. Add strict Pydantic schemas for decision catalogue entries and immutable preview response models. Each branch must declare a Chinese label, an action ID, a Chinese explanation, and effects that reference declared world-state metrics only.
3. Add the milk-tea celebrity endorsement, differentiation recommendation, and low-cost co-branding actions with deterministic effects and Chinese labels.
4. Run `python -m pytest tests/test_decision_preview.py -v`.

## Task 2: Read-Only Deterministic Preview Engine

**Files:**
- Create: `app/engine/decision_preview.py`
- Modify: `app/engine/reducers.py` only if a shared pure effect helper is needed
- Modify: `tests/test_decision_preview.py`

1. Add failing tests proving a celebrity proposal returns all three comparable previews, leaves the input `SimulationState` byte-for-byte unchanged, and produces a materially different cash-flow/risk result for the high-cost user branch.
2. Implement pure mapping and preview functions. Unknown proposals must return a typed clarification result, never invent a branch or apply an effect.
3. Add concise Chinese metric labels and threshold narration for preview summaries, including the `145` versus `150-350` case as “略低于下限 5 杯”.
4. Run `python -m pytest tests/test_decision_preview.py -v`.

## Task 3: Agent Decision Context and Chinese Role Narration

**Files:**
- Modify: `app/agents/contracts.py`
- Modify: `app/agents/base.py`
- Modify: `app/agents/inner_graph.py`
- Create: `app/agents/narration.py`
- Create: `tests/test_agent_decision_context.py`

1. Write failing tests asserting all four `AgentContext` values receive the same latest proposal and frozen profile, and that stub reasons are Chinese, contain the decision label, and differ across market, environment, personal, and risk roles.
2. Add a typed latest-decision field to `AgentContext`. Pass it to every agent in `observe`; do not limit it to personal/risk.
3. Replace generic English stub reasons and fixed `0.5` confidence with deterministic Chinese role narration and bounded confidence derived from profile completeness, proposal uncertainty, and role-specific exposure.
4. Run `python -m pytest tests/test_agent_decision_context.py tests/test_agents_and_validation.py -v` (or the matching existing agent test file if its local name differs).

## Task 4: Preview API and Branch Selection

**Files:**
- Modify: `app/schemas/api.py`
- Modify: `app/api/simulation.py`
- Modify: `app/services/simulation_service.py`
- Modify: `app/engine/engine.py`
- Create: `tests/test_decision_preview_api.py`

1. Write failing API tests that submit “请明星代言” to a paused session, receive three previews without changing year/world state, then choose one branch and verify only that branch can advance exactly one year.
2. Introduce a typed pending-decision preview state. Persisting its history is deliberately deferred to the history module; this task only holds it in the active session flow without mutating the main simulation before selection.
3. Keep exact existing intervention choices working and preserve the module-1 casual/question guard.
4. Run `python -m pytest tests/test_decision_preview_api.py tests/test_resume_input_intent.py tests/test_checkpoint.py -v`.

## Task 5: Frontend Preview and Module Review

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/views/SimView.vue`
- Modify only module files when resolving review findings.

1. Render a compact Chinese comparison panel above agent detail: cash reserve, daily customer flow, monthly profit, risk level, and worst-case loss. Do not render raw field names or English IDs.
2. Offer explicit selection controls for the three branches. A preview must remain visible until a branch is selected.
3. Run `npm.cmd run build`.
4. Run `python -m pytest tests/test_decision_preview.py tests/test_agent_decision_context.py tests/test_decision_preview_api.py tests/test_resume_input_intent.py tests/test_stream.py -v`, then `python -m pytest -q`.
5. Review the mutation boundary, agent-context coverage, Chinese-output validator, and the existing four history/profile failures before marking the module complete.
