<script setup lang="ts">
/**
 * TagInput — 标签录入（技能 / 证书 / 保险 / 目标）。
 * 回车或逗号提交，退格删末项；可给常用值做一键补全。
 */
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    placeholder?: string
    suggestions?: string[]
    max?: number
    accent?: 'cyan' | 'brand' | 'personal'
  }>(),
  { placeholder: '输入后回车添加', suggestions: () => [], max: 30, accent: 'cyan' },
)

const emit = defineEmits<{ 'update:modelValue': [v: string[]] }>()
const draft = ref('')

const ACCENT: Record<string, string> = {
  cyan: 'border-cyan-glow/25 bg-cyan-glow/10 text-cyan-glow',
  brand: 'border-brand/30 bg-brand/10 text-brand',
  personal: 'border-agent-personal/30 bg-agent-personal/10 text-agent-personal',
}

function add(raw?: string) {
  const value = (raw ?? draft.value).trim().replace(/[,，]$/, '')
  if (!value) return
  if (props.modelValue.includes(value)) { draft.value = ''; return }
  if (props.modelValue.length >= props.max) return
  emit('update:modelValue', [...props.modelValue, value])
  draft.value = ''
}

function remove(v: string) {
  emit('update:modelValue', props.modelValue.filter((x) => x !== v))
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',' || e.key === '，') {
    e.preventDefault()
    add()
    return
  }
  if (e.key === 'Backspace' && draft.value === '' && props.modelValue.length) {
    emit('update:modelValue', props.modelValue.slice(0, -1))
  }
}
</script>

<template>
  <div>
    <div
      class="flex min-h-[44px] flex-wrap items-center gap-2 rounded-btn border border-white/8 bg-surface-1/70 px-2.5 py-2 transition-colors focus-within:border-brand/45"
    >
      <span
        v-for="t in modelValue"
        :key="t"
        class="flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-xs"
        :class="ACCENT[accent]"
      >
        {{ t }}
        <button
          type="button"
          class="opacity-50 transition-opacity hover:opacity-100"
          :aria-label="`移除 ${t}`"
          @click="remove(t)"
        >×</button>
      </span>
      <input
        v-model="draft"
        type="text"
        :placeholder="modelValue.length ? '' : placeholder"
        class="min-w-[120px] flex-1 bg-transparent px-1 py-0.5 text-sm outline-none placeholder:text-ink-muted"
        @keydown="onKey"
        @blur="add()"
      />
    </div>

    <div v-if="suggestions.length" class="mt-2 flex flex-wrap gap-1.5">
      <button
        v-for="s in suggestions.filter((x) => !modelValue.includes(x))"
        :key="s"
        type="button"
        class="rounded-chip border border-white/8 px-2.5 py-1 text-[11px] text-ink-muted transition-colors hover:border-brand/40 hover:text-ink-secondary"
        @click="add(s)"
      >
        + {{ s }}
      </button>
    </div>
  </div>
</template>
