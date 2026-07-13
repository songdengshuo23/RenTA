<template>
  <section class="section">
    <div class="container">
      <StaggerReveal :delay="100" :initial-delay="60">
        <!-- ===== Editorial Hero ===== -->
        <header class="square-hero">
          <div class="hero-meta-row">
            <span class="page-issue">RenTA Agent Square</span>
            <div class="hero-meta-right">
              <span><span class="num">{{ agents.length }}</span> 个智能体</span>
              <span class="dot-sep">·</span>
              <span><span class="num">{{ tags.length - 1 }}</span> 个分类</span>
              <span class="dot-sep">·</span>
              <span>即时刷新</span>
            </div>
          </div>
          <div class="hero-title-row">
            <h1 class="hero-title-square">
              探索 <em>AI</em> 智能体
            </h1>
            <div class="hero-actions">
              <button class="hero-cta" @click="router.push('/chat')">
                开始对话
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </button>
              <router-link to="/agent-apply" class="hero-cta-ghost">我要出租 </router-link>
            </div>
          </div>
          <p class="hero-sub">试试大家的Agent，探索无限可能</p>
        </header>

        <!-- ===== Filter bar ===== -->
        <div class="filter-bar">
          <nav class="tab-nav">
            <button :class="['tab-link', { active: activeTab === 'explore' }]" @click="switchToExplore">发现</button>
            <button v-if="auth.isLoggedIn" :class="['tab-link', { active: activeTab === 'mine' }]" @click="switchToMine">我的上传</button>
            <button :class="['tab-link', { active: activeTab === 'library' }]" @click="switchToLibrary">收藏</button>
          </nav>

          <div class="filter-tools">
            <div class="search-wrap">
              <svg class="search-icon-s" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input v-model="searchQuery" @input="handleSearch" type="text" placeholder="搜索…" class="search-input-inline"/>
              <button v-if="searchQuery" @click="clearSearch" class="search-clear">×</button>
            </div>
            <div class="sort-toggle">
              <button :class="{ active: sortBy === 'latest' }" @click="setSort('latest')">最新</button>
              <button :class="{ active: sortBy === 'hottest' }" @click="setSort('hottest')">最热</button>
              <button :class="{ active: sortBy === 'price_asc' }" @click="setSort('price_asc')" title="价格升序">价低</button>
              <button :class="{ active: sortBy === 'price_desc' }" @click="setSort('price_desc')" title="价格降序">价高</button>
            </div>
          </div>
        </div>

        <div class="tag-filter-bar" :class="{ expanded: showAllTags }">
          <button class="tag-btn" :class="{ active: !activeTag }" @click="activeTag = ''; reloadCurrentList()">全部</button>
          <button v-for="(tag, index) in tags.slice(1)" :key="tag.value" class="tag-btn" :class="[{ active: activeTag === tag.value }, { 'is-extra': index >= 3 }]" @click="selectTag(tag.value)">{{ tag.label }}</button>
          <button class="tag-more-btn" type="button" :aria-expanded="showAllTags" @click="showAllTags = !showAllTags">
            <span>{{ showAllTags ? '收起分类' : '更多分类' }}</span>
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" :class="{ rotated: showAllTags }"><polyline points="6 9 12 15 18 9" /></svg>
          </button>
        </div>
      </StaggerReveal>

      <!-- ===== Featured 专题卡 ===== -->
      <article v-if="activeTab === 'explore' && featuredAgent" class="featured-card anim-item" @click="goToDetail(featuredAgent)">
        <div class="featured-avatar">
          <img v-if="featuredAgent.logo_url" :src="featuredAgent.logo_url" class="avatar-img" />
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
        </div>
        <div class="featured-body">
          <div class="featured-meta">
            <span class="featured-kicker">本周热门 · Editor's Pick</span>
            <span class="featured-rating" v-if="featuredAgent.avg_rating">
              <span class="num">★ {{ featuredAgent.avg_rating }}</span>
              <span class="featured-rating-count">({{ featuredAgent.review_count }} 评价)</span>
            </span>
          </div>
          <h2 class="featured-name">{{ featuredAgent.name }}</h2>
          <p class="featured-desc">{{ featuredAgent.description || '这个智能体最近被频繁调用,值得一试。' }}</p>
          <div class="featured-foot">
            <span class="featured-author">by {{ featuredAgent.created_by?.username || featuredAgent.owner_name || '官方' }}</span>
            <span v-if="featuredAgent.price > 0" class="featured-price">{{ featuredAgent.price }} 积分/次</span>
            <span v-else class="featured-free">免费调用</span>
            <span class="featured-cta">查看详情 →</span>
          </div>
        </div>
      </article>

      <!-- ===== Grid ===== -->
      <div v-if="activeTab === 'explore'" class="tab-content">
        <div class="section-divider" style="margin-top: 48px"><span>{{ listTitle }}</span></div>
        <div v-if="showMineHint" class="mine-hint">
          <span class="mine-hint-kicker">REVIEW QUEUE</span>
          <span>当前公开列表没有可展示的智能体，已显示你的上传记录。待 supervisor 审核通过后会进入公开广场。</span>
        </div>
        <div v-if="loading" class="skeleton-grid">
          <div v-for="i in 6" :key="'sk-'+i" class="skeleton-card" :style="{ animationDelay: (i*60)+'ms' }">
            <div class="skeleton-avatar"></div>
            <div class="skeleton-content"><div class="skeleton-line short"></div><div class="skeleton-line medium"></div><div class="skeleton-line long"></div></div>
          </div>
        </div>
        <EmptyState v-else-if="agents.length === 0" :message="searchQuery ? '未找到匹配的智能体' : '暂无智能体'" />
        <div v-else class="agent-grid stagger-grid">
          <AgentCard v-for="(agent, i) in agents" :key="agent.id" :agent="agent" :class="`stagger-${Math.min(i + 1, 6)}`" :favorited="favoriteStatus[agent.id]" :is-admin="auth.isAdmin" @click="goToDetail(agent)" @fav="toggleFavorite(agent.id)" @deactivate="deactivateAgent(agent.id)" />
        </div>
      </div>

      <div v-if="activeTab === 'mine'" class="tab-content">
        <section class="lib-section">
          <h3 class="lib-title"><span class="lib-num">B.</span> 我的上传</h3>
          <LoadingSpinner v-if="loadingMine" />
          <EmptyState v-else-if="filteredMyAgents.length === 0" :message="searchQuery || activeTag ? '未找到匹配的上传记录' : '暂无上传的智能体'" />
          <div v-else class="agent-grid">
            <AgentCard v-for="agent in filteredMyAgents" :key="agent.id" :agent="agent" :favorited="favoriteStatus[agent.id]" :is-admin="auth.isAdmin" @click="goToDetail(agent)" @fav="toggleFavorite(agent.id)" @deactivate="deactivateAgent(agent.id)" />
          </div>
        </section>
      </div>

      <div v-if="activeTab === 'library'" class="tab-content">
        <section class="lib-section">
          <h3 class="lib-title"><span class="lib-num">A.</span> 我的收藏</h3>
          <EmptyState v-if="filteredFavorites.length === 0" :message="searchQuery || activeTag ? '未找到匹配的收藏' : '暂无收藏的智能体'" />
          <div v-else class="agent-grid">
            <AgentCard v-for="agent in filteredFavorites" :key="agent.id" :agent="agent" :favorited="true" :is-admin="auth.isAdmin" @click="goToDetail(agent)" @fav="toggleFavorite(agent.id); fetchFavorites()" @deactivate="deactivateAgent(agent.id)" />
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import AgentCard from '@/components/AgentCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import StaggerReveal from '@/components/StaggerReveal.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const agents = ref([])
const loading = ref(true)
const searchQuery = ref('')
let searchTimer = null

