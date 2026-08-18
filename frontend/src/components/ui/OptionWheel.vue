<script setup lang="ts">
/**
 * OptionWheel — Vue 3 移植自 React Bits (reactbits.dev)
 * 弯曲滚轮选择器，rAF 弹簧物理 + CSS 颜色混合
 */
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

const props = withDefaults(defineProps<{
  items: string[]
  defaultSelected?: number
  textColor?: string
  activeColor?: string
  side?: 'left' | 'right'
  fontSize?: number
  spacing?: number
  curve?: number
  tilt?: number
  blur?: number
  fade?: number
  minOpacity?: number
  smoothing?: number
  inset?: number
  loop?: boolean
  draggable?: boolean
}>(), {
  items: () => [],
  defaultSelected: 0,
  textColor: '#9AA6BC',
  activeColor: '#22D3EE',
  side: 'left',
  fontSize: 2.4,
  spacing: 1.5,
  curve: 0.8,
  tilt: 7,
  blur: 3,
  fade: 0.3,
  minOpacity: 0.06,
  smoothing: 100,
  inset: 120,
  loop: false,
  draggable: true,
})

const emit = defineEmits<{ change: [index: number, item: string] }>()

const rootRef = ref<HTMLDivElement | null>(null)
const itemRefs = ref<HTMLElement[]>([])
const selectedIndex = ref(props.defaultSelected)
const isDragging = ref(false)

/* ── 物理引擎 ─────────────────────────────────── */
let pos = props.defaultSelected
let target = props.defaultSelected
let rafId: number | null = null
let lastTime = 0
let wheelTimer: ReturnType<typeof setTimeout> | null = null
let dragStart: { y: number; start: number } | null = null
let dragMoved = false

const remPx = typeof window !== 'undefined' ? parseFloat(getComputedStyle(document.documentElement).fontSize) || 16 : 16

const rowH = computed(() => Math.max(props.fontSize * props.spacing * remPx, 1))
const count = computed(() => props.items.length)

function runFrame(now: number) {
  const dt = Math.min((now - lastTime) / 1000, 0.05)
  lastTime = now
  const tau = Math.max(props.smoothing, 1) / 1000
  const k = 1 - Math.exp(-dt / tau)
  let next = pos + (target - pos) * k
  const settled = Math.abs(target - next) < 0.001
  if (settled) next = target
  pos = next

  const els = itemRefs.value
  const n = count.value
  const mirror = props.side === 'right' ? -1 : 1
  const tiltRad = (props.tilt * Math.PI) / 180
  const R = tiltRad > 0.0005 ? rowH.value / tiltRad : 0

  for (let i = 0; i < n; i++) {
    const el = els[i]
    if (!el) continue
    let d = i - next
    if (props.loop && n > 1) {
      d = ((d % n) + n) % n
      if (d > n / 2) d -= n
    }
    const dist = Math.abs(d)
    let x = 0, y = d * rowH.value, rot = 0
    if (R > 0) {
      const ang = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, d * tiltRad))
      y = R * Math.sin(ang)
      x = -mirror * R * (1 - Math.cos(ang)) * props.curve
      rot = (mirror * ang * 180) / Math.PI
    }
    el.style.transform = `translate(${x.toFixed(2)}px, calc(${y.toFixed(2)}px - 50%)) rotate(${rot.toFixed(3)}deg)`
    el.style.opacity = String(Math.max(props.minOpacity, 1 - dist * props.fade))
    el.style.filter = props.blur > 0 ? `blur(${(dist * props.blur).toFixed(2)}px)` : 'none'
    el.style.setProperty('--ow-p', Math.max(0, 1 - Math.min(dist, 1)).toFixed(4))
  }
  rafId = settled ? null : requestAnimationFrame(runFrame)
}

function startLoop() {
  if (rafId != null) cancelAnimationFrame(rafId)
  lastTime = performance.now()
  rafId = requestAnimationFrame(runFrame)
}

function applyTarget(value: number, snap: boolean) {
  let v = value
  if (!props.loop) v = Math.min(Math.max(v, 0), Math.max(count.value - 1, 0))
  if (snap) v = Math.round(v)
  target = v
  const idx = ((Math.round(v) % count.value) + count.value) % count.value
  if (idx !== selectedIndex.value) {
    selectedIndex.value = idx
    emit('change', idx, props.items[idx])
  }
  startLoop()
}

