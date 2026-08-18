<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

type LoaderStage = 'systems' | 'analysis' | 'transit'

const visible = ref(false)
const stage = ref<LoaderStage>('systems')
const stageTimers: ReturnType<typeof setTimeout>[] = []

const stageCopy = computed(() => ({
  systems: {
    eyebrow: 'NAVIGATION SYSTEMS',
    title: '正在建立世界状态',
    detail: '校准约束、资源与时间线坐标',
  },
  analysis: {
    eyebrow: 'MULTI-AGENT ANALYSIS',
    title: '四个智能体正在推演',
    detail: '市场、环境、个人与风险判断正在汇合',
  },
  transit: {
    eyebrow: 'ROUTE VALIDATION',
    title: '正在验证分支风险',
    detail: '校验关键代价与可执行路径',
  },
}[stage.value]))

onMounted(() => {
  requestAnimationFrame(() => { visible.value = true })
  stageTimers.push(setTimeout(() => { stage.value = 'analysis' }, 900))
  stageTimers.push(setTimeout(() => { stage.value = 'transit' }, 5000))
})

onBeforeUnmount(() => {
  stageTimers.forEach(clearTimeout)
})
</script>

<template>
  <div
    class="ship-loader pointer-events-none fixed inset-0 z-50 grid place-items-center overflow-hidden"
    :class="{ 'ship-loader--visible': visible }"
    :data-stage="stage"
    aria-live="polite"
    aria-busy="true"
  >
    <div class="space-grid" aria-hidden="true" />
    <div class="starfield" aria-hidden="true">
      <i v-for="star in 20" :key="star" class="star" />
    </div>
    <div class="nav-lane nav-lane--upper" aria-hidden="true" />
    <div class="nav-lane nav-lane--lower" aria-hidden="true" />

    <section class="flight-console" aria-label="推演航行状态">
      <div class="flight-mark">
        <span class="flight-mark__signal" />
        <span>YANJIE // SIMULATION FLIGHT</span>
      </div>

      <div class="ship-stage">
        <div class="engine-field engine-field--left" aria-hidden="true" />
        <div class="engine-field engine-field--right" aria-hidden="true" />
        <svg viewBox="0 0 560 300" class="ship-svg" aria-hidden="true">
          <defs>
            <linearGradient id="hull-main" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#22354c" />
              <stop offset="48%" stop-color="#c8d5df" />
              <stop offset="100%" stop-color="#60788c" />
            </linearGradient>
            <linearGradient id="hull-edge" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#f3f8fb" />
              <stop offset="100%" stop-color="#73899b" />
            </linearGradient>
            <linearGradient id="canopy" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#9af4ff" stop-opacity=".9" />
              <stop offset="55%" stop-color="#2d8fc1" stop-opacity=".65" />
              <stop offset="100%" stop-color="#142a44" stop-opacity=".92" />
            </linearGradient>
            <linearGradient id="plume" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#37e4ff" stop-opacity="0" />
              <stop offset="48%" stop-color="#37e4ff" stop-opacity=".95" />
              <stop offset="100%" stop-color="#f0fbff" stop-opacity=".1" />
            </linearGradient>
            <filter id="engine-glow" x="-80%" y="-120%" width="260%" height="340%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="ship-shadow" x="-40%" y="-60%" width="200%" height="240%">
              <feDropShadow dx="0" dy="10" stdDeviation="9" flood-color="#02101c" flood-opacity=".92" />
            </filter>
          </defs>

          <g class="ship-trail">
            <path d="M10 105 C118 98 172 112 275 132" />
            <path d="M0 190 C130 182 184 170 292 152" />
            <path d="M42 147 L270 143" />
          </g>
          <g class="ship-plume" filter="url(#engine-glow)">
            <path d="M103 119 C54 108 22 105 2 110 C38 121 49 133 103 135 Z" fill="url(#plume)" />
            <path d="M100 165 C44 163 18 176 0 190 C48 184 67 179 111 176 Z" fill="url(#plume)" />
            <path d="M88 137 L18 149 L91 157 Z" fill="#d9fbff" fill-opacity=".72" />
          </g>
          <g class="ship-hull" filter="url(#ship-shadow)">
            <path d="M95 147 L215 72 L468 130 L530 150 L468 170 L215 228 Z" fill="url(#hull-main)" stroke="#dce9f0" stroke-opacity=".72" stroke-width="2" />
            <path d="M176 146 L298 83 L465 130 L307 147 Z" fill="url(#hull-edge)" stroke="#dce9f0" stroke-opacity=".6" stroke-width="1.5" />
            <path d="M176 151 L307 153 L465 170 L298 217 Z" fill="#405a6e" stroke="#b8c8d1" stroke-opacity=".42" stroke-width="1.5" />
            <path d="M150 139 L83 94 L110 150 L83 207 L150 160 Z" fill="#516b7e" stroke="#c8d7df" stroke-opacity=".5" stroke-width="1.4" />
            <path d="M252 95 L296 54 L348 99 L307 131 Z" fill="#7890a1" stroke="#dce9f0" stroke-opacity=".55" stroke-width="1.2" />
            <path d="M252 205 L296 246 L348 201 L307 169 Z" fill="#3f596c" stroke="#b7c9d5" stroke-opacity=".42" stroke-width="1.2" />
          </g>
          <g class="ship-panel-lines" fill="none" stroke="#0a2638" stroke-opacity=".56" stroke-width="1.5">
            <path d="M127 147 L267 99 L408 141 L267 199 Z" />
            <path d="M202 110 L228 184 M269 93 L296 207 M346 107 L366 193" />
            <path d="M125 141 L170 147 L125 159" />
          </g>
          <g class="ship-canopy">
            <path d="M296 107 L387 137 L307 145 L245 143 Z" fill="url(#canopy)" stroke="#a8f4ff" stroke-opacity=".76" stroke-width="1.5" />
            <path d="M296 107 L307 145" fill="none" stroke="#d0fbff" stroke-opacity=".75" />
            <path d="M278 117 L348 141" fill="none" stroke="#d0fbff" stroke-opacity=".32" />
          </g>
          <g class="ship-engines" filter="url(#engine-glow)">
            <circle cx="113" cy="120" r="11" fill="#2ae1ff" fill-opacity=".9" />
            <circle cx="113" cy="175" r="11" fill="#2ae1ff" fill-opacity=".9" />
            <circle cx="113" cy="120" r="4" fill="#efffff" />
            <circle cx="113" cy="175" r="4" fill="#efffff" />
          </g>
          <g class="ship-nav-light" filter="url(#engine-glow)">
            <circle cx="472" cy="150" r="4" fill="#ffbd55" />
          </g>
        </svg>
      </div>

      <div class="flight-readout">
        <div class="flight-readout__top">
          <span class="flight-readout__status"><i /> LINK ACTIVE</span>
          <span class="flight-readout__stage">{{ stageCopy.eyebrow }}</span>
        </div>
        <h2>{{ stageCopy.title }}</h2>
        <p>{{ stageCopy.detail }}</p>
        <div class="flight-readout__track" aria-hidden="true"><span /></div>
      </div>

      <div class="flight-data" aria-hidden="true">
        <span>VECTOR <b>07.24</b></span>
        <span>DRIFT <b>0.003</b></span>
        <span>CORE <b>STABLE</b></span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ship-loader {
  --cyan: #37e4ff;
  --blue: #4f8cff;
  --amber: #ffbd55;
  background: #04070d;
  color: #e7f2f8;
  opacity: 0;
  transition: opacity 260ms ease-out;
}

