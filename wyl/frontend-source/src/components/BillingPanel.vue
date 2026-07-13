<template>
  <div class="billing-panel-inner" :class="{ 'animate-in': showContent }">
    <div class="bp-header">
      <span class="bp-issue">Wallet · 钱包</span>
      <div class="bp-header-actions">
        <button v-if="!showTopup && !showWithdraw" class="btn btn-primary" @click="showTopup = true">充值</button>
        <button v-if="!showTopup && !showWithdraw" class="btn btn-secondary" @click="showWithdraw = true">提现</button>
      </div>
    </div>

    <div v-if="showTopup || showWithdraw" class="action-panel">
      <div class="action-label">{{ showTopup ? '充值金额' : '提现金额' }}</div>
      <div class="action-presets">
        <button v-for="amt in (showTopup ? [100,500,1000,5000] : [50,100,500,1000])" :key="amt" :class="['action-preset', { active: inputAmount === amt }]" @click="inputAmount = amt">{{ amt }}</button>
      </div>
      <div class="action-custom">
        <input v-model.number="inputAmount" type="number" min="1" :placeholder="showTopup ? '自定义金额' : '提现金额'" />
        <button class="btn btn-primary btn-sm" @click="showTopup ? handleTopup() : handleWithdraw()" :disabled="loading">确认</button>
        <button class="btn btn-secondary btn-sm" @click="showTopup = false; showWithdraw = false; inputAmount = 100">取消</button>
      </div>
    </div>

    <div class="overview-grid anim-item anim-1">
      <div class="overview-card balance-section">
        <div class="section-label">当前积分余额</div>
        <div class="balance-amount">
          <span class="balance-number" ref="balanceRef">0</span>
          <span class="balance-unit">积分</span>
        </div>
      </div>
      <div class="overview-card">
        <div class="section-label">累计收入</div>
        <div class="stat-value income" ref="incomeRef">+0</div>
      </div>
      <div class="overview-card">
        <div class="section-label">累计支出</div>
        <div class="stat-value expense" ref="expenseRef">-0</div>
      </div>
    </div>

    <div class="chart-section anim-item anim-2"><PointsChart :data="chartData" /></div>

    <div class="card transaction-card anim-item anim-3">
      <div class="card-header"><h2 class="card-title">交易明细</h2><span class="card-count">{{ total }} 条记录</span></div>

      <LoadingSpinner v-if="loading" />
      <EmptyState v-else-if="transactions.length === 0" message="暂无交易记录">
        <button class="btn btn-primary" @click="showTopup = true">立即充值</button>
      </EmptyState>

      <template v-else>
        <div class="tx-header">
          <span class="tx-col type">类型</span><span class="tx-col desc">说明</span><span class="tx-col time">时间</span><span class="tx-col amount">金额</span><span class="tx-col after">余额</span>
        </div>
        <div class="tx-list">
          <div class="tx-row" v-for="tx in transactions" :key="tx.id">
            <span class="tx-col type"><span class="tx-badge" :class="tx.type">{{ typeLabel(tx.type) }}</span></span>
            <span class="tx-col desc">{{ tx.description }}</span>
            <span class="tx-col time">{{ tx.created_at }}</span>
            <span class="tx-col amount" :class="tx.amount >= 0 ? 'positive' : 'negative'">{{ formatAmount(tx.amount, true) }}</span>
            <span class="tx-col after">{{ formatAmount(tx.balance_after) }}</span>
          </div>
        </div>
      </template>

      <div class="pagination" v-if="total > pageSize">
        <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; fetchTransactions()">上一页</button>
        <span class="page-info">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
        <button class="btn btn-secondary btn-sm" :disabled="page >= Math.ceil(total / pageSize)" @click="page++; fetchTransactions()">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import api from '@/api'
import PointsChart from '@/components/PointsChart.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const showContent = ref(false)
onMounted(() => { nextTick(() => { showContent.value = true }) })

const auth = useAuthStore()
const toast = useToastStore()

