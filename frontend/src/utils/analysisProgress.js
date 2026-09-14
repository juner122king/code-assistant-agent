/** 把 SSE / 历史事件还原成过程时间线。 */

export function createEmptyProgress() {
  return {
    items: [],
    repo: '',
    source: '',
    model: '',
    step: 0,
    maxSteps: 0,
    phase: '',
    phaseMessage: '准备分析…',
    startedAt: 0,
    finishedAt: 0,
    runId: '',
  }
}

export function createProgressState() {
  return {
    progress: createEmptyProgress(),
    itemSeq: 0,
  }
}

function pushItem(state, partial) {
  state.itemSeq += 1
  state.progress.items.push({
    id: state.itemSeq,
    kind: 'status',
    title: '',
    summary: '',
    status: '',
    step: 0,
    preview: '',
    at: Date.now(),
    ...partial,
  })
}

function upsertTool(state, data) {
  const name = data?.name || 'tool'
  const summary = data?.input_summary || ''
  const status = data?.status || 'running'
  const step = data?.step || state.progress.step
  const title = status === 'running' ? `调用工具 ${name}` : `工具 ${name}`

  if (status === 'running') {
    pushItem(state, {
      kind: 'tool',
      title,
      summary,
      status: 'running',
      step,
    })
    return
  }

  const items = state.progress.items
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const it = items[i]
    if (
      it.kind === 'tool' &&
      it.status === 'running' &&
      it.step === step &&
      (it.title.includes(name) || it.summary === summary)
    ) {
      it.status = status
      it.title = status === 'ok' ? `工具 ${name} 完成` : `工具 ${name} 失败`
      it.summary = summary
      it.preview = data?.preview || ''
      return
    }
  }
  pushItem(state, {
    kind: 'tool',
    title: status === 'ok' ? `工具 ${name} 完成` : `工具 ${name} 失败`,
    summary,
    status,
    step,
    preview: data?.preview || '',
  })
}

/**
 * @param {{ progress: object, itemSeq: number }} state
 * @param {string} type
 * @param {object} data
 */
export function applyAnalysisEvent(state, type, data) {
  const progress = state.progress
  if (data?.run_id) progress.runId = data.run_id

  if (type === 'start') {
    progress.repo = data.repo || progress.repo
    progress.source = data.source || progress.source
    progress.model = data.model || progress.model
    progress.maxSteps = data.max_steps || progress.maxSteps
    progress.step = 0
    progress.phase = 'start'
    progress.phaseMessage = 'Agent 已启动，开始多步分析…'
    pushItem(state, {
      kind: 'start',
      title: '已解析仓库',
      summary: `${data.source || ''}: ${data.repo || ''}`,
      status: 'ok',
      at: data.at,
    })
    return
  }

  if (type === 'step') {
    progress.step = data.step || progress.step
    progress.maxSteps = data.max_steps || progress.maxSteps
    progress.phase = data.phase || ''
    progress.phaseMessage = data.message || progress.phaseMessage
    const phaseLabel =
      data.phase === 'llm'
        ? '调用模型'
        : data.phase === 'tools'
          ? '执行工具'
          : data.phase === 'finished'
            ? '整理报告'
            : '步骤更新'
    pushItem(state, {
      kind: 'step',
      title: `步骤 ${data.step || '—'}: ${phaseLabel}`,
      summary: data.message || '',
      status: data.phase === 'finished' ? 'ok' : '',
      step: data.step || 0,
      at: data.at,
    })
    return
  }

  if (type === 'tool') {
    if (data?.status === 'running') {
      progress.phase = 'tools'
      progress.phaseMessage = `正在执行 ${data.name || '工具'}…`
    }
    upsertTool(state, data)
    return
  }

  if (type === 'status') {
    progress.phaseMessage = data?.message || progress.phaseMessage
    pushItem(state, {
      kind: 'status',
      title: data?.message || '状态更新',
      status: '',
      at: data?.at,
    })
    return
  }

  if (type === 'error') {
    progress.phase = 'error'
    progress.phaseMessage = data?.detail || '分析失败'
    pushItem(state, {
      kind: 'status',
      title: '分析中断',
      summary: data?.detail || '',
      status: 'error',
      at: data?.at,
    })
    return
  }

  if (type === 'done') {
    progress.phase = 'finished'
    progress.phaseMessage = '分析完成'
    progress.step = data?.agent_steps || progress.step
    if (data?.model) progress.model = data.model
    if (data?.repo) progress.repo = data.repo
    if (data?.source) progress.source = data.source
    progress.finishedAt = Date.now()
    pushItem(state, {
      kind: 'status',
      title: '分析完成，报告已生成',
      status: 'ok',
      at: data?.at,
    })
  }
}

/**
 * @param {Array<{ type: string, data: object, at?: number }>} events
 * @param {{ repo?: string, source?: string, model?: string, created_at?: number, finished_at?: number }} meta
 */
export function progressFromEvents(events, meta = {}) {
  const state = createProgressState()
  state.progress.repo = meta.repo || ''
  state.progress.source = meta.source || ''
  state.progress.model = meta.model || ''
  state.progress.startedAt = meta.created_at || 0
  state.progress.finishedAt = meta.finished_at || 0
  for (const ev of events || []) {
    const data = ev?.data && typeof ev.data === 'object' ? { ...ev.data, at: ev.at } : { at: ev?.at }
    applyAnalysisEvent(state, ev?.type, data)
  }
  if (meta.finished_at) state.progress.finishedAt = meta.finished_at
  return state.progress
}
