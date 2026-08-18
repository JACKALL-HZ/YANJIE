# Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the reviewed request-boundary and RAG reliability defects without changing simulation, scoring, timeline, or SSE contracts.

**Architecture:** Enforce the body limit at the ASGI receive boundary. Thread the existing RAG setting into the role router and MCP tool, preserve distinct RAG evidence states, and add seed documents for every shipped scenario before re-ingesting Chroma.

**Tech Stack:** FastAPI/Starlette, Pydantic, Chroma, pytest.

## Global Constraints

- Keep scenario rules and scoring untouched.
- Preserve the current four-agent response schema and SSE payloads.
- Use source-labelled, non-fabricated seed knowledge.

### Task 1: Add Regression Tests

**Files:**
- Modify: `tests/test_security_hardening.py`
- Modify: `tests/test_role_tool_router.py`
- Modify: `tests/test_mcp.py`
- Modify: `tests/test_kb.py`

- [x] Write tests for chunked body overflow, disabled RAG, unavailable RAG, MCP configuration, and scenario seed coverage.
- [x] Run the focused tests and confirm they fail on the reviewed defects.

### Task 2: Restore Boundary And RAG Semantics

**Files:**
- Modify: `app/middleware/body_limit.py`
- Modify: `app/schemas/domain_models.py`
- Modify: `app/agents/tool_router.py`
- Modify: `app/agents/inner_graph.py`
- Modify: `app/engine/engine.py`
- Modify: `app/mcp_server/tools.py`

- [x] Replace header-only body validation with bounded ASGI receive handling.
- [x] Preserve `disabled`, `empty`, and `error` as distinct evidence states.
- [x] Ensure `RAG_ENABLED=0` blocks role and MCP retrieval before any provider request.
- [x] Run the focused tests and confirm they pass.

### Task 3: Cover Shipped Scenarios

**Files:**
- Create: `文档种子数据/startup/general_startup/01-通用创业验证与现金流框架.md`
- Create: `文档种子数据/startup/saas_startup/01-SaaS创业验证与现金流框架.md`
- Create: `文档种子数据/startup/retail_store/01-零售门店验证与现金流框架.md`

- [x] Add clearly labelled editorial decision frameworks for the missing scenarios.
- [x] Re-ingest the seed corpus into Chroma.
- [x] Verify a real query returns a source for each newly covered scenario.

### Task 4: Regression Verification

- [x] Run RAG, middleware, agent, API, and yearly-protocol regression tests.
- [x] Run the frontend production build.
