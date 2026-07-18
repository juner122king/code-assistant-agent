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
  font-size: 0.9rem;
}

.count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  margin-left: 0.4rem;
  padding: 0 0.4rem;
  border-radius: 999px;
  background: #e2e8f0;
  color: var(--text-muted);
  font-size: 0.78rem;
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
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  border: 1px solid var(--border);
  background: #f8fafc;
  color: var(--text-muted);
}

.type-chip strong {
  font-variant-numeric: tabular-nums;
  color: var(--text);
}

.type-chip.tone-read {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}
.type-chip.tone-list {
  background: #f5f3ff;
  border-color: #ddd6fe;
  color: #6d28d9;
}
.type-chip.tone-search {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #c2410c;
}
.type-chip.tone-meta {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #047857;
}

.tool-timeline {
  list-style: none;
  margin: 0;
  padding: 0 0 0 0.4rem;
  border-left: 2px solid #e2e8f0;
  max-height: 360px;
  overflow: auto;
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
  background: #fff;
  border: 2px solid #94a3b8;
}

.dot.tone-read {
  border-color: #3b82f6;
  background: #dbeafe;
}
.dot.tone-list {
  border-color: #8b5cf6;
  background: #ede9fe;
}
.dot.tone-search {
  border-color: #f97316;
  background: #ffedd5;
}
.dot.tone-meta {
  border-color: #10b981;
  background: #d1fae5;
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
  color: var(--text-muted);
  font-family: var(--mono);
}

.tool-name {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text);
}

.tool-name.tone-read {
  color: #1d4ed8;
}
.tool-name.tone-list {
  color: #6d28d9;
}
.tool-name.tone-search {
  color: #c2410c;
}
.tool-name.tone-meta {
  color: #047857;
}

.tool-arg {
  display: block;
  margin-top: 0.2rem;
  font-family: var(--mono);
  font-size: 0.78rem;
  color: var(--text-muted);
  word-break: break-all;
  background: #f1f5f9;
  padding: 0.2rem 0.45rem;
  border-radius: 5px;
}
</style>
