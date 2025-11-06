import request from '@/utils/request'

export const surveyArchivesApi = {
  page(params) {
    return request.get('/api/survey-archives/page', { params })
  },
  get(id) {
    return request.get(`/api/survey-archives/${id}`)
  },
  history(id) {
    return request.get(`/api/survey-archives/${id}/history`)
  },
  diff(id, a, b) {
    return request.get(`/api/survey-archives/${id}/diff`, { params: { a, b } })
  },
  patch(id, patchOps, baseVersion, changeSummary) {
    const params = {}
    if (baseVersion != null) params.base_version = baseVersion
    if (changeSummary) params.change_summary = changeSummary
    return request.patch(`/api/survey-archives/${id}`, patchOps, { params })
  },
  revert(id, toVersion) {
    return request.post(`/api/survey-archives/${id}/revert`, null, { params: { to_version: toVersion } })
  },
  uploadPhoto(id, { category_id, item_id, file }) {
    const fd = new FormData()
    fd.append('category_id', category_id)
    fd.append('item_id', item_id)
    fd.append('file', file)
    // 明确为 multipart/form-data，覆盖实例默认的 application/json
    return request.post(`/api/survey-archives/${id}/photos`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  uploadTempPhoto(id, { category_id, item_id, file }) {
    const fd = new FormData()
    fd.append('category_id', category_id)
    fd.append('item_id', item_id)
    fd.append('file', file)
    return request.post(`/api/survey-archives/${id}/photos/temp`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deletePhoto(id, photoId) {
    return request.delete(`/api/survey-archives/${id}/photos/${photoId}`)
  },
  reindex(id, version) {
    return request.post(`/api/survey-archives/${id}/reindex`, null, { params: { version } })
  },
  search(params) {
    return request.get('/api/survey-archives/search', { params })
  },
  exportZip(id) {
    return request.get(`/api/survey-archives/${id}/export`, { responseType: 'blob' })
  },
  exportPdf(id) {
    return request.get(`/api/survey-archives/${id}/export-pdf`, { responseType: 'blob' })
  },
}