const balance = ref(0)
const showTopup = ref(false)
const showWithdraw = ref(false)
const inputAmount = ref(100)
const loading = ref(false)
const transactions = ref([])
const chartData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const summary = ref({ income: 0, expense: 0 })

// 用于 count-up 的 DOM 引用 + 动画状态
const balanceRef = ref(null)
const incomeRef  = ref(null)
const expenseRef = ref(null)
const animated = { balance: 0, income: 0, expense: 0 }
const rafIds    = { balance: 0, income: 0, expense: 0 }

/* 数字 count-up:easeOutCubic,行为对齐 GSAP power2.out */
const animateCount = (key, fromVal, toVal, fmt) => {
  const refMap = { balance: balanceRef, income: incomeRef, expense: expenseRef }
  const el = refMap[key]?.value
  if (!el) return
  cancelAnimationFrame(rafIds[key])
  animated[key] = fromVal
  const start = performance.now()
  const duration = 1100
  const ease = (t) => 1 - Math.pow(1 - t, 3)
  const tick = (now) => {
    const p = Math.min(1, (now - start) / duration)
    animated[key] = fromVal + (toVal - fromVal) * ease(p)
    el.textContent = fmt ? fmt(animated[key]) : Math.round(animated[key]).toLocaleString()
    if (p < 1) rafIds[key] = requestAnimationFrame(tick)
  }
  rafIds[key] = requestAnimationFrame(tick)
}

const typeLabel = (type) => ({
 topup: '充值',
 withdraw: '提现',
 consume: '消费',
 income: '收入',
 refund: '退款',
 adjustment: '调整'
}[type] || type)

const normalizeAmount = (value) => Number(value || 0)

const formatAmount = (value, signed = false) => {
 const number = normalizeAmount(value)
 const text = Math.abs(number).toLocaleString(undefined, { maximumFractionDigits: 2 })
 if (!signed) return number < 0 ? `-${text}` : text
 return `${number >= 0 ? '+' : '-'}${text}`
}

const formatTime = (value) => {
 if (!value) return ''
 const date = new Date(value)
 if (Number.isNaN(date.getTime())) return value
 return date.toLocaleString('zh-CN', {
 month: '2-digit',
 day: '2-digit',
 hour: '2-digit',
 minute: '2-digit'
 })
}

const refreshSummary = async () => {
 const data = await api.get('/points/me/summary')
 const nextBalance = normalizeAmount(data.balance)
 const newIncome = normalizeAmount(data.cumulative_income)
 const newExpense = normalizeAmount(data.cumulative_expense)
 summary.value = { income: newIncome, expense: newExpense }
 await nextTick()
 animateCount('balance', animated.balance, nextBalance, (v) => formatAmount(v))
 animateCount('income', animated.income, newIncome, (v) => '+' + formatAmount(v))
 animateCount('expense', animated.expense, newExpense, (v) => '-' + formatAmount(v))
 balance.value = nextBalance
}

const fetchBalance = async () => {
 try {
 await refreshSummary()
 } catch (err) { toast.error(err.message) }
}

const fetchTransactions = async () => {
 loading.value = true
 try {
 const data = await api.get('/points/me/transactions', {
 params: { page_num: page.value, page_size: pageSize }
 })
 transactions.value = (data.items || []).map((tx) => ({
 ...tx,
 amount: normalizeAmount(tx.amount),
 balance_after: normalizeAmount(tx.balance_after),
 description: tx.description || tx.memo || typeLabel(tx.type),
 created_at: formatTime(tx.created_at)
 }))
 total.value = data.total || 0
 } catch (err) { toast.error(err.message) }
 finally { loading.value = false }
}

const fetchChart = async () => {
 try {
 const data = await api.get('/points/me/trend', { params: { days: 30 } })
 chartData.value = (data || []).map((item) => ({
 date: item.date,
 income: normalizeAmount(item.income),
 expense: normalizeAmount(item.expense)
 }))
 } catch (err) { toast.error(err.message) }
}

