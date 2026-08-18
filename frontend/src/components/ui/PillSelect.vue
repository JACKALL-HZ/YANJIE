<script setup lang="ts">
/**
 * PillSelect — 药丸式单选组。
 * 相比原生 select，选项与释义同屏可见，减少「不知道选哪个」的犹豫。
 * 再次点击已选项可清空（allowClear）。
 */
interface Option { value: string; label: string; hint?: string }

withDefaults(
  defineProps<{
    modelValue: string | null
    options: Option[]
    allowClear?: boolean
    columns?: number
  }>(),
  { allowClear: true, columns: 0 },
)

const emit = defineEmits<{ 'update:modelValue': [v: string | null] }>()

function pick(v: string, current: string | null, allowClear: boolean) {
  emit('update:modelValue', allowClear && current === v ? null : v)
}
</script>

<template>
  <div
    class="flex flex-wrap gap-2"
    :style="columns ? { display: 'grid', gridTemplateColumns: `repeat(${columns}, minmax(0,1fr))` } : undefined"
  >
    <button
      v-for="o in options"
      :key="o.value"
      type="button"
      class="group rounded-btn border px-3 py-2 text-left transition-all duration-200 ease-smooth"
      :class="
        modelValue === o.value
          ? 'border-brand/55 bg-brand/12 text-ink-primary shadow-[0_0_0_1px_rgba(79,140,255,0.18),0_8px_22px_-12px_rgba(79,140,255,0.55)]'
          : 'border-white/8 bg-white/[0.02] text-ink-secondary hover:border-white/18 hover:bg-white/[0.05]'
      "
      @click="pick(o.value, modelValue, allowClear)"
    >
      <span class="block text-sm font-medium leading-tight">{{ o.label }}</span>
      <span v-if="o.hint" class="mt-0.5 block text-[11px] leading-tight text-ink-muted">{{ o.hint }}</span>
    </button>
  </div>
</template>
