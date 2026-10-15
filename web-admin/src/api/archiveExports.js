import request from '@/utils/request'
import config from '@/config/env.js'

// 档案批量导出 PDF：导出前预估确认 + 后台任务 + 轮询进度 + 分卷直链下载
export const archiveExportsApi = {
  preview(data) {
    return request.post('/api/archive-exports/preview', data, {
      timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
    })
  },
  create(data) {
    return request.post('/api/archive-exports', data)
  },
  get(jobId) {
    return request.get(`/api/archive-exports/${encodeURIComponent(jobId)}`)
  },
  downloadUrl(jobId, part = 1) {
    return `${config.API_BASE_URL}/api/archive-exports/${encodeURIComponent(jobId)}/download?part=${part}`
  },
}
