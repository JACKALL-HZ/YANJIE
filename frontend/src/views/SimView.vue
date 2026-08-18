<script lang="ts">
export default { name: 'SimView' }
</script>
<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import WorldStatePanel from '@/components/sim/WorldStatePanel.vue'
import ResultPanel from '@/components/sim/ResultPanel.vue'
import WorldStateChart from '@/components/charts/WorldStateChart.vue'
import ResultJourney from '@/components/sim/ResultJourney.vue'
import ShipLoader from '@/components/motion/ShipLoader.vue'
import AgentPanel from '@/components/sim/AgentPanel.vue'
import DebatePanel from '@/components/sim/DebatePanel.vue'
import ProfileBar from '@/components/sim/ProfileBar.vue'
import ChatBubble from '@/components/chat/ChatBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import OnboardingChat from '@/components/chat/OnboardingChat.vue'
import { streamAsk } from '@/api/sse'
import { useScenariosStore } from '@/stores/scenarios'
import { useSimulationStore } from '@/stores/simulation'
import { api, ApiRequestError } from '@/api/client'
import type { AgentAction, DebateRecord, SessionDetail, StateMetricDefinition, TimelineNode } from '@/api/types'

const route = useRoute()
const router = useRouter()
const scenarios = useScenariosStore()
const sim = useSimulationStore()

const scenarioId = ref<string>((route.params.scenarioId as string) || '')
const extractedVars = ref<Record<string, unknown> | null>(null)  // OnboardingChat 提取的变量
const resumeBusy = ref(false)
const chatInput = ref('')
const chatBusy = ref(false)
const showCharts = ref(false)
const selectedMetricId = ref('')
const showShipLoader = ref(false)
const decisionPromptYear = ref<number | null>(null)
const onboardingRef = ref<{ getHistory: () => OnboardingHistoryItem[] } | null>(null)
const onboardingState = ref({ hasRecognizedInput: false, ready: false })

const MIN_LOADER_DISPLAY_MS = 1_500
let loaderVisibleAt = 0
let loaderDismissTimer: ReturnType<typeof setTimeout> | null = null

function clearLoaderDismissTimer() {
  if (loaderDismissTimer) {
    clearTimeout(loaderDismissTimer)
    loaderDismissTimer = null
  }
}

function hideShipLoaderImmediately() {
  clearLoaderDismissTimer()
  showShipLoader.value = false
  loaderVisibleAt = 0
}

function resetSimulation() {
  hideShipLoaderImmediately()
  sim.reset()
}

watch(() => sim.phase, (phase) => {
  if (phase === 'connecting' || phase === 'running') {
    clearLoaderDismissTimer()
    if (!showShipLoader.value) {
      loaderVisibleAt = Date.now()
      showShipLoader.value = true
    }
    return
  }
  if (!showShipLoader.value) return

  const remaining = Math.max(0, MIN_LOADER_DISPLAY_MS - (Date.now() - loaderVisibleAt))
  loaderDismissTimer = setTimeout(hideShipLoaderImmediately, remaining)
}, { immediate: true })

onBeforeUnmount(hideShipLoaderImmediately)

const legacyResultMetrics: StateMetricDefinition[] = [
  { metric_id: 'cash_flow', label: '可用资金', unit: '元', initial_value: 0, display_order: 1, source_metric: 'cash_flow' },
  { metric_id: 'monthly_profit', label: '月度净收益', unit: '元', initial_value: 0, display_order: 2, source_metric: 'monthly_profit' },
  { metric_id: 'customer_flow', label: '有效客户', unit: '个', initial_value: 0, display_order: 3, source_metric: 'customer_flow' },
  { metric_id: 'competition_count', label: '市场竞争', unit: '分', initial_value: 0, display_order: 4, source_metric: 'competition_count' },
  { metric_id: 'payback_ratio', label: '回报进度', unit: '%', initial_value: 0, display_order: 5, source_metric: 'payback_ratio' },
]

const resultMetrics = computed(() =>
  scenarios.current?.state_metrics?.length
    ? scenarios.current.state_metrics
    : legacyResultMetrics,
)

watch(resultMetrics, (metrics) => {
  if (!metrics.some((metric) => metric.metric_id === selectedMetricId.value)) {
    selectedMetricId.value = metrics[0]?.metric_id || ''
  }
}, { immediate: true })

/* 仅使用用户确认的参数。场景默认值只用于右侧的参考展示。 */
let cachedVars: Record<string, unknown> | null = null
function buildDecisionVars(): Record<string, unknown> {
  if (cachedVars) return cachedVars
  const vars: Record<string, unknown> = {}
  const detail = scenarios.current?.scenario_id === scenarioId.value
    ? scenarios.current
    : null
  const allowedKeys = new Set(detail?.decision_vars.map(item => item.name) || [])

  // 1. OnboardingChat 提取的变量
  if (extractedVars.value) {
    for (const [key, value] of Object.entries(extractedVars.value)) {
      if (!detail || allowedKeys.has(key)) vars[key] = value
    }
  }

  // 2. URL query 参数（从场景库跳转带入）
  for (const [k, v] of Object.entries(route.query)) {
    if (detail && allowedKeys.has(k) && !(k in vars) && v != null && v !== '') {
      vars[k] = isNaN(Number(v)) ? v : Number(v)
    }
  }

  cachedVars = vars
  return vars
}

const budget = computed(() => Number(buildDecisionVars().budget || buildDecisionVars().investment_amount || 200000))
const city = computed(() => String(buildDecisionVars().city || '杭州'))
const spanYears = computed(() => Number(buildDecisionVars().span_years || buildDecisionVars().prep_months || 3))

