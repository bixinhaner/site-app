import request from '@/utils/request'

export const ssvArchivesApi = {
  page(params) {
    return request.get('/api/ssv-archives/page', { params })
  },
  get(id) {
    return request.get(`/api/ssv-archives/${id}`)
  },
  history(id) {
    return request.get(`/api/ssv-archives/${id}/history`)
  },
  diff(id, a, b) {
    return request.get(`/api/ssv-archives/${id}/diff`, { params: { a, b } })
  },
  patch(id, patchOps, params = {}) {
    return request.patch(`/api/ssv-archives/${id}`, patchOps, { params })
  },
  revert(id, toVersion) {
    return request.post(`/api/ssv-archives/${id}/revert`, null, { params: { to_version: toVersion } })
  },
  uploadPhoto(id, { categoryId, itemId, file }) {
    const fd = new FormData()
    fd.append('category_id', categoryId)
    fd.append('item_id', itemId)
    fd.append('file', file)
    return request.post(`/api/ssv-archives/${id}/photos`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  uploadTempPhoto(id, { categoryId, itemId, file }) {
    const fd = new FormData()
    fd.append('category_id', categoryId)
    fd.append('item_id', itemId)
    fd.append('file', file)
    return request.post(`/api/ssv-archives/${id}/photos/temp`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deletePhoto(id, photoId) {
    return request.delete(`/api/ssv-archives/${id}/photos/${photoId}`)
  },
  reindex(id, version) {
    return request.post(`/api/ssv-archives/${id}/reindex`, null, { params: { version } })
  },
  search(params) {
    return request.get('/api/ssv-archives/search', { params })
  },
  exportZip(id) {
    return request.get(`/api/ssv-archives/${id}/export`, { responseType: 'blob' })
  },
  exportPdf(id) {
    return request.get(`/api/ssv-archives/${id}/export-pdf`, { responseType: 'blob' })
  }
}

export default ssvArchivesApi
