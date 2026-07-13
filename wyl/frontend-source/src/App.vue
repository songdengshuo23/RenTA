<template>
  <div id="app">
    <!-- ===== 顶部浅蓝档案条 (/chat 路由下隐藏,聊天页自己接管) ===== -->
    <header v-if="!hideTopbar" class="topbar">
      <router-link to="/" class="topbar-brand" aria-label="RenTA Home">
        <img class="brand-logo" src="/renta-logo-mark.png" alt="RenTA" />
      </router-link>

      <!-- 面包屑：当前页面标签 -->
      <nav class="topbar-breadcrumb" aria-label="当前位置">
        <span class="breadcrumb-sep" aria-hidden="true">/</span>
        <span class="breadcrumb-cur">{{ breadcrumbLabel }}</span>
      </nav>

      <div class="topbar-right">
        <button
          class="topbar-menu-trigger"
          :class="{ 'is-open': menuOpen }"
          @click="menuOpen = true"
          aria-label="Open navigation menu"
        >
          <span class="trigger-icon" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="3" y1="6"  x2="21" y2="6"/>
              <line x1="3" y1="12" x2="15" y2="12"/>
              <line x1="3" y1="18" x2="18" y2="18"/>
            </svg>
          </span>
          <span class="archive-label">MENU</span>
          <span class="trigger-kbd" aria-hidden="true">⌘K</span>
        </button>

        <button v-if="auth.isLoggedIn" class="topbar-user" @click="goAccount">
          <span class="user-avatar">{{ (auth.user?.username || 'U').slice(0,1).toUpperCase() }}</span>
          <span class="user-name">{{ auth.user?.username }}</span>
        </button>
        <router-link v-else to="/auth" class="topbar-cta">登录</router-link>
      </div>
    </header>

    <main :class="['main-content', { 'is-chat': hideTopbar }]">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" :key="$route.fullPath" />
        </Transition>
      </router-view>
    </main>

    <AppMenu v-model="menuOpen" @login="goAuth" />
    <ToastContainer />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppMenu from '@/components/AppMenu.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

/* /chat 路由下隐藏 App 顶栏,聊天页自己接管头部 */
const hideTopbar = computed(() => route.name === 'chat')

/* 面包屑：路由名 → 中文标签 */
const ROUTE_LABELS = {
  home:            '首页 · Home',
  square:          '广场 · Square',
  dashboard:       '工作台 · Dashboard',
  'agent-apply':   '出租 · Apply',
  account:         '账户 · Account',
  auth:            '登录 · Sign In',
  chat:            '对话 · Chat',
  'admin-monitor': '监控 · Monitor',
  'admin-approval':'审批 · Approval',
}
const breadcrumbLabel = computed(() => ROUTE_LABELS[route.name] || route.name || '')

const menuOpen = ref(false)
const openAppMenu = () => { menuOpen.value = true }
provide('openAppMenu', openAppMenu)  // 暴露给 ChatView 等子页面

const goAccount = () => router.push('/account')
const goAuth = () => router.push('/auth')

const onKey = (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    menuOpen.value = !menuOpen.value
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => { document.removeEventListener('keydown', onKey) })
</script>

<style scoped>
#app {
  --topbar-h: 56px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: var(--font-text);
  background:
    radial-gradient(ellipse 1200px 700px at 0% 0%, rgba(46, 122, 184, 0.10) 0%, transparent 60%),
    radial-gradient(ellipse 900px 600px at 100% 100%, rgba(91, 160, 214, 0.10) 0%, transparent 60%),
    var(--bg-page);
}

/* ========== 顶部浅蓝档案条(方案 1+3:减法 + 面包屑) ========== */
.topbar {
  position: sticky;
  top: 0;
  z-index: 1100;
  height: var(--topbar-h);
  background: var(--bg-page);                  /* 稳定锚点：不透明,不被背景洗掉 */
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line-blue);
  flex-shrink: 0;
}

