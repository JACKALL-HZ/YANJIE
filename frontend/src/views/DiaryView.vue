<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import SkeletonCard from '@/components/ui/SkeletonCard.vue'
import { api } from '@/api/client'

interface DiaryEntry {
  session_id: string
  scenario_id?: string
  scenario_title?: string
  result?: string | null
  result_label?: string
  score?: number | null
  tags?: string[]
  notes?: string | null
  archived?: boolean
  actual_result?: string | null
  actual_result_label?: string
  calibration_score?: number | null
  calibration_grade?: string
  created_at?: string
  [k: string]: unknown
}

interface DiaryStats {
  total_entries: number
  calibrated_count: number
  uncalibrated_count: number
  avg_calibration_score: number | null
  result_distribution: Record<string, number>
  tag_distribution: Record<string, number>
  grade_distribution: Record<string, number>
}

const entries = ref<DiaryEntry[]>([])
const stats = ref<DiaryStats | null>(null)
const loading = ref(false)
const errorMsg = ref<string | null>(null)
const editingId = ref<string | null>(null)
const saving = ref(false)

const editTags = ref('')
const editNotes = ref('')
const editArchived = ref(false)

const calibratingId = ref<string | null>(null)
const calResult = ref('')
const calSaving = ref(false)
const calSummary = ref<string | null>(null)

// 标签筛选
const activeTag = ref<string | null>(null)

// 归档筛选
const showArchived = ref<boolean | null>(null)

// 校准结果码选项
const RESULT_OPTIONS = [
  { value: 'goal_reached', label: '达成目标' },
  { value: 'steady', label: '稳定运营' },
  { value: 'bankrupt', label: '破产' },
  { value: 'timeout', label: '超时未完成' },
]

// 校准等级 → 颜色
const GRADE_COLORS: Record<string, string> = {
  '高度准确': 'text-emerald-400 border-emerald-400/30 bg-emerald-400/8',
  '部分偏差': 'text-amber-400 border-amber-400/30 bg-amber-400/8',
  '显著偏差': 'text-rose-400 border-rose-400/30 bg-rose-400/8',
  '未校准': 'text-ink-muted border-white/10 bg-white/5',
}

const filteredEntries = computed(() => {
  let list = entries.value
  if (activeTag.value) {
    list = list.filter(e => (e.tags ?? []).includes(activeTag.value!))
  }
  if (showArchived.value !== null) {
    list = list.filter(e => !!e.archived === showArchived.value)
  }
  return list
})

const allTags = computed(() => {
  if (!stats.value) return []
  return Object.entries(stats.value.tag_distribution)
    .sort((a, b) => b[1] - a[1])
    .map(([tag, count]) => ({ tag, count }))
})

