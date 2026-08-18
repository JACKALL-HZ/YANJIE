import type { SimEvent, SimulationRequest } from './types'

/** 从 localStorage 读取登录令牌，SSE 请求需手动注入（不走 client.ts 包装）。 */
function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('yanjie_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}


export interface SseCallbacks {
  onOpen?: () => void
  onEvent: (event: SimEvent) => void
  onError?: (err: Error) => void
  onDone?: () => void
}

/**
 * POST + SSE：fetch 流式读取 text/event-stream。
 * 后端每事件一行 `data: {json}\n\n`，按空行切帧。
 */
export async function streamSimulation(
  req: SimulationRequest,
  cb: SseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  let resp: Response
  try {
    resp = await fetch('/api/simulations/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(req),
      signal,
    })
  } catch (e) {
    cb.onError?.(e as Error)
    return
  }

  if (!resp.ok || !resp.body) {
    let msg = `HTTP ${resp.status}`
    try {
      const j = await resp.json()
      msg = j.message || msg
    } catch { /* ignore */ }
    cb.onError?.(new Error(msg))
    return
  }

  cb.onOpen?.()

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const flush = (chunk: string) => {
    const frames = chunk.split(/\r?\n\r?\n/)
    // 最后一帧可能不完整，留到下次
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      // 标准 SSE 帧含 id:/event:/data: 多行，逐行找 data:
      for (const line of frame.split(/\r?\n/)) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const jsonStr = trimmed.slice(5).trim()
        if (!jsonStr) continue
        try {
          cb.onEvent(JSON.parse(jsonStr) as SimEvent)
        } catch {
          // 单帧解析失败不阻断流
        }
      }
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      flush(buffer)
    }
    // 收尾：flush 残余帧
    if (buffer.trim()) {
      for (const line of buffer.split(/\r?\n/)) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const jsonStr = trimmed.slice(5).trim()
        if (!jsonStr) continue
        try {
          cb.onEvent(JSON.parse(jsonStr) as SimEvent)
        } catch { /* ignore */ }
      }
    }
    cb.onDone?.()
  } catch (e) {
    if ((e as Error).name !== 'AbortError') cb.onError?.(e as Error)
  }
}

/** SSE 流式追问：逐 token 回调 */
export async function streamAsk(
  sessionId: string,
  question: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const resp = await fetch(`/api/simulations/${sessionId}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ question }),
      signal,
    })
    if (!resp.ok || !resp.body) { onError(new Error(`HTTP ${resp.status}`)); return }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        for (const line of frame.split(/\r?\n/)) {
          const t = line.trim()
          if (!t.startsWith('data:')) continue
          try {
            const data = JSON.parse(t.slice(5).trim())
            if (data.token) onToken(data.token)
            if (data.done) { onDone(); return }
            if (data.message) onError(new Error(data.message))
          } catch { /* skip */ }
        }
      }
    }
    onDone()
  } catch (e) {
    if ((e as Error).name !== 'AbortError') onError(e as Error)
  }
}
