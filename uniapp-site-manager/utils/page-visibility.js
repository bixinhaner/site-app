/**
 * 页面可见性管理工具
 * 处理页面显示/隐藏时的数据刷新
 */

class PageVisibilityManager {
  constructor() {
    this.callbacks = new Map()
    this.lastVisibilityChange = Date.now()
    this.refreshThreshold = 30000 // 30秒阈值，超过此时间才刷新
  }

  /**
   * 注册页面显示时的回调函数
   * @param {string} pageId - 页面唯一标识
   * @param {function} callback - 回调函数
   */
  register(pageId, callback) {
    if (typeof callback === 'function') {
      this.callbacks.set(pageId, {
        callback,
        lastRefresh: Date.now()
      })
    }
  }

  /**
   * 注销页面回调
   * @param {string} pageId - 页面唯一标识
   */
  unregister(pageId) {
    this.callbacks.delete(pageId)
  }

  /**
   * 触发页面显示时的刷新
   * @param {string} pageId - 页面唯一标识
   * @param {boolean} force - 是否强制刷新
   */
  triggerRefresh(pageId, force = false) {
    const callbackData = this.callbacks.get(pageId)
    if (!callbackData) return

    const now = Date.now()
    const timeSinceLastRefresh = now - callbackData.lastRefresh

    // 如果强制刷新或者超过阈值时间，则执行刷新
    if (force || timeSinceLastRefresh > this.refreshThreshold) {
      try {
        callbackData.callback()
        callbackData.lastRefresh = now
      } catch (error) {
        console.error('页面刷新回调执行失败:', error)
      }
    }
  }

  /**
   * 设置刷新阈值
   * @param {number} threshold - 阈值时间（毫秒）
   */
  setRefreshThreshold(threshold) {
    this.refreshThreshold = threshold
  }

  /**
   * 检查是否需要刷新
   * @param {string} pageId - 页面唯一标识
   * @returns {boolean}
   */
  shouldRefresh(pageId) {
    const callbackData = this.callbacks.get(pageId)
    if (!callbackData) return false

    const now = Date.now()
    const timeSinceLastRefresh = now - callbackData.lastRefresh
    return timeSinceLastRefresh > this.refreshThreshold
  }
}

// 创建全局实例
const pageVisibilityManager = new PageVisibilityManager()

// 监听应用生命周期
if (typeof uni !== 'undefined') {
  // 应用显示时触发所有注册的刷新回调
  uni.onAppShow(() => {
    const callbacks = pageVisibilityManager.callbacks
    callbacks.forEach((callbackData, pageId) => {
      pageVisibilityManager.triggerRefresh(pageId)
    })
  })

  // 应用隐藏时更新时间戳
  uni.onAppHide(() => {
    pageVisibilityManager.lastVisibilityChange = Date.now()
  })
}

export default pageVisibilityManager

/**
 * 页面数据刷新组合式函数
 * @param {string} pageId - 页面唯一标识
 * @param {function} refreshCallback - 刷新数据的回调函数
 * @param {object} options - 选项
 */
export function usePageRefresh(pageId, refreshCallback, options = {}) {
  const { 
    threshold = 30000,  // 默认30秒
    autoRegister = true // 是否自动注册
  } = options

  // 设置阈值
  pageVisibilityManager.setRefreshThreshold(threshold)

  // 注册刷新回调
  const register = () => {
    pageVisibilityManager.register(pageId, refreshCallback)
  }

  // 注销回调
  const unregister = () => {
    pageVisibilityManager.unregister(pageId)
  }

  // 手动触发刷新
  const refresh = (force = false) => {
    pageVisibilityManager.triggerRefresh(pageId, force)
  }

  // 检查是否需要刷新
  const shouldRefresh = () => {
    return pageVisibilityManager.shouldRefresh(pageId)
  }

  // 如果启用自动注册，立即注册
  if (autoRegister) {
    register()
  }

  return {
    register,
    unregister,
    refresh,
    shouldRefresh
  }
}