<template>
  <section class="section">
    <div class="container">
      <button class="back-btn" @click="goBack">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        返回广场
      </button>

      <LoadingSpinner v-if="loading" />
      <EmptyState v-else-if="!agent" message="未找到该智能体" />

      <div v-else class="agent-detail" :class="{ 'animate-in': showContent }">
        <div class="agent-header-card anim-item anim-1">
          <div class="agent-header-grid" aria-hidden="true"></div>
          <div class="agent-avatar-large">
            <img v-if="agent.logo_url" :src="agent.logo_url" class="avatar-img" />
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <div class="agent-header-info">
            <span class="page-issue-light">AGENT · 智能体</span>
            <h1 class="agent-name">{{ agent.name }}</h1>
            <div class="agent-meta">
              <span class="status-badge" :class="statusClass(agent.approval_status)">
                {{ statusLabel(agent.approval_status) }}
              </span>
              <span v-if="agent.tag" class="tag-badge">{{ agent.tag }}</span>
              <span class="meta-item">by {{ agent.created_by?.username || agent.created_by?.name || '官方' }}</span>
              <span class="meta-item">{{ formattedCreatedAt }}</span>
            </div>
          </div>
          <div class="agent-header-actions">
            <router-link to="/chat" class="header-cta-primary">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              立即对话
            </router-link>
            <button class="header-cta-ghost" @click.stop="toggleDetailFav" :class="{ active: isFavorited }">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" :fill="isFavorited ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.8"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
              {{ isFavorited ? '已收藏' : '收藏' }}
            </button>
          </div>
        </div>

        <!-- Capabilities pills -->
        <div v-if="cardTags.length > 0" class="capabilities anim-item anim-2">
          <span class="cap-label">能力标签</span>
          <div class="cap-pills">
            <span v-for="t in cardTags" :key="t" class="cap-pill">{{ t }}</span>
          </div>
        </div>

        <div class="detail-grid anim-item anim-3">
          <div class="card description-card">
            <div class="card-head-row">
              <h3 class="card-title">关于这个智能体</h3>
              <span class="card-eyebrow">ABOUT</span>
            </div>
            <p class="description-text">{{ agent.description || '暂无描述' }}</p>
          </div>

          <div class="card quick-stats-card">
            <div class="card-head-row">
              <h3 class="card-title">快速概览</h3>
              <span class="card-eyebrow">SPECS</span>
            </div>
            <div class="quick-stats">
              <div class="qs-item">
                <span class="qs-label">评分</span>
                <span class="qs-value">
                  <span class="qs-big-num" :class="{ 'is-empty': !reviewStats.total }">
                    {{ reviewStats.total ? reviewStats.avg_rating : '—' }}
                  </span>
                  <span class="qs-unit">/ 5</span>
                </span>
              </div>
              <div class="qs-item">
                <span class="qs-label">价格</span>
                <span class="qs-value">
                  <span v-if="agent.price > 0" class="qs-big-num">{{ agent.price }}</span>
                  <span v-else class="qs-free">免费</span>
                  <span v-if="agent.price > 0" class="qs-unit">积分/次</span>
                </span>
              </div>
              <div class="qs-item">
                <span class="qs-label">评价数</span>
                <span class="qs-value">
                  <span class="qs-big-num">{{ reviewStats.total || 0 }}</span>
                  <span class="qs-unit">条</span>
                </span>
              </div>
              <div class="qs-item">
                <span class="qs-label">状态</span>
                <span class="qs-value">
                  <span v-if="agent.approval_status === 'APPROVED'" class="status-badge approved">已批准</span>
                  <span v-else-if="agent.approval_status === 'PENDING'" class="status-badge pending">待审批</span>
                  <span v-else class="status-badge rejected">已拒绝</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="card api-key-card anim-item anim-4">
          <div class="card-head-row">
            <h3 class="card-title">API 访问</h3>
            <span class="card-eyebrow">API KEY</span>
          </div>
          <KeyDisplay v-if="agent.aic" :value="agent.aic" />
          <p v-else class="no-key">暂无 API 密钥,请等待管理员审批通过后获取。</p>
        </div>

        <!-- Reviews -->
        <div class="card reviews-section">
          <h3 class="card-title">用户评价</h3>
          <div class="rating-summary">
            <div class="rating-score">
              <span class="rating-big-number">{{ reviewStats.total ? reviewStats.avg_rating : '—' }}</span>
              <span class="rating-out-of">/ 5</span>
            </div>
            <div class="rating-meta">
              <StarRating :model-value="Math.round(reviewStats.avg_rating || 0)" :readonly="true" :size="16" />
              <span class="rating-total">{{ reviewStats.total || 0 }} 条评价</span>
            </div>
            <div class="rating-distribution">
              <div v-for="star in 5" :key="star" class="distro-row">
                <span class="distro-label">{{ star }}星</span>
                <div class="distro-bar"><div class="distro-fill" :style="{ width: reviewStats.total ? ((reviewStats.distribution[star] || 0) / reviewStats.total * 100) + '%' : '0%' }"></div></div>
                <span class="distro-count">
                  <span class="num">{{ reviewStats.distribution[star] || 0 }}</span>
                  <span class="distro-pct" v-if="reviewStats.total">{{ Math.round((reviewStats.distribution[star] || 0) / reviewStats.total * 100) }}%</span>
                </span>
              </div>
            </div>
          </div>

          <div v-if="auth.isLoggedIn && !myReview" class="review-form">
            <h4 class="review-form-title">撰写评价</h4>
            <StarRating v-model="reviewRating" :size="24" />
            <textarea v-model="reviewComment" placeholder="分享您使用该智能体的体验..." class="review-textarea"></textarea>
            <button class="btn btn-primary" :disabled="!reviewRating || !reviewComment.trim() || reviewSubmitting" @click="submitReview">{{ reviewSubmitting ? '提交中...' : '提交评价' }}</button>
          </div>

          <div v-if="reviews.length > 0" class="reviews-list">
            <div v-for="review in reviews" :key="review.id" class="review-item">
              <div class="review-header">
                <div class="review-user-info">
                  <div class="review-avatar"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>
                  <span class="review-username">{{ review.username }}</span>
                </div>
                <div class="review-actions">
                  <StarRating :model-value="review.rating" :readonly="true" :size="14" />
                  <button v-if="review.user_id === auth.userId || auth.isAdmin" class="review-delete-btn" @click="deleteReview(review.id)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  </button>
                </div>
              </div>
              <p class="review-comment">{{ review.comment }}</p>
              <span class="review-time">{{ review.created_at }}</span>
            </div>

            <div v-if="reviewTotal > 10" class="pagination-row">
              <button class="btn btn-secondary btn-sm" :disabled="reviewPage <= 1" @click="reviewPage--; fetchReviews()">上一页</button>
              <span class="page-info">{{ reviewPage }} / {{ Math.ceil(reviewTotal / 10) }}</span>
              <button class="btn btn-secondary btn-sm" :disabled="reviewPage >= Math.ceil(reviewTotal / 10)" @click="reviewPage++; fetchReviews()">下一页</button>
            </div>
          </div>
          <div v-else-if="!loading" class="review-empty">
            <div class="review-empty-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            </div>
            <p class="review-empty-title">还没有评价</p>
            <p class="review-empty-sub">成为第一个使用并评价这个智能体的人吧</p>
          </div>
        </div>

        <!-- Inline Chat -->
        <div class="card chat-section">
          <h3 class="card-title">与 {{ agent.name }} 对话</h3>
          <div class="chat-widget">
            <div class="chat-messages" ref="chatMessagesRef">
              <div v-if="chatMessages.length === 0" class="chat-welcome">
                <div class="welcome-icon"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
                <h4>开始与 {{ agent.name }} 对话</h4>
                <p>发送消息与这个智能体交互 — 系统会自动分析任务并路由到合适的模型。</p>
                <div class="quick-prompts">
                  <span class="quick-prompts-label">试试这些问题</span>
                  <div class="quick-prompts-list">
                    <button v-for="(p, i) in quickPrompts" :key="i" class="quick-prompt" @click="sendQuickPrompt(p)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                      {{ p }}
                    </button>
                  </div>
                </div>
              </div>
              <div v-for="(msg, index) in chatMessages" :key="index" class="message-item" :class="msg.role">
                <div class="message-avatar" :class="msg.role === 'bot' ? 'bot-avatar' : ''">
                  <svg v-if="msg.role === 'user'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </div>
                <div class="message-bubble"><div class="message-text">{{ msg.content }}</div><div class="message-time">{{ msg.time }}</div></div>
              </div>
              <div v-if="isTyping" class="message-item bot">
                <div class="message-avatar bot-avatar"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
                <div class="message-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>
              </div>
            </div>
            <div class="chat-input-wrapper">
              <input v-model="chatInput" @keydown.enter.exact.prevent="sendMessage" placeholder="输入消息... (Enter 发送)" class="chat-input" />
              <button @click="sendMessage" :disabled="!chatInput.trim() || isTyping" class="chat-send-btn">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, nextTick, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import StarRating from '@/components/StarRating.vue'
