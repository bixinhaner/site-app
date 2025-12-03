import request from '@/utils/request'
import config from '@/config/env.js'

export const siteSurveysApi = {
  // surveys
  list: (params) => request.get('/api/site-surveys/', { params }),
  page: (params) => request.get('/api/site-surveys/page', { params }),
  get: (id) => request.get(`/api/site-surveys/${id}`),
  create: (data) => request.post('/api/site-surveys/', data),
  update: (id, data) => request.put(`/api/site-surveys/${id}`, data),
  remove: (id) => request.delete(`/api/site-surveys/${id}`),
  exportZip: (id) => request.get(`/api/site-surveys/${id}/export`, {
    responseType: 'blob',
    timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
  }),
  exportBatch: (params) => request.get('/api/site-surveys/export-batch', {
    params,
    responseType: 'blob',
    timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
  }),
  exportPdf: (id) => request.get(`/api/site-surveys/${id}/export-pdf`, {
    responseType: 'blob',
    timeout: config.LONG_REQUEST_TIMEOUT || config.TIMEOUT,
  }),
  getAuditLogs: (id, params) => request.get(`/api/site-surveys/${id}/audit-logs`, { params }),

  // photos
  uploadPhoto: (surveyId, formData) => request.post(`/api/site-surveys/${surveyId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  uploadPhotosBatch: (surveyId, formData) => request.post(`/api/site-surveys/${surveyId}/photos/batch`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  listPhotos: (surveyId) => request.get(`/api/site-surveys/${surveyId}/photos`),
  deletePhoto: (photoId) => request.delete(`/api/site-surveys/photos/${photoId}`),
  deletePhotosBatch: (surveyId, data) => request.delete(`/api/site-surveys/${surveyId}/photos`, { data }),
  updatePhoto: (photoId, formData) => request.put(`/api/site-surveys/photos/${photoId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  // 排序与EXIF功能已移除

  // import/export helpers
  downloadImportTemplate: () => request.get('/api/site-surveys/import-template', { responseType: 'blob' }),
  importExcel: (formData) => request.post('/api/site-surveys/import-excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
