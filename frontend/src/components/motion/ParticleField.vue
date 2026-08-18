<script setup lang="ts">
/**
 * ParticleField — 轻量 Canvas 星尘粒子背景。
 * 无依赖，零库：漂浮微光点 + 偶发连线，暗色科技氛围。
 * 移动端自动降密度，prefers-reduced-motion 时静态渲染一帧。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    density?: number
    linkDistance?: number
  }>(),
  { density: 0.00012, linkDistance: 110 },
)

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let raf = 0
let particles: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = []
let w = 0
let h = 0

function resize() {
  const c = canvasRef.value
  if (!c || !ctx) return
  const parent = c.parentElement
  if (!parent) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  w = parent.clientWidth
  h = parent.clientHeight
  c.width = w * dpr
  c.height = h * dpr
  c.style.width = `${w}px`
  c.style.height = `${h}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const coarse = window.matchMedia('(pointer: coarse)').matches
  const target = Math.floor(w * h * props.density * (coarse ? 0.4 : 1))
  particles = Array.from({ length: Math.min(target, 220) }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.25,
    vy: (Math.random() - 0.5) * 0.25,
    r: Math.random() * 1.6 + 0.4,
    a: Math.random() * 0.5 + 0.15,
  }))
}

function frame() {
  if (!ctx) return
  ctx.clearRect(0, 0, w, h)

  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    if (p.x < -10) p.x = w + 10
    if (p.x > w + 10) p.x = -10
    if (p.y < -10) p.y = h + 10
    if (p.y > h + 10) p.y = -10

    ctx!.beginPath()
    ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx!.fillStyle = `rgba(140, 180, 255, ${p.a})`
    ctx!.fill()
  }

  // 邻近连线
  const ld = props.linkDistance
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.hypot(dx, dy)
      if (dist < ld) {
        const alpha = (1 - dist / ld) * 0.12
        ctx!.beginPath()
        ctx!.moveTo(particles[i].x, particles[i].y)
        ctx!.lineTo(particles[j].x, particles[j].y)
        ctx!.strokeStyle = `rgba(79, 140, 255, ${alpha})`
        ctx!.lineWidth = 0.6
        ctx!.stroke()
      }
    }
  }

  raf = requestAnimationFrame(frame)
}

onMounted(() => {
  const c = canvasRef.value
  if (!c) return
  ctx = c.getContext('2d')
  if (!ctx) return
  resize()
  window.addEventListener('resize', resize)
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) {
    frame()
    cancelAnimationFrame(raf)
  } else {
    raf = requestAnimationFrame(frame)
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', resize)
})
</script>

<template>
  <canvas ref="canvasRef" class="pointer-events-none absolute inset-0" aria-hidden="true" />
</template>
