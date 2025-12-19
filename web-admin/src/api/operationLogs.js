import request from '@/utils/request'
import config from '@/config/env.js'

export const operationLogsApi = {
  page: (params) => request.get('/api/operation-logs/page', { params }),
  detail: (id) => request.get(`/api/operation-logs/${id}`),
  options: (params) => request.get('/api/operation-logs/options', { params }),
  getSettings: () => request.get('/api/operation-logs/settings'),
  updateSettings: (data) => request.put('/api/operation-logs/settings', data),
  cleanup: (data) => request.post('/api/operation-logs/cleanup', data),
  exportExcel: (params) => request.get('/api/operation-logs/export', {
    params,
    responseType: 'blob',
    timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
  }),
}

