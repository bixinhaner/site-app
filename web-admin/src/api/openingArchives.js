import request from '@/utils/request'
import config from '@/config/env.js'

export const openingArchivesApi = {
  page(params) {
    return request.get('/api/opening-archives/page', { params })
  },
  get(id) {
    return request.get(`/api/opening-archives/${id}`)
  },
  history(id) {
    return request.get(`/api/opening-archives/${id}/history`)
  },
  diff(id, a, b) {
    return request.get(`/api/opening-archives/${id}/diff`, { params: { a, b } })
  },
  patch(id, patchOps, baseVersion, changeSummary) {
    const params = {}
    if (baseVersion != null) params.base_version = baseVersion
    if (changeSummary) params.change_summary = changeSummary
    return request.patch(`/api/opening-archives/${id}`, patchOps, { params })
  },
  revert(id, toVersion) {
    return request.post(`/api/opening-archives/${id}/revert`, null, { params: { to_version: toVersion } })
  },
  uploadPhoto(id, { category_id, item_id, file }) {
    const fd = new FormData()
    fd.append('category_id', category_id)
    fd.append('item_id', item_id)
    fd.append('file', file)
    return request.post(`/api/opening-archives/${id}/photos`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  uploadTempPhoto(id, { category_id, item_id, file }) {
    const fd = new FormData()
    fd.append('category_id', category_id)
    fd.append('item_id', item_id)
    fd.append('file', file)
    return request.post(`/api/opening-archives/${id}/photos/temp`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deletePhoto(id, photoId) {
    return request.delete(`/api/opening-archives/${id}/photos/${photoId}`)
  },
  reindex(id, version) {
    return request.post(`/api/opening-archives/${id}/reindex`, null, { params: { version } })
  },
  search(params) {
    return request.get('/api/opening-archives/search', { params })
  },
  exportZip(id) {
    return request.get(`/api/opening-archives/${id}/export`, {
      responseType: 'blob',
      timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
    })
  },
  exportPdf(id) {
    return request.get(`/api/opening-archives/${id}/export-pdf`, {
      responseType: 'blob',
      timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
    })
  },
}
