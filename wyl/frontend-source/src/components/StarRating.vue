<template>
  <!-- 只读模式:静态展示 -->
  <div
    v-if="readonly"
    class="star-rating readonly"
    :style="{ gap: `${Math.max(1, Math.round(size / 13))}px` }"
    :aria-label="`评分 ${modelValue} / 5`"
  >
    <svg
      v-for="star in 5"
      :key="star"
      class="star-icon"
      :class="{ filled: star <= modelValue }"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      :fill="star <= modelValue ? 'currentColor' : 'none'"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  </div>

  <!-- 可编辑模式:Uiverse 风格 (粒子炸开 + 选中呼吸光晕) -->
  <div
    v-else
    class="star-rating editable"
    :style="{ gap: `${Math.max(2, Math.round(size / 8))}px` }"
    role="radiogroup"
    :aria-label="`评分 ${modelValue} / 5`"
  >
    <input
      v-for="star in 5"
      :key="`i${star}`"
      type="radio"
      :name="radioName"
      :value="star"
      :id="`star-${uid}-${star}`"
      :checked="star === modelValue"
      @change="$emit('update:modelValue', star)"
    />
    <label
      v-for="star in 5"
      :key="`l${star}`"
      :for="`star-${uid}-${star}`"
      class="star-icon"
      :class="{ filled: star <= (hovered || modelValue) }"
      :title="`${star} 星`"
      @mouseenter="hovered = star"
      @mouseleave="hovered = 0"
    >
      <svg
        :width="size"
        :height="size"
        viewBox="0 0 24 24"
        fill="currentColor"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    </label>
  </div>
</template>

<script>
/* 多个 StarRating 共存时 radio name 不能冲突 — 模块作用域,所有实例共享 */
let uidCounter = 0
</script>

<script setup>
import { ref } from 'vue'

defineProps({
  modelValue: { type: Number, default: 0 },
  readonly: { type: Boolean, default: false },
  size: { type: [Number, String], default: 24 }
})

defineEmits(['update:modelValue'])

const uid = `sr${++uidCounter}`
const radioName = `star-rating-${uid}`

const hovered = ref(0)
</script>

<style scoped>
.star-rating {
  display: inline-flex;
  align-items: center;
  line-height: 0;
}

/* ============================================================
   只读模式 — 静态展示
============================================================ */
.star-rating.readonly .star-icon {
  color: var(--ink-5);
  display: inline-block;
  transition: color var(--t-fast);
}
.star-rating.readonly .star-icon.filled {
  color: var(--signal-star);
}

/* ============================================================
   可编辑模式 — Uiverse 风格粒子 + 光晕
============================================================ */
.star-rating.editable .star-icon {
  position: relative;
  display: inline-block;
  cursor: pointer;
  color: var(--ink-5);
  transition: color var(--t-fast);
  user-select: none;
}
.star-rating.editable .star-icon.filled {
  color: var(--signal-star);
}

/* hover 缩放 + 脉冲 */
.star-rating.editable .star-icon:hover {
  transform: scale(1.2);
  animation: pulse 0.6s infinite alternate;
}
/* 选中态:持续呼吸 + drop-shadow 光晕 */
.star-rating.editable .star-icon.filled {
  animation: pulse 0.8s infinite alternate;
}
.star-rating.editable .star-icon.filled svg {
  filter: drop-shadow(0 0 6px rgba(232, 160, 32, 0.5));
  transition: filter var(--t-fast);
}
.star-rating.editable .star-icon:hover svg {
  filter: drop-shadow(0 0 14px rgba(232, 160, 32, 0.95));
  animation: shimmer 1s ease infinite alternate;
}

/* 粒子 ::before / ::after — hover 时从中心上下炸开 */
.star-rating.editable .star-icon::before,
.star-rating.editable .star-icon::after {
  content: "";
  position: absolute;
  width: 5px; height: 5px;
  background-color: var(--signal-star);
  border-radius: 50%;
  left: 50%;
  opacity: 0;
  transform: translateX(-50%) scale(0);
  transition: transform 0.4s ease, opacity 0.4s ease;
  pointer-events: none;
}
.star-rating.editable .star-icon::before {
  top: -8px;
}
.star-rating.editable .star-icon::after {
  bottom: -8px;
}
.star-rating.editable .star-icon:hover::before,
.star-rating.editable .star-icon:hover::after {
  opacity: 1;
  transform: translateX(-50%) scale(1.4);
}

/* radio input 视觉隐藏,保留可访问性 + label 关联 */
.star-rating.editable input[type="radio"] {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.star-rating.editable input[type="radio"]:focus-visible + .star-icon {
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
  border-radius: 2px;
}

/* 关键帧 */
@keyframes pulse {
  0%   { transform: scale(1); }
  100% { transform: scale(1.1); }
}
@keyframes shimmer {
  0%   { filter: drop-shadow(0 0 6px rgba(232, 160, 32, 0.6)); }
  100% { filter: drop-shadow(0 0 16px rgba(232, 160, 32, 1)); }
}

/* 减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
  .star-rating.editable .star-icon:hover,
  .star-rating.editable .star-icon.filled {
    animation: none;
  }
  .star-rating.editable .star-icon:hover::before,
  .star-rating.editable .star-icon:hover::after {
    display: none;
  }
}
</style>
