/**
 * 修复提案 API：propose（SSE）/ apply / open-pr
 */

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000

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
 * @param {{ repo: string, branch?: string | null, bug: object }} body
 * @param {{
 *   onEvent?: (type: string, data: object) => void,
 *   timeoutMs?: number,
 *   signal?: AbortSignal,
 * }} [options]
 * @returns {Promise<object>} FixProposal
 */
export async function proposeFixStream(body, options = {}) {
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

  const payload = {
    repo: String(body.repo || '').trim(),
    bug: body.bug,
  }
  if (body.branch && String(body.branch).trim()) {
    payload.branch = String(body.branch).trim()
  }

  try {
    const res = await fetch('/fix/propose/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

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
    let proposal = null
    let streamError = null

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
        proposal = data
      } else if (eventType === 'error') {
        streamError = new Error(data?.detail || '生成修复失败')
        if (data?.status) streamError.status = data.status
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
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

    if (buffer.trim()) {
      dispatchBlock(buffer)
      if (streamError) throw streamError
    }

    if (!proposal) {
      throw new Error('修复流已结束，但未收到提案（done 事件）')
    }
    return proposal
  } catch (err) {
    if (err?.name === 'AbortError') {
      const timeoutErr = new Error(
        `请求已取消或超时（>${Math.round(timeoutMs / 60000)} 分钟）。`,
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
 * @param {{ fix_id: string, paths?: string[], force?: boolean }} body
 */
export async function applyFix(body) {
  const res = await fetch('/fix/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
}

/**
 * @param {{ fix_id: string, title?: string, body?: string, branch_name?: string }} body
 */
export async function openFixPr(body) {
  const res = await fetch('/fix/open-pr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
}
