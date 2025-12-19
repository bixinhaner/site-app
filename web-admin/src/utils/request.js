import axios from 'axios'
import config from '@/config/env.js'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

// 创建axios实例
const request = axios.create({
  baseURL: config.API_BASE_URL,
  timeout: config.TIMEOUT || 10000,
  headers: {
    'Content-Type': 'application/json',
    'X-Client': 'web-admin',
  }
})

let isRefreshing = false
let requestQueue = []

// 刷新 token，使用 refresh_token 请求 /api/auth/refresh
async function refreshToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('No refresh token')

  const response = await axios.post(
    `${config.API_BASE_URL}/api/auth/refresh`,
    { refresh_token: refreshToken }
  )

  const { access_token, refresh_token: newRefresh } = response.data || {}
  if (!access_token) throw new Error('Refresh failed')

  localStorage.setItem('access_token', access_token)
  if (newRefresh) localStorage.setItem('refresh_token', newRefresh)
  return access_token
}

function addRequestToQueue(config) {
  return new Promise((resolve, reject) => {
    requestQueue.push({ config, resolve, reject })
  })
}

function retryRequestQueue(newToken) {
  requestQueue.forEach(({ config, resolve, reject }) => {
    config.headers.Authorization = `Bearer ${newToken}`
    request(config).then(resolve).catch(reject)
  })
  requestQueue = []
}

function clearRequestQueue(error) {
  requestQueue.forEach(({ reject }) => reject(error))
  requestQueue = []
}

// 请求拦截器 - 添加token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理token过期和自动刷新
request.interceptors.response.use(
  (response) => {
    // 成功响应直接返回data
    return response.data
  },
  async (error) => {
    const originalRequest = error.config

    // 登录接口返回401时，不做自动刷新，直接把错误抛给调用方处理
    if (error.response?.status === 401 && originalRequest?.url?.includes('/api/auth/login')) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return addRequestToQueue(originalRequest)
      }
      originalRequest._retry = true
      isRefreshing = true
      try {
        const newToken = await refreshToken()
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        retryRequestQueue(newToken)
        isRefreshing = false
        return request(originalRequest)
      } catch (refreshError) {
        isRefreshing = false
        clearRequestQueue(refreshError)
        const userStore = useUserStore()
        userStore.logout()
        ElMessage.error('登录已过期，请重新登录')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default request
