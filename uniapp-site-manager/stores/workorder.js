import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useWorkOrderStore = defineStore('workorder', () => {
  const list = ref([])
  const current = ref(null)
  const items = ref([])
  const loading = ref(false)
  const focusedWorkOrderId = ref(null)

  const userStore = useUserStore()
  const DEFAULT_PAGE_SIZE = 100
  const MAX_AUTO_PAGES = 500

  const appendQueryParams = (baseUrl, queryParams = []) => {
    if (!queryParams.length) return baseUrl
    return `${baseUrl}?${queryParams.join('&')}`
  }

  const fetchPagedWorkOrders = async ({
    path,
    baseParams = [],
    pageSize = DEFAULT_PAGE_SIZE,
    parseItems,
    failureMessage
  }) => {
    const aggregated = []
    const seenIds = new Set()
    let skip = 0

    for (let pageIndex = 0; pageIndex < MAX_AUTO_PAGES; pageIndex += 1) {
      const queryParams = [...baseParams, `skip=${skip}`, `limit=${pageSize}`]
      const url = appendQueryParams(buildApiUrl(path), queryParams)
      const response = await uni.request({
        url,
        ...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
      })

      if (response.statusCode !== 200) {
        throw new Error(response.data?.detail || failureMessage)
      }

      const pageItems = parseItems(response.data)
      if (!pageItems.length) break

      for (const item of pageItems) {
        const itemId = item?.id
        if (itemId === undefined || itemId === null || !seenIds.has(itemId)) {
          if (itemId !== undefined && itemId !== null) seenIds.add(itemId)
          aggregated.push(item)
        }
      }

      if (pageItems.length < pageSize) break
      skip += pageItems.length
    }

    return aggregated
  }

  const getMyWorkOrders = async (status, keyword) => {
    if (!userStore.token) return { success: false, error: '未登录' }
    loading.value = true
    try {
      const workOrderScope = userStore.getDataScope('work_orders')
      const assigneeId = userStore.userInfo?.id

      // 如果有搜索关键词，使用搜索端点
      if (keyword && keyword.trim()) {
        const queryParams = [`keyword=${encodeURIComponent(keyword.trim())}`]
        if (assigneeId && ['assigned', 'assigned_survey_only'].includes(workOrderScope)) {
          queryParams.push(`assigned_to=${encodeURIComponent(assigneeId)}`)
        }
        if (workOrderScope === 'assigned_survey_only') {
          queryParams.push('type=site_survey')
        }
        if (status) {
          queryParams.push(`status=${encodeURIComponent(status)}`)
        }

        const data = await fetchPagedWorkOrders({
          path: `${API_ENDPOINTS.WORK_ORDERS.LIST}/search`,
          baseParams: queryParams,
          pageSize: DEFAULT_PAGE_SIZE,
          parseItems: (payload) => Array.isArray(payload?.work_orders) ? payload.work_orders : [],
          failureMessage: '搜索工单失败'
        })
        list.value = data
        return { success: true, data }
      } else {
        // 没有搜索关键词，使用普通列表端点
        const queryParams = []
        if (assigneeId && ['assigned', 'assigned_survey_only'].includes(workOrderScope)) {
          queryParams.push(`assigned_to=${encodeURIComponent(assigneeId)}`)
        }
        if (status) {
          queryParams.push(`status_filter=${encodeURIComponent(status)}`)
        }
        if (workOrderScope === 'assigned_survey_only') {
          queryParams.push('type_filter=site_survey')
        }

        const data = await fetchPagedWorkOrders({
          path: API_ENDPOINTS.WORK_ORDERS.LIST,
          baseParams: queryParams,
          pageSize: DEFAULT_PAGE_SIZE,
          parseItems: (payload) => Array.isArray(payload) ? payload : [],
          failureMessage: '获取工单失败'
        })
        list.value = data
        return { success: true, data }
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

  return { 
    list, current, items, loading,
    focusedWorkOrderId,
    setFocusedWorkOrder(id) {
      focusedWorkOrderId.value = id || null
    },
    clearFocusedWorkOrder() {
      focusedWorkOrderId.value = null
    },
    getMyWorkOrders, getWorkOrder, getItems, 
    acceptWorkOrder, getInspection, completeWorkOrder,
    updateItem, getItemFieldSchema,
    recallWorkOrder
  }
})
