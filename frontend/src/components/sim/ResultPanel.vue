<script setup lang="ts">
import { computed } from 'vue'
import type { SimulationCompletedPayload } from '@/api/types'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'
import ScoreRadar from '@/components/charts/ScoreRadar.vue'

const props = defineProps<{ result: SimulationCompletedPayload }>()

const outcome = computed(() => {
  const r = props.result.result
  if (r === 'success') return { label: '推演成功', cls: 'text-agent-env', border: 'border-agent-env/30' }
  if (r === 'failure' || r === 'failed') return { label: '推演失败', cls: 'text-agent-risk', border: 'border-agent-risk/30' }
  if (r === 'user_ended') return { label: '已按你的要求结束', cls: 'text-ink-primary', border: 'border-brand/30' }
  return { label: '时间耗尽', cls: 'text-ink-secondary', border: 'border-white/15' }
})

const scoreEntries = computed(() =>
  Object.entries(props.result.score_detail || {}).map(([k, v]) => ({
    key: k,
    label: ({
      market: '机会与环境',
      resource: '资源余量',
      profitability: '结果质量',
      risk: '风险控制',
    } as Record<string, string>)[k] || k,
    value: v,
  })),
)

const settlementRows = computed(() =>
  Object.entries(props.result.startup_settlement?.financial_table || {}).map(([label, value]) => ({
    label,
    value: label === '回本进度' ? Number(value) * 100 : Number(value),
    isPercent: label === '回本进度',
  })),
)
</script>

<template>
  <GlassPanel strong :class="['border', outcome.border]">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <p class="eyebrow mb-2">推演完成</p>
        <h3 class="font-display text-2xl font-bold" :class="outcome.cls">
          {{ outcome.label }}
        </h3>
      </div>
      <div v-if="result.score != null" class="text-right">
        <div class="text-[11px] text-ink-muted">综合评分</div>
        <div class="font-mono text-4xl font-bold text-cyan-glow tabular-nums">
          <AnimatedNumber :value="result.score" :decimals="1" />
        </div>
      </div>
    </div>

    <div v-if="settlementRows.length" class="mt-6">
      <h4 class="mb-3 text-sm font-semibold text-cyan-glow">创业财务总表</h4>
      <div class="grid grid-cols-2 gap-px overflow-hidden rounded-btn border border-white/10 bg-white/10 md:grid-cols-3">
        <div v-for="row in settlementRows" :key="row.label" class="bg-surface/95 px-3 py-2.5">
          <p class="text-[10px] text-ink-muted">{{ row.label }}</p>
          <p class="mt-1 font-mono text-sm text-ink-primary tabular-nums">
            <AnimatedNumber :value="row.value" :decimals="row.isPercent ? 2 : 0" :suffix="row.isPercent ? '%' : ' 元'" />
          </p>
        </div>
      </div>
    </div>

    <!-- 评分雷达 -->
    <div v-if="scoreEntries.length" class="mt-6 grid gap-6 md:grid-cols-[1fr_280px]">
      <div class="grid grid-cols-2 content-start gap-3">
        <div v-for="s in scoreEntries" :key="s.key" class="rounded-btn bg-white/[0.03] px-3 py-2">
          <div class="text-[10px] uppercase tracking-wider text-ink-muted">{{ s.label }}</div>
          <div class="font-mono text-sm text-ink-primary tabular-nums">
            <AnimatedNumber :value="s.value" :decimals="1" />
          </div>
        </div>
      </div>
      <div class="min-h-[240px]">
        <ScoreRadar :score-detail="result.score_detail" />
      </div>
    </div>

    <!-- 风险 -->
    <div v-if="result.risks?.length" class="mt-6">
      <h4 class="mb-3 text-sm font-semibold text-agent-risk">风险清单</h4>
      <ul class="space-y-2">
        <li
          v-for="(r, i) in result.risks"
          :key="i"
          class="rounded-btn border border-agent-risk/15 bg-agent-risk/5 px-4 py-2.5 text-xs leading-relaxed"
        >
          <div class="flex items-start justify-between gap-3">
            <span class="text-ink-secondary">{{ r.message || r.title || r.name || JSON.stringify(r) }}</span>
            <span v-if="r.severity != null" class="shrink-0 rounded-chip px-2 py-0.5 font-mono text-[10px]" :class="Number(r.severity) > 0.5 ? 'bg-agent-risk/15 text-agent-risk' : 'bg-yellow-500/10 text-yellow-400'">
              {{ (Number(r.severity) * 100).toFixed(0) }}%
            </span>
          </div>
          <div v-if="r.current_value != null" class="mt-1 text-[10px] text-ink-muted">
            当前值：{{ typeof r.current_value === 'number' ? r.current_value.toLocaleString() : r.current_value }}
          </div>
        </li>
      </ul>
    </div>

    <!-- 行动计划 -->
    <div v-if="result.action_plan?.length" class="mt-6">
      <h4 class="mb-3 text-sm font-semibold text-agent-env">行动计划</h4>
      <ol class="space-y-2">
        <li
          v-for="(a, i) in result.action_plan"
          :key="i"
          class="flex gap-3 rounded-btn border border-white/8 bg-white/[0.02] px-4 py-2.5 text-xs"
        >
          <span class="mt-0.5 font-mono text-cyan-glow">{{ String(i + 1).padStart(2, '0') }}</span>
          <div class="min-w-0">
            <div class="text-ink-secondary">{{ a.action || a.title || JSON.stringify(a) }}</div>
            <div class="mt-1 flex gap-3 text-[10px] text-ink-muted">
              <span v-if="a.quantity">{{ a.quantity }}</span>
              <span v-if="a.deadline" class="text-ink-muted/60">{{ a.deadline }}</span>
            </div>
          </div>
        </li>
      </ol>
    </div>
  </GlassPanel>
</template>
