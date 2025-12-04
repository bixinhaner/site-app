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

export default systemBackupApi
