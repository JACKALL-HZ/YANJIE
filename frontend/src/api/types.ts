/** 与后端 openapi.json 对齐的类型定义（21 schemas 核心子集） */

export interface WorldState {
  cash_flow: number
  customer_flow: number
  competition_count: number
  monthly_profit: number
  payback_ratio: number
  metrics: Record<string, number>
}

export type PauseReason =
  | 'year_decision_required'
  | 'decision_preview_required'
  | 'intervention_required'
  | 'horizon_review'

export interface StateMetricDefinition {
  metric_id: string
  label: string
  unit: string
  initial_value: number
  display_order: number
  source_metric?: string | null
}

export interface AgentAction {
  agent_id: string
  action_id: string
  reason: string
  confidence: number
  yearly_strategy: string
  generation_source?: 'llm' | 'stub' | 'fallback'
  llm_called?: boolean
  rag_status?: 'disabled' | 'hit' | 'empty' | 'error'
  rag_sources?: string[]
  position?: 'support' | 'oppose' | 'conditional' | 'neutral'
  evidence?: AgentEvidence[]
  recommendation?: string
  key_factors?: string[]
  next_actions?: string[]
  uncertainty?: string | null
  alternatives?: string[]
  objection?: string | null
  stop_condition?: string | null
}

export interface AgentEvidence {
  tool_name: string
  summary: string
  sources: string[]
  status: 'disabled' | 'hit' | 'empty' | 'error' | 'local'
}

export interface DebateParticipant {
  agent_id: string
  position: 'support' | 'oppose' | 'conditional' | 'neutral'
  reason: string
  recommendation?: string
  objection?: string | null
}

export interface DebateRecord {
  trigger: 'judge_conflict' | 'high_impact_decision'
  conflicts: string[]
  recommendations: string[]
  participants: DebateParticipant[]
  judge_summary?: string
}

export interface EndingReason {
  [key: string]: unknown
}

export interface EndingResult {
  result: string
  reason: EndingReason
}

export interface InterventionRecord {
  [key: string]: unknown
}

export interface TimelineNode {
  year: number
  world_state: WorldState
  agent_actions: AgentAction[]
  state_diff: Record<string, number>
  interventions: InterventionRecord[]
  ending: EndingResult | null
  debate?: DebateRecord | null
  business_dashboard?: BusinessDashboard
}

export interface BusinessDashboard {
  日均单量: number
  月营收: number
  月成本: number
  月净利润: number
  剩余现金流: number
  回本进度: number
  本年决策?: string
  风险预警?: string[]
}

export interface PendingIntervention {
  rule_id: string
  year: number
  event: string
  options: string[]
  metric_snapshot: Record<string, number>
}

export interface DecisionPreview {
  branch_id: 'user_proposal' | 'expert_recommendation' | 'low_cost_alternative'
  label: string
  description: string
  world_state: WorldState
  state_diff: Record<string, number>
  risk_level: 'low' | 'medium' | 'high'
  worst_case_loss: number
  summary: string
}

export interface DecisionPreviewSet {
  decision_id: string
  decision_label: string
  proposal_text: string
  branches: DecisionPreview[]
}

export interface SimulationRequest {
  scenario_id: string
  decision_vars?: Record<string, unknown>
  conversation_history?: Array<{
    role: 'user' | 'agent' | 'system'
    agent_id?: string | null
    content: string
    year?: number | null
  }>
  user_profile?: Record<string, unknown> | null
  intervention_choices?: Record<string, string> | null
  strategy_directives?: Record<string, string> | null
  success_definition?: Record<string, unknown> | null
}

export interface SimulationResponse {
  session_id: string
  scenario_id: string
  phase: string
  year: number
  result: string | null
  timeline: TimelineNode[]
  score: number | null
  score_detail: Record<string, number>
  risks: Record<string, unknown>[]
  action_plan: Record<string, unknown>[]
  startup_settlement?: StartupSettlement
  pending_intervention: PendingIntervention | null
  pending_decision_preview?: DecisionPreviewSet | null
  pause_reason?: PauseReason | null
  input_kind?: string | null
  input_feedback?: string | null
}

export interface SessionDetail {
  id: string
  scenario_id: string
  phase: string
  current_year: number
  decision_vars: Record<string, unknown>
  user_profile: Record<string, unknown>
  decision_history: Array<Record<string, unknown>>
  world_state: WorldState
  timeline: TimelineNode[]
  result: string | null
  score: number | null
  score_detail: Record<string, number>
  risks: Record<string, unknown>[]
  action_plan: Record<string, unknown>[]
  startup_settlement?: StartupSettlement
  pending_intervention?: PendingIntervention | null
  pending_decision_preview?: DecisionPreviewSet | null
  pause_reason?: PauseReason | null
  messages: Array<{
    role: 'user' | 'agent' | 'system'
    agent_id: string | null
    content: string
    year: number | null
  }>
}

export interface ResumeRequest {
  choice?: string | null
  strategy_directives?: Record<string, string> | null
}

export interface CommitActionsRequest {
  committed_actions: Record<string, unknown>[]
}

export interface CompareResponse {
  scenario_id: string
  a: SimulationResponse
  b: SimulationResponse
  comparison: CompareComparison
}

