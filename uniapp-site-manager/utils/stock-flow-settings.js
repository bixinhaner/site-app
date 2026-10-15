import { buildApiUrl, API_ENDPOINTS, getAuthHeaders } from '@/config/api.js'

// 读取库存流程设置中的“目标站点必填”开关；失败时按选填处理（后端仍会校验）
export const loadSiteRequiredSettings = async (token) => {
	const result = { material_request_requires_site: false, quick_stock_out_requires_site: false }
	try {
		const res = await uni.request({
			url: buildApiUrl(API_ENDPOINTS.STOCK.FLOW_SETTINGS),
			method: 'GET',
			header: getAuthHeaders(token),
		})
		const s = res.statusCode === 200 ? res.data?.settings || {} : {}
		result.material_request_requires_site = s.material_request_requires_site === true
		result.quick_stock_out_requires_site = s.quick_stock_out_requires_site === true
	} catch (e) {
		console.error('加载库存流程设置失败:', e)
	}
	return result
}
