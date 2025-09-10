import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useSiteStore = defineStore('site', () => {
	const sites = ref([])
	const currentSite = ref(null)
	const loading = ref(false)
	
	const userStore = useUserStore()
	
	// 获取站点列表
	const getSites = async (filters = {}) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		loading.value = true
		try {
			let url = buildApiUrl(API_ENDPOINTS.SITES.LIST)
			const params = []
			
			if (filters.status) params.push(`status=${encodeURIComponent(filters.status)}`)
			if (filters.site_type) params.push(`site_type=${encodeURIComponent(filters.site_type)}`)
			if (filters.assigned_to) params.push(`assigned_to=${encodeURIComponent(filters.assigned_to)}`)
			
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
				sites.value = response.data
				return { success: true, data: response.data }
			} else if (response.statusCode === 401) {
				// 直接处理401错误
				const userStore = useUserStore()
				userStore.logout()
				return { success: false, error: 'Token已过期，请重新登录' }
			} else {
				throw new Error(response.data.detail || '获取站点列表失败')
			}
		} catch (error) {
			console.error('Get sites error:', error)
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
	
	// 获取站点详情
	const getSite = async (siteId) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.SITES.DETAIL(siteId)),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				currentSite.value = response.data
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '获取站点详情失败')
			}
		} catch (error) {
			console.error('Get site error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 创建站点
	const createSite = async (siteData) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.SITES.CREATE),
				...createRequestConfig({
					method: 'POST',
					data: siteData,
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				// 重新获取站点列表
				await getSites()
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '创建站点失败')
			}
		} catch (error) {
			console.error('Create site error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	// 更新站点
	const updateSite = async (siteId, updateData) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.SITES.UPDATE(siteId)),
				...createRequestConfig({
					method: 'PUT',
					data: updateData,
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				// 更新当前站点信息
				if (currentSite.value && currentSite.value.id === siteId) {
					currentSite.value = response.data
				}
				// 重新获取站点列表
				await getSites()
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '更新站点失败')
			}
		} catch (error) {
			console.error('Update site error:', error)
			return { success: false, error: error.message || '网络错误' }
		}
	}
	
	return {
		sites,
		currentSite,
		loading,
		getSites,
		getSite,
		createSite,
		updateSite
	}
})