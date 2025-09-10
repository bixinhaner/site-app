import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'

export const useUserStore = defineStore('user', () => {
	const token = ref('')
	const userInfo = ref(null)
	const isLoggedIn = computed(() => !!token.value)
	
	// 权限相关的计算属性
	const isAdmin = computed(() => userInfo.value?.role === 'admin')
	const isInspector = computed(() => userInfo.value?.role === 'inspector')
	const isUser = computed(() => userInfo.value?.role === 'user')
	
	// 页面访问权限
	const canAccessTaskManagement = computed(() => isAdmin.value)
	const canAccessSiteManagement = computed(() => isAdmin.value)
	const canAccessUserManagement = computed(() => isAdmin.value)
	const canCreateTasks = computed(() => isAdmin.value)
	const canAssignTasks = computed(() => isAdmin.value)
	const canViewAllTasks = computed(() => isAdmin.value)
	const canViewAllInspections = computed(() => isAdmin.value)
	
	// 登录
	const login = async (username, password) => {
		try {
			console.log('开始登录:', { username })
			
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.AUTH.LOGIN),
				...createRequestConfig({
					method: 'POST',
					data: {
						username,
						password
					}
				})
			})
			
			console.log('登录响应:', response)
			
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
				return { success: false, error: '用户名或密码错误' }
			} else {
				console.error('登录失败:', response)
				const errorMsg = response.data?.detail || `服务器错误 (${response.statusCode})`
				return { success: false, error: errorMsg }
			}
		} catch (error) {
			console.error('Login error:', error)
			
			// 网络相关错误处理
			if (error.errMsg) {
				if (error.errMsg.includes('timeout')) {
					return { success: false, error: '请求超时，请检查网络连接' }
				} else if (error.errMsg.includes('fail')) {
					return { success: false, error: '网络连接失败，请检查服务器状态' }
				}
			}
			
			return { success: false, error: error.message || '网络异常' }
		}
	}
	
	// 注册
	const register = async (userData) => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.AUTH.REGISTER),
				...createRequestConfig({
					method: 'POST',
					data: userData
				})
			})
			
			if (response.statusCode === 200) {
				return { success: true, data: response.data }
			} else {
				throw new Error(response.data.detail || '注册失败')
			}
		} catch (error) {
			console.error('Register error:', error)
			return { success: false, error: error.message || '网络错误' }
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
		canAccessTaskManagement,
		canAccessSiteManagement,
		canAccessUserManagement,
		canCreateTasks,
		canAssignTasks,
		canViewAllTasks,
		canViewAllInspections,
		// 方法
		login,
		register,
		logout,
		checkLoginStatus,
		getCurrentUser,
		validateToken
	}
})