import axios from 'axios'
import config from '@/config/env.js'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

// 创建axios实例
const request = axios.create({
  baseURL: config.API_BASE_URL,
  timeout: config.TIMEOUT || 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 是否正在刷新token的标志
let isRefreshing = false
// 待重试的请求队列
let requestQueue = []

/**
 * 刷新token
 */
async function refreshToken() {
  const token = localStorage.getItem('access_token')
  if (!token) {
    throw new Error('No token available')
  }
  
  try {
    const response = await axios.post(
      `${config.API_BASE_URL}/api/auth/refresh`,
      {},
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    )
    
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token)
      if (response.data.user) {
        localStorage.setItem('user_info', JSON.stringify(response.data.user))
      }
      return response.data.access_token
    }
    throw new Error('Refresh token failed')
  } catch (error) {
    // 刷新失败，清除token
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    throw error
  }
}

/**
 * 将失败的请求加入队列
 */
function addRequestToQueue(config) {
  return new Promise((resolve, reject) => {
    requestQueue.push({ config, resolve, reject })
  })
}

/**
 * 重试队列中的所有请求
 */
function retryRequestQueue(newToken) {
  requestQueue.forEach(({ config, resolve, reject }) => {
    config.headers.Authorization = `Bearer ${newToken}`
    request(config).then(resolve).catch(reject)
  })
  requestQueue = []
}

/**
 * 清空请求队列
 */
function clearRequestQueue(error) {
  requestQueue.forEach(({ reject }) => {
    reject(error)
  })
  requestQueue = []
}

// 请求拦截器 - 添加token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
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
    
    // 如果是401错误且不是刷新token的请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 如果正在刷新token，将请求加入队列
      if (isRefreshing) {
        try {
          const newToken = await addRequestToQueue(originalRequest)
          return request(originalRequest)
        } catch (err) {
          return Promise.reject(err)
        }
      }
      
      // 标记该请求已重试过，避免无限循环
      originalRequest._retry = true
      isRefreshing = true
      
      try {
        // 尝试刷新token
        const newToken = await refreshToken()
        
        // 刷新成功，更新请求头
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        
        // 重试队列中的所有请求
        retryRequestQueue(newToken)
        
        // 重置刷新标志
        isRefreshing = false
        
        // 重新发起原始请求
        return request(originalRequest)
      } catch (refreshError) {
        // 刷新token失败，清空队列并跳转登录页
        isRefreshing = false
        clearRequestQueue(refreshError)
        
        // 清除用户信息
        const userStore = useUserStore()
        userStore.logout()
        
        // 显示提示消息
        ElMessage.error('登录已过期，请重新登录')
        
        // 跳转到登录页
        window.location.href = '/login'
        
        return Promise.reject(refreshError)
      }
    }
    
    // 其他错误直接拒绝
    return Promise.reject(error)
  }
)

export default request
