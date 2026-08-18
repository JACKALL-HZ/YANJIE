<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import { api, ApiRequestError } from '@/api/client'
import type { ScenarioDetail } from '@/api/types'

const route = useRoute()
const router = useRouter()

const query = ref((route.query.query as string) || '')
const phase = ref<'loading' | 'result' | 'error' | 'idle'>('idle')
const errorMsg = ref<string | null>(null)
const scenarioDetail = ref<ScenarioDetail | null>(null)
const result = reactive({
  scenario_id: '',
  extracted_vars: {} as Record<string, string>,
  missing_required: [] as string[],
  suggestions: '',
})

/* 可编辑变量副本 */
const editedVars = ref<Record<string, string>>({})

/* 场景 title 映射（从路由 query 或后续 fetch） */
const scenarioTitle = computed(() => {
  return scenarioDetail.value?.title || (result.scenario_id ? '已识别场景' : '尚未识别场景')
})

/* 变量中文标签映射 */
function labelOf(key: string): string {
  const definition = scenarioDetail.value?.decision_vars.find(item => item.name === key)
  if (definition) return definition.label
  const map: Record<string, string> = {
    budget: '启动资金（元）',
    city: '城市',
    industry: '行业',
    span_years: '推演年数',
    competition_level: '竞争烈度',
    location: '地段',
    team_size: '团队规模',
    price_strategy: '定价策略',
  }
  return map[key] || '决策条件'
}

/* 类型推断输入框类型 */
function inputTypeOf(key: string): string {
  const valueType = scenarioDetail.value?.decision_vars.find(item => item.name === key)?.value_type
  if (valueType === 'integer' || valueType === 'number') return 'number'
  if (key === 'budget') return 'number'
  if (key === 'span_years') return 'number'
  return 'text'
}

function placeholderOf(key: string): string {
  if (key === 'budget') return '如：200000'
  if (key === 'span_years') return '如：3'
  if (key === 'city') return '如：杭州'
  return ''
}

const hasMissing = computed(() => result.missing_required.length > 0)
const hasVars = computed(() => Object.keys(editedVars.value).length > 0)

async function runBreakdown() {
  if (!query.value.trim()) return
  phase.value = 'loading'
  errorMsg.value = null
  try {
    const data = await api.breakdown(query.value.trim())
    result.scenario_id = data.scenario_id || ''
    result.extracted_vars = (data.extracted_vars || {}) as Record<string, string>
    result.missing_required = data.missing_required || []
    result.suggestions = data.suggestions || ''
    scenarioDetail.value = result.scenario_id
      ? await api.get<ScenarioDetail>(`/scenarios/${result.scenario_id}`)
      : null

    /* 初始化可编辑副本 */
    editedVars.value = { ...result.extracted_vars }
    phase.value = 'result'
  } catch (e) {
    errorMsg.value = e instanceof ApiRequestError ? e.message : (e as Error).message
    phase.value = 'error'
  }
}

function updateVar(key: string, value: string) {
  editedVars.value = { ...editedVars.value, [key]: value }
}

function startSim() {
  /* 把 editedVars 编码为 query string 传入 sim 页 */
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(editedVars.value)) {
    if (v != null && v !== '') params.set(k, String(v))
  }
  router.push({
    name: 'sim',
    params: { scenarioId: result.scenario_id },
    query: Object.fromEntries(params),
  })
}

onMounted(() => {
  if (query.value.trim()) runBreakdown()
})
</script>

