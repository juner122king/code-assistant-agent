<script setup>
import { computed } from 'vue'
import { countToolNames, parseToolCall } from '../utils/reportStats'

const props = defineProps({
  toolCalls: {
    type: Array,
    default: () => [],
  },
  rawSummary: {
    type: String,
    default: null,
  },
})

const parsed = computed(() => (props.toolCalls || []).map(parseToolCall))

const typeCounts = computed(() => {
  const map = countToolNames(props.toolCalls || [])
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }))
})

function toneClass(name) {
  const n = String(name || '')
  if (n.includes('read')) return 'tone-read'
  if (n.includes('list') || n.includes('tree')) return 'tone-list'
  if (n.includes('search')) return 'tone-search'
  if (n.includes('meta') || n.includes('summar')) return 'tone-meta'
  return 'tone-default'
}
</script>

<template>
  <section class="card tools-card" id="report-tools">
    <h2 class="card-title">
      工具调用轨迹
      <span class="count">{{ toolCalls?.length || 0 }}</span>
    </h2>
    <p class="hint">Agent 分析过程中的工具调用（学习向可视化）。</p>

    <div v-if="typeCounts.length" class="type-chips">
      <span
        v-for="t in typeCounts"
        :key="t.name"
        class="type-chip"
        :class="toneClass(t.name)"
      >
        {{ t.name }}
        <strong>{{ t.count }}</strong>
      </span>
    </div>

    <p v-if="!toolCalls?.length" class="empty-hint">本次无工具调用记录。</p>

    <ol v-else class="tool-timeline">
      <li
        v-for="(call, index) in parsed"
        :key="`${index}-${call.raw}`"
        class="tool-item"
      >
        <span class="dot" :class="toneClass(call.name)" aria-hidden="true" />
        <div class="tool-body">
          <div class="tool-top">
            <span class="tool-idx">#{{ index + 1 }}</span>
            <span class="tool-name" :class="toneClass(call.name)">{{ call.name }}</span>
          </div>
          <code v-if="call.arg" class="tool-arg">{{ call.arg }}</code>
        </div>
      </li>
    </ol>

    <details v-if="rawSummary" class="raw-box">
      <summary>原始模型输出（解析异常时保留）</summary>
      <pre class="raw-pre">{{ rawSummary }}</pre>
    </details>
  </section>
</template>

<style scoped>
.hint {
  margin: -0.4rem 0 0.85rem;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  margin-left: 0.4rem;
  padding: 0 0.4rem;
  border-radius: 999px;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  vertical-align: middle;
}

.type-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.9rem;
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  border: 1px solid var(--border);
  background: var(--surface-subtle);
  color: var(--text-muted);
}

.type-chip strong {
  font-variant-numeric: tabular-nums;
  color: var(--text);
}

.type-chip.tone-read {
  background: rgba(56, 189, 248, 0.12);
  border-color: rgba(56, 189, 248, 0.3);
  color: #38bdf8;
}
.type-chip.tone-list {
  background: rgba(168, 85, 247, 0.12);
  border-color: rgba(168, 85, 247, 0.3);
  color: #c084fc;
}
.type-chip.tone-search {
  background: rgba(251, 191, 36, 0.12);
  border-color: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}
.type-chip.tone-meta {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.3);
  color: #34d399;
}

.tool-timeline {
  list-style: none;
  margin: 0;
  padding: 0 0 0 0.4rem;
  border-left: 2px solid var(--border);
  max-height: 380px;
  overflow-y: auto;
}

.tool-item {
  position: relative;
  display: flex;
  gap: 0.65rem;
  padding: 0.4rem 0 0.5rem 0.9rem;
}

.dot {
  position: absolute;
  left: -0.42rem;
  top: 0.55rem;
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  background: var(--surface);
  border: 2px solid var(--border);
}

.dot.tone-read {
  border-color: #38bdf8;
  background: rgba(56, 189, 248, 0.2);
}
.dot.tone-list {
  border-color: #c084fc;
  background: rgba(168, 85, 247, 0.2);
}
.dot.tone-search {
  border-color: #fbbf24;
  background: rgba(251, 191, 36, 0.2);
}
.dot.tone-meta {
  border-color: #34d399;
  background: rgba(16, 185, 129, 0.2);
}

.tool-body {
  min-width: 0;
  flex: 1;
}

.tool-top {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.tool-idx {
  font-size: 0.72rem;
  color: var(--text-dim);
  font-family: var(--mono);
}

.tool-name {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text);
  font-family: var(--mono);
}

.tool-name.tone-read {
  color: #38bdf8;
}
.tool-name.tone-list {
  color: #c084fc;
}
.tool-name.tone-search {
  color: #fbbf24;
}
.tool-name.tone-meta {
  color: #34d399;
}

.tool-arg {
  display: block;
  margin-top: 0.2rem;
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--text);
  word-break: break-all;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  padding: 0.2rem 0.45rem;
  border-radius: var(--radius-sm);
}
</style>