export interface CompareSummary {
  recommendation: {
    winner: 'A' | 'B' | 'tie'
    title: string
    reason: string
  }
  metrics: Array<{
    label: string
    a: string
    b: string
    delta: string
    better: 'A' | 'B' | 'tie'
  }>
  risks: Array<{
    plan: 'A' | 'B'
    level: string
    message: string
  }>
}

export interface CompareComparison {
  assets: { a: number; b: number; delta: number }
  risk: { a: number; b: number; delta: number }
  growth: { a: number; b: number; delta: number }
  pressure: { a: number; b: number }
  ending: { a: string; b: string }
  summary: CompareSummary
}

export interface ScenarioSummary {
  scenario_id: string
  title: string
  [key: string]: unknown
}

export interface ScenarioDetail {
  scenario_id: string
  title: string
  decision_vars: DecisionVarDefinition[]
  state_metrics: StateMetricDefinition[]
  agents: AgentDefinition[]
  action_descriptions: Record<string, string>
}

export interface DecisionVarDefinition {
  name: string
  label: string
  value_type: 'integer' | 'number' | 'string'
  required: boolean
  default: string | number | null
  minimum?: number | null
  maximum?: number | null
}

export interface AgentDefinition {
  agent_id: 'market' | 'environment' | 'personal' | 'risk'
  name: string
  stance: string
  goal: string
  action_ids: string[]
}

export interface SessionSummary {
  id: string
  scenario_id: string
  scenario_title: string
  phase?: string
  current_year?: number
  result?: string | null
  score?: number | null
  created_at?: string
}

export interface ReportMetric {
  label: string
  value: string
  change?: string | null
}

export interface ReportAgentAction {
  agent_id: 'market' | 'environment' | 'personal' | 'risk'
  agent_name: string
  reason: string
  confidence?: string | null
  generation_source?: 'llm' | 'stub' | 'fallback' | null
  llm_called?: boolean | null
  rag_status?: 'disabled' | 'hit' | 'empty' | 'error' | null
  rag_sources?: string[]
  position?: 'support' | 'oppose' | 'conditional' | 'neutral' | null
  evidence?: AgentEvidence[]
  recommendation?: string | null
  alternatives?: string[]
  objection?: string | null
  stop_condition?: string | null
}

export interface ReportDecision {
  year: number
  proposal: string
  decision_label?: string | null
  selected_branch_label?: string | null
  created_at?: string | null
}

export interface ReportYear {
  year: number
  metrics: ReportMetric[]
  agent_actions: ReportAgentAction[]
  ending?: string | null
  debate?: DebateRecord | null
}

export interface ReportScore {
  label: string
  value: string
}

export interface ReportRisk {
  level: string
  title: string
  message: string
}

export interface ReportActionPlanItem {
  title: string
  committed: boolean
}

export interface ReportMessage {
  role: 'user' | 'agent' | 'system'
  agent_id?: string | null
  content: string
  year?: number | null
  created_at?: string | null
}

export interface SessionReport {
  session_id: string
  scenario_id: string
  scenario_title: string
  created_at?: string | null
  profile: ReportMetric[]
  initial_conditions: ReportMetric[]
  decisions: ReportDecision[]
  messages: ReportMessage[]
  years: ReportYear[]
  conclusion: {
    phase: string
    phase_label: string
    result_label: string
    score?: string | null
    score_details: ReportScore[]
  }
  risks: ReportRisk[]
  action_plan: ReportActionPlanItem[]
}

export interface ApiError {
  code: string
  message: string
  request_id?: string
  detail?: Record<string, unknown>
}

/* ── SSE 事件 ─────────────────────────────────── */

export type SimEventType =
  | 'simulation.started'
  | 'year.started'
  | 'year.completed'
  | 'intervention.pending'
  | 'simulation.completed'
  | 'simulation.paused'
  | 'simulation.failed'

export interface SimEvent<T = Record<string, unknown>> {
  sequence: number
  session_id: string
  scenario_id: string
  event_type: SimEventType
  payload: T
}

export interface YearStartedPayload {
  year: number
  world_state: WorldState
  strategy_prompt?: string
  available_strategies?: string[]
  current_strategy?: string
}

export interface YearCompletedPayload {
  year: number
  world_state: WorldState
  state_diff: Record<string, number>
  agent_actions: AgentAction[]
  ending: EndingResult | null
  score: number | null
  debate?: DebateRecord | null
  business_dashboard?: BusinessDashboard
  interventions?: InterventionRecord[]
}

export interface SimulationCompletedPayload {
  year: number
  result: string
  world_state: WorldState
  score: number | null
  score_detail: Record<string, number>
  risks: Record<string, unknown>[]
  action_plan: Record<string, unknown>[]
  startup_settlement?: StartupSettlement
}

export interface StartupSettlement {
  financial_table: Record<string, number>
  key_attributions: Array<Record<string, string>>
  optimal_path: string[]
  scores: Record<string, number>
}

/* ── 拆解 & 追问 ─────────────────────────────── */

export interface BreakdownResult {
  scenario_id: string
  extracted_vars: Record<string, unknown>
  missing_required: string[]
  suggestions: string
  domain?: string | null
  invalid_vars?: Record<string, string>
}

export interface AskResponse {
  session_id: string
  question: string
  answer: string
}

/* ── 认证 ─────────────────────────────────────── */

export interface AuthUser {
  id: string
  username: string
  email: string | null
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface RegisterPayload {
  username: string
  email?: string
  password: string
}

export interface LoginPayload {
  identifier: string
  password: string
}
