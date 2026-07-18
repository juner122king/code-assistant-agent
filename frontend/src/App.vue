<script setup>
import { onMounted, ref } from 'vue'
import { analyzeRepoStream, checkHealth } from './api/analyze'
import AnalyzeForm from './components/AnalyzeForm.vue'
import AnalysisProgress from './components/AnalysisProgress.vue'
import ErrorBanner from './components/ErrorBanner.vue'
import ReportView from './components/ReportView.vue'

// 使用 ref 才能让 v-model 整对象替换生效（reactive + 重赋值会静默失败）
const form = ref({
  repo: '',
  branch: '',
  focus: 'general',
})

const loading = ref(false)
const error = ref('')
const report = ref(null)
const backendOk = ref(null)

/** 过程面板状态 */
const progress = ref(createEmptyProgress())

let itemSeq = 0

function createEmptyProgress() {
  return {
    items: [],
    repo: '',
    source: '',
    model: '',
    step: 0,
    maxSteps: 0,
    phase: '',
    phaseMessage: '准备分析…',
    startedAt: 0,
  }
}

function pushItem(partial) {
  itemSeq += 1
  progress.value.items.push({
    id: itemSeq,
    kind: 'status',
    title: '',
    summary: '',
    status: '',
    step: 0,
    preview: '',
    at: Date.now(),
    ...partial,
  })
}

/**
 * 更新最近一条「同 step + name + running」的工具条目，否则追加。
 */
function upsertTool(data) {
  const name = data?.name || 'tool'
  const summary = data?.input_summary || ''
  const status = data?.status || 'running'
  const step = data?.step || progress.value.step
  const title = status === 'running' ? `调用工具 ${name}` : `工具 ${name}`

  if (status === 'running') {
    pushItem({
      kind: 'tool',
      title,
      summary,
      status: 'running',
      step,
    })
    return
  }

  // 完成：回填最近一条同名 running
  const items = progress.value.items
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const it = items[i]
    if (
      it.kind === 'tool' &&
      it.status === 'running' &&
      it.step === step &&
      (it.title.includes(name) || it.summary === summary)
    ) {
      it.status = status
      it.title = status === 'ok' ? `工具 ${name} 完成` : `工具 ${name} 失败`
      it.summary = summary
      it.preview = data?.preview || ''
      return
    }
  }
  pushItem({
    kind: 'tool',
    title: status === 'ok' ? `工具 ${name} 完成` : `工具 ${name} 失败`,
    summary,
    status,
    step,
    preview: data?.preview || '',
  })
}

function handleStreamEvent(type, data) {
  if (type === 'start') {
    progress.value.repo = data.repo || ''
    progress.value.source = data.source || ''
    progress.value.model = data.model || ''
    progress.value.maxSteps = data.max_steps || 0
    progress.value.step = 0
    progress.value.phase = 'start'
    progress.value.phaseMessage = 'Agent 已启动，开始多步分析…'
    pushItem({
      kind: 'start',
      title: '已解析仓库',
      summary: `${data.source || ''}: ${data.repo || ''}`,
      status: 'ok',
    })
    return
  }

  if (type === 'step') {
    progress.value.step = data.step || progress.value.step
    progress.value.maxSteps = data.max_steps || progress.value.maxSteps
    progress.value.phase = data.phase || ''
    progress.value.phaseMessage = data.message || progress.value.phaseMessage
    const phaseLabel =
      data.phase === 'llm'
        ? '调用模型'
        : data.phase === 'tools'
          ? '执行工具'
          : data.phase === 'finished'
            ? '整理报告'
            : '步骤更新'
    pushItem({
      kind: 'step',
      title: `步骤 ${data.step || '—'}: ${phaseLabel}`,
      summary: data.message || '',
      status: data.phase === 'finished' ? 'ok' : '',
      step: data.step || 0,
    })
    return
  }

  if (type === 'tool') {
    if (data?.status === 'running') {
      progress.value.phase = 'tools'
      progress.value.phaseMessage = `正在执行 ${data.name || '工具'}…`
    }
    upsertTool(data)
    return
  }

  if (type === 'status') {
    progress.value.phaseMessage = data?.message || progress.value.phaseMessage
    pushItem({
      kind: 'status',
      title: data?.message || '状态更新',
      status: '',
    })
    return
  }

  if (type === 'done') {
    progress.value.phase = 'finished'
    progress.value.phaseMessage = '分析完成'
    progress.value.step = data?.agent_steps || progress.value.step
    if (data?.model) progress.value.model = data.model
    if (data?.repo) progress.value.repo = data.repo
    if (data?.source) progress.value.source = data.source
    pushItem({
      kind: 'status',
      title: '分析完成，报告已生成',
      status: 'ok',
    })
  }
}

onMounted(async () => {
  backendOk.value = await checkHealth()
})

async function onSubmit() {
  if (loading.value) return
  error.value = ''
  report.value = null
  itemSeq = 0
  progress.value = createEmptyProgress()
  progress.value.startedAt = Date.now()
  progress.value.phaseMessage = '正在连接后端并解析仓库…'
  pushItem({
    kind: 'status',
    title: '提交分析请求',
    summary: form.value.repo,
    status: 'running',
  })
  loading.value = true

  try {
    const result = await analyzeRepoStream(
      {
        repo: form.value.repo,
        branch: form.value.branch,
        focus: form.value.focus,
      },
      { onEvent: handleStreamEvent },
    )
    // 将提交中的 running 标记完成
    const first = progress.value.items[0]
    if (first && first.status === 'running') {
      first.status = 'ok'
      first.title = '已提交并建立流式连接'
    }
    report.value = result
  } catch (err) {
    error.value = err?.message || String(err)
    progress.value.phaseMessage = '分析失败'
    pushItem({
      kind: 'status',
      title: '分析中断',
      summary: error.value,
      status: 'error',
    })
  } finally {
    loading.value = false
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
      <AnalyzeForm v-model="form" :loading="loading" @submit="onSubmit" />

      <AnalysisProgress
        v-if="loading"
        :items="progress.items"
        :repo="progress.repo"
        :source="progress.source"
        :model="progress.model"
        :step="progress.step"
        :max-steps="progress.maxSteps"
        :phase="progress.phase"
        :phase-message="progress.phaseMessage"
        :started-at="progress.startedAt"
      />

      <ErrorBanner v-if="error && !loading" :message="error" @dismiss="error = ''" />
      <ReportView v-if="report && !loading" :report="report" />

      <section v-if="!loading && !report && !error" class="card empty">
        <h2 class="card-title">等待分析</h2>
        <p class="empty-hint">
          提交后将通过 <code>POST /analyze/stream</code> 实时展示 Agent 步骤与工具调用。
          也可在 <a href="/docs" target="_blank" rel="noreferrer">/docs</a> 使用 Swagger。
        </p>
      </section>
    </main>

    <footer class="footer">
      <span>MVP：读 + 分析报告 · 过程流式展示 · 非聊天 UI</span>
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
