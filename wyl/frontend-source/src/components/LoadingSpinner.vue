<template>
  <div class="loading-state">
    <div class="spinner"></div>
    <span>{{ text }}</span>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '加载中…' }
})
</script>

<style scoped>
.loading-state {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 48px;
  color: var(--ink-3);
  font-size: 13px;
}
.spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--border-card);
  border-top-color: var(--ink);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
