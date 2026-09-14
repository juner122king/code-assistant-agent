<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import StructurePanel from './StructurePanel.vue'
import FindingsList from './FindingsList.vue'
import ToolCallsPanel from './ToolCallsPanel.vue'
import ReportStats from './ReportStats.vue'
import { aggregateReportStats } from '../utils/reportStats'

const props = defineProps({
  report: {
    type: Object,
    required: true,
  },
  fixingIndex: {
    type: [Number, null],
    default: null,
  },
})

const emit = defineEmits(['propose-fix'])

const activeSection = ref('overview')
const copyState = ref('')
let observer = null

const stats = computed(() => aggregateReportStats(props.report))

const navItems = computed(() => [
  { id: 'overview', label: '总览', target: 'report-overview' },
  { id: 'structure', label: '结构', target: 'report-structure' },
  { id: 'risks', label: `风险 ${stats.value.riskCount}`, target: 'report-risks' },
  { id: 'bugs', label: `Bug ${stats.value.bugCount}`, target: 'report-bugs' },
  { id: 'tools', label: `过程 ${stats.value.toolCount}`, target: 'report-tools' },
])

function sourceLabel(source) {
  if (source === 'github') return 'GitHub'
  if (source === 'local') return '本地'
  return source || '-'
}

const githubUrl = computed(() => {
  if (props.report?.source !== 'github') return null
  const repo = String(props.report.repo || '').trim()
  // owner/name 或完整 URL
  if (/^https?:\/\/github\.com\//i.test(repo)) return repo.replace(/\.git$/, '')
  if (/^[^/\s]+\/[^/\s]+$/.test(repo)) return `https://github.com/${repo}`
  return null
})

function scrollTo(targetId) {
  const el = document.getElementById(targetId)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  activeSection.value = navItems.value.find((n) => n.target === targetId)?.id || activeSection.value
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText(JSON.stringify(props.report, null, 2))
    copyState.value = '已复制'
    setTimeout(() => {
      copyState.value = ''
    }, 1600)
  } catch {
    copyState.value = '复制失败'
    setTimeout(() => {
      copyState.value = ''
    }, 1600)
  }
}

onMounted(async () => {
  await nextTick()
  const ids = navItems.value.map((n) => n.target)
  const elements = ids.map((id) => document.getElementById(id)).filter(Boolean)
  if (!elements.length || typeof IntersectionObserver === 'undefined') return

  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)
      if (!visible.length) return
      const id = visible[0].target.id
      const item = navItems.value.find((n) => n.target === id)
      if (item) activeSection.value = item.id
    },
    { rootMargin: '-20% 0px -55% 0px', threshold: [0.1, 0.25, 0.5] },
  )
  elements.forEach((el) => observer.observe(el))
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="report">
    <section class="card report-hero">
      <div class="hero-top">
        <div>
          <p class="eyebrow">Analysis Report</p>
          <h2 class="hero-title">
            分析报告
            <span class="done-pill">已完成</span>
          </h2>
        </div>
        <button type="button" class="copy-btn" @click="copyJson">
          {{ copyState || '复制 JSON' }}
        </button>
      </div>

      <div class="repo-line">
        <span class="repo-label">仓库</span>
        <a
          v-if="githubUrl"
          class="repo-name link"
          :href="githubUrl"
          target="_blank"
          rel="noreferrer"
        >
          {{ report.repo }}
        </a>
        <code v-else class="repo-name">{{ report.repo }}</code>
      </div>

      <div class="meta-row">
        <span>
          <strong>来源</strong>
          <span class="badge badge-neutral">{{ sourceLabel(report.source) }}</span>
        </span>
        <span><strong>模型</strong> {{ report.model || '-' }}</span>
        <span><strong>Agent 步数</strong> {{ report.agent_steps ?? 0 }}</span>
        <span><strong>工具调用</strong> {{ report.tool_calls?.length ?? 0 }}</span>
      </div>
    </section>

    <nav class="report-nav" aria-label="报告章节">
      <button
        v-for="item in navItems"
        :key="item.id"
        type="button"
        class="nav-pill"
        :class="{ active: activeSection === item.id }"
        @click="scrollTo(item.target)"
      >
        {{ item.label }}
      </button>
    </nav>

    <ReportStats :report="report" />

    <StructurePanel :structure="report.structure || {}" />

    <FindingsList
      title="风险"
      kind="risk"
      section-id="report-risks"
      :items="report.risks || []"
      empty-text="未发现明确风险。"
    />

    <FindingsList
      title="Bug"
      kind="bug"
      section-id="report-bugs"
      :items="report.bugs || []"
      empty-text="未发现明确 Bug。"
      enable-fix
      :fixing-index="fixingIndex"
      @propose-fix="emit('propose-fix', $event)"
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

.report :deep(.card + .card) {
  margin-top: 0;
}

.report :deep(.card) {
  scroll-margin-top: 4.25rem;
}

.report-hero {
  background:
    radial-gradient(1200px 200px at 10% -40%, var(--primary-soft), transparent),
    var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.hero-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.eyebrow {
  margin: 0 0 0.25rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  font-weight: 650;
}

.hero-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  color: var(--text);
}

.done-pill {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--low);
  background: var(--low-bg);
  border: 1px solid var(--low-border);
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  letter-spacing: 0.02em;
}

.copy-btn {
  flex-shrink: 0;
  border: 1px solid var(--border);
  background: var(--surface-subtle);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 0.35rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 600;
  transition: all 0.15s;
}

.copy-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-soft);
}

.repo-line {
  margin-top: 0.85rem;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.45rem 0.65rem;
}

.repo-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-dim);
}

.repo-name {
  font-family: var(--mono);
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text);
  word-break: break-all;
}

.repo-name.link {
  color: var(--primary);
  text-decoration: none;
}

.repo-name.link:hover {
  text-decoration: underline;
}

.meta-row {
  margin-top: 0.75rem;
}

.meta-row .badge {
  margin-left: 0.25rem;
}

.report-nav {
  position: sticky;
  top: 3.5rem;
  z-index: 20;
  display: flex;
  flex-wrap: nowrap;
  gap: 0.35rem;
  overflow-x: auto;
  padding: 0.35rem;
  background: var(--surface-glass);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  -webkit-overflow-scrolling: touch;
}

.nav-pill {
  flex-shrink: 0;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.3rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
  transition: all 0.15s;
}

.nav-pill:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.nav-pill.active {
  background: var(--primary);
  color: #fff;
  box-shadow: 0 2px 8px var(--primary-glow);
}
</style>
