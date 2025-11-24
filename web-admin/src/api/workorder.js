import request from '@/utils/request'

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

  // 更新工单信息
  updateWorkOrder: (workOrderId, workOrderData) => {
    return request.put(`/api/work-orders/${workOrderId}`, workOrderData)
  },

  // 删除工单
  deleteWorkOrder: (workOrderId) => {
    return request.delete(`/api/work-orders/${workOrderId}`)
  },

  // 接受工单
  acceptWorkOrder: (workOrderId) => {
    return request.post(`/api/work-orders/${workOrderId}/accept`)
  },

  // 提交工单
  submitWorkOrder: (workOrderId) => {
    return request.post(`/api/work-orders/${workOrderId}/submit`)
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
  batchOperation: (workOrderIds, operation, value = null) => {
    return request.post('/api/work-orders/batch-operation', {
      work_order_ids: workOrderIds,
      operation: operation,
      value: value
    })
  },

  // 获取工单统计信息
  getWorkOrderStats: () => {
    return request.get('/api/work-orders/stats/summary')
  }
}

export const WorkOrderType = {
  OPENING_INSPECTION: 'opening_inspection',
  SSV: 'ssv',
  MAINTENANCE: 'maintenance',
  POWER_ISSUE: 'power_issue',
  TRANSMISSION_ISSUE: 'transmission_issue',
  GPS_ISSUE: 'gps_issue',
  SIGNAL_ISSUE: 'signal_issue',
  SITE_SURVEY: 'site_survey'
}

export default workOrderAPI