import KeyDisplay from '@/components/KeyDisplay.vue'

const showContent = ref(false)
onMounted(() => { nextTick(() => { showContent.value = true }) })
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const agent = ref(null)
const loading = ref(true)
const chatMessages = ref([])
const chatInput = ref('')
const isTyping = ref(false)
const chatMessagesRef = ref(null)
const reviews = ref([])
const reviewStats = ref({ avg_rating: 0, total: 0, distribution: {} })
const myReview = ref(null)
const reviewRating = ref(0)
const reviewComment = ref('')
const reviewSubmitting = ref(false)
const reviewPage = ref(1)
const reviewTotal = ref(0)
const isFavorited = ref(false)

/* 自动从 name + description 提取能力标签 */
const cardTags = computed(() => {
  const a = agent.value
  if (!a) return []
  if (Array.isArray(a.tags) && a.tags.length > 0) return a.tags.slice(0, 5)
  if (typeof a.tags === 'string' && a.tags.trim()) {
    try { const parsed = JSON.parse(a.tags); if (Array.isArray(parsed)) return parsed.slice(0, 5) } catch {}
    if (a.tags.includes(',')) return a.tags.split(',').map(t => t.trim()).filter(Boolean).slice(0, 5)
    return [a.tags]
  }
  if (a.tag) return [a.tag]
  const text = ((a.name || '') + ' ' + (a.description || '')).toLowerCase()
  const tagOptions = [
    { keywords: ['办公', '效率', '工作', '文档', '表格', 'ppt', 'word', 'excel'], label: '办公效率' },
    { keywords: ['娱乐', '游戏', '音乐', '视频', '电影', '休闲'], label: '休闲娱乐' },
    { keywords: ['生活', '日常', '购物', '外卖', '天气', '日历'], label: '生活服务' },
    { keywords: ['内容', '创作', '写作', '文案', '文章', '小红书', '短视频'], label: '内容创作' },
    { keywords: ['理财', '投资', '股票', '基金', '财务', '记账'], label: '理财投资' },
    { keywords: ['学术', '研究', '论文', '文献', '搜索', '翻译'], label: '学术研究' },
    { keywords: ['代码', '编程', '开发', 'sql', 'python', '重构', 'api'], label: '编程开发' },
    { keywords: ['数据', '分析', '图表', '统计', 'sql'], label: '数据分析' },
  ]
  const matched = []
  for (const opt of tagOptions) {
    if (opt.keywords.some(k => text.includes(k))) matched.push(opt.label)
  }
  return matched.slice(0, 4)
})

