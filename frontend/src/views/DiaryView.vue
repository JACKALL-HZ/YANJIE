<script setup lang="ts">
import { onMounted, ref } from 'vue'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import SkeletonCard from '@/components/ui/SkeletonCard.vue'
import { api } from '@/api/client'

interface DiaryEntry {
  session_id: string
  scenario_id?: string
  tags?: string[]
  notes?: string | null
  archived?: boolean
  calibration?: { actual_result?: string; actual_metrics?: Record<string, unknown> } | null
  [k: string]: unknown
}

const entries = ref<DiaryEntry[]>([])
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

async function fetchDiary() {
  loading.value = true
  errorMsg.value = null
  try {
    entries.value = await api.get<DiaryEntry[]>('/diary')
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
  calResult.value = e.calibration?.actual_result ?? ''
}

async function saveCalibration(sessionId: string) {
  if (calSaving.value || !calResult.value.trim()) return
  calSaving.value = true
  errorMsg.value = null
  try {
    await api.put(`/diary/${sessionId}/calibration`, {
      actual_result: calResult.value.trim(),
    })
    calibratingId.value = null
    await fetchDiary()
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    calSaving.value = false
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

      <div v-if="loading" class="mt-10 space-y-4">
        <SkeletonCard v-for="n in 3" :key="n" :lines="3" />
      </div>

      <div v-else-if="errorMsg" class="mt-10 rounded-btn border border-agent-risk/30 bg-agent-risk/10 px-4 py-3 text-sm text-agent-risk">
        {{ errorMsg }}
      </div>

      <GlassPanel v-else-if="entries.length === 0" class="mt-10 py-16 text-center">
        <p class="text-sm text-ink-muted">还没有日记。推演完成后，记录会出现在这里。</p>
      </GlassPanel>

      <div v-else class="mt-10 space-y-5">
        <GlassPanel
          v-for="e in entries"
          :key="e.session_id"
          :class="e.archived ? 'opacity-60' : ''"
        >
          <!-- 头部 -->
          <div class="flex flex-wrap items-center gap-3">
            <span class="font-medium text-ink-primary">{{ e.scenario_id || '未关联场景' }}</span>
            <span class="font-mono text-[10px] text-ink-muted">{{ e.session_id.slice(0, 8) }}…</span>
            <span v-if="e.archived" class="rounded-chip bg-white/5 px-2 py-0.5 text-[10px] text-ink-muted">已归档</span>
            <div class="ml-auto flex gap-2">
              <button
                class="rounded-btn px-3 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-white/5 hover:text-ink-primary"
                @click="startCalibration(e)"
              >
                校准
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
                class="rounded-chip border border-cyan-glow/20 bg-cyan-glow/8 px-2.5 py-0.5 text-[10px] text-cyan-glow"
              >
                {{ t }}
              </span>
            </div>
            <p class="text-sm leading-relaxed text-ink-secondary">
              {{ e.notes || '（还没有笔记）' }}
            </p>
            <div v-if="e.calibration?.actual_result" class="mt-3 rounded-btn border border-agent-env/20 bg-agent-env/5 px-3 py-2 text-xs text-agent-env">
              现实校准：{{ e.calibration.actual_result }}
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
            <label class="mb-1.5 block text-xs text-agent-env">现实结果（推演 vs 现实，差在哪）</label>
            <textarea
              v-model="calResult"
              rows="3"
              class="w-full rounded-btn border border-white/10 bg-surface-1 px-3 py-2 text-sm outline-none focus:border-agent-env/50"
              placeholder="如：实际第2年现金流断裂，比推演早了一年"
            />
            <div class="mt-3 flex gap-3">
              <FancyButton size="sm" :disabled="calSaving || !calResult.trim()" @click="saveCalibration(e.session_id)">
                {{ calSaving ? '提交中…' : '提交校准' }}
              </FancyButton>
              <FancyButton size="sm" variant="ghost" @click="calibratingId = null">取消</FancyButton>
            </div>
          </div>
        </GlassPanel>
      </div>
    </main>
  </div>
</template>
