<template>
  <section class="section">
    <div class="container" :class="{ 'animate-in': showContent }">
      <header class="page-header">
        <div>
          <span class="page-issue">Account · 账户</span>
          <h1 class="page-title">账户管理</h1>
          <p class="page-desc">查看账户信息、个人资料与账户安全。</p>
        </div>
      </header>

      <EmptyState v-if="!auth.isLoggedIn" message="请先登录以管理账户">
        <router-link to="/auth" class="btn btn-primary">登录 / 注册</router-link>
      </EmptyState>

      <template v-else>
        <!-- ===== 顶部统计条 (跨 tab 共享) ===== -->
        <div class="stats-row anim-item anim-1">
          <div class="stat-card stat-balance">
            <span class="stat-k">USER ID</span>
            <span class="stat-v num stat-id">{{ auth.user.user_id?.slice(0,8) || '—' }}</span>
            <span class="stat-u">身份: {{ auth.isAdmin ? '管理员' : (auth.user.roles?.[0] || 'USER') }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-k">我创建的</span>
            <span class="stat-v num">{{ myAgentCount }}</span>
            <span class="stat-u">个智能体</span>
          </div>
          <div class="stat-card">
            <span class="stat-k">收藏的智能体</span>
            <span class="stat-v num">{{ favoriteCount }}</span>
            <span class="stat-u">个</span>
          </div>
          <div class="stat-card">
            <span class="stat-k">今日调用</span>
            <span class="stat-v num">{{ todayCallCount }}</span>
            <span class="stat-u">次</span>
          </div>
        </div>

        <!-- ===== Tab 切换 ===== -->
        <nav class="account-tabs anim-item anim-2" role="tablist">
          <button
            v-for="t in tabs"
            :key="t.key"
            type="button"
            role="tab"
            class="account-tab"
            :class="{ active: activeTab === t.key }"
            :aria-selected="activeTab === t.key"
            @click="switchTab(t.key)"
          >
            <span class="tab-label">{{ t.label }}</span>
            <span class="tab-hint">{{ t.hint }}</span>
          </button>
        </nav>

        <!-- ===== Tab: 资料 ===== -->
        <div v-if="activeTab === 'profile'" class="tab-pane" :key="activeTab">
          <div class="card profile-card">
            <div class="card-head-row">
              <h2 class="card-title">个人资料</h2>
              <span class="status-badge" :class="auth.isAdmin ? 'approved' : 'neutral'">
                {{ auth.isAdmin ? '管理员' : '普通用户' }}
              </span>
            </div>

            <div class="profile-section">
              <div class="avatar-wrap" @click="triggerAvatarInput" title="点击更换头像">
                <img v-if="auth.user.avatar" :src="`/api/file/${auth.user.avatar}`" class="avatar-img" />
                <span v-else class="avatar-initial">{{ (auth.user.username || 'U').slice(0,1).toUpperCase() }}</span>
                <div class="avatar-overlay">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                </div>
              </div>
              <input ref="avatarInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml" @change="onAvatarChange" style="display:none" />

              <div class="profile-meta">
                <h3 class="profile-name">{{ auth.user.username }}</h3>
                <div class="profile-id">
                  <span class="id-label">USER ID</span>
                  <span class="id-value">{{ auth.user.user_id }}</span>
                </div>
              </div>
            </div>

            <div class="info-list">
              <div class="info-item">
                <span class="info-label">用户名</span>
                <span class="info-value">{{ auth.user.username }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">账户 ID</span>
                <span class="info-value num">{{ auth.user.user_id }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">注册时间</span>
                <span class="info-value">{{ registerTime }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">身份</span>
                <span class="info-value">{{ auth.isAdmin ? '管理员' : '普通用户' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">账户状态</span>
                <span class="info-value">
                  <span class="status-dot" :class="accountStatus.active ? 'on' : 'off'"></span>
                  {{ accountStatus.label }}
                </span>
              </div>
            </div>

            <div class="profile-actions">
              <button v-if="!auth.isAdmin" class="btn btn-secondary" @click="switchTab('billing')">充值 / 提现</button>
              <button @click="handleLogout" class="btn btn-ghost btn-logout">退出登录</button>
            </div>
          </div>
        </div>

        <!-- ===== Tab: 积分与流水 (内嵌 BillingView) ===== -->
        <div v-else-if="activeTab === 'billing'" class="tab-pane" :key="activeTab">
          <BillingPanel />
        </div>

        <!-- ===== Tab: 安全 ===== -->
        <div v-else-if="activeTab === 'security'" class="tab-pane" :key="activeTab">
          <div class="card pwd-card">
            <h2 class="card-title">修改密码</h2>
            <p class="card-desc">定期更换密码可保护你的账户安全。</p>

            <form @submit.prevent="changePassword" class="pwd-form">
              <div class="field">
                <label>原密码</label>
                <input type="password" v-model="passwordForm.old_password" placeholder="输入当前密码" required />
              </div>
              <div class="field">
                <label>新密码</label>
                <input type="password" v-model="passwordForm.new_password" placeholder="至少 6 位" required />
              </div>
              <div class="field">
                <label>确认新密码</label>
                <input type="password" v-model="passwordForm.confirm_password" placeholder="再次输入新密码" required />
              </div>

              <div class="pwd-strength" v-if="passwordForm.new_password">
                <span class="strength-bar" :class="strengthClass"></span>
                <span class="strength-text">{{ strengthText }}</span>
              </div>

              <button type="submit" class="btn btn-primary btn-block" :disabled="changing">
                <span v-if="changing" class="spinner-sm"></span>
                {{ changing ? '修改中…' : '更新密码' }}
              </button>

              <p v-if="pwdMessage" :class="['form-msg', pwdMsgType]">{{ pwdMessage }}</p>
            </form>

            <!-- 安全建议 -->
            <div class="security-tips">
              <span class="tips-label">安全建议</span>
              <ul>
                <li>密码长度 ≥ 8 位,包含数字与字母</li>
                <li>不要在多个网站使用相同密码</li>
                <li>定期更换密码以降低泄露风险</li>
              </ul>
            </div>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import EmptyState from '@/components/EmptyState.vue'
import BillingPanel from '@/components/BillingPanel.vue'

const showContent = ref(false)

// ===== Tab 状态 (从 URL ?tab= 同步) =====
const route = useRoute()
const router = useRouter()
const VALID_TABS = ['profile', 'billing', 'security']
const activeTab = ref(VALID_TABS.includes(route.query.tab) ? route.query.tab : 'profile')
const switchTab = (key) => {
  activeTab.value = key
  // 同步到 URL,方便分享 + 浏览器后退
  router.replace({ query: { ...route.query, tab: key } })
}
const tabs = [
  { key: 'profile',  label: '个人资料', hint: '// Profile' },
  { key: 'billing',  label: '积分与流水', hint: '// Wallet' },
  { key: 'security', label: '账户安全',   hint: '// Security' },
]
// 监听外部路由变化(从 /billing redirect 进来时同步)
watch(() => route.query.tab, (q) => {
  if (q && VALID_TABS.includes(q) && q !== activeTab.value) activeTab.value = q
})
onMounted(async () => {
  nextTick(() => { showContent.value = true })
  if (auth.isLoggedIn) {
    await Promise.allSettled([fetchAccountProfile(), fetchMyAgentCount(), fetchFavoritesCount()])
  }
})
const auth = useAuthStore()
const toast = useToastStore()

const avatarInput = ref(null)
const changing = ref(false)
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const pwdMessage = ref('')
const pwdMsgType = ref('')
let msgTimer = null

// 扩展数据
const myAgentCount = ref(0)
const favoriteCount = ref(0)
const todayCallCount = ref(0)
const registerTime = computed(() => {
  const raw = firstPresent(
    auth.user?.created_at,
    auth.user?.create_time,
    auth.user?.created_time,
    auth.user?.date_joined,
    auth.user?.registered_at,
    auth.user?.register_time
  )
  return formatDateTime(raw)
})

const accountStatus = computed(() => {
  const raw = firstPresent(auth.user?.is_active, auth.user?.active, auth.user?.enabled, auth.user?.status)
  const active = normalizeAccountActive(raw)
  return { active, label: active ? '正常' : '已停用' }
})

const triggerAvatarInput = () => avatarInput.value?.click()

const onAvatarChange = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
 try {
 const formData = new FormData()
 formData.append('file', file)
 // 真后端 (实测 2026-06-10): POST /api/file/upload 返回 { orig_name, file_path }
 // file_path 形如 "uploads/uuid.png",前端 src 拼成 /api/file/{file_path}
 const uploadRes = await api.post('/file/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
 if (!uploadRes?.file_path) {
 throw new Error('上传失败:未返回 file_path')
 }
 const avatar = uploadRes.file_path
 // 真后端:PUT /api/account/me 更新当前用户(只需传 avatar)
 const res = await api.put('/account/me', { avatar })
 if (res?.id || res?.avatar || res?.username) {
 auth.updateAvatar(avatar)
 toast.success('头像已更新')
 } else {
 throw new Error('更新用户信息失败')
 }
 } catch (err) {
 toast.error(err.message || err.error_msg || '头像上传失败')
 } finally {
 if (e.target) e.target.value = ''
 }
}

const changePassword = async () => {
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    pwdMessage.value = '两次输入的新密码不一致'
    pwdMsgType.value = 'error'
    return
  }
  if (passwordForm.value.new_password.length < 6) {
    pwdMessage.value = '新密码至少 6 位'
    pwdMsgType.value = 'error'
    return
  }
  changing.value = true
  try {
 const res = await api.put('/account/me/password', { old_password: passwordForm.value.old_password, new_password: passwordForm.value.new_password })
 if (res?.message || res?.id || res?.username) {
 pwdMessage.value = '密码修改成功'
      pwdMessage.value = '密码修改成功'
      pwdMsgType.value = 'success'
      passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    }
  } catch (err) {
    pwdMessage.value = err.message || '修改失败'
    pwdMsgType.value = 'error'
  } finally {
    changing.value = false
    if (msgTimer) clearTimeout(msgTimer)
    msgTimer = setTimeout(() => { pwdMessage.value = '' }, 4000)
  }
}

onUnmounted(() => { if (msgTimer) clearTimeout(msgTimer) })

const handleLogout = () => {
  auth.logout()
  router.push('/auth')
}

const fetchAccountProfile = async () => {
  try {
    const userInfo = await api.get('/account/me')
    if (userInfo && typeof userInfo === 'object') auth.updateUser(userInfo)
  } catch {}
}

const firstPresent = (...values) => values.find((value) => value !== undefined && value !== null && value !== '')

const normalizeAccountActive = (value) => {
  if (value === undefined || value === null || value === '') return true
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  const text = String(value).trim().toLowerCase()
  if (['false', '0', 'disabled', 'inactive', 'deactivated', 'deleted', 'banned', 'blocked', '停用', '已停用', '禁用'].includes(text)) {
    return false
  }
  return true
}

const formatDateTime = (value) => {
  if (!value) return '暂无记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// 密码强度
const strengthClass = computed(() => {
  const p = passwordForm.value.new_password
  if (p.length < 6) return 'weak'
  if (p.length < 10 || !/[0-9]/.test(p) || !/[a-zA-Z]/.test(p)) return 'medium'
  return 'strong'
})
const strengthText = computed(() => {
  const s = strengthClass.value
  return s === 'weak' ? '弱 · 建议加长' : s === 'medium' ? '中 · 加入数字和字母' : '强 · 安全'
})

// 数据获取
const isExistingAgent = (agent) => agent?.is_deleted !== true && String(agent?.is_deleted).toLowerCase() !== 'true'
const agentCountKey = (agent) => String(agent?.name || '').trim().toLowerCase() || String(agent?.id || '')

const fetchMyAgentCount = async () => {
  try {
    const pageSize = 200
    const params = { page_num: 1, page_size: pageSize, is_deleted: false }
    const first = await api.get('/agent/client', { params })
    const items = Array.isArray(first?.items) ? [...first.items] : []
    const total = Number(first?.total || items.length)
    const pages = Math.ceil(total / pageSize)

    for (let pageNum = 2; pageNum <= pages; pageNum += 1) {
      const res = await api.get('/agent/client', { params: { ...params, page_num: pageNum } })
      if (Array.isArray(res?.items)) items.push(...res.items)
    }

    myAgentCount.value = new Set(items.filter(isExistingAgent).map(agentCountKey)).size
  } catch { myAgentCount.value = 0 }
}

const fetchFavoritesCount = async () => {
  try {
    const stored = localStorage.getItem('favorites')
    if (stored) {
      favoriteCount.value = Object.keys(JSON.parse(stored)).length
    } else {
      favoriteCount.value = 0
    }
  } catch {}
}
</script>

<style scoped>

/* Entry */
.anim-item { opacity: 0; transform: translateY(16px); }
.animate-in .anim-item { animation: fadeInUp 0.4s var(--ease-out) forwards; }
.animate-in .anim-1 { animation-delay: 0ms; }
.animate-in .anim-2 { animation-delay: 80ms; }
.animate-in .anim-3 { animation-delay: 160ms; }
.animate-in .anim-4 { animation-delay: 240ms; }
.animate-in .anim-5 { animation-delay: 320ms; }
.animate-in .anim-6 { animation-delay: 400ms; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.section { padding: 40px 0 96px; background: var(--bg-page); min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 32px; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
  margin-bottom: 32px; padding-bottom: 24px;
  border-bottom: 1px solid var(--ink);
  flex-wrap: wrap;
}
.page-issue {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-blue-d);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-blue);
}
.page-title {
  font-family: var(--font-display);
  font-size: clamp(28px, 3.5vw, 36px);
  font-weight: 600; color: var(--ink);
  letter-spacing: -0.025em;
  margin: 12px 0 0;
}
.page-desc { font-size: 14px; color: var(--ink-3); margin: 8px 0 0; max-width: 60ch; }

/* ===== Stats row ===== */
.stats-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 32px;
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 20px 24px;
  display: flex; flex-direction: column;
  gap: 4px;
  position: relative;
  transition: border-color var(--t-fast), transform var(--t-fast);
  overflow: hidden;
}
.stat-card:hover { border-color: var(--accent-blue-d); transform: translateY(-1px); }
.stat-card::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 0;
  height: 2px; background: var(--line-blue);
  opacity: 0; transition: opacity var(--t-fast);
}
.stat-card:hover::after { opacity: 1; }
.stat-balance { background: linear-gradient(135deg, #2E7AB8 0%, #1B5A8E 100%); color: var(--ink-inverse); border-color: var(--accent-blue-d); box-shadow: 0 12px 28px -10px rgba(27, 90, 142, 0.30); }
.stat-balance::after { background: var(--accent-blue); opacity: 0.5; }

.stat-k {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
}
.stat-balance .stat-k { color: rgba(255,255,255,0.6); }
.stat-v {
  font-family: var(--font-editorial);
  font-size: 32px; font-style: italic; font-weight: 400;
  color: var(--ink);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  margin: 4px 0 2px;
}
.stat-balance .stat-v { color: var(--ink-inverse); font-size: 36px; }
.stat-u {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.12em;
  color: var(--ink-4);
}
.stat-balance .stat-u { color: rgba(255,255,255,0.5); }

/* ===== Account grid (deprecated, kept for back-compat) ===== */
.account-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 24px;
  align-items: start;
}
@media (max-width: 900px) {
  .account-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}

/* ===== Tabs ===== */
.account-tabs {
  position: relative;
  display: flex;
  gap: 0;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-divider);
}
.account-tab {
  display: flex; flex-direction: column;
  gap: 4px;
  padding: 14px 24px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--ink-3);
  cursor: pointer;
  font-family: inherit;
  transition: color var(--t-fast), border-color var(--t-fast), background var(--t-fast);
  margin-bottom: -1px;  /* 抵消容器底边线,让 active 的下边框能盖住 */
  text-align: left;
}
.account-tab:hover { color: var(--ink-2); background: var(--bg-card-soft); }
.account-tab.active {
  color: var(--ink);
  border-bottom-color: var(--accent-blue-d);
}
.tab-label {
  font-family: var(--font-display);
  font-size: 15px; font-weight: 600;
  letter-spacing: -0.01em;
}
.tab-hint {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ink-4);
}
.account-tab.active .tab-hint { color: var(--accent-blue-d); }

/* tab 内容区淡入 */
.tab-pane { animation: tabPaneIn 0.3s var(--ease-out); }
@keyframes tabPaneIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

@media (max-width: 768px) {
  .account-tab { padding: 12px 14px; }
  .tab-hint { display: none; }
}

/* ===== Profile card ===== */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 28px 32px;
  transition: border-color var(--t-fast);
}
.card:hover { border-color: var(--ink-4); }