const handleTopup = async () => {
 if (!inputAmount.value || inputAmount.value < 1) return
 const amount = inputAmount.value
 loading.value = true
 try {
 await api.post('/points/me/topup', { amount })
 showTopup.value = false; inputAmount.value = 100
 toast.success(`成功充值 ${amount} 积分`)
 await Promise.all([refreshSummary(), fetchTransactions(), fetchChart()])
 } catch (err) { toast.error(err.message) }
 finally { loading.value = false }
}

const handleWithdraw = async () => {
 if (!inputAmount.value || inputAmount.value < 1) return
 if (inputAmount.value > balance.value) { toast.error('余额不足'); return }
 const amount = inputAmount.value
 loading.value = true
 try {
 await api.post('/points/me/withdraw', { amount })
 showWithdraw.value = false; inputAmount.value = 100
 toast.success(`成功提现 ${amount} 积分`)
 await Promise.all([refreshSummary(), fetchTransactions(), fetchChart()])
   } catch (err) { toast.error(err.message) }
   finally { loading.value = false }
}

onMounted(async () => {
 if (auth.isLoggedIn) await Promise.all([fetchBalance(), fetchTransactions(), fetchChart()])
})
</script>

<style scoped>
.anim-item { opacity: 0; transform: translateY(16px); }
.animate-in .anim-item { animation: fadeInUp 0.35s cubic-bezier(0.4, 0, 0.2, 1) forwards; }
.animate-in .anim-1 { animation-delay: 0ms; }
.animate-in .anim-2 { animation-delay: 60ms; }
.animate-in .anim-3 { animation-delay: 120ms; }
.animate-in .anim-4 { animation-delay: 180ms; }
.animate-in .anim-5 { animation-delay: 240ms; }
.animate-in .anim-6 { animation-delay: 300ms; }
.animate-in .anim-7 { animation-delay: 360ms; }
.animate-in .anim-8 { animation-delay: 420ms; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.billing-panel-inner { padding-top: 8px; }
.bp-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
}
.bp-issue {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase;
  line-height: 1.45;
  white-space: nowrap;
  color: var(--accent-blue-d);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-blue);
}
.bp-header-actions { display: flex; gap: 10px; }
.bp-header-actions .btn { padding: 8px 20px; font-size: 13px; }

.action-panel { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: var(--r-3); padding: 24px 28px; margin-bottom: 28px; }
.action-label { font-family: var(--font-mono); font-size: 10px; font-weight: 500; letter-spacing: 0.16em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 14px; }
.action-presets { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.action-preset {
  padding: 8px 20px;
  border: 1px solid var(--border-card);
  background: var(--bg-card);
  color: var(--ink-2);
  border-radius: var(--r-2);
  cursor: pointer;
  font-size: 14px; font-weight: 500; font-family: inherit;
  transition: all var(--t-fast);
}
.action-preset:hover { border-color: var(--accent-blue-d); color: var(--ink); }
.action-preset.active { background: var(--sky-grad-deep); border-color: var(--accent-blue-d); color: var(--ink-inverse); }

.action-custom { display: flex; gap: 10px; align-items: center; }
.action-custom input {
  width: 200px;
  padding: 10px 14px;
  border: 1px solid var(--border-input);
  border-radius: var(--r-2);
  background: var(--bg-input);
  color: var(--ink);
  font-size: 14px; font-family: inherit;
  outline: none;
  transition: border-color var(--t-fast);
}
.action-custom input:focus { border-color: var(--accent-blue-d); }

.overview-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr 1fr;
  gap: 20px;
  margin-bottom: 32px;
}
.overview-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 24px 28px;
  transition: border-color var(--t-fast);
}
.overview-card:hover { border-color: var(--accent-blue-d); }

