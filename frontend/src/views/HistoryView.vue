<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import SkeletonCard from '@/components/ui/SkeletonCard.vue'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import { api } from '@/api/client'
import type { SessionReport, SessionSummary } from '@/api/types'

const router = useRouter()
const sessions = ref<SessionSummary[]>([])
const loading = ref(false)
const errorMsg = ref<string | null>(null)
const expanded = ref<string | null>(null)
const reportCache = ref<Record<string, SessionReport>>({})
const reportLoading = ref<string | null>(null)
const reportError = ref<Record<string, string>>({})

// 对比选择
const selectedIds = ref<Set<string>>(new Set())
const compareBusy = ref(false)
const compareError = ref<string | null>(null)

const sorted = computed(() =>
  [...sessions.value].sort((a, b) =>
    String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')),
  ),
)

// 可对比的记录：已完成的
const comparableSessions = computed(() =>
  sorted.value.filter(s => s.phase === 'completed'),
)

const selectedCount = computed(() => selectedIds.value.size)
const canCompare = computed(() => selectedCount.value === 2 && !compareBusy.value)

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else if (selectedIds.value.size < 2) {
    selectedIds.value.add(id)
  }
  // 触发响应式更新
  selectedIds.value = new Set(selectedIds.value)
}

function clearSelection() {
  selectedIds.value = new Set()
  compareError.value = null
}

async function startCompare() {
  if (!canCompare.value) return
  const ids = [...selectedIds.value]
  compareBusy.value = true
  compareError.value = null
  try {
    // 直接跳到 CompareView，带 session ids 作为 query
    router.push({
      path: '/compare',
      query: {
        mode: 'sessions',
        a: ids[0],
        b: ids[1],
      },
    })
  } catch (e) {
    compareError.value = (e as Error).message
  } finally {
    compareBusy.value = false
  }
}

async function fetchSessions() {
  loading.value = true
  errorMsg.value = null
  try {
    sessions.value = await api.get<SessionSummary[]>('/sessions')
  } catch (error) {
    errorMsg.value = (error as Error).message
  } finally {
    loading.value = false
  }
}

async function toggleReport(sessionId: string) {
  if (expanded.value === sessionId) {
    expanded.value = null
    return
  }
  expanded.value = sessionId
  if (reportCache.value[sessionId]) return

  reportLoading.value = sessionId
  reportError.value[sessionId] = ''
  try {
    reportCache.value[sessionId] = await api.get<SessionReport>(`/sessions/${sessionId}/report-detail`)
  } catch (error) {
    reportError.value[sessionId] = (error as Error).message || '报告加载失败'
  } finally {
    reportLoading.value = null
  }
}

