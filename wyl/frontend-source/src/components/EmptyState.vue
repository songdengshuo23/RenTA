<template>
  <div class="empty-state">
    <div class="empty-illustration" v-if="$slots.icon || icon">
      <slot name="icon">
        <svg v-if="icon" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      </slot>
    </div>
    <p class="empty-message">{{ message }}</p>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '暂无内容' },
  description: { type: String, default: '' },
  icon: { type: Boolean, default: false }
})
</script>

<style scoped>
.empty-state {
  text-align: center;
  color: var(--ink-3);
  padding: 64px 24px;
  background: var(--bg-card-soft);
  border: 1px dashed var(--border-card);
  border-radius: var(--r-3);
}
.empty-illustration {
  width: 56px; height: 56px;
  margin: 0 auto 20px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 50%;
  color: var(--ink-3);
}
.empty-message {
  font-family: var(--font-display);
  font-size: 15px; font-weight: 500;
  color: var(--ink-2);
  margin: 0 0 6px;
}
.empty-desc {
  font-size: 13px;
  color: var(--ink-3);
  margin: 0 0 16px;
}
.empty-actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
</style>