const activeTab = ref('explore')
const activeTag = ref('')
const sortBy = ref('latest')
const showAllTags = ref(false)
const favoriteStatus = ref({})
const favorites = ref([])
const myAgents = ref([])
const loadingMine = ref(false)
const usingMineFallback = ref(false)

const tags = [
  { label: '全部', value: '' },
  { label: '办公效率', value: '办公效率' },
  { label: '休闲娱乐', value: '休闲娱乐' },
  { label: '生活服务', value: '生活服务' },
  { label: '内容创作', value: '内容创作' },
  { label: '理财投资', value: '理财投资' },
  { label: '学术研究', value: '学术研究' },
]

const filteredFavorites = computed(() => applySort(filterVisibleAgents(withComputedTags(favorites.value))))
const filteredMyAgents = computed(() => applySort(filterVisibleAgents(withComputedTags(myAgents.value))))
const showMineHint = computed(() => activeTab.value === 'explore' && usingMineFallback.value && agents.value.length > 0)
const listTitle = computed(() => showMineHint.value ? '我的上传记录' : '全部智能体')

const filterVisibleAgents = (items) => {
  let list = [...items]
  const q = searchQuery.value.toLowerCase()
  if (q) list = list.filter(a => (a.name || '').toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q))
  if (activeTag.value) list = list.filter(a => (Array.isArray(a.tags) && a.tags.includes(activeTag.value)) || a.tag === activeTag.value || (a._computedTags || []).includes(activeTag.value))
  return list
}

