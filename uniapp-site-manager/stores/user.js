import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig } from '@/config/api.js'
import {
	setLocationMode,
	setAllowLocalPhotoUpload,
	setLocalUploadWatermarkWithGeo,
	setEnablePhotoLocationDistanceCheck,
	setDistanceExceedBlockUpload,
	setPhotoLocationDistanceThresholdM,
} from '@/utils/locationStrategy.js'
import { flush, startMobileLogReporter, stopMobileLogReporter } from '@/utils/mobileLogReporter.js'

export const useUserStore = defineStore('user', () => {
	const token = ref(uni.getStorageSync('token') || '')
	const refreshToken = ref(uni.getStorageSync('refreshToken') || '')
	const userInfo = ref(uni.getStorageSync('userInfo') || null)
	// 旧流程：我的设备-扫码领货开关（默认关闭；登录后从 /api/system/mobile-settings/effective 刷新）
	const legacyScanPickupEnabled = ref(false)
	const isLoggedIn = computed(() => !!token.value)

	// 权限相关的计算属性
	// 将 manager 视作 admin 等同的权限
	const isAdmin = computed(() => ['admin', 'manager'].includes(userInfo.value?.role))
	const isInspector = computed(() => userInfo.value?.role === 'inspector')
	const isSurveyor = computed(() => userInfo.value?.role === 'surveyor')
	const isUser = computed(() => userInfo.value?.role === 'user')

	// 页面访问权限
	const canAccessSiteManagement = computed(() => isAdmin.value)
	const canAccessUserManagement = computed(() => isAdmin.value)
	const canViewAllInspections = computed(() => isAdmin.value)

	// 登录
	const login = async (username, password) => {
		try {
			console.log('🏪 UserStore: 开始登录:', { username })

			const loginUrl = buildApiUrl(API_ENDPOINTS.AUTH.LOGIN)
			const requestConfig = createRequestConfig({
				method: 'POST',
				data: {
					username,
					password
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
				token.value = access_token
				refreshToken.value = refresh_token
				userInfo.value = user

				uni.setStorageSync('token', access_token)
				if (refresh_token) uni.setStorageSync('refreshToken', refresh_token)
				uni.setStorageSync('userInfo', user)

				// 登录后开始采集并上报日志（不采集未登录阶段）
				try {
					await startMobileLogReporter()
				} catch (e) {
					// ignore
				}

				// 登录成功后，根据当前用户刷新移动端配置（例如定位模式、本地上传开关）
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
							// 未返回时默认允许
							setAllowLocalPhotoUpload(true)
						}
							if (typeof settingsRes.data.local_upload_watermark_with_geo === 'boolean') {
								setLocalUploadWatermarkWithGeo(settingsRes.data.local_upload_watermark_with_geo)
							} else {
								// 未返回时默认携带（沿用现状）
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
						}
					} catch (e) {
						console.warn('刷新移动端配置失败（登录后）:', e)
					}

				console.log('登录成功:', user)
				return { success: true }
			} else if (response.statusCode === 401) {
				return { success: false, errorCode: 'INVALID_CREDENTIALS' }
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
			userInfo.value = savedUserInfo
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
				userInfo.value = response.data
				uni.setStorageSync('userInfo', response.data)
				return response.data
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
				userInfo.value = response.data
				uni.setStorageSync('userInfo', response.data)

				// Token 验证通过后开始采集并上报日志（不采集未登录阶段）
				try {
					await startMobileLogReporter()
				} catch (e) {
					// ignore
				}

				// 验证通过后，同步一次当前用户的移动端配置（例如定位模式、本地上传开关）
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
						}
					} catch (e) {
						console.warn('刷新移动端配置失败（validateToken）:', e)
					}

				return true
			} else if (response.statusCode === 401) {
				// Token无效，清除存储
				token.value = ''
				userInfo.value = null
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
			uni.removeStorageSync('token')
			uni.removeStorageSync('refreshToken')
			uni.removeStorageSync('userInfo')
			return false
		}

		return false
	}

		return {
			token,
			userInfo,
			legacyScanPickupEnabled,
			isLoggedIn,
		// 权限属性
		isAdmin,
		isInspector,
		isUser,
		canAccessSiteManagement,
		canAccessUserManagement,
		canViewAllInspections,
		isSurveyor,
		// 方法
		login,
		logout,
		checkLoginStatus,
		getCurrentUser,
		validateToken
	}
})
