<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  models: {
    type: Array,
    default: () => [],
  },
  priceDisclaimer: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'submit'])

const canSubmit = computed(() => Boolean(String(props.modelValue?.repo || '').trim()))

const freeModels = computed(() => (props.models || []).filter((m) => m.tier === 'free'))
const paidModels = computed(() => (props.models || []).filter((m) => m.tier !== 'free'))
const selectedModel = computed(() => {
  const id = props.modelValue?.model
  return (props.models || []).find((m) => m.id === id) || null
})

function priceLabel(m) {
  if (!m) return ''
  if (m.tier === 'free' || (m.input_cny_per_m === 0 && m.output_cny_per_m === 0)) {
    return '¥0'
  }
  return `¥${m.input_cny_per_m}/${m.output_cny_per_m}`
}

function valueLabel(v) {
  if (v === 'high') return '高'
  if (v === 'medium') return '中'
  if (v === 'low') return '低'
  return v || '—'
}

function optionLabel(m) {
  const price = m.tier === 'free' ? '免费' : priceLabel(m)
  return `${m.id}（${price}）`
}

function updateField(key, event) {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: event.target.value,
  })
}

function updateMaxSteps(event) {
  const raw = event.target.value
  let n = parseInt(raw, 10)
  if (!Number.isFinite(n)) n = 8
  if (n < 1) n = 1
  if (n > 40) n = 40
  emit('update:modelValue', {
    ...props.modelValue,
    max_steps: n,
  })
}

function onSubmit(event) {
  event.preventDefault()
  if (props.loading || !canSubmit.value) return
  emit('submit')
}
</script>

<template>
  <form class="card form" @submit="onSubmit">
    <h2 class="card-title">开始分析</h2>
    <p class="form-hint">
      输入<strong>运行后端机器上</strong>的本地仓库路径，或 GitHub 仓库 URL。Agent 会通过工具调用读取仓库并生成报告。
    </p>

    <label class="field">
      <span class="label">仓库 <em>*</em></span>
      <input
        type="text"
        required
        :disabled="loading"
        :value="modelValue.repo"
        placeholder="例如：/path/to/repo 或 https://github.com/owner/repo"
        @input="updateField('repo', $event)"
      />
    </label>

    <div class="row">
      <label class="field">
        <span class="label">分析侧重点</span>
        <select
          :disabled="loading"
          :value="modelValue.focus"
          @change="updateField('focus', $event)"
        >
          <option value="general">综合（general）</option>
          <option value="security">安全（security）</option>
          <option value="bugs">Bug（bugs）</option>
        </select>
      </label>

      <label class="field">
        <span class="label">模型</span>
        <select
          :disabled="loading"
          :value="modelValue.model || 'Qwen/Qwen3-8B'"
          @change="updateField('model', $event)"
        >
          <optgroup v-if="freeModels.length" label="免费">
            <option v-for="m in freeModels" :key="m.id" :value="m.id">
              {{ optionLabel(m) }}
            </option>
          </optgroup>
          <optgroup v-if="paidModels.length" label="付费">
            <option v-for="m in paidModels" :key="m.id" :value="m.id">
              {{ optionLabel(m) }}
            </option>
          </optgroup>
        </select>
      </label>
    </div>
    <p v-if="selectedModel" class="steps-hint">{{ selectedModel.note }}</p>

    <details class="model-table">
      <summary>适合代码分析的模型与性价比</summary>
      <table>
        <thead>
          <tr>
            <th>模型</th>
            <th>档</th>
            <th>上下文</th>
            <th>输入/输出</th>
            <th>性价比</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in models" :key="m.id">
            <td>
              <code>{{ m.id }}</code>
              <div class="mini">{{ m.label }}</div>
            </td>
            <td>{{ m.tier === 'free' ? '免费' : '付费' }}</td>
            <td>{{ m.context }}</td>
            <td>{{ priceLabel(m) }}</td>
            <td>{{ valueLabel(m.value) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="steps-hint">
        常用参数：max_steps=8，中间步 max_tokens=1024，收束 4096，enable_thinking=false。
        {{ priceDisclaimer }}
      </p>
    </details>

    <label class="field">
      <span class="label">最大步数</span>
      <div class="steps-row">
        <input
          type="number"
          min="1"
          max="40"
          step="1"
          :disabled="loading"
          :value="modelValue.max_steps ?? 8"
          @input="updateMaxSteps"
        />
        <span class="steps-hint">Agent 工具调用轮次上限（1–40）。越大越慢、越费 token；小仓库 6–8 步通常够用。</span>
      </div>
    </label>

    <div class="actions">
      <button class="btn-primary" type="submit" :disabled="loading || !canSubmit">
        {{ loading ? '分析中…' : '开始分析' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.form {
  padding: 1.15rem 1.1rem;
}

.form-hint {
  margin: -0.35rem 0 0.95rem;
  color: var(--text-muted);
  font-size: 0.84rem;
  line-height: 1.45;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
}

.label {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.25rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text);
}

.label em {
  color: var(--danger);
  font-style: normal;
}

input,
select {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
  color: var(--text);
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

input:focus,
select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

input:disabled,
select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem 0.75rem;
}

.steps-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
}

.steps-row input[type='number'] {
  width: 5.5rem;
  flex-shrink: 0;
}

.steps-hint {
  flex: 1;
  min-width: 10rem;
  font-size: 0.76rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.4rem;
}

.btn-primary {
  width: 100%;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-weight: 600;
  font-size: 0.88rem;
  padding: 0.65rem 1.1rem;
  box-shadow: 0 2px 10px var(--primary-glow);
  transition: background 0.15s, transform 0.1s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.model-table {
  margin: 0 0 0.85rem;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.model-table summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 0.45rem;
  transition: color 0.15s;
}

.model-table summary:hover {
  color: var(--text);
}

.model-table table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.model-table th,
.model-table td {
  text-align: left;
  padding: 0.35rem 0.45rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  font-size: 0.75rem;
}

.model-table th {
  color: var(--text-dim);
  font-weight: 600;
}

.model-table code {
  font-size: 0.72rem;
  color: var(--primary);
}

.model-table .mini {
  color: var(--text-dim);
  font-size: 0.7rem;
}

@media (max-width: 640px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
