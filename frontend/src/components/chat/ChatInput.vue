<script setup lang="ts">
/**
 * ChatInput — 通用聊天输入框。
 * 支持 Enter 发送，Shift+Enter 换行。
 */
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    placeholder?: string
    disabled?: boolean
    busy?: boolean
  }>(),
  { placeholder: '输入你的想法…', disabled: false, busy: false },
)

const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')

function submit() {
  const trimmed = text.value.trim()
  if (!trimmed || props.disabled || props.busy) return
  emit('send', trimmed)
  text.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="flex items-end gap-2">
    <div class="relative flex-1">
      <textarea
        v-model="text"
        :disabled="disabled || busy"
        :placeholder="placeholder"
        rows="1"
        class="w-full resize-none rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-ink-primary outline-none backdrop-blur-sm transition-all duration-300 placeholder:text-ink-muted/50 focus:border-brand/50 focus:bg-white/[0.07] focus:shadow-[0_0_30px_rgba(79,140,255,0.1)] disabled:opacity-40"
        @keydown="onKeydown"
        @input="($event.target as HTMLTextAreaElement).style.height = 'auto'; ($event.target as HTMLTextAreaElement).style.height = ($event.target as HTMLTextAreaElement).scrollHeight + 'px'"
      />
    </div>
    <button
      class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand/20 text-brand transition-all hover:bg-brand/30 disabled:opacity-30"
      :disabled="disabled || busy || !text.trim()"
      @click="submit"
      aria-label="发送"
    >
      <!-- 发送图标 -->
      <svg v-if="!busy" width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="m5 12 4 4 10-8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <!-- Loading spinner -->
      <svg v-else class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.3" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      </svg>
    </button>
  </div>
</template>