interface ChatMsg { id: number; role: 'user' | 'agent' | 'system'; agentId?: string; content: string; typing?: boolean }
interface OnboardingHistoryItem { role: 'user' | 'agent'; agentId: string; content: string }
const chatMessages = ref<ChatMsg[]>([])
let msgSeq = 0
const chatRef = ref<HTMLDivElement | null>(null)
const restoringSession = ref(false)
const ACTIVE_SESSION_KEY = 'yanjie_active_simulation_v1'

interface PersistedWorkspace {
  sessionId: string
  scenarioId: string
  messages: Array<Omit<ChatMsg, 'id'>>
}

function clearPersistedWorkspace() {
  localStorage.removeItem(ACTIVE_SESSION_KEY)
}

function persistWorkspace() {
  if (!sim.sessionId || !scenarioId.value) return
  const snapshot: PersistedWorkspace = {
    sessionId: sim.sessionId,
    scenarioId: scenarioId.value,
    messages: chatMessages.value.map(({ role, agentId, content, typing }) => ({
      role,
      agentId,
      content,
      typing,
    })),
  }
  localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(snapshot))
}

function resetScenarioWorkspace(clearPersisted = true) {
  resetSimulation()
  scenarioId.value = ''
  extractedVars.value = null
  cachedVars = null
  chatInput.value = ''
  chatMessages.value = []
  msgSeq = 0
  showCharts.value = false
  resumeBusy.value = false
  chatBusy.value = false
  decisionPromptYear.value = null
  onboardingRef.value = null
  onboardingState.value = { hasRecognizedInput: false, ready: false }
  if (clearPersisted) clearPersistedWorkspace()
}

let routeSyncToken = 0
async function syncScenarioFromRoute(rawRouteName: unknown, rawScenarioId: unknown) {
  if (rawRouteName !== 'sim') return

  const nextScenarioId = typeof rawScenarioId === 'string' ? rawScenarioId : ''
  const activeScenarioChanged =
    nextScenarioId !== scenarioId.value ||
    (nextScenarioId !== '' && sim.scenarioId !== null && sim.scenarioId !== nextScenarioId)

  if (activeScenarioChanged) {
    resetScenarioWorkspace(!restoringSession.value)
    scenarioId.value = nextScenarioId
  }

  const token = ++routeSyncToken
  if (!nextScenarioId) {
    scenarios.clearCurrent()
    cachedVars = null
    return
  }

  scenarios.clearCurrent()
  await scenarios.fetchDetail(nextScenarioId)
  if (token === routeSyncToken) cachedVars = null
}

function addChat(role: ChatMsg['role'], content: string, agentId = '') {
  chatMessages.value.push({ id: ++msgSeq, role, agentId, content })
}

function formatBusinessDashboard(year: number, board: import('@/api/types').BusinessDashboard): string {
  const warning = board.风险预警?.length
    ? `\n风险提示：${board.风险预警.join('；')}`
    : ''
  return [
    `第 ${year} 年经营结算`,
    `本年决策：${board.本年决策 || '未记录'}`,
    `日均单量：${board.日均单量.toFixed(2)} 单`,
    `月营收：¥${board.月营收.toFixed(2)}｜月成本：¥${board.月成本.toFixed(2)}`,
    `月净利润：¥${board.月净利润.toFixed(2)}｜剩余现金：¥${board.剩余现金流.toFixed(2)}`,
    `回本进度：${(board.回本进度 * 100).toFixed(1)}%${warning}`,
  ].join('\n')
}

async function scrollChat() {
  await nextTick()
  if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
}

onMounted(async () => {
  if (scenarios.list.length === 0) await scenarios.fetchList()
  await restorePersistedWorkspace()
})

async function restorePersistedWorkspace() {
  const raw = localStorage.getItem(ACTIVE_SESSION_KEY)
  if (!raw || sim.sessionId) return

  let saved: PersistedWorkspace
  try {
    saved = JSON.parse(raw) as PersistedWorkspace
  } catch {
    clearPersistedWorkspace()
    return
  }
  if (!saved.sessionId || !saved.scenarioId) {
    clearPersistedWorkspace()
    return
  }
  const routeScenarioId = typeof route.params.scenarioId === 'string'
    ? route.params.scenarioId
    : ''
  if (routeScenarioId && routeScenarioId !== saved.scenarioId) return

  restoringSession.value = true
  try {
    if (routeScenarioId !== saved.scenarioId) {
      await router.replace({ name: 'sim', params: { scenarioId: saved.scenarioId } })
    }
    await scenarios.fetchDetail(saved.scenarioId)
    const detail = await api.get<SessionDetail>(`/sessions/${saved.sessionId}`)
    scenarioId.value = detail.scenario_id
    extractedVars.value = detail.decision_vars
    cachedVars = null
    chatMessages.value = saved.messages.map((message) => ({
      ...message,
      id: ++msgSeq,
    }))
    if (chatMessages.value.length === 0) {
      chatMessages.value = detail.messages.map((message) => ({
        id: ++msgSeq,
        role: message.role,
        agentId: message.agent_id || '',
        content: message.content,
      }))
    }
    sim.restoreSession(detail)
    hydrateTimelineMessages(detail.timeline)
    await scrollChat()
  } catch {
    clearPersistedWorkspace()
  } finally {
    await nextTick()
    restoringSession.value = false
  }
}

watch(
  [() => sim.sessionId, () => scenarioId.value, chatMessages],
  () => persistWorkspace(),
  { deep: true },
)

watch(
  () => [route.name, route.params.scenarioId] as const,
  ([routeName, rawScenarioId]) => {
    void syncScenarioFromRoute(routeName, rawScenarioId)
  },
  { immediate: true },
)

/* KeepAlive 激活时：恢复聊天滚动位置 */
onActivated(() => {
  if (chatRef.value && chatMessages.value.length > 0) {
    nextTick(() => {
      if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
    })
  }
})

/* ── 推演流程 ───────────────────────────────────── */
const canStart = computed(() => !!scenarioId.value
  && !sim.isLive
  && (sim.phase !== 'idle' || onboardingState.value.ready))