.card-head-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-divider);
}
.card-title {
  font-family: var(--font-display);
  font-size: 18px; font-weight: 600;
  color: var(--ink);
  margin: 0; letter-spacing: -0.01em;
}
.card-desc { font-size: 13px; color: var(--ink-3); margin: 0 0 20px; }

.profile-section {
  display: flex; align-items: center; gap: 18px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-divider);
}
.avatar-wrap {
  width: 72px; height: 72px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-page-blue);
  border: 1px solid var(--line-blue);
  border-radius: 50%;
  color: var(--accent-blue-d);
  position: relative;
  overflow: hidden;
  cursor: pointer;
  transition: all var(--t-fast);
  flex-shrink: 0;
}
.avatar-wrap:hover { border-color: var(--accent-blue); }
.avatar-wrap .avatar-img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }
.avatar-initial {
  font-family: var(--font-editorial);
  font-size: 32px; font-style: italic; font-weight: 400;
  color: var(--accent-blue-d);
}
.avatar-overlay {
  position: absolute; inset: 0;
  background: rgba(46, 122, 184, 0.85);
  opacity: 0;
  display: flex; align-items: center; justify-content: center;
  transition: opacity var(--t-fast);
  border-radius: 50%;
  color: #fff;
}
.avatar-wrap:hover .avatar-overlay { opacity: 1; }

