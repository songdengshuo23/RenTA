<template>
  <div
    class="workbench-container"
    :class="{
      'workbench-loading': isLoading,
      'workbench-ready': isReady && !isLoading,
      'workbench-error': !!error,
    }"
    :style="containerStyle"
  >
    <!-- 顶部状态条 (常驻,根据状态切换内容) -->
    <div class="workbench-status-strip" :class="{ error: !!error, loading: isLoading }">
      <template v-if="error && !isLoading">
        <span class="ws-kicker">// ERROR · FAILED TO LOAD</span>
        <span class="ws-scene-name">{{ error }}</span>
        <button v-if="retryable" class="ws-retry" @click="$emit('retry')">[ RETRY ]</button>
      </template>
      <template v-else-if="isLoading">
        <span class="ws-kicker">// LOADING SCENE</span>
        <span class="ws-scene-name">{{ currentScene.toUpperCase() }}</span>
        <div v-if="showProgress" class="ws-progress">
          <div class="ws-progress-fill" :style="{ width: loadingProgress + '%' }"></div>
        </div>
        <span class="ws-percent">{{ Math.round(loadingProgress) }}%</span>
      </template>
      <template v-else>
        <span class="ws-kicker">// STATION 0{{ currentStationIdx + 1 }} · {{ currentScene.toUpperCase() }}</span>
        <span class="ws-scene-name">{{ currentStationState }}</span>
        <span class="ws-time">{{ currentTime }}</span>
      </template>
    </div>

    <!-- PixiJS Canvas — 编辑感 Iso-3D 数据站 -->
    <canvas
      ref="canvasRef"
      class="workbench-canvas"
      :key="mountedKey"
    ></canvas>

    <!-- 动画信息浮层（调试用） -->
    <div v-if="showDebugInfo && currentAnimation" class="workbench-debug-info">
      <span>场景: {{ currentScene }}</span>
      <span>动画: {{ currentAnimation }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useWorkbench } from './useWorkbench'

const props = defineProps({
  /** 场景名称: 'office' | 'project' */
  scene: { type: String, default: 'office' },
  /** 容器宽度 */
  width: { type: [Number, String], default: '100%' },
  /** 容器高度 */
  height: { type: [Number, String], default: '100%' },
  /** 是否显示加载进度条 */
  showProgress: { type: Boolean, default: true },
  /** 加载文案 */
  loadingText: { type: String, default: '工作台加载中...' },
  /** 是否显示调试信息 */
  showDebugInfo: { type: Boolean, default: false },
  /** 错误时是否显示重试按钮 */
  retryable: { type: Boolean, default: true },
  /** 自动初始化 */
  autoInit: { type: Boolean, default: true },
  /** 横向排列（Dashboard用） */
  horizontal: { type: Boolean, default: false },
})

const emit = defineEmits([
  'ready',        // 工作台就绪
  'error',        // 出错
  'retry',        // 用户点击重试
  'animationChange', // 动画切换 (animName)
])

const canvasRef = ref(null)
const mountedKey = ref(0)

const {
  isReady,
  isLoading,
  loadingProgress,
  currentScene,
  currentAnimation,
  error,
  init,
  loadScene,
  triggerEvent,
  playAnimation,
  setAgentAnim,
  resize,
  destroy,
} = useWorkbench(canvasRef)

const containerStyle = computed(() => ({
  width: typeof props.width === 'number' ? props.width + 'px' : props.width,
  height: typeof props.height === 'number' ? props.height + 'px' : props.height,
}))

watch(currentAnimation, (anim) => emit('animationChange', anim))
watch(isReady, (ready) => { if (ready) emit('ready') })
watch(error, (err) => { if (err) emit('error', err) })

/* 状态条:解析 currentAnimation "station-N:STATE" */
const currentStationIdx = computed(() => {
  const m = String(currentAnimation.value).match(/^station-(\d+):/)
  return m ? Number(m[1]) : 0
})
const currentStationState = computed(() => {
  const m = String(currentAnimation.value).match(/:(\w+)$/)
  return m ? m[1] : 'IDLE'
})
const currentTime = ref('--:--:--')
let timeInterval = null
function updateTime() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  currentTime.value = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function boot() {
  await init()
  if (!isReady.value) return
  await loadScene(props.scene, props.horizontal)
}

