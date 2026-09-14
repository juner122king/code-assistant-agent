function formatDetail(detail) {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object') return JSON.stringify(detail)
  return String(detail)
}

async function readJson(res) {
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    const err = new Error(formatDetail(data?.detail) || res.statusText || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return data
}

export async function listAnalysisRuns() {
  const res = await fetch('/analyze/runs')
  const data = await readJson(res)
  return data?.runs || []
}

export async function getAnalysisRun(runId) {
  const res = await fetch(`/analyze/runs/${encodeURIComponent(runId)}`)
  return readJson(res)
}

export async function deleteAnalysisRun(runId) {
  const res = await fetch(`/analyze/runs/${encodeURIComponent(runId)}`, { method: 'DELETE' })
  return readJson(res)
}