function start(vars?: Record<string, unknown>, initialHistory?: OnboardingHistoryItem[]) {
  if (!canStart.value) return
  if (vars) { extractedVars.value = vars; cachedVars = null }
  const history = initialHistory ?? onboardingRef.value?.getHistory() ?? []
  chatMessages.value = history.map((message) => ({
    id: ++msgSeq,
    role: message.role,
    agentId: message.agentId,
    content: message.content,
  }))
  addChat('system', '🚀 推演引擎启动…四个智能体正在分析你的决策场景')
  sim.start({
    scenario_id: scenarioId.value,
    decision_vars: buildDecisionVars(),
    conversation_history: history.map((message) => ({
      role: message.role,
      agent_id: message.agentId || null,
      content: message.content,
    })),
  })
}

/* ── 监听 SSE 事件 → 聊天消息 ────────────────────── */
function handleOnboardingStart(
  vars: Record<string, unknown>,
  sid: string,
  history: OnboardingHistoryItem[],
) {
  scenarioId.value = sid
  onboardingState.value = { hasRecognizedInput: true, ready: true }
  start(vars as unknown as Record<string, unknown>, history)
  if (route.params.scenarioId !== sid) {
    void router.replace({
      name: 'sim',
      params: { scenarioId: sid },
      query: Object.fromEntries(
        Object.entries(vars)
          .filter(([, value]) => value != null && value !== '')
          .map(([key, value]) => [key, String(value)]),
      ),
    })
  }
}

function handleOnboardingReadiness(state: {
  hasRecognizedInput: boolean
  ready: boolean
  vars: Record<string, unknown>
}) {
  onboardingState.value = {
    hasRecognizedInput: state.hasRecognizedInput,
    ready: state.ready,
  }
  extractedVars.value = state.vars
  cachedVars = null
}

watch(() => sim.currentYear, (year) => {
  if (restoringSession.value) return
  if (year > 0 && sim.isLive) {
    addChat('system', `📅 第 ${year} 年开始 — 智能体正在观察世界状态并生成策略…`)
    scrollChat()
  }
})

watch(() => sim.initialAnalysis, (analysis) => {
  if (restoringSession.value) return
  if (analysis) {
    addChat('agent', analysis, 'guide')
    scrollChat()
  }
})

watch(() => sim.years.length, (len, prev) => {
  if (restoringSession.value) return
  if (len > (prev || 0)) {
    const latest = sim.years[len - 1]
    addChat('system', `✅ 第 ${latest.year} 年结算完成`)
    if (latest.businessDashboard) {
      addChat(
        'system',
        formatBusinessDashboard(latest.year, latest.businessDashboard),
      )
    }
    for (const action of latest.agentActions) {
      appendAgentMessage(action.agent_id, formatAgentAction(action))
    }
    if (latest.debate) {
      appendAgentMessage('guide', formatDebate(latest.debate))
    }
    scrollChat()
  }
})

watch(() => sim.pending, (p) => {
  if (restoringSession.value) return
  if (p) {
    addChat('agent', `⚠️ **关键决策点**：${p.event}\n\n请告诉我你的选择，我会把它投入下一年的推演。`, 'risk')
    scrollChat()
  }
})

/* 逐年交互模式：暂停时提示用户输入 */
watch(() => sim.pauseReason, (reason) => {
  if (restoringSession.value) return
  if (reason === 'horizon_review') {
    addChat('agent', `已完成你设定的第 ${sim.currentYear} 年推演。你可以继续推演，或按当前结果完成结算。`, 'personal')
    scrollChat()
  }
})

watch(
  [() => sim.pauseReason, () => sim.currentYear, () => sim.pending],
  ([pauseReason, year, pending]) => {
    if (restoringSession.value) return
    if (
      pauseReason === 'year_decision_required'
      && !pending
      && decisionPromptYear.value !== year
    ) {
      decisionPromptYear.value = year
      const summary = personalDecisionSummary.value
      addChat(
        'agent',
        year === 0
          ? '初步分析已完成。请提交第 1 年的关键行动决策，四个智能体会据此展开推演。'
          : summary
            ? `第 ${year} 年推演完成。${summary}\n\n你可以从建议中选择下一步，也可以直接输入自己的决策。`
            : `第 ${year} 年推演完成。请选择下一步，或直接输入自己的决策。`,
        'personal',
      )
      scrollChat()
    }
  },
)

watch(() => sim.finalResult, (r) => {
  if (restoringSession.value) return
  if (r) {
    addChat('system', `🏁 推演结束 — 结局：${resultLabel(r.result)} · 综合评分 ${r.score?.toFixed(1) || '—'}`)
    showCharts.value = true
    scrollChat()
  }
})

watch(() => sim.errorMsg, (e) => {
  if (e && sim.phase === 'failed') { addChat('system', `❌ 推演出错：${e}`); scrollChat() }
})

