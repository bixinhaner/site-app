import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig } from '@/config/api.js'
import { APP_FEATURE_RULES } from '@/config/app-permissions.js'
import {
	setLocationMode,
	setAllowLocalPhotoUpload,
	setLocalUploadWatermarkWithGeo,
	setEnablePhotoLocationDistanceCheck,
	setDistanceExceedBlockUpload,
	setPhotoLocationDistanceThresholdM,
	setPhotoWatermarkEffective,
} from '@/utils/locationStrategy.js'
import { flush, startMobileLogReporter, stopMobileLogReporter } from '@/utils/mobileLogReporter.js'

const normalizeRoleCodes = (rawRoles = [], rawRole = null) => {
	const roleSet = new Set()
	for (const item of rawRoles || []) {
		const code = String(item || '').trim()
		if (code) roleSet.add(code)
	}
	const primaryRole = String(rawRole || '').trim()
	if (primaryRole) roleSet.add(primaryRole)
	return Array.from(roleSet)
}

const normalizePermissionCodes = (rawPermissions = []) => {
	const permissionSet = new Set()
	for (const item of rawPermissions || []) {
		const code = String(item || '').trim()
		if (code) permissionSet.add(code)
	}
	return Array.from(permissionSet)
}

const normalizeDataScopes = (rawDataScopes = null) => {
	const scopeMap = {}
	if (!rawDataScopes || typeof rawDataScopes !== 'object') return scopeMap
	for (const [resource, scope] of Object.entries(rawDataScopes)) {
		const resourceCode = String(resource || '').trim()
		const scopeCode = String(scope || '').trim()
		if (!resourceCode || !scopeCode) continue
		scopeMap[resourceCode] = scopeCode
	}
	return scopeMap
}

const normalizeUserInfo = (rawUser) => {
	if (!rawUser || typeof rawUser !== 'object') return null
	const roles = normalizeRoleCodes(rawUser.roles, rawUser.role)
	const role = String(rawUser.role || roles[0] || '').trim() || null
	const permissions = normalizePermissionCodes(rawUser.permissions)
	const dataScopes = normalizeDataScopes(rawUser.data_scopes)
	return {
		...rawUser,
		role,
		roles,
		permissions,
		data_scopes: dataScopes,
	}
}

const permissionMatches = (targetPermission, grantedPermissions = []) => {
	const target = String(targetPermission || '').trim()
	if (!target) return false
	for (const raw of grantedPermissions || []) {
		const code = String(raw || '').trim()
		if (!code) continue
		if (code === '*' || code === target) return true
		if (code.endsWith(':*') && target.startsWith(code.slice(0, -1))) return true
	}
	return false
}

