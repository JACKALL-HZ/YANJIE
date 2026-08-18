/**
 * 用户画像 —— 类型、枚举取值、字段元数据、API 封装。
 *
 * 字段口径与后端 `app/schemas/profile.py`、`app/db/models.py:UserProfile` 严格一致；
 * 派生指标 derived 由后端 `app/engine/profile_summary.compute_derived` 实时计算，
 * 前端只做展示，保证「用户看到的数字」与「Agent 感知的数字」同源。
 */
import { api } from './client'

/* ── 派生指标（后端算，不落库）─────────────────── */
export interface ProfileDerived {
  net_worth?: number
  debt_ratio?: number
  max_affordable_loss?: number
  runway_months?: number
  monthly_surplus?: number
  completeness: number
  filled_fields: number
  total_fields: number
}

/* ── 画像主体（六维度 28 字段）─────────────────── */
export interface Profile {
  id?: string
  user_id: string
  // 1. 基本信息
  age: number | null
  gender: string | null
  city: string | null
  education: string | null
  marital_status: string | null
  dependents: number | null
  family_burden: boolean | null
  // 2. 职业与能力
  occupation: string | null
  industry: string | null
  years_experience: number | null
  skills: string[]
  certificates: string[]
  career_history: string | null
  strengths: string | null
  weaknesses: string | null
  // 3. 财务状况
  assets: number | null
  monthly_income: number | null
  monthly_expense: number | null
  liabilities: number | null
  income_stability: string | null
  insurance: string[]
  // 4. 风险与决策
  risk_appetite: string | null
  loss_tolerance: number | null
  decision_style: string | null
  past_failures: string | null
  // 5. 时间与资源
  available_time: string | null
  weekly_hours: number | null
  support_network: string | null
  // 6. 目标与约束
  goals: string[]
  constraints: string | null
  time_horizon: number | null
  motivation: string | null
  created_at?: string | null
  updated_at?: string | null
  derived?: ProfileDerived
}

/** 可提交给 PUT /profiles/{id} 的字段（不含 id / user_id / 时间戳 / derived） */
export type ProfilePatch = Partial<
  Omit<Profile, 'id' | 'user_id' | 'created_at' | 'updated_at' | 'derived'>
>

export function emptyProfile(userId = ''): Profile {
  return {
    user_id: userId,
    age: null, gender: null, city: null, education: null,
    marital_status: null, dependents: null, family_burden: false,
    occupation: null, industry: null, years_experience: null,
    skills: [], certificates: [], career_history: null,
    strengths: null, weaknesses: null,
    assets: null, monthly_income: null, monthly_expense: null,
    liabilities: null, income_stability: null, insurance: [],
    risk_appetite: null, loss_tolerance: null, decision_style: null,
    past_failures: null,
    available_time: null, weekly_hours: null, support_network: null,
    goals: [], constraints: null, time_horizon: null, motivation: null,
  }
}

/* ── 枚举取值（与后端 *_CHOICES 对齐）───────────── */
export interface Option { value: string; label: string; hint?: string }

export const EDUCATION_OPTIONS: Option[] = [
  { value: 'high_school', label: '高中' },
  { value: 'college', label: '大专' },
  { value: 'bachelor', label: '本科' },
  { value: 'master', label: '硕士' },
  { value: 'phd', label: '博士' },
  { value: 'other', label: '其他' },
]

export const MARITAL_OPTIONS: Option[] = [
  { value: 'single', label: '未婚' },
  { value: 'married', label: '已婚' },
  { value: 'divorced', label: '离异' },
  { value: 'widowed', label: '丧偶' },
]

export const INCOME_STABILITY_OPTIONS: Option[] = [
  { value: 'stable', label: '稳定', hint: '固定薪资 / 长期合同' },
  { value: 'fluctuating', label: '有波动', hint: '提成 / 项目制' },
  { value: 'unstable', label: '不稳定', hint: '自由职业 / 无固定来源' },
]

export const RISK_OPTIONS: Option[] = [
  { value: 'conservative', label: '保守', hint: '本金安全优先' },
  { value: 'balanced', label: '平衡', hint: '收益与风险兼顾' },
  { value: 'aggressive', label: '激进', hint: '愿承担大波动博高回报' },
]

export const DECISION_STYLE_OPTIONS: Option[] = [
  { value: 'analytical', label: '分析型', hint: '看数据再下结论' },
  { value: 'intuitive', label: '直觉型', hint: '相信盘感' },
  { value: 'decisive', label: '果断型', hint: '快速拍板' },
  { value: 'consensus', label: '共识型', hint: '多方商量后定' },
]

export const AVAILABLE_TIME_OPTIONS: Option[] = [
  { value: 'fulltime', label: '全职', hint: '可 all in' },
  { value: 'parttime', label: '兼职', hint: '保留主业' },
  { value: 'spare', label: '业余', hint: '下班后推进' },
  { value: 'weekend', label: '仅周末', hint: '每周 1–2 天' },
]

