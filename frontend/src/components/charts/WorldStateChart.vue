<script setup lang="ts">
/** WorldStateChart — 现金流 / 月利润 随年份变化辉光折线 */
import { computed } from 'vue'
import ChartBox from './ChartBox.vue'
import { glowLine } from './echarts-theme'
import type { StateMetricDefinition, WorldState } from '@/api/types'
import type { YearRecord } from '@/stores/simulation'

const props = defineProps<{
  years: YearRecord[]
  metricDefinitions?: StateMetricDefinition[]
  selectedMetricId?: string
}>()

interface ChartMetric {
  key: string
  sourceKey: string
  label: string
  unit: string
  color: string
}

const legacyMetrics: ChartMetric[] = [
  { key: 'cash_flow', sourceKey: 'cash_flow', label: '现金流', unit: '万元', color: '#4F8CFF' },
  { key: 'monthly_profit', sourceKey: 'monthly_profit', label: '月利润', unit: '万元', color: '#22D3EE' },
]

function valueFor(state: WorldState, metric: ChartMetric): number {
  const direct = (state as unknown as Record<string, unknown>)[metric.sourceKey]
  return typeof direct === 'number' ? direct : state.metrics?.[metric.key] ?? 0
}

const chartMetrics = computed(() =>
  props.metricDefinitions?.length
    ? props.metricDefinitions.map((metric, index): ChartMetric => ({
        key: metric.metric_id,
        sourceKey: metric.source_metric || metric.metric_id,
        label: metric.label,
        unit: metric.unit,
        color: ['#4F8CFF', '#22D3EE', '#A78BFA', '#F59E0B', '#34D399'][index % 5],
      }))
    : legacyMetrics,
)

const activeMetric = computed(() =>
  chartMetrics.value.find((metric) => metric.key === props.selectedMetricId)
  || chartMetrics.value[0],
)

function chartValue(state: WorldState, metric: ChartMetric) {
  const raw = valueFor(state, metric)
  if (metric.unit === '%' || metric.unit === '％') return +(raw * 100).toFixed(2)
  return +raw.toFixed(2)
}

function chartUnit(metric: ChartMetric) {
  return metric.unit
}

const option = computed(() => {
  const xs = props.years.map((y) => `Y${y.year}`)
  return {
    tooltip: {
      trigger: 'axis' as const,
      valueFormatter: (value: string | number) => `${Number(value).toLocaleString('zh-CN')} ${chartUnit(activeMetric.value!)}`,
    },
    legend: { show: false },
    grid: { left: 12, right: 12, top: 36, bottom: 8, containLabel: true },
    xAxis: { type: 'category' as const, data: xs, boundaryGap: false },
    yAxis: {
      type: 'value' as const,
      name: activeMetric.value ? `${activeMetric.value.label}（${chartUnit(activeMetric.value)}）` : '',
    },
    series: activeMetric.value ? [{
      name: activeMetric.value.label,
      type: 'line' as const,
      data: props.years.map((year) => chartValue(year.worldState, activeMetric.value)),
      ...glowLine(activeMetric.value.color),
    }] : [],
  }
})

const snapshotValue = computed(() => {
  if (!props.years.length || !activeMetric.value) return '--'
  return chartValue(props.years[props.years.length - 1].worldState, activeMetric.value).toLocaleString('zh-CN')
})
</script>

<template>
  <div v-if="years.length < 2" class="flex min-h-[240px] flex-col justify-center border-l-2 border-cyan-glow/60 px-6">
    <p class="text-xs text-ink-muted">第 {{ years[0]?.year }} 年 · {{ activeMetric?.label }}</p>
    <p class="mt-2 font-mono text-3xl font-semibold text-ink-primary tabular-nums">
      {{ snapshotValue }} <span class="text-base text-cyan-glow">{{ activeMetric ? chartUnit(activeMetric) : '' }}</span>
    </p>
    <p class="mt-3 text-xs leading-relaxed text-ink-secondary">当前只有一个年度结果，趋势会在后续年度形成后显示。</p>
  </div>
  <ChartBox v-else :option="option" />
</template>
