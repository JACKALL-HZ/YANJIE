/** ECharts 深色辉光主题 — 对齐衍界设计 token */
export const YANJIE_DARK = {
  color: ['#4F8CFF', '#22D3EE', '#34D399', '#A78BFA', '#F87171', '#FBBF24'],
  backgroundColor: 'transparent',
  textStyle: { color: '#9AA6BC', fontFamily: '"Noto Sans SC", sans-serif' },
  title: { textStyle: { color: '#E6EAF2' } },
  grid: { borderColor: 'rgba(255,255,255,0.07)' },
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.14)' } },
    axisTick: { show: false },
    axisLabel: { color: '#6B7689', fontFamily: '"JetBrains Mono", monospace' },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#6B7689', fontFamily: '"JetBrains Mono", monospace' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
  },
  legend: { textStyle: { color: '#9AA6BC' } },
  tooltip: {
    backgroundColor: 'rgba(20,26,42,0.92)',
    borderColor: 'rgba(255,255,255,0.1)',
    textStyle: { color: '#E6EAF2', fontSize: 12 },
  },
}

/** 柱状图辉光样式 */
export const glowBar = (color: string) => ({
  itemStyle: {
    color: {
      type: 'linear' as const,
      x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [
        { offset: 0, color: `${color}dd` },
        { offset: 1, color: `${color}44` },
      ],
    },
    borderRadius: [4, 4, 0, 0],
  },
  emphasis: { itemStyle: { color } },
})

/** 折线辉光样式 */
export const glowLine = (color: string) => ({
  lineStyle: { color, width: 2, shadowColor: color, shadowBlur: 12 },
  itemStyle: { color },
  areaStyle: {
    color: {
      type: 'linear' as const,
      x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [
        { offset: 0, color: `${color}33` },
        { offset: 1, color: `${color}00` },
      ],
    },
  },
  emphasis: { focus: 'series' as const },
  smooth: true,
  symbol: 'circle',
  symbolSize: 6,
})
