<script setup lang="ts">
import { computed } from 'vue'
import type { AgentAction, WorldState } from '@/api/types'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'

const props = defineProps<{
  actions: AgentAction[]
  running: boolean
  currentYear: number
  worldState: WorldState | null
  scenarioId?: string
}>()

interface AgentDef {
  id: string
  name: string
  emoji: string
  color: string
  bg: string
  border: string
  glow: string
  desc: string
}

const AGENTS: AgentDef[] = [
  {
    id: 'market', name: '市场智能体', emoji: '📊',
    color: '#4F8CFF', bg: 'rgba(79,140,255,0.08)', border: 'rgba(79,140,255,0.3)',
    glow: '0 0 24px rgba(79,140,255,0.2)', desc: '分析竞争格局与市场机会',
  },
  {
    id: 'environment', name: '环境智能体', emoji: '🌍',
    color: '#34D399', bg: 'rgba(52,211,153,0.08)', border: 'rgba(52,211,153,0.3)',
    glow: '0 0 24px rgba(52,211,153,0.2)', desc: '监控政策、经济与行业趋势',
  },
  {
    id: 'personal', name: '个人智能体', emoji: '🧠',
    color: '#A78BFA', bg: 'rgba(167,139,250,0.08)', border: 'rgba(167,139,250,0.3)',
    glow: '0 0 24px rgba(167,139,250,0.2)', desc: '评估你的资源、技能与执行能力',
  },
  {
    id: 'risk', name: '风险智能体', emoji: '🛡️',
    color: '#F87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.3)',
    glow: '0 0 24px rgba(248,113,113,0.2)', desc: '扫描潜在风险与脆弱点',
  },
]

const actionMap = computed(() => {
  const m: Record<string, AgentAction> = {}
  for (const a of props.actions) m[a.agent_id] = a
  return m
})

const strategyLabel = (s: string) =>
  ({ aggressive: '激进', steady: '稳健', conservative: '保守' } as Record<string, string>)[s] || s

function confidencePct(c: number): string {
  return `${(c * 100).toFixed(0)}%`
}

function positionCardClass(position?: AgentAction['position']): string {
  return ({
    support: 'border-l-2 border-l-agent-env',
    oppose: 'border-l-2 border-l-agent-risk',
    conditional: 'border-l-2 border-l-amber-300',
    neutral: 'border-l-2 border-l-white/20',
  } as Record<string, string>)[position || 'neutral']
}

function generationSourceLabel(source?: AgentAction['generation_source']): string {
  return ({
    llm: '\u6a21\u578b\u751f\u6210',
    stub: '\u672c\u5730\u89c4\u5219',
    fallback: '\u964d\u7ea7\u8bf4\u660e',
  } as Record<string, string>)[source || ''] || '\u751f\u6210\u65b9\u5f0f\u672a\u77e5'
}

function ragStatusLabel(status?: AgentAction['rag_status']): string {
  return ({
    hit: '\u77e5\u8bc6\u5e93\u5df2\u547d\u4e2d',
    empty: '\u672a\u68c0\u7d22\u5230\u76f8\u5173\u8d44\u6599',
    error: '\u77e5\u8bc6\u5e93\u6682\u4e0d\u53ef\u7528',
    disabled: '\u672a\u542f\u7528\u77e5\u8bc6\u5e93',
  } as Record<string, string>)[status || ''] || '\u77e5\u8bc6\u5e93\u72b6\u6001\u672a\u77e5'
}

function ragSourcesLabel(sources?: string[]): string {
  return `\u6765\u6e90\uff1a${sources?.join('\u3001') || ''}`
}

function positionLabel(position?: AgentAction['position']): string {
  return ({
    support: '支持方案',
    oppose: '反对方案',
    conditional: '有条件支持',
    neutral: '保持观察',
  } as Record<string, string>)[position || 'neutral'] || '保持观察'
}

function evidenceStatusLabel(status?: string): string {
  return ({
    hit: '已检索',
    local: '本地分析',
    empty: '无直接资料',
    error: '工具降级',
  } as Record<string, string>)[status || ''] || '未调用'
}

