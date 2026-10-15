import request from '@/utils/request'
import config from '@/config/env.js'

// 档案批量导出 PDF：后台任务 + 轮询进度 + 直链下载
export const archiveExportsApi = {
  create(data) {
    return request.post('/api/archive-exports', data)
  },
  get(jobId) {
    return request.get(`/api/archive-exports/${encodeURIComponent(jobId)}`)
  },
  downloadUrl(jobId) {
    return `${config.API_BASE_URL}/api/archive-exports/${encodeURIComponent(jobId)}/download`
  },
}
