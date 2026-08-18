import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { ScenarioDetail, ScenarioSummary } from '@/api/types'

export const useScenariosStore = defineStore('scenarios', () => {
  const list = ref<ScenarioSummary[]>([])
  const current = ref<ScenarioDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let detailRequestId = 0

  async function fetchList() {
    loading.value = true
    error.value = null
    try {
      list.value = await api.get<ScenarioSummary[]>('/scenarios')
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(id: string) {
    const requestId = ++detailRequestId
    loading.value = true
    error.value = null
    current.value = null
    try {
      const detail = await api.get<ScenarioDetail>(`/scenarios/${id}`)
      if (requestId === detailRequestId) current.value = detail
    } catch (e) {
      if (requestId === detailRequestId) {
        error.value = (e as Error).message
        current.value = null
      }
    } finally {
      if (requestId === detailRequestId) loading.value = false
    }
  }

  function clearCurrent() {
    detailRequestId += 1
    current.value = null
    error.value = null
  }

  return { list, current, loading, error, fetchList, fetchDetail, clearCurrent }
})
