<script setup>
import { computed, ref, watch } from 'vue'
import { severityClass, severityLabel } from '../utils/severity'
import { filterAndSortFindings } from '../utils/reportStats'

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    default: () => [],
  },
  /** 'risk' | 'bug' */
  kind: {
    type: String,
    default: 'risk',
  },
  emptyText: {
    type: String,
    default: '未发现相关项。',
  },
  sectionId: {
    type: String,
    default: '',
  },
  /** 是否显示「生成修复」按钮（仅 bug） */
  enableFix: {
    type: Boolean,
    default: false,
  },
  fixingIndex: {
    type: [Number, null],
    default: null,
  },
})

const emit = defineEmits(['propose-fix'])

const filter = ref('all')
const collapsed = ref({})

const filtered = computed(() =>
  filterAndSortFindings(props.items || [], filter.value, 'severity'),
)

const collapseByDefault = computed(() => (props.items?.length || 0) > 5)

watch(
  () => props.items,
  () => {
    collapsed.value = {}
  },
  { deep: true },
)

function isExpanded(index) {
  if (collapsed.value[index] === true) return false
  if (collapsed.value[index] === false) return true
  return !collapseByDefault.value
}

function toggle(index) {
  const open = isExpanded(index)
  collapsed.value = { ...collapsed.value, [index]: open }
}

