# Deep Space Ship Loader Design

## Goal

Replace the current connection overlay with a clear, high-fidelity deep-space ship sequence that communicates the simulation engine is working without changing simulation behavior or creating artificial progress.

## Scope

Only `frontend/src/components/motion/ShipLoader.vue` changes. It remains mounted only while `sim.phase === 'connecting'` in `SimView.vue`. SSE flow, Pinia state, routes, scenario data, and all business copy outside the loader remain unchanged.

## Chosen Direction

Use a near-field vector spacecraft in a sharp deep-space scene.

- The vessel has a segmented hull, canopy, stabilizer fins, twin engines, and a directional navigation light.
- A low-density star field and faint navigation lanes establish depth without using a blurred image backdrop.
- The sequence enters in three visual phases, driven by elapsed display time only:
  1. `systems`: engines charge and navigation instruments initialize.
  2. `analysis`: the ship holds a controlled cruise with a live engine plume while the agent analysis message changes.
  3. `transit`: the scene moves into a sustained jump-speed flight state for connections that take longer than the opening sequence.
- Labels report real processing stages, not numerical progress. They rotate through world-state setup, multi-agent analysis, and risk/branch validation.
- The overlay remains non-interactive and includes `aria-live` / `aria-busy` semantics.

## Visual Rules

- Keep the star field sharp. Do not use the existing image backdrop or CSS blur.
- Use restrained cyan, electric blue, and warm navigation amber against the existing dark environment. The scene must not obscure the ship with decorative effects.
- Keep the visible loading copy concise. The craft, engine state, and navigation lane convey the motion.
- Avoid added dependencies, external media, canvas, and Three.js. The implementation uses Vue, inline SVG, and scoped CSS only.

## Motion And Performance

- Use transform and opacity animation for the hull, plume, stars, and HUD layers to preserve rendering performance.
- Enter animation runs once. The cruise/transit loop is stable for a long connection and does not repeatedly reset or flash.
- The component clears its local stage timer on unmount.
- `prefers-reduced-motion: reduce` displays a stable ship and static star field with no translations, rotation, or flicker.

## Component Contract

- `ShipLoader.vue` retains a zero-prop public API.
- The component owns visual stage timing and does not write to the simulation store.
- `SimView.vue` retains the existing `v-if="sim.phase === 'connecting'"` condition.

## Verification

- Run `npm run build` from `frontend`.
- Verify the initial sequence, sustained state, and reduced-motion CSS manually in a browser using an authenticated simulation start.
- Confirm the loader disappears as soon as the phase leaves `connecting`, and that the existing terminate control, SSE events, and error state behavior remain unchanged.
