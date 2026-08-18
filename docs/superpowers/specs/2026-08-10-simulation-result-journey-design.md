# Simulation Result Journey Design

## Goal

Replace the decorative trend chart and empty Three.js branch stage with a compact result-review surface that lets a user understand what happened in each simulated year.

## Scope

Only the completed-simulation result area in `frontend/src/views/SimView.vue` changes. Simulation state, API payloads, scoring, SSE, history, and scenario rules remain unchanged.

## Chosen Direction

Use a two-part `结果复盘` section:

1. **Year result rail**
   - One selectable outcome card per `TimelineNode`.
   - Each card shows the year, decision direction, a positive/negative/neutral result state, and the most meaningful state delta.
   - The selected year expands into a readable result summary: applied agent recommendations, state deltas, intervention outcome, and judge summary when present.
   - The last year is selected by default. Cards are buttons and remain usable on touch devices and keyboards.

2. **Single-metric trend panel**
   - A segmented metric selector renders one metric at a time, preserving its native unit and scale.
   - The first metric is selected by default. With one simulation year, the chart is replaced by a result summary rather than a meaningless one-point line.
   - Tooltip values use the scenario-provided label and unit. The chart is secondary to the year result rail.

## Data Mapping

- `TimelineNode.year`: result card order and label.
- `TimelineNode.world_state`: selected metric values and current result snapshot.
- `TimelineNode.state_diff`: result direction, delta badges, and decisive change.
- `TimelineNode.agent_actions`: year decision summary.
- `TimelineNode.interventions` and `TimelineNode.debate`: contextual outcome details when available.
- Existing `state_metrics` definitions: metric label, source field, and unit.

## UI Direction

Keep the star field as the application environment, but remove the isolated glass theatre and Three.js grid. The result area uses restrained operational panels, cyan for progress, coral for deterioration, and warm yellow for unresolved or mixed outcomes. Decorative animation is limited to selection feedback and chart transitions.

## Component Boundary

- Replace `WorldStateChart.vue` with a single-metric chart API that receives the current selection.
- Add `ResultJourney.vue` for yearly card selection and the expanded result summary.
- Remove `Timeline3D.vue` from `SimView.vue`; do not alter the background Galaxy component.
- `SimView.vue` owns the selected metric and passes existing timeline data through props.

## Empty And Edge States

- No timeline: hide the whole result-review section.
- One timeline node: render the selected annual result summary and a metric snapshot, without a line chart.
- Missing state diff or optional debate/intervention data: omit that row rather than displaying placeholders.

## Verification

- Add focused Vitest-equivalent static/component tests if the project gains a frontend test runner; currently verify with TypeScript build and browser screenshots at desktop and mobile viewports.
- Run existing backend tests unchanged because the data contract is not modified.
- Confirm no Three.js import remains in `SimView.vue` and the completed result remains readable with one, two, and multiple years.
