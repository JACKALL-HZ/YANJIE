# Horizon Control and Catalogue Expansion Plan

**Goal:** Make planned years a user-controlled review point instead of an automatic timeout, and let each declared scenario decision produce its own deterministic recommendation branches.

## Tasks

1. Expand the milk-tea decision catalogue for local collaboration and marketing-budget increases; classify declared catalogue keywords as business decisions and test that each returns three distinct previews.
2. Add a typed `horizon_review` phase and planned-year snapshot. Reaching the chosen horizon pauses with Chinese controls for extend one year, extend three years, or finalize; only finalization calculates a timeout result and score.
3. Render branch labels rather than internal IDs in chat, and present horizon controls with their remaining-year context.
4. Add a Chinese output guard for live LLM actions: reject internal metric names and unexplained English terms, then fall back to a role-specific Chinese explanation when the model response is not suitable.
5. Run focused tests, frontend build, complete backend suite, and review state persistence and agent-context invariants.