const withComputedTags = (items) => items.map(a => ({ ...a, _computedTags: computeTags(a) }))

/* Featured 专题卡:取评分最高且有评价的 agent */
const featuredAgent = computed(() => {
  if (usingMineFallback.value) return null
  if (!agents.value || agents.value.length === 0) return null
  const withRating = agents.value.filter(a => a.avg_rating > 0)
  if (withRating.length === 0) return null
  return [...withRating].sort((a, b) => (b.avg_rating * Math.log10(b.review_count + 1)) - (a.avg_rating * Math.log10(a.review_count + 1)))[0]
})

const computeTags = (agent) => {
  const text = ((agent.name || '') + ' ' + (agent.description || '')).toLowerCase()
  const tagOptions = [
    { keywords: ['办公', '效率', '工作', '文档', '表格', 'PPT', 'word', 'excel'], label: '办公效率' },
    { keywords: ['娱乐', '游戏', '音乐', '视频', '电影', '休闲'], label: '休闲娱乐' },
    { keywords: ['生活', '日常', '购物', '外卖', '天气', '日历'], label: '生活服务' },
    { keywords: ['内容', '创作', '写作', '文案', '文章', '小红书', '短视频'], label: '内容创作' },
    { keywords: ['理财', '投资', '股票', '基金', '财务', '记账'], label: '理财投资' },
    { keywords: ['学术', '研究', '论文', '文献', '搜索', '翻译'], label: '学术研究' },
  ]
  const matched = []
  for (const opt of tagOptions) {
    if (opt.keywords.some(k => text.includes(k))) matched.push(opt.label)
  }
  return matched.slice(0, 2)
}

const clearSearch = () => { searchQuery.value = ''; reloadCurrentList() }
const handleSearch = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => reloadCurrentList(), 300) }
const goToDetail = (agent) => {
  if (!agent) return
  const id = typeof agent === 'string' ? agent : agent.id
  if (typeof agent === 'object' && agent._source === 'mine') {
    router.push('/dashboard?tab=my-agents')
    return
  }
  router.push(`/agent/${id}`)
}
const selectTag = (tag) => { activeTag.value = activeTag.value === tag ? '' : tag; reloadCurrentList() }
const setSort = (s) => { sortBy.value = s; if (activeTab.value === 'explore') fetchAgents() }

const readItems = (res) => {
  if (Array.isArray(res)) return res
  if (Array.isArray(res?.items)) return res.items
  if (Array.isArray(res?.data?.items)) return res.data.items
  return []
}

const applySort = (list) => {
  if (sortBy.value === 'latest') {
    list.sort((a, b) => (new Date(b.created_at || 0).getTime() || 0) - (new Date(a.created_at || 0).getTime() || 0))
  } else if (sortBy.value === 'hottest') {
    list.sort((a, b) => {
      const sa = (a.avg_rating || 0) * Math.log10((a.review_count || 0) + 1)
      const sb = (b.avg_rating || 0) * Math.log10((b.review_count || 0) + 1)
      return sb - sa
    })
  } else if (sortBy.value === 'price_asc') {
    list.sort((a, b) => (a.price || 0) - (b.price || 0))
  } else if (sortBy.value === 'price_desc') {
    list.sort((a, b) => (b.price || 0) - (a.price || 0))
  }
  return list
}

const reloadCurrentList = () => {
  if (activeTab.value === 'mine') fetchMyAgents()
  else if (activeTab.value === 'library') fetchFavorites()
  else fetchAgents()
}

