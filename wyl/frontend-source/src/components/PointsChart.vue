<template>
  <div class="chart-container">
    <div class="chart-header">
      <h3 class="chart-title">积分变动趋势</h3>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-dot income"></span>收入</span>
        <span class="legend-item"><span class="legend-dot expense"></span>支出</span>
      </div>
    </div>
    <div class="chart-wrapper"><canvas ref="canvas"></canvas></div>
    <div v-if="!hasData" class="chart-empty">暂无数据</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const props = defineProps({ data: { type: Array, default: () => [] } })
const canvas = ref(null)
let chartInstance = null

const hasData = computed(() => props.data.some(d => d.income > 0 || d.expense > 0))

const buildChart = () => {
  if (!canvas.value) return
  const labels = props.data.map(d => d.date.slice(5))
  const incomeData = props.data.map(d => d.income)
  const expenseData = props.data.map(d => d.expense)

  if (chartInstance) {
    chartInstance.data.labels = labels
    chartInstance.data.datasets[0].data = incomeData
    chartInstance.data.datasets[1].data = expenseData
    chartInstance.update('none')
    return
  }
  chartInstance = new Chart(canvas.value, {
    type: 'line', data: {
      labels,
      datasets: [
        { label: '收入', data: incomeData, borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.08)', borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 5, pointBackgroundColor: '#10b981', pointHitRadius: 10 },
        { label: '支出', data: expenseData, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.06)', borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 5, pointBackgroundColor: '#ef4444', pointHitRadius: 10 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#fff', titleColor: '#171A20', bodyColor: '#5C5E62', borderColor: '#eee', borderWidth: 1, padding: 12, cornerRadius: 8, displayColors: true, callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y} 积分` } }
      },
      scales: { x: { grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: 'rgba(0,0,0,0.4)', font: { size: 11 }, maxTicksLimit: 10 } }, y: { grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: 'rgba(0,0,0,0.4)', font: { size: 11 }, maxTicksLimit: 5, callback: (v) => v === 0 ? '0' : v }, beginAtZero: true } }
    }
  })
}

onMounted(() => { nextTick(buildChart) })
watch(() => props.data, () => { nextTick(buildChart) }, { deep: true })
onUnmounted(() => { if (chartInstance) chartInstance.destroy() })
</script>

<style scoped>
.chart-container { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 4px; padding: 24px; position: relative; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.chart-title { font-size: 16px; font-weight: 600; color: var(--text-primary); margin: 0; }
.chart-legend { display: flex; gap: 16px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.legend-dot.income { background: #10b981; }
.legend-dot.expense { background: #ef4444; }
.chart-wrapper { position: relative; height: 240px; }
.chart-empty { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: var(--text-placeholder); font-size: 14px; pointer-events: none; }
canvas { width: 100% !important; height: 100% !important; }
</style>
