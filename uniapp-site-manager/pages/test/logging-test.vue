<template>
	<view class="logging-test-container">
		<view class="header">
			<text class="title">日志系统测试页面</text>
			<text class="subtitle">测试各种用户行为日志记录</text>
		</view>
		
		<!-- 基础操作测试 -->
		<view class="section">
			<text class="section-title">基础操作测试</text>
			<view class="button-grid">
				<button class="test-btn" @click="testBasicAction">基础操作</button>
				<button class="test-btn" @click="testUserInteraction">用户交互</button>
				<button class="test-btn" @click="testFormAction">表单操作</button>
				<button class="test-btn" @click="testBusinessAction">业务操作</button>
			</view>
		</view>
		
		<!-- API测试 -->
		<view class="section">
			<text class="section-title">API调用测试</text>
			<view class="button-grid">
				<button class="test-btn" @click="testApiCall">测试API调用</button>
				<button class="test-btn" @click="testFailedApiCall">测试失败API</button>
				<button class="test-btn" @click="testSyncLogs">同步日志</button>
			</view>
		</view>
		
		<!-- 错误测试 -->
		<view class="section">
			<text class="section-title">错误处理测试</text>
			<view class="button-grid">
				<button class="test-btn" @click="testJavaScriptError">JS错误</button>
				<button class="test-btn" @click="testNetworkError">网络错误</button>
				<button class="test-btn" @click="testCustomError">自定义错误</button>
			</view>
		</view>
		
		<!-- GPS和照片测试 -->
		<view class="section">
			<text class="section-title">GPS和照片测试</text>
			<view class="button-grid">
				<button class="test-btn" @click="testGpsAction">GPS操作</button>
				<button class="test-btn" @click="testPhotoAction">照片操作</button>
				<button class="test-btn" @click="testSearchAction">搜索操作</button>
			</view>
		</view>
		
		<!-- 日志统计 -->
		<view class="section">
			<text class="section-title">日志统计</text>
			<view class="stats-container">
				<view class="stat-item">
					<text class="stat-label">当前会话日志:</text>
					<text class="stat-value">{{ logStats.todayLogs }}</text>
				</view>
				<view class="stat-item">
					<text class="stat-label">待同步日志:</text>
					<text class="stat-value">{{ logStats.pendingLogs }}</text>
				</view>
				<view class="stat-item">
					<text class="stat-label">会话ID:</text>
					<text class="stat-value session-id">{{ logStats.sessionId }}</text>
				</view>
			</view>
			<button class="test-btn refresh-btn" @click="refreshStats">刷新统计</button>
		</view>
		
		<!-- 日志导出 -->
		<view class="section">
			<text class="section-title">日志管理</text>
			<view class="button-grid">
				<button class="test-btn" @click="exportLogs">导出日志</button>
				<button class="test-btn" @click="clearLocalLogs">清理本地日志</button>
				<button class="test-btn" @click="viewLogDetails">查看详细日志</button>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, reactive, onMounted } from 'vue'
	import { useLoggerStore } from '@/stores/logger'
	import { buildApiUrl, API_ENDPOINTS, getAuthHeaders } from '@/config/api.js'
	
	const logger = useLoggerStore()
	
	const logStats = reactive({
		todayLogs: 0,
		pendingLogs: 0,
		sessionId: '',
		totalLogs: 0
	})
	
	// 页面加载时记录日志
	onMounted(() => {
		logger.logPageView('/pages/test/logging-test')
		logger.logAction('LOGGING_TEST_PAGE_LOADED')
		refreshStats()
	})
	
	// 刷新统计信息
	const refreshStats = () => {
		const stats = logger.getLogStats()
		Object.assign(logStats, stats)
	}
	
	// 测试基础操作
	const testBasicAction = () => {
		logger.logAction('TEST_BASIC_ACTION', {
			testType: 'basic',
			timestamp: new Date().toISOString(),
			randomValue: Math.random()
		})
		
		uni.showToast({
			title: '基础操作已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 测试用户交互
	const testUserInteraction = () => {
		logger.logUserInteraction('test-button', 'click', {
			buttonType: 'user-interaction-test',
			testData: {
				clickTime: Date.now(),
				platform: uni.getSystemInfoSync().platform
			}
		})
		
		uni.showToast({
			title: '用户交互已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 测试表单操作
	const testFormAction = () => {
		logger.logFormAction('test-form', 'field_change', 'test-field', 'test-value')
		logger.logFormAction('test-form', 'validation_success', null, null)
		logger.logFormAction('test-form', 'submit', null, { formData: 'test-data' })
		
		uni.showToast({
			title: '表单操作已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 测试业务操作
	const testBusinessAction = () => {
		logger.logBusinessAction('create', 'test-entity', 'test-123', {
			operation: 'create_test_entity',
			entityData: {
				name: 'Test Entity',
				type: 'test',
				createdAt: new Date().toISOString()
			}
		})
		
		uni.showToast({
			title: '业务操作已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 测试API调用
	const testApiCall = async () => {
		try {
			const token = uni.getStorageSync('token')
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.SYSTEM.HEALTH),
				method: 'GET',
				header: getAuthHeaders(token)
			})
			
			uni.showToast({
				title: 'API调用成功',
				icon: 'success'
			})
		} catch (error) {
			logger.logError(error, { context: 'test_api_call' })
		}
		
		refreshStats()
	}
	
	// 测试失败的API调用
	const testFailedApiCall = async () => {
		try {
			await uni.request({
				url: buildApiUrl('/api/test-nonexistent-endpoint'),
				method: 'GET'
			})
		} catch (error) {
			uni.showToast({
				title: '预期的API错误已记录',
				icon: 'none'
			})
		}
		
		refreshStats()
	}
	
	// 测试同步日志
	const testSyncLogs = async () => {
		try {
			await logger.syncPendingLogs()
			uni.showToast({
				title: '日志同步完成',
				icon: 'success'
			})
		} catch (error) {
			uni.showToast({
				title: '日志同步失败',
				icon: 'error'
			})
		}
		
		refreshStats()
	}
	
	// 测试JavaScript错误
	const testJavaScriptError = () => {
		try {
			// 故意创建一个错误
			const undefinedObject = null
			undefinedObject.someProperty.test = 'test'
		} catch (error) {
			logger.logError(error, {
				context: 'javascript_error_test',
				testType: 'intentional_error'
			})
			
			uni.showToast({
				title: 'JavaScript错误已记录',
				icon: 'none'
			})
		}
		
		refreshStats()
	}
	
	// 测试网络错误
	const testNetworkError = () => {
		const networkError = new Error('网络连接失败')
		networkError.name = 'NetworkError'
		
		logger.logError(networkError, {
			context: 'network_error_test',
			testType: 'simulated_network_error',
			errorCode: 'NETWORK_TIMEOUT'
		})
		
		uni.showToast({
			title: '网络错误已记录',
			icon: 'none'
		})
		
		refreshStats()
	}
	
	// 测试自定义错误
	const testCustomError = () => {
		const customError = new Error('这是一个自定义测试错误')
		customError.name = 'CustomTestError'
		
		logger.logError(customError, {
			context: 'custom_error_test',
			errorType: 'custom',
			severity: 'high',
			additionalInfo: {
				userAction: 'test_custom_error',
				timestamp: new Date().toISOString()
			}
		})
		
		uni.showToast({
			title: '自定义错误已记录',
			icon: 'none'
		})
		
		refreshStats()
	}
	
	// 测试GPS操作
	const testGpsAction = () => {
		logger.logGpsAction('location_request', 116.404, 39.915, 10)
		logger.logGpsAction('location_success', 116.404, 39.915, 5)
		
		uni.showToast({
			title: 'GPS操作已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 测试照片操作
	const testPhotoAction = () => {
		logger.logPhotoAction('camera_open')
		logger.logPhotoAction('photo_taken', '/temp/test-photo.jpg', {
			latitude: 116.404,
			longitude: 39.915,
			timestamp: new Date().toISOString()
		})
		
		uni.showToast({
			title: '照片操作已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 测试搜索操作
	const testSearchAction = () => {
		logger.logSearch('site_search', '测试站点', { status: 'operational' }, 5)
		logger.logSearch('user_search', 'admin', {}, 1)
		
		uni.showToast({
			title: '搜索操作已记录',
			icon: 'success'
		})
		
		refreshStats()
	}
	
	// 导出日志
	const exportLogs = () => {
		const exportData = logger.exportLogs()
		
		uni.showModal({
			title: '日志导出',
			content: `共导出 ${exportData.logs.length} 条日志，详细信息请查看控制台`,
			showCancel: false
		})
		
		console.log('导出的日志数据:', exportData)
	}
	
	// 清理本地日志
	const clearLocalLogs = () => {
		uni.showModal({
			title: '确认清理',
			content: '是否确认清理本地存储的所有日志？',
			success: (res) => {
				if (res.confirm) {
					try {
						uni.removeStorageSync('user_logs')
						logger.logs.length = 0
						logger.pendingLogs.length = 0
						
						uni.showToast({
							title: '本地日志已清理',
							icon: 'success'
						})
						
						refreshStats()
					} catch (error) {
						uni.showToast({
							title: '清理失败',
							icon: 'error'
						})
					}
				}
			}
		})
	}
	
	// 查看详细日志
	const viewLogDetails = () => {
		const recentLogs = logger.logs.slice(-10)
		
		uni.showModal({
			title: '最近10条日志',
			content: `请查看控制台输出的详细日志信息`,
			showCancel: false
		})
		
		console.log('最近的日志记录:', recentLogs)
		console.log('日志统计信息:', logger.getLogStats())
	}
</script>

<style lang="scss" scoped>
	.logging-test-container {
		padding: 16px;
		background-color: #f5f5f5;
		min-height: 100vh;
	}
	
	.header {
		text-align: center;
		margin-bottom: 24px;
		padding: 16px;
		background: white;
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}
	
	.title {
		font-size: 20px;
		font-weight: bold;
		color: #f97316;
		display: block;
		margin-bottom: 8px;
	}
	
	.subtitle {
		font-size: 14px;
		color: #6b7280;
	}
	
	.section {
		margin-bottom: 16px;
		padding: 16px;
		background: white;
		border-radius: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}
	
	.section-title {
		font-size: 16px;
		font-weight: 600;
		color: #374151;
		display: block;
		margin-bottom: 12px;
	}
	
	.button-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	
	.test-btn {
		padding: 12px 16px;
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
		border: none;
		border-radius: 8px;
		font-size: 14px;
		font-weight: 500;
		box-shadow: 0 2px 4px rgba(249, 115, 22, 0.3);
		transition: all 0.3s ease;
	}
	
	.test-btn:active {
		transform: translateY(1px);
		box-shadow: 0 1px 2px rgba(249, 115, 22, 0.3);
	}
	
	.refresh-btn {
		width: 100%;
		grid-column: 1 / -1;
		margin-top: 8px;
	}
	
	.stats-container {
		margin-bottom: 12px;
	}
	
	.stat-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 8px 0;
		border-bottom: 1px solid #f3f4f6;
	}
	
	.stat-item:last-child {
		border-bottom: none;
	}
	
	.stat-label {
		font-size: 14px;
		color: #6b7280;
	}
	
	.stat-value {
		font-size: 14px;
		font-weight: 600;
		color: #374151;
	}
	
	.session-id {
		font-family: monospace;
		font-size: 12px;
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>