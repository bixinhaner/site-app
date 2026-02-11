/**
 * API配置管理
 * 统一管理所有API端点和请求配置
 */

import { env, log } from './env.js'

const API_BASE_URL_STORAGE_KEY = 'api_base_url'
const API_SERVER_KEY_STORAGE_KEY = 'api_server_key'

export const API_SERVERS = [
  {
    key: 'id',
    name: 'Indonesia',
    baseUrl: 'https://siteapp.indonesiacentral.cloudapp.azure.com',
    flagIcon: '/static/flags/id.svg',
  },
  {
    key: 'cn',
    name: 'China',
    baseUrl: 'http://113.45.25.135/api',
    flagIcon: '/static/flags/cn.svg',
  },
]

export const DEFAULT_API_SERVER_KEY = 'id'

const safeGetStorageSync = (key) => {
  try {
    if (typeof uni === 'undefined' || typeof uni.getStorageSync !== 'function') return ''
    return uni.getStorageSync(key)
  } catch (e) {
    return ''
  }
}

const safeSetStorageSync = (key, value) => {
  try {
    if (typeof uni === 'undefined' || typeof uni.setStorageSync !== 'function') return
    uni.setStorageSync(key, value)
  } catch (e) {
    // ignore
  }
}

const safeRemoveStorageSync = (key) => {
  try {
    if (typeof uni === 'undefined' || typeof uni.removeStorageSync !== 'function') return
    uni.removeStorageSync(key)
  } catch (e) {
    // ignore
  }
}

export const normalizeApiBaseUrl = (rawUrl) => {
  let url = String(rawUrl || '').trim()
  if (!url) return ''

  url = url.replace(/\/+$/, '')
  url = url.replace(/\/+$/, '')

  return url
}

export const normalizeApiBaseUrlForMatch = (rawUrl) => {
  let url = normalizeApiBaseUrl(rawUrl)
  url = url.replace(/\/api$/, '')
  url = url.replace(/\/+$/, '')
  return url
}

const resolveServerByKey = (serverKey) => {
  if (!serverKey) return null
  return API_SERVERS.find((s) => s.key === serverKey) || null
}

const resolveServerByBaseUrlForMatch = (rawUrl) => {
  const match = normalizeApiBaseUrlForMatch(rawUrl)
  if (!match) return null
  return API_SERVERS.find((s) => normalizeApiBaseUrlForMatch(s.baseUrl) === match) || null
}

export const getApiServerKey = () => {
  const key = String(safeGetStorageSync(API_SERVER_KEY_STORAGE_KEY) || '').trim()
  return key || DEFAULT_API_SERVER_KEY
}

export const setApiServerKey = (serverKey) => {
  const key = String(serverKey || '').trim()
  if (!key) {
    safeRemoveStorageSync(API_SERVER_KEY_STORAGE_KEY)
    return
  }
  safeSetStorageSync(API_SERVER_KEY_STORAGE_KEY, key)
}

export const getApiBaseUrl = () => {
  // 优先使用已选择的 server key（避免 baseUrl 旧值导致路由不一致）
  const storedKey = String(safeGetStorageSync(API_SERVER_KEY_STORAGE_KEY) || '').trim()
  const serverByKey = resolveServerByKey(storedKey)
  if (serverByKey?.baseUrl) {
    const canonical = normalizeApiBaseUrl(serverByKey.baseUrl)
    // 统一写回 baseUrl，便于调试与兼容历史逻辑
    if (canonical) safeSetStorageSync(API_BASE_URL_STORAGE_KEY, canonical)
    return canonical
  }

  // 兼容历史：仅存了 baseUrl 的情况
  const stored = normalizeApiBaseUrl(safeGetStorageSync(API_BASE_URL_STORAGE_KEY))
  if (stored) {
    const matched = resolveServerByBaseUrlForMatch(stored)
    if (matched?.baseUrl) {
      const canonical = normalizeApiBaseUrl(matched.baseUrl)
      // 记住 server key，并把 baseUrl 规范成当前 server 配置（例如 CN 需要 /api 前缀）
      setApiServerKey(matched.key)
      if (canonical && canonical !== stored) safeSetStorageSync(API_BASE_URL_STORAGE_KEY, canonical)
      return canonical
    }
    return stored
  }

  const defaultServer = API_SERVERS.find((s) => s.key === DEFAULT_API_SERVER_KEY) || API_SERVERS[0]
  const canonical = normalizeApiBaseUrl(defaultServer?.baseUrl)
  if (defaultServer?.key) setApiServerKey(defaultServer.key)
  if (canonical) safeSetStorageSync(API_BASE_URL_STORAGE_KEY, canonical)
  return canonical
}