.ship-loader--visible { opacity: 1; }

.space-grid,
.starfield,
.nav-lane { position: absolute; inset: 0; }

.space-grid {
  opacity: .22;
  background-image: linear-gradient(rgba(89, 166, 200, .13) 1px, transparent 1px), linear-gradient(90deg, rgba(89, 166, 200, .09) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: linear-gradient(to bottom, transparent 0%, black 38%, transparent 100%);
}

.starfield { overflow: hidden; }
.star {
  position: absolute;
  width: 2px;
  height: 2px;
  background: #d8f9ff;
  box-shadow: 0 0 7px rgba(93, 225, 255, .8);
  opacity: .75;
}
.star:nth-child(1) { left: 7%; top: 16%; }
.star:nth-child(2) { left: 15%; top: 67%; width: 3px; height: 3px; }
.star:nth-child(3) { left: 23%; top: 31%; }
.star:nth-child(4) { left: 31%; top: 82%; }
.star:nth-child(5) { left: 39%; top: 13%; width: 3px; height: 3px; }
.star:nth-child(6) { left: 46%; top: 74%; }
.star:nth-child(7) { left: 52%; top: 26%; }
.star:nth-child(8) { left: 61%; top: 58%; width: 3px; height: 3px; }
.star:nth-child(9) { left: 69%; top: 18%; }
.star:nth-child(10) { left: 76%; top: 77%; }
.star:nth-child(11) { left: 84%; top: 38%; width: 3px; height: 3px; }
.star:nth-child(12) { left: 93%; top: 20%; }
.star:nth-child(13) { left: 4%; top: 46%; }
.star:nth-child(14) { left: 18%; top: 91%; }
.star:nth-child(15) { left: 35%; top: 47%; }
.star:nth-child(16) { left: 58%; top: 91%; width: 3px; height: 3px; }
.star:nth-child(17) { left: 66%; top: 8%; }
.star:nth-child(18) { left: 80%; top: 61%; }
.star:nth-child(19) { left: 89%; top: 90%; }
.star:nth-child(20) { left: 97%; top: 54%; width: 3px; height: 3px; }

.nav-lane {
  inset: 50% auto auto 50%;
  width: min(1200px, 120vw);
  height: 1px;
  transform-origin: left center;
  background: linear-gradient(90deg, transparent, rgba(55, 228, 255, .45), transparent 82%);
  opacity: .42;
}
.nav-lane--upper { transform: rotate(-12deg) translate(-14%, -132px); }
.nav-lane--lower { transform: rotate(11deg) translate(-14%, 132px); }

.flight-console { width: min(92vw, 680px); }
.flight-mark,
.flight-data,
.flight-readout__top { display: flex; justify-content: space-between; gap: 1rem; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 10px; letter-spacing: 0; }
.flight-mark { color: rgba(202, 233, 241, .62); }
.flight-mark__signal { width: 7px; height: 7px; border: 1px solid var(--cyan); box-shadow: 0 0 10px var(--cyan); }

.ship-stage {
  position: relative;
  height: min(43vw, 300px);
  margin: 1.35rem 0 .6rem;
  opacity: 0;
  transform: translate3d(110px, 12px, 0) scale(.9);
  transition: transform 1200ms cubic-bezier(.16, 1, .3, 1), opacity 550ms ease-out;
  will-change: transform, opacity;
}
.ship-loader--visible .ship-stage { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
.ship-svg { position: relative; z-index: 2; width: 100%; height: 100%; overflow: visible; }
.engine-field { position: absolute; z-index: 1; top: 42%; width: 36%; height: 14%; opacity: .6; background: linear-gradient(90deg, transparent, rgba(55, 228, 255, .2), transparent); transform: skewX(-22deg); }
.engine-field--left { left: 2%; }
.engine-field--right { left: 2%; top: 61%; }

.ship-trail path { fill: none; stroke: rgba(123, 232, 255, .65); stroke-width: 1.4; stroke-dasharray: 20 14; }
.ship-plume { transform-origin: 110px 150px; animation: plume-pulse 850ms ease-in-out infinite alternate; }
.ship-engines { animation: engine-charge 850ms ease-in-out infinite alternate; }
.ship-nav-light { animation: nav-pulse 1.3s ease-in-out infinite; }

.flight-readout { border-left: 2px solid var(--cyan); padding: .8rem 1rem .15rem; }
.flight-readout__top { color: rgba(205, 232, 240, .55); }
.flight-readout__status { color: var(--cyan); }
.flight-readout__status i { display: inline-block; width: 6px; height: 6px; margin-right: 6px; background: var(--cyan); box-shadow: 0 0 9px var(--cyan); }
.flight-readout__stage { text-align: right; }
.flight-readout h2 { margin: .45rem 0 0; font-family: var(--font-display, ui-sans-serif, system-ui); font-size: 21px; font-weight: 600; letter-spacing: 0; }
.flight-readout p { margin: .3rem 0 0; color: rgba(208, 229, 236, .7); font-size: 13px; line-height: 1.65; }
.flight-readout__track { width: 100%; height: 2px; margin-top: .9rem; overflow: hidden; background: rgba(113, 183, 203, .18); }
.flight-readout__track span { display: block; width: 38%; height: 100%; background: var(--cyan); box-shadow: 0 0 12px var(--cyan); animation: scan-track 1.5s ease-in-out infinite; }
.flight-data { margin-top: 1rem; color: rgba(190, 219, 228, .45); }
.flight-data b { color: rgba(226, 247, 251, .82); font-weight: 500; }

.ship-loader[data-stage='analysis'] .ship-stage { animation: cruise-drift 3.8s ease-in-out infinite alternate; }
.ship-loader[data-stage='analysis'] .ship-trail path { animation: trail-flow 1.2s linear infinite; }
.ship-loader[data-stage='transit'] .ship-stage { animation: transit-drift 2.4s ease-in-out infinite alternate; }
.ship-loader[data-stage='transit'] .starfield { animation: stars-transit 1.15s linear infinite; }
.ship-loader[data-stage='transit'] .ship-trail path { stroke-width: 2.4; stroke-dasharray: 88 30; animation: trail-flow 470ms linear infinite; }
.ship-loader[data-stage='transit'] .nav-lane { opacity: .8; animation: lane-slide 1.1s linear infinite; }
.ship-loader[data-stage='transit'] .engine-field { opacity: .95; animation: engine-field 500ms ease-in-out infinite alternate; }
.ship-loader[data-stage='transit'] .ship-plume { animation-duration: 430ms; }

@keyframes plume-pulse { from { transform: scaleX(.76); opacity: .55; } to { transform: scaleX(1.15); opacity: 1; } }
@keyframes engine-charge { from { opacity: .55; } to { opacity: 1; } }
@keyframes nav-pulse { 0%, 100% { opacity: .45; } 50% { opacity: 1; } }
@keyframes scan-track { from { transform: translateX(-110%); } to { transform: translateX(290%); } }
@keyframes cruise-drift { from { transform: translate3d(0, 0, 0) rotate(-.45deg); } to { transform: translate3d(-8px, -5px, 0) rotate(.35deg); } }
@keyframes transit-drift { from { transform: translate3d(-4px, -2px, 0) rotate(-.6deg); } to { transform: translate3d(8px, 3px, 0) rotate(.55deg); } }
@keyframes trail-flow { to { stroke-dashoffset: -160; } }
@keyframes stars-transit { from { transform: translateX(-2%); } to { transform: translateX(2%); } }
@keyframes lane-slide { from { background-position-x: 0; } to { background-position-x: 480px; } }
@keyframes engine-field { from { transform: skewX(-22deg) scaleX(.82); } to { transform: skewX(-22deg) scaleX(1.2); } }

@media (max-width: 520px) {
  .flight-console { width: min(92vw, 430px); }
  .ship-stage { height: 47vw; margin-top: 2.25rem; }
  .flight-mark { font-size: 9px; }
  .flight-readout { padding-left: .8rem; }
  .flight-readout h2 { font-size: 18px; }
  .flight-readout p { max-width: 270px; font-size: 12px; }
  .flight-readout__stage { max-width: 120px; }
  .flight-data { font-size: 8px; gap: .4rem; }
}

@media (prefers-reduced-motion: reduce) {
  .ship-loader,
  .ship-stage,
  .ship-plume,
  .ship-engines,
  .ship-nav-light,
  .flight-readout__track span,
  .ship-loader[data-stage='analysis'] .ship-stage,
  .ship-loader[data-stage='analysis'] .ship-trail path,
  .ship-loader[data-stage='transit'] .ship-stage,
  .ship-loader[data-stage='transit'] .starfield,
  .ship-loader[data-stage='transit'] .ship-trail path,
  .ship-loader[data-stage='transit'] .nav-lane,
  .ship-loader[data-stage='transit'] .engine-field {
    animation: none;
    transition: none;
  }
  .ship-loader,
  .ship-loader--visible { opacity: 1; }
  .ship-stage,
  .ship-loader--visible .ship-stage { opacity: 1; transform: none; }
}
</style>
