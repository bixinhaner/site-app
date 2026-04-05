import request from '@/utils/request'
import config from '@/config/env.js'

// 工单API
export const workOrderAPI = {
  // 搜索工单（带分页和筛选）
  searchWorkOrders: (params = {}) => {
    const searchParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        searchParams.append(key, params[key])
      }
    })
    
    return request.get(`/api/work-orders/search?${searchParams.toString()}`)
  },

  // 获取工单列表
  getWorkOrders: (params = {}) => {
    return request.get('/api/work-orders', { params })
  },

  // 创建工单
  createWorkOrder: (workOrderData) => {
    return request.post('/api/work-orders', workOrderData)
  },

  // 获取工单详情
  getWorkOrder: (workOrderId) => {
    return request.get(`/api/work-orders/${workOrderId}`)
  },

  // 获取 Web 工单执行上下文
  getExecutionContext: (workOrderId) => {
    return request.get(`/api/work-orders/${workOrderId}/execution-context`)
  },

  // 获取工单关联检查
  getWorkOrderInspection: (workOrderId) => {
    return request.get(`/api/work-orders/${workOrderId}/inspection`)
  },

  // 更新工单信息
  updateWorkOrder: (workOrderId, workOrderData) => {
    return request.put(`/api/work-orders/${workOrderId}`, workOrderData)
  },

  // 删除工单
  deleteWorkOrder: (workOrderId) => {
    return request.delete(`/api/work-orders/${workOrderId}`)
  },

  // 作废工单
  voidWorkOrder: (workOrderId, reason) => {
    return request.post(`/api/work-orders/${workOrderId}/void`, { reason })
  },

  // 接受工单
  acceptWorkOrder: (workOrderId) => {
    return request.post(`/api/work-orders/${workOrderId}/accept`)
  },

  // 提交工单
  submitWorkOrder: (workOrderId) => {
    return request.post(`/api/work-orders/${workOrderId}/submit`)
  },

  // 撤回工单
  recallWorkOrder: (workOrderId) => {
    return request.post(`/api/work-orders/${workOrderId}/recall`)
  },

  // 完成工单
  completeWorkOrder: (workOrderId) => {
    return request.post(`/api/work-orders/${workOrderId}/complete`)
  },

  // 审核工单
  reviewWorkOrder: (workOrderId, reviewData) => {
    return request.post(`/api/work-orders/${workOrderId}/review`, reviewData)
  },

  // 批量操作工单
  batchOperation: (workOrderIds, operation, value = null, reason = null) => {
    return request.post('/api/work-orders/batch-operation', {
      work_order_ids: workOrderIds,
      operation: operation,
      value: value,
      reason: reason
    })
  },

  // 获取工单统计信息
  getWorkOrderStats: () => {
    return request.get('/api/work-orders/stats/summary')
  },

  getWorkOrderProgress: (workOrderId) => {
    return request.get(`/api/work-orders/${workOrderId}/progress`)
  },
}

export const inspectionExecutionApi = {
  getInspectionDetail: (inspectionId) => request.get(`/api/inspections/detail/${inspectionId}`),

  getInspectionItems: (inspectionId, params = {}) => request.get(`/api/inspections/detail/${inspectionId}/items`, { params }),

  getInspectionPhotoDetail: (photoId) =>
    request.get(`/api/inspections/photos/${photoId}/detail`),

  getCheckItemFieldReviewHistory: (inspectionId, itemId, params = {}) =>
    request.get(`/api/inspections/detail/${inspectionId}/items/${itemId}/field-reviews/history`, { params }),

  updateInspectionItem: (inspectionId, itemId, data) =>
    request.put(`/api/inspections/detail/${inspectionId}/items/${itemId}`, data),

  precheckPhotoUpload: (inspectionId, data) =>
    request.post(`/api/inspections/detail/${inspectionId}/photos/precheck`, data),

  uploadPhoto: (inspectionId, formData) =>
    request.post(`/api/inspections/detail/${inspectionId}/photos`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: config.LONG_REQUEST_TIMEOUT,
    }),

  deletePhoto: (photoId) => request.delete(`/api/inspections/photos/${photoId}`),

  replacePhoto: (photoId, formData) =>
    request.put(`/api/inspections/photos/${photoId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: config.LONG_REQUEST_TIMEOUT,
    }),

  bindEquipment: (inspectionId, data) =>
    request.post(`/api/inspections/detail/${inspectionId}/bind-equipment`, data),

  checkEquipmentPickup: (sn) =>
    request.get(`/api/inspections/equipment/check-pickup/${encodeURIComponent(sn)}`),
}

export const WorkOrderType = {
  OPENING_INSPECTION: 'opening_inspection',
  SSV: 'ssv',
  MAINTENANCE: 'maintenance',
  EQUIPMENT_REPLACEMENT: 'equipment_replacement',
  POWER_ISSUE: 'power_issue',
  TRANSMISSION_ISSUE: 'transmission_issue',
  GPS_ISSUE: 'gps_issue',
  SIGNAL_ISSUE: 'signal_issue',
  SITE_SURVEY: 'site_survey'
}

export default workOrderAPI
