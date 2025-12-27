import request from '@/utils/request'
import config from '@/config/env.js'

export const mobileClientLogsApi = {
  page: (params) => request.get('/api/mobile-logs/page', { params }),
  detail: (id) => request.get(`/api/mobile-logs/${id}`),
  getSettings: () => request.get('/api/mobile-logs/settings'),
  updateSettings: (data) => request.put('/api/mobile-logs/settings', data),
  cleanup: (data) => request.post('/api/mobile-logs/cleanup', data),
  exportExcel: (params) => request.get('/api/mobile-logs/export', {
    params,
    responseType: 'blob',
    timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
  }),
}