.profile-meta { flex: 1; min-width: 0; }
.profile-name {
  font-family: var(--font-display);
  font-size: 22px; font-weight: 600;
  color: var(--ink);
  margin: 0 0 6px;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.profile-id { display: flex; align-items: center; gap: 8px; }
.id-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ink-3);
}
.id-value {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-2);
  background: var(--bg-card-soft);
  padding: 2px 8px;
  border-radius: var(--r-1);
}

/* Info list */
.info-list {
  display: flex; flex-direction: column;
  margin-bottom: 24px;
}
.info-item {
  display: grid;
  grid-template-columns: 110px 1fr;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-divider);
  font-size: 13px;
}
.info-item:last-child { border-bottom: none; }
.info-label {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
}
.info-value {
  color: var(--ink);
  font-weight: 500;
}
.stat-id { font-size: 24px; letter-spacing: 0.04em; font-family: var(--font-mono); }

.status-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: 1px;
}
.status-dot.on  { background: var(--signal-positive); box-shadow: 0 0 0 3px var(--signal-positive-soft); }
.status-dot.off { background: var(--signal-negative); }

.profile-actions {
  display: flex; gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--border-divider);
}
.btn-logout { color: var(--signal-negative); }
.btn-logout:hover:not(:disabled) { background: var(--signal-negative-soft); }

