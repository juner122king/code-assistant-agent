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
})

const emit = defineEmits(['update:modelValue', 'submit'])

const canSubmit = computed(() => Boolean(String(props.modelValue?.repo || '').trim()))

function updateField(key, event) {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: event.target.value,
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
        <span class="label">分支（可选）</span>
        <input
          type="text"
          :disabled="loading"
          :value="modelValue.branch"
          placeholder="默认分支留空"
          @input="updateField('branch', $event)"
        />
      </label>

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
    </div>

    <div class="actions">
      <button class="btn-primary" type="submit" :disabled="loading || !canSubmit">
        {{ loading ? '分析中…' : '开始分析' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.form-hint {
  margin: -0.35rem 0 1rem;
  color: var(--text-muted);
  font-size: 0.92rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.9rem;
}

.label {
  font-size: 0.88rem;
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
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

input:focus,
select:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

input:disabled,
select:disabled {
  opacity: 0.7;
  background: #f8fafc;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem 1rem;
}

.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.25rem;
}

.btn-primary {
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-weight: 600;
  padding: 0.65rem 1.25rem;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 640px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