const fetchAgents = async () => {
  loading.value = true
  try {
    const res = await api.get('/agent/public/recent', { params: { limit: 50, with_users: true } })
    let list = filterVisibleAgents(withComputedTags(readItems(res)))
    usingMineFallback.value = false
    if (list.length === 0 && auth.isLoggedIn) {
      await fetchMyAgents({ silent: true })
      list = filteredMyAgents.value
      usingMineFallback.value = list.length > 0
    }
    agents.value = applySort(list)
    loadFavoriteStatus()
    loadReviewStats()
  } catch (err) {
    usingMineFallback.value = false
    if (auth.isLoggedIn) {
      await fetchMyAgents({ silent: true })
      const list = applySort(filteredMyAgents.value)
      if (list.length > 0) {
        agents.value = list
        usingMineFallback.value = true
        loadFavoriteStatus()
        return
      }
    }
    toast.error(err.message)
  }
  finally { loading.value = false }
}

const loadFavoriteStatus = () => {
  const stored = localStorage.getItem('favorites')
  favoriteStatus.value = stored ? JSON.parse(stored) : {}
}

const loadReviewStatsFor = (items) => {
  items.forEach(a => {
    const stored = localStorage.getItem(`review_stats_${a.id}`)
    if (stored) {
      const stats = JSON.parse(stored)
      a.avg_rating = stats.avg_rating
      a.review_count = stats.total
    } else {
      a.avg_rating = a.avg_rating || 0
      a.review_count = a.review_count || 0
    }
  })
}

const loadReviewStats = () => loadReviewStatsFor(agents.value)

const toggleFavorite = async (agentId) => {
  if (!auth.isLoggedIn) { toast.warning('请先登录'); return }
  const stored = localStorage.getItem('favorites')
  const favMap = stored ? JSON.parse(stored) : {}
  if (favMap[agentId]) {
    delete favMap[agentId]; toast.success('已取消收藏')
  } else {
    const agent = [...agents.value, ...myAgents.value, ...favorites.value].find(a => a.id === agentId)
    if (agent) {
      favMap[agentId] = { id: agent.id, name: agent.name, description: agent.description, tags: agent.tags, logo_url: agent.logo_url }
      toast.success('已添加收藏')
    }
  }
  localStorage.setItem('favorites', JSON.stringify(favMap))
  favoriteStatus.value = { ...favMap }
}

const fetchFavorites = async () => {
  if (!auth.isLoggedIn) return
  const stored = localStorage.getItem('favorites')
  favorites.value = stored ? Object.values(JSON.parse(stored)) : []
  favorites.value.forEach(a => {
    const statsStored = localStorage.getItem(`review_stats_${a.id}`)
    if (statsStored) {
      const stats = JSON.parse(statsStored)
      a.avg_rating = stats.avg_rating
      a.review_count = stats.total
    } else { a.avg_rating = 0; a.review_count = 0 }
  })
}

const normalizeTags = (value, agent) => {
  if (Array.isArray(value)) return value
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return parsed
    } catch {}
    if (value.includes(',')) return value.split(',').map(t => t.trim()).filter(Boolean)
    return [value]
  }
  return computeTags(agent)
}

const normalizeMineAgent = (agent) => {
  const status = agent.status || agent.approval_status || agent.review_status || agent.lifecycle_status || ''
  return {
    ...agent,
    _source: 'mine',
    status,
    approval_status: agent.approval_status || status,
    owner_name: agent.created_by?.username || auth.username || '我',
    tags: normalizeTags(agent.tags, agent),
  }
}

const fetchMyAgents = async ({ silent = false } = {}) => {
  if (!auth.isLoggedIn) {
    myAgents.value = []
    return
  }
  if (!silent) loadingMine.value = true
  try {
    const res = await api.get('/agent/client', { params: { page_num: 1, page_size: 50, with_users: true, is_deleted: false } })
    myAgents.value = readItems(res).map(normalizeMineAgent)
    loadReviewStatsFor(myAgents.value)
  } catch (err) {
    if (!silent) toast.error(err.message)
    myAgents.value = []
  } finally {
    if (!silent) loadingMine.value = false
  }
}

const switchToExplore = () => { activeTab.value = 'explore'; fetchAgents() }
const switchToLibrary = () => { activeTab.value = 'library'; activeTag.value = ''; fetchFavorites() }
const switchToMine = () => { activeTab.value = 'mine'; activeTag.value = ''; fetchMyAgents() }
const deactivateAgent = async () => { toast.info('下架功能暂未支持') }

