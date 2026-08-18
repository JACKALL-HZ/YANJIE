# Simulation Result Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the decorative completed-simulation trend and 3D area with a readable annual result-review surface.

**Architecture:** `ResultJourney.vue` consumes existing `TimelineNode` records and owns annual selection. `WorldStateChart.vue` becomes a single-metric chart that preserves native metric units. `SimView.vue` composes both and removes its direct Three.js timeline dependency.

**Tech Stack:** Vue 3, TypeScript, Tailwind CSS, ECharts, Vite.

## Global Constraints

- Do not change API types, backend state, scoring, SSE, or scenario JSON.
- Keep the Galaxy background; remove only the empty result-area 3D scene.
- Render one-year simulations as a summary, not a line chart.
- Preserve keyboard and touch access to year selection.

### Task 1: Build Result Journey Component

**Files:**
- Create: `frontend/src/components/sim/ResultJourney.vue`
- Modify: `frontend/src/api/types.ts`

- [x] Add a focused result card for each `TimelineNode`, defaulting to the last year.
- [x] Derive result direction, decisive state difference, applied decision label, and optional debate/intervention details from existing timeline data.
- [x] Ensure missing optional data is omitted cleanly.

### Task 2: Make Trends Single-Metric

**Files:**
- Modify: `frontend/src/components/charts/WorldStateChart.vue`

- [x] Accept one selected metric rather than rendering unlike metrics together.
- [x] Render a one-year snapshot instead of a line chart when only one node exists.
- [x] Format tooltip and value labels with scenario units.

### Task 3: Compose And Remove Decorative 3D

**Files:**
- Modify: `frontend/src/views/SimView.vue`

- [x] Remove the direct `Timeline3D` import and 3D result section.
- [x] Add a metric selector and compose `ResultJourney` plus `WorldStateChart` in the completed result area.
- [x] Keep existing `showCharts` lifecycle and result visibility behavior.

### Task 4: Verify

- [x] Run `npm run build` in `frontend`.
- [ ] Start the local frontend if needed and verify the completed-simulation area at desktop and mobile widths.
- [ ] Confirm the result area renders with one, two, and multiple timeline years without overflowing text.
