/**
 * 调用后端分析接口。
 * - analyzeRepo：一次性 POST /analyze
 * - analyzeRepoStream：SSE POST /analyze/stream，实时过程事件
 */

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000

/**
 * @param {{ repo: string, branch?: string | null, focus?: string }} body
 * @returns {object}
 */
function buildPayload(body) {
  const payload = {
    repo: body.repo.trim(),
    focus: body.focus || 'general',
  }
  if (body.branch && String(body.branch).trim()) {
    payload.branch = String(body.branch).trim()
  }
  return payload
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
    const res = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildPayload(body)),
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
 * SSE 流式分析：过程事件通过 onEvent 回调推送，最终 resolve 报告。
 *
 * @param {{ repo: string, branch?: string | null, focus?: string }} body
 * @param {{
 *   onEvent?: (type: string, data: object) => void,
 *   timeoutMs?: number,
 *   signal?: AbortSignal,
 * }} [options]
 * @returns {Promise<object>}
 */
export async function analyzeRepoStream(body, options = {}) {
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
    const res = await fetch('/analyze/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(buildPayload(body)),
      signal: controller.signal,
    })

    // 非 SSE 错误体（如校验失败、未配置 key）
    if (!res.ok) {
      let data = null
      try {
        data = await res.json()
      } catch {
        data = null
      }
      const detail = formatDetail(data?.detail) || res.statusText || `HTTP ${res.status}`
      const err = new Error(detail)
      err.status = res.status
      throw err
    }

    if (!res.body) {
      throw new Error('浏览器不支持流式响应（ReadableStream 不可用）')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let report = null
    let streamError = null

    /**
     * 解析并分发一块完整的 SSE 事件（以空行分隔）
     * @param {string} raw
     */
    function dispatchBlock(raw) {
      const lines = raw.split(/\r?\n/)
      let eventType = 'message'
      const dataLines = []
      for (const line of lines) {
        if (!line || line.startsWith(':')) continue
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).replace(/^ /, ''))
        }
      }
      if (!dataLines.length) return

      let data
      try {
        data = JSON.parse(dataLines.join('\n'))
      } catch {
        data = { raw: dataLines.join('\n') }
      }

      if (typeof options.onEvent === 'function') {
        options.onEvent(eventType, data)
      }

      if (eventType === 'done') {
        report = data
      } else if (eventType === 'error') {
        streamError = new Error(data?.detail || '分析失败')
        if (data?.status) streamError.status = data.status
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE 事件以空行分隔
      let sep
      while ((sep = buffer.search(/\r?\n\r?\n/)) !== -1) {
        const block = buffer.slice(0, sep)
        buffer = buffer.slice(sep).replace(/^\r?\n\r?\n/, '')
        if (block.trim()) dispatchBlock(block)
        if (streamError) {
          try {
            await reader.cancel()
          } catch {
            /* ignore */
          }
          throw streamError
        }
      }
    }

    // 流结束时的残余
    if (buffer.trim()) {
      dispatchBlock(buffer)
      if (streamError) throw streamError
    }

    if (!report) {
      throw new Error('分析流已结束，但未收到完整报告（done 事件）')
    }
    return report
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