let resizeObserver = null
onMounted(() => {
  if (canvasRef.value?.parentElement) {
    resizeObserver = new ResizeObserver(() => resize())
    resizeObserver.observe(canvasRef.value.parentElement)
  }
})
onUnmounted(() => { if (resizeObserver) resizeObserver.disconnect() })

onMounted(async () => {
  mountedKey.value++
  await nextTick()
  await new Promise(r => setTimeout(r, 50))
  if (props.autoInit) {
    await boot()
    resize()
  }
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  destroy()
})

watch(() => props.scene, async (newScene) => {
  if (isReady.value) await loadScene(newScene, props.horizontal)
})

defineExpose({ triggerEvent, playAnimation, setAgentAnim, resize, loadScene })
</script>

<style scoped>
.workbench-container {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(25px);
  -webkit-backdrop-filter: blur(25px);
  border: 1px solid rgba(255, 255, 255, 0.8);
}

.workbench-canvas {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: auto;
}

/* 顶部状态条 (编辑感 hairline 卡) */
.workbench-status-strip {
  position: absolute;
  top: 0; left: 0; right: 0;
  z-index: 10;
  height: 32px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(247, 249, 251, 0.92) 100%);
  backdrop-filter: blur(10px) saturate(180%);
  -webkit-backdrop-filter: blur(10px) saturate(180%);
  border-bottom: 1px solid var(--line-blue);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.5) inset, 0 2px 8px -2px rgba(20, 22, 26, 0.04);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--ink-3);
  animation: ws-slide-in 240ms var(--ease-out);
  position: absolute;
  top: 0; left: 0; right: 0;
  z-index: 10;
}
.workbench-status-strip::before {
  content: '';
  position: absolute;
  left: 8px; top: 50%;
  transform: translateY(-50%);
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--signal-positive);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18);
  animation: ws-pulse 2s ease-in-out infinite;
}
.workbench-status-strip.error {
  border-bottom-color: var(--signal-negative);
  color: var(--signal-negative);
}
.workbench-status-strip.error::before {
  background: var(--signal-negative);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.18);
  animation: none;
}
@keyframes ws-slide-in {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes ws-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18); }
  50%      { box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.05); }
}

.ws-kicker {
  color: var(--accent-blue-d);
  font-weight: 600;
  text-transform: uppercase;
  margin-left: 6px;
}
.workbench-status-strip.error .ws-kicker { color: var(--signal-negative); }

.ws-scene-name {
  color: var(--ink);
  text-transform: uppercase;
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.2em;
}

.ws-progress {
  flex: 1;
  max-width: 200px;
  height: 2px;
  background: var(--border-card);
  border-radius: 1px;
  overflow: hidden;
  position: relative;
}
.ws-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue) 0%, var(--accent-blue-d) 100%);
  border-radius: 1px;
  transition: width 0.3s var(--ease-out);
}
.workbench-status-strip.error .ws-progress-fill {
  background: linear-gradient(90deg, var(--signal-negative) 0%, #DC2626 100%);
  width: 100% !important;
}

.ws-percent {
  color: var(--accent-blue);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  min-width: 36px;
  text-align: right;
  font-size: 11px;
}
.workbench-status-strip.error .ws-percent { display: none; }

.ws-time {
  margin-left: auto;
  color: var(--ink-4);
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  font-size: 10px;
  letter-spacing: 0.1em;
}

.ws-retry {
  margin-left: auto;
  background: transparent;
  border: none;
  color: var(--signal-negative);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  cursor: pointer;
  padding: 4px 8px;
  transition: opacity var(--t-fast);
}
.ws-retry:hover { opacity: 0.7; text-decoration: underline; }

/* 调试信息 */
.workbench-debug-info {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 20;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  font-family: monospace;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  pointer-events: none;
}
</style>
