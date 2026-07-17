<script setup>
defineProps({
  message: {
    type: String,
    default: 'Agent 正在多步工具调用分析仓库，可能需要 1～数分钟，请耐心等待…',
  },
})
</script>

<template>
  <div class="card loading" role="status" aria-live="polite">
    <div class="spinner" aria-hidden="true" />
    <div>
      <h2 class="card-title">分析进行中</h2>
      <p class="msg">{{ message }}</p>
      <p class="sub">请求超时默认 10 分钟；请勿关闭或刷新本页。</p>
    </div>
  </div>
</template>

<style scoped>
.loading {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.spinner {
  width: 28px;
  height: 28px;
  margin-top: 0.15rem;
  border-radius: 50%;
  border: 3px solid #dbeafe;
  border-top-color: var(--primary);
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.msg {
  margin: 0 0 0.35rem;
  color: var(--text);
}

.sub {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.88rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