/* ===== Pwd card ===== */
.pwd-form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
  display: flex; align-items: center; gap: 6px;
  margin: 0;
}
.field input {
  padding: 10px 14px;
  border: 1px solid var(--border-input);
  border-radius: var(--r-2);
  background: var(--bg-input);
  color: var(--ink);
  font-size: 14px;
  transition: border-color var(--t-fast);
}
.field input:focus { outline: none; border-color: var(--accent-blue-d); }

/* Password strength */
.pwd-strength {
  display: flex; align-items: center; gap: 10px;
  margin-top: -4px;
}
.strength-bar {
  flex: 1;
  height: 3px;
  background: var(--bg-card-soft);
  border-radius: 2px;
  overflow: hidden;
  position: relative;
}
.strength-bar::after {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  border-radius: 2px;
  transition: width 0.3s, background 0.3s;
}
.strength-bar.weak::after { width: 30%; background: var(--signal-negative); }
.strength-bar.medium::after { width: 65%; background: var(--signal-warning); }
.strength-bar.strong::after { width: 100%; background: var(--signal-positive); }
.strength-text {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.08em;
  color: var(--ink-3);
  white-space: nowrap;
}

.form-msg { padding: 10px 14px; border-radius: var(--r-2); font-size: 13px; text-align: center; }
.form-msg.success { background: var(--signal-positive-soft); color: var(--signal-positive); }
.form-msg.error   { background: var(--signal-negative-soft); color: var(--signal-negative); }

.spinner-sm {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid currentColor; border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 6px; vertical-align: -2px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.security-tips {
  margin-top: 20px;
  padding: 16px;
  background: var(--bg-page-blue);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-2);
}
.tips-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--accent-blue-d);
  margin-bottom: 8px;
}
.security-tips ul {
  display: flex; flex-direction: column; gap: 4px;
  font-size: 12px; color: var(--ink-3);
  list-style: none; padding: 0; margin: 0;
}
.security-tips li {
  position: relative;
  padding-left: 16px;
}
.security-tips li::before {
  content: '·';
  position: absolute; left: 4px; top: -2px;
  color: var(--accent-blue);
  font-weight: 700;
}

@media (max-width: 768px) {
  .account-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: 1fr 1fr; }
  .stat-card { min-width: 0; padding: 18px; }
  .stat-balance .stat-id {
    max-width: 100%;
    overflow: hidden;
    font-size: 22px;
    letter-spacing: 0;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .profile-section { flex-direction: column; text-align: center; }
  .info-item { grid-template-columns: 90px 1fr; }
}
</style>
