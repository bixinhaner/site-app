import axios from 'axios'
import config from '@/config/env.js'

// 创建axios实例
const apiClient = axios.create({
  baseURL: config.API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const equipmentApi = {
  // 获取设备列表
  getEquipmentList: (params = {}) => 
    apiClient.get('/api/equipment/', { params }),
  
  // 创建设备型号
  createEquipment: (data) => 
    apiClient.post('/api/equipment/', data),
  
  // 更新设备型号
  updateEquipment: (id, data) => 
    apiClient.put(`/api/equipment/${id}`, data),
  
  // 删除设备型号
  deleteEquipment: (id) => 
    apiClient.delete(`/api/equipment/${id}`),
  
  // 获取套装列表
  getPackageList: (params = {}) => 
    apiClient.get('/api/equipment/packages', { params }),
  
  // 创建设备套装
  createPackage: (data) => 
    apiClient.post('/api/equipment/packages', data),
  
  // 获取套装详情
  getPackageDetail: (id) => 
    apiClient.get(`/api/equipment/packages/${id}`),
  
  // 更新设备套装
  updatePackage: (id, data) => 
    apiClient.put(`/api/equipment/packages/${id}`, data),
  
  // 删除设备套装
  deletePackage: (id) => 
    apiClient.delete(`/api/equipment/packages/${id}`),
  
  // 通过条码获取设备信息
  getEquipmentByBarcode: (barcode) => 
    apiClient.get(`/api/equipment/${barcode}/barcode-info`)
}