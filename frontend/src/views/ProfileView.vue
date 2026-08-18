<script setup lang="ts">
/**
 * 个人画像 —— 六维度结构化录入。
 *
 * 这里填的不是「个人资料」，是推演的输入参数：
 * 资产决定预算压力、负债与月支出决定现金跑道、风险偏好与可承受亏损
 * 决定 Agent 判定激进方案时的容忍度。填得越全，推演越贴身。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import SkeletonCard from '@/components/ui/SkeletonCard.vue'
import PillSelect from '@/components/ui/PillSelect.vue'
import TagInput from '@/components/ui/TagInput.vue'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'
import {
  AVAILABLE_TIME_OPTIONS,
  COMPLETENESS_FIELDS,
  DECISION_STYLE_OPTIONS,
  EDUCATION_OPTIONS,
  INCOME_STABILITY_OPTIONS,
  MARITAL_OPTIONS,
  PROFILE_SECTIONS,
  RISK_OPTIONS,
  computeDerived,
  emptyProfile,
  money,
  profileApi,
  sectionProgress,
  type Profile,
  type ProfilePatch,
} from '@/api/profile'

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const creating = ref(false)
const exists = ref(false)
const errorMsg = ref<string | null>(null)
const savedTip = ref(false)
const dirty = ref(false)
let hydrating = false

const form = reactive<Profile>(emptyProfile())
const activeKey = ref(PROFILE_SECTIONS[0].key)

const SKILL_SUGGESTIONS = ['产品设计', '数据分析', '市场营销', '供应链', '前端开发', '销售谈判', '内容运营', '财务建模']
const GOAL_SUGGESTIONS = ['财务自由', '副业转正', '换城市生活', '积累行业口碑', '陪伴家人', '技能转型']
const INSURANCE_SUGGESTIONS = ['社保', '医疗险', '重疾险', '意外险', '寿险', '车险']

/* ── 派生指标：边填边算，不等保存往返 ─────────── */
const derived = computed(() => computeDerived(form as unknown as Record<string, unknown>))
const completenessPct = computed(() => Math.round(derived.value.completeness * 100))

const sectionStats = computed(() =>
  PROFILE_SECTIONS.map((s) => ({
    ...s,
    ...sectionProgress(s, form as unknown as Record<string, unknown>),
  })),
)

const activeSection = computed(
  () => sectionStats.value.find((s) => s.key === activeKey.value) ?? sectionStats.value[0],
)

const activeIndex = computed(() => PROFILE_SECTIONS.findIndex((s) => s.key === activeKey.value))

/** 完成度环形进度的 stroke-dashoffset */
const RING = 2 * Math.PI * 34
const ringOffset = computed(() => RING * (1 - derived.value.completeness))

const gradeText = computed(() => {
  const p = completenessPct.value
  if (p >= 85) return '画像充分 · 智能体可做精细推演'
  if (p >= 55) return '画像可用 · 补齐财务项会更准'
  if (p >= 25) return '画像偏薄 · 智能体只能给通用建议'
  return '几乎空白 · 推演结果参考价值有限'
})

/* ── 数据装载 ───────────────────────────────── */
function hydrate(p: Profile) {
  hydrating = true
  Object.assign(form, emptyProfile(p.user_id), p, {
    skills: [...(p.skills ?? [])],
    certificates: [...(p.certificates ?? [])],
    insurance: [...(p.insurance ?? [])],
    goals: [...(p.goals ?? [])],
  })
  requestAnimationFrame(() => {
    hydrating = false
    dirty.value = false
  })
}

