# Security Boundary Hardening Design

## Goal

Require an authenticated user for all simulation and LLM-consuming operations while preserving public health, authentication, and scenario browsing endpoints.

## Decisions

- Simulation creation, comparison, streaming, resume, session history, diary, reports, follow-up questions, and decision breakdown require a valid JWT.
- The browser no longer sends or stores a guest identity. Unauthenticated users are redirected to login before entering protected workflows.
- CORS defaults to the two local Vite origins. Wildcard origins are rejected outside explicit local development configuration.
- JWT configuration fails closed for an absent or known development secret. Access tokens default to one hour.
- MCP is documented and launched only as a local stdio server. It does not claim unsupported HTTP token authentication.
- API and SSE responses use stable public error messages; detailed failures remain in server logs.
- Passwords longer than bcrypt's 72 UTF-8 byte input limit are rejected, avoiding credential aliasing.
- Agent user text and retrieved text are delimited and sanitised as untrusted data before model calls.

## Compatibility

Existing logged-in workflows retain their routes, payloads, and response formats. Existing anonymous sessions become inaccessible, which is an intentional product decision. Public scenario discovery and login/register remain available.

## Verification

Regression tests cover unauthenticated rejection, authenticated execution, safe configuration defaults, trusted-proxy forwarding, password byte limits, error redaction, and prompt isolation. The frontend build is run after TypeScript route/header changes.
