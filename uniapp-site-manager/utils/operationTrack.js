import { API_CONFIG, buildApiUrl } from '@/config/api.js'
import pagesConfig from '@/pages.json'

const TRACK_ENDPOINT = '/api/operation-logs/track'

const buildPageTitleMap = () => {
  const map = {}
  try {
    const pages = Array.isArray(pagesConfig?.pages) ? pagesConfig.pages : []
    pages.forEach((p) => {
      const key = p?.path
      const title = p?.style?.navigationBarTitleText
      if (key && title) map[key] = title
    })
  } catch (e) {
    // ignore
  }
  return map
}

const PAGE_TITLE_MAP = buildPageTitleMap()

const inferModuleByRoute = (route) => {
  const r = String(route || '')
  if (r.startsWith('pages/site/')) return '站点管理'
  if (r.startsWith('pages/workorder/')) return '工单管理'
  if (r.startsWith('pages/inspection/')) return '检查管理'
  if (r.startsWith('pages/stock/')) return '库存管理'
  if (r.startsWith('pages/map/')) return '地图'
  if (r.startsWith('pages/profile/')) return '个人中心'
  return '系统'
}

export const trackOperation = (payload) => {
  try {
    const token = uni.getStorageSync('token')
    if (!token) return Promise.resolve()

    return new Promise((resolve) => {
      uni.request({
        url: buildApiUrl(TRACK_ENDPOINT),
        method: 'POST',
        header: {
          ...API_CONFIG.HEADERS,
          Authorization: `Bearer ${token}`,
        },
        data: payload,
        timeout: 5000,
        success: () => resolve(),
        fail: () => resolve(),
      })
    })
  } catch (e) {
    return Promise.resolve()
  }
}

export const createDebouncedTracker = (waitMs = 800) => {
  let timer = null
  let lastPayload = null

  return (payload) => {
    lastPayload = payload
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      trackOperation(lastPayload)
    }, waitMs)
  }
}

export const trackPageView = () => {
  try {
    const pages = getCurrentPages()
    const currentPage = pages?.[pages.length - 1]
    const route = currentPage?.route || ''
    if (!route) return
    if (String(route).startsWith('pages/login/')) return

    const title = PAGE_TITLE_MAP[route] || route

    trackOperation({
      module: inferModuleByRoute(route),
      action: '打开页面',
      object_type: '页面',
      object_name: title,
      data: {
        route,
        options: currentPage?.options || {},
      },
    })
  } catch (e) {
    // ignore
  }
}

