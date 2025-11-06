/**
 * API配置管理
 * 统一管理所有API端点和请求配置
 */

import { env, log } from './env.js'

// API基础配置
export const API_CONFIG = {
  BASE_URL: env.API_BASE_URL,
  TIMEOUT: 30000, // 增加到30秒
  
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
    DELETE: (id) => `/api/sites/${id}`,
    PLANNING: (id) => `/api/sites/${id}/planning`
  },
  
  
  // 检查相关
  INSPECTIONS: {
    LIST: '/api/inspections/',
    DETAIL: (id) => `/api/inspections/detail/${id}`,
    CREATE: '/api/inspections/',
    UPDATE: (id) => `/api/inspections/detail/${id}`,
    DELETE: (id) => `/api/inspections/${id}`,
    PHOTOS: (id) => `/api/inspections/detail/${id}/photos`,
    DELETE_PHOTO: (photoId) => `/api/inspections/photos/${photoId}`
  },
  
  // 工单（统一工作流）
  WORK_ORDERS: {
    LIST: '/api/work-orders',
    DETAIL: (id) => `/api/work-orders/${id}`,
    CREATE: '/api/work-orders',
    UPDATE: (id) => `/api/work-orders/${id}`,
    ACCEPT: (id) => `/api/work-orders/${id}/accept`,
    RECALL: (id) => `/api/work-orders/${id}/recall`,
    COMPLETE: (id) => `/api/work-orders/${id}/complete`,
    INSPECTION: (id) => `/api/work-orders/${id}/inspection`,
    ITEMS: (id) => `/api/work-orders/${id}/items`,
    PHOTOS: (id) => `/api/work-orders/${id}/photos`,
    DELETE_PHOTO: (photoId) => `/api/work-orders/photos/${photoId}`,
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
    RETURN_PICKUP: '/api/stock/return-pickup',
    TRANSACTIONS: '/api/stock/transactions'
  },
  
  // 系统相关
  SYSTEM: {
    HEALTH: '/health',
    VERSION: '/version'
  },
  
  // 用户日志相关
  LOGS: {
    CREATE: '/api/logs',
    BATCH: '/api/logs/batch',
    LIST: '/api/logs',
    STATS: '/api/logs/stats',
    USER_ACTIVITY: (userId) => `/api/logs/users/${userId}/activity`,
    CLEANUP: '/api/logs/cleanup'
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
 * 构建图片URL
 * @param {string} filePath - 文件相对路径
 * @returns {string} 完整的图片URL
 */
export const buildImageUrl = (filePath) => {
  if (!filePath) return ''
  
  // 如果已经是完整URL，直接返回
  if (filePath.startsWith('http')) {
    return filePath
  }
  
  // 如果是本地临时文件（包括uni-app临时文件路径），直接返回
  if (filePath.includes('temp') || 
      filePath.includes('tmp') ||
      filePath.includes('_tmp_') ||
      filePath.startsWith('wxfile://') ||
      filePath.startsWith('file://') ||
      filePath.startsWith('/var/mobile/') ||
      filePath.includes('uniapp_temp')) {
    return filePath
  }
  
  // 如果路径已经包含 /uploads，直接拼接
  if (filePath.startsWith('/uploads') || filePath.startsWith('uploads')) {
    const cleanPath = filePath.startsWith('/') ? filePath : `/${filePath}`
    return `${API_CONFIG.BASE_URL}${cleanPath}`
  }
  
  // 默认情况，假设是 uploads 目录下的文件
  return `${API_CONFIG.BASE_URL}/${filePath}`
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
