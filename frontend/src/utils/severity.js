/** @typedef {'high' | 'medium' | 'low' | string} Severity */

const LABELS = {
  high: '高',
  medium: '中',
  low: '低',
}

const ORDER = {
  high: 0,
  medium: 1,
  low: 2,
}

/**
 * @param {Severity} severity
 * @returns {string}
 */
export function severityLabel(severity) {
  const key = String(severity || 'medium').toLowerCase()
  return LABELS[key] || severity || '中'
}

/**
 * @param {Severity} severity
 * @returns {'high' | 'medium' | 'low'}
 */
export function severityClass(severity) {
  const key = String(severity || 'medium').toLowerCase()
  if (key === 'high' || key === 'medium' || key === 'low') return key
  return 'medium'
}

/**
 * 排序权重：高 < 中 < 低（数字越小越靠前）
 * @param {Severity} severity
 * @returns {number}
 */
export function severityOrder(severity) {
  return ORDER[severityClass(severity)] ?? 1
}

/**
 * @param {Severity} severity
 * @returns {string} CSS 变量色
 */
export function severityColorVar(severity) {
  const key = severityClass(severity)
  if (key === 'high') return 'var(--high)'
  if (key === 'low') return 'var(--low)'
  return 'var(--medium)'
}
