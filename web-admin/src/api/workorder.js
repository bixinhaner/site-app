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

// 工单API
export const workOrderAPI = {
  // 搜索工单（带分页和筛选）
  searchWorkOrders: (params = {}) => {
    const searchParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        searchParams.append(key, params[key])
      }
    })
    
    return apiClient.get(`/api/work-orders/search?${searchParams.toString()}`)
  },

  // 获取工单列表
  getWorkOrders: (params = {}) => {
    return apiClient.get('/api/work-orders', { params })
  },

  // 创建工单
  createWorkOrder: (workOrderData) => {
    return apiClient.post('/api/work-orders', workOrderData)
  },

  // 获取工单详情
  getWorkOrder: (workOrderId) => {
    return apiClient.get(`/api/work-orders/${workOrderId}`)
  },

  // 更新工单信息
  updateWorkOrder: (workOrderId, workOrderData) => {
    return apiClient.put(`/api/work-orders/${workOrderId}`, workOrderData)
  },

  // 删除工单
  deleteWorkOrder: (workOrderId) => {
    return apiClient.delete(`/api/work-orders/${workOrderId}`)
  },

  // 接受工单
  acceptWorkOrder: (workOrderId) => {
    return apiClient.post(`/api/work-orders/${workOrderId}/accept`)
  },

  // 提交工单
  submitWorkOrder: (workOrderId) => {
    return apiClient.post(`/api/work-orders/${workOrderId}/submit`)
  },

  // 完成工单
  completeWorkOrder: (workOrderId) => {
    return apiClient.post(`/api/work-orders/${workOrderId}/complete`)
  },

  // 审核工单
  reviewWorkOrder: (workOrderId, reviewData) => {
    return apiClient.post(`/api/work-orders/${workOrderId}/review`, reviewData)
  },

  // 批量操作工单
  batchOperation: (workOrderIds, operation, value = null) => {
    return apiClient.post('/api/work-orders/batch-operation', {
      work_order_ids: workOrderIds,
      operation: operation,
      value: value
    })
  },

  // 获取工单统计信息
  getWorkOrderStats: () => {
    return apiClient.get('/api/work-orders/stats/summary')
  }
}

export default workOrderAPI