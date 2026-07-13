/**
 * AgentAnimator.js — 状态机薄壳
 *
 * 保留 emit/on/off 接口供旧代码用,内部不再管 sprite 帧动画
 * 实际状态由 useWorkbench 渲染为编辑感数据站
 */

export const ANIMATIONS = {
  STANDBY: 'IDLE',
  WORKING: 'WORKING',
  THINKING: 'THINKING',
  READY: 'READY',
  ERROR: 'ERROR',
}

const EVENT_TO_STATE = {
  idle: 'IDLE',
  userSendMessage: 'WORKING',
  aiThinking: 'THINKING',
  aiResponse: 'READY',
  switchAgent: 'WORKING',
  agentActivated: 'READY',
  error: 'ERROR',
  longIdle: 'IDLE',
  leave: 'IDLE',
  deactivated: 'ERROR',
  searching: 'WORKING',
  fileOperation: 'WORKING',
  appUsage: 'WORKING',
}

export class AgentAnimator {
  constructor(_animationSets, _options = {}) {
    this.listeners = new Map()
    this.currentAnimation = null
  }

  resolveAnimation(_name) { return null }
  play(_name, _options = {}) {}
  playByEvent(event, _options = {}) {
    const state = EVENT_TO_STATE[event]
    if (state) {
      this.currentAnimation = state
      this.emit('animationChange', { from: null, to: state })
    }
  }
  waitForCompletion(cb) { if (cb) cb() }
  stop() {}
  setVariant() {}
  getCategory() { return 'state' }

  on(event, cb) {
    if (!this.listeners.has(event)) this.listeners.set(event, [])
    this.listeners.get(event).push(cb)
  }
  off(event, cb) {
    const cbs = this.listeners.get(event)
    if (cbs) {
      const idx = cbs.indexOf(cb)
      if (idx >= 0) cbs.splice(idx, 1)
    }
  }
  emit(event, data) {
    const cbs = this.listeners.get(event)
    if (cbs) cbs.forEach(cb => cb(data))
  }
  destroy() { this.listeners.clear() }
}
