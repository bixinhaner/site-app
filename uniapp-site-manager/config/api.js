/**
 * API配置管理
 * 统一管理所有API端点和请求配置
 */

import { env, log } from './env.js'

// API基础配置
export const API_CONFIG = {
  BASE_URL: env.API_BASE_URL,
  TIMEOUT: 10000,
  
  // 请求头配置
  HEADERS: {
    'Content-Type': 'application/json'
  }
}

// API端点定义
export const API_ENDPOINTS = {
  // 认证相关
  AUTH: {
    LOGIN: '/api/auth/login',
    REGISTER: '/api/auth/register',
    ME: '/api/auth/me',
    REFRESH: '/api/auth/refresh'
  },
  
  // 用户相关
  USERS: {
    LIST: '/api/users/',
    DETAIL: (id) => `/api/users/${id}`,
    CREATE: '/api/users/',
    UPDATE: (id) => `/api/users/${id}`,
    DELETE: (id) => `/api/users/${id}`
  },
  
  // 站点相关
  SITES: {
    LIST: '/api/sites/',
    DETAIL: (id) => `/api/sites/${id}`,
    CREATE: '/api/sites/',
    UPDATE: (id) => `/api/sites/${id}`,
    DELETE: (id) => `/api/sites/${id}`
  },
  
  // 任务相关
  TASKS: {
    LIST: '/api/tasks/',
    DETAIL: (id) => `/api/tasks/${id}`,
    CREATE: '/api/tasks/',
    UPDATE: (id) => `/api/tasks/${id}`,
    DELETE: (id) => `/api/tasks/${id}`,
    STATUS: (id) => `/api/tasks/${id}/status`,
    ASSIGN: (id) => `/api/tasks/${id}/assign`,
    PHOTOS: (id) => `/api/tasks/${id}/photos`,
    HISTORY: (id) => `/api/tasks/${id}/history`,
    REVIEW: (id) => `/api/tasks/${id}/review`,
    ASSIGNMENTS: (id) => `/api/tasks/${id}/assignments`,
    STATISTICS: {
      OVERVIEW: '/api/tasks/statistics/overview'
    }
  },
  
  // 检查相关
  INSPECTIONS: {
    LIST: '/api/inspections/',
    DETAIL: (id) => `/api/inspections/detail/${id}`,
    CREATE: '/api/inspections/',
    UPDATE: (id) => `/api/inspections/detail/${id}`,
    DELETE: (id) => `/api/inspections/${id}`,
    PHOTOS: (id) => `/api/inspections/detail/${id}/photos`
  },
  
  // 工单（统一工作流）
  WORK_ORDERS: {
    LIST: '/api/work-orders',
    DETAIL: (id) => `/api/work-orders/${id}`,
    CREATE: '/api/work-orders',
    UPDATE: (id) => `/api/work-orders/${id}`,
    ACCEPT: (id) => `/api/work-orders/${id}/accept`,
    COMPLETE: (id) => `/api/work-orders/${id}/complete`,
    INSPECTION: (id) => `/api/work-orders/${id}/inspection`,
    ITEMS: (id) => `/api/work-orders/${id}/items`,
    PHOTOS: (id) => `/api/work-orders/${id}/photos`,
    ITEM_UPDATE: (id, itemId) => `/api/work-orders/${id}/items/${itemId}`
  },
  
  // 设备相关
  EQUIPMENT: {
    LIST: '/api/equipment/',
    DETAIL: (id) => `/api/equipment/${id}`,
    PACKAGES: '/api/equipment/packages',
    PACKAGE_DETAIL: (id) => `/api/equipment/packages/${id}`,
    BARCODE_INFO: (barcode) => `/api/equipment/${barcode}/barcode-info`
  },
  
  // 库存相关
  STOCK: {
    INVENTORY: '/api/stock/inventory',
    SCAN_CHECKOUT: '/api/stock/scan-checkout',
    CONFIRM_PICKUP: '/api/stock/confirm-pickup',
    MY_PICKUPS: '/api/stock/my-pickups',
    TRANSACTIONS: '/api/stock/transactions'
  },
  
  // 系统相关
  SYSTEM: {
    HEALTH: '/health',
    VERSION: '/version'
  }
}

/**
 * 构建完整的API URL
 * @param {string} endpoint - API端点
 * @returns {string} 完整的URL
 */
export const buildApiUrl = (endpoint) => {
  const url = `${API_CONFIG.BASE_URL}${endpoint}`
  log('Building API URL:', url)
  return url
}

/**
 * 获取认证头
 * @param {string} token - 访问令牌
 * @returns {Object} 认证头对象
 */
export const getAuthHeaders = (token) => {
  if (!token) return {}
  
  return {
    'Authorization': `Bearer ${token}`
  }
}

/**
 * 创建请求配置
 * @param {Object} options - 请求选项
 * @returns {Object} 完整的请求配置
 */
export const createRequestConfig = (options = {}) => {
  const config = {
    timeout: API_CONFIG.TIMEOUT,
    header: {
      ...API_CONFIG.HEADERS,
      ...options.headers
    },
    ...options
  }
  
  log('Request config:', config)
  return config
}

// 导出配置信息用于调试
export const getApiInfo = () => {
  return {
    baseUrl: API_CONFIG.BASE_URL,
    environment: env.DEBUG ? 'development' : 'production',
    version: env.APP_VERSION
  }
}
