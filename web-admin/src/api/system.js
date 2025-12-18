import request from '@/utils/request'

// 系统备份相关 API
export const systemBackupApi = {
  // 获取备份配置
  getConfig() {
    return request.get('/api/system/backup/config')
  },

  // 更新备份配置
  updateConfig(data) {
    return request.put('/api/system/backup/config', data)
  },

  // 手动触发备份
  runBackup() {
    return request.post('/api/system/backup/run')
  },

  // 获取备份历史
  getHistory(params = {}) {
    return request.get('/api/system/backup/history', { params })
  },

  // 获取恢复操作历史
  getRestoreHistory(params = {}) {
    return request.get('/api/system/backup/restore-history', { params })
  },

  // 从指定备份记录恢复
  restore(id, confirm) {
    return request.post(`/api/system/backup/${id}/restore`, { confirm })
  },
}

// 移动端设置相关 API（包含定位模式）
export const mobileSettingsApi = {
  // 获取完整移动端配置（包含默认 / 按角色 / 按用户）
  getMobileSettings() {
    return request.get('/api/system/mobile-settings')
  },

  // 更新完整移动端配置
  updateMobileSettings(data) {
    return request.put('/api/system/mobile-settings', data)
  },

  // 兼容旧接口：仅获取/设置全局默认定位模式
  getLocationMode() {
    return request.get('/api/system/location-mode')
  },

  updateLocationMode(mode) {
    return request.put('/api/system/location-mode', { mode })
  },
}

// 逆地理缓存观测相关 API
export const geocodeCacheApi = {
  getStats() {
    return request.get('/api/system/geocode-cache/stats')
  },

  getEntries(params = {}) {
    return request.get('/api/system/geocode-cache/entries', { params })
  },

  // 与移动端“在线逆地理（国内Baidu/海外Google）”一致：调用后端 /api/geo/baidu-reverse
  reverseGeocode(params) {
    return request.get('/api/geo/baidu-reverse', { params })
  },
}

export default systemBackupApi
