<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  analyzeRepoStream,
  checkHealth,
  listAnalysisModels,
} from './api/analyze'
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
  repo: './',
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

const sidebarTab = ref('form') // 'form' | 'history'
const sidebarCollapsed = ref(false)
const showFixDrawer = ref(false)

function selectPreset(repoPath) {
  form.value.repo = repoPath
  sidebarTab.value = 'form'
  sidebarCollapsed.value = false
}

function resetView() {
  selectedId.value = ''
  report.value = null
  fixProposal.value = null
  error.value = ''
  fixError.value = ''
  bindProgress(createEmptyProgress())
  progressState.itemSeq = 0
  sidebarTab.value = 'form'
  sidebarCollapsed.value = false
}

/** 里程碑阶段推导 (1~4) */
const currentStage = computed(() => {
  if (fixLoading.value || fixProposal.value) return 4
  if (report.value) return 3
  if (loading.value) {
    if ((progress.value.step || 0) > 1) return 2
    return 1
  }
  return 0
})

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
  localStorage.removeItem('agent-theme')
  document.documentElement.removeAttribute('data-theme')
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
  showFixDrawer.value = false

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
  showFixDrawer.value = false
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
  showFixDrawer.value = true

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
  <div class="app-container">
    <!-- 顶部全景导航栏 -->
    <header class="top-nav">
      <div class="nav-left">
        <button
          type="button"
          class="sidebar-toggle-btn"
          :title="sidebarCollapsed ? '展开控制台侧边栏' : '折叠侧边栏'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <span class="icon">▤</span>
        </button>

        <div class="brand" @click="resetView">
          <div class="brand-logo">
            <span>CA</span>
          </div>
          <div class="brand-text">
            <h1 class="brand-title">Code Assistant Agent</h1>
            <span class="brand-badge">ReAct Loop</span>
          </div>
        </div>

        <div class="backend-status-pill" :class="backendOk === false ? 'down' : ''">
          <span class="pulse-dot" v-if="backendOk" />
          <span class="dot-down" v-else-if="backendOk === false" />
          <template v-if="backendOk === null">检测服务中…</template>
          <template v-else-if="backendOk">服务就绪 :8000</template>
          <template v-else>后端未启动</template>
        </div>
      </div>

      <div class="nav-right">
        <button
          type="button"
          class="nav-action-btn"
          @click="resetView"
          title="清空当前画布并回到初始配置"
        >
          <span>+ 新建分析</span>
        </button>
        <a href="/docs" target="_blank" rel="noreferrer" class="nav-link" title="OpenAPI Swagger 文档">
          <span class="nav-link-icon">📑</span>
          <span>API 接口</span>
        </a>
      </div>
    </header>

    <!-- 阶段演进流水线 (Pipeline Banner) -->
    <nav
      v-if="currentStage > 0"
      class="mission-pipeline"
      aria-label="Agent 执行闭环阶段"
    >
      <div class="pipeline-track">
        <div class="pipeline-step" :class="{ done: currentStage > 1, active: currentStage === 1 }">
          <div class="step-num">1</div>
          <div class="step-info">
            <span class="step-title">挂载仓库</span>
            <span class="step-sub">{{ form.repo ? '目标已设定' : '等待解析' }}</span>
          </div>
        </div>

        <div class="pipeline-arrow">➔</div>

        <div class="pipeline-step" :class="{ done: currentStage > 2, active: currentStage === 2 }">
          <div class="step-num">2</div>
          <div class="step-info">
            <span class="step-title">结构与工具探索</span>
            <span class="step-sub">{{ progress.step ? `${progress.step} 轮调用` : 'ReAct 循环' }}</span>
          </div>
        </div>

        <div class="pipeline-arrow">➔</div>

        <div class="pipeline-step" :class="{ done: currentStage > 3, active: currentStage === 3 }">
          <div class="step-num">3</div>
          <div class="step-info">
            <span class="step-title">风险与缺陷审计</span>
            <span class="step-sub">{{ report ? `${(report.bugs?.length || 0)} Bug · ${(report.risks?.length || 0)} 风险` : '深度分析' }}</span>
          </div>
        </div>

        <div class="pipeline-arrow">➔</div>

        <div class="pipeline-step" :class="{ done: fixProposal?.applied, active: currentStage === 4 }">
          <div class="step-num">4</div>
          <div class="step-info">
            <span class="step-title">闭环修复提案</span>
            <span class="step-sub">{{ fixProposal ? 'Diff 补丁就绪' : '一键生成' }}</span>
          </div>
        </div>
      </div>
    </nav>

    <!-- 错误横幅提示 -->
    <div v-if="error || fixError" class="error-container">
      <ErrorBanner v-if="error && !loading" :message="error" @dismiss="error = ''" />
      <ErrorBanner v-if="fixError && !fixLoading" :message="fixError" @dismiss="fixError = ''" />
    </div>

    <!-- 主工作区分栏 -->
    <main class="workbench-layout" :class="{ 'sidebar-hidden': sidebarCollapsed, 'drawer-open': showFixDrawer || fixProposal }">
      <!-- 左侧边栏：分析配置与历史管理 -->
      <aside class="sidebar-panel">
        <div class="sidebar-tabs">
          <button
            type="button"
            class="tab-btn"
            :class="{ active: sidebarTab === 'form' }"
            @click="sidebarTab = 'form'"
          >
            <span>开始分析</span>
          </button>
          <button
            type="button"
            class="tab-btn"
            :class="{ active: sidebarTab === 'history' }"
            @click="sidebarTab = 'history'"
          >
            <span>分析记录</span>
            <span class="tab-count" v-if="runs.length">{{ runs.length }}</span>
          </button>
        </div>

        <div class="sidebar-content">
          <!-- 快捷预设提示条 -->
          <div v-if="sidebarTab === 'form'" class="presets-bar">
            <span class="presets-label">快捷填充:</span>
            <button type="button" class="preset-pill" @click="selectPreset('./')">
              ./ 本地当前
            </button>
            <button type="button" class="preset-pill" @click="selectPreset('fastapi/fastapi')">
              fastapi
            </button>
            <button type="button" class="preset-pill" @click="selectPreset('pallets/flask')">
              flask
            </button>
          </div>

          <div v-show="sidebarTab === 'form'" class="form-wrapper">
            <AnalyzeForm
              v-model="form"
              :loading="loading"
              :models="catalogModels"
              :price-disclaimer="catalogDisclaimer"
              @submit="onSubmit"
            />
          </div>

          <div v-show="sidebarTab === 'history'" class="history-wrapper">
            <AnalysisHistory
              :runs="runs"
              :selected-id="selectedId"
              :loading="historyLoading"
              @select="onSelectRun"
              @delete="onDeleteRun"
            />
          </div>
        </div>
      </aside>

      <!-- 中间核心工作区 (Main Canvas) -->
      <section class="main-canvas">
        <!-- 实时执行流状态条与时间线 -->
        <AnalysisProgress
          v-if="loading || (progress.items.length && !report)"
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

        <!-- 完整报告展示 -->
        <ReportView
          v-if="report && !loading"
          :report="report"
          :fixing-index="fixingIndex"
          @propose-fix="onProposeFix"
        />

        <!-- 初始空状态 -->
        <div v-if="!loading && !report && !error && !progress.items.length" class="empty-workbench">
          <div class="empty-hero">
            <div class="empty-icon-ring">
              <span class="icon">⚡</span>
            </div>
            <h2 class="empty-title">欢迎使用 Code Assistant Agent</h2>
            <p class="empty-desc">
              输入本地或 GitHub 仓库地址，Agent 将利用自动化工具调用闭环深度探索架构并生成结构化诊断报告。
            </p>

            <div class="quick-actions-grid">
              <div class="quick-card" @click="selectPreset('./')">
                <div class="card-icon">📂</div>
                <div class="card-text">
                  <span class="card-action">分析当前项目 (./)</span>
                  <span class="card-detail">快速对本仓库执行架构扫描与代码审计</span>
                </div>
              </div>
              <div class="quick-card" @click="selectPreset('fastapi/fastapi')">
                <div class="card-icon">🐙</div>
                <div class="card-text">
                  <span class="card-action">分析 FastAPI 示例</span>
                  <span class="card-detail">体验远端 GitHub 仓库克隆与自动化审计</span>
                </div>
              </div>
              <div class="quick-card" @click="sidebarTab = 'form'">
                <div class="card-icon">⚙️</div>
                <div class="card-text">
                  <span class="card-action">自定义模型与侧重点</span>
                  <span class="card-detail">支持 Qwen3-8B 免费模型及安全/Bug专项分析</span>
                </div>
              </div>
              <div class="quick-card" @click="sidebarTab = 'history'" v-if="runs.length">
                <div class="card-icon">🕒</div>
                <div class="card-text">
                  <span class="card-action">查看历史记录 ({{ runs.length }})</span>
                  <span class="card-detail">回放过往运行的工具调用轨迹与报告</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 右侧 / 浮动抽屉：Fix 修复与 Diff 审阅器 -->
      <aside
        v-if="fixLoading || fixProposal || showFixDrawer"
        class="fix-drawer-panel"
        id="fix-preview"
      >
        <FixPreviewPanel
          :proposal="fixProposal"
          :loading="fixLoading"
          :progress-message="fixProgressMsg"
          @close="showFixDrawer = false; fixProposal = null; fixLoading = false"
          @applied="onFixApplied"
          @pr-opened="onPrOpened"
          @error="(m) => (fixError = m)"
        />
      </aside>
    </main>

    <!-- 底部状态条 -->
    <footer class="app-status-bar">
      <div class="status-item">
        <span class="status-dot"></span>
        <span>ReAct Tool Loop · 自动化架构探索与审计</span>
      </div>
      <div class="status-item">
        <span class="status-badge-clean">纯净亮色工作台</span>
      </div>
      <div class="status-item ml-auto">
        <span>模式: 先审后写 · 闭环修复 (本地 Apply / GitHub PR)</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
}