const filterOptions = [
  { value: 'all', label: '全部' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

function countFor(sev) {
  if (sev === 'all') return props.items?.length || 0
  return (props.items || []).filter((i) => severityClass(i.severity) === sev).length
}

function onProposeFix(item, index) {
  emit('propose-fix', { item, index })
}
</script>

<template>
  <section class="card findings-card" :id="sectionId || undefined">
    <div class="findings-head">
      <h2 class="card-title">
        {{ title }}
        <span class="count">{{ items?.length || 0 }}</span>
      </h2>

      <div v-if="items?.length" class="filter-bar" role="tablist" :aria-label="`${title}筛选`">
        <button
          v-for="opt in filterOptions"
          :key="opt.value"
          type="button"
          class="filter-chip"
          :class="{ active: filter === opt.value, [`sev-${opt.value}`]: opt.value !== 'all' }"
          role="tab"
          :aria-selected="filter === opt.value"
          @click="filter = opt.value"
        >
          {{ opt.label }}
          <span class="filter-n">{{ countFor(opt.value) }}</span>
        </button>
      </div>
    </div>

    <div v-if="!items?.length" class="empty-state">
      <div class="empty-icon" aria-hidden="true">✓</div>
      <p class="empty-hint">{{ emptyText }}</p>
    </div>

    <div v-else-if="!filtered.length" class="empty-state mild">
      <p class="empty-hint">当前筛选下无匹配项。</p>
    </div>

    <div v-else class="finding-list">
      <article
        v-for="(item, index) in filtered"
        :key="`${item.title}-${index}`"
        class="finding-item"
        :class="`finding-item--${severityClass(item.severity)}`"
      >
        <div class="finding-head">
          <div class="title-wrap">
            <span class="idx">{{ index + 1 }}</span>
            <h3 class="finding-title">{{ item.title || '未命名' }}</h3>
          </div>
          <div class="head-actions">
            <span class="badge" :class="`badge-${severityClass(item.severity)}`">
              {{ severityLabel(item.severity) }}
            </span>
            <button
              v-if="collapseByDefault"
              type="button"
              class="toggle-btn"
              @click="toggle(index)"
            >
              {{ isExpanded(index) ? '收起' : '展开' }}
            </button>
          </div>
        </div>

        <div v-show="isExpanded(index)" class="finding-body">
          <div v-if="kind === 'bug' && item.location" class="loc-row">
            <span class="loc-label">位置</span>
            <code class="loc-path">{{ item.location }}</code>
          </div>

          <div v-if="item.evidence" class="block evidence">
            <div class="block-label">依据</div>
            <p class="block-text">{{ item.evidence }}</p>
          </div>

          <div
            v-if="kind === 'risk' && item.recommendation"
            class="block action"
          >
            <div class="block-label">建议</div>
            <p class="block-text">{{ item.recommendation }}</p>
          </div>

          <div
            v-if="kind === 'bug' && item.suggestion"
            class="block action"
          >
            <div class="block-label">修复建议</div>
            <p class="block-text">{{ item.suggestion }}</p>
          </div>

          <div v-if="kind === 'bug' && enableFix" class="fix-actions">
            <button
              type="button"
              class="fix-btn"
              :disabled="fixingIndex === index"
              @click="onProposeFix(item, index)"
            >
              {{ fixingIndex === index ? '生成中…' : '生成修复' }}
            </button>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.findings-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem 1rem;
  margin-bottom: 0.85rem;
}

.findings-head .card-title {
  margin: 0;
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

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.filter-chip {
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.filter-chip:hover {
  border-color: #cbd5e1;
  color: var(--text);
}

.filter-chip.active {
  background: var(--primary-soft);
  border-color: #bfdbfe;
  color: var(--primary);
}

.filter-chip.sev-high.active {
  background: var(--high-bg);
  border-color: #fecaca;
  color: var(--high);
}

.filter-chip.sev-medium.active {
  background: var(--medium-bg);
  border-color: #fde68a;
  color: var(--medium);
}

.filter-chip.sev-low.active {
  background: var(--low-bg);
  border-color: #a7f3d0;
  color: var(--low);
}

.filter-n {
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 1.25rem 0.5rem 0.75rem;
  text-align: center;
}

.empty-state.mild {
  padding: 0.75rem;
}

.empty-icon {
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--low-bg);
  color: var(--low);
  font-weight: 700;
  border: 1px solid #a7f3d0;
}

.finding-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.finding-item {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.9rem 1rem 0.9rem 1.05rem;
  background: #fafbfc;
  border-left: 4px solid #94a3b8;
  transition: box-shadow 0.15s;
}

.finding-item:hover {
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
}

.finding-item--high {
  border-left-color: var(--high);
  background: linear-gradient(90deg, #fef2f2 0%, #fafbfc 28%);
}

.finding-item--medium {
  border-left-color: var(--medium);
  background: linear-gradient(90deg, #fffbeb 0%, #fafbfc 28%);
}

.finding-item--low {
  border-left-color: var(--low);
  background: linear-gradient(90deg, #ecfdf5 0%, #fafbfc 28%);
}

.finding-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  min-width: 0;
}

.idx {
  flex-shrink: 0;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 6px;
  background: #e2e8f0;
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.1rem;
}

.finding-title {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 650;
  line-height: 1.4;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.toggle-btn {
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-muted);
  border-radius: 6px;
  padding: 0.15rem 0.45rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.toggle-btn:hover {
  color: var(--text);
  border-color: #cbd5e1;
}

.finding-body {
  margin-top: 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.loc-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.55rem;
}

.loc-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
}

.loc-path {
  font-family: var(--mono);
  font-size: 0.8rem;
  background: #0f172a;
  color: #e2e8f0;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  word-break: break-all;
}

.block {
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border);
  background: #fff;
}

.block.evidence {
  background: #f8fafc;
}

.block.action {
  background: var(--primary-soft);
  border-color: #bfdbfe;
}

.block-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}

.block.action .block-label {
  color: var(--primary);
}

.block-text {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.55;
  white-space: pre-wrap;
  color: var(--text);
}

.fix-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.15rem;
}

.fix-btn {
  border: 1px solid #bfdbfe;
  background: var(--primary-soft);
  color: var(--primary);
  border-radius: 8px;
  padding: 0.35rem 0.75rem;
  font-size: 0.82rem;
  font-weight: 650;
}

.fix-btn:hover:not(:disabled) {
  background: #dbeafe;
}

.fix-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
