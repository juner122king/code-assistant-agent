<script setup>
import { severityClass, severityLabel } from '../utils/severity'

defineProps({
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
})
</script>

<template>
  <section class="card">
    <h2 class="card-title">
      {{ title }}
      <span class="count">{{ items?.length || 0 }}</span>
    </h2>

    <p v-if="!items?.length" class="empty-hint">{{ emptyText }}</p>

    <div v-else class="finding-list">
      <article v-for="(item, index) in items" :key="`${item.title}-${index}`" class="finding-item">
        <div class="finding-head">
          <h3 class="finding-title">{{ item.title || '未命名' }}</h3>
          <span class="badge" :class="`badge-${severityClass(item.severity)}`">
            {{ severityLabel(item.severity) }}
          </span>
        </div>

        <dl class="finding-field" v-if="kind === 'bug' && item.location">
          <dt>位置</dt>
          <dd>{{ item.location }}</dd>
        </dl>

        <dl class="finding-field" v-if="item.evidence">
          <dt>依据</dt>
          <dd>{{ item.evidence }}</dd>
        </dl>

        <dl class="finding-field" v-if="kind === 'risk' && item.recommendation">
          <dt>建议</dt>
          <dd>{{ item.recommendation }}</dd>
        </dl>

        <dl class="finding-field" v-if="kind === 'bug' && item.suggestion">
          <dt>修复建议</dt>
          <dd>{{ item.suggestion }}</dd>
        </dl>
      </article>
    </div>
  </section>
</template>

<style scoped>
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
