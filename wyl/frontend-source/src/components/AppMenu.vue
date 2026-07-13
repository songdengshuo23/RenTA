<template>
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div
        v-if="modelValue"
        class="app-menu__backdrop"
        @click="close"
        aria-hidden="true"
      />
    </Transition>

    <Transition name="drawer-slide">
      <aside
        v-if="modelValue"
        class="app-menu"
        @keydown.esc.stop="close"
        tabindex="-1"
        ref="rootRef"
        role="dialog"
        aria-label="导航菜单"
      >
        <!-- 顶部 RenTA logo 区 -->
        <header class="app-menu__brand">
          <span class="app-menu__brand-logo">RenTA</span>
          <span class="app-menu__brand-mark" aria-hidden="true"></span>
        </header>
        <div class="hairline-strong"></div>

        <!-- 命令列表 -->
        <nav class="app-menu__nav">
          <div class="menu-list">
            <RouterLink
              v-for="(cmd, idx) in visibleItems"
              :key="cmd.to"
              :to="cmd.to"
              @click="close"
              class="app-menu__item"
              :style="{ '--menu-idx': idx }"
            >
              <span class="app-menu__num" :class="`app-menu__num--${(idx % 4) + 1}`">
                {{ String(idx).padStart(2, '0') }}
              </span>
              <span class="app-menu__label">
                <span class="app-menu__label-main">{{ cmd.label }}</span>
                <span class="app-menu__hint">{{ cmd.hint }}</span>
              </span>
            </RouterLink>

            <!-- 登录（未登录） -->
            <button
              v-if="!auth.isLoggedIn"
              @click="handleLogin"
              class="app-menu__item app-menu__item--auth"
              type="button"
              :style="{ '--menu-idx': visibleItems.length }"
            >
              <span class="app-menu__num app-menu__num--auth">
                {{ String(visibleItems.length).padStart(2, '0') }}
              </span>
              <span class="app-menu__label">
                <span class="app-menu__label-main app-menu__label-main--accent">登 录</span>
                <span class="app-menu__hint">// 登录 · 注册</span>
              </span>
            </button>

            <!-- 退出（已登录） -->
            <button
              v-if="auth.isLoggedIn"
              @click="handleLogout"
              class="app-menu__item app-menu__item--logout"
              type="button"
              :style="{ '--menu-idx': visibleItems.length }"
            >
              <span class="app-menu__num app-menu__num--logout">99</span>
              <span class="app-menu__label">
                <span class="app-menu__label-main">退 出</span>
                <span class="app-menu__hint">// 结束会话</span>
              </span>
            </button>
          </div>
        </nav>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'login'])

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const rootRef = ref(null)

/* 单一真源：所有菜单项 + 权限标签 */
const baseItems = [
  { to: '/',               label: '首页',      hint: '// 入口' },
  { to: '/square',         label: '广场',      hint: '// 智能体索引' },
  { to: '/dashboard',      label: '工作台',    hint: '// 调用监控 + 我的智能体', requiresAuth: true, userOnly: true },
  { to: '/agent-apply',    label: '出租',      hint: '// 发布智能体',   requiresAuth: true, userOnly: true },
  { to: '/account',        label: '账户',      hint: '// 个人中心 · 积分', requiresAuth: true },
  { to: '/admin/monitor',  label: '监控',      hint: '// 流量',         requiresAuth: true, adminOnly: true },
  { to: '/admin/approval', label: '审批',      hint: '// 审核队列',     requiresAuth: true, adminOnly: true },
]

const visibleItems = computed(() => baseItems.filter((i) => {
  if (i.requiresAuth && !auth.isLoggedIn) return false
  if (i.userOnly  && auth.isAdmin) return false
  if (i.adminOnly && !auth.isAdmin) return false
  return true
}))

const close = () => emit('update:modelValue', false)

const handleLogin = () => {
  close()
  emit('login')
}

const handleLogout = () => {
  auth.logout()
  close()
  toast.info('Session terminated')
  router.push('/')
}

const onKey = (e) => {
  if (e.key === 'Escape' && props.modelValue) {
    e.preventDefault()
    close()
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKey)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKey)
})

/* 打开时锁 body 滚动并聚焦容器 */
watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      document.body.style.overflow = 'hidden'
      await nextTick()
      rootRef.value?.focus()
    } else {
      document.body.style.overflow = ''
    }
  }
)
</script>

<style scoped>
/* ==========================================================================
   Atelier Sky · AppMenu — 档案抽屉
   编号即视觉、印章即 hover、横线即节奏
   ========================================================================== */

/* ===== 遮罩：半透明深海军 + 轻模糊 ===== */
.app-menu__backdrop {
  position: fixed;
  inset: 0;
  z-index: 9998;
  background: rgba(14, 42, 71, 0.35);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  cursor: pointer;
}

