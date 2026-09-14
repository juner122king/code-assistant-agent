<script setup>
import { onMounted, ref } from 'vue'
import { analyzeRepoStream, checkHealth, listAnalysisModels } from './api/analyze'
import { proposeFixStream } from './api/fix'
import { deleteAnalysisRun, getAnalysisRun, listAnalysisRuns } from './api/history'
import AnalyzeForm from './components/AnalyzeForm.vue'
import AnalysisHistory from './components/AnalysisHistory.vue'
import AnalysisProgress from './components/AnalysisProgress.vue'
import ErrorBanner from './components/ErrorBanner.vue'
import FixPreviewPanel from './components/FixPreviewPanel.vue'
import ReportView from './components/ReportView.vue'
import {
  applyAnalysisEvent,
  createEmptyProgress,
  progressFromEvents,
} from './utils/analysisProgress'

const form = ref({
  repo: '',
  branch: '',
  focus: 'general',
  max_steps: 8,
  model: 'Qwen/Qwen3-8B',
})

const loading = ref(false)
const error = ref('')
const report = ref(null)
const backendOk = ref(null)

/** 修复提案状态 */
const fixLoading = ref(false)
const fixProposal = ref(null)
const fixProgressMsg = ref('')
const fixingIndex = ref(null)
const fixError = ref('')

const progress = ref(createEmptyProgress())
const progressState = { progress: progress.value, itemSeq: 0 }

const runs = ref([])
const selectedId = ref('')
const historyLoading = ref(false)
const catalogModels = ref([])
const catalogDisclaimer = ref('')

async function refreshRuns() {
  historyLoading.value = true
  try {
    runs.value = await listAnalysisRuns()
  } catch {
    /* 列表失败不阻断主流程 */
  } finally {
    historyLoading.value = false
  }
}

function bindProgress(next) {
  progress.value = next
  progressState.progress = next
}

function handleStreamEvent(type, data) {
  applyAnalysisEvent(progressState, type, data)
  if (data?.run_id) selectedId.value = data.run_id
}

onMounted(async () => {
  backendOk.value = await checkHealth()
  await refreshRuns()
  try {
    const cat = await listAnalysisModels()
    catalogModels.value = cat.models || []
    catalogDisclaimer.value = cat.disclaimer || ''
  } catch {
    catalogModels.value = []
  }
})

async function onSubmit() {
  if (loading.value) return
  error.value = ''
  report.value = null
  fixProposal.value = null
  fixError.value = ''
  fixingIndex.value = null
  selectedId.value = ''
  const next = createEmptyProgress()
  next.startedAt = Date.now()
  next.phaseMessage = '正在连接后端并解析仓库…'
  bindProgress(next)
  progressState.itemSeq = 0
  applyAnalysisEvent(progressState, 'status', {
    message: '提交分析请求',
  })
  const first = progress.value.items[0]
  if (first) {
    first.status = 'running'
    first.summary = form.value.repo
  }
  loading.value = true

  try {
    const result = await analyzeRepoStream(
      {
        repo: form.value.repo,
        branch: form.value.branch,
        focus: form.value.focus,
        max_steps: form.value.max_steps,
        model: form.value.model,
      },
      { onEvent: handleStreamEvent },
    )
    if (first && first.status === 'running') {
      first.status = 'ok'
      first.title = '已提交并建立流式连接'
    }
    report.value = result
    if (result?.run_id) selectedId.value = result.run_id
    await refreshRuns()
  } catch (err) {
    error.value = err?.message || String(err)
    applyAnalysisEvent(progressState, 'error', { detail: error.value })
    await refreshRuns()
  } finally {
    loading.value = false
  }
}

async function onSelectRun(id) {
  if (loading.value || !id) return
  error.value = ''
  fixProposal.value = null
  selectedId.value = id
  try {
    const detail = await getAnalysisRun(id)
    report.value = detail.report || null
    bindProgress(
      progressFromEvents(detail.events || [], {
        repo: detail.repo,
        source: detail.source,
        model: detail.model,
        created_at: detail.created_at,
        finished_at: detail.finished_at,
      }),
    )
    if (detail.status === 'error' && detail.error) {
      error.value = detail.error
    }
  } catch (err) {
    error.value = err?.message || String(err)
  }
}

async function onDeleteRun(id) {
  if (!id || loading.value) return
  try {
    await deleteAnalysisRun(id)
    if (selectedId.value === id) {
      selectedId.value = ''
      report.value = null
      bindProgress(createEmptyProgress())
      progressState.itemSeq = 0
    }
    await refreshRuns()
  } catch (err) {
    error.value = err?.message || String(err)
  }
}

function handleFixEvent(type, data) {
  if (type === 'step' || type === 'status') {
    fixProgressMsg.value = data?.message || fixProgressMsg.value
  } else if (type === 'tool' && data?.status === 'running') {
    fixProgressMsg.value = `调用工具 ${data.name || ''}…`
  } else if (type === 'start') {
    fixProgressMsg.value = '修复 Agent 已启动…'
  }
}