/* 快速试用提示 */
const quickPrompts = computed(() => {
  const a = agent.value
  if (!a) return []
  const text = ((a.name || '') + ' ' + (a.description || '')).toLowerCase()
  if (/代码|编程|开发|sql|python|重构|api/.test(text)) {
    return [
      '帮我重构这段代码,提高可读性',
      '解释一下这段 SQL 的执行计划',
      '写一个 Python 函数,实现...'
    ]
  }
  if (/内容|创作|写作|文案|文章|小红书|短视频/.test(text)) {
    return [
      '帮我写一段产品介绍文案',
      '把这个想法改写成小红书风格',
      '生成 5 个短视频脚本标题'
    ]
  }
  if (/数据|分析|图表|统计/.test(text)) {
    return [
      '分析一下这份 CSV 的关键指标',
      '用图表展示 Q3 销售趋势',
      '找出数据中的异常值'
    ]
  }
  if (/翻译|学术|研究|论文|文献/.test(text)) {
    return [
      '翻译这段英文摘要',
      '总结这篇论文的核心观点',
      '找出相关领域的研究综述'
    ]
  }
  return [
    `介绍一下你自己能做什么`,
    `给我一个 ${a.name} 的使用示例`,
    '你可以处理多长的输入?'
  ]
})

const sendQuickPrompt = (prompt) => {
  chatInput.value = prompt
  sendMessage()
}

