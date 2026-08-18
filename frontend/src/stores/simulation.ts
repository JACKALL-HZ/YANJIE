import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { streamSimulation } from '@/api/sse'
import type {
  AgentAction,
  BusinessDashboard,
  DebateRecord,
  DecisionPreviewSet,
  PendingIntervention,
  PauseReason,
  SimEvent,
  SimulationCompletedPayload,
  SimulationRequest,
  SimulationResponse,
  SessionDetail,
  WorldState,
  YearCompletedPayload,
} from '@/api/types'

export type SimPhase =
  | 'idle'
  | 'connecting'
  | 'running'
  | 'paused'
  | 'horizon_review'
  | 'completed'
  | 'failed'

export interface YearRecord {
  year: number
  worldState: WorldState
  stateDiff: Record<string, number>
  agentActions: AgentAction[]
  score: number | null
  debate: DebateRecord | null
  businessDashboard: BusinessDashboard | null
  interventions: Record<string, unknown>[]
}

export const useSimulationStore = defineStore('simulation', () => {
  const phase = ref<SimPhase>('idle')
  const sessionId = ref<string | null>(null)
  const scenarioId = ref<string | null>(null)
  const currentYear = ref(0)
  const worldState = ref<WorldState | null>(null)
  const years = ref<YearRecord[]>([])
  const pending = ref<PendingIntervention | null>(null)
  const pendingDecisionPreview = ref<DecisionPreviewSet | null>(null)
  const pauseReason = ref<PauseReason | null>(null)
  const finalResult = ref<SimulationCompletedPayload | null>(null)
  const initialAnalysis = ref('')
  const errorMsg = ref<string | null>(null)

  let aborter: AbortController | null = null
  let connectTimer: ReturnType<typeof setTimeout> | null = null

  const isLive = computed(
    () => phase.value === 'connecting' || phase.value === 'running',
  )

  function clearConnectTimer() {
    if (connectTimer) { clearTimeout(connectTimer); connectTimer = null }
  }

  function handleEvent(ev: SimEvent) {
    if (ev.event_type !== 'simulation.failed') errorMsg.value = null
    switch (ev.event_type) {
      case 'simulation.started': {
        const p = ev.payload as { year: number; world_state: WorldState; initial_analysis?: string }
        currentYear.value = p.year
        initialAnalysis.value = p.initial_analysis || ''
        worldState.value = p.world_state
        pauseReason.value = null
        phase.value = 'running'
        break
      }
      case 'year.started': {
        const p = ev.payload as { year: number; world_state: WorldState }
        currentYear.value = p.year
        worldState.value = p.world_state
        break
      }
      case 'year.completed': {
        const p = ev.payload as unknown as YearCompletedPayload
        currentYear.value = p.year
        worldState.value = p.world_state
        years.value.push({
          year: p.year,
          worldState: p.world_state,
          stateDiff: p.state_diff,
          agentActions: p.agent_actions || [],
          score: p.score,
          debate: p.debate ?? null,
          businessDashboard: p.business_dashboard ?? null,
          interventions: p.interventions ?? [],
        })
        break
      }
      case 'intervention.pending': {
        const p = ev.payload as { pending_intervention: PendingIntervention }
        pending.value = p.pending_intervention
        pauseReason.value = 'intervention_required'
        phase.value = 'paused'
        break
      }
      case 'simulation.paused': {
        const p = ev.payload as { pause_reason?: PauseReason | null }
        pauseReason.value = p.pause_reason ?? null
        phase.value = p.pause_reason === 'horizon_review' ? 'horizon_review' : 'paused'
        break
      }
      case 'simulation.completed': {
        finalResult.value = ev.payload as unknown as SimulationCompletedPayload
        pauseReason.value = null
        phase.value = 'completed'
        break
      }
      case 'simulation.failed': {
        const p = ev.payload as { message?: string; code?: string }
        errorMsg.value = p.message || p.code || '推演失败'
        phase.value = 'failed'
        break
      }
    }
  }

  function start(req: SimulationRequest) {
    stop()
    phase.value = 'connecting'
    sessionId.value = null
    scenarioId.value = req.scenario_id
    currentYear.value = 0
    worldState.value = null
    years.value = []
    pending.value = null
    pendingDecisionPreview.value = null
    pauseReason.value = null
    finalResult.value = null
    initialAnalysis.value = ''
    errorMsg.value = null

    // 连接超时：30 秒收不到第一个事件则报错
    connectTimer = setTimeout(() => {
      if (phase.value === 'connecting') {
        errorMsg.value = '推演引擎连接超时，请确认后端服务已启动'
        phase.value = 'failed'
      }
    }, 30_000)

    aborter = new AbortController()
    void streamSimulation(
      req,
      {
        onOpen: () => {
          clearConnectTimer()
        },
        onEvent: (ev) => {
          clearConnectTimer()
          sessionId.value = ev.session_id
          handleEvent(ev)
        },
        onError: (e) => {
          clearConnectTimer()
          errorMsg.value = e.message
          phase.value = 'failed'
        },
        onDone: () => {
          clearConnectTimer()
          if (phase.value === 'running' || phase.value === 'connecting') {
            // 流结束但未到 completed：保持现状（可能暂停中）
          }
        },
      },
      aborter.signal,
    )
  }

  /** resume 端点返回完整 SimulationResponse：合并时间线 + 终局 */
  function applyResponse(resp: SimulationResponse) {
    sessionId.value = resp.session_id
    currentYear.value = resp.year
    // 用完整 timeline 重建年份记录（去重已有年份）
    const existing = new Set(years.value.map((y) => y.year))
    for (const node of resp.timeline) {
      if (existing.has(node.year)) continue
      years.value.push({
        year: node.year,
        worldState: node.world_state,
        stateDiff: node.state_diff,
        agentActions: node.agent_actions || [],
        score: null,
        debate: node.debate ?? null,
        businessDashboard: node.business_dashboard ?? null,
        interventions: node.interventions ?? [],
      })
    }
    const last = resp.timeline[resp.timeline.length - 1]
    if (last) worldState.value = last.world_state
    pending.value = resp.pending_intervention
    pendingDecisionPreview.value = resp.pending_decision_preview ?? null
    pauseReason.value = resp.pause_reason ?? null
    if (resp.phase === 'completed') {
      finalResult.value = {
        year: resp.year,
        result: resp.result ?? 'timeout',
        world_state: (last?.world_state ?? worldState.value)!,
        score: resp.score,
        score_detail: resp.score_detail,
        risks: resp.risks,
        action_plan: resp.action_plan,
        startup_settlement: resp.startup_settlement,
      }
      phase.value = 'completed'
    } else if (resp.phase === 'paused' || resp.phase === 'horizon_review') {
      phase.value = resp.phase
    } else {
      phase.value = 'running'
    }
  }

  function restoreSession(detail: SessionDetail) {
    stop()
    sessionId.value = detail.id
    scenarioId.value = detail.scenario_id
    currentYear.value = detail.current_year
    years.value = detail.timeline.map((node) => ({
      year: node.year,
      worldState: node.world_state,
      stateDiff: node.state_diff,
      agentActions: node.agent_actions || [],
      score: null,
      debate: node.debate ?? null,
      businessDashboard: node.business_dashboard ?? null,
      interventions: node.interventions ?? [],
    }))
    const latestTimelineNode = detail.timeline[detail.timeline.length - 1]
    worldState.value = latestTimelineNode?.world_state ?? detail.world_state
    pending.value = detail.pending_intervention ?? null
    pendingDecisionPreview.value = detail.pending_decision_preview ?? null
    pauseReason.value = detail.pause_reason ?? null
    errorMsg.value = null
    if (detail.phase === 'completed') {
      finalResult.value = {
        year: detail.current_year,
        result: detail.result ?? 'timeout',
        world_state: worldState.value!,
        score: detail.score,
        score_detail: detail.score_detail,
        risks: detail.risks,
        action_plan: detail.action_plan,
        startup_settlement: detail.startup_settlement,
      }
      phase.value = 'completed'
    } else if (detail.phase === 'paused' || detail.phase === 'horizon_review') {
      phase.value = detail.phase
    } else {
      phase.value = 'running'
    }
  }

  function stop() {
    clearConnectTimer()
    aborter?.abort()
    aborter = null
  }

  function reset() {
    stop()
    clearConnectTimer()
    phase.value = 'idle'
    sessionId.value = null
    scenarioId.value = null
    currentYear.value = 0
    worldState.value = null
    years.value = []
    pending.value = null
    pendingDecisionPreview.value = null
    pauseReason.value = null
    finalResult.value = null
    initialAnalysis.value = ''
    errorMsg.value = null
  }

  return {
    phase,
    sessionId,
    scenarioId,
    currentYear,
    worldState,
    years,
    pending,
    pendingDecisionPreview,
    pauseReason,
    finalResult,
    initialAnalysis,
    errorMsg,
    isLive,
    start,
    stop,
    reset,
    applyResponse,
    restoreSession,
    clearConnectTimer,
  }
})
