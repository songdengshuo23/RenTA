import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(readUser())

  const isLoggedIn = computed(() => {
    const current = user.value
    return Boolean(current && current.username && (current.user_id || current.id))
  })

  const isAdmin = computed(() => {
    const current = user.value
    return Boolean(
      current &&
      (current.is_admin === true ||
        current.is_admin === 1 ||
        (Array.isArray(current.roles) && current.roles.some((role) => /admin/i.test(String(role)))))
    )
  })

  const userId = computed(() => user.value?.user_id || user.value?.id || '')
  const username = computed(() => user.value?.username || '')

  function login(nextUser) {
    const normalized = normalizeUser(nextUser)
    user.value = normalized
    localStorage.setItem('user', JSON.stringify(normalized))
  }

  function updateUser(nextUser) {
    if (!nextUser || typeof nextUser !== 'object') return
    const normalized = normalizeUser({ ...(user.value || {}), ...nextUser })
    user.value = normalized
    localStorage.setItem('user', JSON.stringify(normalized))
  }

  function logout() {
    try {
      const request = api.post('/auth/logout')
      request?.catch?.(() => {})
    } catch {}
    user.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  function updateAvatar(avatar) {
    if (!user.value) return
    user.value.avatar = avatar
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  return { user, isLoggedIn, isAdmin, userId, username, login, logout, updateUser, updateAvatar }
})

function readUser() {
  try {
    const raw = localStorage.getItem('user')
    if (!raw) return null
    return normalizeUser(JSON.parse(raw))
  } catch {
    localStorage.removeItem('user')
    return null
  }
}

function normalizeUser(value) {
  if (!value || typeof value !== 'object') return null
  const normalized = { ...value }
  if (!normalized.user_id && normalized.id) normalized.user_id = normalized.id
  return normalized
}
