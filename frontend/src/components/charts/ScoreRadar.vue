<script setup lang="ts">
/** ScoreRadar — 评分明细雷达图 */
import { computed } from 'vue'
import ChartBox from './ChartBox.vue'

const props = defineProps<{ scoreDetail: Record<string, number> }>()

const option = computed(() => {
  const entries = Object.entries(props.scoreDetail || {})
  return {
    radar: {
      indicator: entries.map(([k]) => ({
        name: k.replace(/_/g, ' '),
        max: 100,
      })),
      radius: '68%',
      axisName: { color: '#9AA6BC', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      splitArea: { show: false },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    },
    series: [
      {
        type: 'radar' as const,
        data: [
          {
            value: entries.map(([, v]) => v),
            name: '评分维度',
            areaStyle: { color: 'rgba(79,140,255,0.18)' },
            lineStyle: {
              color: '#4F8CFF',
              width: 2,
              shadowColor: '#4F8CFF',
              shadowBlur: 14,
            },
            itemStyle: { color: '#22D3EE' },
          },
        ],
      },
    ],
  }
})
</script>

<template>
  <ChartBox :option="option" />
</template>