<template>
  <div class="min-h-[100dvh]">
    <NavBar />

    <main class="relative mx-auto max-w-[720px] px-5 pb-24 pt-28 md:px-8 md:pt-36">
      <div class="relative z-10">
        <p class="eyebrow mb-4">AI 拆解</p>
        <h1 class="font-display text-3xl font-bold tracking-tight md:text-4xl">
          AI 理解你的处境
        </h1>

        <!-- 用户原始输入引用 -->
        <blockquote class="mt-4 rounded-card border-l-4 border-brand/60 bg-white/[0.03] px-5 py-4 text-sm italic leading-relaxed text-ink-secondary">
          "{{ query }}"
        </blockquote>

        <!-- Loading 态 -->
        <div v-if="phase === 'loading'" class="mt-10 space-y-5">
          <div class="flex items-center gap-4 text-sm text-ink-muted">
            <span class="flex gap-1">
              <span class="h-2 w-2 animate-pulse-soft rounded-full bg-brand" />
              <span class="h-2 w-2 animate-pulse-soft rounded-full bg-brand" style="animation-delay:0.15s" />
              <span class="h-2 w-2 animate-pulse-soft rounded-full bg-brand" style="animation-delay:0.3s" />
            </span>
            AI 正在解析你的描述…
          </div>
          <GlassPanel>
            <div class="space-y-4">
              <div class="skeleton h-5 w-2/3" />
              <div class="skeleton h-4 w-1/2" />
              <div class="skeleton h-10 w-full" />
              <div class="skeleton h-10 w-full" />
              <div class="skeleton h-10 w-3/4" />
            </div>
          </GlassPanel>
        </div>

        <!-- Error 态 -->
        <div v-else-if="phase === 'error'" class="mt-10">
          <GlassPanel class="text-center">
            <p class="text-sm text-agent-risk">{{ errorMsg }}</p>
            <p class="mt-2 text-xs text-ink-muted">请确认后端服务已启动（uvicorn app.main:app）</p>
            <div class="mt-6 flex justify-center gap-3">
              <FancyButton @click="runBreakdown">重试</FancyButton>
              <FancyButton variant="ghost" @click="router.push('/library')">浏览场景库</FancyButton>
            </div>
          </GlassPanel>
        </div>

        <!-- Idle（无 query 直接进页） -->
        <div v-else-if="phase === 'idle'" class="mt-10">
          <GlassPanel class="text-center">
            <p class="text-sm text-ink-muted">请从首页输入你的决策描述，或直接浏览场景库。</p>
            <div class="mt-6 flex justify-center">
              <FancyButton variant="ghost" @click="router.push('/library')">浏览场景库</FancyButton>
            </div>
          </GlassPanel>
        </div>

        <!-- 结果态 -->
        <div v-else class="mt-10 space-y-6">
          <!-- 场景匹配 -->
          <GlassPanel>
            <div class="flex items-center gap-3">
              <span class="rounded-chip border border-cyan-glow/25 bg-cyan-glow/10 px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-cyan-glow">
                场景匹配
              </span>
              <span class="text-sm font-medium text-ink-primary">{{ scenarioTitle }}</span>
            </div>
          </GlassPanel>

          <!-- 拆解变量 -->
          <GlassPanel v-if="hasVars" strong>
            <h2 class="mb-5 text-sm font-semibold text-ink-primary">AI 提取的决策变量</h2>
            <div class="grid gap-4 sm:grid-cols-2">
              <div
                v-for="(value, key) in editedVars"
                :key="key"
                class="space-y-1.5"
              >
                <label class="text-xs text-ink-muted">{{ labelOf(String(key)) }}</label>
                <input
                  :type="inputTypeOf(String(key))"
                  :value="value"
                  :placeholder="placeholderOf(String(key))"
                  class="w-full rounded-btn border border-white/10 bg-surface-1 px-3 py-2.5 font-mono text-sm text-ink-primary outline-none transition-colors focus:border-brand/50"
                  @input="updateVar(String(key), ($event.target as HTMLInputElement).value)"
                />
              </div>
            </div>
          </GlassPanel>

          <!-- 缺失必填项 -->
          <GlassPanel v-if="hasMissing" class="border-l-4 border-agent-risk/50">
            <h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-agent-risk">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" />
                <path d="M12 8v4m0 4h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              </svg>
              还需要补充的信息
            </h2>
            <p class="text-sm leading-relaxed text-ink-secondary whitespace-pre-line">{{ result.suggestions }}</p>
          </GlassPanel>

          <!-- CTA -->
          <div v-if="result.scenario_id" class="flex flex-col items-center gap-4 pt-4">
            <FancyButton size="lg" @click="startSim">
              确认并开始推演
            </FancyButton>
            <button
              class="text-xs text-ink-muted transition-colors hover:text-ink-secondary"
              @click="router.push('/library')"
            >
              或者先浏览场景库了解更多
            </button>
          </div>
          <p v-else class="pt-4 text-center text-sm text-ink-muted">
            {{ result.suggestions || '请补充你想做的事情、目标以及时间或预算等信息。' }}
          </p>
        </div>
      </div>
    </main>
  </div>
</template>
