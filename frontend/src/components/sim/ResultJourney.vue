<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { StateMetricDefinition } from '@/api/types'
import type { YearRecord } from '@/stores/simulation'

const props = withDefaults(defineProps<{
  years: YearRecord[]
  metricDefinitions?: StateMetricDefinition[]
}>(), {
  metricDefinitions: () => [],
})

const selectedIndex = ref(0)

watch(
  () => props.years.length,
  (length) => {
    selectedIndex.value = Math.max(0, length - 1)
  },
  { immediate: true },
)

const selectedYear = computed(() => props.years[selectedIndex.value] ?? null)

const metricMap = computed(() => {
  const entries = new Map<string, StateMetricDefinition>()
  for (const metric of props.metricDefinitions) {
    entries.set(metric.metric_id, metric)
    if (metric.source_metric) entries.set(metric.source_metric, metric)
  }
  return entries
})

const fallbackLabels: Record<string, string> = {
  cash_flow: '现金流',
  customer_flow: '有效客户',
  competition_count: '市场竞争',
  monthly_profit: '月度净收益',
  payback_ratio: '回报进度',
}

function metricLabel(key: string) {
  return metricMap.value.get(key)?.label || fallbackLabels[key] || key
}

function metricUnit(key: string) {
  return metricMap.value.get(key)?.unit || (key === 'payback_ratio' ? '%' : '')
}

function scaleValue(value: number, key: string) {
  return metricUnit(key) === '%' ? value * 100 : value
}

function formatValue(value: number, key: string, withSign = false) {
  const scaled = scaleValue(value, key)
  const sign = withSign && scaled > 0 ? '+' : ''
  const unit = metricUnit(key)
  if (unit === '元' && Math.abs(scaled) >= 10000) {
    return `${sign}${(scaled / 10000).toFixed(1)}万`
  }
  const fraction = Math.abs(scaled) < 10 && scaled % 1 !== 0 ? 1 : 0
  return `${sign}${scaled.toLocaleString('zh-CN', { maximumFractionDigits: fraction })}${unit ? ` ${unit}` : ''}`
}

const priority = ['monthly_profit', 'cash_flow', 'payback_ratio', 'customer_flow', 'competition_count']

const selectedDiffs = computed(() => {
  if (!selectedYear.value) return []
  return Object.entries(selectedYear.value.stateDiff || {})
    .filter(([, value]) => Number.isFinite(value) && value !== 0)
    .sort(([leftKey, leftValue], [rightKey, rightValue]) => {
      const leftPriority = priority.indexOf(leftKey)
      const rightPriority = priority.indexOf(rightKey)
      if (leftPriority !== rightPriority) {
        return (leftPriority === -1 ? 99 : leftPriority) - (rightPriority === -1 ? 99 : rightPriority)
      }
      return Math.abs(rightValue) - Math.abs(leftValue)
    })
    .slice(0, 4)
    .map(([key, value]) => ({ key, label: metricLabel(key), value, text: formatValue(value, key, true) }))
})

const selectedInterventions = computed(() => {
  if (!selectedYear.value) return []
  return selectedYear.value.interventions
    .map((record) => {
      const text = [record.event, record.choice, record.selected_option, record.description, record.message]
        .find((value): value is string => typeof value === 'string' && value.trim().length > 0)
      return text || ''
    })
    .filter(Boolean)
})

function impactValue(key: string, value: number) {
  return key === 'competition_count' ? -value : value
}

function toneFor(year: YearRecord) {
  const meaningful = Object.entries(year.stateDiff || {})
    .filter(([key]) => priority.includes(key))
    .map(([key, value]) => impactValue(key, value))
  const score = meaningful.reduce((total, value) => total + Math.sign(value), 0)
  if (score > 0) return { label: '结果改善', className: 'border-agent-env/45 bg-agent-env/10 text-agent-env' }
  if (score < 0) return { label: '压力上升', className: 'border-agent-risk/45 bg-agent-risk/10 text-agent-risk' }
  return { label: '继续观察', className: 'border-amber-400/35 bg-amber-400/10 text-amber-300' }
}

function primaryDecision(year: YearRecord) {
  const action = year.agentActions.find((item) => item.agent_id === 'personal') || year.agentActions[0]
  return action?.recommendation || action?.reason || '本年度按既定计划推进'
}

