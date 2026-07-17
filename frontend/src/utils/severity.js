/** @typedef {'high' | 'medium' | 'low' | string} Severity */

const LABELS = {
  high: '高',
  medium: '中',
  low: '低',
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
 * @returns {string} CSS class suffix
 */
export function severityClass(severity) {
  const key = String(severity || 'medium').toLowerCase()
  if (key === 'high' || key === 'medium' || key === 'low') return key
  return 'medium'
}
