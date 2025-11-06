import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig } from '@/config/api.js'

export const useUserStore = defineStore('user', () => {
	const token = ref('')
	const userInfo = ref(null)
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
				const { access_token, user } = response.data
				token.value = access_token
				userInfo.value = user
				
				// 保存到本地存储
				uni.setStorageSync('token', access_token)
				uni.setStorageSync('userInfo', user)
				
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
		token.value = ''
		userInfo.value = null
		uni.removeStorageSync('token')
		uni.removeStorageSync('userInfo')
		
		// 跳转到登录页
		uni.reLaunch({
			url: '/pages/login/login'
		})
	}
	
	// 检查登录状态
	const checkLoginStatus = () => {
		const savedToken = uni.getStorageSync('token')
		const savedUserInfo = uni.getStorageSync('userInfo')
		
		if (savedToken && savedUserInfo) {
			token.value = savedToken
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
			// 如果是认证错误，清除token
			if (error.message && error.message.includes('Could not validate credentials')) {
				logout()
			}
		}
		
		return null
	}
	
	// 验证token有效性
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
			// 如果是认证错误，清除token
			token.value = ''
			userInfo.value = null
			uni.removeStorageSync('token')
			uni.removeStorageSync('userInfo')
			return false
		}
		
		return false
	}
	
	return {
		token,
		userInfo,
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
