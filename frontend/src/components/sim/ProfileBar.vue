<script setup lang="ts">
/**
 * ProfileBar — 推演页顶部的画像状态条。
 *
 * 三态软引导（任何一态都不阻断推演）：
 *  1. 未建画像 → 提示 + 一键去创建
 *  2. 已建但偏薄 → 提示补全，显示完成度
 *  3. 已建且充分 → 收起为一行指标，并把「本次投入 vs 你的资产」当场算给用户看，
 *     与后端 profile_summary 里喂给 Agent 的投入压力口径一致。
 */
import { computed, onMounted, ref } from 'vue'
import { RISK_LABEL, money, profileApi, type Profile } from '@/api/profile'
import AnimatedNumber from '@/components/ui/AnimatedNumber.vue'

const props = withDefaults(defineProps<{ budget?: number }>(), { budget: 0 })

const loading = ref(true)
const exists = ref(false)
const profile = ref<Profile | null>(null)

const completeness = computed(() =>
  Math.round(((profile.value?.derived?.completeness ?? 0) as number) * 100),
)
const assets = computed(() => profile.value?.assets ?? null)
const maxLoss = computed(() => profile.value?.derived?.max_affordable_loss ?? null)

/** 本次投入占资产比例 —— Agent 感知到的「压上几成身家」 */
const pressure = computed(() => {
  if (!props.budget || !assets.value) return null
  const ratio = props.budget / assets.value
  const level = ratio >= 1 ? 'over' : ratio >= 0.5 ? 'heavy' : ratio >= 0.2 ? 'medium' : 'light'
  return { ratio, pct: Math.round(ratio * 100), level }
})

const PRESSURE_TEXT: Record<string, string> = {
  light: '轻仓试水',
  medium: '中等仓位',
  heavy: '重仓',
  over: '超出可支配资产',
}
const PRESSURE_CLASS: Record<string, string> = {
  light: 'text-agent-env',
  medium: 'text-cyan-glow',
  heavy: 'text-amber-300',
  over: 'text-agent-risk',
}

onMounted(async () => {
  try {
    const res = await profileApi.me()
    exists.value = res.exists
    profile.value = res.profile
  } catch {
    // 画像探针失败不影响推演，静默降级
    exists.value = false
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="!loading" class="mb-5">
    <!-- 未建画像 -->
    <div
      v-if="!exists"
      class="glass flex flex-wrap items-center justify-between gap-3 rounded-card border-l-2 border-l-brand/60 px-4 py-3"
    >
      <div class="flex items-start gap-3">
        <span class="mt-0.5 text-base leading-none text-brand">◎</span>
        <div>
          <div class="text-sm font-medium text-ink-primary">还没建立个人画像</div>
          <div class="mt-0.5 text-xs leading-snug text-ink-muted">
            现在推演，智能体只能按通用假设算。填一份画像，它会知道你有多少家底、能亏多少、每周能投多少时间。
          </div>
        </div>
      </div>
      <RouterLink
        to="/profile"
        class="shrink-0 rounded-btn border border-brand/40 bg-brand/10 px-3.5 py-1.5 text-xs text-brand transition-colors hover:bg-brand/20"
      >
        去建立画像 →
      </RouterLink>
    </div>

    <!-- 已建画像 -->
    <div
      v-else
      class="glass flex flex-wrap items-center gap-x-5 gap-y-2 rounded-card px-4 py-2.5"
      :class="completeness < 40 ? 'border-l-2 border-l-amber-400/60' : 'border-l-2 border-l-agent-env/50'"
    >
      <div class="flex items-center gap-2">
        <span class="h-1.5 w-1.5 rounded-full" :class="completeness < 40 ? 'bg-amber-400' : 'bg-agent-env'" />
        <span class="text-xs text-ink-secondary">画像已载入</span>
        <span class="font-mono text-xs text-ink-muted">
          <AnimatedNumber :value="completeness" suffix="%" />
        </span>
      </div>

      <div v-if="assets != null" class="flex items-center gap-1.5 text-xs">
        <span class="text-ink-muted">可支配资产</span>
        <span class="font-mono text-ink-primary">
          <AnimatedNumber :value="assets" :format="money" />
        </span>
      </div>

      <div v-if="profile?.risk_appetite" class="flex items-center gap-1.5 text-xs">
        <span class="text-ink-muted">风险偏好</span>
        <span class="font-mono text-ink-primary">{{ RISK_LABEL[profile.risk_appetite] || profile.risk_appetite }}</span>
      </div>

      <div v-if="maxLoss != null" class="flex items-center gap-1.5 text-xs">
        <span class="text-ink-muted">可承受亏损</span>
        <span class="font-mono text-ink-primary">
          <AnimatedNumber :value="maxLoss" :format="money" />
        </span>
      </div>

      <!-- 投入压力：与后端喂给 Agent 的口径一致 -->
      <div v-if="pressure" class="flex items-center gap-1.5 text-xs">
        <span class="text-ink-muted">本次投入</span>
        <span class="font-mono" :class="PRESSURE_CLASS[pressure.level]">
          占资产 <AnimatedNumber :value="pressure.pct" suffix="%" /> · {{ PRESSURE_TEXT[pressure.level] }}
        </span>
      </div>

      <RouterLink
        to="/profile"
        class="ml-auto shrink-0 text-xs text-ink-muted transition-colors hover:text-brand"
      >
        {{ completeness < 40 ? '补全画像 →' : '编辑' }}
      </RouterLink>
    </div>
  </div>
</template>
