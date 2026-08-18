<script setup lang="ts">
import { ref } from 'vue'
import type { PendingIntervention } from '@/api/types'
import FancyButton from '@/components/ui/FancyButton.vue'

const props = defineProps<{
  intervention: PendingIntervention
  busy?: boolean
}>()

const emit = defineEmits<{ choose: [option: string] }>()
const selected = ref<string | null>(null)

function confirm() {
  if (selected.value) emit('choose', selected.value)
}
</script>

<template>
  <div class="glass-strong rounded-modal border border-agent-risk/30 p-6 shadow-[0_0_40px_rgba(248,113,113,0.08)]">
    <div class="mb-4 flex items-center gap-3">
      <span class="flex h-8 w-8 items-center justify-center rounded-full bg-agent-risk/15 text-agent-risk">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </span>
      <div>
        <div class="text-sm font-semibold text-ink-primary">关键决策点 · 第 {{ intervention.year }} 年</div>
        <div class="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          {{ intervention.rule_id }}
        </div>
      </div>
    </div>

    <p class="text-sm leading-relaxed text-ink-secondary">{{ intervention.event }}</p>

    <div class="mt-5 space-y-2">
      <button
        v-for="opt in intervention.options"
        :key="opt"
        class="w-full rounded-btn border px-4 py-3 text-left text-sm transition-all duration-200"
        :class="
          selected === opt
            ? 'border-brand/60 bg-brand/10 text-ink-primary'
            : 'border-white/10 bg-white/[0.02] text-ink-secondary hover:border-white/20 hover:text-ink-primary'
        "
        @click="selected = opt"
      >
        {{ opt }}
      </button>
    </div>

    <div class="mt-6 flex justify-end">
      <FancyButton :disabled="!selected || busy" @click="confirm">
        {{ busy ? '恢复推演中…' : '确认并继续' }}
      </FancyButton>
    </div>
  </div>
</template>
