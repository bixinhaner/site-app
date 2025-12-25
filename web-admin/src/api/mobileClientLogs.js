import request from '@/utils/request'

export const mobileClientLogsApi = {
  page: (params) => request.get('/api/mobile-logs/page', { params }),
  detail: (id) => request.get(`/api/mobile-logs/${id}`),
  getSettings: () => request.get('/api/mobile-logs/settings'),
  updateSettings: (data) => request.put('/api/mobile-logs/settings', data),
}

