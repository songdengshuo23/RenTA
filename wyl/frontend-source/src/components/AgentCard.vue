<template>
  <div class="agent-card-item" @click="$emit('click')">
    <div class="card-top">
      <div class="agent-avatar">
        <img v-if="agent.logo_url" :src="agent.logo_url" class="avatar-img" />
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
      </div>
      <div class="agent-info">
        <h3 class="agent-name">{{ agent.name }}</h3>
        <div class="agent-subline">
          <span class="agent-owner">{{ agent.created_by?.username || agent.owner_name || '官方' }}</span>
          <span v-if="statusBadge" :class="['agent-status-badge', statusBadge.key]" :title="statusBadge.title">
            {{ statusBadge.label }}
          </span>
        </div>
      </div>
      <div class="card-actions">
        <span class="ui-bookmark" :class="{ favorited, animating: favAnimating }" @click.stop>
          <input
            type="checkbox"
            :id="`fav-${agent.id}`"
            :checked="favorited"
            @click.stop
            @change="handleFav"
          />
          <label
            :for="`fav-${agent.id}`"
            class="bookmark"
            :title="favorited ? '取消收藏' : '收藏'"
            @click.stop
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" :fill="favorited ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.8"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
          </label>
        </span>
        <button v-if="isAdmin" class="deactivate-btn" @click.stop="$emit('deactivate')" title="下架智能体">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    </div>

    <div v-if="cardTags.length > 0" class="tag-row">
      <span v-for="t in cardTags" :key="t" class="tag-item">{{ t }}</span>
    </div>

    <div v-if="agent.description" class="agent-desc">{{ agent.description }}</div>

    <div class="card-bottom">
      <div v-if="agent.review_count > 0" class="rating">
        <StarRating :model-value="Math.round(agent.avg_rating || 0)" :readonly="true" :size="13" />
        <span class="rating-score">{{ agent.avg_rating }}</span>
        <span class="rating-count">{{ agent.review_count }} 评价</span>
      </div>
      <div v-else class="no-rating">暂无评价</div>
      <span v-if="agent.price > 0" class="price">{{ agent.price }} <span class="price-unit">积分/次</span></span>
      <span v-else class="free-badge">免费</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import StarRating from '@/components/StarRating.vue'

const props = defineProps({
  agent: { type: Object, required: true },
  favorited: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false }
})

const emit = defineEmits(['click', 'fav', 'deactivate'])

const favAnimating = ref(false)

const handleFav = () => {
  favAnimating.value = true
  emit('fav')
  setTimeout(() => favAnimating.value = false, 400)
}

const statusBadge = computed(() => {
  const raw = props.agent.status || props.agent.approval_status || props.agent.review_status || ''
  const key = String(raw).toLowerCase()
  const map = {
    approved: { key: 'approved', label: '已上线', title: 'Supervisor 已审核通过,可在公开广场展示' },
    pending: { key: 'pending', label: '待审核', title: '已提交 supervisor 审核,通过后进入公开广场' },
    rejected: { key: 'rejected', label: '未通过', title: 'Supervisor 审核未通过' },
    draft: { key: 'draft', label: '草稿', title: '尚未提交审核' },
  }
  if (map[key]) return map[key]
  if (props.agent.is_deleted) return { key: 'rejected', label: '已删除', title: '该智能体已被删除' }
  if (props.agent._source === 'mine' && props.agent.is_active === false) {
    return { key: 'draft', label: '未启用', title: '该智能体当前未启用' }
  }
  return null
})

const cardTags = computed(() => {
  const a = props.agent
  if (Array.isArray(a.tags) && a.tags.length > 0) return a.tags.slice(0, 3)
  if (typeof a.tags === 'string' && a.tags.trim()) {
    try { const parsed = JSON.parse(a.tags); if (Array.isArray(parsed)) return parsed.slice(0, 3) } catch {}
    if (a.tags.includes(',')) return a.tags.split(',').map(t => t.trim()).filter(Boolean).slice(0, 3)
    return [a.tags]
  }
  if (a.tag) return [a.tag]
  const text = ((a.name || '') + ' ' + (a.description || '')).toLowerCase()
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
})
</script>

<style scoped>
.agent-card-item {
  position: relative;
  width: 100%;
  min-width: 0;
  padding: 22px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  cursor: pointer;
  transition: all var(--t-base);
  display: flex; flex-direction: column;
  gap: 14px;
  overflow: hidden;
}
.agent-card-item:hover {
  border-color: var(--ink);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.card-top { display: flex; align-items: center; gap: 12px; }
.agent-avatar {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  color: var(--ink-2);
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}
.avatar-img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }

.agent-info { flex: 1; min-width: 0; }
.agent-name {
  font-family: var(--font-display);
  font-size: 15px; font-weight: 600;
  color: var(--ink);
  margin: 0 0 2px;
  letter-spacing: -0.01em;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.agent-owner {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3);
}
.agent-subline {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}
.agent-status-badge {
  display: inline-flex;
  align-items: center;
  max-width: 88px;
  padding: 2px 7px;
  border: 1px solid var(--border-card);
  border-radius: var(--r-1);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.08em;
  white-space: nowrap;
}
.agent-status-badge.approved {
  color: #047857;
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.28);
}
.agent-status-badge.pending {
  color: #92400e;
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.30);
}
.agent-status-badge.rejected {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.28);
}
.agent-status-badge.draft {
  color: var(--ink-3);
  background: var(--bg-card-soft);
  border-color: var(--border-card);
}

