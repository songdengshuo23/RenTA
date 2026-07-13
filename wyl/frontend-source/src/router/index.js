import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  {
    path: '/account',
    name: 'account',
    component: () => import('@/views/AccountView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/agent-apply',
    name: 'agent-apply',
    component: () => import('@/views/AgentApplyView.vue'),
    meta: { requiresAuth: true }
  },
  { path: '/square', name: 'square', component: () => import('@/views/AgentSquareView.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/AgentDashboardView.vue') },
  { path: '/agent/:id', name: 'agent-detail', component: () => import('@/views/AgentDetailView.vue') },
  // 兼容旧链接 /agent-manage → /dashboard?tab=my-agents
  { path: '/agent-manage', redirect: '/dashboard?tab=my-agents' },
  {
    path: '/auth',
    name: 'auth',
    component: () => import('@/views/AuthView.vue'),
    meta: { guestOnly: true }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/billing',
    redirect: '/account?tab=billing'
  },
  {
    path: '/admin/monitor',
    name: 'admin-monitor',
    component: () => import('@/views/AdminMonitorView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/approval',
    name: 'admin-approval',
    component: () => import('@/views/AdminApprovalView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const loggedIn = auth.isLoggedIn

  if (to.meta.requiresAuth && !loggedIn) {
    return { name: 'auth', query: { redirect: to.fullPath } }
  }

  if (to.meta.guestOnly && loggedIn) {
    return { name: 'home' }
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'home' }
  }

  return true
})

export default router