const formattedCreatedAt = computed(() => {
  if (!agent.value?.created_at) return ''
  const d = new Date(agent.value.created_at)
  if (isNaN(d.getTime())) return agent.value.created_at
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
})

const scrollToBottom = () => { nextTick(() => { if (chatMessagesRef.value) chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight }) }
const goBack = () => router.back()

const toggleDetailFav = () => {
  if (!auth.isLoggedIn) { toast.warning('请先登录'); return }
  const stored = localStorage.getItem('favorites')
  const favMap = stored ? JSON.parse(stored) : {}
  if (favMap[agent.value.id]) {
    delete favMap[agent.value.id]
    isFavorited.value = false
    toast.success('已取消收藏')
  } else {
    favMap[agent.value.id] = {
      id: agent.value.id,
      name: agent.value.name,
      description: agent.value.description,
      tags: agent.value.tags,
      logo_url: agent.value.logo_url
    }
    isFavorited.value = true
    toast.success('已添加收藏')
  }
  localStorage.setItem('favorites', JSON.stringify(favMap))
}

const loadDetailFav = () => {
  const stored = localStorage.getItem('favorites')
  if (!stored) return
  const favMap = JSON.parse(stored)
  isFavorited.value = !!favMap[agent.value?.id]
}

const fetchAgent = async () => {
  loading.value = true
  try {
    const endpoint = auth.isAdmin
      ? `/agent/staff/${route.params.id}`
      : `/agent/public/${route.params.id}`
    const res = await api.get(endpoint)
    agent.value = res
  }
  catch (err) { toast.error(err.message) }
  finally { loading.value = false }
}

const statusClass = (status) => {
  if (status === 'APPROVED') return 'approved'
  if (status === 'PENDING') return 'pending'
  return 'rejected'
}

const statusLabel = (status) => {
  const map = { APPROVED: '已上线', PENDING: '待审批', REJECTED: '已拒绝', DRAFT: '草稿' }
  return map[status] || '未知状态'
}

