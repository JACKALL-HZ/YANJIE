import type { ApiError, AskResponse, BreakdownResult } from './types'

const BASE = '/api'

export function actorHeaders(): Record<string, string> {
  return {}
}

function normalizeHeaders(input?: HeadersInit): Record<string, string> {
  if (!input) return {}
  if (input instanceof Headers) {
    const result: Record<string, string> = {}
    input.forEach((value, key) => { result[key] = value })
    return result
  }
  if (Array.isArray(input)) {
    return input.reduce<Record<string, string>>((result, [key, value]) => {
      result[key] = value
      return result
    }, {})
  }
  return { ...input }
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('yanjie_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function requestHeaders(extra?: HeadersInit): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...normalizeHeaders(extra),
    ...authHeaders(),
  }
}

export class ApiRequestError extends Error {
  code: string
  status: number
  requestId?: string

  constructor(status: number, body: ApiError) {
    super(body.message || `HTTP ${status}`)
    this.name = 'ApiRequestError'
    this.code = body.code || 'UNKNOWN'
    this.status = status
    this.requestId = body.request_id
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = requestHeaders(init?.headers)
  const token = localStorage.getItem('yanjie_token')

  const resp = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!resp.ok) {
    let body: ApiError
    try {
      body = (await resp.json()) as ApiError
    } catch {
      body = { code: 'HTTP_ERROR', message: `HTTP ${resp.status}` }
    }
    if (resp.status === 401) {
      // /auth/me 失败仅代表 token 过期，静默放行不要跳转。
      // 其他端点携带 token 被拒 → 跳转登录。
      const isMe = path === '/auth/me' || path.startsWith('/auth/me?')
      if (token && !isMe) {
        const p = window.location.pathname
        if (p !== '/login' && p !== '/register') {
          localStorage.removeItem('yanjie_token')
          localStorage.removeItem('yanjie_user')
          window.location.href = `/login?redirect=${encodeURIComponent(p)}`
        }
      }
    }
    throw new ApiRequestError(resp.status, body)
  }
  return (await resp.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),

  async downloadReport(sessionId: string): Promise<string> {
    const headers: Record<string, string> = {}
    const token = localStorage.getItem('yanjie_token')
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await fetch(`${BASE}/simulations/${sessionId}/report`, { headers })
    if (!response.ok) {
      throw new Error('报告下载失败')
    }
    return response.text()
  },

  /** 自然语言 → 结构化决策变量 */
  breakdown(query: string, scenarioId?: string, latestQuery?: string) {
    return request<BreakdownResult>('/assistant/breakdown', {
      method: 'POST',
      body: JSON.stringify({
        query,
        scenario_id: scenarioId ?? null,
        latest_query: latestQuery ?? null,
      }),
      headers: { 'Content-Type': 'application/json' },
    })
  },

  /** 基于模拟上下文追问 AI */
  ask(sessionId: string, question: string, year?: number) {
    const qs = year != null ? `?year=${year}` : ''
    return request<AskResponse>(`/simulations/${sessionId}/ask${qs}`, {
      method: 'POST',
      body: JSON.stringify({ question }),
      headers: { 'Content-Type': 'application/json' },
    })
  },
}