/* ── 用户发送消息 ──────────────────────────────── */
async function handleUserSend(text: string, displayText = text) {
  addChat('user', displayText)
  await scrollChat()

  // 暂停中：服务端统一分类，前端不再猜测用户意图。
  if ((sim.phase === 'paused' || sim.phase === 'horizon_review') && sim.sessionId) {
    const phaseBeforeResume = sim.phase
    const pauseReasonBeforeResume = sim.pauseReason
    const isYearlyDecision = sim.pauseReason === 'year_decision_required'
    const submittedYear = sim.currentYear + 1
    resumeBusy.value = true
    if (isYearlyDecision) {
      sim.phase = 'running'
      addChat(
        'system',
        `第 ${submittedYear} 年推演进行中：四个智能体正在根据你的行动决策分析影响。`,
      )
      await scrollChat()
    }
    try {
      const resp = await api.post<import('@/api/types').SimulationResponse>(
        `/simulations/${sim.sessionId}/resume`,
        { choice: text },
      )
      sim.applyResponse(resp)
      hydrateTimelineMessages(resp.timeline)
      if (resp.input_feedback) addChat('agent', resp.input_feedback, 'guide')
      // 年度续推的 HTTP 响应不是 SSE 事件，主动完成聊天区的渲染收尾。
      persistWorkspace()
      await scrollChat()
    } catch (e) {
      sim.phase = phaseBeforeResume
      sim.pauseReason = pauseReasonBeforeResume
      sim.errorMsg = (e as Error).message
      let feedback = '这次决策暂时没有提交成功，请稍后重试。'
      if (e instanceof ApiRequestError && e.status === 409) {
        try {
          const current = await api.get<{ phase: string; year: number }>(
            `/simulations/${sim.sessionId}/state`,
          )
          const currentPhase = current.phase
          if (currentPhase === 'simulating') {
            sim.phase = 'running'
          } else if (['idle', 'connecting', 'running', 'paused', 'horizon_review', 'completed', 'failed'].includes(currentPhase)) {
            sim.phase = currentPhase as typeof sim.phase
          }
          sim.currentYear = current.year
          feedback = currentPhase === 'completed'
            ? '上一条决策已结束本次推演，不能再继续提交新的行动决策。'
            : currentPhase === 'simulating'
              ? '上一条决策仍在处理，请等待本轮结果生成后再提交。'
              : '推演状态已同步，请根据当前页面提示继续操作。'
        } catch {
          feedback = '推演状态发生变化，暂时无法同步。请刷新页面后再继续。'
        }
      } else if (e instanceof ApiRequestError && e.status === 422) {
        feedback = '这条决策暂时无法识别，请换成具体动作后再提交。'
      } else if (e instanceof ApiRequestError && e.status >= 500) {
        feedback = '推演服务暂时出错，当前决策未生效，请稍后重试。'
      }
      addChat('agent', feedback, 'guide')
      await scrollChat()
    } finally {
      resumeBusy.value = false
    }
    return
  }

  // 推演完成后的追问：SSE 流式逐字输出
  if (sim.phase === 'completed' && sim.sessionId) {
    chatBusy.value = true
    const msgId = ++msgSeq
    chatMessages.value.push({ id: msgId, role: 'agent', agentId: 'guide', content: '' })
    scrollChat()
    try {
      await streamAsk(
        sim.sessionId,
        text,
        (token) => {
          const idx = chatMessages.value.findIndex(m => m.id === msgId)
          if (idx >= 0) chatMessages.value[idx].content += token
          scrollChat()
        },
        () => { /* onDone */ },
        (err) => {
          const idx = chatMessages.value.findIndex(m => m.id === msgId)
          if (idx >= 0) chatMessages.value[idx].content = `抱歉，连接失败：${err.message}`
        },
      )
    } catch (e) {
      const idx = chatMessages.value.findIndex(m => m.id === msgId)
      if (idx >= 0) chatMessages.value[idx].content = `抱歉，请求失败：${(e as Error).message}`
    } finally {
      chatBusy.value = false
      await scrollChat()
    }
    return
  }

  // 推演前可修改参数
  if (sim.phase === 'idle') {
    addChat('agent', '推演还未启动。你可以调整左侧参数后点击「启动推演」，或继续描述你的需求。', 'guide')
    await scrollChat()
  }
}

function chooseIntervention(option: string) {
  handleUserSend(option)
}

function previewRiskLabel(level: string) {
  return ({ low: '较低', medium: '中等', high: '较高' } as Record<string, string>)[level] || '待评估'
}

/* ── 工具函数 ───────────────────────────────────── */
function strategyLabel(s: string) {
  return ({ aggressive: '激进', steady: '稳健', conservative: '保守' } as Record<string, string>)[s] || s
}

function formatAgentAction(action: AgentAction): string {
  const sections = [
    `判断：${action.recommendation || action.reason}`,
    `依据：${action.reason}`,
  ]
  if (action.alternatives?.length) {
    sections.push(`备选：${action.alternatives.join('；')}`)
  }
  if (action.objection) sections.push(`保留意见：${action.objection}`)
  if (action.stop_condition) sections.push(`止损条件：${action.stop_condition}`)
  sections.push(`置信度 ${(action.confidence * 100).toFixed(0)}% · 策略：${strategyLabel(action.yearly_strategy)}`)
  return sections.join('\n\n')
}

function formatDebate(debate: DebateRecord): string {
  const focus = debate.conflicts.join('；')
  const recommendation = debate.judge_summary || debate.recommendations.join('；')
  return `观点分歧：${focus}\n\n综合建议：${recommendation}`
}

function appendAgentMessage(agentId: string, content: string) {
  const alreadyShown = chatMessages.value.some(
    (message) => message.role === 'agent'
      && message.agentId === agentId
      && message.content === content,
  )
  if (!alreadyShown) addChat('agent', content, agentId)
}

function hydrateTimelineMessages(timeline: TimelineNode[]) {
  for (const node of timeline) {
    for (const action of node.agent_actions || []) {
      appendAgentMessage(action.agent_id, formatAgentAction(action))
    }
    if (node.debate) appendAgentMessage('guide', formatDebate(node.debate))
  }
}

function resultLabel(r: string) {
  return ({ goal_reached: '目标达成 🎉', steady: '平稳收尾', bankrupt: '资金断裂 💸', timeout: '时间耗尽 ⏰', user_ended: '用户主动结束' } as Record<string, string>)[r] || r
}
function cityLabel(c: string) {
  return ({ hangzhou: '杭州', shanghai: '上海', beijing: '北京', shenzhen: '深圳', guangzhou: '广州', chengdu: '成都', wuhan: '武汉', nanjing: '南京', changsha: '长沙', chongqing: '重庆', xian: '西安', hefei: '合肥', fuzhou: '福州', xiamen: '厦门' } as Record<string, string>)[c] || c
}

