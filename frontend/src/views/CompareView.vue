<script lang="ts">
export default { name: 'CompareView' }
</script>
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'
import ChartBox from '@/components/charts/ChartBox.vue'
import { glowBar, glowLine } from '@/components/charts/echarts-theme'
import { api, ApiRequestError } from '@/api/client'
import type { CompareResponse, DecisionVarDefinition, SimulationResponse } from '@/api/types'
import { useScenariosStore } from '@/stores/scenarios'
import {
  createDecisionValues,
  decisionHint,
  decisionLabel,
  type DecisionValues,
  toDecisionPayload,
} from '@/utils/decision-vars'

const scenarios = useScenariosStore()
const scenarioId = ref('')
const formA = ref<DecisionValues>({})
const formB = ref<DecisionValues>({})
const showParams = ref(true)
const showOptional = ref(false)
const loading = ref(false)
const formLoading = ref(false)
const errorMsg = ref<string | null>(null)
const result = ref<CompareResponse | null>(null)

const definitions = computed(() =>
  scenarios.current?.scenario_id === scenarioId.value
    ? scenarios.current.decision_vars
    : [],
)
const requiredDefinitions = computed(() => definitions.value.filter((definition) => definition.required))
const optionalDefinitions = computed(() => definitions.value.filter((definition) => !definition.required))
const plans = computed(() => [
  { key: 'A' as const, values: formA.value },
  { key: 'B' as const, values: formB.value },
])
const summary = computed(() => result.value?.comparison.summary ?? null)
const winner = computed(() => summary.value?.recommendation.winner ?? 'tie')
const canRun = computed(() =>
  !loading.value
  && !formLoading.value
  && definitions.value.length > 0
  && plans.value.every((plan) => requiredDefinitions.value.every((definition) => hasValue(plan.values[definition.name]))),
)

onMounted(async () => {
  if (scenarios.list.length === 0) await scenarios.fetchList()
  if (scenarios.list.length > 0) scenarioId.value = scenarios.list[0].scenario_id
})

watch(scenarioId, async (nextScenarioId) => {
  if (!nextScenarioId) return
  await loadScenario(nextScenarioId)
})

async function loadScenario(nextScenarioId: string) {
  formLoading.value = true
  errorMsg.value = null
  result.value = null
  showOptional.value = false
  try {
    await scenarios.fetchDetail(nextScenarioId)
    if (scenarios.current?.scenario_id !== nextScenarioId) {
      throw new Error('场景参数加载失败')
    }
    const defaults = createDecisionValues(scenarios.current.decision_vars)
    formA.value = { ...defaults }
    formB.value = { ...defaults }
  } catch (error) {
    formA.value = {}
    formB.value = {}
    errorMsg.value = (error as Error).message || '场景参数加载失败'
  } finally {
    formLoading.value = false
  }
}

function hasValue(value: string | number | undefined): boolean {
  return value !== undefined && value !== ''
}

function updateValue(
  plan: 'A' | 'B',
  definition: DecisionVarDefinition,
  rawValue: string,
) {
  const values = plan === 'A' ? formA.value : formB.value
  values[definition.name] = rawValue === ''
    ? ''
    : definition.value_type === 'string' ? rawValue : Number(rawValue)
}

function inputType(definition: DecisionVarDefinition) {
  return definition.value_type === 'string' ? 'text' : 'number'
}

async function run() {
  if (!canRun.value) return
  loading.value = true
  errorMsg.value = null
  result.value = null
  try {
    result.value = await api.post<CompareResponse>('/simulations/compare', {
      scenario_id: scenarioId.value,
      decision_vars_a: toDecisionPayload(definitions.value, formA.value),
      decision_vars_b: toDecisionPayload(definitions.value, formB.value),
    })
  } catch (error) {
    errorMsg.value = error instanceof ApiRequestError ? error.message : (error as Error).message
  } finally {
    loading.value = false
  }
}

