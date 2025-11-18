import request from '@/utils/request'

export const sitePlanningApi = {
  getCurrent: (siteId) => request.get(`/api/sites/${siteId}/planning`),
  putPlanning: (siteId, payload) => request.put(`/api/sites/${siteId}/planning`, payload),
  listVersions: (siteId) => request.get(`/api/sites/${siteId}/planning/versions`),
  getVersion: (siteId, version) => request.get(`/api/sites/${siteId}/planning/versions/${version}`),
  restoreVersion: (siteId, version) => request.post(`/api/sites/${siteId}/planning/versions/${version}/restore`),
  listLogs: (siteId, params = {}) => request.get(`/api/sites/${siteId}/planning/logs`, { params }),
  importPlanning: (siteId, file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/${siteId}/planning/upload?dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  downloadTemplate: () => request.get('/api/sites/planning/import-template', { responseType: 'blob' }),
  downloadTemplateUrl: () => '/api/sites/planning/import-template',
  downloadBatchTemplate: () => request.get('/api/sites/planning/batch-template', { responseType: 'blob' }),
  batchImportPlanning: (file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/planning/batch-upload?dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  // LLD 新版规划导入/查询接口
  downloadLldBatchTemplate: () => request.get('/api/sites/planning/lld-batch-template', { responseType: 'blob' }),
  lldBatchImportPlanning: (file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/planning/lld-batch-upload?dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  lldImportPlanning: (siteId, file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/${siteId}/planning/lld-upload?dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  getLldPlanning: (siteId) => request.get(`/api/sites/${siteId}/planning/lld`),
}

export default sitePlanningApi