async function onProposeFix({ item, index }) {
  if (fixLoading.value || loading.value) return
  const repo = form.value.repo || report.value?.repo
  if (!repo) {
    fixError.value = '缺少仓库路径，请重新分析。'
    return
  }

  fixLoading.value = true
  fixProposal.value = null
  fixError.value = ''
  fixingIndex.value = index
  fixProgressMsg.value = '正在生成修复提案…'

  try {
    const proposal = await proposeFixStream(
      {
        repo,
        branch: form.value.branch || undefined,
        bug: {
          title: item.title || '未命名',
          severity: item.severity || 'medium',
          location: item.location || '',
          evidence: item.evidence || '',
          suggestion: item.suggestion || '',
        },
      },
      { onEvent: handleFixEvent },
    )
    fixProposal.value = proposal
    // 滚动到预览
    requestAnimationFrame(() => {
      document.getElementById('fix-preview')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  } catch (err) {
    fixError.value = err?.message || String(err)
  } finally {
    fixLoading.value = false
    fixingIndex.value = null
  }
}

function onFixApplied(res) {
  if (fixProposal.value) {
    fixProposal.value = { ...fixProposal.value, applied: true }
  }
  if (res?.conflicts?.length) {
    fixError.value = `部分冲突: ${res.conflicts.join('; ')}`
  }
}

function onPrOpened(res) {
  if (fixProposal.value) {
    fixProposal.value = { ...fixProposal.value, applied: true }
  }
  if (res?.pr_url) {
    fixError.value = ''
  }
}
</script>

<template>
  <div class="page">
    <header class="hero">
      <div class="hero-inner">
        <p class="eyebrow">学习型 AI Agent</p>
        <h1>Code Assistant Agent</h1>
        <p class="subtitle">
          输入代码仓库，Agent 通过工具调用闭环分析并输出<strong>结构 / 风险 / Bug</strong>报告。
        </p>
        <p class="backend-status" :class="backendOk === false ? 'down' : ''">
          <template v-if="backendOk === null">正在检测后端…</template>
          <template v-else-if="backendOk">后端健康检查：正常</template>
          <template v-else>后端不可达（请启动 uvicorn :8000，开发模式需 Vite 代理）</template>
        </p>
      </div>
    </header>

    <main class="main">
      <AnalyzeForm
        v-model="form"
        :loading="loading"
        :models="catalogModels"
        :price-disclaimer="catalogDisclaimer"
        @submit="onSubmit"
      />

      <AnalysisHistory
        :runs="runs"
        :selected-id="selectedId"
        :loading="historyLoading"
        @select="onSelectRun"
        @delete="onDeleteRun"
      />

      <AnalysisProgress
        v-if="loading || progress.items.length"
        :items="progress.items"
        :repo="progress.repo"
        :source="progress.source"
        :model="progress.model"
        :step="progress.step"
        :max-steps="progress.maxSteps"
        :phase="progress.phase"
        :phase-message="progress.phaseMessage"
        :started-at="progress.startedAt"
        :finished-at="progress.finishedAt"
        :live="loading"
      />

      <ErrorBanner v-if="error && !loading" :message="error" @dismiss="error = ''" />
      <ErrorBanner v-if="fixError && !fixLoading" :message="fixError" @dismiss="fixError = ''" />

      <ReportView
        v-if="report && !loading"
        :report="report"
        :fixing-index="fixingIndex"
        @propose-fix="onProposeFix"
      />

      <div id="fix-preview">
        <FixPreviewPanel
          v-if="fixLoading || fixProposal"
          :proposal="fixProposal"
          :loading="fixLoading"
          :progress-message="fixProgressMsg"
          @close="fixProposal = null; fixLoading = false"
          @applied="onFixApplied"
          @pr-opened="onPrOpened"
          @error="(m) => (fixError = m)"
        />
      </div>

      <section v-if="!loading && !report && !error && !progress.items.length" class="card empty">
        <h2 class="card-title">等待分析</h2>
        <p class="empty-hint">
          提交后将通过 <code>POST /analyze/stream</code> 实时展示 Agent 步骤与工具调用。
          也可在 <a href="/docs" target="_blank" rel="noreferrer">/docs</a> 使用 Swagger。
          分析完成后可在 Bug 列表中「生成修复」→ 预览 diff → 应用到本地或提交 PR。
        </p>
      </section>
    </main>

    <footer class="footer">
      <span>分析 + 修复提案 · 先审后写 · 本地 apply / GitHub PR</span>
    </footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
  color: #eff6ff;
  padding: 2.2rem 1.25rem 2rem;
}

.hero-inner {
  max-width: 960px;
  margin: 0 auto;
}

.eyebrow {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.8;
}

h1 {
  margin: 0 0 0.55rem;
  font-size: clamp(1.6rem, 3vw, 2rem);
  letter-spacing: -0.02em;
}

.subtitle {
  margin: 0;
  max-width: 42rem;
  opacity: 0.92;
  font-size: 0.98rem;
}

.backend-status {
  margin: 0.9rem 0 0;
  font-size: 0.85rem;
  opacity: 0.85;
}

.backend-status.down {
  color: #fecaca;
  opacity: 1;
}

.main {
  width: 100%;
  max-width: 960px;
  margin: -1.1rem auto 0;
  padding: 0 1.25rem 2.5rem;
  flex: 1;
}

.empty {
  margin-top: 1rem;
}

.empty code {
  font-family: var(--mono);
  font-size: 0.85rem;
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.footer {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.82rem;
  padding: 0 1rem 1.5rem;
}
</style>