/* ================= 顶栏 Navigation ================= */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 1.25rem;
  background: var(--surface-glass);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 40;
}

.nav-left, .nav-right {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.sidebar-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 1.1rem;
  transition: all 0.15s;
}

.sidebar-toggle-btn:hover {
  color: var(--primary);
  border-color: var(--primary);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  cursor: pointer;
  user-select: none;
}

.brand-logo {
  width: 2rem;
  height: 2rem;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 0.85rem;
  box-shadow: 0 2px 10px var(--primary-soft);
}

.brand-text {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.brand-title {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--text);
}

.brand-badge {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
  border: 1px solid var(--border);
}

.backend-status-pill {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  color: var(--text-muted);
}

.backend-status-pill.down {
  border-color: var(--danger-border);
  color: var(--danger);
  background: var(--danger-soft);
}

.dot-down {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--danger);
}

.nav-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.85rem;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #ffffff;
  border: 1px solid var(--primary);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.2);
}

.nav-action-btn:hover {
  background: var(--primary-hover);
  box-shadow: 0 2px 8px var(--primary-glow);
  transform: translateY(-1px);
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-muted);
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  transition: all 0.15s ease-in-out;
}

.nav-link:hover {
  color: var(--primary);
  border-color: var(--border-hover);
  background: var(--surface-hover);
  text-decoration: none;
}

