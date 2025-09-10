import apiClient from './auth'

export const stockApi = {
  // 获取库存列表
  getInventoryList: (params = {}) => 
    apiClient.get('/api/stock/inventory', { params }),
  
  // 获取库存看板数据
  getInventoryDashboard: () => 
    apiClient.get('/api/stock/inventory/dashboard'),
  
  // 创建入库单
  createStockIn: (data) => 
    apiClient.post('/api/stock/stock-in', data),
  
  // 扫码出库
  scanCheckout: (data) => 
    apiClient.post('/api/stock/scan-checkout', data),
  
  // 确认领料
  confirmPickup: (data) => 
    apiClient.post('/api/stock/confirm-pickup', data),
  
  // 获取我的领料记录
  getMyPickups: (params = {}) => 
    apiClient.get('/api/stock/my-pickups', { params }),
  
  // 获取出入库记录
  getStockTransactions: (params = {}) => 
    apiClient.get('/api/stock/transactions', { params }),
  
  // 获取仓库列表
  getWarehouses: () => 
    apiClient.get('/api/stock/warehouses'),
  
  // 创建仓库
  createWarehouse: (data) => 
    apiClient.post('/api/stock/warehouses', data),

  // SN批量导入相关
  importSN: (data) => 
    apiClient.post('/api/stock/import-sn', data),
    
  downloadImportTemplate: () => 
    apiClient.get('/api/stock/import-template', { responseType: 'blob' }),
    
  getImportHistory: (params = {}) => 
    apiClient.get('/api/stock/import-history', { params }),
    
  getImportDetails: (importId) => 
    apiClient.get(`/api/stock/import-history/${importId}/details`),
    
  validateSN: (serialNumber) => 
    apiClient.get(`/api/stock/validate-sn/${serialNumber}`),
    
  // 获取设备实例列表
  getEquipmentInstances: (equipmentId, params = {}) => 
    apiClient.get(`/api/stock/equipment/${equipmentId}/instances`, { params }),
    
  // 批量检查SN是否存在
  checkSNBatch: (snList) => 
    apiClient.post('/api/stock/check-sn-batch', { sn_list: snList })
}