export const RISK_LABEL: Record<string, string> = Object.fromEntries(
  RISK_OPTIONS.map((o) => [o.value, o.label]),
)

/* ── 六维度分组元数据（驱动表单渲染 + 导航）────── */
export interface ProfileSection {
  key: string
  title: string
  desc: string
  /** 该组包含的字段名，用于分组完成度统计 */
  fields: (keyof ProfilePatch)[]
}

export const PROFILE_SECTIONS: ProfileSection[] = [
  {
    key: 'basic',
    title: '基本信息',
    desc: '年龄、城市、家庭结构 —— 决定你的风险底盘',
    fields: ['age', 'gender', 'city', 'education', 'marital_status', 'dependents'],
  },
  {
    key: 'career',
    title: '职业与能力',
    desc: '你手里的牌：经验、技能、资质与短板',
    fields: [
      'occupation', 'industry', 'years_experience', 'skills',
      'certificates', 'career_history', 'strengths', 'weaknesses',
    ],
  },
  {
    key: 'finance',
    title: '财务状况',
    desc: '推演里最硬的约束 —— 钱能撑多久',
    fields: [
      'assets', 'monthly_income', 'monthly_expense',
      'liabilities', 'income_stability', 'insurance',
    ],
  },
  {
    key: 'risk',
    title: '风险与决策',
    desc: '你能扛多大的亏，以及你习惯怎么做决定',
    fields: ['risk_appetite', 'loss_tolerance', 'decision_style', 'past_failures'],
  },
  {
    key: 'time',
    title: '时间与资源',
    desc: '除了钱，你还能投入什么',
    fields: ['available_time', 'weekly_hours', 'support_network'],
  },
  {
    key: 'goal',
    title: '目标与约束',
    desc: '你要什么，以及什么绝不能碰',
    fields: ['goals', 'constraints', 'time_horizon', 'motivation'],
  },
]

/** 与后端 COMPLETENESS_FIELDS 一致的 31 项（family_burden 不计入） */
export const COMPLETENESS_FIELDS: (keyof ProfilePatch)[] =
  PROFILE_SECTIONS.flatMap((s) => s.fields)

export function isFilled(v: unknown): boolean {
  if (v === null || v === undefined) return false
  if (typeof v === 'string') return v.trim().length > 0
  if (Array.isArray(v)) return v.length > 0
  return true
}

/** 单个维度的填写进度（本地实时算，不等后端返回） */
export function sectionProgress(
  section: ProfileSection,
  data: Record<string, unknown>,
): { filled: number; total: number } {
  const filled = section.fields.filter((f) => isFilled(data[f as string])).length
  return { filled, total: section.fields.length }
}

/**
 * 本地派生指标计算 —— 公式镜像后端 `compute_derived`，
 * 目的是让用户边填边看到净资产/跑道变化，不必等保存往返。
 * 保存后仍以服务端返回的 derived 为准（两边公式一致，结果相同）。
 */
export function computeDerived(p: Record<string, unknown>): ProfileDerived {
  const num = (k: string): number | null => {
    const v = p[k]
    return typeof v === 'number' && !Number.isNaN(v) ? v : null
  }
  const assets = num('assets')
  const liabilities = num('liabilities')
  const income = num('monthly_income')
  const expense = num('monthly_expense')
  const lossTolerance = num('loss_tolerance')

  const d: ProfileDerived = {
    completeness: 0,
    filled_fields: 0,
    total_fields: COMPLETENESS_FIELDS.length,
  }
  if (assets !== null) {
    d.net_worth = assets - (liabilities ?? 0)
    if (liabilities && assets) d.debt_ratio = Math.round((liabilities / assets) * 1000) / 1000
    if (lossTolerance !== null) d.max_affordable_loss = Math.floor((assets * lossTolerance) / 100)
    if (expense) d.runway_months = Math.round((assets / expense) * 10) / 10
  }
  if (income !== null && expense !== null) d.monthly_surplus = income - expense

  const filled = COMPLETENESS_FIELDS.filter((f) => isFilled(p[f as string])).length
  d.filled_fields = filled
  d.completeness = Math.round((filled / COMPLETENESS_FIELDS.length) * 100) / 100
  return d
}

/* ── 金额格式化（与后端摘要口径一致：>=1万 显示万元）── */
export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  if (Math.abs(v) >= 10000) {
    return `${(v / 10000).toFixed(1).replace(/\.0$/, '')} 万`
  }
  return `${v}`
}

/* ── API ─────────────────────────────────────── */
export interface ProfileMeResponse {
  exists: boolean
  profile: Profile | null
}

export const profileApi = {
  /** 软探针：未建画像返回 exists=false，不抛 404 */
  me: () => api.get<ProfileMeResponse>('/profiles/me'),
  create: () => api.post<Profile>('/profiles', {}),
  update: (userId: string, patch: ProfilePatch) =>
    api.put<Profile>(`/profiles/${encodeURIComponent(userId)}`, patch),
}