/* ===== 抽屉本体：右侧固定 480px ===== */
.app-menu {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  max-width: 92vw;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, var(--bg-card) 0%, var(--bg-page-blue) 100%);
  box-shadow: -24px 0 64px -12px rgba(14, 42, 71, 0.28);
  outline: none;
  overflow: hidden;
  /* 极细噪点纹理，呼应主页 .home-grain */
  position: fixed;
}

/* ===== 顶部 RenTA logo 区 ===== */
.app-menu__brand {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 28px clamp(24px, 5vw, 40px);
  flex-shrink: 0;
}
.app-menu__brand-logo {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  font-style: italic;
  letter-spacing: -0.04em;
  color: var(--ink);
}
.app-menu__brand-mark {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: var(--accent-blue);
  border-radius: 50%;
  box-shadow: 0 0 0 4px var(--accent-blue-bg);
}

/* ===== 抽屉 nav ===== */
.app-menu__nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 clamp(24px, 5vw, 40px);
}
.menu-list {
  display: flex;
  flex-direction: column;
}

/* ===== 单条菜单项 ===== */
.app-menu__item {
  display: grid;
  grid-template-columns: 96px 1fr;             /* 编号列 + 标签列，编号当主角 */
  align-items: center;
  gap: 20px;
  padding: 22px 0;
  border-top: 1px solid var(--border-card);
  background: transparent;
  border-left: none;
  border-right: none;
  border-bottom: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-decoration: none;
  position: relative;
  transition:
    transform 0.22s var(--ease-out),
    border-color 0.22s var(--ease-out);
  /* 错开入场动画 —— 抽屉滑入后逐项升起 */
  opacity: 0;
  transform: translateY(14px);
  animation: appMenuItemIn 0.55s var(--ease-out) forwards;
  animation-delay: calc(180ms + var(--menu-idx, 0) * 60ms);
}
.app-menu__item:last-child {
  border-bottom: 1px solid var(--border-card); /* 末条封口，跟其他行形成封闭档案 */
}
@keyframes appMenuItemIn {
  to { opacity: 1; transform: translateY(0); }
}

/* hover：整行右移 8px */
.app-menu__item:hover {
  transform: translateX(8px);
  border-top-color: var(--border-strong);
}
.app-menu__item:last-child:hover {
  border-bottom-color: var(--border-strong);
}

/* ===== 编号：无底色纯文字 ===== */
.app-menu__num {
  font-family: var(--font-display);
  font-size: 56px;
  font-weight: 300;
  font-style: italic;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--accent-blue-d);
  text-align: left;
  transition: color 0.22s var(--ease-out);
}

/* 路由激活态：颜色加深 */
.app-menu__item.router-link-active .app-menu__num {
  color: var(--ink);
}

/* 编号微差：每行轮换极轻的色相，避免单调 */
.app-menu__num--1 { color: var(--accent-blue-d); }
.app-menu__num--2 { color: var(--accent-blue); }
.app-menu__num--3 { color: var(--ink); }
.app-menu__num--4 { color: var(--accent-blue-d); }
.app-menu__num--auth { color: var(--accent-blue-d); }
.app-menu__num--logout { color: var(--signal-negative); }

/* ===== 标签 ===== */
.app-menu__label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.app-menu__label-main {
  font-family: var(--font-display);
  font-size: clamp(28px, 4.4vw, 44px);
  font-weight: 500;
  line-height: 1.05;
  letter-spacing: -0.025em;
  color: var(--ink);
  transition: color 0.22s var(--ease-out);
}
.app-menu__label-main--accent { color: var(--accent-blue-d); }

/* hover：标签不变色，靠整行右移 + 编号色变化承担反馈 */

.app-menu__item.router-link-active .app-menu__label-main {
  color: var(--accent-blue);
}

/* hint：mono 元信息条 */
.app-menu__hint {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 登录/退出行的微差 ===== */
.app-menu__item--auth .app-menu__label-main { color: var(--accent-blue-d); }
.app-menu__item--logout .app-menu__label-main { color: var(--ink); }

/* ===== 抽屉过渡动画 ===== */
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.32s var(--ease-out);
}
.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.42s var(--ease-out);
  will-change: transform;
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}

/* 抽屉内容入场后再展示菜单项 —— 避免滑入过程中动画打架 */
/* （用 animation-delay 在抽屉内部，已经做了） */

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .app-menu__brand { padding: 20px 20px; }
  .app-menu__nav { padding: 0 20px; }
  .app-menu__item {
    grid-template-columns: 64px 1fr;
    gap: 14px;
    padding: 18px 0;
  }
  .app-menu__num { font-size: 36px; padding: 2px 6px; margin-left: -6px; }
  .app-menu__label-main { font-size: clamp(24px, 7vw, 36px); }
}
</style>