/* 世界状态聚焦指标 */
function focusMetric(agentId: string): {
  label: string
  value: number
  format: (value: number) => string
} | null {
  if (!props.worldState) return null
  const isGeneralStartup = props.scenarioId === 'general_startup'
  const isStartup = ['general_startup', 'milktea_startup', 'restaurant_startup', 'retail_store', 'saas_startup']
    .includes(props.scenarioId || '')
  if (!isStartup) return null
  const ws = props.worldState
  switch (agentId) {
    case 'market': return { label: isGeneralStartup ? '有效客户' : '客流量', value: ws.customer_flow, format: (value) => value.toFixed(0) }
    case 'environment': return { label: isGeneralStartup ? '市场竞争' : '竞争数', value: ws.competition_count, format: (value) => value.toFixed(0) }
    case 'personal': return { label: '现金流', value: ws.cash_flow, format: (value) => `¥${(value / 10000).toFixed(1)}万` }
    case 'risk': return { label: '回本率', value: ws.payback_ratio * 100, format: (value) => `${value.toFixed(0)}%` }
    default: return null
  }
}
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <div
      v-for="agent in AGENTS"
      :key="agent.id"
      class="group glass relative overflow-hidden rounded-card transition-all duration-500"
      :class="actionMap[agent.id] ? positionCardClass(actionMap[agent.id].position) : ''"
      :style="{
        borderColor: actionMap[agent.id] ? agent.border : 'rgba(255,255,255,0.07)',
        boxShadow: actionMap[agent.id] ? agent.glow : '',
      }"
    >
      <!-- Thinking 脉冲光晕 -->
      <div
        v-if="running && !actionMap[agent.id]"
        class="pointer-events-none absolute inset-0 animate-pulse-soft"
        :style="{ background: `radial-gradient(circle at 50% 30%, ${agent.color}15, transparent 70%)` }"
      />

      <!-- 头部 -->
      <div class="flex items-center gap-3 p-4 pb-2">
        <span class="text-xl">{{ agent.emoji }}</span>
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold text-ink-primary">{{ agent.name }}</div>
          <div class="text-[10px] text-ink-muted">{{ agent.desc }}</div>
        </div>
        <!-- 状态点 -->
        <span
          class="h-2.5 w-2.5 shrink-0 rounded-full transition-colors duration-500"
          :style="{
            backgroundColor: actionMap[agent.id] ? agent.color : 'rgba(255,255,255,0.15)',
            boxShadow: actionMap[agent.id] ? `0 0 8px ${agent.color}` : 'none',
          }"
        />
      </div>

      <div class="px-4 pb-4">
        <!-- 思考中 -->
        <div
          v-if="running && !actionMap[agent.id]"
          class="flex items-center gap-2 py-3 text-xs text-ink-muted"
        >
          <span class="flex gap-1">
            <span class="h-1 w-1 animate-pulse-soft rounded-full" :style="{ backgroundColor: agent.color }" />
            <span class="h-1 w-1 animate-pulse-soft rounded-full" :style="{ backgroundColor: agent.color, animationDelay: '0.2s' }" />
            <span class="h-1 w-1 animate-pulse-soft rounded-full" :style="{ backgroundColor: agent.color, animationDelay: '0.4s' }" />
          </span>
          正在分析第 {{ currentYear }} 年局势…
        </div>

        <!-- 有决策 -->
        <template v-if="actionMap[agent.id]">
          <div class="mb-2 flex items-center gap-2">
            <span
              class="inline-block rounded-chip px-2 py-0.5 text-[10px] font-medium"
              :style="{ backgroundColor: agent.bg, color: agent.color }"
            >
              {{ strategyLabel(actionMap[agent.id].yearly_strategy) }}
            </span>
            <span class="rounded-chip border border-white/10 px-2 py-0.5 text-[10px] text-ink-secondary">
              {{ positionLabel(actionMap[agent.id].position) }}
            </span>
          </div>

          <!-- 推理文字 -->
          <div class="mb-2 flex flex-wrap gap-1.5 text-[10px]">
            <span class="rounded-chip border border-white/10 px-2 py-0.5 text-ink-secondary">
              {{ generationSourceLabel(actionMap[agent.id].generation_source) }}
            </span>
            <span class="rounded-chip border border-white/10 px-2 py-0.5 text-ink-muted">
              {{ ragStatusLabel(actionMap[agent.id].rag_status) }}
            </span>
          </div>

          <dl class="space-y-2 text-xs leading-relaxed">
            <div>
              <dt class="text-[10px] font-semibold text-ink-muted">判断</dt>
              <dd class="mt-0.5 text-ink-primary">
                {{ actionMap[agent.id].recommendation || actionMap[agent.id].reason }}
              </dd>
            </div>
            <div>
              <dt class="text-[10px] font-semibold text-ink-muted">依据</dt>
              <dd class="mt-0.5 text-ink-secondary">
                {{ actionMap[agent.id].reason }}
              </dd>
            </div>
            <div v-if="actionMap[agent.id].key_factors?.length">
              <dt class="text-[10px] font-semibold text-ink-muted">关键依据</dt>
              <dd class="mt-0.5 space-y-1 text-ink-secondary">
                <p v-for="factor in actionMap[agent.id].key_factors" :key="factor">{{ factor }}</p>
              </dd>
            </div>
            <div v-if="actionMap[agent.id].next_actions?.length">
              <dt class="text-[10px] font-semibold text-ink-muted">今年先做</dt>
              <dd class="mt-0.5 space-y-1 text-ink-primary">
                <p v-for="nextAction in actionMap[agent.id].next_actions" :key="nextAction">{{ nextAction }}</p>
              </dd>
            </div>
            <div v-if="actionMap[agent.id].uncertainty">
              <dt class="text-[10px] font-semibold text-ink-muted">仍需确认</dt>
              <dd class="mt-0.5 text-amber-200">{{ actionMap[agent.id].uncertainty }}</dd>
            </div>
            <div v-if="actionMap[agent.id].alternatives?.length">
              <dt class="text-[10px] font-semibold text-ink-muted">备选方案</dt>
              <dd class="mt-0.5 text-ink-secondary">
                {{ actionMap[agent.id].alternatives!.join('；') }}
              </dd>
            </div>
            <div v-if="actionMap[agent.id].objection">
              <dt class="text-[10px] font-semibold text-ink-muted">保留意见</dt>
              <dd class="mt-0.5 text-amber-200">
                {{ actionMap[agent.id].objection }}
              </dd>
            </div>
            <div v-if="actionMap[agent.id].stop_condition">
              <dt class="text-[10px] font-semibold text-ink-muted">止损条件</dt>
              <dd class="mt-0.5 text-agent-risk">
                {{ actionMap[agent.id].stop_condition }}
              </dd>
            </div>
          </dl>
          <div v-if="actionMap[agent.id].evidence?.length" class="mt-2 space-y-1">
            <div v-for="item in actionMap[agent.id].evidence" :key="item.tool_name" class="text-[10px] text-ink-muted">
              {{ item.tool_name === 'search_knowledge' ? '知识库' : item.tool_name === 'assess_execution_capacity' ? '执行能力评估' : '风险压力测试' }} · {{ evidenceStatusLabel(item.status) }}
            </div>
          </div>
          <p
            v-if="actionMap[agent.id].rag_sources?.length"
            class="mt-2 truncate text-[10px] text-ink-muted"
          >
            {{ ragSourcesLabel(actionMap[agent.id].rag_sources) }}
          </p>

          <!-- 置信度条 -->
          <div class="mt-3 flex items-center gap-2">
            <div class="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                :key="`${agent.id}-${actionMap[agent.id].confidence}-${currentYear}`"
                class="progress-fill h-full rounded-full transition-all duration-700 ease-smooth"
                :style="{
                  '--progress': confidencePct(actionMap[agent.id].confidence),
                  backgroundColor: agent.color,
                }"
              />
            </div>
            <span class="font-mono text-[10px] text-ink-muted tabular-nums">
              <AnimatedNumber :value="actionMap[agent.id].confidence * 100" suffix="%" />
            </span>
          </div>

          <!-- 关注指标 -->
          <div
            v-if="focusMetric(agent.id)"
            class="mt-3 flex items-center justify-between rounded-btn px-3 py-1.5"
            :style="{ backgroundColor: agent.bg }"
          >
            <span class="text-[10px] text-ink-muted">{{ focusMetric(agent.id)!.label }}</span>
            <span class="font-mono text-xs font-medium" :style="{ color: agent.color }">
              <AnimatedNumber
                :value="focusMetric(agent.id)!.value"
                :format="focusMetric(agent.id)!.format"
              />
            </span>
          </div>
        </template>

        <!-- 无数据（初始态） -->
        <div
          v-if="!running && !actionMap[agent.id]"
          class="py-3 text-center text-xs text-ink-muted"
        >
          等待推演启动…
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-fill {
  width: 0;
  animation: confidence-in 800ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes confidence-in {
  to { width: var(--progress); }
}
</style>
