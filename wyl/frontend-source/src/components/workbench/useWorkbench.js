/**
 * useWorkbench.js — 编辑感 Iso-3D 数据站 (PIXI v8)
 *
 * 设计：从"office + 像素角色"改为"3 个 iso-3D 数据站 + 连线 + 流动粒子"
 * 视觉语言与 HomeView 的 iso-stage 一致
 *
 * 对外接口（保持兼容）：
 *   - state: isReady / isLoading / loadingProgress / currentScene / currentAnimation / error
 *   - ops:   init / loadScene / loadAgent / triggerEvent / playAnimation / setAgentAnim / setVariant / resize / destroy
 */

import { ref } from 'vue'
import { Application, Container, Graphics, Text } from 'pixi.js'

/* ============= 状态常量 ============= */
export const STATION_STATE = {
  IDLE:     'IDLE',
  WORKING:  'WORKING',
  THINKING: 'THINKING',
  READY:    'READY',
  ERROR:    'ERROR',
}

const STATION_STATE_COLOR = {
  IDLE:     0x8E8E8E,
  WORKING:  0x10B981,
  THINKING: 0x4A8DB5,
  READY:    0x4A8DB5,
  ERROR:    0xEF4444,
}

const STATION_STATE_TEXT = {
  IDLE:     'IDLE',
  WORKING:  'WORKING',
  THINKING: 'THINKING',
  READY:    'READY',
  ERROR:    'ERROR',
}

const EVENT_ACTIONS = {
  idle:            { type: 'broadcast', state: STATION_STATE.IDLE },
  userSendMessage: { type: 'pulse',     from: 0, to: 1, endState: STATION_STATE.THINKING },
  aiThinking:      { type: 'set',       station: 1, state: STATION_STATE.THINKING },
  aiResponse:      { type: 'pulse',     from: 1, to: 2, endState: STATION_STATE.READY },
  switchAgent:     { type: 'cycle' },
  agentActivated:  { type: 'broadcast', state: STATION_STATE.READY },
  error:           { type: 'broadcast', state: STATION_STATE.ERROR },
  longIdle:        { type: 'broadcast', state: STATION_STATE.IDLE },
  leave:           { type: 'broadcast', state: STATION_STATE.IDLE },
  deactivated:     { type: 'broadcast', state: STATION_STATE.ERROR },
  searching:       { type: 'set',       station: 1, state: STATION_STATE.WORKING },
  fileOperation:   { type: 'set',       station: 1, state: STATION_STATE.WORKING },
  appUsage:        { type: 'set',       station: 1, state: STATION_STATE.WORKING },
}

const PLATFORM_W = 70
const PLATFORM_H = 50
const SPACING_RATIO = 0.28  // 站间距 = 容器宽 × 0.28
const CENTER_Y_RATIO = 0.55