.nav-link-icon {
  font-size: 0.85rem;
}

/* ================= 任务阶段 Pipeline ================= */
.mission-pipeline {
  background: var(--surface-subtle);
  border-bottom: 1px solid var(--border);
  padding: 0.5rem 1.25rem;
}

.pipeline-track {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1100px;
  margin: 0 auto;
  gap: 0.5rem;
  overflow-x: auto;
}

.pipeline-step {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  opacity: 0.5;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.pipeline-step.active, .pipeline-step.done {
  opacity: 1;
}

.step-num {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
}

.pipeline-step.active .step-num {
  border-color: var(--primary);
  background: var(--primary);
  color: #fff;
  box-shadow: 0 0 10px var(--primary-glow);
}

.pipeline-step.done .step-num {
  border-color: var(--low);
  background: var(--low-bg);
  color: var(--low);
}

.step-info {
  display: flex;
  flex-direction: column;
}

.step-title {
  font-size: 0.78rem;
  font-weight: 650;
  color: var(--text);
}

.step-sub {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.pipeline-arrow {
  color: var(--text-dim);
  font-size: 0.8rem;
  user-select: none;
}

.error-container {
  padding: 0.75rem 1.25rem 0;
  max-width: 1300px;
  margin: 0 auto;
  width: 100%;
}

/* ================= 核心工作区分栏布局 ================= */
.workbench-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  transition: grid-template-columns 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.workbench-layout.sidebar-hidden {
  grid-template-columns: 0 minmax(0, 1fr);
}

.workbench-layout.drawer-open {
  grid-template-columns: 340px minmax(0, 1fr) 480px;
}

.workbench-layout.sidebar-hidden.drawer-open {
  grid-template-columns: 0 minmax(0, 1fr) 520px;
}

/* 左侧边栏 */
.sidebar-panel {
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.sidebar-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--surface-subtle);
}

.tab-btn {
  flex: 1;
  padding: 0.65rem 0.5rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: var(--text);
}

.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  background: var(--surface);
}