onMounted(() => { fetchAgents() })
onUnmounted(() => { clearTimeout(searchTimer) })
</script>

<style scoped>
.section {
  padding: 16px 0 80px;
  background: var(--bg-page);
  min-height: 100vh;
  position: relative;
}
.section::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 200px;
  background: linear-gradient(180deg, rgba(30, 58, 76, 0.04) 0%, transparent 100%);
  pointer-events: none;
}
.container { max-width: 1200px; margin: 0 auto; padding: 0 32px; position: relative; }

/* ===== Hero ===== */
.square-hero {
  text-align: left;
  padding: 24px 0 40px;
  border-bottom: 2px solid var(--accent-blue-d);
  margin-bottom: 40px;
}
.hero-meta-row {
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 12px;
  margin-bottom: 20px;
}
.hero-meta-right {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
}
.hero-meta-right .num {
  font-family: var(--font-editorial);
  font-style: italic; font-weight: 500;
  font-size: 13px;
  color: var(--ink);
  margin-right: 2px;
}
.dot-sep { color: var(--ink-4); }

.hero-title-row {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 24px; flex-wrap: wrap;
  margin-bottom: 16px;
}
.hero-title-square {
  font-family: var(--font-display);
  font-size: clamp(52px, 7vw, 80px);
  font-weight: 700;
  color: var(--ink);
  margin: 0;
  letter-spacing: -0.035em;
  line-height: 1.0;
}
.hero-title-square em {
  font-family: var(--font-editorial);
  font-style: italic; font-weight: 400;
  color: var(--accent);
  font-size: 1.1em;
}

.hero-sub {
  font-size: 17px;
  color: var(--ink-3);
  margin: 0 0 24px 0;
  max-width: 60ch;
  line-height: 1.5;
}
.hero-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.hero-cta {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 14px 28px;
  background: var(--sky-grad-deep); color: var(--ink-inverse);
  border: 1px solid var(--accent-blue-d);
  border-radius: var(--r-3);
  font-size: 15px; font-weight: 600; font-family: inherit;
  cursor: pointer;
  transition: all var(--t-fast);
  box-shadow: 0 4px 12px rgba(46, 122, 184, 0.25);
}
.hero-cta:hover { background: var(--accent-blue-d); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(46, 122, 184, 0.35); }
.hero-cta-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 14px 22px;
  color: var(--ink);
  font-size: 15px; font-weight: 500;
  text-decoration: none;
  border-radius: var(--r-3);
  transition: background var(--t-fast);
}
.hero-cta-ghost:hover { background: var(--bg-card-soft); }

/* ===== Featured 专题卡(浅蓝渐变) ===== */
.featured-card {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 28px;
  align-items: center;
  padding: 28px 32px;
  margin-bottom: 8px;
  background: linear-gradient(135deg, #2E7AB8 0%, #1B5A8E 100%);
  color: var(--ink-inverse);
  border-radius: var(--r-3);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: transform var(--t-base), box-shadow var(--t-base);
  box-shadow: 0 12px 32px -12px rgba(27, 90, 142, 0.35);
}
.featured-card::after {
  content: '';
  position: absolute; right: -60px; top: -60px;
  width: 280px; height: 280px;
  background: radial-gradient(circle, rgba(125, 200, 235, 0.25) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}
.featured-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 48px -12px rgba(27, 90, 142, 0.45);
}
.featured-avatar {
  width: 96px; height: 96px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--r-3);
  color: var(--ink-inverse);
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}
.featured-avatar .avatar-img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }
.featured-body { position: relative; z-index: 1; min-width: 0; }
.featured-meta {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.featured-kicker {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-blue-l);
  padding: 3px 8px;
  background: rgba(46, 122, 184, 0.15);
  border-radius: var(--r-1);
}
.featured-rating {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
  display: flex; align-items: center; gap: 6px;
}
.featured-rating .num {
  font-family: var(--font-editorial);
  font-style: italic; font-weight: 500;
  font-size: 14px;
  color: var(--signal-star);
  letter-spacing: -0.01em;
}
.featured-name {
  font-family: var(--font-display);
  font-size: 28px; font-weight: 600;
  margin: 0 0 8px;
  color: var(--ink-inverse);
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.featured-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin: 0 0 16px;
  max-width: 64ch;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.featured-foot {
  display: flex; align-items: center; gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
}
.featured-author { color: rgba(255, 255, 255, 0.5); font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; }
.featured-author::before { content: 'by '; opacity: 0.6; }
.featured-price { color: var(--ink-inverse); font-weight: 600; }
.featured-free {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--signal-positive);
  padding: 2px 8px;
  background: rgba(16, 185, 129, 0.15);
  border-radius: var(--r-1);
}
.featured-cta {
  margin-left: auto;
  font-size: 13px; font-weight: 500;
  color: var(--accent-blue-l);
  transition: transform var(--t-fast);
}
.featured-card:hover .featured-cta { transform: translateX(4px); }

