import request from '@/utils/request'

export default {
  listSourceFields: () => request.get('/api/site-groups/source-fields'),
  listCategories: (params = {}) => request.get('/api/site-groups/categories', { params }),
  createCategory: (payload) => request.post('/api/site-groups/categories', payload),
  updateCategory: (categoryId, payload) => request.put(`/api/site-groups/categories/${categoryId}`, payload),
  createOption: (categoryId, payload) => request.post(`/api/site-groups/categories/${categoryId}/options`, payload),
  updateOption: (optionId, payload) => request.put(`/api/site-groups/options/${optionId}`, payload),
  deriveCategory: (categoryId, payload) => request.post(`/api/site-groups/categories/${categoryId}/derive`, payload),
  seedDeliveryScopeFromLld: (payload) => request.post('/api/site-groups/delivery-scope/seed-from-lld-duplex', payload),
  updateSiteAssignment: (siteId, payload) => request.put(`/api/site-groups/sites/${siteId}/assignments`, payload),
  batchUpdateAssignments: (payload) => request.post('/api/site-groups/assignments/batch', payload),
}
