import request from '@/utils/request'

export const equipmentApi = {
  // 获取设备列表
  getEquipmentList: (params = {}) => 
    request.get('/api/equipment/', { params }),
  
  // 创建设备型号
  createEquipment: (data) => 
    request.post('/api/equipment/', data),
  
  // 更新设备型号
  updateEquipment: (id, data) => 
    request.put(`/api/equipment/${id}`, data),
  
  // 删除设备型号
  deleteEquipment: (id) => 
    request.delete(`/api/equipment/${id}`),
  
  // 获取套装列表
  getPackageList: (params = {}) => 
    request.get('/api/equipment/packages', { params }),
  
  // 创建设备套装
  createPackage: (data) => 
    request.post('/api/equipment/packages', data),
  
  // 获取套装详情
  getPackageDetail: (id) => 
    request.get(`/api/equipment/packages/${id}`),
  
  // 更新设备套装
  updatePackage: (id, data) => 
    request.put(`/api/equipment/packages/${id}`, data),
  
  // 删除设备套装
  deletePackage: (id) => 
    request.delete(`/api/equipment/packages/${id}`),
  
  // 通过条码获取设备信息
  getEquipmentByBarcode: (barcode) => 
    request.get(`/api/equipment/${barcode}/barcode-info`)
}