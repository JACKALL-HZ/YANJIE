<script setup lang="ts">
/** GlassPanel — 液态玻璃容器。spotlight 边框光随 hover 扫过。 */
import { ref } from 'vue'

withDefaults(
  defineProps<{
    strong?: boolean
    spotlight?: boolean
    padded?: boolean
  }>(),
  { strong: false, spotlight: false, padded: true },
)

const el = ref<HTMLElement | null>(null)
const glowX = ref('50%')
const glowY = ref('50%')
const hovering = ref(false)

function onMove(e: MouseEvent) {
  if (!el.value) return
  const r = el.value.getBoundingClientRect()
  glowX.value = `${((e.clientX - r.left) / r.width) * 100}%`
  glowY.value = `${((e.clientY - r.top) / r.height) * 100}%`
}
</script>

<template>
  <div
    ref="el"
    class="relative overflow-hidden rounded-card transition-colors duration-300"
    :class="[strong ? 'glass-strong' : 'glass', padded && 'p-6']"
    @mousemove="spotlight ? onMove : undefined"
    @mouseenter="spotlight && (hovering = true)"
    @mouseleave="spotlight && (hovering = false)"
  >
    <div
      v-if="spotlight"
      class="pointer-events-none absolute inset-0 transition-opacity duration-300"
      :style="{
        opacity: hovering ? 1 : 0,
        background: `radial-gradient(420px circle at ${glowX} ${glowY}, rgba(79,140,255,0.12), transparent 65%)`,
      }"
    />
    <div class="relative z-10">
      <slot />
    </div>
  </div>
</template>
