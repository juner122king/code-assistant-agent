<script setup>
defineProps({
  toolCalls: {
    type: Array,
    default: () => [],
  },
  rawSummary: {
    type: String,
    default: null,
  },
})
</script>

<template>
  <section class="card">
    <h2 class="card-title">
      工具调用轨迹
      <span class="count">{{ toolCalls?.length || 0 }}</span>
    </h2>
    <p class="hint">用于观察 Agent 在分析过程中调用了哪些工具（学习向）。</p>

    <p v-if="!toolCalls?.length" class="empty-hint">本次无工具调用记录。</p>
    <ol v-else class="tool-list">
      <li v-for="(call, index) in toolCalls" :key="`${index}-${call}`">{{ call }}</li>
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
</style>