export const setApiBaseUrl = (baseUrl) => {
  const normalized = normalizeApiBaseUrl(baseUrl)
  if (!normalized) {
    safeRemoveStorageSync(API_BASE_URL_STORAGE_KEY)
    safeRemoveStorageSync(API_SERVER_KEY_STORAGE_KEY)
    return
  }
  const matched = resolveServerByBaseUrlForMatch(normalized)
  if (matched?.key) safeSetStorageSync(API_SERVER_KEY_STORAGE_KEY, matched.key)
  safeSetStorageSync(API_BASE_URL_STORAGE_KEY, normalized)
}

export const getCurrentApiServer = () => {
  const baseUrl = getApiBaseUrl()
  const normalized = normalizeApiBaseUrlForMatch(baseUrl)
  const hit = API_SERVERS.find((s) => normalizeApiBaseUrlForMatch(s.baseUrl) === normalized)
  return hit || API_SERVERS.find((s) => s.key === DEFAULT_API_SERVER_KEY) || API_SERVERS[0]
}

export const setCurrentApiServer = (serverKey) => {
  const hit = API_SERVERS.find((s) => s.key === serverKey)
  if (!hit) return
  setApiServerKey(hit.key)
  setApiBaseUrl(hit.baseUrl)
}

// API基础配置
export const API_CONFIG = {
  get BASE_URL() {
    return getApiBaseUrl()
  },
  TIMEOUT: 30000, // 增加到30秒

  // 请求头配置
  HEADERS: {
    'Content-Type': 'application/json',
    'X-Client': 'uniapp',
  }
}

// API端点定义
export const API_ENDPOINTS = {
  // 认证相关
  AUTH: {
    LOGIN: '/api/auth/login',
    REGISTER: '/api/auth/register',
    ME: '/api/auth/me',
    REFRESH: '/api/auth/refresh',
    CHANGE_PASSWORD: '/api/auth/change-password',
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
    PLANNING: (id) => `/api/sites/${id}/planning`,
    OMC_STATUS: (id) => `/api/sites/${id}/omc/devices`,
    OMC_STATUS_EVER: (id) => `/api/sites/${id}/omc/devices/ever`
  },


  // 检查相关
  INSPECTIONS: {
    LIST: '/api/inspections/',
    DETAIL: (id) => `/api/inspections/detail/${id}`,
    CREATE: '/api/inspections/',
    UPDATE: (id) => `/api/inspections/detail/${id}`,
    DELETE: (id) => `/api/inspections/${id}`,
    PHOTO_PRECHECK: (id) => `/api/inspections/detail/${id}/photos/precheck`,
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
    // 新流程：物料申请 / 领料单 / 快速出库 / 退库（按出库单明细）
    FLOW_SETTINGS: '/api/stock/flow-settings',
    MATERIAL_REQUESTS: '/api/stock/material-requests',
    MATERIAL_REQUEST_DETAIL: (id) => `/api/stock/material-requests/${id}`,
    MATERIAL_REQUEST_SUBMIT: (id) => `/api/stock/material-requests/${id}/submit`,
    MATERIAL_REQUEST_CANCEL: (id) => `/api/stock/material-requests/${id}/cancel`,
    ISSUE_DRAFTS: '/api/stock/issue-drafts',
    ISSUE_DRAFT_DETAIL: (id) => `/api/stock/issue-drafts/${id}`,
    ISSUE_DRAFT_SCAN_MAIN: (id) => `/api/stock/issue-drafts/${id}/scan-main`,
    ISSUE_DRAFT_SERIAL_DELETE: (draftId, serialId) => `/api/stock/issue-drafts/${draftId}/serials/${serialId}`,
    ISSUE_DRAFT_AUX_ITEMS: (id) => `/api/stock/issue-drafts/${id}/aux-items`,
    ISSUE_DRAFT_SUBMIT: (id) => `/api/stock/issue-drafts/${id}/submit`,
    ISSUE_DRAFT_CANCEL: (id) => `/api/stock/issue-drafts/${id}/cancel`,
    MANUAL_STOCK_OUT: '/api/stock/manual-stock-out',
    MY_STOCK_OUTS: '/api/stock/my-stock-outs',
    CREATE_RETURN: '/api/stock/returns',
    MY_RETURNS: '/api/stock/my-returns',
    SCAN_CHECKOUT: '/api/stock/scan-checkout',
    CONFIRM_PICKUP: '/api/stock/confirm-pickup',
    MY_PICKUPS: '/api/stock/my-pickups',
    RETURN_PICKUP: '/api/stock/return-pickup',
    SCAN_RETURN_PREVIEW: '/api/stock/scan-return/preview',
    SCAN_RETURN_UNBIND: '/api/stock/scan-return/unbind',
    SCAN_RETURN_REQUEST: '/api/stock/scan-return/request',
    SCAN_RETURN_CANCEL: '/api/stock/scan-return/cancel',
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
  },

  // App版本升级
  APP_VERSION: {
    BASE: '/api/app-version',
    CHECK: '/api/app-version/check',
    LATEST: '/api/app-version/latest',
    DOWNLOAD_START: '/api/app-version/download-start',
    DOWNLOAD_COMPLETE: '/api/app-version/download-complete'
  }
}