function resultTag(state: SimulationResponse) {
  if (state.result === 'goal_reached') return { label: '目标达成', cls: 'text-agent-env bg-agent-env/10' }
  if (state.result === 'bankrupt') return { label: '资金断裂', cls: 'text-agent-risk bg-agent-risk/10' }
  if (state.result === 'timeout') return { label: '推演期结束', cls: 'text-ink-muted bg-white/5' }
  return { label: '稳步经营', cls: 'text-ink-secondary bg-white/5' }
}

function betterClass(plan: 'A' | 'B' | 'tie', target: 'A' | 'B') {
  if (plan === 'tie') return 'text-ink-secondary'
  return plan === target ? 'text-agent-env' : 'text-ink-secondary'
}

function risksFor(plan: 'A' | 'B') {
  return summary.value?.risks.filter((risk) => risk.plan === plan) ?? []
}

const compareChartOption = computed(() => {
  if (!result.value) return null
  const timelineA = result.value.a.timeline ?? []
  const timelineB = result.value.b.timeline ?? []
  const yearCount = Math.max(timelineA.length, timelineB.length)
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['A 现金储备', 'A 月利润', 'B 现金储备', 'B 月利润'], top: 0, textStyle: { color: '#9AA6BC', fontSize: 11 } },
    grid: { left: 12, right: 12, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: 'category' as const, data: Array.from({ length: yearCount }, (_, index) => `第 ${index + 1} 年`), axisLabel: { color: '#6B7689', fontSize: 10 } },
    yAxis: { type: 'value' as const, name: '万元', nameTextStyle: { color: '#6B7689' } },
    series: [
      { name: 'A 现金储备', type: 'line' as const, data: timelineA.map((year) => +(year.world_state.cash_flow / 10000).toFixed(2)), ...glowLine('#4F8CFF') },
      { name: 'A 月利润', type: 'line' as const, data: timelineA.map((year) => +(year.world_state.monthly_profit / 10000).toFixed(2)), ...glowLine('#7BAFFF'), lineStyle: { type: 'dashed' as const } },
      { name: 'B 现金储备', type: 'line' as const, data: timelineB.map((year) => +(year.world_state.cash_flow / 10000).toFixed(2)), ...glowLine('#22D3EE') },
      { name: 'B 月利润', type: 'line' as const, data: timelineB.map((year) => +(year.world_state.monthly_profit / 10000).toFixed(2)), ...glowLine('#5CE6FF'), lineStyle: { type: 'dashed' as const } },
    ],
  }
})

const scoreBarOption = computed(() => {
  if (!result.value) return null
  const labels: Record<string, string> = { market: '市场可行性', resource: '资源充足度', profitability: '盈利能力', risk: '风险抵御能力' }
  const detailA = result.value.a.score_detail ?? {}
  const detailB = result.value.b.score_detail ?? {}
  const keys = [...new Set([...Object.keys(detailA), ...Object.keys(detailB)])]
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['方案 A', '方案 B'], top: 0, textStyle: { color: '#9AA6BC', fontSize: 11 } },
    grid: { left: 12, right: 12, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: 'category' as const, data: keys.map((key) => labels[key] ?? '综合表现'), axisLabel: { color: '#6B7689', fontSize: 10 } },
    yAxis: { type: 'value' as const, nameTextStyle: { color: '#6B7689' } },
    series: [
      { name: '方案 A', type: 'bar' as const, data: keys.map((key) => detailA[key] ?? 0), ...glowBar('#4F8CFF') },
      { name: '方案 B', type: 'bar' as const, data: keys.map((key) => detailB[key] ?? 0), ...glowBar('#22D3EE') },
    ],
  }
})
</script>

