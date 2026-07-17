<script setup>
import { onMounted, ref } from 'vue'
import { analyzeRepo, checkHealth } from './api/analyze'
import AnalyzeForm from './components/AnalyzeForm.vue'
import LoadingState from './components/LoadingState.vue'
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

onMounted(async () => {
  backendOk.value = await checkHealth()
})

async function onSubmit() {
  if (loading.value) return
  error.value = ''
  report.value = null
  loading.value = true
  try {
    report.value = await analyzeRepo({
      repo: form.value.repo,
      branch: form.value.branch,
      focus: form.value.focus,
    })
  } catch (err) {
    error.value = err?.message || String(err)
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

      <LoadingState v-if="loading" />
      <ErrorBanner v-if="error && !loading" :message="error" @dismiss="error = ''" />
      <ReportView v-if="report && !loading" :report="report" />

      <section v-if="!loading && !report && !error" class="card empty">
        <h2 class="card-title">等待分析</h2>
        <p class="empty-hint">
          提交后将调用 <code>POST /analyze</code>。分析可能较慢（默认最多 12 步 Agent 循环）。
          也可在 <a href="/docs" target="_blank" rel="noreferrer">/docs</a> 使用 Swagger。
        </p>
      </section>
    </main>

    <footer class="footer">
      <span>MVP：读 + 分析报告 · 非聊天 UI</span>
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
