import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useWorkOrderStore = defineStore('workorder', () => {
  const list = ref([])
  const current = ref(null)
  const items = ref([])
  const photos = ref([])
  const loading = ref(false)
  const focusedWorkOrderId = ref(null)

  const userStore = useUserStore()

  const getMyWorkOrders = async (status, keyword) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    loading.value = true
    try {
      // 如果有搜索关键词，使用搜索端点
      if (keyword && keyword.trim()) {
        const queryParams = []
        queryParams.push(`keyword=${encodeURIComponent(keyword.trim())}`)
        if (userStore.userInfo?.id) {
          queryParams.push(`assigned_to=${userStore.userInfo.id}`)
        }
        if (status) {
          queryParams.push(`status=${status}`)
        }

        // 使用搜索端点
        let url = buildApiUrl(`${API_ENDPOINTS.WORK_ORDERS.LIST}/search`)
        if (queryParams.length > 0) {
          url += '?' + queryParams.join('&')
        }

        const response = await uni.request({
          url,
          ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
        })
        if (response.statusCode === 200) {
          list.value = response.data.work_orders || []
          return { success: true, data: response.data.work_orders || [] }
        }
        throw new Error(response.data?.detail || '搜索工单失败')
      } else {
        // 没有搜索关键词，使用普通列表端点
        const queryParams = []
        if (userStore.userInfo?.id) {
          queryParams.push(`assigned_to=${userStore.userInfo.id}`)
        }
        if (status) {
          queryParams.push(`status_filter=${status}`)
        }
        if (userStore.userInfo?.role === 'surveyor') {
          queryParams.push('type_filter=site_survey')
        }

        // 构建完整URL
        let url = buildApiUrl(API_ENDPOINTS.WORK_ORDERS.LIST)
        if (queryParams.length > 0) {
          url += '?' + queryParams.join('&')
        }

        const response = await uni.request({
          url,
          ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
        })
        if (response.statusCode === 200) {
          list.value = response.data
          return { success: true, data: response.data }
        }
        throw new Error(response.data?.detail || '获取工单失败')
      }
    } catch (e) {
      console.error('getMyWorkOrders error:', e)
      return { success: false, error: e.message || '网络错误' }
    } finally {
      loading.value = false
    }
  }

  const getWorkOrder = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.DETAIL(id)),
        ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
      })
      if (response.statusCode === 200) {
        current.value = response.data
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '获取工单详情失败')
    } catch (e) {
      console.error('getWorkOrder error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const getItems = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.ITEMS(id)),
        ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
      })
      if (response.statusCode === 200) {
        items.value = response.data
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '获取检查项失败')
    } catch (e) {
      console.error('getItems error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const getPhotos = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.PHOTOS(id)),
        ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
      })
      if (response.statusCode === 200) {
        photos.value = response.data
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '获取照片失败')
    } catch (e) {
      console.error('getPhotos error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const acceptWorkOrder = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.ACCEPT(id)),
        ...createRequestConfig({ method: 'POST', headers: getAuthHeaders(userStore.token) })
      })
      if ([200, 201].includes(response.statusCode)) {
        current.value = response.data.work_order
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '接受工单失败')
    } catch (e) {
      console.error('acceptWorkOrder error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const getInspection = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.INSPECTION(id)),
        ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
      })
      if (response.statusCode === 200) {
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '获取关联检查失败')
    } catch (e) {
      console.error('getInspection error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const completeWorkOrder = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.COMPLETE(id)),
        ...createRequestConfig({ method: 'POST', headers: getAuthHeaders(userStore.token) })
      })
      if ([200, 201].includes(response.statusCode)) {
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '完成工单失败')
    } catch (e) {
      console.error('completeWorkOrder error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const recallWorkOrder = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.RECALL(id)),
        ...createRequestConfig({ method: 'POST', headers: getAuthHeaders(userStore.token) })
      })
      if ([200].includes(response.statusCode)) {
        // 更新当前工单状态
        if (current.value && current.value.id === id) {
          current.value = response.data.work_order || current.value
        }
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '撤回失败')
    } catch (e) {
      console.error('recallWorkOrder error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const uploadPhoto = async (id, filePath, additional = {}) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.uploadFile({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.PHOTOS(id)),
        filePath,
        name: 'file',
        formData: additional,
        header: getAuthHeaders(userStore.token)
      })
      if ([200, 201].includes(response.statusCode)) {
        const data = JSON.parse(response.data)
        return { success: true, data }
      }
      throw new Error('上传失败')
    } catch (e) {
      console.error('uploadPhoto error:', e)
      return { success: false, error: e.message || '上传失败' }
    }
  }

  const updateItem = async (id, itemId, payload) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.ITEM_UPDATE(id, itemId)),
        ...createRequestConfig({ method: 'PUT', data: payload, headers: getAuthHeaders(userStore.token) })
      })
      if ([200, 201].includes(response.statusCode)) {
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '更新检查项失败')
    } catch (e) {
      console.error('updateItem error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const getItemFieldSchema = async (id) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(`${API_ENDPOINTS.WORK_ORDERS.DETAIL(id)}/items/field-schema`),
        ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
      })
      if (response.statusCode === 200) {
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '获取字段定义失败')
    } catch (e) {
      console.error('getItemFieldSchema error:', e)
      return { success: false, error: e.message || '网络错误' }
    }
  }

  const deletePhoto = async (photoId) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    try {
      const response = await uni.request({
        url: buildApiUrl(API_ENDPOINTS.WORK_ORDERS.DELETE_PHOTO(photoId)),
        ...createRequestConfig({ method: 'DELETE', headers: getAuthHeaders(userStore.token) })
      })
      if (response.statusCode === 200) {
        return { success: true, data: response.data }
      }
      throw new Error(response.data?.detail || '删除照片失败')
    } catch (e) {
      console.error('deletePhoto error:', e)
      return { success: false, error: e.message || '删除失败' }
    }
  }

  return { 
    list, current, items, photos, loading,
    focusedWorkOrderId,
    setFocusedWorkOrder(id) {
      focusedWorkOrderId.value = id || null
    },
    clearFocusedWorkOrder() {
      focusedWorkOrderId.value = null
    },
    getMyWorkOrders, getWorkOrder, getItems, getPhotos, 
    acceptWorkOrder, getInspection, completeWorkOrder,
    uploadPhoto, deletePhoto, updateItem, getItemFieldSchema,
    recallWorkOrder
  }
})
