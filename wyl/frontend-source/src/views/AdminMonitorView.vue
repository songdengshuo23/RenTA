<template>
  <div class="container" v-if="auth.isAdmin">
    <StaggerReveal :delay="80" :initial-delay="40">
      <div class="page-header">
        <div>
          <span class="page-issue">Admin · 流量监控</span>
          <h1 class="page-title">实时流量</h1>
          <p class="page-desc">直接读取编排端流量快照，展示平台上所有路由到 mode2 任务的 tokens/s、Top 发送端和最近消息流向。</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-primary btn-sm action-btn" @click="refreshStats(true)" :disabled="loading">
            <span class="action-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 1 1-3-6.7" />
                <polyline points="21 3 21 9 15 9" />
              </svg>
            </span>
            <span>立即刷新</span>
          </button>
          <button class="btn btn-secondary btn-sm action-btn" @click="togglePolling">
            <span class="action-icon" aria-hidden="true">
              <svg v-if="polling" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="6" y="5" width="4" height="14" rx="1" />
                <rect x="14" y="5" width="4" height="14" rx="1" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="8,5 19,12 8,19" />
              </svg>
            </span>
            <span>{{ polling ? '暂停刷新' : '继续刷新' }}</span>
          </button>
          <span class="auto-refresh">
            <span class="dot" :class="{ active: polling && !loading }"></span>
            {{ polling ? '每 5 秒刷新' : '已暂停' }}
          </span>
        </div>
      </div>

      <div class="overview-row">
        <div class="overview-card">
          <div class="ov-label">窗口 TPS</div>
          <div class="ov-value" ref="globalTpsRef">0</div>
          <div class="ov-foot">{{ windowLabel }}</div>
        </div>
        <div class="overview-card">
          <div class="ov-label">窗口 Tokens</div>
          <div class="ov-value" ref="windowTokensRef">0</div>
          <div class="ov-foot">最近60秒</div>
        </div>
        <div class="overview-card">
          <div class="ov-label">活跃对象</div>
          <div class="ov-value" ref="activeAgentRef">0</div>
          <div class="ov-foot">发送 / 接收 / 边</div>
        </div>
        <div class="overview-card">
          <div class="ov-label">平台 TPS</div>
          <div class="ov-value" ref="platformTpsRef">0</div>
          <div class="ov-foot">{{ mode2Label }}</div>
        </div>
      </div>

      <div class="overview-row secondary-row">
        <div class="overview-card stat-card">
          <div class="ov-label">总消息数</div>
          <div class="ov-value small" ref="messagesRef">0</div>
          <div class="ov-foot">{{ lastUpdatedLabel }}</div>
        </div>
        <div class="overview-card stat-card">
          <div class="ov-label">最近事件</div>
          <div class="ov-value small" ref="eventsRef">0</div>
          <div class="ov-foot">最近 20 条</div>
        </div>
        <div class="overview-card stat-card">
          <div class="ov-label">Top 发送端</div>
          <div class="ov-value small ellipsis-value" :title="topSenderName || ''">{{ topSenderDisplayName || '—' }}</div>
          <div class="ov-foot">{{ topSenderTokensLabel }}</div>
        </div>
        <div class="overview-card stat-card">
          <div class="ov-label">Top 接收端</div>
          <div class="ov-value small ellipsis-value" :title="topReceiverName || ''">{{ topReceiverDisplayName || '—' }}</div>
          <div class="ov-foot">{{ topReceiverTokensLabel }}</div>
        </div>
      </div>

      <div class="traffic-grid">
        <section class="monitor-card monitor-card-chart">
          <div class="card-header compact-header">
            <h2 class="card-title">实时趋势</h2>
            <span class="card-count">{{ chartSeriesNames.length }} 条曲线</span>
          </div>
          <div class="chart-toolbar">
            <div class="chart-tabs">
              <button
                v-for="m in [5, 15, 30]"
                :key="m"
                class="time-btn"
                :class="{ active: timeRange === m }"
                @click="timeRange = m"
              >
                {{ m }}分钟
              </button>
            </div>
            <span class="chart-note">基于最近轮询快照采样</span>
          </div>
          <div class="chart-wrapper"><canvas ref="chartCanvas"></canvas></div>
          <div v-if="!hasHistory" class="chart-empty-hint">暂无快照，页面会在首次刷新后开始绘制</div>
        </section>

        <section class="monitor-card monitor-card-list">
          <div class="card-header compact-header">
            <h2 class="card-title">Top 流量</h2>
            <span class="card-count">{{ topFlows.length }} 项</span>
          </div>
          <div class="flow-list" v-if="topFlows.length">
            <div class="flow-item" v-for="(item, index) in topFlows" :key="item.key">
              <div class="flow-rank" :class="{ top: index < 3 }">{{ index + 1 }}</div>
              <div class="flow-body">
                <div class="flow-title-row">
                  <span class="flow-name">{{ item.label }}</span>
                  <span class="flow-metric">{{ formatRate(item.tps) }} TPS</span>
                </div>
                <div class="flow-bar-wrap">
                  <div class="flow-bar" :class="'bar-' + (index % 5)" :style="{ width: flowWidth(item.tps) }"></div>
                </div>
                <div class="flow-subline">{{ item.detail }}</div>
              </div>
            </div>
          </div>
          <EmptyState v-else message="暂无 Top 流量" description="等有真实调用后，这里会出现发送端、接收端和边的排行。" />
        </section>
      </div>

      <section class="monitor-card monitor-card-table">
        <div class="card-header compact-header">
          <h2 class="card-title">最近事件</h2>
          <span class="card-count">{{ recentEvents.length }} 条</span>
        </div>
        <div class="event-table" v-if="recentEvents.length">
          <div class="event-head event-row">
            <span>时间</span>
            <span>流向</span>
            <span>Tokens</span>
            <span>类型</span>
          </div>
          <div class="event-row" v-for="event in recentEvents" :key="event.id">
            <span class="event-time">{{ event.timeLabel }}</span>
            <span class="event-flow">{{ event.flowLabel }}</span>
            <span class="event-tokens">{{ formatNumber(event.tokens) }}</span>
            <span class="event-type">{{ event.edgeType }}</span>
          </div>
        </div>
        <EmptyState v-else message="暂无最近事件" description="编排端记录到新的 agent 消息后，这里会实时滚动更新。" />
      </section>
    </StaggerReveal>
  </div>

  <div class="container" v-else><EmptyState message="无权限访问此页面" /></div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import { modeRouterApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import EmptyState from '@/components/EmptyState.vue'
import StaggerReveal from '@/components/StaggerReveal.vue'

Chart.register(...registerables)

const auth = useAuthStore()
const toast = useToastStore()
const loading = ref(false)
const polling = ref(true)
const timeRange = ref(15)
const chartCanvas = ref(null)
const chartHistory = ref([])
const snapshot = ref(null)
const platformSnapshot = ref(null)
const currentSeriesKeys = ref([])
let chartInstance = null
let pollTimer = null
let stopWatch = null
let updateSeq = 0

const globalTpsRef = ref(null)
const windowTokensRef = ref(null)
const activeAgentRef = ref(null)
const platformTpsRef = ref(null)
const messagesRef = ref(null)
const eventsRef = ref(null)
const animated = { globalTps: 0, windowTokens: 0, activeAgents: 0, platformTps: 0, messages: 0, events: 0 }
const rafIds = { globalTps: 0, windowTokens: 0, activeAgents: 0, platformTps: 0, messages: 0, events: 0 }

const COLORS = ['#1B5A8E', '#2E7AB8', '#10b981', '#f59e0b', '#d4906a', '#8b5cf6', '#06b6d4', '#f97316']
const POLL_SECONDS = 5
const MAX_HISTORY_MINUTES = 30
const MAX_HISTORY_SAMPLES = (MAX_HISTORY_MINUTES * 60) / POLL_SECONDS

const windowSeconds = computed(() => Number(snapshot.value?.window_seconds || 60))
const windowLabel = computed(() => '实时')
const mode2Label = computed(() => {
  if (!platformSnapshot.value) return '等待编排端响应'
  return `累计 ${formatNumber(mode2TotalTokens.value)} tokens`
})
const lastUpdatedLabel = computed(() => {
  if (!snapshot.value?.captured_at) return '尚未刷新'
  return `更新时间 ${formatTime(snapshot.value.captured_at)}`
})
const hasHistory = computed(() => chartHistory.value.length > 0)
const chartSeriesNames = computed(() => {
  const names = new Set(['global_tps', 'platform_tps'])
  currentSeriesKeys.value.forEach((name) => names.add(name))
  return Array.from(names)
})
const mode2TopSenders = computed(() => {
  const cumulative = normalizePartyStats(platformSnapshot.value?.top_senders || [], 'tps_since_start')
  return cumulative.length ? cumulative : normalizePartyStats(snapshot.value?.top_senders || [], 'tps')
})
const mode2TopReceivers = computed(() => {
  const cumulative = normalizePartyStats(platformSnapshot.value?.top_receivers || [], 'tps_since_start')
  return cumulative.length ? cumulative : normalizePartyStats(snapshot.value?.top_receivers || [], 'tps')
})
const mode2Edges = computed(() => {
  const cumulative = normalizeEdges(platformSnapshot.value?.edges || [], 'tps_since_start')
  return cumulative.length ? cumulative : normalizeEdges(snapshot.value?.edges || [], 'tps')
})
const mode2TotalTokens = computed(() => Number(platformSnapshot.value?.tokens_total || snapshot.value?.tokens_total_since_reset || 0))
const mode2TotalMessages = computed(() => Number(platformSnapshot.value?.messages_total || snapshot.value?.records_total_since_reset || 0))
const topSenderName = computed(() => mode2TopSenders.value[0]?.agent || null)
const topSenderDisplayName = computed(() => shortenAgentName(topSenderName.value))
const topSenderTokensLabel = computed(() => {
  const item = mode2TopSenders.value[0]
  if (!item) return '暂无数据'
  return `${formatNumber(item.tokens_total || 0)} tokens`
})
const topReceiverName = computed(() => mode2TopReceivers.value[0]?.agent || null)
const topReceiverDisplayName = computed(() => shortenAgentName(topReceiverName.value))
const topReceiverTokensLabel = computed(() => {
  const item = mode2TopReceivers.value[0]
  if (!item) return '暂无数据'
  return `${formatNumber(item.tokens_total || 0)} tokens`
})

const totalMessages = computed(() => mode2TotalMessages.value)
const totalTokens = computed(() => Number(snapshot.value?.global_tokens_total || 0))
const activeAgents = computed(() => collectAgents(snapshot.value).size)
const platformTps = computed(() => Number(platformSnapshot.value?.tps_since_start || 0))
const topFlowCap = computed(() => {
  const values = [
    ...(mode2TopSenders.value.map((item) => Number(item.tps || 0))),
    ...(mode2TopReceivers.value.map((item) => Number(item.tps || 0))),
    ...(mode2Edges.value.map((item) => Number(item.tps || 0)))
  ]
  return Math.max(...values, 1)
})

const topFlows = computed(() => {
  const flows = []
  const seen = new Set()
  ;(mode2TopSenders.value || []).slice(0, 4).forEach((item) => {
    const key = `sender:${item.agent}`
    seen.add(key)
    flows.push({
      key,
      label: item.agent,
      detail: `${formatNumber(item.tokens_total || 0)} tokens · 发送端`,
      tps: Number(item.tps || 0)
    })
  })
  ;(mode2TopReceivers.value || []).slice(0, 3).forEach((item) => {
    const key = `receiver:${item.agent}`
    if (seen.has(key)) return
    seen.add(key)
    flows.push({
      key,
      label: item.agent,
      detail: `${formatNumber(item.tokens_total || 0)} tokens · 接收端`,
      tps: Number(item.tps || 0)
    })
  })
  ;(mode2Edges.value || []).slice(0, 4).forEach((item) => {
    const key = `edge:${item.from}->${item.to}`
    if (seen.has(key)) return
    flows.push({
      key,
      label: `${item.from} → ${item.to}`,
      detail: `${formatNumber(item.tokens_total || 0)} tokens · ${Number(item.messages_total || 0)} 条消息`,
      tps: Number(item.tps || 0)
    })
  })
  return flows.slice(0, 8)
})

const recentEvents = computed(() => {
  return (snapshot.value?.last_events || []).slice().reverse().map((event, index) => ({
    id: `${event.time || index}-${event.source || 'src'}-${event.target || 'dst'}-${index}`,
    timeLabel: formatTime(event.time),
    flowLabel: `${event.source || 'unknown'} → ${event.target || 'unknown'}`,
    tokens: Number(event.tokens || 0),
    edgeType: event.edge_type || 'unknown'
  })).slice(0, 10)
})

const chartSampleCount = computed(() => Math.max(1, Math.floor((timeRange.value * 60) / POLL_SECONDS)))

function animateCount(key, fromVal, toVal, el, formatter) {
  if (!el?.value) return
  cancelAnimationFrame(rafIds[key])
  animated[key] = fromVal
  const start = performance.now()
  const duration = 900
  const ease = (t) => 1 - Math.pow(1 - t, 3)
  const tick = (now) => {
    const p = Math.min(1, (now - start) / duration)
    animated[key] = fromVal + (toVal - fromVal) * ease(p)
    el.value.textContent = formatter ? formatter(animated[key]) : formatNumber(animated[key])
    if (p < 1) rafIds[key] = requestAnimationFrame(tick)
  }
  rafIds[key] = requestAnimationFrame(tick)
}

function updateAnimatedSummary() {
  animateCount('globalTps', animated.globalTps, Number(snapshot.value?.global_tps || 0), globalTpsRef, (v) => formatRate(v))
  animateCount('windowTokens', animated.windowTokens, totalTokens.value, windowTokensRef, (v) => formatNumber(v))
  animateCount('activeAgents', animated.activeAgents, activeAgents.value, activeAgentRef, (v) => formatNumber(v))
  animateCount('platformTps', animated.platformTps, platformTps.value, platformTpsRef, (v) => formatRate(v))
  animateCount('messages', animated.messages, totalMessages.value, messagesRef, (v) => formatNumber(v))
  animateCount('events', animated.events, recentEvents.value.length, eventsRef, (v) => formatNumber(v))
}

function collectAgents(current) {
  const names = new Set()
  if (!current) return names
  ;(current.top_senders || []).forEach((item) => {
    if (item?.agent) names.add(item.agent)
  })
  ;(current.top_receivers || []).forEach((item) => {
    if (item?.agent) names.add(item.agent)
  })
  ;(current.edges || []).forEach((item) => {
    if (item?.from) names.add(item.from)
    if (item?.to) names.add(item.to)
  })
  ;(current.last_events || []).forEach((item) => {
    if (item?.source) names.add(item.source)
    if (item?.target) names.add(item.target)
  })
  return names
}

function normalizePartyStats(items, rateKey = 'tps') {
  if (!Array.isArray(items)) return []
  return items.map((item) => ({
    agent: item.agent || item.name || 'unknown',
    tokens_total: Number(item.tokens_total || 0),
    messages_total: Number(item.messages_total || 0),
    tps: Number(item[rateKey] || item.tps || item.tps_since_start || 0)
  })).sort((a, b) => b.tokens_total - a.tokens_total)
}

function normalizeEdges(items, rateKey = 'tps') {
  if (!Array.isArray(items)) return []
  return items.map((item) => ({
    from: item.from || item.source || 'unknown',
    to: item.to || item.target || 'unknown',
    tokens_total: Number(item.tokens_total || 0),
    messages_total: Number(item.messages_total || 0),
    tps: Number(item[rateKey] || item.tps || item.tps_since_start || 0)
  })).sort((a, b) => b.tokens_total - a.tokens_total)
}

function shortenAgentName(name) {
  const text = String(name || '')
  if (!text) return ''
  const parts = text.split('.')
  if (parts.length > 6) return `${parts.slice(0, 6).join('.')}...`
  return text.length > 28 ? `${text.slice(0, 28)}...` : text
}

function normalizeSnapshot(data) {
  const base = data || {}
  const now = new Date().toISOString()
  const topSenders = Array.isArray(base.top_senders) ? base.top_senders : []
  const topReceivers = Array.isArray(base.top_receivers) ? base.top_receivers : []
  const edges = Array.isArray(base.edges) ? base.edges : []
  const lastEvents = Array.isArray(base.last_events) ? base.last_events : []
  const uniqueAgents = collectAgents(base)
  return {
    captured_at: base.captured_at || now,
    enabled: Boolean(base.enabled),
    global_tps: Number(base.global_tps || 0),
    global_tokens_total: Number(base.global_tokens_total || 0),
    messages_total: Number(base.messages_total || 0),
    window_seconds: Number(base.window_seconds || 60),
    records_total_since_reset: Number(base.records_total_since_reset || 0),
    tokens_total_since_reset: Number(base.tokens_total_since_reset || 0),
    edges: edges.map((item) => ({
      from: item.from || 'unknown',
      to: item.to || 'unknown',
      tokens_total: Number(item.tokens_total || 0),
      messages_total: Number(item.messages_total || 0),
      tps: Number(item.tps || 0)
    })),
    top_senders: topSenders.map((item) => ({
      agent: item.agent || 'unknown',
      tokens_total: Number(item.tokens_total || 0),
      tps: Number(item.tps || 0)
    })),
    top_receivers: topReceivers.map((item) => ({
      agent: item.agent || 'unknown',
      tokens_total: Number(item.tokens_total || 0),
      tps: Number(item.tps || 0)
    })),
    last_events: lastEvents.map((item) => ({
      time: item.time || now,
      source: item.source || 'unknown',
      target: item.target || 'unknown',
      tokens: Number(item.tokens || 0),
      edge_type: item.edge_type || item.edgeType || 'unknown',
      session_id: item.session_id || '',
      execution_id: item.execution_id || '',
      route_mode: item.route_mode || item.mode || 'unknown'
    })),
    unique_agents: Array.from(uniqueAgents)
  }
}

function toPlatformSnapshot(data) {
  const base = data || {}
  return {
    scope: base.scope || 'all_mode2_tasks_since_process_start',
    tokens_total: Number(base.tokens_total || 0),
    messages_total: Number(base.messages_total || 0),
    uptime_seconds: Number(base.uptime_seconds || 0),
    tps_since_start: Number(base.tps_since_start || 0),
    modes: Array.isArray(base.modes) ? base.modes : [],
    edges: Array.isArray(base.edges) ? base.edges : [],
    edge_types: Array.isArray(base.edge_types) ? base.edge_types : [],
    top_senders: Array.isArray(base.top_senders) ? base.top_senders : [],
    top_receivers: Array.isArray(base.top_receivers) ? base.top_receivers : [],
    sessions: Array.isArray(base.sessions) ? base.sessions : [],
    executions: Array.isArray(base.executions) ? base.executions : [],
    window: base.window || {}
  }
}

function appendHistory(current) {
  if (!current) return
  const sample = {
    at: current.captured_at || new Date().toISOString(),
    global_tps: Number(current.global_tps || 0),
    global_tokens_total: Number(current.global_tokens_total || 0),
    messages_total: Number(current.messages_total || 0),
    platform_tps: Number(platformSnapshot.value?.tps_since_start || 0),
    series: {}
  }
  current.top_senders.forEach((item) => {
    sample.series[item.agent] = Number(item.tps || 0)
  })
  chartHistory.value.push(sample)
  const seen = new Set()
  const keys = []
  for (const item of chartHistory.value) {
    Object.keys(item.series).forEach((key) => {
      if (!seen.has(key)) {
        seen.add(key)
        keys.push(key)
      }
    })
  }
  currentSeriesKeys.value = keys.slice(0, 3)
  if (chartHistory.value.length > MAX_HISTORY_SAMPLES) {
    chartHistory.value = chartHistory.value.slice(-MAX_HISTORY_SAMPLES)
  }
}

async function refreshStats(force = false) {
  const seq = ++updateSeq
  if (force) loading.value = true
  try {
    const [snapshotResult, platformResult] = await Promise.allSettled([
      modeRouterApi.get('/traffic/snapshot'),
      modeRouterApi.get('/traffic/mode2')
    ])
    if (snapshotResult.status === 'rejected') throw snapshotResult.reason
    if (seq !== updateSeq) return
    const rawSnapshot = snapshotResult.value || {}
    snapshot.value = normalizeSnapshot(rawSnapshot)
    platformSnapshot.value = platformResult.status === 'fulfilled'
      ? toPlatformSnapshot(platformResult.value)
      : toPlatformSnapshot(rawSnapshot.platform_mode2_group_chat || {})
    appendHistory(snapshot.value)
    await nextTick()
    renderChart()
    updateAnimatedSummary()
  } catch (err) {
    toast.error(err.message || '获取流量快照失败')
  } finally {
    if (force) loading.value = false
  }
}

function renderChart() {
  if (!chartCanvas.value) return
  const samples = chartHistory.value.slice(-chartSampleCount.value)
  if (!samples.length) return
  const labels = samples.map((item) => formatTime(item.at, true))
  const datasets = [
    {
      label: 'global_tps',
      data: samples.map((item) => round1(item.global_tps)),
      borderColor: COLORS[0],
      backgroundColor: COLORS[0] + '22',
      borderWidth: 2,
      tension: 0.28,
      pointRadius: 2,
      pointHoverRadius: 4,
      fill: false
    },
    {
      label: 'platform_tps',
      data: samples.map((item) => round1(item.platform_tps)),
      borderColor: COLORS[2],
      backgroundColor: COLORS[2] + '22',
      borderWidth: 2,
      tension: 0.28,
      pointRadius: 2,
      pointHoverRadius: 4,
      fill: false
    }
  ]
  currentSeriesKeys.value.forEach((name, index) => {
    datasets.push({
      label: name,
      data: samples.map((item) => round1(item.series[name] || 0)),
      borderColor: COLORS[(index + 3) % COLORS.length],
      backgroundColor: COLORS[(index + 3) % COLORS.length] + '22',
      borderWidth: 2,
      tension: 0.28,
      pointRadius: 2,
      pointHoverRadius: 4,
      fill: false
    })
  })

  if (chartInstance) {
    chartInstance.data.labels = labels
    chartInstance.data.datasets = datasets
    chartInstance.update('none')
    return
  }

  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: 'rgba(14, 42, 71, 0.75)',
            padding: 14,
            usePointStyle: true,
            pointStyleWidth: 8
          }
        },
        tooltip: {
          backgroundColor: '#fff',
          titleColor: '#171A20',
          bodyColor: '#5C5E62',
          borderColor: '#eee',
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: 'rgba(0,0,0,0.4)', font: { size: 11 }, maxTicksLimit: 10 }
        },
        y: {
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: 'rgba(0,0,0,0.4)', font: { size: 11 }, callback: (v) => (v === 0 ? '0' : v) },
          beginAtZero: true,
          title: { display: true, text: 'TPS', color: 'rgba(0,0,0,0.4)' }
        }
      }
    }
  })
}

