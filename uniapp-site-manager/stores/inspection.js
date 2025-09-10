import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useInspectionStore = defineStore('inspection', () => {
	const inspections = ref([])
	const currentInspection = ref(null)
	const loading = ref(false)
	
	const userStore = useUserStore()
	
	// 获取检查列表
	const getInspections = async (filters = {}) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		loading.value = true
		try {
			let url = buildApiUrl(API_ENDPOINTS.INSPECTIONS.LIST)
			const params = []
			
			if (filters.site_id) params.push(`site_id=${encodeURIComponent(filters.site_id)}`)
			if (filters.status) params.push(`status=${encodeURIComponent(filters.status)}`)
			
			if (params.length > 0) {
				url += '?' + params.join('&')
			}
			
			const response = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				inspections.value = response.data
				return { success: true, data: response.data }
			} else if (response.statusCode === 401) {
				// 直接处理401错误
				const userStore = useUserStore()
				userStore.logout()
				return { success: false, error: 'Token已过期，请重新登录' }
			} else {
				throw new Error(response.data.detail || '获取检查列表失败')
			}
		} catch (error) {
			console.error('Get inspections error:', error)
			// 如果是401错误，可能token已过期
			if (error.message && error.message.includes('Could not validate credentials')) {
				// 清除用户登录状态
				const userStore = useUserStore()
				userStore.logout()
				return { success: false, error: 'Token已过期，请重新登录' }
			}
			return { success: false, error: error.message || '网络错误' }
		} finally {
			loading.value = false
		}
	}
	
	// 获取检查详情
	const getInspection = async (inspectionId) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.DETAIL(inspectionId)),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				currentInspection.value = response.data
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '获取检查详情失败')
			}
		} catch (error) {
			console.error('Get inspection error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 创建检查
	const createInspection = async (inspectionData) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.CREATE),
				...createRequestConfig({
					method: 'POST',
					data: inspectionData,
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200 || response.statusCode === 201) {
				currentInspection.value = response.data
				await getInspections()
				return { success: true, data: response.data }
			} else {
				console.error('Create inspection failed:', response)
				throw new Error(response.data?.detail || response.data?.message || '创建检查失败')
			}
		} catch (error) {
			console.error('Create inspection error:', error)
			// 尝试解析错误信息
			let errorMessage = '网络错误'
			if (error.message && error.message !== '[object Object]') {
				errorMessage = error.message
			} else if (error.data && typeof error.data === 'string') {
				errorMessage = error.data
			} else if (error.response && error.response.data) {
				errorMessage = error.response.data.detail || error.response.data.message || '创建失败'
			}
			return { success: false, error: errorMessage }
		}
	}
	
	// 更新检查
	const updateInspection = async (inspectionId, updateData) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.UPDATE(inspectionId)),
				...createRequestConfig({
					method: 'PUT',
					data: updateData,
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				if (currentInspection.value && currentInspection.value.id === inspectionId) {
					currentInspection.value = response.data
				}
				await getInspections()
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '更新检查失败')
			}
		} catch (error) {
			console.error('Update inspection error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 上传检查照片
	const uploadPhoto = async (inspectionId, filePath, additionalData = {}) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const formData = {
				...additionalData
			}
			
			const response = await uni.uploadFile({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.PHOTOS(inspectionId)),
				filePath,
				name: 'file',
				formData,
				header: getAuthHeaders(userStore.token)
			})
			
			if (response.statusCode === 200) {
				const data = JSON.parse(response.data)
				return { success: true, data }
			} else {
				throw new Error('上传照片失败')
			}
		} catch (error) {
			console.error('Upload photo error:', error)
			return { success: false, error: error.message || '上传失败' }
		}
	}
	
	// 删除检查
	const deleteInspection = async (inspectionId) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.DELETE(inspectionId)),
				...createRequestConfig({
					method: 'DELETE',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				// 从列表中移除已删除的检查
				inspections.value = inspections.value.filter(inspection => inspection.id !== inspectionId)
				return { success: true }
			} else {
				throw new Error(response.data.detail || '删除检查失败')
			}
		} catch (error) {
			console.error('Delete inspection error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 获取检查统计信息
	const getStatistics = async () => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl('/api/inspections/statistics/overview'),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				return { success: true, data: response.data }
			} else if (response.statusCode === 401) {
				// 直接处理401错误
				const userStore = useUserStore()
				userStore.logout()
				return { success: false, error: 'Token已过期，请重新登录' }
			} else {
				throw new Error(response.data.detail || '获取统计信息失败')
			}
		} catch (error) {
			console.error('Get statistics error:', error)
			// 如果是401错误，可能token已过期
			if (error.message && error.message.includes('Could not validate credentials')) {
				// 清除用户登录状态
				const userStore = useUserStore()
				userStore.logout()
				return { success: false, error: 'Token已过期，请重新登录' }
			}
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 获取检查模板
	const getTemplates = async (siteId) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			let url = buildApiUrl('/api/inspections/templates')
			if (siteId) {
				url += `?site_id=${encodeURIComponent(siteId)}`
			}
			
			const response = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '获取检查模板失败')
			}
		} catch (error) {
			console.error('Get templates error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 获取检查详情 (别名方法，兼容页面调用)
	const getInspectionDetail = async (inspectionId) => {
		return await getInspection(inspectionId)
	}
	
	// 获取检查项列表
	const getInspectionItems = async (inspectionId) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(`/api/inspections/detail/${inspectionId}/items`),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '获取检查项失败')
			}
		} catch (error) {
			console.error('Get inspection items error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 更新检查项
	const updateInspectionItem = async (inspectionId, itemId, updateData) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(`/api/inspections/detail/${inspectionId}/items/${itemId}`),
				...createRequestConfig({
					method: 'PUT',
					data: updateData,
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '更新检查项失败')
			}
		} catch (error) {
			console.error('Update inspection item error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}

	return {
		inspections,
		currentInspection,
		loading,
		getInspections,
		getInspection,
		getInspectionDetail,
		getInspectionItems,
		updateInspectionItem,
		createInspection,
		updateInspection,
		deleteInspection,
		uploadPhoto,
		getStatistics,
		getTemplates
	}
})