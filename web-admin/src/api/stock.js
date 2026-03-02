import request from '@/utils/request'

export const stockApi = {
  // 获取库存列表
  getInventoryList: (params = {}) => 
    request.get('/api/stock/inventory', { params }),
  
  // 获取库存看板数据
  getInventoryDashboard: () => 
    request.get('/api/stock/inventory/dashboard'),
  
  // 创建入库单
  createStockIn: (data) => 
    request.post('/api/stock/stock-in', data),

  // ===== 线下单据（可复用）=====
  createOfflineDocument: (data) =>
    request.post('/api/stock/offline-documents', data),

  getOfflineDocument: (documentId) =>
    request.get(`/api/stock/offline-documents/${documentId}`),

  uploadOfflineDocumentPhoto: (documentId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request.post(`/api/stock/offline-documents/${documentId}/photos`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteOfflineDocumentPhoto: (documentId, photoId) =>
    request.delete(`/api/stock/offline-documents/${documentId}/photos/${photoId}`),
  
  // 扫码出库
  scanCheckout: (data) => 
    request.post('/api/stock/scan-checkout', data),
  
  // 确认领料
  confirmPickup: (data) => 
    request.post('/api/stock/confirm-pickup', data),
  
  // 获取我的领料记录
  getMyPickups: (params = {}) => 
    request.get('/api/stock/my-pickups', { params }),
  
  // 获取出入库记录
  getStockTransactions: (params = {}) => 
    request.get('/api/stock/transactions', { params }),
  
  // 获取仓库列表
  getWarehouses: () => 
    request.get('/api/stock/warehouses'),
  
  // 创建仓库
  createWarehouse: (data) => 
    request.post('/api/stock/warehouses', data),

  // 更新仓库
  updateWarehouse: (id, data) =>
    request.put(`/api/stock/warehouses/${id}`, data),

  // SN批量导入相关
  importSN: (data) => 
    request.post('/api/stock/import-sn', data),
    
  downloadImportTemplate: () => 
    request.get('/api/stock/import-template', { responseType: 'blob' }),
    
  getImportHistory: (params = {}) => 
    request.get('/api/stock/import-history', { params }),
    
  getImportDetails: (importId) => 
    request.get(`/api/stock/import-history/${importId}/details`),
    
  validateSN: (serialNumber) => 
    request.get(`/api/stock/validate-sn/${serialNumber}`),
    
  // 获取设备实例列表
  getEquipmentInstances: (equipmentId, params = {}) => 
    request.get(`/api/stock/equipment/${equipmentId}/instances`, { params }),
    
  // 批量检查SN是否存在
  checkSNBatch: (snList) => 
    request.post('/api/stock/check-sn-batch', { sn_list: snList }),

  // ===== 库存更正/撤销/编辑 =====
  updateTransactionNotes: (transactionId, data) =>
    request.patch(`/api/stock/transactions/${transactionId}`, data),

  updateTransactionItem: (itemId, data) =>
    request.patch(`/api/stock/transaction-items/${itemId}`, data),

  adjustTransactionItem: (itemId, data) =>
    request.post(`/api/stock/transaction-items/${itemId}/adjust`, data),

  voidInstances: (data) =>
    request.post('/api/stock/instances/void', data),

  updateEquipmentInstance: (instanceId, data) =>
    request.patch(`/api/stock/instances/${instanceId}`, data),

  // ===== 退库（待收货/收货确认）=====
  returnPreview: (data) =>
    request.post('/api/stock/scan-return/preview', data),

  getReturnRequests: (params = {}) =>
    request.get('/api/stock/return-requests', { params }),

  receiveReturn: (data) =>
    request.post('/api/stock/scan-return/receive', data),

  rejectReturn: (data) =>
    request.post('/api/stock/scan-return/reject', data),

  // ===== 流程设置 =====
  getFlowSettings: () =>
    request.get('/api/stock/flow-settings'),

  updateFlowSettings: (data) =>
    request.put('/api/stock/flow-settings', data),

  // ===== 物料申请（新流程）=====
  createMaterialRequest: (data) =>
    request.post('/api/stock/material-requests', data),

  listMaterialRequests: (params = {}) =>
    request.get('/api/stock/material-requests', { params }),

  getMaterialRequestDetail: (id) =>
    request.get(`/api/stock/material-requests/${id}`),

  updateMaterialRequest: (id, data) =>
    request.put(`/api/stock/material-requests/${id}`, data),

  submitMaterialRequest: (id) =>
    request.post(`/api/stock/material-requests/${id}/submit`),

  cancelMaterialRequest: (id, data) =>
    request.post(`/api/stock/material-requests/${id}/cancel`, data),

  abandonMaterialRequest: (id, data) =>
    request.post(`/api/stock/material-requests/${id}/abandon`, data),

  approveMaterialRequest: (id, data) =>
    request.post(`/api/stock/material-requests/${id}/approve`, data),

  rejectMaterialRequest: (id, data) =>
    request.post(`/api/stock/material-requests/${id}/reject`, data),

  // ===== 领料单 / 待确认出库 =====
  listIssueDrafts: (params = {}) =>
    request.get('/api/stock/issue-drafts', { params }),

  getIssueDraftDetail: (id) =>
    request.get(`/api/stock/issue-drafts/${id}`),

  confirmIssueDraft: (id, data) =>
    request.post(`/api/stock/issue-drafts/${id}/confirm`, data),

  rejectIssueDraft: (id, data) =>
    request.post(`/api/stock/issue-drafts/${id}/reject`, data),

  rejectRemainingIssueDraft: (id, data) =>
    request.post(`/api/stock/issue-drafts/${id}/reject-remaining`, data),

  // ===== 快速出库（无申请）=====
  manualStockOut: (data) =>
    request.post('/api/stock/manual-stock-out', data),

  // ===== 退库（新方案：按出库单明细，可部分收货）=====
  createReturnByActual: (data) =>
    request.post('/api/stock/returns/by-actual', data),

  listReturnsWorkbench: (params = {}) =>
    request.get('/api/stock/returns', { params }),

  listReturnWorkbenchBatches: (params = {}) =>
    request.get('/api/stock/returns/workbench-batches', { params }),

  getReturnDetail: (id) =>
    request.get(`/api/stock/returns/${id}`),

  receiveReturnV2: (id, data) =>
    request.post(`/api/stock/returns/${id}/receive`, data),

  rejectReturnV2: (id, data) =>
    request.post(`/api/stock/returns/${id}/reject`, data),

  // ===== 人员归属（web-admin）=====
  getUserIssuedItems: (userId, params = {}) =>
    request.get(`/api/stock/users/${userId}/issued-items`, { params }),

  exportUserIssuedItems: (userId, params = {}) =>
    request.get(`/api/stock/users/${userId}/issued-items/export`, { params, responseType: 'blob' }),

  getStockOutDetail: (outTransactionId) =>
    request.get(`/api/stock/stock-outs/${outTransactionId}`),

  getUserOwnershipSummary: (params = {}) =>
    request.get('/api/stock/user-ownership/summary', { params }),

  exportUserOwnershipAll: (params = {}) =>
    request.get('/api/stock/user-ownership/export', { params, responseType: 'blob' }),
}
