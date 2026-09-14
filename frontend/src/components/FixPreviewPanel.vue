<script setup>
import { computed, ref } from 'vue'
import { applyFix, openFixPr } from '../api/fix'

const props = defineProps({
  proposal: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  progressMessage: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'applied', 'pr-opened', 'error'])

const acting = ref(false)
const actionMsg = ref('')
const prUrl = ref('')
const expanded = ref({})

const source = computed(() => props.proposal?.source || '')
const canApplyLocal = computed(
  () => source.value === 'local' && props.proposal?.fix_id && !props.proposal?.applied,
)
const canOpenPr = computed(
  () => source.value === 'github' && props.proposal?.fix_id && !props.proposal?.applied,
)
const changes = computed(() => props.proposal?.changes || [])

function toggle(path) {
  expanded.value = { ...expanded.value, [path]: !expanded.value[path] }
}

function isOpen(path, index) {
  if (expanded.value[path] === true) return true
  if (expanded.value[path] === false) return false
  return index === 0
}

async function copyAllDiff() {
  const text = changes.value.map((c) => c.unified_diff || `# ${c.path}\n`).join('\n')
  try {
    await navigator.clipboard.writeText(text || props.proposal?.summary || '')
    actionMsg.value = '已复制 diff'
    setTimeout(() => {
      if (actionMsg.value === '已复制 diff') actionMsg.value = ''
    }, 1600)
  } catch {
    actionMsg.value = '复制失败'
  }
}

async function onApply() {
  if (!canApplyLocal.value || acting.value) return
  acting.value = true
  actionMsg.value = ''
  try {
    const res = await applyFix({ fix_id: props.proposal.fix_id })
    actionMsg.value = res.message || '已应用'
    emit('applied', res)
  } catch (err) {
    const msg = err?.message || '应用失败'
    actionMsg.value = msg
    emit('error', msg)
  } finally {
    acting.value = false
  }
}

async function onOpenPr() {
  if (!canOpenPr.value || acting.value) return
  acting.value = true
  actionMsg.value = ''
  prUrl.value = ''
  try {
    const res = await openFixPr({ fix_id: props.proposal.fix_id })
    prUrl.value = res.pr_url || ''
    actionMsg.value = res.message || 'PR 已创建'
    emit('pr-opened', res)
  } catch (err) {
    const msg = err?.message || '创建 PR 失败'
    actionMsg.value = msg
    emit('error', msg)
  } finally {
    acting.value = false
  }
}
</script>

<template>
  <aside class="fix-panel card" aria-label="修复预览">
    <div class="panel-head">
      <div>
        <p class="eyebrow">Fix Preview</p>
        <h2 class="panel-title">修复提案</h2>
      </div>
      <button type="button" class="close-btn" @click="emit('close')">关闭</button>
    </div>

    <div v-if="loading" class="loading-block">
      <div class="spinner" aria-hidden="true" />
      <p>{{ progressMessage || '正在生成修复提案…' }}</p>
    </div>

    <template v-else-if="proposal">
      <div class="meta">
        <span class="badge" :class="source === 'github' ? 'badge-neutral' : 'badge-neutral'">
          {{ source === 'github' ? 'GitHub' : '本地' }}
        </span>
        <code class="fix-id">{{ proposal.fix_id }}</code>
      </div>

      <div v-if="proposal.bug" class="bug-box">
        <div class="block-label">目标 Bug</div>
        <p class="bug-title">{{ proposal.bug.title }}</p>
        <p v-if="proposal.bug.location" class="bug-loc">
          <code>{{ proposal.bug.location }}</code>
        </p>
      </div>

      <div class="summary-box">
        <div class="block-label">修复说明</div>
        <p class="summary-text">{{ proposal.summary || '（无说明）' }}</p>
      </div>

      <div class="changes-head">
        <h3>变更文件 <span class="count">{{ changes.length }}</span></h3>
        <button
          v-if="changes.length"
          type="button"
          class="ghost-btn"
          @click="copyAllDiff"
        >
          复制 diff
        </button>
      </div>

      <div v-if="!changes.length" class="empty-hint">
        提案中无文件变更。可能是 Agent 无法可靠修复，请查看说明或重新生成。
      </div>

      <div v-else class="change-list">
        <article
          v-for="(ch, index) in changes"
          :key="ch.path"
          class="change-item"
        >
          <button type="button" class="change-head" @click="toggle(ch.path)">
            <span class="action-tag">{{ ch.action }}</span>
            <code class="path">{{ ch.path }}</code>
            <span class="chev">{{ isOpen(ch.path, index) ? '▾' : '▸' }}</span>
          </button>
          <pre v-show="isOpen(ch.path, index)" class="diff">{{ ch.unified_diff || '（无 diff）' }}</pre>
        </article>
      </div>

      <div class="actions">
        <button
          v-if="canApplyLocal"
          type="button"
          class="primary-btn"
          :disabled="acting || !changes.length"
          @click="onApply"
        >
          {{ acting ? '应用中…' : '应用到本地' }}
        </button>
        <button
          v-if="canOpenPr"
          type="button"
          class="primary-btn"
          :disabled="acting || !changes.length"
          @click="onOpenPr"
        >
          {{ acting ? '提交中…' : '提交 PR' }}
        </button>
        <p v-if="source === 'github' && !canOpenPr && proposal.applied" class="hint">
          该提案已使用。
        </p>
        <p v-if="source === 'local' && !canApplyLocal && proposal.applied" class="hint">
          该提案已应用到本地。
        </p>
      </div>

      <p v-if="actionMsg" class="action-msg">{{ actionMsg }}</p>
      <p v-if="prUrl" class="pr-link">
        <a :href="prUrl" target="_blank" rel="noreferrer">{{ prUrl }}</a>
      </p>
    </template>

    <div v-else class="empty-hint">暂无提案。</div>
  </aside>
