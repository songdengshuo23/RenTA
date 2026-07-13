<template>
  <section class="section">
    <div class="container" :class="{ 'animate-in': showContent }">
      <header class="page-header">
        <div>
          <span class="page-issue">Admin · 审批</span>
          <h1 class="page-title">智能体审批</h1>
          <p class="page-desc">审核用户提交的智能体上架申请,通过后会上架到广场。</p>
        </div>
      </header>

      <LoadingSpinner v-if="loading" text="加载中..." />

      <EmptyState v-else-if="pendingAgents.length === 0" message="暂无待审批的智能体" />

      <div v-else class="agent-list">
        <article v-for="agent in pendingAgents" :key="agent.id" class="agent-card">
          <div class="agent-head">
            <div class="agent-info">
              <div class="agent-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              </div>
              <div class="agent-titles">
                <div class="agent-name">{{ agent.name }}</div>
                <div class="agent-version">v{{ agent.version }}</div>
              </div>
            </div>
            <div class="agent-meta">
              <span class="status-badge pending">{{ statusText(agent.approval_status) }}</span>
              <span class="submit-time">{{ formatTime(agent.created_at) }}</span>
              <button class="detail-link" @click="openAgentDetail(agent.id)">查看详情</button>
            </div>
          </div>

          <div v-if="agent.description" class="agent-desc">{{ agent.description }}</div>

          <div v-if="agent.created_by" class="agent-creator">
            <span class="creator-label">申请人</span>
            <span class="creator-name">{{ agent.created_by.username || agent.created_by.name || '未知' }}</span>
          </div>

          <div class="agent-actions">
            <input v-model="commentMap[agent.id]" class="comment-input" placeholder="审批意见(可选)" />
            <button @click="rejectAgent(agent.id)" class="btn btn-secondary btn-sm" :disabled="processing[agent.id]">
              拒绝
            </button>
            <button
              @click="approveAgent(agent.id)"
              class="btn btn-primary btn-sm"
              :disabled="processing[agent.id] || agent.is_active === false"
              :title="agent.is_active === false ? '历史失效请求只能拒绝' : '批准该智能体'"
            >
              {{ processing[agent.id] ? '处理中…' : '批准' }}
            </button>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'

const showContent = ref(false)
onMounted(() => { nextTick(() => { showContent.value = true }) })
const auth = useAuthStore()
const toast = useToastStore()
const router = useRouter()

const loading = ref(false)
const pendingAgents = ref([])
const processing = ref({})
const commentMap = ref({})

const statusText = (status) => {
  const map = { DRAFT: '草稿', PENDING: '待审批', APPROVED: '已批准', REJECTED: '已拒绝' }
  return map[status] || status
}

const formatTime = (time) => {
  if (!time) return ''
  const d = new Date(time)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

const openAgentDetail = (agentId) => {
  router.push({ name: 'agent-detail', params: { id: agentId }, query: { from: 'approval' } })
}

const fetchPendingAgents = async () => {
 loading.value = true
 try {
 const res = await api.get('/agent/staff', {
 params: {
 statuses: 'PENDING',
 is_disabled: false,
 page_num: 1,
 page_size: 50,
 with_users: true
 }
 })
 // 真后端 AgentListResponse: { items, total, page_num, page_size }
 const items = (res?.items || []).filter(a =>
   a.approval_status === 'PENDING' &&
   a.is_disabled !== true
 )
 pendingAgents.value = items.map(a => ({
 id: a.id,
 name: a.name,
 version: a.version,
 description: a.description || '',
 logo_url: a.logo_url,
 approval_status: a.approval_status,
 aic: a.aic,
 is_active: a.is_active,
 is_deleted: a.is_deleted,
 is_disabled: a.is_disabled,
 created_at: a.created_at,
 submitted_at: a.submitted_at,
 created_by: a.created_by,
 processed_at: a.processed_at,
 process_comments: a.process_comments,
 acs: a.acs
 }))
 } catch (err) {
 toast.error(err.message || '获取待审批智能体失败')
 } finally {
 loading.value = false
 }
}

const approveAgent = async (agentId) => {
  processing.value[agentId] = true
  try {
    const comment = commentMap.value[agentId] || 'approved'
    await api.post(`/agent/staff/${agentId}/process`, {
      approve: true,
      comments: comment
    })
    toast.success('已批准该智能体')
    pendingAgents.value = pendingAgents.value.filter(a => a.id !== agentId)
  } catch (err) {
    toast.error(err.message || '操作失败')
  } finally {
    processing.value[agentId] = false
  }
}

const rejectAgent = async (agentId) => {
  processing.value[agentId] = true
  try {
    const comment = commentMap.value[agentId] || 'rejected'
    await api.post(`/agent/staff/${agentId}/process`, {
      approve: false,
      comments: comment
    })
    toast.success('已拒绝该智能体')
    pendingAgents.value = pendingAgents.value.filter(a => a.id !== agentId)
  } catch (err) {
    toast.error(err.message || '操作失败')
  } finally {
    processing.value[agentId] = false
  }
}

onMounted(() => {
  if (auth.isAdmin) {
    fetchPendingAgents()
  }
})
</script>

<style scoped>
.section { padding: 48px 0 96px; background: var(--bg-page); min-height: 100vh; }
.container { max-width: 900px; margin: 0 auto; padding: 0 32px; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
  margin-bottom: 40px; padding-bottom: 24px;
  border-bottom: 2px solid var(--ink);
}
.page-issue {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--accent-line);
}
.page-title {
  font-family: var(--font-display);
  font-size: clamp(28px, 3.5vw, 36px);
  font-weight: 600; color: var(--ink);
  letter-spacing: -0.025em;
  margin: 12px 0 0;
}
.page-desc { font-size: 14px; color: var(--ink-3); margin: 8px 0 0; }

.agent-list { display: flex; flex-direction: column; gap: 16px; }
.agent-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 24px 28px;
  transition: border-color var(--t-fast);
}
.agent-card:hover { border-color: var(--ink); }
.agent-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-divider);
}
.agent-info { display: flex; align-items: center; gap: 14px; }
.agent-avatar {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  color: var(--ink-2);
}
.agent-name {
  font-family: var(--font-display);
  font-size: 17px; font-weight: 600; color: var(--ink);
  letter-spacing: -0.01em;
}
.agent-version {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3);
  margin-top: 2px;
}
.agent-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.submit-time {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-4);
}
.detail-link {
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
}
.detail-link:hover { text-decoration: underline; }
.agent-desc {
  color: var(--ink-2);
  font-size: 14px; line-height: 1.6;
  margin-bottom: 12px;
  padding: 12px 16px;
  background: var(--bg-card-soft);
  border-radius: var(--r-2);
}
.agent-creator {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}
.creator-label {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
}
.creator-name { font-weight: 600; color: var(--ink); }

.agent-actions { display: flex; gap: 8px; align-items: center; }
.comment-input {
  flex: 1;
  padding: 8px 14px;
  border: 1px solid var(--border-input);
  border-radius: var(--r-2);
  font-size: 13px;
  background: var(--bg-input);
  color: var(--ink);
  outline: none;
  transition: border-color var(--t-fast);
}
.comment-input:focus { border-color: var(--ink); }
</style>