async function load() {
  loading.value = true
  errorMsg.value = null
  try {
    const res = await profileApi.me()
    exists.value = res.exists
    if (res.exists && res.profile) hydrate(res.profile)
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function createProfile() {
  if (creating.value) return
  creating.value = true
  errorMsg.value = null
  try {
    const p = await profileApi.create()
    exists.value = true
    hydrate(p)
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    creating.value = false
  }
}

/* ── 保存 ───────────────────────────────────── */
function buildPatch(): ProfilePatch {
  const patch: Record<string, unknown> = {}
  for (const f of COMPLETENESS_FIELDS) {
    const v = (form as unknown as Record<string, unknown>)[f as string]
    if (typeof v === 'string') patch[f as string] = v.trim() === '' ? null : v.trim()
    else if (typeof v === 'number' && Number.isNaN(v)) patch[f as string] = null
    else patch[f as string] = v ?? null
  }
  patch.family_burden = !!form.family_burden
  return patch as ProfilePatch
}

async function save() {
  if (!exists.value || saving.value) return
  saving.value = true
  savedTip.value = false
  errorMsg.value = null
  try {
    const updated = await profileApi.update(form.user_id, buildPatch())
    hydrate(updated)
    savedTip.value = true
    setTimeout(() => (savedTip.value = false), 2400)
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

/* 数字输入：清空时写 null 而不是空串，避免后端 422 */
function setNum(key: keyof Profile, e: Event) {
  const raw = (e.target as HTMLInputElement).value
  ;(form as unknown as Record<string, unknown>)[key as string] = raw === '' ? null : Number(raw)
}

function goSection(key: string) {
  activeKey.value = key
  document.getElementById('profile-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function step(delta: number) {
  const next = activeIndex.value + delta
  if (next >= 0 && next < PROFILE_SECTIONS.length) goSection(PROFILE_SECTIONS[next].key)
}

watch(form, () => { if (!hydrating) dirty.value = true }, { deep: true })

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return window.confirm('画像有未保存的修改，确定离开吗？')
})

onMounted(load)
</script>

<template>
  <div class="min-h-[100dvh]">
    <NavBar />

    <main class="mx-auto max-w-[1400px] px-5 pb-28 pt-24 md:px-8 md:pt-28">
      <!-- 头部 -->
      <div class="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p class="eyebrow mb-2">个人画像</p>
          <h1 class="font-display text-3xl font-bold tracking-tight md:text-4xl">你的决策底牌</h1>
          <p class="mt-3 max-w-[600px] text-sm leading-relaxed text-ink-secondary">
            推演不是空中楼阁。资产决定这一把压上了多少身家，负债与月支出决定你能撑几个月，
            风险偏好决定智能体何时该拉你一把 —— 填得越全，四个智能体的博弈就越贴着你的现实。
          </p>
        </div>
        <div class="relative hidden h-[150px] w-[280px] overflow-hidden rounded-card md:block">
          <img src="/assets/img/astronaut.jpg" alt="" class="h-full w-full object-cover opacity-75" loading="lazy" />
          <div class="absolute inset-0 bg-gradient-to-r from-[rgba(11,15,26,0.96)] via-[rgba(11,15,26,0.45)] to-transparent" />
        </div>
      </div>

      <!-- 加载骨架 -->
      <div v-if="loading" class="mt-8 grid gap-6 lg:grid-cols-[300px_1fr]">
        <SkeletonCard :lines="4" />
        <SkeletonCard :lines="8" />
      </div>

      <!-- 未创建：空态引导 -->
      <GlassPanel v-else-if="!exists" strong class="mt-8">
        <div class="flex flex-col items-center py-10 text-center">
          <div class="mb-5 flex h-16 w-16 items-center justify-center rounded-full border border-brand/30 bg-brand/10 text-2xl">◎</div>
          <h2 class="font-display text-xl font-bold">还没有画像</h2>
          <p class="mt-2 max-w-[440px] text-sm leading-relaxed text-ink-secondary">
            没有画像也能推演，但智能体只能按通用假设算。建一份画像，
            它会在每次推演开始时被冻结成快照，跟着这次推演一起存档。
          </p>
          <div class="mt-6">
            <FancyButton :disabled="creating" @click="createProfile">
              {{ creating ? '创建中…' : '创建我的画像' }}
            </FancyButton>
          </div>
        </div>
      </GlassPanel>

      <!-- 主体 -->
      <div v-else class="mt-8 grid gap-6 lg:grid-cols-[300px_1fr]">
        <!-- 左：完成度 + 维度导航 + 派生指标 -->
        <div class="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <GlassPanel strong>
            <div class="flex items-center gap-4">
              <div class="relative h-[84px] w-[84px] shrink-0">
                <svg viewBox="0 0 80 80" class="h-full w-full -rotate-90">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="7" />
                  <circle
                    cx="40" cy="40" r="34" fill="none" stroke="url(#ringGrad)" stroke-width="7"
                    stroke-linecap="round" :stroke-dasharray="RING" :stroke-dashoffset="ringOffset"
                    style="transition: stroke-dashoffset 0.6s cubic-bezier(0.16,1,0.3,1)"
                  />
                  <defs>
                    <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stop-color="#22D3EE" />
                      <stop offset="100%" stop-color="#4F8CFF" />
                    </linearGradient>
                  </defs>
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="font-mono text-lg font-bold leading-none">{{ completenessPct }}<span class="text-xs">%</span></span>
                </div>
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold">画像完成度</div>
                <div class="mt-1 text-xs leading-snug text-ink-muted">{{ gradeText }}</div>
                <div class="mt-1.5 font-mono text-[11px] text-ink-muted">
                  {{ derived.filled_fields }} / {{ derived.total_fields }} 项
                </div>
              </div>
            </div>
          </GlassPanel>

          <!-- 维度导航 -->
          <nav class="glass overflow-hidden rounded-card">
            <button
              v-for="(s, i) in sectionStats"
              :key="s.key"
              type="button"
              class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-200"
              :class="[
                activeKey === s.key ? 'bg-brand/10' : 'hover:bg-white/[0.03]',
                i > 0 ? 'border-t border-white/5' : '',
              ]"
              @click="goSection(s.key)"
            >
              <span
                class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px]"
                :class="s.filled === s.total
                  ? 'bg-agent-env/15 text-agent-env'
                  : activeKey === s.key ? 'bg-brand/20 text-brand' : 'bg-white/5 text-ink-muted'"
              >{{ s.filled === s.total ? '✓' : i + 1 }}</span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm" :class="activeKey === s.key ? 'text-ink-primary' : 'text-ink-secondary'">
                  {{ s.title }}
                </span>
                <span class="mt-1 block h-[3px] w-full overflow-hidden rounded-full bg-white/6">
                  <span
                    class="block h-full rounded-full bg-gradient-to-r from-cyan-glow to-brand transition-all duration-500 ease-smooth"
                    :style="{ width: `${(s.filled / s.total) * 100}%` }"
                  />
                </span>
              </span>
              <span class="shrink-0 font-mono text-[11px] text-ink-muted">{{ s.filled }}/{{ s.total }}</span>
            </button>
          </nav>

          <!-- 派生指标 -->
          <GlassPanel>
            <h3 class="mb-3 text-xs font-semibold tracking-wider text-ink-muted">推演读到的指标</h3>
            <dl class="space-y-2.5 text-sm">
              <div class="flex items-baseline justify-between gap-3">
                <dt class="text-ink-muted">净资产</dt>
                <dd class="font-mono" :class="(derived.net_worth ?? 0) < 0 ? 'text-agent-risk' : 'text-ink-primary'">
                  <AnimatedNumber v-if="derived.net_worth != null" :value="derived.net_worth" :format="money" />
                  <span v-else>—</span>
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="text-ink-muted">月结余</dt>
                <dd class="font-mono" :class="(derived.monthly_surplus ?? 0) < 0 ? 'text-agent-risk' : 'text-agent-env'">
                  <AnimatedNumber v-if="derived.monthly_surplus != null" :value="derived.monthly_surplus" :format="money" />
                  <span v-else>—</span>
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="text-ink-muted">现金跑道</dt>
                <dd class="font-mono text-ink-primary">
                  <AnimatedNumber v-if="derived.runway_months != null" :value="derived.runway_months" suffix=" 个月" />
                  <span v-else>—</span>
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="text-ink-muted">可承受亏损</dt>
                <dd class="font-mono text-ink-primary">
                  <AnimatedNumber v-if="derived.max_affordable_loss != null" :value="derived.max_affordable_loss" :format="money" />
                  <span v-else>—</span>
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="text-ink-muted">负债率</dt>
                <dd class="font-mono" :class="(derived.debt_ratio ?? 0) > 0.6 ? 'text-agent-risk' : 'text-ink-primary'">
                  <AnimatedNumber v-if="derived.debt_ratio != null" :value="(derived.debt_ratio ?? 0) * 100" suffix="%" />
                  <span v-else>—</span>
                </dd>
              </div>
            </dl>
            <p class="mt-3 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-ink-muted">
              推演启动时，智能体会把本次投入金额与你的资产、可承受亏损做对照，
              判断这一把是「小试」还是「压上全部身家」。
            </p>
          </GlassPanel>
        </div>

        <!-- 右：表单 -->
        <div id="profile-form">
          <GlassPanel strong>
            <div class="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-white/6 pb-5">
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-mono text-xs text-brand">0{{ activeIndex + 1 }}</span>
                  <h2 class="font-display text-xl font-bold">{{ activeSection.title }}</h2>
                </div>
                <p class="mt-1.5 text-sm text-ink-secondary">{{ activeSection.desc }}</p>
              </div>
              <span
                class="rounded-chip border px-3 py-1 font-mono text-[11px]"
                :class="dirty ? 'border-brand/40 bg-brand/10 text-brand' : 'border-white/8 text-ink-muted'"
              >{{ dirty ? '有未保存修改' : '已同步' }}</span>
            </div>

            <!-- 1. 基本信息 -->
            <section v-show="activeKey === 'basic'" class="space-y-5">
              <div class="grid gap-5 sm:grid-cols-3">
                <div>
                  <label class="fld-label">年龄</label>
                  <input :value="form.age" type="number" min="0" max="150" class="fld-input" placeholder="如 32" @input="setNum('age', $event)" />
                </div>
                <div>
                  <label class="fld-label">性别</label>
                  <input v-model="form.gender" type="text" class="fld-input" placeholder="选填" />
                </div>
                <div>
                  <label class="fld-label">所在城市</label>
                  <input v-model="form.city" type="text" class="fld-input" placeholder="如 杭州" />
                </div>
              </div>

              <div>
                <label class="fld-label">学历</label>
                <PillSelect v-model="form.education" :options="EDUCATION_OPTIONS" />
              </div>

              <div class="grid gap-5 sm:grid-cols-2">
                <div>
                  <label class="fld-label">婚姻状况</label>
                  <PillSelect v-model="form.marital_status" :options="MARITAL_OPTIONS" />
                </div>
                <div>
                  <label class="fld-label">需抚养人数</label>
                  <input :value="form.dependents" type="number" min="0" max="20" class="fld-input" placeholder="老人 + 小孩" @input="setNum('dependents', $event)" />
                  <p class="fld-hint">抚养人数越多，智能体对现金流断裂的容忍度越低。</p>
                </div>
              </div>

              <label class="flex cursor-pointer items-center gap-3 text-sm text-ink-secondary">
                <button
                  type="button" role="switch" :aria-checked="!!form.family_burden"
                  class="relative h-6 w-11 shrink-0 rounded-full transition-colors"
                  :class="form.family_burden ? 'bg-brand' : 'bg-white/10'"
                  @click="form.family_burden = !form.family_burden"
                >
                  <span class="absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all" :class="form.family_burden ? 'left-[22px]' : 'left-0.5'" />
                </button>
                有明确家庭负担（房贷、赡养、子女教育等刚性支出）
              </label>
            </section>

            <!-- 2. 职业与能力 -->
            <section v-show="activeKey === 'career'" class="space-y-5">
              <div class="grid gap-5 sm:grid-cols-3">
                <div>
                  <label class="fld-label">当前职业</label>
                  <input v-model="form.occupation" type="text" class="fld-input" placeholder="如 产品经理" />
                </div>
                <div>
                  <label class="fld-label">所在行业</label>
                  <input v-model="form.industry" type="text" class="fld-input" placeholder="如 互联网 / 餐饮" />
                </div>
                <div>
                  <label class="fld-label">工作年限</label>
                  <input :value="form.years_experience" type="number" min="0" max="80" class="fld-input" placeholder="年" @input="setNum('years_experience', $event)" />
                </div>
              </div>

              <div>
                <label class="fld-label">技能标签</label>
                <TagInput v-model="form.skills" :suggestions="SKILL_SUGGESTIONS" placeholder="输入技能后回车" />
              </div>

              <div>
                <label class="fld-label">资质 / 证书</label>
                <TagInput v-model="form.certificates" accent="brand" placeholder="如 CPA、教师资格证" />
              </div>

              <div>
                <label class="fld-label">职业经历</label>
                <textarea v-model="form.career_history" rows="4" class="fld-input" placeholder="做过什么、带过多大盘子、有没有从 0 到 1 的经验。" />
              </div>

              <div class="grid gap-5 sm:grid-cols-2">
                <div>
                  <label class="fld-label">个人优势</label>
                  <textarea v-model="form.strengths" rows="3" class="fld-input" placeholder="你比同行强在哪。" />
                </div>
                <div>
                  <label class="fld-label">已知短板</label>
                  <textarea v-model="form.weaknesses" rows="3" class="fld-input" placeholder="诚实点，智能体会据此提示风险。" />
                </div>
              </div>
            </section>

            <!-- 3. 财务状况 -->
            <section v-show="activeKey === 'finance'" class="space-y-5">
              <div class="grid gap-5 sm:grid-cols-2">
                <div>
                  <label class="fld-label">可支配资产（元）</label>
                  <input :value="form.assets" type="number" min="0" step="10000" class="fld-input" placeholder="现金 + 可快速变现资产" @input="setNum('assets', $event)" />
                  <p class="fld-hint">推演预算会与它对照，算出「压上了几成身家」。</p>
                </div>
                <div>
                  <label class="fld-label">负债总额（元）</label>
                  <input :value="form.liabilities" type="number" min="0" step="10000" class="fld-input" placeholder="房贷 + 车贷 + 信用负债" @input="setNum('liabilities', $event)" />
                </div>
                <div>
                  <label class="fld-label">月收入（元）</label>
                  <input :value="form.monthly_income" type="number" min="0" step="1000" class="fld-input" placeholder="税后" @input="setNum('monthly_income', $event)" />
                </div>
                <div>
                  <label class="fld-label">月支出（元）</label>
                  <input :value="form.monthly_expense" type="number" min="0" step="1000" class="fld-input" placeholder="含房贷、生活、赡养" @input="setNum('monthly_expense', $event)" />
                </div>
              </div>

              <div
                v-if="derived.runway_months != null || derived.monthly_surplus != null"
                class="rounded-btn border border-white/8 bg-white/[0.02] px-4 py-3 text-sm"
              >
                <span class="text-ink-muted">实时测算：</span>
                <span v-if="derived.monthly_surplus != null" class="ml-1 font-mono" :class="derived.monthly_surplus < 0 ? 'text-agent-risk' : 'text-agent-env'">
                  月结余 {{ money(derived.monthly_surplus) }}
                </span>
                <span v-if="derived.runway_months != null" class="ml-3 font-mono text-ink-primary">
                  纯靠资产可撑 {{ derived.runway_months }} 个月
                </span>
              </div>

              <div>
                <label class="fld-label">收入稳定性</label>
                <PillSelect v-model="form.income_stability" :options="INCOME_STABILITY_OPTIONS" />
              </div>

              <div>
                <label class="fld-label">已有保险覆盖</label>
                <TagInput v-model="form.insurance" accent="personal" :suggestions="INSURANCE_SUGGESTIONS" placeholder="如 重疾险" />
              </div>
            </section>

            <!-- 4. 风险与决策 -->
            <section v-show="activeKey === 'risk'" class="space-y-5">
              <div>
                <label class="fld-label">风险偏好</label>
                <PillSelect v-model="form.risk_appetite" :options="RISK_OPTIONS" />
              </div>

              <div>
                <label class="fld-label">
                  可承受最大亏损
                  <span class="ml-2 font-mono text-brand">{{ form.loss_tolerance ?? 0 }}%</span>
                  <span v-if="derived.max_affordable_loss != null" class="ml-2 font-mono text-ink-muted">
                    ≈ {{ money(derived.max_affordable_loss) }}
                  </span>
                </label>
                <input
                  :value="form.loss_tolerance ?? 0" type="range" min="0" max="100" step="5"
                  class="fld-range" @input="setNum('loss_tolerance', $event)"
                />
                <div class="mt-1 flex justify-between font-mono text-[10px] text-ink-muted">
                  <span>0% 不能亏</span><span>50%</span><span>100% 全押</span>
                </div>
              </div>

              <div>
                <label class="fld-label">决策风格</label>
                <PillSelect v-model="form.decision_style" :options="DECISION_STYLE_OPTIONS" />
              </div>

              <div>
                <label class="fld-label">过往失败经历</label>
                <textarea v-model="form.past_failures" rows="4" class="fld-input" placeholder="踩过的坑最值钱 —— 智能体会避免让你在同一个地方摔第二次。" />
              </div>
            </section>

            <!-- 5. 时间与资源 -->
            <section v-show="activeKey === 'time'" class="space-y-5">
              <div>
                <label class="fld-label">可投入时间</label>
                <PillSelect v-model="form.available_time" :options="AVAILABLE_TIME_OPTIONS" />
              </div>

              <div class="sm:max-w-[240px]">
                <label class="fld-label">每周可投入小时数</label>
                <input :value="form.weekly_hours" type="number" min="0" max="168" class="fld-input" placeholder="如 20" @input="setNum('weekly_hours', $event)" />
              </div>

              <div>
                <label class="fld-label">可动用的人脉与资源</label>
                <textarea v-model="form.support_network" rows="4" class="fld-input" placeholder="能帮上忙的人、渠道、场地、启动客户 —— 这些常常比钱更决定成败。" />
              </div>
            </section>

            <!-- 6. 目标与约束 -->
            <section v-show="activeKey === 'goal'" class="space-y-5">
              <div>
                <label class="fld-label">核心目标</label>
                <TagInput v-model="form.goals" :suggestions="GOAL_SUGGESTIONS" placeholder="你想达成什么" />
              </div>

              <div class="sm:max-w-[240px]">
                <label class="fld-label">时间视野（年）</label>
                <input :value="form.time_horizon" type="number" min="1" max="50" class="fld-input" placeholder="打算看多远" @input="setNum('time_horizon', $event)" />
              </div>

              <div>
                <label class="fld-label">硬性约束（不可妥协项）</label>
                <textarea v-model="form.constraints" rows="3" class="fld-input" placeholder="如：不能离开本地、不能动养老钱、不接受借贷创业。" />
              </div>

              <div>
                <label class="fld-label">决策动机</label>
                <textarea v-model="form.motivation" rows="3" class="fld-input" placeholder="为什么现在要做这个决定。" />
              </div>
            </section>

            <!-- 底部操作 -->
            <div class="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-white/6 pt-6">
              <div class="flex items-center gap-2">
                <button type="button" class="nav-step" :disabled="activeIndex === 0" @click="step(-1)">← 上一步</button>
                <button type="button" class="nav-step" :disabled="activeIndex === PROFILE_SECTIONS.length - 1" @click="step(1)">下一步 →</button>
              </div>
              <div class="flex items-center gap-4">
                <span v-if="savedTip" class="text-sm text-agent-env">✓ 已保存</span>
                <FancyButton size="sm" variant="ghost" @click="router.push('/library')">去推演</FancyButton>
                <FancyButton :disabled="saving || !dirty" @click="save">
                  {{ saving ? '保存中…' : '保存画像' }}
                </FancyButton>
              </div>
            </div>
          </GlassPanel>
        </div>
      </div>

      <div v-if="errorMsg" class="mt-6 rounded-btn border border-agent-risk/30 bg-agent-risk/10 px-4 py-3 text-sm text-agent-risk">
        {{ errorMsg }}
      </div>
    </main>
  </div>
</template>

<style scoped>
.fld-label {
  @apply mb-2 block text-xs font-medium text-ink-secondary;
}
.fld-hint {
  @apply mt-1.5 text-[11px] leading-snug text-ink-muted;
}
.fld-input {
  @apply w-full rounded-btn px-3 py-2.5 text-sm leading-relaxed outline-none;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(20, 26, 42, 0.7);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}
.fld-input:focus {
  border-color: rgba(79, 140, 255, 0.5);
  box-shadow: 0 0 0 3px rgba(79, 140, 255, 0.1);
}
.fld-input::placeholder {
  @apply text-ink-muted;
}
input.fld-input {
  @apply font-mono;
}
.fld-range {
  @apply h-1.5 w-full cursor-pointer appearance-none rounded-full;
  background: linear-gradient(90deg, #22d3ee, #4f8cff);
  opacity: 0.85;
}
.fld-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e6eaf2;
  border: 3px solid #4f8cff;
  box-shadow: 0 2px 10px rgba(79, 140, 255, 0.5);
  cursor: grab;
}
.fld-range::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #e6eaf2;
  border: 3px solid #4f8cff;
}
.nav-step {
  @apply rounded-btn px-3 py-1.5 text-xs text-ink-secondary transition-colors;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.nav-step:hover:not(:disabled) {
  @apply text-ink-primary;
  border-color: rgba(255, 255, 255, 0.2);
}
.nav-step:disabled {
  @apply cursor-not-allowed opacity-35;
}
</style>
