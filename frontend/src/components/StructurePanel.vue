<script setup>
import { computed, ref } from 'vue'
import { parseIndentedTree } from '../utils/reportStats'

const props = defineProps({
  structure: {
    type: Object,
    default: () => ({ summary: '', tree_preview: '', tech_stack: [] }),
  },
})

const treeNodes = computed(() => parseIndentedTree(props.structure?.tree_preview || ''))
const useTreeUi = computed(() => Array.isArray(treeNodes.value) && treeNodes.value.length > 0)

/** 折叠的目录 id 集合 */
const collapsed = ref(/** @type {Record<string, boolean>} */ ({}))

/**
 * 展平树为带可见性的行（支持折叠）
 */
const flatRows = computed(() => {
  const roots = treeNodes.value || []
  /** @type {Array<{ id: string, label: string, depth: number, hasChildren: boolean, open: boolean }>} */
  const rows = []

  function walk(nodes, depth) {
    for (const node of nodes || []) {
      const hasChildren = !!(node.children && node.children.length)
      const open = collapsed.value[node.id] !== true
      rows.push({
        id: node.id,
        label: node.label,
        depth,
        hasChildren,
        open,
      })
      if (hasChildren && open) {
        walk(node.children, depth + 1)
      }
    }
  }

  walk(roots, 0)
  return rows
})

function toggle(id) {
  collapsed.value = {
    ...collapsed.value,
    [id]: collapsed.value[id] !== true,
  }
}
</script>

<template>
  <section class="card structure" id="report-structure">
    <h2 class="card-title">项目结构</h2>

    <div class="structure-grid">
      <div class="summary-col">
        <div class="section-label">摘要</div>
        <p v-if="structure?.summary" class="summary">{{ structure.summary }}</p>
        <p v-else class="empty-hint">暂无结构摘要。</p>
      </div>

      <div v-if="structure?.tech_stack?.length" class="stack-col">
        <div class="section-label">技术栈</div>
        <div class="chips">
          <span
            v-for="(item, i) in structure.tech_stack"
            :key="item"
            class="chip"
            :class="`chip-tone-${i % 5}`"
          >
            {{ item }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="structure?.tree_preview" class="tree-wrap">
      <div class="section-label">目录预览</div>

      <div v-if="useTreeUi" class="tree-ui" role="tree">
        <div
          v-for="row in flatRows"
          :key="row.id"
          class="tree-row"
          :style="{ paddingLeft: `${0.35 + row.depth * 0.9}rem` }"
          role="treeitem"
          :aria-expanded="row.hasChildren ? row.open : undefined"
        >
          <button
            v-if="row.hasChildren"
            type="button"
            class="tree-toggle"
            :aria-label="row.open ? '折叠' : '展开'"
            @click="toggle(row.id)"
          >
            {{ row.open ? '▾' : '▸' }}
          </button>
          <span v-else class="tree-spacer" />
          <span class="tree-label" :class="{ dir: row.hasChildren }">{{ row.label }}</span>
        </div>
      </div>
      <pre v-else class="tree-box">{{ structure.tree_preview }}</pre>
    </div>
  </section>
</template>

<style scoped>
.structure-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 1rem 1.25rem;
}

@media (max-width: 720px) {
  .structure-grid {
    grid-template-columns: 1fr;
  }
}

.section-label {
  font-size: 0.8rem;
  font-weight: 650;
  color: var(--text-dim);
  margin-bottom: 0.45rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.summary {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 0.88rem;
  color: var(--text);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.chip {
  display: inline-block;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 600;
  border: 1px solid transparent;
}

.chip-tone-0 {
  background: rgba(56, 189, 248, 0.14);
  color: #38bdf8;
  border-color: rgba(56, 189, 248, 0.3);
}
.chip-tone-1 {
  background: rgba(168, 85, 247, 0.14);
  color: #c084fc;
  border-color: rgba(168, 85, 247, 0.3);
}
.chip-tone-2 {
  background: rgba(16, 185, 129, 0.14);
  color: #34d399;
  border-color: rgba(16, 185, 129, 0.3);
}
.chip-tone-3 {
  background: rgba(251, 191, 36, 0.14);
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.3);
}
.chip-tone-4 {
  background: rgba(244, 63, 94, 0.14);
  color: #fb7185;
  border-color: rgba(244, 63, 94, 0.3);
}

.tree-wrap {
  margin-top: 1.15rem;
}

.tree-ui {
  max-height: 360px;
  overflow-y: auto;
  padding: 0.65rem 0.6rem;
  background: var(--surface-subtle);
  color: var(--text);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.tree-row {
  display: flex;
  align-items: center;
  gap: 0.1rem;
  min-height: 1.5rem;
}

.tree-toggle {
  width: 1.25rem;
  height: 1.25rem;
  border: none;
  background: transparent;
  color: var(--text-dim);
  padding: 0;
  font-size: 0.75rem;
  line-height: 1;
  flex-shrink: 0;
  transition: color 0.15s;
}

.tree-toggle:hover {
  color: var(--primary);
}

.tree-spacer {
  width: 1.25rem;
  flex-shrink: 0;
}

.tree-label {
  font-family: var(--mono);
  font-size: 0.78rem;
  color: var(--text);
  word-break: break-all;
}

.tree-label.dir {
  color: var(--primary);
  font-weight: 600;
}
</style>
