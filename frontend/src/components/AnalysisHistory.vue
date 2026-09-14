<script setup>
import { computed } from 'vue'

const props = defineProps({
  runs: { type: Array, default: () => [] },
  selectedId: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'delete'])

function statusLabel(status) {
  if (status === 'done') return '完成'
  if (status === 'error') return '失败'
  if (status === 'running') return '进行中'
  return status || '—'
}

function relativeTime(ms) {
  if (!ms) return ''
  const diff = Date.now() - Number(ms)
  if (diff < 45_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.max(1, Math.round(diff / 60_000))} 分钟前`
  if (diff < 86_400_000) return `${Math.max(1, Math.round(diff / 3_600_000))} 小时前`
  const d = new Date(Number(ms))
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function durationLabel(ms) {
  if (ms == null || ms < 0) return ''
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}m${String(r).padStart(2, '0')}s`
}

function onDelete(event, id) {
  event.stopPropagation()
  emit('delete', id)
}

const empty = computed(() => !props.loading && (!props.runs || props.runs.length === 0))
</script>

<template>
  <section class="card history">
    <header class="history-head">
      <h2 class="card-title">分析记录</h2>
      <span class="count">{{ runs.length }}</span>
    </header>
    <p class="hint">点击一条即可回看完整工具调用过程与报告。</p>

    <p v-if="loading" class="empty-hint">加载记录…</p>
    <p v-else-if="empty" class="empty-hint">还没有记录。完成一次分析后会出现在这里。</p>

    <ul v-else class="run-list">
      <li
        v-for="run in runs"
        :key="run.id"
        class="run-item"
        :class="{ selected: run.id === selectedId, [`st-${run.status}`]: true }"
      >
        <button type="button" class="run-main" @click="emit('select', run.id)">
          <div class="run-top">
            <span class="repo" :title="run.repo">{{ run.repo_short || run.repo }}</span>
            <span class="badge" :class="`st-${run.status}`">{{ statusLabel(run.status) }}</span>
          </div>
          <div class="run-meta">
            <span>{{ relativeTime(run.created_at) }}</span>
            <span v-if="run.source">{{ run.source === 'github' ? 'GitHub' : '本地' }}</span>
            <span v-if="run.focus && run.focus !== 'general'">{{ run.focus }}</span>
            <span v-if="run.duration_ms">{{ durationLabel(run.duration_ms) }}</span>
          </div>
          <div class="run-stats">
            <span>{{ run.agent_steps || 0 }} 步</span>
            <span>{{ run.event_count || 0 }} 事件</span>
            <span>{{ run.risk_count || 0 }} 风险</span>
            <span>{{ run.bug_count || 0 }} Bug</span>
          </div>
        </button>
        <button
          type="button"
          class="run-del"
          title="删除记录"
          :disabled="run.status === 'running'"
          @click="onDelete($event, run.id)"
        >
          删除
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.history {
  padding: 1rem 0.9rem;
}

.history-head {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.2rem;
}

.count {
  display: inline-flex;
  min-width: 1.45rem;
  padding: 0 0.35rem;
  border-radius: 999px;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  justify-content: center;
}

.hint,
.empty-hint {
  margin: 0 0 0.75rem;
  color: var(--text-muted);
  font-size: 0.82rem;
  line-height: 1.4;
}

.run-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.run-item {
  display: flex;
  gap: 0.45rem;
  align-items: stretch;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
  transition: all 0.15s;
}

.run-item:hover {
  border-color: var(--border-hover);
  background: var(--surface-hover);
}

.run-item.selected {
  border-color: var(--primary);
  background: var(--primary-soft);
  box-shadow: 0 0 10px var(--primary-glow);
}

.run-main {
  flex: 1;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 0.6rem 0.75rem;
  min-width: 0;
}

.run-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.repo {
  font-weight: 650;
  font-size: 0.88rem;
  color: var(--text);
  font-family: var(--mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge {
  flex-shrink: 0;
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.badge.st-done {
  background: var(--low-bg);
  color: var(--low);
  border-color: var(--low-border);
}

.badge.st-error {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: var(--danger-border);
}

.badge.st-running {
  background: var(--primary-soft);
  color: var(--primary);
  border-color: var(--border-hover);
}

.run-meta,
.run-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.65rem;
  margin-top: 0.28rem;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.run-del {
  border: 0;
  border-left: 1px solid var(--border);
  background: transparent;
  color: var(--text-dim);
  padding: 0 0.65rem;
  font-size: 0.75rem;
  transition: all 0.15s;
}

.run-del:hover:not(:disabled) {
  color: var(--danger);
  background: var(--danger-soft);
}

.run-del:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
