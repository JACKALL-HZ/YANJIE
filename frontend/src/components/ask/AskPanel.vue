<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { api, ApiRequestError } from '@/api/client'
import type { AskResponse } from '@/api/types'

const props = defineProps<{
  sessionId: string
  disabled?: boolean
}>()

interface Message {
  role: 'user' | 'ai'
  content: string
  loading?: boolean
}

const messages = ref<Message[]>([])
const input = ref('')
const sending = ref(false)
const listRef = ref<HTMLDivElement | null>(null)

async function scrollBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

async function send() {
  const q = input.value.trim()
  if (!q || sending.value || props.disabled) return

  input.value = ''
  messages.value.push({ role: 'user', content: q })
  const aiIdx = messages.value.length
  messages.value.push({ role: 'ai', content: '', loading: true })
  await scrollBottom()

  sending.value = true
  try {
    const { streamAsk } = await import('@/api/sse')
    await streamAsk(
      props.sessionId,
      q,
      (token) => {
        messages.value[aiIdx].content += token
        messages.value[aiIdx].loading = false
      },
      () => { /* done */ },
      (err) => {
        messages.value[aiIdx] = { role: 'ai', content: err.message, loading: false }
      },
    )
  } catch (e) {
    messages.value[aiIdx] = {
      role: 'ai',
      content: e instanceof ApiRequestError ? e.message : (e as Error).message,
      loading: false,
    }
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

watch(() => props.sessionId, () => {
  messages.value = []
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="flex flex-col" style="min-height: 320px">
    <!-- 消息列表 -->
    <div
      ref="listRef"
      class="flex-1 space-y-4 overflow-y-auto px-1"
      style="max-height: 380px"
    >
      <div
        v-if="messages.length === 0"
        class="py-8 text-center text-xs text-ink-muted"
      >
        {{ disabled ? '推演完成后可追问 AI' : '向 AI 追问这次推演的决策逻辑、风险成因或替代方案。' }}
      </div>

      <div
        v-for="(m, i) in messages"
        :key="i"
        class="flex"
        :class="m.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <!-- AI 头像 -->
        <div v-if="m.role === 'ai'" class="mr-2 mt-1 shrink-0">
          <div class="flex h-6 w-6 items-center justify-center rounded-full bg-brand/20 text-[10px] text-brand">
            AI
          </div>
        </div>

        <!-- 气泡 -->
        <div
          class="max-w-[82%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
          :class="m.role === 'user'
            ? 'bg-brand/20 text-ink-primary rounded-br-md'
            : 'glass text-ink-secondary rounded-bl-md'"
        >
          <span v-if="m.loading" class="flex gap-1 py-1">
            <span class="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand" />
            <span class="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand" style="animation-delay:0.15s" />
            <span class="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand" style="animation-delay:0.3s" />
          </span>
          <span v-else>{{ m.content }}</span>
        </div>

        <!-- 用户头像 -->
        <div v-if="m.role === 'user'" class="ml-2 mt-1 shrink-0">
          <div class="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-glow/15 text-[10px] text-cyan-glow">
            你
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="mt-4 flex gap-2">
      <input
        v-model="input"
        type="text"
        :disabled="disabled || sending"
        :placeholder="disabled ? '推演完成后可追问…' : '输入追问，如：为什么第2年现金流暴跌？'"
        class="min-w-0 flex-1 rounded-btn border border-white/10 bg-surface-1 px-4 py-2.5 text-sm text-ink-primary outline-none transition-colors placeholder:text-ink-muted focus:border-brand/50 disabled:opacity-50"
        @keydown="onKeydown"
      />
      <button
        class="shrink-0 rounded-btn bg-brand/20 px-4 py-2.5 text-sm font-medium text-brand transition-all hover:bg-brand/30 disabled:opacity-40"
        :disabled="disabled || sending || !input.trim()"
        @click="send"
      >
        {{ sending ? '…' : '发送' }}
      </button>
    </div>
  </div>
</template>