const sendMessage = async () => {
  const text = chatInput.value.trim()
  if (!text || isTyping.value) return

  chatMessages.value.push({ role: 'user', content: text, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
  chatInput.value = ''; scrollToBottom(); isTyping.value = true

  try {
    // 通过当前平台入口调用，避免把部署地址固化在浏览器代码中。
    const res = await fetch('/mode-router/pipeline/discovery', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: text,
        discovery_url: `${window.location.origin}/acps-adp-v2/discover`,
        limit: 5,
        hints: {
          estimated_skill_count: 4,
          requires_independent_roles: false,
          parallelizable: false
        }
      })
    })
    const data = await res.json()

    isTyping.value = false

    // 解析返回结果
    const mode = data.decision?.mode || 'unknown'
    const skillCount = data.normalized_skill_count || 0
    const summary = data.decision?.summary || '分析完成'
    const selectedSkills = data.decision?.evidence?.selected_skills || []

    let skillList = ''
    if (selectedSkills.length > 0) {
      skillList = '\n\n发现的相关技能：\n' + selectedSkills.map((s, i) =>
        `${i + 1}. ${s.agent_name || '未知智能体'} - ${s.skillid || '未知技能'}`
      ).join('\n')
    }

    const resultText = `【任务分析结果】\n\n模式: ${mode}\n相关技能数: ${skillCount}\n\n${summary}${skillList}`

    chatMessages.value.push({ role: 'bot', content: resultText, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
    scrollToBottom()
  } catch (err) {
    isTyping.value = false
    chatMessages.value.push({ role: 'bot', content: `分析失败: ${err.message}`, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
    scrollToBottom()
    toast.error(err.message)
  }
}

const fetchReviewStats = async () => {
  // 本地存储评价统计
  const stats = localStorage.getItem(`review_stats_${route.params.id}`)
  reviewStats.value = stats ? JSON.parse(stats) : { avg_rating: 0, total: 0, distribution: {1:0,2:0,3:0,4:0,5:0} }
}

const fetchReviews = async () => {
  // 本地存储评价
  const stored = localStorage.getItem(`reviews_${route.params.id}`)
  reviews.value = stored ? JSON.parse(stored) : []
  reviewTotal.value = reviews.value.length
}

const fetchMyReview = async () => {
  // 本地存储我的评价
  if (!auth.isLoggedIn) return
  const stored = localStorage.getItem(`reviews_${route.params.id}`)
  const allReviews = stored ? JSON.parse(stored) : []
  myReview.value = allReviews.find(r => r.user_id === auth.userId) || null
}

const submitReview = async () => {
  if (!reviewRating.value || !reviewComment.value.trim()) return
  reviewSubmitting.value = true
  try {
    const newReview = {
      id: Date.now().toString(),
      agent_id: route.params.id,
      user_id: auth.userId,
      username: auth.username,
      rating: reviewRating.value,
      comment: reviewComment.value.trim(),
      created_at: new Date().toLocaleString('zh-CN')
    }

    // 保存到本地
    const stored = localStorage.getItem(`reviews_${route.params.id}`)
    const allReviews = stored ? JSON.parse(stored) : []
    allReviews.unshift(newReview)
    localStorage.setItem(`reviews_${route.params.id}`, JSON.stringify(allReviews))

    // 更新统计
    const stats = { avg_rating: 0, total: 0, distribution: {1:0,2:0,3:0,4:0,5:0} }
    allReviews.forEach(r => {
      stats.total++
      stats.distribution[r.rating] = (stats.distribution[r.rating] || 0) + 1
    })
    const sum = allReviews.reduce((acc, r) => acc + r.rating, 0)
    stats.avg_rating = stats.total > 0 ? (sum / stats.total).toFixed(1) : 0
    localStorage.setItem(`review_stats_${route.params.id}`, JSON.stringify(stats))

    reviewRating.value = 0
    reviewComment.value = ''
    reviewPage.value = 1
    await Promise.all([fetchReviews(), fetchReviewStats(), fetchMyReview()])
    toast.success('评价已提交')
  } catch (err) { toast.error(err.message) }
  finally { reviewSubmitting.value = false }
}

const deleteReview = async (reviewId) => {
  if (!confirm('确定要删除这条评价吗？')) return
  try {
    const stored = localStorage.getItem(`reviews_${route.params.id}`)
    const allReviews = stored ? JSON.parse(stored) : []
    const updated = allReviews.filter(r => r.id !== reviewId)
    localStorage.setItem(`reviews_${route.params.id}`, JSON.stringify(updated))

    await Promise.all([fetchReviews(), fetchReviewStats(), fetchMyReview()])
    toast.success('评价已删除')
  } catch (err) { toast.error(err.message) }
}

onMounted(async () => {
  await Promise.allSettled([fetchAgent(), fetchReviewStats(), fetchReviews(), fetchMyReview()])
  loadDetailFav()
})
</script>

<style scoped>

/* Entry */
.anim-item { opacity: 0; transform: translateY(16px); }
.animate-in .anim-item { animation: fadeInUp 0.4s var(--ease-out) forwards; }
.animate-in .anim-1 { animation-delay: 0ms; }
.animate-in .anim-2 { animation-delay: 80ms; }
.animate-in .anim-3 { animation-delay: 160ms; }
.animate-in .anim-4 { animation-delay: 240ms; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.section { padding: 40px 0 96px; background: var(--bg-page); min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 32px; }

.back-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 16px 8px 12px;
  background: transparent;
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  font-size: 13px; font-weight: 500;
  color: var(--ink-2);
  cursor: pointer;
  transition: all var(--t-fast);
  margin-bottom: 24px;
  font-family: inherit;
}
.back-btn:hover { border-color: var(--accent-blue-d); color: var(--ink); background: var(--bg-card-soft); transform: translateX(-2px); }
.back-btn svg { transition: transform var(--t-fast); }
.back-btn:hover svg { transform: translateX(-2px); }

/* === Agent header (editorial cover) === */
.agent-header-card {
  display: grid;
  grid-template-columns: 96px 1fr auto;
  gap: 28px;
  align-items: center;
  padding: 40px;
  background: var(--sky-grad-deep);
  color: var(--ink-inverse);
  border-radius: var(--r-3);
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}
.agent-header-card::after {
  content: '';
  position: absolute; right: -40px; top: -40px;
  width: 240px; height: 240px;
  background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}
.agent-header-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse 80% 70% at 80% 50%, #000 30%, transparent 100%);
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 80% 50%, #000 30%, transparent 100%);
  pointer-events: none;
}
.agent-avatar-large {
  width: 96px; height: 96px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: var(--r-3);
  overflow: hidden;
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  box-shadow: 0 0 0 6px rgba(255, 255, 255, 0.04), 0 12px 32px -8px rgba(0, 0, 0, 0.4);
}
.agent-avatar-large .avatar-img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }
.agent-header-info { position: relative; z-index: 1; min-width: 0; }
.page-issue-light {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-blue-l);
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(46, 122, 184, 0.3);
}
.agent-name {
  font-family: var(--font-display);
  font-size: 40px; font-weight: 600;
  margin: 0 0 14px 0;
  letter-spacing: -0.025em;
  line-height: 1.1;
  word-wrap: break-word;
}
.agent-meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.meta-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px;
  color: rgba(255,255,255,0.7);
}
.meta-item::before { content: '·'; color: rgba(255,255,255,0.4); }
.meta-item:first-of-type::before { display: none; }
.tag-badge {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  color: rgba(255,255,255,0.85);
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  padding: 3px 10px;
  border-radius: var(--r-1);
  letter-spacing: 0.12em; text-transform: uppercase;
}