async function fetchDiary() {
  loading.value = true
  errorMsg.value = null
  try {
    const [listData, statsData] = await Promise.all([
      api.get<DiaryEntry[]>('/diary'),
      api.get<DiaryStats>('/diary/stats'),
    ])
    entries.value = listData
    stats.value = statsData
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function startEdit(e: DiaryEntry) {
  editingId.value = e.session_id
  editTags.value = (e.tags ?? []).join(', ')
  editNotes.value = e.notes ?? ''
  editArchived.value = !!e.archived
}

function cancelEdit() {
  editingId.value = null
}

async function saveEntry(sessionId: string) {
  if (saving.value) return
  saving.value = true
  errorMsg.value = null
  try {
    const tags = editTags.value
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
    await api.put(`/diary/${sessionId}`, {
      tags,
      notes: editNotes.value || null,
      archived: editArchived.value,
    })
    editingId.value = null
    await fetchDiary()
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

function startCalibration(e: DiaryEntry) {
  calibratingId.value = e.session_id
  calResult.value = e.actual_result ?? ''
  calSummary.value = null
}

async function saveCalibration(sessionId: string) {
  if (calSaving.value || !calResult.value.trim()) return
  calSaving.value = true
  errorMsg.value = null
  try {
    const resp = await api.put<{
      calibration_grade: string
      calibration_score: number
      summary: string
      simulated_result_label: string
      actual_result_label: string
    }>(`/diary/${sessionId}/calibration`, {
      actual_result: calResult.value.trim(),
    })
    // 展示校准总结而非静默关闭
    calSummary.value = resp.summary
    // 刷新列表和统计
    await fetchDiary()
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    calSaving.value = false
  }
}

function closeCalibration() {
  calibratingId.value = null
  calSummary.value = null
}

function toggleTag(tag: string) {
  activeTag.value = activeTag.value === tag ? null : tag
}

function fmtDate(iso?: string): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return iso
  }
}

onMounted(fetchDiary)
</script>

<template>
  <div class="min-h-[100dvh]">
    <NavBar />

    <main class="mx-auto max-w-[1000px] px-5 pb-24 pt-24 md:px-8 md:pt-28">
      <p class="eyebrow mb-2">决策日记</p>
      <h1 class="font-display text-3xl font-bold tracking-tight md:text-4xl">决策日记</h1>
      <p class="mt-3 max-w-[560px] text-sm text-ink-secondary">
        推演是预演，现实是答卷。给每场推演写下注脚，再用真实结果校准它。
      </p>

      <!-- ── 统计概览面板 ── -->
      <div v-if="stats" class="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        <GlassPanel class="p-4">
          <p class="text-[11px] text-ink-muted">推演记录</p>
          <p class="mt-1 font-display text-2xl font-bold text-ink-primary">{{ stats.total_entries }}</p>
        </GlassPanel>
        <GlassPanel class="p-4">
          <p class="text-[11px] text-ink-muted">已校准</p>
          <p class="mt-1 font-display text-2xl font-bold text-cyan-glow">{{ stats.calibrated_count }}</p>
          <p class="mt-0.5 text-[10px] text-ink-muted">待校准 {{ stats.uncalibrated_count }}</p>
        </GlassPanel>
        <GlassPanel class="p-4">
          <p class="text-[11px] text-ink-muted">平均校准分</p>
          <p class="mt-1 font-display text-2xl font-bold" :class="stats.avg_calibration_score === null ? 'text-ink-muted' : stats.avg_calibration_score >= 0.8 ? 'text-emerald-400' : stats.avg_calibration_score >= 0.5 ? 'text-amber-400' : 'text-rose-400'">
            {{ stats.avg_calibration_score !== null ? stats.avg_calibration_score.toFixed(2) : '—' }}
          </p>
        </GlassPanel>
        <GlassPanel class="p-4">
          <p class="text-[11px] text-ink-muted">校准等级分布</p>
          <div class="mt-1.5 space-y-0.5">
            <div v-for="grade in ['高度准确', '部分偏差', '显著偏差', '未校准']" :key="grade" class="flex items-center justify-between text-[11px]">
              <span :class="grade === '高度准确' ? 'text-emerald-400' : grade === '部分偏差' ? 'text-amber-400' : grade === '显著偏差' ? 'text-rose-400' : 'text-ink-muted'">{{ grade }}</span>
              <span class="font-mono text-ink-secondary">{{ stats.grade_distribution[grade] || 0 }}</span>
            </div>
          </div>
        </GlassPanel>
      </div>

      <!-- ── 标签筛选栏 ── -->
      <div v-if="allTags.length > 0" class="mt-6 flex flex-wrap items-center gap-2">
        <span class="text-[11px] text-ink-muted">标签筛选：</span>
        <button
          class="rounded-chip px-2.5 py-1 text-[11px] transition-colors"
          :class="activeTag === null ? 'bg-brand/20 text-brand' : 'bg-white/5 text-ink-secondary hover:bg-white/10'"
          @click="activeTag = null"
        >
          全部
        </button>
        <button
          v-for="{ tag, count } in allTags.slice(0, 12)"
          :key="tag"
          class="rounded-chip px-2.5 py-1 text-[11px] transition-colors"
          :class="activeTag === tag ? 'bg-cyan-glow/20 text-cyan-glow' : 'bg-white/5 text-ink-secondary hover:bg-white/10'"
          @click="toggleTag(tag)"
        >
          {{ tag }} <span class="ml-0.5 font-mono text-ink-muted">{{ count }}</span>
        </button>
        <div class="ml-auto flex gap-2">
          <button
            class="rounded-chip px-2.5 py-1 text-[11px] transition-colors"
            :class="showArchived === null ? 'bg-white/5 text-ink-secondary' : showArchived ? 'bg-white/10 text-ink-primary' : 'bg-brand/20 text-brand'"
            @click="showArchived = showArchived === null ? false : showArchived === false ? true : null"
          >
            {{ showArchived === null ? '全部状态' : showArchived ? '仅归档' : '仅活跃' }}
          </button>
        </div>
      </div>

      <!-- ── 加载态 ── -->
      <div v-if="loading" class="mt-8 space-y-4">
        <SkeletonCard v-for="n in 3" :key="n" :lines="3" />
      </div>

      <!-- ── 错误态 ── -->
      <div v-else-if="errorMsg" class="mt-8 rounded-btn border border-agent-risk/30 bg-agent-risk/10 px-4 py-3 text-sm text-agent-risk">
        {{ errorMsg }}
      </div>

      <!-- ── 空态 ── -->
      <GlassPanel v-else-if="entries.length === 0" class="mt-8 py-16 text-center">
        <p class="text-sm text-ink-muted">还没有日记。推演完成后，记录会出现在这里。</p>
      </GlassPanel>

      <!-- ── 筛选无结果 ── -->
      <GlassPanel v-else-if="filteredEntries.length === 0" class="mt-8 py-12 text-center">
        <p class="text-sm text-ink-muted">当前筛选条件下没有记录。</p>
      </GlassPanel>

      <!-- ── 日记列表 ── -->
      <div v-else class="mt-8 space-y-5">
        <GlassPanel
          v-for="e in filteredEntries"
          :key="e.session_id"
          :class="e.archived ? 'opacity-60' : ''"
        >
          <!-- 头部 -->
          <div class="flex flex-wrap items-center gap-3">
            <span class="font-medium text-ink-primary">{{ e.scenario_title || e.scenario_id || '未关联场景' }}</span>
            <span v-if="e.result_label" class="rounded-chip bg-white/5 px-2 py-0.5 text-[10px] text-ink-secondary">
              推演：{{ e.result_label }}
            </span>
            <span v-if="e.score !== null && e.score !== undefined" class="font-mono text-[10px] text-ink-muted">
              评分 {{ e.score }}
            </span>
            <span class="font-mono text-[10px] text-ink-muted">{{ fmtDate(e.created_at) }}</span>
            <span v-if="e.archived" class="rounded-chip bg-white/5 px-2 py-0.5 text-[10px] text-ink-muted">已归档</span>
            <div class="ml-auto flex gap-2">
              <button
                class="rounded-btn px-3 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-white/5 hover:text-ink-primary"
                @click="startCalibration(e)"
              >
                {{ e.actual_result ? '查看校准' : '校准' }}
              </button>
              <button
                class="rounded-btn px-3 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-white/5 hover:text-ink-primary"
                @click="startEdit(e)"
              >
                编辑
              </button>
            </div>
          </div>

          <!-- 标签 + 笔记（展示态） -->
          <div v-if="editingId !== e.session_id" class="mt-3">
            <div v-if="(e.tags ?? []).length" class="mb-2 flex flex-wrap gap-1.5">
              <span
                v-for="t in e.tags"
                :key="t"
                class="cursor-pointer rounded-chip border border-cyan-glow/20 bg-cyan-glow/8 px-2.5 py-0.5 text-[10px] text-cyan-glow transition-colors hover:bg-cyan-glow/15"
                @click="toggleTag(t)"
              >
                {{ t }}
              </span>
            </div>
            <p class="text-sm leading-relaxed text-ink-secondary">
              {{ e.notes || '（还没有笔记）' }}
            </p>

            <!-- 校准结果展示 -->
            <div v-if="e.actual_result" class="mt-3 rounded-btn border px-3 py-2.5 text-xs" :class="GRADE_COLORS[e.calibration_grade || '未校准']">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <span class="font-medium">现实校准</span>
                <span class="text-ink-secondary">{{ e.result_label || e.result || '—' }}</span>
                <span class="text-ink-muted">→</span>
                <span class="text-ink-primary">{{ e.actual_result_label || e.actual_result }}</span>
                <span class="ml-auto rounded-chip px-2 py-0.5 text-[10px] font-medium" :class="GRADE_COLORS[e.calibration_grade || '未校准']">
                  {{ e.calibration_grade }}
                </span>
              </div>
              <div v-if="e.calibration_score !== null && e.calibration_score !== undefined" class="mt-1.5 text-[10px] text-ink-muted">
                校准分 {{ e.calibration_score.toFixed(2) }}
              </div>
            </div>
          </div>

          <!-- 编辑态 -->
          <div v-else class="mt-4 space-y-4">
            <div>
              <label class="mb-1.5 block text-xs text-ink-muted">标签（逗号分隔）</label>
              <input
                v-model="editTags"
                type="text"
                class="w-full rounded-btn border border-white/10 bg-surface-1 px-3 py-2 text-sm outline-none focus:border-brand/50"
                placeholder="如：第一次创业, 奶茶, 杭州"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-xs text-ink-muted">笔记</label>
              <textarea
                v-model="editNotes"
                rows="4"
                class="w-full rounded-btn border border-white/10 bg-surface-1 px-3 py-2 text-sm leading-relaxed outline-none focus:border-brand/50"
              />
            </div>
            <label class="flex cursor-pointer items-center gap-2 text-sm text-ink-secondary">
              <input v-model="editArchived" type="checkbox" class="accent-brand" />
              归档此记录
            </label>
            <div class="flex gap-3">
              <FancyButton size="sm" :disabled="saving" @click="saveEntry(e.session_id)">
                {{ saving ? '保存中…' : '保存' }}
              </FancyButton>
              <FancyButton size="sm" variant="ghost" @click="cancelEdit">取消</FancyButton>
            </div>
          </div>

          <!-- 校准态 -->
          <div v-if="calibratingId === e.session_id" class="mt-4 rounded-btn border border-agent-env/25 bg-agent-env/5 p-4">
            <!-- 已有校准 → 展示总结 -->
            <div v-if="calSummary && !calSaving" class="space-y-3">
              <div class="flex items-center gap-2">
                <span class="text-xs font-medium text-agent-env">校准完成</span>
              </div>
              <p class="text-sm leading-relaxed text-ink-primary">{{ calSummary }}</p>
              <div class="flex gap-3">
                <FancyButton size="sm" variant="ghost" @click="closeCalibration">关闭</FancyButton>
                <FancyButton size="sm" variant="ghost" @click="calSummary = null">重新校准</FancyButton>
              </div>
            </div>

            <!-- 输入态 -->
            <div v-else>
              <label class="mb-2 block text-xs text-agent-env">现实结果（推演 vs 现实，差在哪）</label>
              <div class="mb-3 flex flex-wrap gap-2">
                <button
                  v-for="opt in RESULT_OPTIONS"
                  :key="opt.value"
                  class="rounded-btn px-3 py-1.5 text-xs transition-colors"
                  :class="calResult === opt.value ? 'bg-agent-env/20 text-agent-env' : 'bg-white/5 text-ink-secondary hover:bg-white/10'"
                  @click="calResult = opt.value"
                >
                  {{ opt.label }}
                </button>
              </div>
              <div class="flex gap-3">
                <FancyButton size="sm" :disabled="calSaving || !calResult.trim()" @click="saveCalibration(e.session_id)">
                  {{ calSaving ? '提交中…' : '提交校准' }}
                </FancyButton>
                <FancyButton size="sm" variant="ghost" @click="closeCalibration">取消</FancyButton>
              </div>
            </div>
          </div>
        </GlassPanel>
      </div>
    </main>
  </div>
</template>
