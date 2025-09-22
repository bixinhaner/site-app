/**
 * 用户行为日志系统
 * 记录用户在APP中的所有操作行为和使用轨迹
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { buildApiUrl } from '@/config/api.js'

export const useLoggerStore = defineStore('logger', () => {
	const logs = ref([])
	const sessionId = ref('')
	const isOnline = ref(false)
	const pendingLogs = ref([])
	
	// 生成会话ID
	const generateSessionId = () => {
		const timestamp = Date.now()
		const random = Math.random().toString(36).substr(2, 9)
		return `session_${timestamp}_${random}`
	}
	
	// 初始化日志系统
	const initLogger = () => {
		console.log('🔧 Logger initLogger() called')
		
		try {
			sessionId.value = generateSessionId()
			console.log('✅ Session ID generated:', sessionId.value)
		} catch (error) {
			console.error('❌ Failed to generate session ID:', error)
		}
		
		// UniApp环境下获取网络状态
		try {
			console.log('🌐 Getting network type...')
			uni.getNetworkType({
				success: (res) => {
					isOnline.value = res.networkType !== 'none'
					console.log('✅ Network status:', res.networkType, 'isOnline:', isOnline.value)
				},
				fail: () => {
					isOnline.value = true // 默认为在线状态
					console.log('⚠️ Failed to get network type, defaulting to online')
				}
			})
		} catch (error) {
			isOnline.value = true // 默认为在线状态
			console.error('❌ Error getting network type:', error)
		}
		
		// 监听网络状态变化
		uni.onNetworkStatusChange((res) => {
			isOnline.value = res.isConnected
			if (isOnline.value && pendingLogs.value.length > 0) {
				syncPendingLogs()
			}
		})
		
		// 记录应用启动日志
		logAction('APP_START', {
			timestamp: new Date().toISOString(),
			platform: uni.getSystemInfoSync().platform,
			version: uni.getSystemInfoSync().version
		})
	}
	
	// 获取用户信息
	const getUserContext = () => {
		try {
			console.log('👤 Getting user context...')
			const userInfo = uni.getStorageSync('userInfo')
			const result = {
				userId: userInfo?.id || 'anonymous',
				username: userInfo?.username || 'anonymous',
				role: userInfo?.role || 'unknown'
			}
			console.log('✅ User context retrieved:', result)
			return result
		} catch (error) {
			console.error('❌ Error getting user context:', error)
			return {
				userId: 'anonymous',
				username: 'anonymous',
				role: 'unknown'
			}
		}
	}
	
	// 获取页面信息
	const getPageContext = () => {
		try {
			console.log('📄 Getting page context...')
			const pages = getCurrentPages()
			console.log('📄 Current pages:', pages?.length || 0)
			const currentPage = pages[pages.length - 1]
			const result = {
				route: currentPage?.route || 'unknown',
				options: currentPage?.options || {}
			}
			console.log('✅ Page context retrieved:', result)
			return result
		} catch (error) {
			console.error('❌ Error getting page context:', error)
			return {
				route: 'unknown',
				options: {}
			}
		}
	}
	
	// 记录用户行为
	const logAction = (action, data = {}, level = 'INFO') => {
		console.log(`⚠️ LogAction disabled for debugging: ${action}`)
		return  // 早期返回，不执行任何日志操作
		
		try {
			console.log(`📊 LogAction called: ${action}`, { data, level })
			
			const logEntry = {
				id: Date.now() + Math.random(),
				sessionId: sessionId.value,
				timestamp: new Date().toISOString(),
				action,
				level,
				user: getUserContext(),
				page: getPageContext(),
				data,
				deviceInfo: {
					platform: uni.getSystemInfoSync().platform,
					model: uni.getSystemInfoSync().model,
					screenWidth: uni.getSystemInfoSync().screenWidth,
					screenHeight: uni.getSystemInfoSync().screenHeight
				}
			}
			
			console.log(`✅ Log entry created for ${action}:`, logEntry)
			
			logs.value.push(logEntry)
			
			// 保存到本地存储
			try {
				console.log(`💾 Saving log to local storage...`)
				const storedLogs = uni.getStorageSync('user_logs') || []
				storedLogs.push(logEntry)
				// 只保留最近1000条日志
				if (storedLogs.length > 1000) {
					storedLogs.splice(0, storedLogs.length - 1000)
				}
				uni.setStorageSync('user_logs', storedLogs)
				console.log(`✅ Log saved to local storage`)
			} catch (error) {
				console.error('❌ 保存日志到本地存储失败:', error)
			}
			
			// 尝试发送到服务器
			if (isOnline.value) {
				console.log(`🌐 Sending log to server...`)
				sendLogToServer(logEntry)
			} else {
				console.log(`📱 Offline, adding to pending logs`)
				pendingLogs.value.push(logEntry)
			}
		} catch (error) {
			console.error(`❌ Error in logAction for ${action}:`, error)
		}
	}
	
	// 记录页面访问
	const logPageView = (pagePath, options = {}) => {
		console.log(`⚠️ LogPageView disabled for debugging: ${pagePath}`)
		return
		// logAction('PAGE_VIEW', {
		// 	pagePath,
		// 	options,
		// 	previousPage: getCurrentPages().length > 1 ? getCurrentPages()[getCurrentPages().length - 2]?.route : null
		// })
	}
	
	// 记录用户交互
	const logUserInteraction = (element, action, data = {}) => {
		console.log(`⚠️ LogUserInteraction disabled for debugging: ${element} - ${action}`)
		return
		// logAction('USER_INTERACTION', {
		// 	element,
		// 	interaction: action,
		// 	...data
		// })
	}
	
	// 记录API调用
	const logApiCall = (endpoint, method, requestData = {}, responseStatus, responseTime, error = null) => {
		logAction('API_CALL', {
			endpoint,
			method,
			requestData: typeof requestData === 'object' ? JSON.stringify(requestData) : requestData,
			responseStatus,
			responseTime,
			error: error ? error.toString() : null
		}, error ? 'ERROR' : 'INFO')
	}
	
	// 记录错误
	const logError = (error, context = {}) => {
		logAction('ERROR', {
			error: {
				message: error.message || error.toString(),
				stack: error.stack || 'No stack trace',
				name: error.name || 'Unknown Error'
			},
			context
		}, 'ERROR')
	}
	
	// 记录业务操作
	const logBusinessAction = (businessAction, entityType, entityId, data = {}) => {
		logAction('BUSINESS_ACTION', {
			businessAction,
			entityType,
			entityId,
			...data
		})
	}
	
	// 记录表单操作
	const logFormAction = (formName, action, fieldName = null, fieldValue = null) => {
		logAction('FORM_ACTION', {
			formName,
			formAction: action,
			fieldName,
			fieldValue: typeof fieldValue === 'object' ? JSON.stringify(fieldValue) : fieldValue
		})
	}
	
	// 记录搜索操作
	const logSearch = (searchType, keyword, filters = {}, resultsCount = 0) => {
		logAction('SEARCH', {
			searchType,
			keyword,
			filters,
			resultsCount
		})
	}
	
	// 记录GPS相关操作
	const logGpsAction = (gpsAction, latitude = null, longitude = null, accuracy = null, error = null) => {
		logAction('GPS_ACTION', {
			gpsAction,
			latitude,
			longitude,
			accuracy,
			error: error ? error.toString() : null
		}, error ? 'ERROR' : 'INFO')
	}
	
	// 记录照片操作
	const logPhotoAction = (photoAction, photoPath = null, gpsInfo = null, error = null) => {
		logAction('PHOTO_ACTION', {
			photoAction,
			photoPath,
			gpsInfo,
			error: error ? error.toString() : null
		}, error ? 'ERROR' : 'INFO')
	}
	
	// 发送日志到服务器
	const sendLogToServer = async (logEntry) => {
		try {
			const token = uni.getStorageSync('token')
			if (!token) return
			
			await uni.request({
				url: buildApiUrl('/api/logs'),
				method: 'POST',
				header: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${token}`
				},
				data: logEntry,
				timeout: 5000
			})
		} catch (error) {
			pendingLogs.value.push(logEntry)
		}
	}
	
	// 同步待发送的日志
	const syncPendingLogs = async () => {
		if (pendingLogs.value.length === 0) return
		
		try {
			const token = uni.getStorageSync('token')
			if (!token) return
			
			const logsToSend = [...pendingLogs.value]
			pendingLogs.value = []
			
			await uni.request({
				url: buildApiUrl('/api/logs/batch'),
				method: 'POST',
				header: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${token}`
				},
				data: { logs: logsToSend },
				timeout: 10000
			})
			
			console.log(`已同步 ${logsToSend.length} 条离线日志`)
		} catch (error) {
			console.error('同步离线日志失败:', error)
		}
	}
	
	// 清理旧日志
	const cleanOldLogs = () => {
		try {
			const storedLogs = uni.getStorageSync('user_logs') || []
			const now = new Date()
			const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
			
			const recentLogs = storedLogs.filter(log => {
				const logDate = new Date(log.timestamp)
				return logDate > sevenDaysAgo
			})
			
			uni.setStorageSync('user_logs', recentLogs)
			logs.value = recentLogs
		} catch (error) {
			console.error('清理旧日志失败:', error)
		}
	}
	
	// 获取日志统计
	const getLogStats = () => {
		const storedLogs = uni.getStorageSync('user_logs') || []
		const now = new Date()
		const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
		
		const todayLogs = storedLogs.filter(log => {
			const logDate = new Date(log.timestamp)
			return logDate >= today
		})
		
		const actionCounts = {}
		todayLogs.forEach(log => {
			actionCounts[log.action] = (actionCounts[log.action] || 0) + 1
		})
		
		return {
			totalLogs: storedLogs.length,
			todayLogs: todayLogs.length,
			pendingLogs: pendingLogs.value.length,
			actionCounts,
			sessionId: sessionId.value
		}
	}
	
	// 导出日志（用于调试）
	const exportLogs = () => {
		const storedLogs = uni.getStorageSync('user_logs') || []
		return {
			logs: storedLogs,
			stats: getLogStats()
		}
	}
	
	return {
		logs,
		sessionId,
		isOnline,
		pendingLogs,
		
		// 初始化
		initLogger,
		
		// 基础日志记录
		logAction,
		logError,
		
		// 特定类型日志记录
		logPageView,
		logUserInteraction,
		logApiCall,
		logBusinessAction,
		logFormAction,
		logSearch,
		logGpsAction,
		logPhotoAction,
		
		// 日志管理
		syncPendingLogs,
		cleanOldLogs,
		getLogStats,
		exportLogs
	}
})