/* ── 滚轮事件（优化：累积分数 + 自适应步长）───── */
let wheelAccum = 0
function onWheel(e: WheelEvent) {
  e.preventDefault()
  // 标准化 delta：不同设备/browser 差异很大，归一化到像素
  let px = 0
  if (e.deltaMode === 0) px = e.deltaY           // 像素（触控板）
  else if (e.deltaMode === 1) px = e.deltaY * 18  // 行（普通鼠标滚轮）
  else px = e.deltaY * 600                         // 页

  // 自适应步长：快速滚动时加速，慢速时精确
  const rawStep = px / rowH.value
  const absStep = Math.abs(rawStep)
  const sign = rawStep > 0 ? 1 : -1
  // 低于 0.3 步时累积，超过后移动整数步
  const threshold = 0.25
  wheelAccum += rawStep
  if (Math.abs(wheelAccum) >= threshold) {
    const move = Math.trunc(wheelAccum / threshold) * (threshold > 0.5 ? 1 : threshold)
    wheelAccum = 0
    applyTarget(target + move, false)
  }
  if (wheelTimer) clearTimeout(wheelTimer)
  wheelTimer = setTimeout(() => {
    wheelAccum = 0
    applyTarget(target, true)
  }, 120)
}

/* ── 拖拽 ─────────────────────────────────────── */
function onPointerDown(e: PointerEvent) {
  if (!props.draggable) return
  dragStart = { y: e.clientY, start: target }
  dragMoved = false
  isDragging.value = true
}
function onPointerMove(e: PointerEvent) {
  if (!dragStart) return
  const dy = e.clientY - dragStart.y
  if (!dragMoved && Math.abs(dy) > 4) {
    dragMoved = true
    rootRef.value?.setPointerCapture(e.pointerId)
  }
  if (dragMoved) applyTarget(dragStart.start - dy / rowH.value, false)
}
function onPointerEnd() {
  if (!dragStart) return
  dragStart = null
  isDragging.value = false
  if (dragMoved) applyTarget(target, true)
}

/* ── 键盘 ─────────────────────────────────────── */
function onKeyDown(e: KeyboardEvent) {
  let delta: number | null = null
  if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') delta = -1
  else if (e.key === 'ArrowDown' || e.key === 'ArrowRight') delta = 1
  if (delta == null) return
  e.preventDefault()
  applyTarget(Math.round(target) + delta, true)
}

function onItemClick(index: number) {
  if (dragMoved) return
  const cur = target
  let d = index - (((cur % count.value) + count.value) % count.value)
  if (props.loop && count.value > 1) {
    if (d > count.value / 2) d -= count.value
    else if (d < -count.value / 2) d += count.value
  }
  applyTarget(cur + d, true)
}

/* ── 初始化 + 参数变化重算 ────────────────────── */
onMounted(() => {
  applyTarget(props.defaultSelected, false)
})

watch(
  () => [props.items, props.fontSize, props.spacing, props.curve, props.tilt, props.blur, props.fade, props.side, props.loop, props.smoothing],
  () => { applyTarget(target, false) },
)

onBeforeUnmount(() => {
  if (rafId != null) cancelAnimationFrame(rafId)
  if (wheelTimer) clearTimeout(wheelTimer)
})
</script>

<template>
  <div
    ref="rootRef"
    class="option-wheel"
    :class="{
      'option-wheel--right': side === 'right',
      'option-wheel--dragging': isDragging,
    }"
    role="listbox"
    tabindex="0"
    aria-label="场景选择器"
    :style="{
      '--ow-text-color': textColor,
      '--ow-active-color': activeColor,
      '--ow-font-size': `${fontSize}rem`,
      '--ow-inset': `${inset}px`,
    }"
    @wheel="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerEnd"
    @pointercancel="onPointerEnd"
    @keydown="onKeyDown"
  >
    <div
      v-for="(label, index) in items"
      :key="`${label}-${index}`"
      :ref="(el) => { if (el) itemRefs[index] = el as HTMLElement }"
      role="option"
      :aria-selected="selectedIndex === index"
      class="option-wheel__item"
      :class="{ 'option-wheel__item--selected': selectedIndex === index }"
      @click="onItemClick(index)"
    >
      {{ label }}
    </div>
  </div>
</template>

<style scoped>
.option-wheel {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 420px;
  overflow: hidden;
  cursor: grab;
  user-select: none;
  touch-action: none;
  outline: none;
}
.option-wheel--dragging { cursor: grabbing; }
.option-wheel__item {
  position: absolute;
  top: 50%;
  left: var(--ow-inset);
  white-space: nowrap;
  font-size: var(--ow-font-size);
  line-height: 1;
  font-weight: 300;
  letter-spacing: -0.01em;
  transform-origin: left center;
  cursor: pointer;
  will-change: transform, opacity, filter;
  color: color-mix(in srgb, var(--ow-active-color) calc(var(--ow-p, 0) * 100%), var(--ow-text-color));
  transition: font-weight 0.2s ease;
}
.option-wheel--right .option-wheel__item {
  left: auto;
  right: var(--ow-inset);
  transform-origin: right center;
}
.option-wheel__item--selected { font-weight: 600; }
</style>