async function downloadReport(sessionId: string) {
  try {
    const markdown = await api.downloadReport(sessionId)
    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `衍界推演报告-${sessionId.slice(0, 8)}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    reportError.value[sessionId] = (error as Error).message || '报告下载失败'
  }
}

function phaseLabel(phase: string) {
  return {
    completed: '已完成',
    paused: '等待决策',
    horizon_review: '等待确认周期',
    simulating: '推演中',
    scoring: '生成结论中',
  }[phase] ?? '处理中'
}

function phaseClass(phase: string) {
  return {
    completed: 'text-agent-env border-agent-env/30 bg-agent-env/10',
    paused: 'text-agent-risk border-agent-risk/30 bg-agent-risk/10',
    horizon_review: 'text-agent-env border-agent-env/30 bg-agent-env/10',
    simulating: 'text-cyan-glow border-cyan-glow/30 bg-cyan-glow/10',
  }[phase] ?? 'text-ink-muted border-white/10 bg-white/5'
}

function agentClass(agentId: string) {
  return {
    market: 'border-brand/30 bg-brand/10 text-brand',
    environment: 'border-agent-env/30 bg-agent-env/10 text-agent-env',
    personal: 'border-cyan-glow/30 bg-cyan-glow/10 text-cyan-glow',
    risk: 'border-agent-risk/30 bg-agent-risk/10 text-agent-risk',
  }[agentId] ?? 'border-white/10 bg-white/5 text-ink-secondary'
}

function generationSourceLabel(source?: string | null) {
  return ({
    llm: '\u6a21\u578b\u751f\u6210',
    stub: '\u672c\u5730\u89c4\u5219',
    fallback: '\u964d\u7ea7\u8bf4\u660e',
  } as Record<string, string>)[source || ''] || '\u751f\u6210\u65b9\u5f0f\u672a\u77e5'
}

function ragStatusLabel(status?: string | null) {
  return ({
    hit: '\u77e5\u8bc6\u5e93\u5df2\u547d\u4e2d',
    empty: '\u672a\u68c0\u7d22\u5230\u76f8\u5173\u8d44\u6599',
    error: '\u77e5\u8bc6\u5e93\u6682\u4e0d\u53ef\u7528',
    disabled: '\u672a\u542f\u7528\u77e5\u8bc6\u5e93',
  } as Record<string, string>)[status || ''] || '\u77e5\u8bc6\u5e93\u72b6\u6001\u672a\u77e5'
}

function positionLabel(position?: string | null) {
  return ({ support: '支持', oppose: '反对', conditional: '有条件支持', neutral: '保持观察' } as Record<string, string>)[position || 'neutral'] || '保持观察'
}

function confidenceNumber(value?: string | null): number | null {
  if (!value) return null
  const match = value.match(/-?\d+(?:\.\d+)?/)
  if (!match) return null
  const number = Number(match[0])
  if (Number.isNaN(number)) return null
  return value.includes('%') ? number : number <= 1 ? number * 100 : number
}

function formatDate(value?: string) {
  return value ? value.slice(0, 16).replace('T', ' ') : '时间未知'
}

function messageRoleLabel(role: string, agentId?: string | null) {
  if (role === 'user') return '你'
  if (role === 'system') return '系统'
  if (agentId === 'guide' || agentId === 'personal') return '衍界向导'
  return '智能体'
}

function resultLabel(result?: string | null): string {
  return ({
    goal_reached: '目标达成',
    steady: '稳定运营',
    bankrupt: '破产',
    timeout: '超时',
    user_ended: '主动结束',
  } as Record<string, string>)[result || ''] || result || '—'
}

onMounted(fetchSessions)
</script>

<template>
  <div class="min-h-[100dvh]">
    <NavBar />

    <main class="mx-auto max-w-[1400px] px-5 pb-24 pt-24 md:px-8 md:pt-28">
      <p class="eyebrow mb-2">推演历史</p>
      <h1 class="font-display text-3xl font-bold tracking-tight md:text-4xl">推演历史</h1>
      <p class="mt-3 max-w-[560px] text-sm text-ink-secondary">每一次推演都被完整保存，可随时查看决策与各年度结论。</p>

      <!-- 对比操作栏 -->
      <div v-if="comparableSessions.length >= 2" class="mt-6 flex flex-wrap items-center gap-3 rounded-btn border border-cyan-glow/20 bg-cyan-glow/5 px-4 py-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-medium text-cyan-glow">方案对比</span>
          <span class="text-[11px] text-ink-muted">
            已选 {{ selectedCount }}/2 · 勾选两条已完成记录即可对比
          </span>
        </div>
        <div class="ml-auto flex items-center gap-2">
          <FancyButton v-if="selectedCount > 0" size="sm" variant="ghost" @click="clearSelection">清空</FancyButton>
          <FancyButton size="sm" :disabled="!canCompare" @click="startCompare">
            {{ compareBusy ? '加载中…' : selectedCount === 2 ? '开始对比' : `还需选 ${2 - selectedCount} 条` }}
          </FancyButton>
        </div>
        <p v-if="compareError" class="w-full text-xs text-agent-risk">{{ compareError }}</p>
      </div>

      <div v-if="loading" class="mt-10 space-y-4">
        <SkeletonCard v-for="n in 4" :key="n" :lines="2" />
      </div>

      <div v-else-if="errorMsg" class="mt-10 rounded-btn border border-agent-risk/30 bg-agent-risk/10 px-4 py-3 text-sm text-agent-risk">{{ errorMsg }}</div>

      <GlassPanel v-else-if="sorted.length === 0" class="mt-10 py-16 text-center">
        <p class="text-sm text-ink-muted">还没有推演记录，先完成一场推演吧。</p>
      </GlassPanel>

      <div v-else class="mt-10 space-y-3">
        <section v-for="session in sorted" :key="session.id" class="glass overflow-hidden rounded-card" :class="selectedIds.has(session.id) ? 'ring-1 ring-cyan-glow/40' : ''">
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
            <!-- 对比复选框（仅已完成记录显示） -->
            <label
              v-if="session.phase === 'completed'"
              class="relative z-10 flex shrink-0 cursor-pointer items-center gap-2"
              @click.stop
            >
              <input
                type="checkbox"
                :checked="selectedIds.has(session.id)"
                class="pointer-events-auto h-[18px] w-[18px] accent-cyan-glow"
                :disabled="selectedIds.size >= 2 && !selectedIds.has(session.id)"
                @change="toggleSelect(session.id)"
              />
              <span class="select-none text-[11px] text-ink-muted">对比</span>
            </label>

            <button class="min-w-0 flex-1 text-left" @click="toggleReport(session.id)">
              <p class="font-medium text-ink-primary">{{ session.scenario_title }}</p>
              <p class="mt-1 font-mono text-[10px] text-ink-muted">
                {{ formatDate(session.created_at) }} · 第 {{ session.current_year ?? 0 }} 年
                <span v-if="session.result" class="ml-2 text-ink-secondary">{{ resultLabel(session.result) }}</span>
              </p>
            </button>
            <span class="rounded-chip border px-2.5 py-0.5 text-[10px]" :class="phaseClass(session.phase ?? '')">{{ phaseLabel(session.phase ?? '') }}</span>
            <span v-if="session.score != null" class="font-mono text-sm text-cyan-glow tabular-nums">
              <AnimatedNumber :value="Number(session.score)" :decimals="1" />
            </span>
            <button class="border border-white/10 px-2.5 py-1 text-xs text-ink-secondary transition-colors hover:border-cyan-glow/40 hover:text-cyan-glow" title="下载 Markdown 报告" @click="downloadReport(session.id)">下载</button>
            <button class="flex h-7 w-7 items-center justify-center border border-white/10 text-ink-muted transition-colors hover:text-ink-primary" :title="expanded === session.id ? '收起报告' : '查看完整报告'" @click="toggleReport(session.id)">
              <span class="text-base leading-none" :class="expanded === session.id ? 'rotate-45' : ''">+</span>
            </button>
          </div>

          <div v-if="expanded === session.id" class="border-t border-white/5 px-5 py-5">
            <div v-if="reportLoading === session.id" class="space-y-3"><div class="skeleton h-4 w-1/3" /><div class="skeleton h-3 w-2/3" /><div class="skeleton h-3 w-1/2" /></div>
            <p v-else-if="reportError[session.id]" class="text-sm text-agent-risk">{{ reportError[session.id] }}</p>
            <div v-else-if="reportCache[session.id]" class="space-y-7">
              <div class="flex flex-wrap items-end justify-between gap-3 border-l-2 border-cyan-glow/60 pl-4">
                <div><p class="text-xs text-ink-muted">{{ reportCache[session.id].conclusion.phase_label }}</p><p class="mt-1 font-display text-xl font-bold text-ink-primary">{{ reportCache[session.id].conclusion.result_label }}</p></div>
                <p v-if="reportCache[session.id].conclusion.score" class="font-mono text-2xl text-cyan-glow tabular-nums">
                  <AnimatedNumber :value="Number(reportCache[session.id].conclusion.score)" :decimals="1" />
                </p>
              </div>

              <div v-if="reportCache[session.id].profile.length" class="border-t border-white/5 pt-4">
                <h2 class="text-sm font-semibold text-ink-primary">推演时的用户画像</h2>
                <dl class="mt-3 grid gap-x-5 gap-y-3 sm:grid-cols-2 lg:grid-cols-3"><div v-for="item in reportCache[session.id].profile" :key="item.label"><dt class="text-[11px] text-ink-muted">{{ item.label }}</dt><dd class="mt-0.5 text-sm text-ink-secondary">{{ item.value }}</dd></div></dl>
              </div>

              <div v-if="reportCache[session.id].decisions.length" class="border-t border-white/5 pt-4">
                <h2 class="text-sm font-semibold text-ink-primary">你的决策</h2>
                <div class="mt-3 space-y-2"><div v-for="decision in reportCache[session.id].decisions" :key="`${decision.year}-${decision.created_at}`" class="border-l-2 border-brand/60 pl-3 text-sm"><p class="text-ink-primary">第 {{ decision.year }} 年 · {{ decision.proposal }}</p><p v-if="decision.selected_branch_label" class="mt-1 text-xs text-ink-secondary">最终选择：{{ decision.selected_branch_label }}</p></div></div>
              </div>

              <div v-if="reportCache[session.id].messages.length" class="border-t border-white/5 pt-4">
                <h2 class="text-sm font-semibold text-ink-primary">启动前的对话</h2>
                <div class="mt-3 space-y-3">
                  <div v-for="(message, index) in reportCache[session.id].messages" :key="`${message.created_at}-${index}`" class="border-l-2 pl-3" :class="message.role === 'user' ? 'border-brand/60' : 'border-cyan-glow/40'">
                    <p class="text-[11px] text-ink-muted">{{ messageRoleLabel(message.role, message.agent_id) }}</p>
                    <p class="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink-secondary">{{ message.content }}</p>
                  </div>
                </div>
              </div>

              <div class="border-t border-white/5 pt-4">
                <h2 class="text-sm font-semibold text-ink-primary">逐年复盘</h2>
                <div v-if="reportCache[session.id].years.length" class="mt-3 space-y-5">
                  <article v-for="year in reportCache[session.id].years" :key="year.year" class="border-l border-white/10 pl-4">
                    <div class="flex items-center justify-between gap-3"><h3 class="font-medium text-ink-primary">第 {{ year.year }} 年</h3><span v-if="year.ending" class="text-xs text-agent-env">{{ year.ending }}</span></div>
                    <dl class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><div v-for="metric in year.metrics" :key="metric.label"><dt class="text-[11px] text-ink-muted">{{ metric.label }}</dt><dd class="mt-0.5 font-mono text-sm text-ink-primary">{{ metric.value }}</dd><p v-if="metric.change" class="mt-0.5 text-[10px] text-ink-muted">{{ metric.change }}</p></div></dl>
                    <div class="mt-4 grid gap-2 lg:grid-cols-2"><div v-for="agent in year.agent_actions" :key="agent.agent_id" class="border px-3 py-2.5" :class="agentClass(agent.agent_id)"><div class="flex items-center justify-between gap-3"><p class="text-xs font-semibold">{{ agent.agent_name }}</p><span v-if="agent.confidence" class="font-mono text-[10px] opacity-80"><AnimatedNumber v-if="confidenceNumber(agent.confidence) != null" :value="confidenceNumber(agent.confidence)!" suffix="%" /><span v-else>{{ agent.confidence }}</span></span></div><div class="mt-1 flex flex-wrap gap-1 text-[10px] text-ink-muted"><span>{{ positionLabel(agent.position) }}</span><span>·</span><span>{{ generationSourceLabel(agent.generation_source) }}</span><span>·</span><span>{{ ragStatusLabel(agent.rag_status) }}</span></div><p class="mt-1.5 text-xs leading-relaxed text-ink-secondary">{{ agent.reason }}</p><p v-for="evidence in agent.evidence || []" :key="evidence.tool_name" class="mt-1 text-[10px] text-ink-muted">{{ evidence.tool_name }} · {{ evidence.status === 'hit' ? '已检索' : evidence.status === 'local' ? '本地分析' : '降级' }}</p></div></div>
                    <div v-if="year.debate" class="mt-4 border border-agent-env/30 bg-agent-env/5 p-3"><p class="text-xs font-semibold text-ink-primary">观点分歧</p><p v-for="conflict in year.debate.conflicts" :key="conflict" class="mt-1 text-xs leading-relaxed text-ink-secondary">{{ conflict }}</p><p v-for="recommendation in year.debate.recommendations" :key="recommendation" class="mt-2 text-xs leading-relaxed text-agent-env">建议：{{ recommendation }}</p></div>
                  </article>
                </div>
                <p v-else class="mt-3 text-sm text-ink-muted">这场推演尚未完成年度结算。</p>
              </div>

              <div v-if="reportCache[session.id].risks.length || reportCache[session.id].action_plan.length" class="grid gap-5 border-t border-white/5 pt-4 lg:grid-cols-2">
                <div v-if="reportCache[session.id].risks.length"><h2 class="text-sm font-semibold text-agent-risk">需要关注的风险</h2><div class="mt-3 space-y-2"><div v-for="risk in reportCache[session.id].risks" :key="`${risk.title}-${risk.message}`" class="border border-agent-risk/20 bg-agent-risk/5 px-3 py-2.5"><p class="text-xs font-medium text-agent-risk">{{ risk.level }}风险 · {{ risk.title }}</p><p class="mt-1 text-xs leading-relaxed text-ink-secondary">{{ risk.message }}</p></div></div></div>
                <div v-if="reportCache[session.id].action_plan.length"><h2 class="text-sm font-semibold text-agent-env">后续行动</h2><ol class="mt-3 space-y-2"><li v-for="(action, index) in reportCache[session.id].action_plan" :key="`${index}-${action.title}`" class="flex gap-2 text-xs text-ink-secondary"><span class="font-mono text-agent-env">{{ index + 1 }}</span>{{ action.title }}</li></ol></div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>
