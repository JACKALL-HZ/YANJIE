<script setup lang="ts">
/**
 * OnboardingChat — 对话式决策引导。
 * 多轮对话收集决策变量，确认后跳转推演或 emit start 事件。
 */
import { nextTick, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import ChatBubble from '@/components/chat/ChatBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import { api, ApiRequestError } from '@/api/client'
import type { ScenarioDetail } from '@/api/types'

const props = withDefaults(
  defineProps<{ embedded?: boolean; initialScenarioId?: string }>(),
  { embedded: false, initialScenarioId: '' },
)
type OnboardingHistoryItem = {
  role: 'user' | 'agent'
  agentId: string
  content: string
}

const emit = defineEmits<{
  start: [
    vars: Record<string, unknown>,
    scenarioId: string,
    history: OnboardingHistoryItem[],
  ]
  'readiness-change': [
    state: {
      hasRecognizedInput: boolean
      ready: boolean
      vars: Record<string, unknown>
    },
  ]
}>()
const router = useRouter()
const scenarioLocked = Boolean(props.initialScenarioId)

interface ChatMsg {
  id: number
  role: 'user' | 'agent'
  agentId: string
  content: string
  typing?: boolean
  time?: string
}

const messages = ref<ChatMsg[]>([])
const busy = ref(false)
const ready = ref(false)            // 变量齐全，可以开始推演
const hasRecognizedInput = ref(false)
const listRef = ref<HTMLDivElement | null>(null)
const scenarioDetail = ref<ScenarioDetail | null>(null)

/* 累积的上下文 */
const ctx = reactive({
  query: '',
  scenarioId: props.initialScenarioId || '',
  // Only values explicitly extracted from the user's messages can unlock a simulation.
  // Scenario defaults remain reference values and must never be treated as user input.
  confirmedKeys: new Set<string>(),
  extractedVars: {} as Record<string, unknown>,
  missingRequired: [] as string[],
  invalidVars: {} as Record<string, string>,
  suggestions: '',
  turn: 0,
})

let msgId = 0

function resetCollectedVars() {
  for (const key of Object.keys(ctx.extractedVars)) delete ctx.extractedVars[key]
  ctx.confirmedKeys.clear()
}

function isConfirmedValue(value: unknown): boolean {
  return value != null
    && value !== ''
    && value !== '待确认'
    && value !== '待明确'
}

function recomputeMissingRequired() {
  if (!scenarioDetail.value) return
  ctx.missingRequired = scenarioDetail.value.decision_vars
    .filter(definition => (definition.required || definition.name === 'span_years') && (
      !ctx.confirmedKeys.has(definition.name)
      || !isConfirmedValue(ctx.extractedVars[definition.name])
    ))
    .map(definition => definition.name)
}

function syncReadiness() {
  ready.value = hasRecognizedInput.value
    && ctx.missingRequired.length === 0
    && Object.keys(ctx.invalidVars).length === 0
    && ctx.confirmedKeys.size > 0
  emit('readiness-change', {
    hasRecognizedInput: hasRecognizedInput.value,
    ready: ready.value,
    vars: { ...ctx.extractedVars },
  })
}

function addMsg(role: 'user' | 'agent', content: string, agentId = '', typing = false) {
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  messages.value.push({ id: ++msgId, role, agentId, content, typing, time })
}

async function scrollBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

async function loadScenarioDetail(id: string) {
  if (!id) {
    scenarioDetail.value = null
    return
  }
  try {
    scenarioDetail.value = await api.get<ScenarioDetail>(`/scenarios/${id}`)
    recomputeMissingRequired()
  } catch {
    scenarioDetail.value = null
  }
}

/**
 * 调用 breakdown API 并生成 AI 回复
 */
async function analyzeAndRespond(userInput: string) {
  busy.value = true

  // 累积查询：把新输入追加到上下文
  ctx.query = ctx.query ? `${ctx.query}。${userInput}` : userInput
  ctx.turn++

  try {
    const previousScenarioId = ctx.scenarioId
    const result = await api.breakdown(
      ctx.query,
      ctx.scenarioId || undefined,
      scenarioLocked ? undefined : userInput,
    )

    const sceneChanged = Boolean(
      previousScenarioId &&
      result.scenario_id &&
      result.scenario_id !== previousScenarioId,
    )
    const unresolvedGeneral = !previousScenarioId && !scenarioLocked && result.domain === 'general'
    if (sceneChanged || unresolvedGeneral) {
      // A new scene must not inherit fields from the previous scene.
      resetCollectedVars()
      hasRecognizedInput.value = false
      ctx.invalidVars = {}
      if (sceneChanged) ctx.query = userInput
    }

    if (unresolvedGeneral) {
      ctx.scenarioId = ''
      ctx.missingRequired = []
      ctx.invalidVars = {}
      ctx.suggestions = result.suggestions || ''
    } else {
      ctx.scenarioId = result.scenario_id || ctx.scenarioId
      ctx.missingRequired = result.missing_required || []
      // 以本轮后端结果为准；用户修正参数后不能继续沿用上一轮错误。
      ctx.invalidVars = result.invalid_vars || {}
      ctx.suggestions = result.suggestions || ''
    }

    await loadScenarioDetail(ctx.scenarioId)

    // 合并提取的变量
    if (result.extracted_vars) {
      if (!unresolvedGeneral) {
        Object.assign(ctx.extractedVars, result.extracted_vars)
        for (const [key, value] of Object.entries(result.extracted_vars)) {
          if (isConfirmedValue(value)) ctx.confirmedKeys.add(key)
        }
        if (Object.keys(result.extracted_vars).length > 0) {
          hasRecognizedInput.value = true
        }
      }
    }
    // The API sees only the latest turn. Rebuild missing fields from every
    // value the user has explicitly supplied during this conversation.
    if (!unresolvedGeneral && scenarioDetail.value) {
      recomputeMissingRequired()
    }
    syncReadiness()

    // 生成 AI 回复
    const reply = buildReply(ctx)
    addMsg('agent', reply, 'guide', true)
    await scrollBottom()

    // 打字机效果
    const idx = messages.value.length - 1
    const fullText = reply
    for (let i = 1; i <= fullText.length; i++) {
      messages.value[idx].content = fullText.slice(0, i)
      messages.value[idx].typing = true
      if (i % 4 === 0) {
        await new Promise(r => setTimeout(r, 12))
        await scrollBottom()
      }
    }
    messages.value[idx].typing = false

  } catch (e) {
    const err = e instanceof ApiRequestError ? e.message : (e as Error).message
    addMsg('agent', `抱歉，连接后端失败：${err}。请确认后端服务已启动。`, 'guide')
  } finally {
    busy.value = false
    await scrollBottom()
  }
}

/**
 * 根据上下文生成自然语言 AI 回复
 */
function buildReply(c: typeof ctx): string {
  const vars = c.extractedVars
  const varNames = Object.keys(vars)
  const missing = c.missingRequired
  const invalidMessages = Object.values(c.invalidVars)
  if (!c.scenarioId) {
    return '我还没有识别出你想推演的场景。请告诉我你想做什么，例如：准备考研、申请留学、找工作、买房或创业。'
  }

  if (invalidMessages.length > 0) {
    return `请先修正：**${invalidMessages.join('；')}**。`
  }

  if (missing.length > 0) {
    const missingCn = missing.map(m => labelOf(m)).join('、')
    return `已识别为${scenarioDetail.value?.title || '当前场景'}。还需要补充：**${missingCn}**。`
  }

  if (ready.value) {
    const summary = Object.entries(vars)
      .map(([k, v]) => `• ${labelOf(k)}：${formatVar(k, v)}`)
      .join('\n')
    return `信息已齐全，当前参数：\n\n${summary}\n\n可以开始推演。输入「开始」或点击下方按钮。`
  }

  return '我已识别到当前场景。请继续补充你的实际情况。'

  // 第一轮：刚收到用户输入
  if (c.turn === 1) {
    const parts: string[] = ['好的，我理解了你的决策场景：']

    if (scenarioDetail.value) {
      parts.push(`• 场景：${scenarioDetail.value!.title}`)
      for (const [key, value] of Object.entries(vars)) {
        parts.push(`• ${labelOf(key)}：${formatVar(key, value)}`)
      }
    }

    if (vars.budget) parts.push(`• 启动资金：${Number(vars.budget).toLocaleString()} 元`)
    if (vars.city) parts.push(`• 城市：${vars.city}`)
    if (vars.industry) parts.push(`• 行业：${vars.industry}`)
    if (vars.span_years) parts.push(`• 推演年限：${vars.span_years} 年`)

    if (varNames.length <= 1) {
      if (scenarioDetail.value) {
        const missingCn = missing.map(m => labelOf(m)).join('、')
        return missingCn
          ? `已识别为${scenarioDetail.value!.title}。还需要补充：${missingCn}。`
          : `已识别为${scenarioDetail.value!.title}，请再补充一些与你当前情况相关的信息。`
      }
      // 尚未识别场景时不要假设用户一定在创业。
      return '我收到你的描述了。为了准确识别场景，请告诉我你准备做什么、目标是什么，以及已知的预算、时间或地点等信息。'
    }

    parts.push('')
    if (invalidMessages.length > 0) {
      parts.push(`请先修正：**${invalidMessages.join('；')}**。`)
    } else if (missing.length > 0) {
      const missingCn = missing.map(m => labelOf(m)).join('、')
      parts.push(`还需要确认：**${missingCn}**。能补充一下吗？`)
    } else if (hasRecognizedInput.value) {
      parts.push('信息已经齐全。要现在开始推演吗？输入「开始」或点击下方按钮。')
    } else {
      parts.push('右侧显示的是参考示例。请先输入你的实际情况，识别到有效参数后才能开始推演。')
    }
    return parts.join('\n')
  }

  // 后续轮次
  if (varNames.length >= 3 && missing.length === 0 && invalidMessages.length === 0 && hasRecognizedInput.value) {
    const summary = Object.entries(vars)
      .map(([k, v]) => `• ${labelOf(k)}：${formatVar(k, v)}`)
      .join('\n')
    return `信息已更新，当前完整参数：\n${summary}\n\n四个智能体已就位：\n📊 市场智能体 — 分析竞争格局与市场机会\n🌍 环境智能体 — 监控政策、经济与行业趋势\n🧠 个人智能体 — 评估你的资源、技能与执行能力\n🛡️ 风险智能体 — 扫描潜在风险与脆弱点\n\n准备好了，输入「开始」或点击下方按钮启动推演。`
  }

  if (invalidMessages.length > 0) {
    return `请先修正：**${invalidMessages.join('；')}**。`
  }

  if (missing.length > 0) {
    const missingCn = missing.map(m => labelOf(m)).join('、')
    return `收到。还差一些关键信息：**${missingCn}**。能告诉我吗？`
  }

  return '右侧参数目前仅是参考示例。请补充你的实际情况，识别到有效参数后才能开始推演。'
}

function labelOf(k: string): string {
  return scenarioDetail.value?.decision_vars.find(item => item.name === k)?.label || '待补充信息'
}

function formatVar(k: string, v: unknown): string {
  if (['budget', 'investment_amount', 'income', 'salary_expectation'].includes(k)) {
    return `${Number(v).toLocaleString()} 元`
  }
  const valueLabels: Record<string, Record<string, string>> = {
    city: {
      hangzhou: '杭州', shanghai: '上海', beijing: '北京', shenzhen: '深圳',
      guangzhou: '广州', chengdu: '成都', wuhan: '武汉', nanjing: '南京',
      changsha: '长沙', chongqing: '重庆', xian: '西安', hefei: '合肥',
      fuzhou: '福州', xiamen: '厦门',
    },
    industry: {
      milk_tea: '奶茶', coffee: '咖啡', catering: '餐饮', restaurant: '餐饮',
      retail: '零售', saas: '软件服务',
    },
    risk_level: { conservative: '保守', balanced: '均衡', aggressive: '激进' },
  }
  const translated = valueLabels[k]?.[String(v)]
  if (translated) return translated
  return String(v)
}

function openingMessage(): string {
  const title = scenarioDetail.value?.title
  if (scenarioLocked && title) {
    const fields = scenarioDetail.value?.decision_vars.map(item => item.label).join('、')
    return `你好，我是衍界智能向导 ✦\n\n你已进入「${title}」场景。本轮只会使用这个场景的参数${fields ? `：${fields}` : ''}。你可以直接补充或修改信息，确认后让四个专业智能体开始推演。`
  }
  return '你好，我是衍界智能向导 ✦\n\n我可以帮你推演创业、升学、留学、职场、买房和投资等人生决策。你可以直接描述想做什么、目标是什么，以及已知的预算、时间或地点；我会先识别场景，再只收集该场景需要的参数。'
}

/** 暴露上下文给父组件 */
function getHistory(): OnboardingHistoryItem[] {
  return messages.value.map(({ role, agentId, content }) => ({
    role,
    agentId,
    content,
  }))
}

defineExpose({ ctx, messages, ready, getHistory })

async function handleSend(text: string) {
  const isStartCommand = text === '开始' || text === '开始推演' || text.toLowerCase() === 'start'
  if (isStartCommand && !ready.value) {
    addMsg('user', text)
    const missingCn = ctx.missingRequired.map(name => labelOf(name)).join('、')
    addMsg(
      'agent',
      missingCn
        ? `还不能开始推演，还需要补充：${missingCn}。`
        : '请先描述你想推演的决策场景和实际情况。',
      'guide',
    )
    await scrollBottom()
    return
  }
  // 检查是否是"开始"指令
  if (false && isStartCommand && !ready.value) {
    addMsg('user', text)
    addMsg('agent', '请先输入你的实际情况。右侧数值只是示例，识别到有效参数后才能启动推演。', 'guide')
    await scrollBottom()
    return
  }
  if (ready.value && isStartCommand) {
    addMsg('user', text)
    await scrollBottom()
    addMsg('agent', '正在启动推演引擎…', 'guide')
    await scrollBottom()
    if (props.embedded) {
      emit(
        'start',
        { ...ctx.extractedVars },
        ctx.scenarioId,
        messages.value.map(({ role, agentId, content }) => ({ role, agentId, content })),
      )
    } else {
      const params = new URLSearchParams()
      for (const [k, v] of Object.entries(ctx.extractedVars)) {
        if (v != null && v !== '') params.set(k, String(v))
      }
      router.push({
        name: 'sim',
        params: { scenarioId: ctx.scenarioId },
        query: Object.fromEntries(params),
      })
    }
    return
  }

  addMsg('user', text)
  await scrollBottom()
  await analyzeAndRespond(text)
}

/* 初始化：AI 先打招呼 */
async function init() {
  await loadScenarioDetail(ctx.scenarioId)
  addMsg('agent', openingMessage(), 'guide')
  syncReadiness()
}

void init()
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- 消息列表 -->
    <div
      ref="listRef"
      class="flex-1 space-y-4 overflow-y-auto px-2 py-4"
      style="max-height: 420px"
    >
      <ChatBubble
        v-for="m in messages"
        :key="m.id"
        :role="m.role"
        :agent-id="m.agentId"
        :content="m.content"
        :typing="m.typing"
        :time="m.time"
      />
    </div>

    <!-- 输入区 -->
    <div class="shrink-0 border-t border-white/5 px-2 pt-4">
      <!-- 就绪提示 -->
      <div
        v-if="ready"
        class="mb-3 flex items-center gap-2 rounded-xl border border-agent-env/30 bg-agent-env/5 px-4 py-2.5"
      >
        <span class="h-2 w-2 rounded-full bg-agent-env shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
        <span class="text-sm text-agent-env">参数齐全，可以开始推演</span>
        <button
          class="ml-auto rounded-lg bg-agent-env/20 px-4 py-1.5 text-sm font-medium text-agent-env transition-colors hover:bg-agent-env/30"
          @click="handleSend('开始')"
        >
          开始推演 →
        </button>
      </div>

      <ChatInput
        :placeholder="ready ? '输入「开始」启动推演，或继续补充信息…' : '描述你的决策场景…'"
        :busy="busy"
        @send="handleSend"
      />
    </div>
  </div>
</template>