/* Capabilities pills 行 */
.capabilities {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 24px;
  padding: 14px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  flex-wrap: wrap;
}
.cap-label {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--ink-3);
  flex-shrink: 0;
}
.cap-pills { display: flex; gap: 6px; flex-wrap: wrap; }
.cap-pill {
  display: inline-flex; align-items: center;
  padding: 4px 12px;
  font-size: 12px; font-weight: 500;
  color: var(--accent-blue-d);
  background: var(--accent-blue-bg);
  border: 1px solid var(--accent-blue-border);
  border-radius: var(--r-pill);
  transition: all var(--t-fast);
}
.cap-pill:hover {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
}

/* 通用 card head 行(标题 + eyebrow) */
.card-head-row {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-divider);
}
.card-eyebrow {
  font-family: var(--font-mono);
  font-size: 9px; font-weight: 500;
  letter-spacing: 0.24em; text-transform: uppercase;
  color: var(--ink-4);
}

/* Header 主 CTA + 副操作 */
.agent-header-actions {
  display: flex; align-items: center; gap: 10px;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}
.header-cta-primary {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px;
  background: var(--ink-inverse);
  color: var(--ink);
  border: 1px solid var(--ink-inverse);
  border-radius: var(--r-3);
  font-size: 14px; font-weight: 600;
  text-decoration: none;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--t-fast);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.1);
}
.header-cta-primary:hover {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
  transform: translateY(-1px);
  box-shadow: 0 8px 20px -4px rgba(46, 122, 184, 0.4);
}
.header-cta-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 11px 16px;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--r-3);
  font-size: 13px; font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--t-fast);
}
.header-cta-ghost:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.08);
}
.header-cta-ghost.active {
  color: var(--signal-favorite);
  border-color: rgba(199, 62, 90, 0.5);
  background: rgba(199, 62, 90, 0.1);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}
.description-card { display: flex; flex-direction: column; }
.quick-stats-card { display: flex; flex-direction: column; }
.api-key-card { margin-bottom: 24px; }
@media (max-width: 768px) {
  .detail-grid { grid-template-columns: 1fr; }
}

.description-text {
  font-size: 16px; line-height: 1.75;
  color: var(--ink-2);
  margin: 0;
  letter-spacing: 0.005em;
}

/* Quick stats 卡片 */
.quick-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px 24px;
  flex: 1;
}
.qs-item {
  display: flex; flex-direction: column; gap: 4px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-divider);
}
.qs-item:nth-last-child(-n+2) { border-bottom: none; }
.qs-label {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ink-3);
}
.qs-value {
  display: flex; align-items: baseline; gap: 4px;
  flex-wrap: wrap;
}
.qs-big-num {
  font-family: var(--font-editorial);
  font-style: italic; font-weight: 500;
  font-size: 26px;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1;
}
.qs-big-num.is-empty { color: var(--ink-4); font-size: 22px; }
.qs-unit {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em;
  color: var(--ink-3);
}
.qs-free {
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--signal-positive);
  padding: 2px 10px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: var(--r-1);
}

.no-key {
  color: var(--ink-3);
  font-size: 14px;
  margin: 0;
  padding: 12px 16px;
  background: var(--bg-card-soft);
  border: 1px dashed var(--border-card);
  border-radius: var(--r-2);
}