export const useUserStore = defineStore('user', () => {
	const token = ref(uni.getStorageSync('token') || '')
	const refreshToken = ref(uni.getStorageSync('refreshToken') || '')
	const userInfo = ref(normalizeUserInfo(uni.getStorageSync('userInfo')) || null)
	// 旧流程：我的设备-扫码领货开关（默认关闭；登录后从 /api/system/mobile-settings/effective 刷新）
	const legacyScanPickupEnabled = ref(false)
	const isLoggedIn = computed(() => !!token.value)
	const roles = computed(() => normalizeRoleCodes(userInfo.value?.roles, userInfo.value?.role))
	const permissions = computed(() => normalizePermissionCodes(userInfo.value?.permissions))
	const dataScopes = computed(() => normalizeDataScopes(userInfo.value?.data_scopes))
	const hasAnyAppPermission = computed(() => permissions.value.some(code => String(code || '').startsWith('app:')))

	const hasRole = (roleCode) => {
		const code = String(roleCode || '').trim()
		if (!code) return false
		return roles.value.includes(code)
	}

	const hasAnyRole = (roleCodes = []) => {
		return (roleCodes || []).some(code => hasRole(code))
	}

	const hasPermission = (permissionCode) => {
		return permissionMatches(permissionCode, permissions.value)
	}

	const hasAnyPermission = (permissionCodes = []) => {
		return (permissionCodes || []).some(code => hasPermission(code))
	}

	const hasAllPermissions = (permissionCodes = []) => {
		return (permissionCodes || []).every(code => hasPermission(code))
	}

	const getDataScope = (resourceCode) => {
		const key = String(resourceCode || '').trim()
		if (!key) return null
		return dataScopes.value[key] || null
	}

	const hasDataScope = (resourceCode, scopeCodes = []) => {
		const current = getDataScope(resourceCode)
		if (!current) return false
		return (scopeCodes || []).some(code => String(code || '').trim() === current)
	}

	// 权限相关的计算属性
	const isAdmin = computed(() => hasRole('admin'))
	const isActualAdmin = computed(() => hasRole('admin'))
	const isManager = computed(() => hasRole('manager'))
	const isWarehouseManager = computed(() => hasRole('warehouse_manager'))
	const isInspector = computed(() => hasRole('inspector'))
	const isSurveyor = computed(() => hasRole('surveyor'))
	const isUser = computed(() => hasRole('user'))
	const isWarehouseOperator = computed(() => hasPermission('inventory:stock-out:write') || isAdmin.value || isWarehouseManager.value)

	// 页面访问权限
	const canAccessSiteManagement = computed(() => hasAnyPermission(['sites:create:write', 'sites:update:write', 'sites:survey-stage:write']) || isActualAdmin.value)
	const canAccessUserManagement = computed(() => hasAnyPermission(['users:list:read', 'users:update:write', 'users:create:write']) || isActualAdmin.value)
	const canViewAllInspections = computed(() => hasPermission('workorder:review:write') || isActualAdmin.value)

	const can = (featureKey) => {
		const key = String(featureKey || '').trim()
		if (!key) return false
		const rule = APP_FEATURE_RULES[key]
		if (!rule) return false
		if (isActualAdmin.value || hasPermission('*')) return true

		const allPermissions = Array.isArray(rule.allPermissions) ? rule.allPermissions : []
		const anyPermissions = Array.isArray(rule.anyPermissions) ? rule.anyPermissions : []
		const roleCodes = Array.isArray(rule.roles) ? rule.roles : []

		const permissionsReady = hasAllPermissions(allPermissions) && (anyPermissions.length === 0 || hasAnyPermission(anyPermissions))
		const rolesReady = roleCodes.length === 0 || hasAnyRole(roleCodes)
		if (permissionsReady && rolesReady) return true

		if (!hasAnyAppPermission.value && Array.isArray(rule.legacyRoles) && rule.legacyRoles.length > 0) {
			return hasAnyRole(rule.legacyRoles)
		}
		return false
	}

	// 登录
	const login = async (username, password) => {
		try {
			console.log('🏪 UserStore: 开始登录:', { username })

			const loginUrl = buildApiUrl(API_ENDPOINTS.AUTH.LOGIN)
			const requestConfig = createRequestConfig({
				method: 'POST',
				data: {
					username,
					password,
					client_type: 'app',
				}
			})

			console.log('🌐 请求URL:', loginUrl)
			console.log('⚙️ 请求配置:', requestConfig)

			// 使用Promise包装uni.request以确保正确的错误处理
			const response = await new Promise((resolve, reject) => {
				console.log('📤 发送uni.request...')
				uni.request({
					url: loginUrl,
					...requestConfig,
					success: (res) => {
						console.log('✅ uni.request success:', res)
						resolve(res)
					},
					fail: (err) => {
						console.log('❌ uni.request fail:', err)
						reject(err)
					}
				})
			})

			console.log('📋 完整登录响应:', response)

			if (response.statusCode === 200) {
				const { access_token, refresh_token, user } = response.data
				const normalizedUser = normalizeUserInfo(user)
				token.value = access_token
				refreshToken.value = refresh_token
				userInfo.value = normalizedUser

				uni.setStorageSync('token', access_token)
				if (refresh_token) uni.setStorageSync('refreshToken', refresh_token)
				uni.setStorageSync('userInfo', normalizedUser)

				try {
					await startMobileLogReporter()
				} catch (e) {
					// ignore
				}

				try {
					const settingsRes = await uni.request({
						url: buildApiUrl('/api/system/mobile-settings/effective'),
						method: 'GET',
						header: {
							Authorization: `Bearer ${token.value}`,
						},
					})
					if (settingsRes.statusCode === 200 && settingsRes.data) {
						const mode = (settingsRes.data.location_mode || '').toLowerCase()
						if (mode === 'baidu' || mode === 'native') {
							setLocationMode(mode)
						}
						if (typeof settingsRes.data.allow_local_photo_upload === 'boolean') {
							setAllowLocalPhotoUpload(settingsRes.data.allow_local_photo_upload)
						} else {
							setAllowLocalPhotoUpload(true)
						}
						if (typeof settingsRes.data.local_upload_watermark_with_geo === 'boolean') {
							setLocalUploadWatermarkWithGeo(settingsRes.data.local_upload_watermark_with_geo)
						} else {
							setLocalUploadWatermarkWithGeo(true)
						}
						if (typeof settingsRes.data.enable_photo_location_distance_check === 'boolean') {
							setEnablePhotoLocationDistanceCheck(settingsRes.data.enable_photo_location_distance_check)
						} else {
							setEnablePhotoLocationDistanceCheck(true)
						}
						if (typeof settingsRes.data.distance_exceed_block_upload === 'boolean') {
							setDistanceExceedBlockUpload(settingsRes.data.distance_exceed_block_upload)
						} else {
							setDistanceExceedBlockUpload(false)
						}
						if (typeof settingsRes.data.photo_location_distance_threshold_m === 'number') {
							setPhotoLocationDistanceThresholdM(settingsRes.data.photo_location_distance_threshold_m)
						} else {
							setPhotoLocationDistanceThresholdM(100)
						}
						if (typeof settingsRes.data.enable_legacy_scan_pickup === 'boolean') {
							legacyScanPickupEnabled.value = settingsRes.data.enable_legacy_scan_pickup === true
						} else {
							legacyScanPickupEnabled.value = false
						}
						if (settingsRes.data.photo_watermark_effective && typeof settingsRes.data.photo_watermark_effective === 'object') {
							setPhotoWatermarkEffective(settingsRes.data.photo_watermark_effective)
						} else {
							setPhotoWatermarkEffective(null)
						}
					}
				} catch (e) {
					console.warn('刷新移动端配置失败（登录后）:', e)
				}

				console.log('登录成功:', user)
				return { success: true }
			} else if (response.statusCode === 401 || response.statusCode === 403) {
				const backendDetail = String(response.data?.detail || '').trim()
				return {
					success: false,
					errorCode: backendDetail || (response.statusCode === 401 ? 'INVALID_CREDENTIALS' : 'PERMISSION_DENIED'),
					error: backendDetail || '',
				}
			} else {
				console.error('登录失败:', response)
				const errorMsg = response.data?.detail || `服务器错误 (${response.statusCode})`
				return { success: false, error: errorMsg, errorCode: 'SERVER_ERROR' }
			}
		} catch (error) {
			console.error('Login error:', error)

			// 网络相关错误处理
			if (error.errMsg) {
				if (error.errMsg.includes('timeout')) {
					return { success: false, errorCode: 'NETWORK_TIMEOUT' }
				} else if (error.errMsg.includes('fail')) {
					return { success: false, errorCode: 'NETWORK_FAIL' }
				}
			}

			return { success: false, errorCode: 'NETWORK_ERROR', error: error.message }
		}
	}

	// 退出登录
	const logout = () => {
		// 尽量在清除 token 前尝试上报一次；失败则保留在本地队列中
		try {
			flush().catch(() => {})
		} catch (e) {
			// ignore
		}
		try {
			stopMobileLogReporter().catch(() => {})
		} catch (e) {
			// ignore
		}

		token.value = ''
		refreshToken.value = ''
		userInfo.value = null
		legacyScanPickupEnabled.value = false
		setPhotoWatermarkEffective(null)
		uni.removeStorageSync('token')
		uni.removeStorageSync('refreshToken')
		uni.removeStorageSync('userInfo')

		// 跳转到登录页
		uni.reLaunch({
			url: '/pages/login/login'
		})
	}

	// 检查登录状态
	const checkLoginStatus = () => {
		const savedToken = uni.getStorageSync('token')
		const savedRefresh = uni.getStorageSync('refreshToken')
			const savedUserInfo = uni.getStorageSync('userInfo')

			if (savedToken && savedUserInfo) {
				token.value = savedToken
				refreshToken.value = savedRefresh || ''
				userInfo.value = normalizeUserInfo(savedUserInfo)
			}
		}

	// 获取当前用户信息
	const getCurrentUser = async () => {
		if (!token.value) return null

		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.AUTH.ME),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${token.value}`
				}
				})

				if (response.statusCode === 200) {
					const normalizedUser = normalizeUserInfo(response.data)
					userInfo.value = normalizedUser
					uni.setStorageSync('userInfo', normalizedUser)
					return normalizedUser
			} else if (response.statusCode === 401) {
				// Token无效，清除存储并跳转到登录页
				logout()
				return null
			}
		} catch (error) {
			console.error('Get current user error:', error)
			// 如果认证失败，尝试刷新
			if (await tryRefresh()) {
				return getCurrentUser()
			}
			logout()
		}

		return null
	}

	// 验证token有效性
	const tryRefresh = async () => {
		if (!refreshToken.value) return false
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.AUTH.REFRESH),
				method: 'POST',
				data: { refresh_token: refreshToken.value }
			})
			if (res.statusCode === 200 && res.data?.access_token) {
				token.value = res.data.access_token
				if (res.data.refresh_token) refreshToken.value = res.data.refresh_token
				uni.setStorageSync('token', token.value)
				if (res.data.refresh_token) uni.setStorageSync('refreshToken', res.data.refresh_token)
				return true
			}
		} catch (e) {
			console.error('Refresh token failed:', e)
		}
		return false
	}

	const validateToken = async () => {
		if (!token.value) {
			return false
		}

		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.AUTH.ME),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${token.value}`
				}
			})

			if (response.statusCode === 200) {
				const normalizedUser = normalizeUserInfo(response.data)
				userInfo.value = normalizedUser
				uni.setStorageSync('userInfo', normalizedUser)

				try {
					await startMobileLogReporter()
				} catch (e) {
					// ignore
				}

				try {
					const settingsRes = await uni.request({
						url: buildApiUrl('/api/system/mobile-settings/effective'),
						method: 'GET',
						header: {
							Authorization: `Bearer ${token.value}`,
						},
					})
					if (settingsRes.statusCode === 200 && settingsRes.data) {
						const mode = (settingsRes.data.location_mode || '').toLowerCase()
						if (mode === 'baidu' || mode === 'native') {
							setLocationMode(mode)
						}
						if (typeof settingsRes.data.allow_local_photo_upload === 'boolean') {
							setAllowLocalPhotoUpload(settingsRes.data.allow_local_photo_upload)
						} else {
							setAllowLocalPhotoUpload(true)
						}
						if (typeof settingsRes.data.local_upload_watermark_with_geo === 'boolean') {
							setLocalUploadWatermarkWithGeo(settingsRes.data.local_upload_watermark_with_geo)
						} else {
							setLocalUploadWatermarkWithGeo(true)
						}
						if (typeof settingsRes.data.enable_photo_location_distance_check === 'boolean') {
							setEnablePhotoLocationDistanceCheck(settingsRes.data.enable_photo_location_distance_check)
						} else {
							setEnablePhotoLocationDistanceCheck(true)
						}
						if (typeof settingsRes.data.distance_exceed_block_upload === 'boolean') {
							setDistanceExceedBlockUpload(settingsRes.data.distance_exceed_block_upload)
						} else {
							setDistanceExceedBlockUpload(false)
						}
						if (typeof settingsRes.data.photo_location_distance_threshold_m === 'number') {
							setPhotoLocationDistanceThresholdM(settingsRes.data.photo_location_distance_threshold_m)
						} else {
							setPhotoLocationDistanceThresholdM(100)
						}
						if (typeof settingsRes.data.enable_legacy_scan_pickup === 'boolean') {
							legacyScanPickupEnabled.value = settingsRes.data.enable_legacy_scan_pickup === true
						} else {
							legacyScanPickupEnabled.value = false
						}
						if (settingsRes.data.photo_watermark_effective && typeof settingsRes.data.photo_watermark_effective === 'object') {
							setPhotoWatermarkEffective(settingsRes.data.photo_watermark_effective)
						} else {
							setPhotoWatermarkEffective(null)
						}
					}
				} catch (e) {
					console.warn('刷新移动端配置失败（validateToken）:', e)
				}

				return true
			} else if (response.statusCode === 401) {
				// Token无效，清除存储
				token.value = ''
				userInfo.value = null
				legacyScanPickupEnabled.value = false
				setPhotoWatermarkEffective(null)
				uni.removeStorageSync('token')
				uni.removeStorageSync('userInfo')
				return false
			}
		} catch (error) {
			console.error('Token validation error:', error)
			if (await tryRefresh()) {
				return validateToken()
			}
			token.value = ''
			refreshToken.value = ''
			userInfo.value = null
			legacyScanPickupEnabled.value = false
			setPhotoWatermarkEffective(null)
			uni.removeStorageSync('token')
			uni.removeStorageSync('refreshToken')
			uni.removeStorageSync('userInfo')
			return false
		}

		return false
	}

	return {
		token,
		refreshToken,
		userInfo,
			roles,
			permissions,
			dataScopes,
			legacyScanPickupEnabled,
		isLoggedIn,
		isAdmin,
		isActualAdmin,
		isManager,
		isWarehouseManager,
		isInspector,
		isUser,
		canAccessSiteManagement,
		canAccessUserManagement,
		canViewAllInspections,
		isSurveyor,
		isWarehouseOperator,
		hasRole,
		hasAnyRole,
			hasPermission,
			hasAnyPermission,
			hasAllPermissions,
			getDataScope,
			hasDataScope,
			can,
		login,
		logout,
		checkLoginStatus,
		getCurrentUser,
		validateToken,
	}
})
