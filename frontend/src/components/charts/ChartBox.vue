<script setup lang="ts">
/** ChartBox — ECharts 通用容器：初始化、resize、主题注入、销毁清理 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, RadarChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import { YANJIE_DARK } from './echarts-theme'

echarts.use([
  LineChart,
  RadarChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
])

const props = defineProps<{ option: EChartsCoreOption }>()
const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let ro: ResizeObserver | null = null

function render() {
  if (!chart) return
  chart.setOption({ ...YANJIE_DARK, ...props.option }, true)
}

onMounted(() => {
  if (!el.value) return
  chart = echarts.init(el.value)
  render()
  ro = new ResizeObserver(() => chart?.resize())
  ro.observe(el.value)
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  ro?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" class="h-full min-h-[240px] w-full" role="img" aria-label="数据图表" />
</template>
