import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useSiteStore = defineStore('site', () => {
	const sites = ref([])
	const currentSite = ref(null)
	const loading = ref(false)
	
	const userStore = useUserStore()
	const DEFAULT_PAGE_SIZE = 100
	const MAX_AUTO_PAGES = 500

	const normalizeInteger = (value) => {
		if (value === undefined || value === null || value === '') return null
		const parsed = Number(value)
		if (!Number.isFinite(parsed)) return null
		return Math.floor(parsed)
	}

	const buildSiteListQueryParams = (filters = {}) => {
		const params = []

		if (filters.status) params.push(`status=${encodeURIComponent(filters.status)}`)
		if (filters.site_type) params.push(`site_type=${encodeURIComponent(filters.site_type)}`)
		if (filters.assigned_to) params.push(`assigned_to=${encodeURIComponent(filters.assigned_to)}`)

		const skip = normalizeInteger(filters.skip)
		if (skip !== null && skip >= 0) {
			params.push(`skip=${skip}`)
		}

		const rawLimit = filters.limit ?? filters.page_size
		const limit = normalizeInteger(rawLimit)
		if (limit !== null && limit > 0) {
			params.push(`limit=${limit}`)
		}

		return params
	}

	const requestSitesPage = async (filters = {}) => {
		let url = buildApiUrl(API_ENDPOINTS.SITES.LIST)
		const params = buildSiteListQueryParams(filters)
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
			return Array.isArray(response.data) ? response.data : []
		}
		if (response.statusCode === 401) {
			throw new Error('__TOKEN_EXPIRED__')
		}
		throw new Error(response.data?.detail || '获取站点列表失败')
	}
	
	// 获取站点列表
	const getSites = async (filters = {}) => {
		if (!userStore.token) return { success: false, error: '未登录' }
		
		loading.value = true
		try {
			const hasExplicitPagination =
				Object.prototype.hasOwnProperty.call(filters, 'skip') ||
				Object.prototype.hasOwnProperty.call(filters, 'limit') ||
				Object.prototype.hasOwnProperty.call(filters, 'page_size')

			// 传了分页参数：按调用方要求请求单页（例如检查页站点选择器）
			if (hasExplicitPagination) {
				const pageData = await requestSitesPage(filters)
				sites.value = pageData
				return { success: true, data: pageData }
			}

			// 未传分页参数：自动翻页拉全量，避免被后端默认 limit=100 截断
			const { skip: _skip, limit: _limit, page_size: _pageSize, ...baseFilters } = filters || {}
			const pageSize = DEFAULT_PAGE_SIZE
			const aggregated = []
			const seenIds = new Set()
			let currentSkip = 0

			for (let pageIndex = 0; pageIndex < MAX_AUTO_PAGES; pageIndex += 1) {
				const pageData = await requestSitesPage({
					...baseFilters,
					skip: currentSkip,
					limit: pageSize
				})

				if (!pageData.length) break

				for (const site of pageData) {
					const siteId = site?.id
					if (siteId === undefined || siteId === null || !seenIds.has(siteId)) {
						if (siteId !== undefined && siteId !== null) seenIds.add(siteId)
						aggregated.push(site)
					}
				}

				if (pageData.length < pageSize) break
				currentSkip += pageData.length
			}

			if (aggregated.length > 0 || currentSkip === 0) {
				sites.value = aggregated
				return { success: true, data: aggregated }
			}

			sites.value = []
			return { success: true, data: [] }
		} catch (error) {
			console.error('Get sites error:', error)
			// 如果是401错误，可能token已过期
			if (error.message === '__TOKEN_EXPIRED__' || (error.message && error.message.includes('Could not validate credentials'))) {
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
