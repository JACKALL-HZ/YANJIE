# Authentication and Boundary Hardening Design

## Goal

Tighten the authentication and request-boundary protections discovered in the
core-code review while preserving the simulation engine, scenario data, scoring,
and agent decision contracts. Login and registration access tokens will expire
after one day.

## Considered Approaches

1. Keep the existing stateless JWT model, reduce its lifetime to 24 hours, and
   return explicit expiry metadata. This is the selected approach because it is
   backward compatible for existing callers and does not introduce database
   state or a frontend refresh-token flow.
2. Add short-lived access tokens plus refresh tokens. This gives finer session
   control but requires token persistence, revocation, UI refresh behavior, and
   migration work. It is out of scope for the targeted bug fix.
3. Keep the current seven-day token and only document the expiry. This leaves
   the requested session-duration change unmet and does not make expiry visible
   to clients.

## Authentication Contract

- `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to `1440` (one day). A deployment can
  override it with an integer environment value.
- JWT payloads retain `sub`, `username`, `iat`, and `exp`. `exp` is generated
  from the configured duration and is verified when a protected endpoint reads
  the token.
- Registration and login responses retain `access_token`, `token_type`, and
  `user`, and add `expires_at` (UTC ISO-8601) plus `expires_in` (seconds).
  Adding fields is response-compatible for current clients.
- Expired, malformed, wrongly signed, or userless tokens receive the existing
  generic `401 UNAUTHORIZED` response. The API does not expose token parsing
  failures.
- Registration checks usernames unconditionally and checks email only when an
  email was supplied. This permits multiple accounts without email while still
  rejecting duplicate real emails.
- Usernames and non-null emails receive database unique indexes. Startup
  migration creates these indexes only after checking for existing duplicates;
  a conflicting legacy database fails clearly rather than silently deleting or
  changing user records. The application also converts unique-constraint races
  into the existing `409 USERNAME_TAKEN` or `EMAIL_TAKEN` response.

## Request and Prompt Boundaries

- Replace the header-only body size check with an ASGI receive wrapper that
  counts every received body chunk. Requests that exceed `BODY_MAX_BYTES` are
  rejected with the existing `413 PAYLOAD_TOO_LARGE` response whether or not
  they provide `Content-Length`. Requests with an oversized declared header are
  still rejected before reading the body.
- Rate limiting uses the direct peer address by default. `X-Forwarded-For` is
  used only when `TRUST_PROXY_HEADERS=1`, for deployments where the reverse
  proxy is controlled and overwrites that header.
- All user-controlled text inserted into an LLM prompt, including profile
  summaries, the annual user message, and latest decision text, passes through
  `sanitize_user_input` before prompt construction. Scenario-defined facts and
  deterministic simulation values remain unchanged.
- SSE follow-up failures are logged server-side and emit a stable generic
  client message instead of exception text.

## MCP Protection

- `MCP_TOKEN`, when configured, is enforced through FastMCP's supported bearer
  token verifier rather than the existing no-op per-tool function.
- The verifier accepts a constant-time matched bearer token and returns the
  minimum required MCP access-token metadata. Missing or invalid bearer tokens
  are rejected by FastMCP before a tool runs. Unconfigured `MCP_TOKEN` retains
  local stdio/development behavior.
- This changes the documented HTTP authentication header to
  `Authorization: Bearer <MCP_TOKEN>`; the server no longer claims support for
  the unenforced `X-MCP-Token` header.

## Configuration Safety

- A production-mode deployment must provide a non-default `JWT_SECRET` and an
  `API_KEY`. Local/test behavior remains available only through an explicit
  development environment setting, so current automated tests and offline MVP
  workflow continue to operate.
- `.env.example` documents `JWT_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES=1440`,
  `API_KEY`, `MCP_TOKEN`, and `TRUST_PROXY_HEADERS` without containing secret
  values.

## Error Handling and Compatibility

The simulation API, engine state, scenario JSON, scoring, and Agent action
schema are out of scope. Existing status codes and structured error codes are
retained. The only intentional public-response additions are optional expiry
metadata on successful auth responses; callers that ignore unknown JSON fields
continue to work unchanged.

## Test Strategy

- Add JWT unit tests proving the configured expiry is one day, expired tokens
  fail validation, and auth responses expose matching expiry metadata.
- Add API regression tests for two email-less registrations, duplicate username
  and email handling, and database-race conversion where practical.
- Add middleware tests for chunked bodies without `Content-Length` and proxy
  header trust being opt-in.
- Add prompt-construction tests with instruction-like profile, message, and
  decision text.
- Add SSE tests proving internal exception strings do not reach clients.
- Add MCP verifier tests for missing, invalid, and valid bearer tokens.

## Non-Goals

- No refresh-token, logout revocation list, password reset, or multi-device
  session management.
- No changes to simulation results, decision variables, LLM routing policy,
  scenarios, or scoring formulas.
- No source-control commit or push; the workspace does not expose a usable Git
  worktree and repository instructions prohibit unsolicited commits.
