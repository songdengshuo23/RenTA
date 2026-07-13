<template>
  <div class="agent-log" ref="logRef">
    <div class="log-header">
      <span class="log-title">Agent 协同日志</span>
      <span class="log-count" v-if="messages.length">{{ messages.length }} 条</span>
    </div>
    <div class="log-body" ref="bodyRef">
      <div v-if="messages.length === 0" class="log-empty">
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>暂无协同记录,发送消息后展示各 Agent 的思考和调度</span>
      </div>
      <div
        v-for="msg in messages" :key="msg.id"
        class="log-item"
        :class="['log-' + (msg.type || 'info'), { 'is-expanded': isExpanded(msg.id), 'is-long': isLong(msg.text) }]"
        @click="toggle(msg.id)"
        @keydown.enter.prevent="toggle(msg.id)"
        @keydown.space.prevent="toggle(msg.id)"
        :tabindex="isLong(msg.text) ? 0 : -1"
        :role="isLong(msg.text) ? 'button' : undefined"
        :aria-expanded="isLong(msg.text) ? isExpanded(msg.id) : undefined"
      >
        <span class="log-dot" :style="{ background: msg.color || '#888' }"></span>
        <span class="log-agent">{{ msg.agent }}</span>
        <span class="log-text" :title="isLong(msg.text) ? '点击展开/收起完整内容' : ''">{{ msg.text }}</span>
        <span class="log-time">{{ msg.time }}</span>
        <span v-if="isLong(msg.text)" class="log-chevron" :class="{ open: isExpanded(msg.id) }">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
})

const bodyRef = ref(null)
// 展开状态:存已展开的 msg.id —— Set 查找 O(1),新消息进来默认折叠
const expandedIds = ref(new Set())

const isExpanded = (id) => expandedIds.value.has(id)
// 文本超过 60 字符或包含换行符 → 可展开
const isLong = (text) => {
  if (!text) return false
  return text.length > 60 || text.includes('\n')
}

const toggle = (id) => {
  if (!isLong(props.messages.find(m => m.id === id)?.text)) return
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

// 消息列表变化时,清理已不存在的 id 防止内存泄漏
watch(() => props.messages.map(m => m.id).join(','), () => {
  const live = new Set(props.messages.map(m => m.id))
  const cleaned = new Set([...expandedIds.value].filter(id => live.has(id)))
  if (cleaned.size !== expandedIds.value.size) expandedIds.value = cleaned
  nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  })
})
</script>

<style scoped>
.agent-log {
  display: flex; flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  overflow: hidden;
  flex: 1; min-height: 0;
}
.log-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-divider);
  flex-shrink: 0;
}
.log-title {
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ink-2);
}
.log-count {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em;
  color: var(--ink-3);
  background: var(--bg-card-soft);
  padding: 2px 8px;
  border-radius: var(--r-1);
}
.log-body { flex: 1; overflow-y: auto; padding: 8px 12px; }
.log-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; height: 100%;
  color: var(--ink-4);
  font-size: 12px; text-align: center;
  padding: 20px;
}
.log-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  border-radius: var(--r-1);
  margin-bottom: 2px;
  font-size: 12px; line-height: 1.5;
  transition: background var(--t-fast);
  cursor: default;
  border-left: 2px solid transparent;
}
.log-item.is-long { cursor: pointer; }
.log-item.is-long:hover { background: var(--bg-card-soft); }
.log-item.is-long:focus-visible {
  outline: 2px solid var(--accent-blue, #4a8db5);
  outline-offset: -2px;
}
.log-item.is-expanded {
  flex-wrap: wrap;
  align-items: flex-start;
  background: var(--bg-card-soft);
  border-left-color: var(--accent-blue, #4a8db5);
  cursor: pointer;
}
.log-item.is-expanded .log-text {
  white-space: pre-wrap;
  word-break: break-word;
  overflow: visible;
  text-overflow: clip;
  flex-basis: 100%;
  margin-top: 4px;
  max-height: 320px;
  overflow-y: auto;
}
.log-item.log-action { background: var(--accent-soft); }
.log-item.log-result { background: var(--signal-positive-soft); }
.log-item.log-error  { background: var(--signal-negative-soft); }
/* 展开后保留各自语义背景 */
.log-item.log-action.is-expanded,
.log-item.log-result.is-expanded,
.log-item.log-error.is-expanded { background: var(--bg-card-soft); }

.log-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
  margin-top: 1px;  /* 跟文字基线对齐 */
}
.log-agent {
  font-weight: 600; color: var(--ink-2);
  white-space: nowrap; flex-shrink: 0;
  margin-top: 1px;
}
.log-text {
  color: var(--ink-3);
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
.log-time {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-4);
  flex-shrink: 0;
  margin-top: 1px;
}
.log-chevron {
  flex-shrink: 0;
  display: inline-flex;
  color: var(--ink-4);
  transition: transform var(--t-fast, 0.15s);
  margin-top: 2px;
}
.log-chevron.open { transform: rotate(180deg); color: var(--accent-blue, #4a8db5); }
</style>
