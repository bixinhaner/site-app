/**
 * 检查模板管理 API
 */

import request from '@/utils/request'

const API_BASE = '/api/inspections'

// 模板管理
export const templateAPI = {
  // 获取模板列表
  async getTemplates(params = {}) {
    const { skip = 0, limit = 100, site_id, site_type, task_type, q } = params
    const searchParams = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    
    if (site_id) searchParams.append('site_id', site_id)
    if (site_type) searchParams.append('site_type', site_type)
    if (task_type) searchParams.append('task_type', task_type)
    if (q) searchParams.append('q', q)
    
    return request.get(`${API_BASE}/templates?${searchParams}`)
  },

  // 获取模板详情
  async getTemplate(templateId) {
    return request.get(`${API_BASE}/templates/${templateId}`)
  },

  // 创建模板
  async createTemplate(templateData) {
    return request.post(`${API_BASE}/templates`, templateData)
  },

  // 更新模板
  async updateTemplate(templateId, templateData) {
    return request.put(`${API_BASE}/templates/${templateId}`, templateData)
  },

  // 删除模板
  async deleteTemplate(templateId) {
    return request.delete(`${API_BASE}/templates/${templateId}`)
  },

  // 获取模板使用情况
  async getTemplateUsage(templateId) {
    return request.get(`${API_BASE}/templates/${templateId}/usage`)
  }
}

// 模板绑定管理
export const bindingAPI = {
  // 获取模板绑定列表
  async getTemplateBindings(templateId, params = {}) {
    const { skip = 0, limit = 100, active_only = false } = params
    const searchParams = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
      active_only: active_only.toString()
    })
    
    return request.get(`${API_BASE}/templates/${templateId}/bindings?${searchParams}`)
  },

  // 创建模板绑定
  async createBinding(templateId, bindingData) {
    return request.post(`${API_BASE}/templates/${templateId}/bindings`, bindingData)
  },

  // 更新模板绑定
  async updateBinding(templateId, bindingId, bindingData) {
    return request.put(`${API_BASE}/templates/${templateId}/bindings/${bindingId}`, bindingData)
  },

  // 删除模板绑定
  async deleteBinding(templateId, bindingId) {
    return request.delete(`${API_BASE}/templates/${templateId}/bindings/${bindingId}`)
  },

  // 批量更新绑定优先级
  async batchUpdatePriority(templateId, bindingUpdates) {
    return request.post(`${API_BASE}/templates/${templateId}/bindings/batch-update`, { binding_updates: bindingUpdates })
  }
}

// 模板解析
export const resolverAPI = {
  // 解析模板
  async resolveTemplate(context, showAll = false) {
    const params = new URLSearchParams({ show_all: showAll.toString() })
    
    return request.post(`${API_BASE}/templates/resolve?${params}`, context)
  }
}

// 枚举值和常量
export const TASK_TYPES = {
  OPENING_INSPECTION: 'opening_inspection',
  MAINTENANCE: 'maintenance',
  POWER_ISSUE: 'power_issue',
  TRANSMISSION_ISSUE: 'transmission_issue',
  GPS_ISSUE: 'gps_issue',
  SIGNAL_ISSUE: 'signal_issue'
}

export const TASK_TYPE_LABELS = {
  [TASK_TYPES.OPENING_INSPECTION]: '新站点设备安装',
  [TASK_TYPES.MAINTENANCE]: '维护检查',
  [TASK_TYPES.POWER_ISSUE]: '断电问题',
  [TASK_TYPES.TRANSMISSION_ISSUE]: '传输问题',
  [TASK_TYPES.GPS_ISSUE]: 'GPS问题',
  [TASK_TYPES.SIGNAL_ISSUE]: '信号问题'
}

export const SITE_TYPES = {
  MACRO: 'macro',
  MICRO: 'micro',
  INDOOR: 'indoor',
  OUTDOOR: 'outdoor'
}

export const SITE_TYPE_LABELS = {
  [SITE_TYPES.MACRO]: '宏站',
  [SITE_TYPES.MICRO]: '微站',
  [SITE_TYPES.INDOOR]: '室内站',
  [SITE_TYPES.OUTDOOR]: '室外站'
}

export const REQUIRED_TYPES = {
  PHOTO: 'photo',
  DATA: 'data',
  BOTH: 'both'
}

export const REQUIRED_TYPE_LABELS = {
  [REQUIRED_TYPES.PHOTO]: '仅拍照',
  [REQUIRED_TYPES.DATA]: '仅数据',
  [REQUIRED_TYPES.BOTH]: '拍照+数据'
}