.section-label {
  font-family: var(--font-mono);
  font-size: 13px; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase;
  line-height: 1.45;
  white-space: nowrap;
  color: var(--ink-3);
  margin-bottom: 16px;
}
.balance-section {
  display: flex; flex-direction: column; justify-content: center;
  position: relative;
}
.balance-section::before {
  content: '';
  position: absolute; left: -1px; top: 24px; bottom: 24px;
  width: 2px;
  background: linear-gradient(180deg, transparent, var(--ink), transparent);
  opacity: 0.5;
}
.balance-amount { display: flex; align-items: baseline; gap: 12px; }
.balance-number {
  font-family: var(--font-editorial);
  font-size: 56px;
  font-weight: 400; font-style: italic;
  letter-spacing: -0.03em;
  color: var(--ink);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  transition: color 0.3s;
}
.balance-unit {
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-3);
}
.stat-value {
  font-family: var(--font-editorial);
  font-size: 36px; font-weight: 400; font-style: italic;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1;
  color: var(--ink);
}
.stat-value.income  { color: var(--signal-positive); }
.stat-value.expense { color: var(--signal-negative); }

.chart-section { margin-bottom: 32px; }

.card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: var(--r-3); }
.card-header {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 24px 32px 0;
  margin-bottom: 20px;
}
.card-title { font-size: 18px; font-weight: 600; color: var(--ink); margin: 0; letter-spacing: -0.01em; }
.card-count {
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-3);
}

.tx-header { display: flex; align-items: center; padding: 0 32px 12px; border-bottom: 1px solid var(--border-divider); }
.tx-header .tx-col {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--ink-3);
}
.tx-list { padding: 0 32px; }
.tx-row {
  display: flex; align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-divider);
  font-size: 14px;
  transition: background var(--t-fast);
}
.tx-row:hover { background: var(--bg-card-soft); }
.tx-row:last-child { border-bottom: none; }

.tx-col.type { width: 90px; flex-shrink: 0; }
.tx-col.desc { flex: 1; min-width: 0; padding-right: 24px; color: var(--ink); font-weight: 500; }
.tx-col.time { width: 160px; flex-shrink: 0; color: var(--ink-4); font-size: 13px; font-family: var(--font-mono); }
.tx-col.amount { width: 100px; flex-shrink: 0; text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.tx-col.after { width: 100px; flex-shrink: 0; text-align: right; color: var(--ink-4); font-size: 13px; font-variant-numeric: tabular-nums; }
.tx-col.amount.positive { color: var(--signal-positive); }
.tx-col.amount.negative { color: var(--signal-negative); }

.tx-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px;
  border-radius: var(--r-1);
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.1em; text-transform: uppercase;
}
.tx-badge.topup    { background: var(--signal-positive-soft); color: var(--signal-positive); }
.tx-badge.withdraw { background: var(--signal-negative-soft); color: var(--signal-negative); }
.tx-badge.consume  { background: var(--signal-negative-soft); color: var(--signal-negative); }
.tx-badge.income   { background: var(--signal-positive-soft); color: var(--signal-positive); }
.tx-badge.refund   { background: var(--signal-positive-soft); color: var(--signal-positive); }
.tx-badge.adjustment { background: var(--bg-card-soft); color: var(--ink-3); }

.pagination {
  display: flex; justify-content: center; align-items: center; gap: 20px;
  padding: 20px 32px;
  border-top: 1px solid var(--border-divider);
}
.page-info { font-size: 13px; color: var(--ink-3); }

@media (max-width: 768px) {
  .overview-grid { grid-template-columns: 1fr; gap: 12px; }
  .overview-card { padding: 20px 24px; }
  .bp-issue { font-size: 11px; letter-spacing: 0.14em; }
  .section-label { font-size: 12px; letter-spacing: 0.06em; }
  .balance-number { font-size: 44px; }
  .stat-value { font-size: 28px; }
  .action-panel { padding: 20px 24px; }
  .tx-col.time, .tx-col.after { display: none; }
  .tx-header .tx-col.time, .tx-header .tx-col.after { display: none; }
  .tx-row { padding: 14px 0; font-size: 13px; }
  .tx-header, .tx-list { padding-left: 24px; padding-right: 24px; }
  .card-header { padding-left: 24px; padding-right: 24px; }
  .pagination { padding: 16px 24px; }
  .bp-header { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