/* === Chat widget === */
.chat-section { margin-top: 24px; }
.chat-widget {
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  overflow: hidden;
}
.chat-messages {
  height: 440px;
  overflow-y: auto;
  padding: 24px;
  display: flex; flex-direction: column; gap: 16px;
  scroll-behavior: smooth;
}
.chat-messages::-webkit-scrollbar { width: 6px; }
.chat-messages::-webkit-scrollbar-thumb { background: var(--border-card); border-radius: 3px; }
.chat-messages::-webkit-scrollbar-thumb:hover { background: var(--ink-4); }
.chat-welcome {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; text-align: center;
  color: var(--ink-3);
  padding: 16px;
}
.welcome-icon {
  width: 64px; height: 64px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 50%;
  margin-bottom: 16px;
  color: var(--ink);
}
.chat-welcome h4 { font-size: 16px; font-weight: 600; color: var(--ink); margin: 0 0 8px; }
.chat-welcome p { font-size: 14px; margin: 0 0 20px; max-width: 50ch; }

.quick-prompts {
  width: 100%;
  max-width: 480px;
  margin-top: 8px;
}
.quick-prompts-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--ink-3);
  margin-bottom: 10px;
}
.quick-prompts-list {
  display: flex; flex-direction: column; gap: 6px;
  align-items: stretch;
}
.quick-prompt {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  font-size: 13px;
  color: var(--ink-2);
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--t-fast);
}
.quick-prompt:hover {
  border-color: var(--accent-blue);
  background: var(--accent-blue-bg);
  color: var(--accent-blue-d);
  transform: translateX(2px);
}
.quick-prompt svg { color: var(--ink-4); flex-shrink: 0; transition: color var(--t-fast); }
.quick-prompt:hover svg { color: var(--accent-blue); }

.message-item { display: flex; gap: 12px; max-width: 80%; }
.message-item.user { flex-direction: row-reverse; align-self: flex-end; margin-left: auto; }
.message-item.bot { align-self: flex-start; }
.message-avatar {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 50%;
  color: var(--ink-2);
  flex-shrink: 0;
}
.message-item.user .message-avatar { background: var(--sky-grad-deep); border-color: var(--accent-blue-d); color: var(--ink-inverse); }
.message-bubble { display: flex; flex-direction: column; gap: 4px; }
.message-text {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px; line-height: 1.55;
}
.message-item.bot .message-text { background: var(--bg-card); color: var(--ink); border: 1px solid var(--border-card); border-bottom-left-radius: 4px; }
.message-item.user .message-text { background: var(--sky-grad-deep); color: var(--ink-inverse); box-shadow: 0 2px 8px rgba(46, 122, 184, 0.22); border-bottom-right-radius: 4px; }
.message-time {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-4);
  padding: 0 4px;
}
.message-item.user .message-time { text-align: right; }

.typing-dots {
  display: flex; gap: 4px;
  padding: 14px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 14px; border-bottom-left-radius: 4px;
}
.typing-dots span {
  width: 6px; height: 6px;
  background: var(--sky-grad-deep);
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out both;
}
.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes typingBounce { 0%,80%,100% { transform: scale(0); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

.chat-input-wrapper {
  display: flex; gap: 12px;
  padding: 16px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-divider);
}
.chat-input {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid var(--border-input);
  border-radius: var(--r-pill);
  font-size: 14px;
  background: var(--bg-input);
  color: var(--ink);
  outline: none;
  transition: border-color var(--t-fast);
}
.chat-input:focus { border-color: var(--accent-blue-d); }
.chat-send-btn {
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  background: var(--sky-grad-deep);
  border: none; border-radius: 50%;
  color: var(--ink-inverse);
  cursor: pointer;
  transition: transform var(--t-fast), background var(--t-fast);
}
.chat-send-btn:hover:not(:disabled) { background: var(--ink-2); transform: scale(1.05); }
.chat-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* === Reviews === */
.reviews-section { margin-bottom: 24px; }
.rating-summary {
  display: flex; align-items: center; gap: 32px;
  padding: 24px 0;
  border-bottom: 1px solid var(--border-divider);
  margin-bottom: 28px;
  flex-wrap: wrap;
}
.rating-score { display: flex; align-items: baseline; gap: 4px; }
.rating-big-number {
  font-family: var(--font-editorial);
  font-size: 64px; font-style: italic; font-weight: 400;
  color: var(--ink);
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}
.rating-out-of {
  font-size: 16px;
  color: var(--ink-3);
}
.rating-meta {
  display: flex; flex-direction: column; gap: 6px;
}
.rating-total {
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
}
.rating-distribution {
  flex: 1; min-width: 280px;
  display: flex; flex-direction: column; gap: 8px;
  margin-left: auto;
}
.distro-row { display: flex; align-items: center; gap: 10px; }
.distro-label {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em;
  color: var(--ink-3);
  width: 32px;
}
.distro-bar {
  flex: 1; height: 5px;
  background: var(--border-card);
  border-radius: 3px;
  overflow: hidden;
}
.distro-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue) 0%, var(--accent-blue-d) 100%);
  border-radius: 3px;
  transition: width 0.6s var(--ease-out);
}
.distro-count {
  display: flex; align-items: baseline; gap: 6px;
  width: 60px; justify-content: flex-end;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
}
.distro-count .num { color: var(--ink); font-weight: 500; }
.distro-pct { color: var(--ink-4); font-size: 10px; }

