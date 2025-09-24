import axios from 'axios'
import config from '@/config/env.js'

const API_BASE_URL = config.API_BASE_URL

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 - 处理401错误
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // 清除token并跳转到登录页
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 用户API
export const userAPI = {
  // 搜索用户（带分页和筛选）
  searchUsers: (params = {}) => {
    const searchParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        searchParams.append(key, params[key])
      }
    })
    
    return apiClient.get(`/api/users/search?${searchParams.toString()}`)
  },

  // 获取用户列表
  getUsers: (skip = 0, limit = 100) => {
    return apiClient.get(`/api/users/?skip=${skip}&limit=${limit}`)
  },

  // 创建用户
  createUser: (userData) => {
    return apiClient.post('/api/users/', userData)
  },

  // 获取用户详情
  getUser: (userId) => {
    return apiClient.get(`/api/users/${userId}`)
  },

  // 更新用户信息
  updateUser: (userId, userData) => {
    return apiClient.put(`/api/users/${userId}`, userData)
  },

  // 删除用户（软删除）
  deleteUser: (userId) => {
    return apiClient.delete(`/api/users/${userId}`)
  },

  // 重置用户密码
  resetPassword: (userId, newPassword) => {
    return apiClient.post('/api/users/reset-password', {
      user_id: userId,
      new_password: newPassword
    })
  },

  // 批量操作用户
  batchOperation: (userIds, operation, value = null) => {
    return apiClient.post('/api/users/batch-operation', {
      user_ids: userIds,
      operation: operation,
      value: value
    })
  },

  // 获取用户统计信息
  getUserStats: () => {
    return apiClient.get('/api/users/stats/summary')
  }
}

export default userAPI