<template>
  <div class="key-box">
    <div class="key-label">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
      </svg>
      {{ label }}
    </div>
    <div class="key-value">{{ value }}</div>
    <button @click="copy" class="btn btn-secondary btn-sm">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
      {{ copied ? '已复制' : copyText }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  value: { type: String, default: '' },
  label: { type: String, default: 'API 密钥' },
  copyText: { type: String, default: '复制密钥' }
})

const toast = useToastStore()
const copied = ref(false)

const copy = async () => {
  try {
    await navigator.clipboard.writeText(props.value)
    copied.value = true
    toast.success('已复制到剪贴板')
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    toast.error('复制失败')
  }
}
</script>

<style scoped>
.key-box {
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  padding: 16px;
  margin: 12px 0;
}
.key-label {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ink-3);
  margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.key-value {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--ink);
  word-break: break-all;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  margin-bottom: 12px;
  letter-spacing: 0.02em;
}
</style>
