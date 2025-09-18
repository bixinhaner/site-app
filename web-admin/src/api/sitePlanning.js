import apiClient from './auth'

export const sitePlanningApi = {
  getCurrent: (siteId) => apiClient.get(`/api/sites/${siteId}/planning`),
  putPlanning: (siteId, payload) => apiClient.put(`/api/sites/${siteId}/planning`, payload),
  listVersions: (siteId) => apiClient.get(`/api/sites/${siteId}/planning/versions`),
  getVersion: (siteId, version) => apiClient.get(`/api/sites/${siteId}/planning/versions/${version}`),
  restoreVersion: (siteId, version) => apiClient.post(`/api/sites/${siteId}/planning/versions/${version}/restore`),
  listLogs: (siteId, params = {}) => apiClient.get(`/api/sites/${siteId}/planning/logs`, { params }),
  importPlanning: (siteId, file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/${siteId}/planning/upload?dry_run=${dryRun}`
    return apiClient.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  downloadTemplate: () => apiClient.get('/api/sites/planning/import-template', { responseType: 'blob' }),
  downloadTemplateUrl: () => '/api/sites/planning/import-template',
  downloadBatchTemplate: () => apiClient.get('/api/sites/planning/batch-template', { responseType: 'blob' }),
  batchImportPlanning: (file, dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/planning/batch-upload?dry_run=${dryRun}`
    return apiClient.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
}

export default sitePlanningApi