</template>

<style scoped>
.fix-panel {
  margin-top: 1rem;
  border: 1px solid #bfdbfe;
  background:
    radial-gradient(800px 120px at 100% 0%, rgba(37, 99, 235, 0.08), transparent),
    var(--surface);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.eyebrow {
  margin: 0 0 0.2rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  font-weight: 650;
}

.panel-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
}

.close-btn,
.ghost-btn {
  border: 1px solid var(--border);
  background: var(--surface-subtle);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 0.3rem 0.65rem;
  font-size: 0.78rem;
  font-weight: 600;
  transition: all 0.15s;
}

.close-btn:hover,
.ghost-btn:hover {
  color: var(--text);
  border-color: var(--border-hover);
  background: var(--surface-hover);
}

.loading-block {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 0;
  color: var(--text-muted);
}

.spinner {
  width: 1.1rem;
  height: 1.1rem;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.fix-id {
  font-size: 0.72rem;
  color: var(--text-dim);
  font-family: var(--mono);
  word-break: break-all;
}

.bug-box,
.summary-box {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.55rem 0.7rem;
  background: var(--surface-subtle);
  margin-bottom: 0.65rem;
}

.block-label {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 0.2rem;
}

.bug-title {
  margin: 0;
  font-weight: 650;
  color: var(--text);
  font-size: 0.9rem;
}

.bug-loc {
  margin: 0.3rem 0 0;
}

.bug-loc code {
  font-size: 0.76rem;
  background: var(--surface);
  color: var(--primary);
  border: 1px solid var(--border);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.summary-text {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.55;
  white-space: pre-wrap;
  color: var(--text);
}

.changes-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0.75rem 0 0.45rem;
}

.changes-head h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 650;
  color: var(--text);
}

.count {
  display: inline-flex;
  min-width: 1.3rem;
  padding: 0 0.35rem;
  border-radius: 999px;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
}

.change-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.change-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--surface-subtle);
}

.change-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.6rem;
  background: var(--surface);
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s;
}

.change-head:hover {
  background: var(--surface-hover);
}

.action-tag {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--primary);
  flex-shrink: 0;
}

.path {
  flex: 1;
  font-size: 0.78rem;
  font-family: var(--mono);
  color: var(--text);
  word-break: break-all;
}

.chev {
  opacity: 0.6;
}

.diff {
  margin: 0;
  padding: 0.6rem 0.75rem;
  font-family: var(--mono);
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--text);
  background: var(--surface-subtle);
  overflow-x: auto;
  white-space: pre;
  max-height: 320px;
  overflow-y: auto;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  margin-top: 1rem;
}

.primary-btn {
  border: none;
  background: linear-gradient(135deg, var(--low), #059669);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 0.5rem 1rem;
  font-weight: 650;
  font-size: 0.86rem;
  box-shadow: 0 2px 10px rgba(16, 185, 129, 0.3);
  transition: all 0.15s;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.primary-btn:not(:disabled):hover {
  transform: translateY(-1px);
  filter: brightness(1.05);
}

.hint,
.action-msg,
.empty-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0.35rem 0 0;
}

.pr-link {
  margin: 0.4rem 0 0;
  word-break: break-all;
}

.pr-link a {
  color: var(--primary);
}
</style>