.tab-count {
  font-size: 0.7rem;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  padding: 0 0.4rem;
  border-radius: 999px;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 0.85rem;
}

.presets-bar {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
  font-size: 0.75rem;
}

.presets-label {
  color: var(--text-dim);
}

.preset-pill {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  color: var(--primary);
  font-family: var(--mono);
  font-size: 0.72rem;
  transition: all 0.15s;
}

.preset-pill:hover {
  background: var(--primary-soft);
  border-color: var(--primary);
}

/* 中间主画布 */
.main-canvas {
  padding: 1.25rem 1.5rem 2.5rem;
  overflow-y: auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* 右侧 Diff 抽屉 */
.fix-drawer-panel {
  background: var(--surface);
  border-left: 1px solid var(--border);
  overflow-y: auto;
  padding: 1rem;
  box-shadow: -4px 0 24px rgba(15, 23, 42, 0.08);
  z-index: 20;
}

/* ================= 初始空状态设计 ================= */
.empty-workbench {
  margin: auto;
  max-width: 680px;
  padding: 2.5rem 1rem;
  text-align: center;
}

.empty-icon-ring {
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  background: var(--primary-soft);
  border: 1px solid var(--border-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  margin: 0 auto 1rem;
  color: var(--primary);
}

.empty-title {
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 0.5rem;
}

.empty-desc {
  font-size: 0.92rem;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0 0 1.75rem;
}

.quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.85rem;
  text-align: left;
}

.quick-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  gap: 0.75rem;
}

.quick-card:hover {
  border-color: var(--primary);
  background: var(--surface-hover);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.06);
}

.card-icon {
  font-size: 1.3rem;
  flex-shrink: 0;
}

.card-text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.card-action {
  font-weight: 650;
  font-size: 0.88rem;
  color: var(--text);
}

.card-detail {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* ================= 底部状态条 ================= */
.app-status-bar {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 0.35rem 1.25rem;
  background: var(--surface-subtle);
  border-top: 1px solid var(--border);
  font-size: 0.75rem;
  color: var(--text-dim);
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
}

.status-badge-clean {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--primary-soft);
  color: var(--primary);
  border: 1px solid rgba(37, 99, 235, 0.2);
}

.ml-auto {
  margin-left: auto;
}

/* 响应式调整 */
@media (max-width: 1024px) {
  .workbench-layout {
    grid-template-columns: 300px minmax(0, 1fr);
  }
  .workbench-layout.drawer-open {
    grid-template-columns: 0 minmax(0, 1fr) 440px;
  }
}

@media (max-width: 768px) {
  .top-nav {
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .workbench-layout {
    display: flex;
    flex-direction: column;
  }
  .sidebar-panel {
    border-right: none;
    border-bottom: 1px solid var(--border);
    max-height: 420px;
  }
}
</style>

