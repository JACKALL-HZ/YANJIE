# Reliable Demo Baseline Design

## Goal

Turn the existing MVP into a credible, stable demonstration baseline: agent recommendations must agree with quantitative startup results, streaming must honor its SSE contract, tools must expose reliable outcomes, and the system must have bounded live-provider acceptance checks.

## Scope

This iteration changes only user-facing correctness and reliability boundaries:

1. Make `general_startup` select a deterministic ledger decision from the four validated AgentAction records, with explicit user exit intent as the only override.
2. Repair the SSE question stream contract and remove obsolete unreachable batch execution from the interactive simulation protocol.
3. Replace MCP empty-string failure signaling with structured tool outcomes while retaining the supported inline transport.
4. Make the configured checkpointer behavior explicit and protect production configuration from silent PostgreSQL checkpoint fallback.
5. Add an opt-in live acceptance suite for LLM, embedding, reranking, Tavily, RAG, and the complete authenticated HTTP resume flow.

Long-term AgentMemoryStore retrieval/writeback and classify_scene collection routing are intentionally excluded. They will remain accurately documented as infrastructure not yet used by the runtime.

## Architecture

### Startup decision reconciliation

`SimulationEngine` will call a new pure selector after the inner graph validates the four actions. The selector receives the user decision text, yearly strategy, and the action list and returns a ledger decision ID plus an auditable reason.

Explicit user exit/transfer language returns `transfer_or_close`. Otherwise, the selector scores the validated role actions: `risk.contain` and `personal.defer` favor `defensive`; `market.differentiate` plus `environment.localize` favors `precision_breakthrough`; remaining combinations select `steady_growth`. `yearly_strategy` only breaks ties. The selected source and role actions are persisted in the startup ledger/dashboard so the displayed narrative and numeric result can be reconciled.

### Streaming and session protocol

The product protocol remains interactive: create a session, pause for the first annual decision, resume one year, then pause/complete. The unreachable pre-existing batch loop will be removed. `/ask/stream` will use the same SSE implementation family as the simulation stream, emit typed JSON events, and be verified through a TestClient stream consumer.

### MCP results

Inline MCP remains the supported app transport. `McpToolClient.call()` will return a typed result containing `status`, `content`, and optional `error_code`, rather than conflating failures with an empty result. `RoleToolRouter` will translate those statuses to `AgentEvidence` and keep conservative local fallbacks. The unsupported stdio mode will fail fast with a clear configuration error instead of pretending to work.

### Configuration and live acceptance

The default in-process checkpoint remains `memory`; session recovery continues to use SQLite business state. PostgreSQL checkpoint configuration will raise a startup error when the optional saver is unavailable. Live tests will be explicitly enabled with `YANJIE_RUN_LIVE_TESTS=1`; normal `pytest` never invokes paid providers.

## Acceptance Criteria

- A startup scenario with different validated AgentAction combinations produces different ledger decisions and materially different quantitative paths.
- User exit intent still selects closure, while strategy breaks only equivalent action scores.
- The HTTP ask stream supplies at least one `token` event and a terminal `done` event.
- No unreachable legacy loop remains after initial session pause.
- Inline MCP can distinguish `ok`, `empty`, and `error`; unsupported stdio fails immediately.
- PostgreSQL checkpoint configuration cannot silently fall back to memory.
- Full local pytest is green, frontend production build succeeds, and opt-in live checks report provider-specific evidence without secrets.
