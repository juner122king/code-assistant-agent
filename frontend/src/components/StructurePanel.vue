<script setup>
defineProps({
  structure: {
    type: Object,
    default: () => ({ summary: '', tree_preview: '', tech_stack: [] }),
  },
})
</script>

<template>
  <section class="card">
    <h2 class="card-title">项目结构</h2>

    <p v-if="structure?.summary" class="summary">{{ structure.summary }}</p>
    <p v-else class="empty-hint">暂无结构摘要。</p>

    <div v-if="structure?.tech_stack?.length" class="stack">
      <div class="section-label">技术栈</div>
      <div class="chips">
        <span v-for="item in structure.tech_stack" :key="item" class="chip">{{ item }}</span>
      </div>
    </div>

    <div v-if="structure?.tree_preview" class="tree-wrap">
      <div class="section-label">目录预览</div>
      <pre class="tree-box">{{ structure.tree_preview }}</pre>
    </div>
  </section>
</template>

<style scoped>
.summary {
  margin: 0;
  white-space: pre-wrap;
}

.stack,
.tree-wrap {
  margin-top: 1rem;
}

.section-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 0.45rem;
}
</style>
