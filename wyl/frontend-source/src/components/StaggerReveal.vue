<template>
  <div ref="containerRef" class="stagger-reveal" :class="{ revealed }">
    <slot />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, useSlots, computed } from 'vue'

const props = defineProps({
  /* 每个子项之间的延迟(ms),默认 80 */
  delay: { type: Number, default: 80 },
  /* 第一次延迟(ms) */
  initialDelay: { type: Number, default: 0 },
  /* 触发阈值 0~1 */
  threshold: { type: Number, default: 0.12 },
  /* 动画持续时间(ms) */
  duration: { type: Number, default: 420 },
  /* 位移幅度(px) */
  translateY: { type: Number, default: 16 },
  /* 是否只触发一次,触发后即停 observer */
  once: { type: Boolean, default: true }
})

const containerRef = ref(null)
const revealed = ref(false)
const slots = useSlots()
const reducedMotion = typeof window !== 'undefined'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches

let io = null

const childCount = computed(() => {
  const vnodes = slots.default ? slots.default() : []
  // 只计算 element 类型的子节点(过滤注释/空)
  return vnodes.filter(v => v && v.type && (typeof v.type === 'string' || typeof v.type === 'object')).length
})

const apply = () => {
  if (!containerRef.value) return
  if (reducedMotion) { revealed.value = true; return }
  const children = containerRef.value.children
  for (let i = 0; i < children.length; i++) {
    const el = children[i]
    el.style.animationDelay = `${props.initialDelay + i * props.delay}ms`
    el.style.animationDuration = `${props.duration}ms`
    el.style.setProperty('--stagger-y', `${props.translateY}px`)
  }
  revealed.value = true
}

onMounted(() => {
  if (reducedMotion || !containerRef.value) { revealed.value = true; return }
  io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        apply()
        if (props.once) io.disconnect()
      } else if (!props.once) {
        revealed.value = false
      }
    })
  }, { threshold: props.threshold })
  io.observe(containerRef.value)
})

onBeforeUnmount(() => { if (io) io.disconnect() })
</script>

<style scoped>
.stagger-reveal > :deep(*) {
  opacity: 0;
  transform: translateY(var(--stagger-y, 16px));
  animation-fill-mode: both;
  animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  animation-name: staggerReveal;
}
.stagger-reveal.revealed > :deep(*) {
  animation-play-state: running;
}
@keyframes staggerReveal {
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .stagger-reveal > :deep(*) {
    opacity: 1 !important;
    transform: none !important;
    animation: none !important;
  }
}
</style>