function displayDecisionValue(key: string, value: unknown): string {
  if (value == null || value === '') return '—'
  if (['budget', 'investment_amount', 'income', 'salary_expectation'].includes(key)) {
    return `${Number(value).toLocaleString()} 元`
  }
  if (key === 'city') return cityLabel(String(value))
  const labels: Record<string, string> = {
    milk_tea: '奶茶', coffee: '咖啡', catering: '餐饮', restaurant: '餐饮',
    retail: '零售', saas: '软件服务',
    conservative: '保守', balanced: '均衡', aggressive: '激进',
  }
  return labels[String(value)] || String(value)
}

function displayParameterValue(definition: Record<string, unknown>): string {
  const key = String(definition.name)
  const value = buildDecisionVars()[key]
  if (value != null && value !== '') return displayDecisionValue(key, value)

  const example = definition.default
  return example != null && example !== ''
    ? `待补充（示例：${displayDecisionValue(key, example)}）`
    : '待补充'
}

function formatPreviewMetric(
  metric: { metric_id: string; label: string; unit: string; source_metric?: string | null },
  worldState: Record<string, unknown>,
): string {
  const sourceKey = metric.source_metric || metric.metric_id
  const sourceValue = worldState[sourceKey]
  const metricValue = (worldState.metrics as Record<string, unknown> | undefined)?.[metric.metric_id]
  const value = typeof sourceValue === 'number'
    ? sourceValue
    : typeof metricValue === 'number' ? metricValue : 0
  if (metric.unit === '元') return `¥${value.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
  if (metric.unit === '%') {
    const percent = Math.abs(value) <= 1 ? value * 100 : value
    return `${percent.toFixed(1)}%`
  }
  return `${value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })} ${metric.unit}`
}

/* ── 状态标签 ───────────────────────────────────── */
const pausePrompt = computed(() => {
  switch (sim.pauseReason) {
    case 'year_decision_required':
      return sim.currentYear === 0
        ? '输入第 1 年的关键行动决策，例如：制定每周学习计划并安排首次模考…'
        : '输入下一年的关键行动决策，例如：根据模考结果调整复习重点…'
    case 'decision_preview_required':
      return '请从右侧选择一个方案后继续推演'
    case 'intervention_required':
      return '请从右侧选择风险处置方案'
    case 'horizon_review':
      return '请选择继续推演或按当前结果完成结算'
    default:
      return ''
  }
})

const statusText = computed(() => {
  switch (sim.phase) {
    case 'idle': return '待启动'
    case 'connecting': return '连接中…'
    case 'running': return '推演中'
    case 'paused':
      return ({
        year_decision_required: '等待年度决策',
        decision_preview_required: '等待方案确认',
        intervention_required: '等待风险处置',
      } as Record<string, string>)[sim.pauseReason || ''] || '等待你的决策'
    case 'horizon_review': return '等待续推确认'
    case 'completed': return '已完成'
    case 'failed': return '失败'
  }
})
const statusClass = computed(() => {
  switch (sim.phase) {
    case 'running': return 'text-cyan-glow border-cyan-glow/40 bg-cyan-glow/10'
    case 'paused': return 'text-agent-risk border-agent-risk/40 bg-agent-risk/10'
    case 'horizon_review': return 'text-agent-env border-agent-env/40 bg-agent-env/10'
    case 'completed': return 'text-agent-env border-agent-env/40 bg-agent-env/10'
    case 'failed': return 'text-agent-risk border-agent-risk/40 bg-agent-risk/10'
    default: return 'text-ink-muted border-white/10 bg-white/5'
  }
})

const latestActions = computed(() => {
  if (!sim.years.length) return []
  return sim.years[sim.years.length - 1].agentActions || []
})
const latestDebate = computed(() => {
  if (!sim.years.length) return null
  return sim.years[sim.years.length - 1].debate || null
})

type PersonalDecisionOption = {
  id: string
  title: string
  description: string
  decision: string
}

function latestActionFor(agentId: AgentAction['agent_id']) {
  return latestActions.value.find(action => action.agent_id === agentId)
}

const actionLabelFallbacks: Record<string, string> = {
  differentiate: '测试差异化产品或服务',
  hold: '先小范围验证再扩大投入',
  localize: '调整本地化运营方案',
  monitor: '持续监测外部变化',
  stabilize: '梳理资源分工和执行节奏',
  defer: '暂缓不可逆投入',
  contain: '设置预算上限和止损线',
  insure: '补齐合规和风险保障',
  analyze_trend: '分析目标趋势并调整方向',
  adjust_target: '调整目标难度或范围',
  monitor_policy: '跟踪政策变化',
  adapt_plan: '调整执行计划和时间分配',
  intensive_study: '增加集中投入和执行时长',
  balanced_plan: '保持均衡且可持续的执行节奏',
  early_warning: '提前识别风险信号',
  prepare_planb: '准备可切换的备选方案',
  track_price: '跟踪价格走势和入场时机',
  compare_regions: '比较不同区域方案',
  monitor_loan: '关注贷款条件变化',
  analyze_policy: '核查政策资格和交易成本',
  optimize_budget: '优化预算和现金流安排',
  increase_income: '增加收入来源',
  stress_test: '进行最坏情景压力测试',
  diversify_assets: '分散资产风险',
  analyze_sector: '分析行业板块机会',
  timing_signal: '优化投入和退出时机',
  track_macro: '跟踪宏观经济指标',
  policy_arbitrage: '根据政策变化调整策略',
  balance_portfolio: '调整资产配置比例',
  increase_capital: '追加投入扩大收益基数',
  set_stoploss: '设置单笔投入止损线',
  hedge_tailrisk: '对冲极端风险',
  scan_opportunities: '扫描外部发展机会',
  build_reputation: '建立专业影响力',
  map_politics: '梳理关键决策关系',
  align_strategy: '对齐个人目标和组织目标',
  close_gap: '弥补关键能力差距',
  showcase_value: '展示工作成果和可见价值',
  assess_jobhop: '评估跳槽机会和代价',
  prevent_burnout: '调整工作节奏避免过劳',
  target_hot_roles: '针对目标岗位投递',
  broaden_search: '扩大求职范围',
  track_economy: '跟踪就业环境变化',
  identify_growth: '寻找高增长细分领域',
  upskill: '学习目标岗位紧缺技能',
  network_referral: '争取内推和面试机会',
  vet_employer: '核查雇主背景和岗位风险',
  negotiate_salary: '谈判薪资和福利条件',
}

function actionDescription(action?: AgentAction): string {
  if (!action) return ''
  const description = scenarios.current?.action_descriptions?.[action.action_id] || action.reason
  if (/[\u4e00-\u9fff]/.test(description)) return description
  const suffix = action.action_id.split('.').pop() || action.action_id
  return actionLabelFallbacks[suffix] || '执行该智能体提出的具体方案'
}

const personalDecisionSummary = computed(() => {
  const personal = latestActionFor('personal')
  if (!personal) return ''

  const recommendation = actionDescription(personal)
    .replace(/\s+/g, ' ')
    .split(/[。！？]/)[0]
    .slice(0, 90)
  return `综合本年的市场、环境和风险判断，下一步建议：${recommendation}。`
})

const personalDecisionOptions = computed<PersonalDecisionOption[]>(() => {
  const market = latestActionFor('market')
  const environment = latestActionFor('environment')
  const personal = latestActionFor('personal')
  const risk = latestActionFor('risk')
  if (!personal) return []

  const dashboard = sim.years.length
    ? sim.years[sim.years.length - 1].businessDashboard
    : null
  if (dashboard?.风险预警?.length) {
    return [
      {
        id: 'startup-stop-loss',
        title: '收缩止损',
        description: '停止新增投入，压缩营业时段，优先保住剩余现金。',
        decision: '我选择收缩止损，停止新增投入并压缩营业时段。',
      },
      {
        id: 'startup-transfer-close',
        title: '转让或闭店',
        description: '停止继续消耗现金，评估转让、清算库存和退出成本。',
        decision: '我选择转让或闭店，停止继续投入并评估退出成本。',
      },
    ]
  }

  return [
    {
      id: 'personal-recommendation',
      title: '执行个人智能体建议',
      description: actionDescription(personal),
      decision: `我决定先执行：${actionDescription(personal)}`,
    },
    {
      id: 'market-growth',
      title: '执行增长方案',
      description: `${actionDescription(market) || '验证市场机会'} 同时${actionDescription(environment) || '观察外部条件'}`,
      decision: `我决定执行增长方案：${actionDescription(market)}；同时${actionDescription(environment)}`,
    },
    {
      id: 'risk-control',
      title: '执行稳健方案',
      description: `${actionDescription(risk) || '控制投入并设置止损线'} 同时${actionDescription(personal)}`,
      decision: `我决定按稳健方案推进：${actionDescription(risk)}；同时${actionDescription(personal)}`,
    },
  ]
})
const parameterTitle = computed(() => (
  onboardingState.value.hasRecognizedInput ? '当前推演参数' : '示例参数'
))
const parameterHint = computed(() => {
  if (!scenarioId.value) return '先描述你的决策场景，系统会识别所需参数。'
  return onboardingState.value.hasRecognizedInput
    ? '以下为系统识别到的本次推演参数。'
    : '以下为场景参考示例，输入你的实际情况后会更新。'
})
</script>

<template>
  <div class="min-h-[100dvh]">
    <ShipLoader v-if="showShipLoader" />
    <NavBar />

    <main class="mx-auto max-w-[1500px] px-5 pb-24 pt-20 md:px-8 md:pt-24">
      <!-- 头部 -->
      <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="eyebrow mb-1">推演</p>
          <h1 class="font-display text-2xl font-bold tracking-tight md:text-3xl">决策推演</h1>
        </div>
        <div class="flex items-center gap-3">
          <span class="rounded-chip border px-3 py-1 font-mono text-xs" :class="statusClass">{{ statusText }}</span>
          <FancyButton
            v-if="sim.phase === 'completed'"
            size="sm"
            @click="start()"
          >
            重新推演
          </FancyButton>
          <FancyButton v-else-if="sim.phase === 'failed'" size="sm" @click="resetSimulation">重新填写参数</FancyButton>
          <FancyButton v-if="sim.isLive" size="sm" variant="ghost" @click="resetSimulation">终止</FancyButton>
        </div>
      </div>

      <!-- 画像状态条：未建则软引导，已建则显示 Agent 读到的家底与本次投入压力 -->
      <ProfileBar :budget="budget" />

      <div class="grid gap-6 lg:grid-cols-[1fr_380px]">
        <!-- ── 左：对话流（主视觉区）─────────────────── -->
        <div class="flex flex-col">
          <GlassPanel class="flex flex-1 flex-col" style="min-height: 520px">
            <!-- 消息列表 -->
            <div ref="chatRef" class="flex-1 space-y-4 overflow-y-auto px-2 py-3" style="max-height: 520px">
              <!-- 空闲态：OnboardingChat 对话引导 -->
              <OnboardingChat
                v-if="sim.phase === 'idle'"
                :key="scenarioId || 'freeform'"
                ref="onboardingRef"
                embedded
                :initial-scenario-id="scenarioId"
                @start="handleOnboardingStart"
                @readiness-change="handleOnboardingReadiness"
              />

              <!-- 推演中/完成：Agent 消息流 -->
              <template v-if="(sim.phase as string) !== 'idle'">
                <template v-for="m in chatMessages" :key="m.id">
                  <div v-if="m.role === 'system'" class="flex justify-center py-2">
                    <span class="rounded-chip border border-white/8 bg-white/[0.03] px-4 py-1.5 text-xs text-ink-muted">{{ m.content }}</span>
                  </div>
                  <ChatBubble v-else :role="m.role" :agent-id="m.agentId || ''" :content="m.content" />
                </template>
              </template>
            </div>

            <!-- 输入区（推演中/完成后） -->
            <div v-if="(sim.phase as string) !== 'idle'" class="shrink-0 border-t border-white/5 px-2 pt-3">
              <ChatInput
                :placeholder="
                  pausePrompt || (
                    sim.phase === 'completed' ? '追问 AI，如：为什么第2年现金流暴跌？' :
                    sim.phase === 'idle' ? '描述你的决策场景或直接启动推演…' :
                    '推演进行中…'
                  )
                "
                :disabled="
                  sim.phase === 'running'
                  || sim.phase === 'connecting'
                  || sim.pauseReason === 'decision_preview_required'
                  || sim.pauseReason === 'intervention_required'
                "
                :busy="resumeBusy || chatBusy"
                @send="handleUserSend"
              />
            </div>
          </GlassPanel>
        </div>

        <!-- ── 右：状态面板 ─────────────────────────── -->
        <div class="space-y-5">
          <!-- 参数（仅 idle 时显示） -->
          <GlassPanel v-if="sim.phase === 'idle'">
            <h2 class="text-sm font-semibold text-ink-primary">{{ parameterTitle }}</h2>
            <p class="mb-4 mt-1 text-xs leading-relaxed text-ink-muted">{{ parameterHint }}</p>
            <div class="mb-3">
              <span class="text-xs text-ink-muted">场景</span>
              <div class="mt-0.5 text-sm font-medium text-ink-primary">{{ scenarios.list.find(s => s.scenario_id === scenarioId)?.title || scenarioId || '—' }}</div>
            </div>
            <div class="grid grid-cols-2 gap-3 text-xs">
              <template v-for="dv in ((scenarios.current?.decision_vars as unknown) as Record<string, unknown>[] || [])" :key="dv.name as string">
                <div>
                  <span class="text-ink-muted">{{ (dv.label as string) || (dv.name as string) }}</span>
                  <div class="mt-0.5 font-mono font-medium text-ink-primary">
                    {{ displayParameterValue(dv) }}
                  </div>
                </div>
              </template>
            </div>
          </GlassPanel>

          <!-- 世界状态 -->
          <section v-if="sim.worldState">
            <h2 class="mb-2 text-xs font-semibold text-ink-muted tracking-wider">世界状态</h2>
            <WorldStatePanel
              :state="sim.worldState"
              :diff="sim.years.length ? sim.years[sim.years.length - 1].stateDiff : null"
              :scenario-id="scenarioId"
              :metric-definitions="scenarios.current?.state_metrics || []"
            />
          </section>

          <!-- 干预选项快捷按钮 -->
          <section v-if="sim.pauseReason === 'decision_preview_required' && sim.pendingDecisionPreview" class="border border-brand/30 bg-white/[0.03] p-4">
            <div class="mb-3">
              <h2 class="text-sm font-semibold text-ink-primary">{{ sim.pendingDecisionPreview.decision_label }}方案推演</h2>
              <p class="mt-1 text-xs leading-relaxed text-ink-secondary">{{ sim.pendingDecisionPreview.proposal_text }}</p>
            </div>
            <div class="space-y-3">
              <article
                v-for="branch in sim.pendingDecisionPreview.branches"
                :key="branch.branch_id"
                class="border border-white/10 p-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <h3 class="text-sm font-medium text-ink-primary">{{ branch.label }}</h3>
                    <p class="mt-1 text-xs leading-relaxed text-ink-secondary">{{ branch.description }}</p>
                  </div>
                  <span class="shrink-0 text-xs text-ink-muted">风险{{ previewRiskLabel(branch.risk_level) }}</span>
                </div>
                <div class="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-ink-secondary">
                  <template v-if="scenarios.current?.state_metrics?.length">
                    <span v-for="metric in scenarios.current.state_metrics.slice(0, 4)" :key="metric.metric_id">
                      {{ metric.label }} {{ formatPreviewMetric(metric, branch.world_state as unknown as Record<string, unknown>) }}
                    </span>
                  </template>
                  <template v-else>
                    <span>现金储备 ¥{{ (branch.world_state.cash_flow / 10000).toFixed(1) }}万</span>
                    <span>日客流 {{ branch.world_state.customer_flow.toFixed(0) }}杯</span>
                    <span>月利润 ¥{{ (branch.world_state.monthly_profit / 10000).toFixed(1) }}万</span>
                  </template>
                  <span>最坏影响 ¥{{ (branch.worst_case_loss / 10000).toFixed(1) }}万</span>
                </div>
                <button
                  class="mt-3 w-full border border-brand/40 bg-brand/10 px-3 py-2 text-xs font-medium text-ink-primary transition-colors hover:bg-brand/20 disabled:opacity-50"
                  :disabled="resumeBusy"
                  @click="handleUserSend(branch.branch_id, `选择方案：${branch.label}`)"
                >
                  选择此方案
                </button>
              </article>
            </div>
          </section>

          <section
            v-if="sim.pauseReason === 'year_decision_required' && personalDecisionOptions.length"
            class="border border-agent-personal/30 bg-white/[0.03] p-4"
          >
            <div class="mb-3">
              <h2 class="text-sm font-semibold text-ink-primary">个人智能体的下一步建议</h2>
              <p class="mt-1 text-xs leading-relaxed text-ink-secondary">{{ personalDecisionSummary }}</p>
            </div>
            <div class="space-y-2">
              <button
                v-for="option in personalDecisionOptions"
                :key="option.id"
                :disabled="resumeBusy"
                class="w-full border border-white/10 bg-white/[0.03] px-3 py-2.5 text-left transition-colors hover:border-agent-personal/50 hover:bg-agent-personal/10 disabled:opacity-50"
                @click="handleUserSend(option.decision, option.title)"
              >
                <span class="block text-xs font-medium text-ink-primary">{{ option.title }}</span>
                <span class="mt-1 block text-xs leading-relaxed text-ink-secondary">{{ option.description }}</span>
              </button>
            </div>
          </section>

          <section v-if="sim.pauseReason === 'horizon_review'" class="border border-agent-env/30 bg-white/[0.03] p-4">
            <h2 class="text-sm font-semibold text-ink-primary">已完成第 {{ sim.currentYear }} 年推演</h2>
            <p class="mt-1 text-xs leading-relaxed text-ink-secondary">选择后仍会先等待你的下一步行动决策，不会直接推进年份。</p>
            <div class="mt-3 grid gap-2">
              <button
                :disabled="resumeBusy"
                class="border border-white/10 bg-white/[0.03] px-3 py-2 text-left text-xs text-ink-secondary transition-colors hover:border-brand/40 hover:text-ink-primary disabled:opacity-50"
                @click="handleUserSend('extend_1_year', '继续推演 1 年')"
              >
                继续推演 1 年
              </button>
              <button
                :disabled="resumeBusy"
                class="border border-white/10 bg-white/[0.03] px-3 py-2 text-left text-xs text-ink-secondary transition-colors hover:border-brand/40 hover:text-ink-primary disabled:opacity-50"
                @click="handleUserSend('extend_3_years', '继续推演 3 年')"
              >
                继续推演 3 年
              </button>
              <button
                :disabled="resumeBusy"
                class="border border-agent-env/40 bg-agent-env/10 px-3 py-2 text-left text-xs font-medium text-ink-primary transition-colors hover:bg-agent-env/20 disabled:opacity-50"
                @click="handleUserSend('finalize_simulation', '按当前结果完成结算')"
              >
                完成结算
              </button>
            </div>
          </section>

          <div v-if="sim.pauseReason === 'intervention_required' && sim.pending" class="glass-strong rounded-card border border-agent-risk/30 p-4 shadow-[0_0_30px_rgba(248,113,113,0.1)]">
            <div class="mb-3 flex items-center gap-2">
              <span class="text-sm">🛡️</span>
              <span class="text-sm font-semibold text-agent-risk">风险智能体需要你的决策</span>
            </div>
            <p class="mb-3 text-xs leading-relaxed text-ink-secondary">{{ sim.pending.event }}</p>
            <div class="space-y-2">
              <button
                v-for="opt in sim.pending.options"
                :key="opt"
                :disabled="resumeBusy"
                class="w-full rounded-btn border border-white/10 bg-white/[0.03] px-3 py-2.5 text-left text-xs text-ink-secondary transition-all hover:border-brand/40 hover:text-ink-primary disabled:opacity-50"
                @click="chooseIntervention(opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>

          <!-- 结果摘要 -->
          <ResultPanel v-if="sim.finalResult" :result="sim.finalResult" />
        </div>
      </div>

      <!-- 四方观点：放在主内容宽度中，避免侧栏压缩成竖排窄卡 -->
      <section v-if="latestDebate" class="mt-8">
        <div class="mb-3 flex items-end justify-between gap-3">
          <div>
            <p class="text-xs font-semibold tracking-wider text-agent-env">本轮交锋</p>
            <h2 class="mt-1 text-lg font-semibold text-ink-primary">四方智能体立场对照</h2>
          </div>
          <span class="text-xs text-ink-muted">先看分歧，再看综合建议</span>
        </div>
        <DebatePanel :debate="latestDebate" />
      </section>

      <section v-if="latestActions.length > 0" class="mt-8">
        <div class="mb-3 flex items-end justify-between gap-3">
          <div>
            <p class="text-xs font-semibold tracking-wider text-ink-muted">本轮输出</p>
            <h2 class="mt-1 text-lg font-semibold text-ink-primary">四个智能体各自的判断</h2>
          </div>
          <span class="text-xs text-ink-muted">第 {{ sim.currentYear }} 年</span>
        </div>
        <AgentPanel
          :actions="latestActions"
          :running="sim.isLive"
          :current-year="sim.currentYear"
          :world-state="sim.worldState"
          :scenario-id="scenarioId"
        />
      </section>

      <!-- ── 年度结果复盘（推演完成后展开）─────────────── -->
      <div v-if="showCharts && sim.years.length > 0" class="mt-10 space-y-8">
        <section>
          <ResultJourney :years="sim.years" :metric-definitions="resultMetrics" />
        </section>
        <section>
          <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p class="eyebrow mb-1">指标变化</p>
              <h2 class="text-lg font-semibold text-ink-primary">只看一个指标的真实走势</h2>
            </div>
            <div class="flex flex-wrap gap-2" role="tablist" aria-label="选择结果指标">
              <button
                v-for="metric in resultMetrics"
                :key="metric.metric_id"
                type="button"
                role="tab"
                :aria-selected="selectedMetricId === metric.metric_id"
                class="border px-3 py-1.5 text-xs transition-colors duration-200 focus-visible:outline-none"
                :class="selectedMetricId === metric.metric_id ? 'border-brand/50 bg-brand/15 text-ink-primary' : 'border-white/10 bg-black/15 text-ink-muted hover:border-white/25 hover:text-ink-secondary'"
                @click="selectedMetricId = metric.metric_id"
              >
                {{ metric.label }}
              </button>
            </div>
          </div>
          <GlassPanel class="min-h-[260px] p-4">
            <WorldStateChart
              :years="sim.years"
              :metric-definitions="resultMetrics"
              :selected-metric-id="selectedMetricId"
            />
          </GlassPanel>
        </section>
      </div>
    </main>
  </div>
</template>
