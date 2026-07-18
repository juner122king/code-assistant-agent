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
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 0.45rem;
}

.summary {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 0.95rem;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.chip {
  display: inline-block;
  padding: 0.28rem 0.65rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid transparent;
}

.chip-tone-0 {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #bfdbfe;
}
.chip-tone-1 {
  background: #f5f3ff;
  color: #6d28d9;
  border-color: #ddd6fe;
}
.chip-tone-2 {
  background: #ecfdf5;
  color: #047857;
  border-color: #a7f3d0;
}
.chip-tone-3 {
  background: #fff7ed;
  color: #c2410c;
  border-color: #fed7aa;
}
.chip-tone-4 {
  background: #fdf2f8;
  color: #be185d;
  border-color: #fbcfe8;
}

.tree-wrap {
  margin-top: 1.15rem;
}

.tree-ui {
  max-height: 360px;
  overflow: auto;
  padding: 0.55rem 0.5rem;
  background: #0b1220;
  color: #e2e8f0;
  border-radius: 10px;
  border: 1px solid #1e293b;
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
  color: #94a3b8;
  padding: 0;
  font-size: 0.75rem;
  line-height: 1;
  flex-shrink: 0;
}

.tree-toggle:hover {
  color: #e2e8f0;
}

.tree-spacer {
  width: 1.25rem;
  flex-shrink: 0;
}

.tree-label {
  font-family: var(--mono);
  font-size: 0.8rem;
  color: #cbd5e1;
  word-break: break-all;
}

.tree-label.dir {
  color: #93c5fd;
  font-weight: 600;
}
</style>
