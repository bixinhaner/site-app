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
    request.post('/api/stock/check-sn-batch', { sn_list: snList })
}
