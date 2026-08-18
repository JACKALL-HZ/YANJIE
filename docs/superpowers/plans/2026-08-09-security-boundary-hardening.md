# Security Boundary Hardening Implementation Plan

> **For agentic workers:** Execute inline with a review checkpoint after each task. No commit is created because this checkout has no Git worktree and repository rules prohibit unsolicited commits.

**Goal:** Close anonymous access to simulation and LLM endpoints, fail closed on unsafe security configuration, and remove error and credential handling weaknesses.

**Architecture:** FastAPI dependencies become the single authentication boundary for all costly or session-bound routes. Configuration and middleware enforce safe startup, CORS, and proxy behavior. The Vue client removes anonymous identity propagation and redirects users before protected requests.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, PyJWT, bcrypt, Vue 3, TypeScript, pytest.

## Global Constraints

- Preserve the existing authenticated API paths, request schemas, and response schemas.
- Do not reveal credentials or raw exception text to clients.
- Use TDD: add a failing regression test before each implementation change.
- Do not commit or push changes.

---

### Task 1: Authentication and CORS Boundary

**Files:**
- Modify: `app/api/dependencies.py`, `app/api/assistant.py`, `app/api/simulation.py`, `app/api/stream.py`, `app/api/ask.py`, `app/api/sessions.py`, `app/api/diary.py`, `app/api/report.py`, `app/middleware/cors.py`
- Modify: `frontend/src/api/client.ts`, `frontend/src/api/sse.ts`, `frontend/src/router/index.ts`
- Test: `tests/test_auth.py`, `tests/test_session_isolation.py`, `tests/test_api.py`

- [ ] Add failing tests proving unauthenticated simulation and breakdown requests return 401 while authenticated requests retain success behavior.
- [ ] Require `get_current_user` for protected endpoints and remove guest identity headers from the frontend request helpers.
- [ ] Restrict CORS defaults to local development origins and reject wildcard production configuration.
- [ ] Run the focused auth and API tests.

### Task 2: Configuration, Rate Limits, and MCP Surface

**Files:**
- Modify: `app/core/config.py`, `app/middleware/rate_limit.py`, `app/mcp_server/server.py`, `.env.example`
- Test: `tests/test_config_and_loader.py`, `tests/test_mcp.py`

- [ ] Add failing tests for rejecting absent/default JWT secrets, a one-hour default token lifetime, and ignoring forwarded headers from untrusted clients.
- [ ] Make JWT configuration fail closed, allow forwarded IP resolution only for configured trusted proxies, and remove unsupported MCP HTTP-auth claims.
- [ ] Run focused configuration, rate-limit, and MCP tests.

### Task 3: Error, Password, and Prompt Boundaries

**Files:**
- Modify: `app/api/ask.py`, `app/services/ask_service.py`, `app/core/security.py`, `app/api/auth.py`, `app/agents/llm_agent.py`
- Test: `tests/test_auth.py`, `tests/test_agent_output_guard.py`, `tests/test_ask.py`

- [ ] Add failing tests for public error redaction, over-72-byte password rejection, and sanitised agent prompt content.
- [ ] Replace raw exception responses with stable messages, reject oversized UTF-8 passwords, and treat user/RAG text as delimited untrusted data.
- [ ] Run focused tests.

### Task 4: Dependency and Frontend Verification

**Files:**
- Modify: `pyproject.toml`
- Verify: `python -m pip check`, `python -m pytest`, `cmd.exe /d /c npm run build`, `cmd.exe /d /c npm audit --package-lock-only --offline`

- [ ] Tighten the LangChain package compatibility ranges.
- [ ] Create or use a project-local virtual environment for verification rather than the incompatible global interpreter.
- [ ] Run backend tests, frontend build, dependency checks, and the offline frontend audit.