<template>
  <div class="min-h-[100dvh]">
    <NavBar />
    <main class="mx-auto max-w-[1500px] px-5 pb-24 pt-24 md:px-8 md:pt-28">
      <p class="eyebrow mb-2">方案对比</p>
      <h1 class="font-display text-3xl font-bold tracking-tight md:text-4xl">分支对比</h1>
      <p class="mt-3 max-w-[580px] text-sm text-ink-secondary">同一场景、两套条件，查看哪条路径更符合你的目标和风险承受能力。</p>

      <div class="mt-8 flex flex-wrap items-center gap-4">
        <select v-model="scenarioId" :disabled="loading || formLoading" class="rounded-btn border border-white/10 bg-surface-1 px-4 py-2.5 text-sm outline-none focus:border-brand/50 disabled:opacity-50"><option value="" disabled>选择场景</option><option v-for="scenario in scenarios.list" :key="scenario.scenario_id" :value="scenario.scenario_id">{{ scenario.title }}</option></select>
        <FancyButton :disabled="!canRun" @click="run">{{ formLoading ? '加载参数中...' : loading ? '双路推演中...' : '开始对比' }}</FancyButton>
      </div>

      <div v-if="errorMsg" class="mt-6 rounded-btn border border-agent-risk/30 bg-agent-risk/10 px-4 py-3 text-sm text-agent-risk">{{ errorMsg }}</div>

      <section v-if="definitions.length" class="mt-8">
        <div class="mb-3 flex items-center justify-between gap-3"><div><h2 class="font-display text-lg font-bold text-ink-primary">对比条件</h2><p class="mt-1 text-xs text-ink-muted">两套方案可分别修改，必填条件需要完整填写。</p></div><button v-if="optionalDefinitions.length" class="border border-white/10 px-2.5 py-1 text-xs text-ink-secondary transition-colors hover:border-cyan-glow/40 hover:text-cyan-glow" @click="showOptional = !showOptional">{{ showOptional ? '收起可选条件' : `更多可选条件（${optionalDefinitions.length}）` }}</button></div>
        <div class="grid gap-5 lg:grid-cols-2">
          <GlassPanel v-for="plan in plans" :key="plan.key" :class="winner === plan.key ? 'border-brand/40' : ''">
            <div class="mb-4 flex items-center justify-between"><h3 class="font-display text-lg font-bold">方案 <span :class="plan.key === 'A' ? 'text-brand' : 'text-cyan-glow'">{{ plan.key }}</span></h3><span v-if="winner === plan.key" class="rounded-chip bg-brand/15 px-2 py-0.5 text-xs text-brand">推荐方案</span></div>
            <div class="grid gap-3 sm:grid-cols-2">
              <label v-for="definition in requiredDefinitions" :key="definition.name" class="block"><span class="mb-1 block text-[11px] text-ink-secondary">{{ decisionLabel(definition) }} <b class="font-normal text-agent-risk">*</b></span><input :value="plan.values[definition.name] ?? ''" :type="inputType(definition)" :min="definition.minimum ?? undefined" :max="definition.maximum ?? undefined" :disabled="loading" class="w-full rounded-btn border border-white/10 bg-surface-1 px-2.5 py-2 text-sm outline-none focus:border-brand/50 disabled:opacity-50" @input="updateValue(plan.key, definition, ($event.target as HTMLInputElement).value)" /><span v-if="decisionHint(definition)" class="mt-1 block text-[10px] text-ink-muted">{{ decisionHint(definition) }}</span></label>
            </div>
            <div v-if="showOptional && optionalDefinitions.length" class="mt-4 border-t border-white/5 pt-4"><p class="mb-3 text-[11px] text-ink-muted">可选条件</p><div class="grid gap-3 sm:grid-cols-2"><label v-for="definition in optionalDefinitions" :key="definition.name" class="block"><span class="mb-1 block text-[11px] text-ink-secondary">{{ decisionLabel(definition) }}</span><input :value="plan.values[definition.name] ?? ''" :type="inputType(definition)" :min="definition.minimum ?? undefined" :max="definition.maximum ?? undefined" :disabled="loading" class="w-full rounded-btn border border-white/10 bg-surface-1 px-2.5 py-2 text-sm outline-none focus:border-brand/50 disabled:opacity-50" @input="updateValue(plan.key, definition, ($event.target as HTMLInputElement).value)" /><span v-if="decisionHint(definition)" class="mt-1 block text-[10px] text-ink-muted">{{ decisionHint(definition) }}</span></label></div></div>
          </GlassPanel>
        </div>
      </section>

      <template v-if="result && summary">
        <GlassPanel strong class="mt-10 border-l-2 border-l-cyan-glow"><p class="text-xs text-ink-muted">推演建议</p><h2 class="mt-1 font-display text-2xl font-bold text-ink-primary">{{ summary.recommendation.title }}</h2><p class="mt-2 max-w-3xl text-sm leading-relaxed text-ink-secondary">{{ summary.recommendation.reason }}</p></GlassPanel>
        <div class="mt-5 grid gap-5 lg:grid-cols-2"><GlassPanel v-for="key in ['a', 'b'] as const" :key="key" strong :class="winner === key.toUpperCase() ? 'border-brand/50 glow-brand' : ''"><div class="flex items-baseline justify-between"><h3 class="font-display text-lg font-bold">方案 <span :class="key === 'a' ? 'text-brand' : 'text-cyan-glow'">{{ key.toUpperCase() }}</span></h3><span class="rounded-chip px-2.5 py-0.5 text-xs font-medium" :class="resultTag(result[key]).cls">{{ resultTag(result[key]).label }}</span></div><div class="mt-4 flex items-end justify-between"><div class="text-[10px] text-ink-muted">综合评分</div><div class="font-mono text-4xl font-bold" :class="key === 'a' ? 'text-brand' : 'text-cyan-glow'"><AnimatedNumber v-if="result[key].score != null" :value="result[key].score" :decimals="1" /><span v-else>暂未评分</span></div></div></GlassPanel></div>
        <div class="mt-8"><h3 class="mb-3 text-sm font-semibold text-ink-primary">关键推演指标</h3><GlassPanel class="overflow-x-auto p-0"><table class="w-full min-w-[680px] text-left text-sm"><thead class="border-b border-white/10 text-[11px] text-ink-muted"><tr><th class="px-4 py-3 font-medium">指标</th><th class="px-4 py-3 font-medium">方案 A</th><th class="px-4 py-3 font-medium">方案 B</th><th class="px-4 py-3 font-medium">差异</th><th class="px-4 py-3 font-medium">更占优</th></tr></thead><tbody><tr v-for="metric in summary.metrics" :key="metric.label" class="border-b border-white/5 last:border-0"><td class="px-4 py-3 text-ink-primary">{{ metric.label }}</td><td class="px-4 py-3 font-mono" :class="betterClass(metric.better, 'A')">{{ metric.a }}</td><td class="px-4 py-3 font-mono" :class="betterClass(metric.better, 'B')">{{ metric.b }}</td><td class="px-4 py-3 font-mono text-ink-secondary">{{ metric.delta }}</td><td class="px-4 py-3 text-xs text-ink-secondary">{{ metric.better === 'tie' ? '两者接近' : `方案 ${metric.better}` }}</td></tr></tbody></table></GlassPanel></div>
        <div v-if="compareChartOption" class="mt-8"><h3 class="mb-3 text-sm font-semibold text-ink-primary">现金储备与月利润走势</h3><GlassPanel class="min-h-[300px] p-4"><ChartBox :option="compareChartOption" /></GlassPanel></div>
        <div v-if="scoreBarOption" class="mt-8"><h3 class="mb-3 text-sm font-semibold text-ink-primary">评分维度对比</h3><GlassPanel class="min-h-[260px] p-4"><ChartBox :option="scoreBarOption" /></GlassPanel></div>
        <div class="mt-8 grid gap-5 lg:grid-cols-2"><GlassPanel v-for="plan in ['A', 'B'] as const" :key="plan"><h3 class="text-sm font-semibold" :class="plan === 'A' ? 'text-brand' : 'text-cyan-glow'">方案 {{ plan }} 的风险提示</h3><div class="mt-3 space-y-2"><div v-for="risk in risksFor(plan)" :key="risk.message" class="border border-agent-risk/20 bg-agent-risk/5 px-3 py-2.5"><p class="text-xs font-medium text-agent-risk">{{ risk.level }}风险</p><p class="mt-1 text-xs leading-relaxed text-ink-secondary">{{ risk.message }}</p></div></div></GlassPanel></div>
      </template>
    </main>
  </div>
</template>