/**
 * 构建完整的API URL
 * @param {string} endpoint - API端点
 * @returns {string} 完整的URL
 */
export const buildApiUrl = (endpoint) => {
  if (!endpoint) return API_CONFIG.BASE_URL
  if (String(endpoint).startsWith('http')) return endpoint
  const baseUrl = normalizeApiBaseUrl(API_CONFIG.BASE_URL)
  let path = String(endpoint || '')

  const url = `${baseUrl}${path}`
  return url
}

/**
 * 判断是否为本地图片路径（不应拼接 API BASE URL）
 * @param {string} filePath
 * @returns {boolean}
 */
export const isLocalImagePath = (filePath) => {
  const raw = String(filePath || '').trim()
  if (!raw) return false

  const lower = raw.toLowerCase()
  if (
    lower.startsWith('file://') ||
    lower.startsWith('content://') ||
    lower.startsWith('wxfile://') ||
    lower.startsWith('blob:') ||
    lower.startsWith('data:image/')
  ) {
    return true
  }

  // 绝对路径但并非服务端 uploads 路径时，视为本地文件
  if (raw.startsWith('/') && !raw.startsWith('/uploads')) {
    return true
  }

  if (
    lower.includes('/storage/') ||
    lower.includes('/sdcard/') ||
    lower.includes('/data/user/') ||
    lower.includes('/cache/') ||
    lower.includes('/tmp/') ||
    lower.includes('_doc/') ||
    lower.includes('uniapp_temp') ||
    lower.includes('dcim/')
  ) {
    return true
  }

  if (
    lower.includes('temp') ||
    lower.includes('_tmp_')
  ) {
    return true
  }

  return false
}

/**
 * 构建图片URL
 * @param {string} filePath - 文件相对路径
 * @returns {string} 完整的图片URL
 */
export const buildImageUrl = (filePath) => {
  if (!filePath) return ''

  const rawPath = String(filePath || '').trim()

  // 如果已经是完整URL，直接返回
  if (rawPath.startsWith('http')) {
    return rawPath
  }

  // 本地路径不拼接API域名
  if (isLocalImagePath(rawPath)) {
    return rawPath
  }

  // 如果路径已经包含 /uploads，直接拼接
  if (rawPath.startsWith('/uploads') || rawPath.startsWith('uploads')) {
    const cleanPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`
    return `${API_CONFIG.BASE_URL}${cleanPath}`
  }

  // 默认情况，假设是 uploads 目录下的文件
  return `${API_CONFIG.BASE_URL}/${rawPath}`
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

  return config
}

// 导出配置信息用于调试
export const getApiInfo = () => {
  return {
    baseUrl: getApiBaseUrl(),
    environment: env.DEBUG ? 'development' : 'production',
    version: env.APP_VERSION
  }
}