/* Grid 入场动画 */
.stagger-grid { animation: gridFadeIn 0.5s var(--ease-out) both; }
.stagger-grid > * { opacity: 0; animation: fadeInUp 0.4s var(--ease-out) forwards; }
.stagger-1 { animation-delay: 60ms; }
.stagger-2 { animation-delay: 120ms; }
.stagger-3 { animation-delay: 180ms; }
.stagger-4 { animation-delay: 240ms; }
.stagger-5 { animation-delay: 300ms; }
.stagger-6 { animation-delay: 360ms; }
@keyframes gridFadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

/* ===== Filter bar ===== */
.filter-bar {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 16px; flex-wrap: wrap;
  margin-bottom: 16px;
}
.filter-tools { display: flex; align-items: center; gap: 10px; }
.mine-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: 0 0 18px;
  padding: 12px 14px;
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-left: 3px solid var(--signal-warning);
  border-radius: var(--r-2);
  background: rgba(245, 158, 11, 0.08);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.5;
}
.mine-hint-kicker {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #92400e;
}

/* Library section */
.lib-section { margin-top: 8px; }
.lib-title {
  display: flex; align-items: baseline; gap: 12px;
  font-family: var(--font-display);
  font-size: 22px; font-weight: 600;
  color: var(--ink);
  margin: 0 0 20px; padding-bottom: 12px;
  border-bottom: 1px solid var(--border-card);
  letter-spacing: -0.01em;
}
.lib-num {
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 500;
  color: var(--ink-3);
  letter-spacing: 0.08em;
}

.tag-more-btn { display: none; }

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .section { padding: 8px 0 56px; overflow-x: clip; }
  .container { width: 100%; padding: 0 16px; }
  .square-hero { padding: 20px 0 28px; margin-bottom: 28px; }
  .hero-meta-row { align-items: flex-start; }
  .hero-meta-right { max-width: 100%; flex-wrap: wrap; gap: 6px; letter-spacing: 0.08em; }
  .hero-title-row { flex-direction: column; align-items: flex-start; }
  .hero-title-square { font-size: 36px; letter-spacing: 0; }
  .hero-actions { width: 100%; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .hero-cta, .hero-cta-ghost { min-height: 48px; padding: 12px 14px; justify-content: center; text-align: center; border-radius: 8px; }
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-tools { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .search-wrap { width: 100%; min-width: 0; min-height: 48px; flex: 1; }
  .sort-toggle {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    overflow: visible;
  }
  .sort-toggle button { min-width: 0; min-height: 44px; padding: 0 6px; }
  .tag-filter-bar { align-items: stretch; gap: 8px; }
  .tag-btn { min-height: 44px; padding: 9px 14px; }
  .tag-filter-bar:not(.expanded) .tag-btn.is-extra { display: none; }
  .tag-more-btn {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    padding: 9px 14px;
    border: 1px dashed var(--accent-blue-border);
    border-radius: var(--r-pill);
    background: rgba(255, 255, 255, 0.45);
    color: var(--accent-blue-d);
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .tag-more-btn svg { transition: transform var(--t-fast); }
  .tag-more-btn svg.rotated { transform: rotate(180deg); }
  .agent-grid { width: 100%; grid-template-columns: minmax(0, 1fr) !important; }
  :deep(.agent-card-item) { width: 100%; min-width: 0; }
  .featured-card { grid-template-columns: 1fr; padding: 20px; }
  .featured-avatar { width: 64px; height: 64px; }
  .featured-name { font-size: 22px; }
  .featured-cta { margin-left: 0; }
}
</style>
