<script setup>
defineProps({
  message: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['dismiss'])
</script>

<template>
  <div class="card error" role="alert">
    <div class="body">
      <strong>分析失败</strong>
      <p>{{ message }}</p>
    </div>
    <button type="button" class="close" aria-label="关闭" @click="emit('dismiss')">×</button>
  </div>
</template>

<style scoped>
.error {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  background: var(--danger-soft);
  border-color: #fecaca;
}

.body {
  min-width: 0;
}

strong {
  display: block;
  color: var(--danger);
  margin-bottom: 0.25rem;
}

p {
  margin: 0;
  color: #7f1d1d;
  word-break: break-word;
}

.close {
  border: none;
  background: transparent;
  color: #991b1b;
  font-size: 1.4rem;
  line-height: 1;
  padding: 0 0.25rem;
}
</style>
