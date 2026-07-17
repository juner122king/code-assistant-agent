/**
 * 调用后端 POST /analyze。
 * 分析可能经历多步 Agent 工具调用，默认超时 10 分钟。
 */

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000

/**
 * @param {{ repo: string, branch?: string | null, focus?: string }} body
 * @param {{ timeoutMs?: number, signal?: AbortSignal }} [options]
 * @returns {Promise<object>}
 */
export async function analyzeRepo(body, options = {}) {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  const onOuterAbort = () => controller.abort()
  if (options.signal) {
    if (options.signal.aborted) {
      clearTimeout(timer)
      throw new DOMException('Aborted', 'AbortError')
    }
    options.signal.addEventListener('abort', onOuterAbort, { once: true })
  }

  try {
    const payload = {
      repo: body.repo.trim(),
      focus: body.focus || 'general',
    }
    if (body.branch && String(body.branch).trim()) {
      payload.branch = String(body.branch).trim()
    }

    const res = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    let data = null
    try {
      data = await res.json()
    } catch {
      data = null
    }

    if (!res.ok) {
      const detail = formatDetail(data?.detail) || res.statusText || `HTTP ${res.status}`
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    return data
  } catch (err) {
    if (err?.name === 'AbortError') {
      const timeoutErr = new Error(
        `请求已取消或超时（>${Math.round(timeoutMs / 60000)} 分钟）。Agent 多步分析可能较慢，请稍后重试。`,
      )
      timeoutErr.name = 'AbortError'
      throw timeoutErr
    }
    if (err instanceof TypeError) {
      throw new Error('无法连接后端，请确认 uvicorn 已在 8000 端口运行。')
    }
    throw err
  } finally {
    clearTimeout(timer)
    if (options.signal) {
      options.signal.removeEventListener('abort', onOuterAbort)
    }
  }
}

/**
 * @param {unknown} detail
 * @returns {string}
 */
function formatDetail(detail) {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : ''
          return loc ? `${loc}: ${item.msg || JSON.stringify(item)}` : item.msg || JSON.stringify(item)
        }
        return String(item)
      })
      .join('; ')
  }
  if (typeof detail === 'object') {
    return JSON.stringify(detail)
  }
  return String(detail)
}

/**
 * @returns {Promise<boolean>}
 */
export async function checkHealth() {
  try {
    const res = await fetch('/health')
    if (!res.ok) return false
    const data = await res.json()
    return data?.status === 'ok'
  } catch {
    return false
  }
}
