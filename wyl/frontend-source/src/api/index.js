import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
})

export const modeRouterApi = axios.create({
  baseURL: '/mode-router',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use(
  attachAuthHeader,
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => unwrapResponse(response),
  async (error) => {
    const status = error.response?.status
    const config = error.config

    if (status === 401 && config && !config._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        config._retry = true
        try {
          const refresh = await axios.post('/api/auth/refresh-token', { refresh_token: refreshToken })
          const payload = refresh.data || {}
          const token = payload.access_token || payload.token
          if (!token) throw new Error('刷新 token 失败')
          localStorage.setItem('access_token', token)
          if (payload.refresh_token) localStorage.setItem('refresh_token', payload.refresh_token)
          config.headers.Authorization = `Bearer ${token}`
          return api(config)
        } catch (refreshError) {
          clearAuthStorage()
          const redirect = encodeURIComponent(window.location.pathname + window.location.search)
          window.location.href = `/auth?redirect=${redirect}`
          return Promise.reject(new ApiError('登录已过期,请重新登录', 401, refreshError.response?.data))
        }
      }
    }

    const data = error.response?.data
    const message = extractMessage(data) || error.message || '网络错误'
    return Promise.reject(new ApiError(message, status, data))
  }
)

modeRouterApi.interceptors.request.use(
  attachAuthHeader,
  (error) => Promise.reject(error)
)

modeRouterApi.interceptors.response.use(
  (response) => unwrapResponse(response),
  (error) => handleModeRouterError(error)
)

function attachAuthHeader(config) {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
}

async function handleModeRouterError(error) {
  const status = error.response?.status
  const config = error.config

  if (status === 401 && config && !config._retry) {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      config._retry = true
      try {
        const refresh = await axios.post('/api/auth/refresh-token', { refresh_token: refreshToken })
        const payload = refresh.data || {}
        const token = payload.access_token || payload.token
        if (!token) throw new Error('刷新 token 失败')
        localStorage.setItem('access_token', token)
        if (payload.refresh_token) localStorage.setItem('refresh_token', payload.refresh_token)
        config.headers.Authorization = `Bearer ${token}`
        return modeRouterApi(config)
      } catch (refreshError) {
        clearAuthStorage()
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/auth?redirect=${redirect}`
        return Promise.reject(new ApiError('登录已过期,请重新登录', 401, refreshError.response?.data))
      }
    }
  }

  const data = error.response?.data
  const message = extractMessage(data) || error.message || '网络错误'
  return Promise.reject(new ApiError(message, status, data))
}

function unwrapResponse(response) {
  const data = response.data
  if (!data || typeof data !== 'object') return data
  if (typeof data.status_code === 'number' && data.status_code >= 400 && (data.error_msg || data.error_name)) {
    return Promise.reject(new ApiError(extractMessage(data), data.status_code, data))
  }
  if ('detail' in data && !('data' in data)) {
    return Promise.reject(new ApiError(formatDetail(data.detail), response.status, data))
  }
  if ('status' in data && 'data' in data) {
    if (data.status === 'error') {
      return Promise.reject(new ApiError(data.message || '操作失败', response.status, data))
    }
    return data.data
  }
  return data
}

function clearAuthStorage() {
  localStorage.removeItem('user')
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

function formatDetail(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const loc = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : ''
      return loc ? `${loc}: ${item.msg}` : item.msg || JSON.stringify(item)
    }).join('; ')
  }
  return JSON.stringify(detail)
}

const errorMessages = {
  invalid_credentials: '用户名或密码错误',
  invalid_token: '登录已过期,请重新登录',
  token_expired: '登录已过期',
  insufficient_permissions: '权限不足',
  forbidden: '无权访问',
  not_found: '资源不存在',
  validation_error: '输入参数有误',
  rate_limited: '操作过于频繁,请稍后再试',
  server_error: '服务器内部错误,请稍后重试',
  network_error: '网络连接失败'
}

function extractMessage(data) {
  if (!data) return ''
  if (data.error_name && errorMessages[data.error_name]) return errorMessages[data.error_name]
  if (data.error_msg) return data.error_msg
  if (data.detail) return formatDetail(data.detail)
  if (data.message) return data.message
  return ''
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export default api
