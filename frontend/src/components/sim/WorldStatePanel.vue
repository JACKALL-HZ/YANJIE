<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { StateMetricDefinition, WorldState } from '@/api/types'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'

const props = defineProps<{
  state: WorldState | null
  diff?: Record<string, number> | null
  scenarioId?: string
  metricDefinitions?: StateMetricDefinition[]
}>()

const flashTick = ref(0)
watch(
  () => [props.state, props.diff],
  () => { flashTick.value += 1 },
  { deep: true },
)

interface Metric {
  key: string
  sourceKey?: string
  label: string
  format: (v: number) => string
  formatDelta?: (v: number) => string
}

const startupMetrics: Metric[] = [
  { key: 'cash_flow', label: '现金流', format: (v) => `¥${fmt(v)}` },
  { key: 'monthly_profit', label: '月利润', format: (v) => `¥${fmt(v)}` },
  { key: 'customer_flow', label: '客流量', format: (v) => `${fmt(v)}` },
  { key: 'competition_count', label: '竞争数', format: (v) => `${v.toFixed(0)}` },
  { key: 'payback_ratio', label: '回本率', format: (v) => `${(v * 100).toFixed(1)}%` },
]

const generalStartupMetrics: Metric[] = [
  { key: 'cash_flow', label: '可用资金', format: (v) => `¥${fmt(v)}` },
  { key: 'monthly_profit', label: '月度净收益', format: (v) => `¥${fmt(v)}` },
  { key: 'customer_flow', label: '有效客户', format: (v) => `${fmt(v)}` },
  { key: 'competition_count', label: '市场竞争', format: (v) => `${v.toFixed(0)}` },
  { key: 'payback_ratio', label: '回报进度', format: (v) => `${(v * 100).toFixed(1)}%` },
]

const generalMetrics: Metric[] = [
  { key: 'cash_flow', label: '可用资源', format: (v) => `¥${fmt(v)}` },
  { key: 'payback_ratio', label: '目标进度', format: (v) => `${(v * 100).toFixed(1)}%` },
]

const metrics = computed(() => {
  if (props.metricDefinitions?.length) {
    return [...props.metricDefinitions]
      .sort((a, b) => a.display_order - b.display_order)
      .map((metric) => ({
        key: metric.metric_id,
        sourceKey: metric.source_metric || metric.metric_id,
        label: metric.label,
        format: (value: number) => formatDynamicMetric(value, metric.unit),
        formatDelta: (value: number) => formatDynamicDelta(value, metric.unit),
      }))
  }
  if (props.scenarioId === 'general_startup') return generalStartupMetrics
  return ['milktea_startup', 'restaurant_startup', 'retail_store', 'saas_startup']
    .includes(props.scenarioId || '')
    ? startupMetrics
    : generalMetrics
})

function fmt(v: number): string {
  if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(1)}万`
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function formatDynamicMetric(value: number, unit: string): string {
  if (unit === '元') return `¥${fmt(value)}`
  if (unit === '%') return `${fmt(Math.abs(value) <= 1 ? value * 100 : value)}%`
  return unit ? `${fmt(value)} ${unit}` : fmt(value)
}

function formatDynamicDelta(value: number, unit: string): string {
  const prefix = value >= 0 ? '+' : ''
  if (unit === '元') return `${prefix}¥${fmt(value)}`
  if (unit === '%') return `${prefix}${fmt(Math.abs(value) <= 1 ? value * 100 : value)}%`
  return `${prefix}${fmt(value)}${unit ? ` ${unit}` : ''}`
}

const items = computed(() =>
  metrics.value.map((m) => {
    const stateValues = props.state as unknown as Record<string, unknown> | null
    const rawValue = stateValues?.[m.sourceKey || m.key]
    const val = typeof rawValue === 'number' ? rawValue : props.state?.metrics?.[m.key] ?? 0
    const d = props.diff?.[m.sourceKey || m.key] ?? props.diff?.[m.key]
    return {
      ...m,
      raw: val,
      delta: d,
      deltaClass: d == null ? '' : d >= 0 ? 'text-agent-env' : 'text-agent-risk',
      deltaTone: d == null ? '' : d >= 0 ? 'metric-up' : 'metric-down',
      flashKey: `${m.key}-${flashTick.value}`,
      deltaText:
        d == null
          ? ''
          : m.formatDelta?.(d)
            ?? `${d >= 0 ? '+' : ''}${Math.abs(d) >= 10000 ? (d / 10000).toFixed(1) + '万' : d.toFixed(Math.abs(d) < 10 ? 1 : 0)}`,
    }
  }),
)
</script>

<template>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
    <template v-for="it in items" :key="it.flashKey">
      <div
        class="metric-cell glass rounded-btn px-4 py-3 transition-all duration-300"
        :class="it.deltaTone"
      >
        <div class="text-[11px] text-ink-muted">{{ it.label }}</div>
        <div class="mt-1 font-mono text-lg font-medium text-ink-primary tabular-nums">
          <AnimatedNumber v-if="state" :value="it.raw" :format="it.format" />
          <span v-else>—</span>
        </div>
        <div v-if="it.deltaText" class="mt-0.5 font-mono text-xs" :class="it.deltaClass">
          {{ it.deltaText }}
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.metric-up {
  animation: metric-up 900ms ease-out both;
}

.metric-down {
  animation: metric-down 900ms ease-out both;
}

@keyframes metric-up {
  0% { background-color: rgba(52, 211, 153, 0.22); transform: translateY(2px); }
  100% { background-color: rgba(255, 255, 255, 0.03); transform: translateY(0); }
}

@keyframes metric-down {
  0% { background-color: rgba(248, 113, 113, 0.24); transform: translateY(2px); }
  100% { background-color: rgba(255, 255, 255, 0.03); transform: translateY(0); }
}
</style>
