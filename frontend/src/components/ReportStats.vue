<script setup>
import { computed } from 'vue'
import { aggregateReportStats } from '../utils/reportStats'
import { severityLabel } from '../utils/severity'

const props = defineProps({
  report: {
    type: Object,
    required: true,
  },
})

const stats = computed(() => aggregateReportStats(props.report))

const barSegments = computed(() => {
  const { high, medium, low } = stats.value.severity
  const total = high + medium + low
  if (!total) {
    return [
      { key: 'empty', label: '无问题', count: 0, pct: 100, className: 'seg-empty' },
    ]
  }
  return [
    { key: 'high', label: severityLabel('high'), count: high, pct: (high / total) * 100, className: 'seg-high' },
    { key: 'medium', label: severityLabel('medium'), count: medium, pct: (medium / total) * 100, className: 'seg-medium' },
    { key: 'low', label: severityLabel('low'), count: low, pct: (low / total) * 100, className: 'seg-low' },
  ].filter((s) => s.count > 0)
})
</script>

<template>
  <section class="stats card" id="report-overview">
    <div class="stats-head">
      <h2 class="card-title">结果总览</h2>
      <p v-if="stats.isClean" class="clean-tag">未发现明确风险或 Bug</p>
      <p v-else class="hint-tag">按严重度汇总风险与 Bug</p>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">风险</div>
        <div class="stat-value">{{ stats.riskCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Bug</div>
        <div class="stat-value">{{ stats.bugCount }}</div>
      </div>
      <div class="stat-card" :class="{ alert: stats.highCount > 0 }">
        <div class="stat-label">高严重度</div>
        <div class="stat-value">{{ stats.highCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Agent 步数</div>
        <div class="stat-value">{{ stats.steps }}</div>
        <div class="stat-sub">{{ stats.toolCount }} 次工具调用</div>
      </div>
    </div>

    <div class="severity-block">
      <div class="severity-head">
        <span class="section-label">严重度分布</span>
        <span class="severity-total">共 {{ stats.findingsTotal }} 项</span>
      </div>
      <div class="severity-bar" role="img" :aria-label="`高${stats.severity.high} 中${stats.severity.medium} 低${stats.severity.low}`">
        <div
          v-for="seg in barSegments"
          :key="seg.key"
          class="severity-seg"
          :class="seg.className"
          :style="{ width: `${Math.max(seg.pct, seg.count ? 4 : 0)}%` }"
          :title="`${seg.label}: ${seg.count}`"
        />
      </div>
      <div class="severity-legend">
        <span class="legend-item">
          <i class="dot high" />高 {{ stats.severity.high }}
        </span>
        <span class="legend-item">
          <i class="dot medium" />中 {{ stats.severity.medium }}
        </span>
        <span class="legend-item">
          <i class="dot low" />低 {{ stats.severity.low }}
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.stats-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
  margin-bottom: 0.25rem;
}

.stats-head .card-title {
  margin-bottom: 0;
}

.clean-tag {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--low);
  background: var(--low-bg);
  border: 1px solid var(--low-border);
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
}

.hint-tag {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 0.85rem;
}

@media (max-width: 720px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.stat-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
  padding: 0.75rem 0.9rem;
  min-height: 4.5rem;
  transition: all 0.15s;
}

.stat-card:hover {
  border-color: var(--border-hover);
  transform: translateY(-1px);
}

.stat-card.alert {
  border-color: var(--high-border);
  background: linear-gradient(180deg, var(--high-bg) 0%, var(--surface-subtle) 100%);
}

.stat-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-dim);
  letter-spacing: 0.02em;
}

.stat-value {
  margin-top: 0.2rem;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
  color: var(--text);
  font-family: var(--mono);
}

.stat-card.alert .stat-value {
  color: var(--high);
}

.stat-sub {
  margin-top: 0.2rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.severity-block {
  margin-top: 1.1rem;
}

.severity-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.45rem;
}

.section-label {
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--text-muted);
}

.severity-total {
  font-size: 0.78rem;
  color: var(--text-dim);
}

.severity-bar {
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  gap: 2px;
}

.severity-seg {
  height: 100%;
  min-width: 0;
  transition: width 0.35s ease;
}

.seg-high {
  background: var(--high);
}

.seg-medium {
  background: var(--medium);
}

.seg-low {
  background: var(--low);
}

.seg-empty {
  background: var(--border-hover);
  opacity: 0.35;
}

.severity-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.1rem;
  margin-top: 0.55rem;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  display: inline-block;
}

.dot.high {
  background: var(--high);
}

.dot.medium {
  background: var(--medium);
}

.dot.low {
  background: var(--low);
}
</style>