/* 空态:更像杂志 */
.review-empty {
  text-align: center;
  padding: 56px 24px;
  color: var(--ink-3);
}
.review-empty-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 56px; height: 56px;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: 50%;
  color: var(--ink-4);
  margin-bottom: 12px;
}
.review-empty-title {
  font-size: 15px; font-weight: 600;
  color: var(--ink);
  margin: 0 0 4px;
}
.review-empty-sub {
  font-size: 13px;
  color: var(--ink-3);
  margin: 0;
}

.review-form {
  padding-bottom: 24px; margin-bottom: 24px;
  border-bottom: 1px solid var(--border-divider);
}
.review-form-title { font-size: 14px; font-weight: 600; color: var(--ink); margin: 0 0 12px; }
.review-textarea {
  width: 100%;
  min-height: 100px;
  padding: 12px 16px;
  border: 1px solid var(--border-input);
  border-radius: var(--r-2);
  font-size: 14px;
  background: var(--bg-input);
  color: var(--ink);
  resize: vertical;
  outline: none;
  transition: border-color var(--t-fast);
  margin-bottom: 12px;
}
.review-textarea:focus { border-color: var(--accent-blue-d); }

.reviews-list { display: flex; flex-direction: column; gap: 12px; }
.review-item {
  padding: 16px 20px;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
}
.review-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.review-user-info { display: flex; align-items: center; gap: 8px; }
.review-avatar {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 50%;
  color: var(--ink-2);
}
.review-username { font-size: 14px; font-weight: 600; color: var(--ink); }
.review-actions { display: flex; align-items: center; gap: 8px; }
.review-delete-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  background: none; border: none;
  border-radius: var(--r-1);
  color: var(--ink-4);
  cursor: pointer;
  transition: all var(--t-fast);
}
.review-delete-btn:hover { color: var(--signal-negative); background: var(--signal-negative-soft); }
.review-comment { font-size: 14px; line-height: 1.6; color: var(--ink-2); margin: 0 0 8px; }
.review-time {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-4);
}
.review-empty { text-align: center; padding: 40px 24px; color: var(--ink-3); font-size: 14px; }
.pagination-row { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 20px; }
.page-info { font-size: 13px; color: var(--ink-3); }

@media (max-width: 768px) {
  .agent-header-card { grid-template-columns: 1fr; text-align: center; padding: 28px; gap: 16px; }
  .agent-avatar-large { margin: 0 auto; }
  .agent-name { font-size: 30px; }
  .agent-meta { justify-content: center; }
  .agent-header-actions { width: 100%; justify-content: center; }
  .header-cta-primary, .header-cta-ghost { flex: 1; justify-content: center; }
  .capabilities { padding: 12px 16px; }
  .cap-label { width: 100%; }
  .quick-stats { grid-template-columns: 1fr; gap: 0; }
  .qs-item:nth-last-child(-n+2) { border-bottom: 1px solid var(--border-divider); }
  .qs-item:last-child { border-bottom: none; }
  .message-item { max-width: 90%; }
  .rating-big-number { font-size: 48px; }
  .rating-summary { gap: 20px; }
  .rating-distribution { width: 100%; margin-left: 0; }
  .chat-messages { height: 360px; padding: 16px; }
}
</style>
