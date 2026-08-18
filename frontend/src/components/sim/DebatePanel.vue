<script setup lang="ts">
import { computed } from 'vue'
import type { DebateRecord } from '@/api/types'

const props = defineProps<{ debate: DebateRecord | null }>()

const positionLabel = (position: string) => ({
  support: '支持',
  oppose: '反对',
  conditional: '有条件支持',
  neutral: '保持观察',
} as Record<string, string>)[position] || '保持观察'

const positionClass = (position: string) => ({
  support: 'text-agent-market',
  oppose: 'text-agent-risk',
  conditional: 'text-agent-env',
  neutral: 'text-ink-muted',
} as Record<string, string>)[position] || 'text-ink-muted'

const agentName = (agentId: string) => ({
  market: '市场智能体',
  environment: '环境智能体',
  personal: '个人智能体',
  risk: '风险智能体',
} as Record<string, string>)[agentId] || agentId

const frontline = computed(() => {
  if (!props.debate) return null
  const support = props.debate.participants.find((item) => item.position === 'support')
  const oppose = props.debate.participants.find((item) => item.position === 'oppose')
  if (!support || !oppose) return null
  return { support, oppose }
})

interface ReasonPart {
  text: string
  emphasis: boolean
}

function reasonParts(reason: string): ReasonPart[] {
  const pattern = /(支持|反对|不建议|但是|不过|然而|条件|妥协|止损|优先|风险|机会)/g
  const parts: ReasonPart[] = []
  let cursor = 0
  for (const match of reason.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) parts.push({ text: reason.slice(cursor, index), emphasis: false })
    parts.push({ text: match[0], emphasis: true })
    cursor = index + match[0].length
  }
  if (cursor < reason.length) parts.push({ text: reason.slice(cursor), emphasis: false })
  return parts.length ? parts : [{ text: reason, emphasis: false }]
}
</script>

<template>
  <section v-if="debate" class="border-l-2 border-agent-env/70 bg-agent-env/5 p-5 shadow-[0_0_36px_rgba(52,211,153,0.08)]">
    <div class="flex items-center justify-between gap-3">
      <div>
        <p class="text-sm font-semibold text-ink-primary">观点分歧与交锋</p>
        <p class="mt-1 text-xs text-ink-muted">展示四方原始立场、各自保留意见，以及裁判给出的协调结论</p>
      </div>
      <span class="text-[10px] text-agent-env">{{ debate.trigger === 'judge_conflict' ? '存在明确冲突' : '高影响决策' }}</span>
    </div>

    <div
      v-if="frontline"
      class="mt-4 border border-agent-risk/25 bg-black/10 px-3 py-3"
      aria-label="智能体立场交锋"
    >
      <div class="flex items-center justify-between gap-3 text-xs">
        <div class="min-w-0">
          <p class="truncate font-semibold text-agent-env">{{ agentName(frontline.support.agent_id) }}</p>
          <p class="mt-0.5 text-[10px] text-ink-muted">支持推进</p>
        </div>
        <div class="debate-bridge flex min-w-[100px] flex-1 items-center justify-center gap-2 px-2 text-[10px] text-ink-muted">
          <span class="h-px flex-1 bg-agent-env/60" />
          <span class="whitespace-nowrap rounded-chip border border-white/10 px-2 py-0.5">立场交锋</span>
          <span class="h-px flex-1 bg-agent-risk/60" />
        </div>
        <div class="min-w-0 text-right">
          <p class="truncate font-semibold text-agent-risk">{{ agentName(frontline.oppose.agent_id) }}</p>
          <p class="mt-0.5 text-[10px] text-ink-muted">收缩防守</p>
        </div>
      </div>
      <div class="mt-2 flex justify-center">
        <span class="debate-pulse text-sm text-amber-300">↔</span>
      </div>
    </div>

    <div class="mt-3 space-y-2">
      <p v-for="conflict in debate.conflicts" :key="conflict" class="border-l-2 border-agent-risk/60 pl-3 text-xs leading-relaxed text-ink-secondary">
        {{ conflict }}
      </p>
    </div>

    <div class="mt-4 grid gap-2 sm:grid-cols-2">
      <article v-for="participant in debate.participants" :key="participant.agent_id" class="border border-white/10 bg-black/10 p-3">
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs font-semibold text-ink-primary">{{ agentName(participant.agent_id) }}</span>
          <span class="text-[10px]" :class="positionClass(participant.position)">{{ positionLabel(participant.position) }}</span>
        </div>
        <p class="mt-1.5 text-xs leading-relaxed text-ink-secondary">
          <template v-for="(part, index) in reasonParts(participant.reason)" :key="`${participant.agent_id}-${index}`">
            <strong v-if="part.emphasis" class="font-semibold text-ink-primary">{{ part.text }}</strong>
            <span v-else>{{ part.text }}</span>
          </template>
        </p>
        <p v-if="participant.recommendation" class="mt-2 text-xs leading-relaxed text-ink-primary">
          <span class="text-[10px] font-semibold text-ink-muted">主张</span>
          {{ participant.recommendation }}
        </p>
        <p v-if="participant.objection" class="mt-2 text-xs leading-relaxed text-amber-200">
          <span class="text-[10px] font-semibold text-ink-muted">保留</span>
          {{ participant.objection }}
        </p>
      </article>
    </div>

    <div class="mt-3 border-t border-white/10 pt-3">
      <p class="text-[10px] font-semibold text-ink-muted">裁判协调结论</p>
      <p v-if="debate.judge_summary" class="mt-1 text-xs leading-relaxed text-ink-primary">
        {{ debate.judge_summary }}
      </p>
      <p v-for="recommendation in debate.recommendations" :key="recommendation" class="mt-1 text-xs leading-relaxed text-ink-secondary">
        {{ recommendation }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.debate-pulse {
  animation: debate-pulse 1.6s ease-in-out infinite;
}

@keyframes debate-pulse {
  0%, 100% { opacity: 0.45; transform: translateX(-2px); }
  50% { opacity: 1; transform: translateX(2px); }
}
</style>