.card-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.deactivate-btn {
  display: flex; align-items: center; justify-content: center;
  width: 32px; height: 32px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  transition: all var(--t-fast);
}
.deactivate-btn:hover { color: var(--signal-warning); background: var(--signal-warning-soft); }

/* ============================================================
   收藏按钮 (Uiverse 风格 — 8 方向粒子 + 心形弹性 + 圆环涟漪)
============================================================ */
.ui-bookmark {
  --icon-size: 24px;
  --icon-secondary-color: var(--ink-3);
  --icon-hover-color: var(--signal-favorite);
  --icon-primary-color: var(--signal-favorite);
  --icon-circle-border: 1px solid var(--icon-primary-color);
  --icon-circle-size: 32px;
  --icon-anmt-duration: 0.4s;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  flex-shrink: 0;
}
.ui-bookmark input {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.ui-bookmark input:focus-visible + .bookmark {
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
  border-radius: 50%;
}
.ui-bookmark .bookmark {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--icon-size); height: var(--icon-size);
  cursor: pointer;
  color: var(--icon-secondary-color);
  fill: var(--icon-secondary-color);
  transition: color 0.2s;
  z-index: 1;
}

/* 8 方向 box-shadow 粒子 ::after — 点击时炸开 */
.ui-bookmark .bookmark::after {
  content: "";
  position: absolute;
  inset: 0;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: transparent;
  box-shadow:
    0 16px 0 -4px var(--icon-primary-color),
    16px 0 0 -4px var(--icon-primary-color),
    0 -16px 0 -4px var(--icon-primary-color),
    -16px 0 0 -4px var(--icon-primary-color),
    -12px 12px 0 -4px var(--icon-primary-color),
    -12px -12px 0 -4px var(--icon-primary-color),
    12px -12px 0 -4px var(--icon-primary-color),
    12px 12px 0 -4px var(--icon-primary-color);
  transform: scale(0);
  pointer-events: none;
  z-index: 0;
}

/* 圆环涟漪 ::before — 选中时扩散 */
.ui-bookmark .bookmark::before {
  content: "";
  position: absolute;
  inset: 0;
  margin: auto;
  width: 0; height: 0;
  border-radius: 50%;
  border: var(--icon-circle-border);
  opacity: 0;
  pointer-events: none;
  z-index: 0;
}

/* hover 状态 */
.ui-bookmark:hover .bookmark { color: var(--icon-hover-color); fill: var(--icon-hover-color); }

/* 选中 (favorited=true) — 心形填充 + 弹性回弹 */
.ui-bookmark.favorited .bookmark {
  color: var(--icon-primary-color);
  fill: var(--icon-primary-color);
  animation: bookmarkBounce var(--icon-anmt-duration) cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
  animation-delay: 0.15s;
  filter: drop-shadow(0 0 6px rgba(199, 62, 90, 0.35));
}
.ui-bookmark.favorited .bookmark::after {
  animation: bookmarkCircles var(--icon-anmt-duration) cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
  animation-delay: var(--icon-anmt-duration);
}
.ui-bookmark.favorited .bookmark::before {
  animation: bookmarkRing var(--icon-anmt-duration) cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
  animation-delay: var(--icon-anmt-duration);
}

/* 外层 wrapper 心跳 (保留原有 favAnimating 行为) */
.ui-bookmark.animating { animation: favPulse 0.4s var(--ease); }

@keyframes favPulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.2); } }
@keyframes bookmarkBounce {
  50%  { transform: scaleY(0.6); }
  100% { transform: scaleY(1); }
}
@keyframes bookmarkRing {
  from { width: 0; height: 0; opacity: 0; }
  90% { width: var(--icon-circle-size); height: var(--icon-circle-size); opacity: 1; }
  to   { opacity: 0; }
}
@keyframes bookmarkCircles {
  from { transform: scale(0); }
  40% { opacity: 1; }
  to   { transform: scale(0.9); opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .ui-bookmark.animating,
  .ui-bookmark.favorited .bookmark,
  .ui-bookmark.favorited .bookmark::after,
  .ui-bookmark.favorited .bookmark::before {
    animation: none !important;
  }
}

.tag-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-item {
  display: inline-flex; align-items: center;
  font-size: 10px; font-weight: 500; letter-spacing: 0.06em;
  color: var(--ink-2);
  padding: 2px 8px;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-1);
}

.agent-desc {
  font-size: 13px; line-height: 1.5;
  color: var(--ink-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

@media (max-width: 768px) {
  .agent-card-item { padding: 18px; }
  .card-top { min-width: 0; }
  .ui-bookmark { width: 44px; height: 44px; }
  .deactivate-btn { width: 44px; height: 44px; }
}

.card-bottom {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: 12px;
  margin-top: auto;
  border-top: 1px solid var(--border-divider);
}
.rating { display: flex; align-items: center; gap: 6px; }
.rating-score {
  font-family: var(--font-editorial);
  font-size: 14px; font-style: italic; font-weight: 500;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.rating-count {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em;
  color: var(--ink-3);
}
.no-rating { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-4); }

.price {
  font-family: var(--font-editorial);
  font-size: 18px; font-style: italic; font-weight: 400;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}
.price-unit {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
  font-style: normal;
  margin-left: 2px;
}
.free-badge {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--signal-positive);
}
</style>
