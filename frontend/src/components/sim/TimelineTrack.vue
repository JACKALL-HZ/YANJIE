<script setup lang="ts">
import type { YearRecord } from '@/stores/simulation'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'

defineProps<{
  years: YearRecord[]
  currentYear: number
  running: boolean
}>()
</script>

<template>
  <div class="relative">
    <!-- 轨道线 -->
    <div class="absolute left-[15px] top-2 bottom-2 w-px bg-gradient-to-b from-brand/50 via-white/10 to-transparent" />

    <ol class="relative space-y-6">
      <li
        v-for="y in years"
        :key="y.year"
        class="relative flex gap-5 pl-1 animate-fade-up"
      >
        <!-- 节点 -->
        <div class="relative z-10 mt-1.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-brand/40 bg-surface-1 font-mono text-xs text-brand shadow-[0_0_16px_rgba(79,140,255,0.3)]">
          {{ y.year }}
        </div>

        <div class="glass flex-1 rounded-btn p-4">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <span class="text-sm font-medium text-ink-primary">第 {{ y.year }} 年</span>
            <span v-if="y.score != null" class="font-mono text-xs text-cyan-glow">
              评分 <AnimatedNumber :value="y.score" :decimals="1" />
            </span>
          </div>
          <div class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-secondary sm:grid-cols-3">
            <span>现金流 <AnimatedNumber :value="y.worldState.cash_flow / 10000" :decimals="1" prefix="¥" suffix="万" /></span>
            <span>月利润 <AnimatedNumber :value="y.worldState.monthly_profit / 10000" :decimals="1" prefix="¥" suffix="万" /></span>
            <span>回本率 <AnimatedNumber :value="y.worldState.payback_ratio * 100" suffix="%" /></span>
          </div>
        </div>
      </li>

      <!-- 进行中的年份 -->
      <li v-if="running" class="relative flex gap-5 pl-1">
        <div class="relative z-10 mt-1.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-cyan-glow/50 bg-surface-1">
          <span class="h-2 w-2 animate-pulse-soft rounded-full bg-cyan-glow" />
        </div>
        <div class="flex-1 rounded-btn border border-dashed border-white/10 p-4 text-sm text-ink-muted">
          第 {{ currentYear }} 年推演中…
        </div>
      </li>
    </ol>
  </div>
</template>
