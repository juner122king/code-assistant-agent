<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  /** 时间线条目：{ id, kind, title, summary, status, step, preview, at } */
  items: {
    type: Array,
    default: () => [],
  },
  repo: { type: String, default: '' },
  source: { type: String, default: '' },
  model: { type: String, default: '' },
  step: { type: Number, default: 0 },
  maxSteps: { type: Number, default: 0 },
  phase: { type: String, default: '' },
  phaseMessage: { type: String, default: '准备分析…' },
  startedAt: { type: Number, default: 0 },
  finishedAt: { type: Number, default: 0 },
  live: { type: Boolean, default: true },
})

const elapsedSec = ref(0)
const listEl = ref(null)
let timer = null

onMounted(() => {
  tick()
  if (props.live) timer = setInterval(tick, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

watch(
  () => [props.live, props.startedAt, props.finishedAt],
  () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    tick()
    if (props.live) timer = setInterval(tick, 1000)
  },
)

function tick() {
  if (!props.startedAt) {
    elapsedSec.value = 0
    return
  }
  const end = props.live ? Date.now() : props.finishedAt || Date.now()
  elapsedSec.value = Math.max(0, Math.floor((end - props.startedAt) / 1000))
}

const elapsedLabel = computed(() => {
  const s = elapsedSec.value
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
})

const progressPct = computed(() => {
  if (!props.maxSteps || props.maxSteps <= 0) return 8
  const base = Math.min(props.step, props.maxSteps) / props.maxSteps
  // 进行中略微留一点余量；finished 阶段拉满一点
  if (!props.live || props.phase === 'finished') return 100
  if (props.phase === 'finished') return Math.min(96, Math.round(base * 100))
  return Math.max(6, Math.min(92, Math.round(base * 100)))
})

const sourceLabel = computed(() => {
  if (props.source === 'github') return 'GitHub'
  if (props.source === 'local') return '本地'
  return props.source || '—'
})

watch(
  () => props.items.length,
  async () => {
    await nextTick()
    const el = listEl.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

function statusIcon(status) {
  if (status === 'ok') return '✓'
  if (status === 'error') return '!'
  if (status === 'running') return '…'
  return '•'
}

function kindClass(item) {
  return {
    'is-running': item.status === 'running',
    'is-ok': item.status === 'ok',
    'is-error': item.status === 'error',
    [`kind-${item.kind || 'status'}`]: true,
  }
}
</script>

<template>
  <section class="card progress" role="status" aria-live="polite">
    <header class="progress-head">
      <div class="head-left">
        <div v-if="live" class="spinner" aria-hidden="true" />
        <div>
          <h2 class="card-title">{{ live ? '分析进行中' : '分析过程' }}</h2>
          <p class="phase-msg">{{ phaseMessage }}</p>
        </div>
      </div>
      <div class="head-right">
        <span class="elapsed" title="已用时间">已用 {{ elapsedLabel }}</span>
      </div>
    </header>

    <div class="meta-row">
      <span v-if="repo"><strong>仓库</strong> {{ repo }}</span>
      <span v-if="source">
        <strong>来源</strong>
        <span class="badge badge-neutral">{{ sourceLabel }}</span>
      </span>
      <span v-if="model"><strong>模型</strong> {{ model }}</span>
      <span v-if="maxSteps">
        <strong>进度</strong> 第 {{ step || 0 }} / {{ maxSteps }} 步
      </span>
    </div>

    <div class="bar-track" aria-hidden="true">
      <div class="bar-fill" :style="{ width: `${progressPct}%` }" />
    </div>

    <h3 class="timeline-title">
      {{ live ? '实时过程' : '完整过程' }}
      <span class="count">{{ items.length }}</span>
    </h3>

    <div ref="listEl" class="timeline" tabindex="0">
      <p v-if="!items.length" class="empty-hint">等待 Agent 启动…</p>
      <ol v-else class="timeline-list">
        <li
          v-for="item in items"
          :key="item.id"
          class="timeline-item"
          :class="kindClass(item)"
        >
          <span class="dot" aria-hidden="true">
            <span v-if="item.status === 'running'" class="dot-spin" />
            <template v-else>{{ statusIcon(item.status) }}</template>
          </span>
          <div class="item-body">
            <div class="item-top">
              <span class="item-title">{{ item.title }}</span>
              <span v-if="item.step" class="item-step">步骤 {{ item.step }}</span>
            </div>
            <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
            <details v-if="item.preview && item.status !== 'running'" class="item-preview">
              <summary>结果预览</summary>
              <pre>{{ item.preview }}</pre>
            </details>
          </div>
        </li>
      </ol>
    </div>

    <p v-if="live" class="foot-hint">请勿关闭或刷新本页。默认超时 10 分钟。</p>
  </section>
</template>

<style scoped>
.progress {
  margin-top: 1rem;
}

.progress-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.85rem;
}

.head-left {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
  min-width: 0;
}

.head-right {
  flex-shrink: 0;
}

.spinner {
  width: 26px;
  height: 26px;
  margin-top: 0.2rem;
  border-radius: 50%;
  border: 3px solid #dbeafe;
  border-top-color: var(--primary);
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.phase-msg {
  margin: 0.15rem 0 0;
  color: var(--text-muted);
  font-size: 0.92rem;
}

.elapsed {
  display: inline-block;
  font-family: var(--mono);
  font-size: 0.85rem;
  color: var(--text-muted);
  background: #f1f5f9;
  padding: 0.25rem 0.55rem;
  border-radius: 8px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1.1rem;
  font-size: 0.88rem;
  margin-bottom: 0.75rem;
  color: var(--text);
}

.meta-row strong {
  margin-right: 0.3rem;
  color: var(--text-muted);
  font-weight: 600;
}

.bar-track {
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
  margin-bottom: 1rem;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  transition: width 0.35s ease;
}

.timeline-title {
  margin: 0 0 0.55rem;
  font-size: 0.95rem;
  font-weight: 650;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.45rem;
  padding: 0 0.35rem;
  border-radius: 999px;
  background: #e2e8f0;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 700;
}

.timeline {
  max-height: 340px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #f8fafc;
  padding: 0.65rem 0.75rem;
}

.timeline-list {
  list-style: none;
  margin: 0;
  padding: 0 0 0 0.35rem;
  border-left: 2px solid #cbd5e1;
}

.timeline-item {
  position: relative;
  display: flex;
  gap: 0.65rem;
  padding: 0.45rem 0 0.55rem 0.85rem;
}

.dot {
  position: absolute;
  left: -0.55rem;
  top: 0.55rem;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.62rem;
  font-weight: 700;
  color: #64748b;
  line-height: 1;
}

.kind-tool .dot {
  border-color: #3b82f6;
  color: #2563eb;
}

.kind-step .dot {
  border-color: #8b5cf6;
  color: #7c3aed;
}

.kind-start .dot,
.kind-status .dot {
  border-color: #64748b;
}

.is-ok .dot {
  border-color: #059669;
  color: #059669;
  background: #ecfdf5;
}

.is-error .dot {
  border-color: #dc2626;
  color: #dc2626;
  background: #fef2f2;
}

.is-running .dot {
  border-color: #2563eb;
  background: #eff6ff;
}

.dot-spin {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  border: 1.5px solid #bfdbfe;
  border-top-color: #2563eb;
  animation: spin 0.7s linear infinite;
}

.item-body {
  min-width: 0;
  flex: 1;
}

.item-top {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem 0.65rem;
}

.item-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
}

.item-step {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--mono);
}

.item-summary {
  margin: 0.15rem 0 0;
  font-size: 0.84rem;
  color: var(--text-muted);
  font-family: var(--mono);
  word-break: break-all;
}

.item-preview {
  margin-top: 0.3rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.item-preview summary {
  cursor: pointer;
  user-select: none;
}

.item-preview pre {
  margin-top: 0.35rem;
  padding: 0.45rem 0.55rem;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  max-height: 120px;
  overflow: auto;
  font-size: 0.78rem;
}

.foot-hint {
  margin: 0.75rem 0 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.empty-hint {
  margin: 0.4rem 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
