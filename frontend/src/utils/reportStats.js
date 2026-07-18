import { severityClass, severityOrder } from './severity'

/**
 * @param {Array<{ severity?: string }>} items
 * @returns {{ high: number, medium: number, low: number, total: number }}
 */
export function countBySeverity(items = []) {
  const counts = { high: 0, medium: 0, low: 0 }
  for (const item of items || []) {
    const key = severityClass(item?.severity)
    counts[key] += 1
  }
  return {
    ...counts,
    total: counts.high + counts.medium + counts.low,
  }
}

/**
 * 合并 risks + bugs 的严重度分布
 * @param {object} report
 */
export function aggregateReportStats(report = {}) {
  const risks = report.risks || []
  const bugs = report.bugs || []
  const riskCounts = countBySeverity(risks)
  const bugCounts = countBySeverity(bugs)
  const severity = {
    high: riskCounts.high + bugCounts.high,
    medium: riskCounts.medium + bugCounts.medium,
    low: riskCounts.low + bugCounts.low,
  }
  const findingsTotal = severity.high + severity.medium + severity.low
  const toolCalls = report.tool_calls || []

  return {
    riskCount: risks.length,
    bugCount: bugs.length,
    highCount: severity.high,
    steps: report.agent_steps ?? 0,
    toolCount: toolCalls.length,
    severity,
    findingsTotal,
    isClean: findingsTotal === 0,
  }
}

/**
 * @param {Array<{ severity?: string }>} items
 * @param {'all' | 'high' | 'medium' | 'low'} filter
 * @param {'severity' | 'original'} sortBy
 */
export function filterAndSortFindings(items = [], filter = 'all', sortBy = 'severity') {
  let list = (items || []).map((item, index) => ({ item, index }))
  if (filter && filter !== 'all') {
    list = list.filter(({ item }) => severityClass(item?.severity) === filter)
  }
  if (sortBy === 'severity') {
    list = [...list].sort((a, b) => {
      const d = severityOrder(a.item?.severity) - severityOrder(b.item?.severity)
      return d !== 0 ? d : a.index - b.index
    })
  }
  return list.map(({ item }) => item)
}

/**
 * 解析 tool_calls 字符串：name(arg) 或 name
 * @param {string} call
 * @returns {{ name: string, arg: string, raw: string }}
 */
export function parseToolCall(call) {
  const raw = String(call || '')
  const m = raw.match(/^([a-zA-Z0-9_./-]+)\((.*)\)$/)
  if (m) {
    return { name: m[1], arg: m[2], raw }
  }
  return { name: raw || 'tool', arg: '', raw }
}

/**
 * @param {string[]} toolCalls
 * @returns {Record<string, number>}
 */
export function countToolNames(toolCalls = []) {
  const map = {}
  for (const call of toolCalls || []) {
    const { name } = parseToolCall(call)
    map[name] = (map[name] || 0) + 1
  }
  return map
}

/**
 * 将缩进文本解析为简易树节点；失败返回 null
 * @param {string} text
 * @returns {Array<{ id: string, label: string, depth: number, children: any[] }> | null}
 */
export function parseIndentedTree(text) {
  if (!text || !String(text).trim()) return null
  const lines = String(text)
    .replace(/\r\n/g, '\n')
    .split('\n')
    .filter((l) => l.trim().length > 0)
  if (lines.length < 1) return null

  /** @type {Array<{ id: string, label: string, depth: number, children: any[] }>} */
  const roots = []
  const stack = []

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    // 支持空格缩进或 tree 字符
    const cleaned = line
      .replace(/[│├└─┌┐┘┤┬┴┼]/g, ' ')
      .replace(/\t/g, '  ')
    const leading = cleaned.match(/^[ ]*/)?.[0]?.length ?? 0
    const label = cleaned.trim()
    if (!label) continue
    // 每 2 空格一层；tree 符号清理后可能 depth=0 全平
    const depth = Math.floor(leading / 2)
    const node = {
      id: `n-${i}`,
      label,
      depth,
      children: [],
    }

    while (stack.length && stack[stack.length - 1].depth >= depth) {
      stack.pop()
    }
    if (!stack.length) {
      roots.push(node)
    } else {
      stack[stack.length - 1].children.push(node)
    }
    stack.push(node)
  }

  // 全是 depth 0 且无 children → 无法形成树结构，用 flat 也可展示
  if (roots.length === 0) return null
  return roots
}