const selectedTone = computed(() => selectedYear.value ? toneFor(selectedYear.value) : null)
</script>

<template>
  <section v-if="years.length" aria-label="年度结果复盘">
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="eyebrow mb-1">结果复盘</p>
        <h2 class="text-lg font-semibold text-ink-primary">每一年，发生了什么</h2>
      </div>
      <span class="text-xs text-ink-muted">{{ years.length }} 个推演节点</span>
    </div>

    <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" role="tablist" aria-label="选择年度结果">
      <button
        v-for="(year, index) in years"
        :key="year.year"
        type="button"
        role="tab"
        :aria-selected="selectedIndex === index"
        class="min-h-[108px] border p-4 text-left transition-colors duration-200 focus-visible:outline-none"
        :class="selectedIndex === index ? toneFor(year).className : 'border-white/10 bg-black/15 text-ink-secondary hover:border-white/25 hover:bg-white/[0.04]'"
        @click="selectedIndex = index"
      >
        <div class="flex items-start justify-between gap-3">
          <span class="font-mono text-xs">第 {{ year.year }} 年</span>
          <span class="text-[11px]" :class="selectedIndex === index ? '' : 'text-ink-muted'">{{ toneFor(year).label }}</span>
        </div>
        <p class="mt-4 line-clamp-2 text-sm font-medium leading-relaxed text-ink-primary">
          {{ primaryDecision(year) }}
        </p>
      </button>
    </div>

    <div v-if="selectedYear && selectedTone" class="mt-4 border-l-2 px-4 py-4" :class="selectedTone.className">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p class="text-xs font-medium" :class="selectedTone.className.split(' ').slice(-1)[0]">{{ selectedTone.label }}</p>
          <h3 class="mt-1 text-base font-semibold text-ink-primary">第 {{ selectedYear.year }} 年的结果</h3>
        </div>
        <span v-if="selectedYear.businessDashboard?.['本年决策']" class="max-w-full text-right text-xs text-ink-secondary">
          {{ selectedYear.businessDashboard['本年决策'] }}
        </span>
      </div>

      <div v-if="selectedDiffs.length" class="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        <span v-for="diff in selectedDiffs" :key="diff.key" class="text-xs text-ink-secondary">
          {{ diff.label }}
          <b class="ml-1 font-mono font-medium" :class="impactValue(diff.key, diff.value) >= 0 ? 'text-agent-env' : 'text-agent-risk'">{{ diff.text }}</b>
        </span>
      </div>

      <div class="mt-5 grid gap-5 lg:grid-cols-2">
        <div v-if="selectedYear.agentActions.length">
          <p class="mb-2 text-[11px] font-semibold text-ink-muted">本年执行判断</p>
          <ul class="space-y-2">
            <li v-for="action in selectedYear.agentActions" :key="action.agent_id" class="text-xs leading-relaxed text-ink-secondary">
              <span class="mr-2 font-medium text-ink-primary">{{ action.agent_id === 'market' ? '市场' : action.agent_id === 'environment' ? '环境' : action.agent_id === 'personal' ? '个人' : '风险' }}</span>
              {{ action.recommendation || action.reason }}
            </li>
          </ul>
        </div>
        <div v-if="selectedInterventions.length">
          <p class="mb-2 text-[11px] font-semibold text-ink-muted">本年关键处置</p>
          <ul class="space-y-2">
            <li v-for="(intervention, index) in selectedInterventions" :key="`${index}-${intervention}`" class="text-xs leading-relaxed text-ink-secondary">
              {{ intervention }}
            </li>
          </ul>
        </div>
        <div v-if="selectedYear.debate?.judge_summary || selectedYear.debate?.recommendations?.length">
          <p class="mb-2 text-[11px] font-semibold text-ink-muted">协调结论</p>
          <p v-if="selectedYear.debate.judge_summary" class="text-xs leading-relaxed text-ink-secondary">{{ selectedYear.debate.judge_summary }}</p>
          <p v-for="recommendation in selectedYear.debate.recommendations" :key="recommendation" class="mt-2 text-xs leading-relaxed text-cyan-glow">{{ recommendation }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
