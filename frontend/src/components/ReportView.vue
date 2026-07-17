<script setup>
import StructurePanel from './StructurePanel.vue'
import FindingsList from './FindingsList.vue'
import ToolCallsPanel from './ToolCallsPanel.vue'

defineProps({
  report: {
    type: Object,
    required: true,
  },
})

function sourceLabel(source) {
  if (source === 'github') return 'GitHub'
  if (source === 'local') return '本地'
  return source || '-'
}
</script>

<template>
  <div class="report">
    <section class="card meta">
      <h2 class="card-title">分析报告</h2>
      <div class="meta-row">
        <span><strong>仓库</strong> {{ report.repo }}</span>
        <span>
          <strong>来源</strong>
          <span class="badge badge-neutral">{{ sourceLabel(report.source) }}</span>
        </span>
        <span><strong>模型</strong> {{ report.model || '-' }}</span>
        <span><strong>Agent 步数</strong> {{ report.agent_steps ?? 0 }}</span>
      </div>
    </section>

    <StructurePanel :structure="report.structure || {}" />

    <FindingsList
      title="风险"
      kind="risk"
      :items="report.risks || []"
      empty-text="未发现明确风险。"
    />

    <FindingsList
      title="Bug"
      kind="bug"
      :items="report.bugs || []"
      empty-text="未发现明确 Bug。"
    />

    <ToolCallsPanel
      :tool-calls="report.tool_calls || []"
      :raw-summary="report.raw_summary"
    />
  </div>
</template>

<style scoped>
.report {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.meta .badge {
  margin-left: 0.25rem;
}
</style>