export function useWorkbench(canvasRef) {
  const isReady = ref(false)
  const isLoading = ref(true)
  const loadingProgress = ref(0)
  const currentScene = ref('office')
  const currentAnimation = ref('IDLE')
  const error = ref(null)

  let app = null
  let sceneContainer = null
  let linesLayer = null
  let stationsLayer = null
  let particlesLayer = null
  let frameInterval = null
  let idleTimer = null
  const idleTimeout = 30000

  /* 3 个站的状态 + 视觉对象 */
  const stations = [
    { state: STATION_STATE.IDLE, graphics: null, kickerText: null, statusText: null, timeText: null, time: '00:00:00' },
    { state: STATION_STATE.IDLE, graphics: null, kickerText: null, statusText: null, timeText: null, time: '00:00:00' },
    { state: STATION_STATE.IDLE, graphics: null, kickerText: null, statusText: null, timeText: null, time: '00:00:00' },
  ]

  /* 2 条连线的粒子 */
  const lines = [
    { graphics: null, particles: [], active: false },
    { graphics: null, particles: [], active: false },
  ]

  /* ============= 初始化 ============= */
  async function init() {
    const canvas = canvasRef?.value
    if (!canvas) { error.value = 'Canvas not found'; return }

    try {
      isLoading.value = true
      loadingProgress.value = 10

      const parent = canvas.parentElement
      const w = parent?.clientWidth || 400
      const h = parent?.clientHeight || 400

      app = new Application()
      await app.init({
        canvas, width: w, height: h,
        background: 0xF7F9FB, backgroundAlpha: 1,
        antialias: true, resolution: window.devicePixelRatio || 1, autoDensity: true,
      })
      loadingProgress.value = 30

      sceneContainer = new Container()
      sceneContainer.label = 'scene-root'
      sceneContainer.sortableChildren = true
      app.stage.addChild(sceneContainer)

      drawBackground(w, h)
      loadingProgress.value = 50

      layersSetup()
      drawStations(w, h)
      drawLines(w, h)
      loadingProgress.value = 80

      app.ticker.add(tick)
      isReady.value = true
    } catch (err) {
      error.value = err.message
      console.error('[Workbench] Init error:', err)
    } finally {
      isLoading.value = false
      loadingProgress.value = 100
    }
  }

  function drawBackground(w, h) {
    const bg = new Graphics()
    /* 中心径向渐变 (略浅中央,边缘略深) */
    const cx = w * 0.5
    const cy = h * 0.55
    const maxR = Math.max(w, h) * 0.7
    /* 16 圈由内向外渐变 */
    for (let r = maxR; r > 0; r -= maxR / 16) {
      const a = 0.025 * (1 - r / maxR)
      bg.circle(cx, cy, r).fill({ color: 0x4A8DB5, alpha: a })
    }
    /* 细网格 16px, 极淡 */
    const gridColor = 0x4A8DB5
    for (let x = 0; x < w; x += 16) {
      bg.moveTo(x + 0.5, 0).lineTo(x + 0.5, h).stroke({ color: gridColor, alpha: 0.04, width: 1 })
    }
    for (let y = 0; y < h; y += 16) {
      bg.moveTo(0, y + 0.5).lineTo(w, y + 0.5).stroke({ color: gridColor, alpha: 0.04, width: 1 })
    }
    /* 内框 (1px 蓝 hairline, 类似 manuscript 边框) */
    bg.rect(8, 8, w - 16, h - 16).stroke({ color: 0x4A8DB5, alpha: 0.15, width: 1 })
    /* 四角装饰 L 形 */
    const cornerLen = 12
    const corners = [[10, 10, 1, 1], [w - 10, 10, -1, 1], [10, h - 10, 1, -1], [w - 10, h - 10, -1, -1]]
    for (const [x, y, dx, dy] of corners) {
      bg.moveTo(x, y + dy * cornerLen).lineTo(x, y).lineTo(x + dx * cornerLen, y)
        .stroke({ color: 0x4A8DB5, alpha: 0.6, width: 1.5 })
    }
    bg.label = 'bg'
    sceneContainer.addChildAt(bg, 0)
  }

  function layersSetup() {
    linesLayer = new Container()
    linesLayer.label = 'lines'
    sceneContainer.addChild(linesLayer)

    stationsLayer = new Container()
    stationsLayer.label = 'stations'
    sceneContainer.addChild(stationsLayer)

    particlesLayer = new Container()
    particlesLayer.label = 'particles'
    sceneContainer.addChild(particlesLayer)
  }

  function stationX(i, w) {
    const spacing = w * SPACING_RATIO
    return w * 0.5 - spacing + i * spacing
  }

  function centerY(h) {
    return h * CENTER_Y_RATIO
  }

  function drawStations(w, h) {
    const y = centerY(h)
    for (let i = 0; i < 3; i++) {
      const x = stationX(i, w)
      const station = stations[i]

      const g = new Graphics()
      g.label = `station-${i}`
      drawIsoPlatform(g, x, y, station.state)
      stationsLayer.addChild(g)
      station.graphics = g

      /* 上方 kicker:稍大、稍蓝 */
      const kicker = new Text({
        text: `// STATION 0${i + 1}`,
        style: { fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: '600', letterSpacing: 1.8, fill: 0x4A8DB5 }
      })
      kicker.anchor.set(0.5, 0)
      kicker.x = x
      kicker.y = y - PLATFORM_H / 2 - 22
      stationsLayer.addChild(kicker)
      station.kickerText = kicker

      /* 状态 badge:字号加大、letter-spacing 加大 */
      const status = new Text({
        text: STATION_STATE_TEXT[station.state],
        style: { fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: '700', letterSpacing: 1.8, fill: 0xFFFFFF }
      })
      status.anchor.set(0.5, 0.5)
      status.x = x
      status.y = y - PLATFORM_H / 2 + 4
      stationsLayer.addChild(status)
      station.statusText = status

      /* 下方时间戳:tabular-nums + 淡蓝灰 */
      station.time = formatTime(new Date())
      const time = new Text({
        text: station.time,
        style: { fontFamily: 'JetBrains Mono, monospace', fontSize: 9, fontWeight: '500', fill: 0x8E8E8E, letterSpacing: 0.5 }
      })
      time.anchor.set(0.5, 0)
      time.x = x
      time.y = y + 10
      stationsLayer.addChild(time)
      station.timeText = time
    }
  }

  function drawIsoPlatform(g, x, y, state) {
    const color = STATION_STATE_COLOR[state]
    const offset = 6
    /* 阴影(更深 + 偏移更大,真 iso-3D 感) */
    g.roundRect(x - PLATFORM_W / 2 + offset, y - PLATFORM_H / 2 + offset, PLATFORM_W, PLATFORM_H, 6)
      .fill({ color: 0x000000, alpha: 0.12 })
    /* 顶层:蓝/绿/红的纯色底 */
    g.roundRect(x - PLATFORM_W / 2, y - PLATFORM_H / 2, PLATFORM_W, PLATFORM_H, 6)
      .fill({ color: color, alpha: 0.95 })
    /* 内层高光:略缩 3px,白色 6% 透明,模拟玻璃感 */
    g.roundRect(x - PLATFORM_W / 2 + 3, y - PLATFORM_H / 2 + 3, PLATFORM_W - 6, PLATFORM_H - 6, 4)
      .stroke({ color: 0xFFFFFF, alpha: 0.18, width: 1 })
    /* 外框:1.5px 实色边 */
    g.roundRect(x - PLATFORM_W / 2, y - PLATFORM_H / 2, PLATFORM_W, PLATFORM_H, 6)
      .stroke({ color: color, alpha: 1, width: 1.5 })
    /* 顶部高光线(1px 浅色横线在平台上沿) */
    g.moveTo(x - PLATFORM_W / 2 + 4, y - PLATFORM_H / 2 + 0.5)
      .lineTo(x + PLATFORM_W / 2 - 4, y - PLATFORM_H / 2 + 0.5)
      .stroke({ color: 0xFFFFFF, alpha: 0.4, width: 1 })
  }

  function drawLines(w, h) {
    const y = centerY(h) - PLATFORM_H / 2 + 4
    for (let i = 0; i < 2; i++) {
      const x1 = stationX(i, w) + PLATFORM_W / 2
      const x2 = stationX(i + 1, w) - PLATFORM_W / 2

      const lineG = new Graphics()
      lineG.label = `line-${i}`
      drawLineGraphic(lineG, x1, x2, y, false)
      linesLayer.addChild(lineG)
      lines[i].graphics = lineG

      /* 中点小圆点(类似"管线节点") */
      for (let p = 0; p < 2; p++) {
        const midDot = new Graphics()
        midDot.circle(0, 0, 1.2).fill({ color: 0xD4E3EE, alpha: 0.7 })
        midDot.x = x1 + (x2 - x1) * (0.3 + p * 0.4)
        midDot.y = y
        midDot.label = `mid-${i}-${p}`
        linesLayer.addChild(midDot)
        lines[i].midDots = lines[i].midDots || []
        lines[i].midDots.push(midDot)
      }

      /* 流动粒子(2 个,错开 0.5 周期) */
      for (let p = 0; p < 2; p++) {
        const particle = new Graphics()
        particle.circle(0, 0, 2.5).fill({ color: 0x4A8DB5, alpha: 0 })
        particle.x = x1
        particle.y = y
        particle.label = `particle-${i}-${p}`
        particlesLayer.addChild(particle)
        lines[i].particles.push({ graphics: particle, t: p * 0.5 })
      }
    }
  }

  function drawLineGraphic(g, x1, x2, y, active) {
    g.clear()
    const color = active ? 0x4A8DB5 : 0xD4E3EE
    /* 主线稍粗 */
    g.moveTo(x1, y).lineTo(x2, y).stroke({ color, alpha: 0.95, width: 1.8 })
    /* 加重箭头(三角实心感) */
    const arrowSize = 6
    g.moveTo(x2, y)
      .lineTo(x2 - arrowSize, y - arrowSize / 2)
      .lineTo(x2 - arrowSize, y + arrowSize / 2)
      .closePath()
      .fill({ color, alpha: 0.95 })
  }

  function setStationState(idx, state) {
    if (idx < 0 || idx > 2) return
    if (!Object.values(STATION_STATE).includes(state)) return
    const station = stations[idx]
    station.state = state
    currentAnimation.value = `station-${idx}:${state}`

    if (station.graphics && app) {
      const w = app.renderer.width
      const h = app.renderer.height
      const x = stationX(idx, w)
      const y = centerY(h)
      drawIsoPlatform(station.graphics, x, y, state)
    }
    if (station.statusText) {
      station.statusText.text = STATION_STATE_TEXT[state]
    }
    station.time = formatTime(new Date())
    if (station.timeText) station.timeText.text = station.time
  }

  function setLineState(lineIdx, active) {
    if (lineIdx < 0 || lineIdx > 1) return
    if (!app) return
    const line = lines[lineIdx]
    if (line.active === active) return
    line.active = active
    const w = app.renderer.width
    const h = app.renderer.height
    const y = centerY(h) - PLATFORM_H / 2 + 4
    const x1 = stationX(lineIdx, w) + PLATFORM_W / 2
    const x2 = stationX(lineIdx + 1, w) - PLATFORM_W / 2
    drawLineGraphic(line.graphics, x1, x2, y, active)
  }

  function formatTime(d) {
    const pad = (n) => String(n).padStart(2, '0')
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }

  function tick(delta) {
    if (!app) return
    const t = (performance.now() || Date.now()) * 0.001
    const w = app.renderer.width
    const h = app.renderer.height
    const y = centerY(h) - PLATFORM_H / 2 + 4
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const x1 = stationX(i, w) + PLATFORM_W / 2
      const x2 = stationX(i + 1, w) - PLATFORM_W / 2
      const baseSpeed = line.active ? 0.6 : 0.3
      line.particles.forEach(p => {
        p.t += (delta || 0.016) * baseSpeed
        if (p.t > 1) p.t -= 1
        if (p.t < 0) p.t += 1
        p.graphics.x = x1 + (x2 - x1) * p.t
        p.graphics.y = y
        /* 数据包式渐变:中段 0.9 + 边 0.2 (用 sin 半周期更"呼吸") */
        p.graphics.alpha = Math.sin(p.t * Math.PI) * (line.active ? 0.95 : 0.35)
      })
      /* 中点圆点轻微脉动(active 时) */
      if (line.midDots) {
        line.midDots.forEach((dot, di) => {
          const phase = di * 0.5
          const pulse = line.active ? 0.5 + 0.5 * Math.sin(t * 2 + phase) : 0.7
          dot.alpha = pulse
        })
      }
    }
  }

  /* ============= 业务事件 ============= */
  function triggerEvent(eventName, options = {}) {
    resetIdleTimer()
    const action = EVENT_ACTIONS[eventName]
    if (!action) {
      console.warn(`[Workbench] No action for event: ${eventName}`)
      return
    }
    handleAction(action, options)
  }

  function handleAction(action, options) {
    if (action.type === 'broadcast') {
      stations.forEach((_, i) => setStationState(i, action.state))
      lines.forEach((_, i) => setLineState(i, false))
    } else if (action.type === 'set') {
      setStationState(action.station, action.state)
    } else if (action.type === 'pulse') {
      setStationState(action.from, STATION_STATE.WORKING)
      setStationState(action.to, action.endState || STATION_STATE.THINKING)
      setLineState(action.from, true)
    } else if (action.type === 'cycle') {
      const i = Math.floor(Math.random() * 3)
      setStationState(i, STATION_STATE.WORKING)
    }
  }

  function playAnimation(stateOrName, options = {}) {
    resetIdleTimer()
    if (Object.values(STATION_STATE).includes(stateOrName)) {
      handleAction({ type: 'broadcast', state: stateOrName })
      return
    }
    triggerEvent(stateOrName, options)
  }

  function setAgentAnim(idx, stateName) {
    if (idx < 0 || idx > 2) return
    setStationState(idx, stateName)
  }

  function setVariant(_v) { /* no-op: 编辑感数据站无变体 */ }

  function loadScene(sceneName = 'office', _horizontal = false) {
    currentScene.value = sceneName
    return Promise.resolve()
  }

  function loadAgent(_url, _options = {}) {
    return Promise.resolve()
  }

  /* ============= 闲置检测 ============= */
  function resetIdleTimer() {
    clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      handleAction({ type: 'broadcast', state: STATION_STATE.IDLE })
    }, idleTimeout)
  }

  /* ============= Resize ============= */
  function resize() {
    if (app?.renderer?.resize && app.canvas) {
      const p = app.canvas.parentElement
      if (p) {
        const w = p.clientWidth
        const h = p.clientHeight
        app.renderer.resize(w, h)
        sceneContainer.removeChildren()
        drawBackground(w, h)
        layersSetup()
        drawStations(w, h)
        drawLines(w, h)
      }
    }
  }

  /* ============= Destroy ============= */
  function destroy() {
    clearTimeout(idleTimer)
    if (frameInterval) { clearInterval(frameInterval); frameInterval = null }
    if (app) { try { app.destroy(false) } catch {} app = null }
    sceneContainer = null
    stationsLayer = null
    linesLayer = null
    particlesLayer = null
    isReady.value = false
  }

  return {
    isReady, isLoading, loadingProgress, currentScene, currentAnimation, error,
    init, loadScene, loadAgent, triggerEvent, playAnimation, setAgentAnim, setVariant, resize, destroy,
    STATION_STATE,
  }
}