.topbar-brand {
  width: clamp(88px, 6vw, 112px);
  height: 42px;
  display: flex;
  align-items: center;
  text-decoration: none;
  color: var(--ink);
  flex-shrink: 0;
}
.brand-logo {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: left center;
}
.brand-mark {
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  background: var(--sky-grad-deep);
  color: #fff;
  font-family: var(--font-editorial);
  font-size: 14px; font-style: italic; font-weight: 400;
  border-radius: 50%;
}
.brand-name {
  font-family: var(--font-display);
  font-size: 16px; font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink);
}

/* ===== 面包屑：当前页面标签 ===== */
.topbar-breadcrumb {
  display: flex; align-items: center; gap: 10px;
  flex: 1;                                    /* 占满中间，把左右推开 */
  min-width: 0;
}
.breadcrumb-sep {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-4);
  flex-shrink: 0;
}
.breadcrumb-cur {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.22s var(--ease-out);     /* 路由切换时颜色平滑过渡 */
}

.topbar-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.topbar-user {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-page-blue);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-pill);
  padding: 4px 12px 4px 4px;
  color: var(--ink);
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: background var(--t-fast), border-color var(--t-fast);
}
.topbar-user:hover { background: var(--bg-page-2); border-color: var(--accent-blue); }
.user-avatar {
  width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  background: var(--sky-grad-deep);
  color: #fff;
  border-radius: 50%;
  font-size: 11px; font-weight: 600;
}
.user-name { font-weight: 500; }

/* 登录 CTA：浅蓝软底，跟首页副 CTA 同款 */
.topbar-cta {
  display: inline-flex; align-items: center;
  padding: 6px 14px;
  background: var(--accent-blue-bg);          /* 浅蓝软底 */
  color: var(--accent-blue-d);                /* 深空蓝文字 */
  border: 1px solid var(--accent-blue-border);
  border-radius: var(--r-2);
  text-decoration: none;
  font-size: 13px; font-weight: 500;
  transition: all var(--t-fast);
}
.topbar-cta:hover {
  background: var(--accent-blue-border);
  border-color: var(--accent-blue-d);
}

/* ===== 顶栏 MENU 触发按钮(减法清理) ===== */
.topbar-menu-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  background: var(--bg-page-blue);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-2);
  color: var(--ink);
  font-family: inherit;
  cursor: pointer;
  transition: background var(--t-fast), border-color var(--t-fast);
}
.topbar-menu-trigger:hover {
  background: var(--bg-page-2);
  border-color: var(--accent-blue);
}
.topbar-menu-trigger.is-open {
  background: var(--bg-page-2);
  border-color: var(--accent-blue);
}
.trigger-icon {
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--accent-blue-d);
  transition: color var(--t-fast);
}
.topbar-menu-trigger.is-open .trigger-icon { color: var(--accent-blue-d); }
.topbar-menu-trigger .archive-label {
  color: var(--ink-2);
  letter-spacing: 0.28em;
}
.topbar-menu-trigger:hover .archive-label { color: var(--ink); }
.topbar-menu-trigger.is-open .archive-label { color: var(--accent-blue-d); }

/* ⌘K 键盘提示：mono 小字胶囊 */
.trigger-kbd {
  display: inline-flex; align-items: center; justify-content: center;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  background: var(--bg-card);
  border: 1px solid var(--line-blue);
  border-radius: 3px;
  color: var(--ink-3);
  margin-left: 2px;
}

/* ========== Main ========== */
.main-content {
  flex: 1;
  width: 100%;
  min-height: 0;
}
.main-content.is-chat {
  height: 100vh;
}

/* ========== 顶栏响应式 ========== */
@media (max-width: 768px) {
  .topbar { gap: 10px; padding: 0 14px; }
  .topbar-brand { min-height: 44px; }
  .user-name { display: none; }                /* 移动端隐藏用户名，只留头像 */
  .breadcrumb-cur { display: none; }           /* 移动端隐藏面包屑 */
  .breadcrumb-sep { display: none; }
  .trigger-kbd { display: none; }              /* 移动端隐藏 ⌘K 提示 */
  .topbar-menu-trigger { min-height: 44px; padding: 6px 10px; }
  .topbar-cta { min-height: 44px; padding: 0 14px; }
  .topbar-user { min-width: 44px; min-height: 44px; padding: 4px; justify-content: center; }
  .user-avatar { width: 28px; height: 28px; }
}
</style>
