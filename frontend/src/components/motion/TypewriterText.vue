<script setup lang="ts">
/** 打字机：逐字输出 + 闪烁光标。用于 SSE 流式文本、标题强调。 */
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    text: string
    speed?: number
    cursor?: boolean
    start?: boolean
  }>(),
  { speed: 34, cursor: true, start: true },
)

const emit = defineEmits<{ done: [] }>()
const shown = ref('')
let timer: ReturnType<typeof setInterval> | null = null

function run() {
  if (timer) clearInterval(timer)
  shown.value = ''
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) {
    shown.value = props.text
    emit('done')
    return
  }
  let i = 0
  timer = setInterval(() => {
    i += 1
    shown.value = props.text.slice(0, i)
    if (i >= props.text.length) {
      if (timer) clearInterval(timer)
      emit('done')
    }
  }, props.speed)
}

onMounted(() => {
  if (props.start) run()
})
watch(
  () => props.text,
  () => {
    if (props.start) run()
  },
)
</script>

<template>
  <span class="inline">
    {{ shown
    }}<span
      v-if="cursor"
      class="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[0.15em] animate-pulse-soft bg-cyan-glow align-baseline"
    />
  </span>
</template>
