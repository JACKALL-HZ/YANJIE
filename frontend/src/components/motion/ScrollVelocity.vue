<script setup lang="ts">
/**
 * ScrollVelocity — 移植自 reactbits.dev/text-animations/scroll-velocity
 * 滚动速度驱动的 marquee：滚动越快，文字滑动越快并带方向感；
 * 静止时按 baseVelocity 缓慢漂移。rAF + 弹簧阻尼，GPU transform only。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    texts?: string[]
    baseVelocity?: number
    numCopies?: number
    damping?: number
    stiffness?: number
    className?: string
  }>(),
  {
    texts: () => [],
    baseVelocity: 2.5,
    numCopies: 6,
    damping: 50,
    stiffness: 400,
    className: '',
  },
)

const rows = ref<HTMLElement[]>([])
const setRowRef = (el: unknown, i: number) => {
  if (el instanceof HTMLElement) rows.value[i] = el
}

interface RowState {
  x: number
  v: number // 弹簧追踪的滚动速度
  target: number
  halfWidth: number
}

let states: RowState[] = []
let raf = 0
let lastY = 0
let lastT = 0

function measure() {
  states = rows.value.map((el) => {
    const w = el ? el.scrollWidth / 2 : 0
    return { x: 0, v: 0, target: 0, halfWidth: w }
  })
}

function tick(t: number) {
  const y = window.scrollY
  const dt = Math.min((t - lastT) / 1000, 0.05) || 0.016
  lastT = t

  const scrollV = (y - lastY) / dt // px/s
  lastY = y

  rows.value.forEach((el, i) => {
    const s = states[i]
    if (!el || !s || s.halfWidth === 0) return

    // 弹簧追踪滚动速度（damping/stiffness 语义对齐原组件）
    const dir = i % 2 === 0 ? 1 : -1
    s.target = scrollV * 0.12 * dir
    const k = props.stiffness / 400
    const d = props.damping / 50
    s.v += (s.target - s.v) * Math.min(1, k * dt * 10)
    s.v *= Math.max(0, 1 - d * dt * 2)

    s.x += (props.baseVelocity * dir * 60 + s.v) * dt

    // 无缝循环：单份宽度取 scrollWidth/copies
    const unit = el.scrollWidth / props.numCopies
    if (unit > 0) {
      if (s.x <= -unit) s.x += unit
      if (s.x >= 0) s.x -= unit
    }
    el.style.transform = `translate3d(${s.x}px, 0, 0)`
  })

  raf = requestAnimationFrame(tick)
}

onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
  lastY = window.scrollY
  lastT = performance.now()
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!reduce) raf = requestAnimationFrame(tick)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', measure)
})
</script>

<template>
  <div class="overflow-hidden select-none" aria-hidden="true">
    <div
      v-for="(text, i) in texts"
      :key="i"
      class="whitespace-nowrap will-change-transform"
    >
      <div :ref="(el) => setRowRef(el, i)" class="inline-block will-change-transform">
        <span
          v-for="n in numCopies"
          :key="n"
          class="inline-block pr-[0.6em]"
          :class="className"
          >{{ text }}<span class="mx-[0.5em] text-cyan-glow/60">✦</span></span
        >
      </div>
    </div>
  </div>
</template>
