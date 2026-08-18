<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number | null | undefined
    decimals?: number
    prefix?: string
    suffix?: string
    format?: (value: number) => string
  }>(),
  { decimals: 0, prefix: '', suffix: '' },
)

const displayed = ref(0)
let frame = 0

function cancelAnimation() {
  if (frame) cancelAnimationFrame(frame)
  frame = 0
}

function animate(targetValue: number | null | undefined) {
  cancelAnimation()
  if (targetValue == null || Number.isNaN(Number(targetValue))) {
    displayed.value = 0
    return
  }

  const target = Number(targetValue)
  const start = displayed.value
  const distance = target - start
  if (!distance) return

  const reducedMotion = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reducedMotion) {
    displayed.value = target
    return
  }

  const startedAt = performance.now()
  const duration = 700
  const easeOut = (progress: number) => 1 - Math.pow(1 - progress, 3)
  const tick = (now: number) => {
    const progress = Math.min((now - startedAt) / duration, 1)
    displayed.value = start + distance * easeOut(progress)
    if (progress < 1) frame = requestAnimationFrame(tick)
    else frame = 0
  }
  frame = requestAnimationFrame(tick)
}

watch(() => props.value, animate, { immediate: true })
onBeforeUnmount(cancelAnimation)

const formatted = computed(() => {
  if (props.value == null) return '—'
  if (props.format) return props.format(displayed.value)
  return `${props.prefix}${displayed.value.toLocaleString('zh-CN', {
    minimumFractionDigits: props.decimals,
    maximumFractionDigits: props.decimals,
  })}${props.suffix}`
})
</script>

<template>{{ formatted }}</template>
