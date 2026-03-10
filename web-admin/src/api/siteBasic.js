import request from '@/utils/request'

export const siteBasicApi = {
  downloadTemplate: () => request.get('/api/sites/basic/batch-template', { responseType: 'blob' }),
  batchUpload: (file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/basic/batch-upload?dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  downloadUpdateTemplate: () => request.get('/api/sites/basic/batch-update-template', { responseType: 'blob' }),
  batchUpdateUpload: (file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/basic/batch-update-upload?dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  listImportHistory: (params = {}) => request.get('/api/sites/basic/import-history', { params }),
  getImportHistoryDetail: (batchId) => request.get(`/api/sites/basic/import-history/${batchId}`),
  createSite: (payload) => request.post('/api/sites/', payload),
  listSites: (params = {}) => request.get('/api/sites/', { params }),
}

export default siteBasicApi
