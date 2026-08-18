# Deep Space Ship Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the simulation connection overlay into a sharp, high-fidelity deep-space spacecraft sequence without changing simulation behavior.

**Architecture:** Keep `ShipLoader.vue` as a zero-prop, self-contained overlay. Vue local state advances visual-only stages while inline SVG and scoped CSS render the craft, engine plume, navigation lanes, and HUD. `SimView.vue` keeps the existing `sim.phase === 'connecting'` mounting contract unchanged.

**Tech Stack:** Vue 3, TypeScript, inline SVG, scoped CSS, Tailwind utilities, Vite.

## Global Constraints

- Modify only `frontend/src/components/motion/ShipLoader.vue` unless a build failure requires a minimal related type fix.
- Do not change SSE flow, Pinia state, routes, backend contracts, scenario data, or `SimView.vue` loader condition.
- Do not add dependencies, external media, canvas, or Three.js.
- Do not create artificial numerical progress.
- Support `prefers-reduced-motion: reduce`.
- Do not commit or push.

### Task 1: Define Visual-Only Loading Stages

**Files:**
- Modify: `frontend/src/components/motion/ShipLoader.vue`

**Interfaces:**
- Consumes: no props and no store state.
- Produces: a local `stage` ref with values `systems`, `analysis`, and `transit`; a derived label for the visible loading state.

- [x] **Step 1: Add the stage contract**

Add the following declaration before changing the template:

```ts
type LoaderStage = 'systems' | 'analysis' | 'transit'

const stage = ref<LoaderStage>('systems')
const stageCopy = computed(() => ({
  systems: { eyebrow: '系统上线', title: '正在建立世界状态', detail: '校准约束、资源与时间线坐标' },
  analysis: { eyebrow: '并行推演', title: '四个智能体正在推演', detail: '市场、环境、个人与风险判断正在汇合' },
  transit: { eyebrow: '航线校验', title: '正在验证分支风险', detail: '校验关键代价与可执行路径' },
}[stage.value]))
```

- [x] **Step 2: Implement deterministic visual stage timing**

Add `onBeforeUnmount`, retain the existing first-frame reveal, and schedule visual-only stage transitions:

```ts
const stageTimers: ReturnType<typeof setTimeout>[] = []

onMounted(() => {
  requestAnimationFrame(() => { visible.value = true })
  stageTimers.push(setTimeout(() => { stage.value = 'analysis' }, 1600))
  stageTimers.push(setTimeout(() => { stage.value = 'transit' }, 6200))
})

onBeforeUnmount(() => {
  stageTimers.forEach(clearTimeout)
})
```

Use a timer collection or two named timers so every scheduled timeout is cleared. Do not import or access `useSimulationStore`.

- [x] **Step 3: Run the frontend build**

Run: `npm run build` from `frontend`.

Expected: `vue-tsc -b && vite build` succeeds. This project has no frontend test runner, so TypeScript compilation and browser lifecycle validation are the focused verification cycle.

### Task 2: Replace the Decorative Loader With A Sharp Spacecraft Scene

**Files:**
- Modify: `frontend/src/components/motion/ShipLoader.vue`

**Interfaces:**
- Consumes: `visible`, `stage`, and `stageCopy` from Task 1.
- Produces: one non-interactive `aria-live="polite"` overlay with explicit stage classes.

- [x] **Step 1: Remove the blurred image backdrop**

Delete the `<img src="/assets/img/aetheris-odyssey.jpg">` layer and its blur class. Replace it with HTML layers for a sharp star field, navigation lanes, and a restrained atmospheric tint.

- [x] **Step 2: Replace the ship SVG with a near-field craft**

Create an inline SVG with the following named groups, used by scoped CSS:

```html
<svg viewBox="0 0 560 300" class="ship-svg" aria-hidden="true">
  <g class="ship-trail">...</g>
  <g class="ship-plume">...</g>
  <g class="ship-hull">...</g>
  <g class="ship-canopy">...</g>
  <g class="ship-nav-light">...</g>
</svg>
```

The hull must contain a fuselage, paired stabilizers, segmented panel lines, a canopy, two engine nozzles, and a small amber navigation light. Use SVG gradients and filters declared inside the same SVG. The ship must remain visually legible at `min(78vw, 560px)`.

- [x] **Step 3: Add a compact navigation HUD and stage-driven copy**

Render `stageCopy.eyebrow`, `stageCopy.title`, and `stageCopy.detail`. Give the stage root a `:data-stage="stage"` attribute so CSS can distinguish engine charge, cruise, and sustained transit. Do not render a percentage or countdown.

- [x] **Step 4: Add scoped motion rules**

Implement transform- and opacity-based keyframes for entry, engine charge, controlled cruise, transit streaks, and the navigation lanes. The entry animation runs once. `transit` loops steadily and does not reset the full scene. Apply `will-change: transform, opacity` only to moving layers.

- [x] **Step 5: Add reduced-motion rules**

Inside `@media (prefers-reduced-motion: reduce)`, disable every keyframe animation and transition used by the component. Keep the final spacecraft, stage title, and navigation lines visible.

- [x] **Step 6: Run the frontend build**

Run: `npm run build` from `frontend`.

Expected: `vue-tsc -b && vite build` succeeds.

### Task 3: Verify In Browser

**Files:**
- Verify: `frontend/src/components/motion/ShipLoader.vue`

- [ ] **Step 1: Start or reuse the Vite server**

Run: `npm run dev -- --host 127.0.0.1 --port 5174` from `frontend`, selecting an unused Vite port if needed.

- [ ] **Step 2: Validate connection overlay lifecycle**

Using an authenticated simulation start, observe the loader at initial entry, after two seconds, and after seven seconds. Confirm:

- the sharp scene has no blurred image backdrop;
- the ship remains the first visual signal;
- stages progress from world state to multi-agent analysis to risk validation;
- exit is immediate when `connecting` changes to `running`;
- the terminate button and later agent output are unaffected.

- [ ] **Step 3: Validate responsive and reduced-motion rendering**

At desktop and 390px mobile widths, confirm no hull, HUD, or copy overlaps. In browser reduced-motion emulation, confirm the craft and copy remain visible while motion is disabled.

- [x] **Step 4: Run final frontend build**

Run: `npm run build` from `frontend`.

Expected: `vue-tsc -b && vite build` succeeds. Record any existing bundle-size warning separately from this change.