function togglePolling() {
  polling.value ? stopPolling() : startPolling()
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  polling.value = true
  pollTimer = setInterval(() => refreshStats(false), POLL_SECONDS * 1000)
}

function stopPolling() {
  polling.value = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function flowWidth(val) {
  return `${(Number(val || 0) / topFlowCap.value) * 100}%`
}

function formatRate(value) {
  return `${Number(value || 0).toFixed(1)}`
}

function formatNumber(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? Math.round(num).toLocaleString() : '0'
}

function round1(value) {
  return Math.round(Number(value || 0) * 10) / 10
}

function formatTime(value, compact = false) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return compact ? `${hh}:${mm}:${ss}` : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${hh}:${mm}:${ss}`
}

onMounted(async () => {
  if (auth.isAdmin) {
    await refreshStats(true)
    startPolling()
    stopWatch = watch(timeRange, async () => {
      await nextTick()
      renderChart()
    })
  }
})

onUnmounted(() => {
  stopPolling()
  if (stopWatch) stopWatch()
  if (chartInstance) chartInstance.destroy()
  Object.values(rafIds).forEach((id) => cancelAnimationFrame(id))
})
</script>

<style scoped>
.container { padding: 48px 32px 96px; max-width: 1280px; margin: 0 auto; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
  margin-bottom: 32px; padding-bottom: 24px;
  border-bottom: 2px solid var(--ink);
  flex-wrap: wrap;
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
  font-size: clamp(32px, 4vw, 40px);
  font-weight: 600; color: var(--ink);
  letter-spacing: -0.025em;
  margin: 12px 0 0;
}
.page-desc { font-size: 14px; color: var(--ink-3); margin: 8px 0 0; max-width: 70ch; }
.header-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.action-btn { min-width: 120px; }
.action-icon {
  width: 14px; height: 14px;
  display: inline-flex; align-items: center; justify-content: center;
}
.action-icon svg {
  width: 14px; height: 14px;
}
.auto-refresh {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-3);
}
.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--ink-4);
  transition: background var(--t-fast);
}
.dot.active {
  background: var(--signal-positive);
  animation: pulseDot 1.5s ease-in-out infinite;
}
@keyframes pulseDot { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(0.7); opacity: 0.5; } }

.overview-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.secondary-row { margin-top: 0; }
.overview-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 22px 24px;
  transition: all var(--t-fast);
  position: relative;
  min-width: 0;
}
.overview-card:hover {
  border-color: var(--accent-blue-d);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
.ov-label {
  font-family: var(--font-mono);
  font-size: 12px; font-weight: 600;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-3);
  margin-bottom: 18px;
  line-height: 1.25;
}
.ov-value {
  font-family: var(--font-editorial);
  font-size: 40px; font-weight: 400; font-style: italic;
  color: var(--ink);
  line-height: 1;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  min-height: 1em;
  max-width: 100%;
}
.ov-value.small { font-size: 32px; }
.ellipsis-value {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ov-foot {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3);
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-card);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.traffic-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.95fr);
  gap: 16px;
  margin-top: 16px;
}
.monitor-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 24px;
  min-width: 0;
}
.compact-header { align-items: center; margin-bottom: 18px; }
.chart-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
}
.chart-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.chart-note {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-4);
}
.time-btn {
  padding: 6px 14px;
  border: 1px solid var(--border-card);
  background: var(--bg-card);
  color: var(--ink-3);
  border-radius: var(--r-1);
  cursor: pointer;
  font-size: 13px; font-family: inherit;
  transition: all var(--t-fast);
}
.time-btn:hover, .time-btn.active { border-color: var(--accent-blue-d); color: var(--ink); }
.time-btn.active { background: var(--sky-grad-deep); color: var(--ink-inverse); box-shadow: 0 2px 8px rgba(46, 122, 184, 0.22); }
.chart-wrapper { position: relative; height: 320px; }
.chart-empty-hint { text-align: center; color: var(--ink-4); font-size: 14px; padding: 20px 0 0; }

.flow-list { display: flex; flex-direction: column; gap: 14px; }
.flow-item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.flow-rank {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono);
  font-size: 12px; font-weight: 600;
  color: var(--ink-3);
  background: var(--bg-card-soft);
  border-radius: var(--r-1);
}
.flow-rank.top { background: var(--sky-grad-deep); color: var(--ink-inverse); box-shadow: 0 2px 8px rgba(46, 122, 184, 0.22); }
.flow-body { min-width: 0; }
.flow-title-row {
  display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  margin-bottom: 8px;
}
.flow-name {
  font-size: 14px; font-weight: 500; color: var(--ink);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.flow-metric {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-2);
  white-space: nowrap;
}
.flow-bar-wrap { height: 4px; background: var(--bg-card-soft); border-radius: 2px; overflow: hidden; }
.flow-bar { height: 100%; border-radius: 2px; transition: width 0.5s var(--ease-out); }
.bar-0 { background: var(--sky-grad-deep); }
.bar-1 { background: var(--accent); }
.bar-2 { background: var(--signal-warning); }
.bar-3 { background: var(--signal-positive); }
.bar-4 { background: var(--ink-3); }
.flow-subline {
  margin-top: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-3);
}

.event-table { display: flex; flex-direction: column; gap: 0; }
.event-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) 120px 120px;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-divider);
  align-items: center;
}
.event-row span { min-width: 0; }
.event-head {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-3);
  padding-top: 0;
}
.event-time,
.event-flow,
.event-type,
.event-tokens {
  font-size: 13px;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-tokens,
.event-type {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.event-row:last-child { border-bottom: none; }

.monitor-card-table { margin-top: 16px; }

@media (max-width: 1100px) {
  .traffic-grid { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .overview-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .event-row { grid-template-columns: 140px minmax(0, 1fr) 100px 100px; }
}
@media (max-width: 600px) {
  .container { padding: 32px 18px 72px; }
  .page-header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .overview-row { grid-template-columns: 1fr; }
  .chart-wrapper { height: 240px; }
  .event-row { grid-template-columns: 1fr; gap: 4px; }
  .event-head { display: none; }
  .event-type, .event-tokens { color: var(--ink-3); }
}
</style>
