/**
 * API请求拦截器
 * 自动记录所有API调用日志
 */

import { useLoggerStore } from '@/stores/logger'

// 保存原始的uni.request方法
const originalRequest = uni.request

// 包装uni.request以添加日志记录
const createRequestInterceptor = () => {
	uni.request = (options) => {
		let logger
		try {
			logger = useLoggerStore()
		} catch (error) {
			// 如果logger store还未初始化，直接调用原始请求
			return originalRequest.call(uni, options)
		}
		const startTime = Date.now()
		
		// 记录请求开始日志
		const requestId = `req_${startTime}_${Math.random().toString(36).substr(2, 9)}`
		logger.logApiCall(
			options.url,
			options.method || 'GET',
			options.data || {},
			'PENDING',
			0,
			null
		)
		
		// 包装success回调
		const originalSuccess = options.success
		options.success = (response) => {
			const responseTime = Date.now() - startTime
			
			// 记录成功响应日志
			logger.logApiCall(
				options.url,
				options.method || 'GET',
				options.data || {},
				response.statusCode,
				responseTime,
				null
			)
			
			// 如果是认证相关的响应，记录特殊日志
			if (options.url.includes('/auth/login') && response.statusCode === 200) {
				logger.logAction('API_LOGIN_SUCCESS', {
					responseTime,
					userRole: response.data?.user?.role
				})
			} else if (response.statusCode === 401) {
				logger.logAction('API_UNAUTHORIZED', {
					url: options.url,
					responseTime
				})
			}
			
			// 调用原始成功回调
			if (originalSuccess) {
				originalSuccess(response)
			}
		}
		
		// 包装fail回调
		const originalFail = options.fail
		options.fail = (error) => {
			const responseTime = Date.now() - startTime
			
			// 记录失败日志
			logger.logApiCall(
				options.url,
				options.method || 'GET',
				options.data || {},
				'ERROR',
				responseTime,
				error
			)
			
			logger.logError(error, {
				context: 'api_request_failed',
				url: options.url,
				method: options.method || 'GET',
				requestData: options.data,
				responseTime
			})
			
			// 调用原始失败回调
			if (originalFail) {
				originalFail(error)
			}
		}
		
		// 包装complete回调
		const originalComplete = options.complete
		options.complete = (response) => {
			const responseTime = Date.now() - startTime
			
			// 记录请求完成日志
			logger.logAction('API_REQUEST_COMPLETE', {
				url: options.url,
				method: options.method || 'GET',
				statusCode: response?.statusCode,
				responseTime,
				requestId
			})
			
			// 调用原始完成回调
			if (originalComplete) {
				originalComplete(response)
			}
		}
		
		// 调用原始请求方法
		return originalRequest.call(uni, options)
	}
}

// 添加全局错误处理
const setupGlobalErrorHandling = () => {
	let logger
	try {
		logger = useLoggerStore()
	} catch (error) {
		console.warn('Logger store not ready for global error handling')
		return
	}
	
	// 监听应用错误
	uni.onError = (error) => {
		logger.logError(new Error(error), {
			context: 'global_app_error',
			timestamp: new Date().toISOString()
		})
	}
	
	// 监听页面未找到错误
	uni.onPageNotFound = (options) => {
		logger.logError(new Error('Page not found'), {
			context: 'page_not_found',
			path: options.path,
			query: options.query,
			timestamp: new Date().toISOString()
		})
	}
	
	// 监听网络状态变化
	try {
		uni.onNetworkStatusChange((result) => {
			logger.logAction('NETWORK_STATUS_CHANGE', {
				isConnected: result.isConnected,
				networkType: result.networkType,
				timestamp: new Date().toISOString()
			})
		})
	} catch (error) {
		console.warn('网络状态监听设置失败:', error)
	}
}

// 添加页面路由拦截
const setupPageInterceptor = () => {
	let logger
	try {
		logger = useLoggerStore()
	} catch (error) {
		console.warn('Logger store not ready for page interceptor')
		return
	}
	
	// 保存原始页面跳转方法
	const originalNavigateTo = uni.navigateTo
	const originalRedirectTo = uni.redirectTo
	const originalReLaunch = uni.reLaunch
	const originalNavigateBack = uni.navigateBack
	
	// 包装页面跳转方法（保留日志记录，但不再单独包装 switchTab）
	uni.navigateTo = (options) => {
		logger.logAction('PAGE_NAVIGATE', {
			type: 'navigateTo',
			url: options.url,
			timestamp: new Date().toISOString()
		})
		return originalNavigateTo.call(uni, options)
	}
	
	uni.redirectTo = (options) => {
		logger.logAction('PAGE_NAVIGATE', {
			type: 'redirectTo',
			url: options.url,
			timestamp: new Date().toISOString()
		})
		return originalRedirectTo.call(uni, options)
	}
	
	uni.reLaunch = (options) => {
		logger.logAction('PAGE_NAVIGATE', {
			type: 'reLaunch',
			url: options.url,
			timestamp: new Date().toISOString()
		})
		return originalReLaunch.call(uni, options)
	}
	
	uni.navigateBack = (options = {}) => {
		logger.logAction('PAGE_NAVIGATE', {
			type: 'navigateBack',
			delta: options.delta || 1,
			timestamp: new Date().toISOString()
		})
		return originalNavigateBack.call(uni, options)
	}
}

// 添加用户交互事件监听
const setupInteractionLogging = () => {
	let logger
	try {
		logger = useLoggerStore()
	} catch (error) {
		console.warn('Logger store not ready for interaction logging')
		return
	}
	
	// 监听应用生命周期
	const originalOnShow = uni.onAppShow
	const originalOnHide = uni.onAppHide
	
	uni.onAppShow = (options) => {
		logger.logAction('APP_FOREGROUND', {
			path: options.path,
			query: options.query,
			scene: options.scene,
			timestamp: new Date().toISOString()
		})
		if (originalOnShow) originalOnShow(options)
	}
	
	uni.onAppHide = () => {
		logger.logAction('APP_BACKGROUND', {
			timestamp: new Date().toISOString()
		})
		if (originalOnHide) originalOnHide()
	}
}

// 初始化所有拦截器
export const initInterceptors = () => {
	try {
		createRequestInterceptor()
		setupGlobalErrorHandling()
		setupPageInterceptor()
		setupInteractionLogging()
		
		console.log('API拦截器初始化完成')
		
		// 记录拦截器初始化日志
		try {
			const logger = useLoggerStore()
			logger.logAction('INTERCEPTORS_INITIALIZED', {
				timestamp: new Date().toISOString(),
				interceptors: ['api', 'error', 'page', 'interaction']
			})
		} catch (error) {
			console.warn('Logger store not ready for interceptor init log')
		}
	} catch (error) {
		console.error('API拦截器初始化失败:', error)
	}
}

// 恢复原始方法（用于调试或特殊情况）
export const restoreOriginalMethods = () => {
	uni.request = originalRequest
	console.log('已恢复原始API方法')
}
