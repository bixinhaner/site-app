<template>
	<view id="app">
		<!-- 全局加载提示 -->
		<uni-load-more v-if="globalLoading" status="loading" :content-text="loadingText"></uni-load-more>
	</view>
</template>

<script setup>
	import { ref } from 'vue'
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useOfflineStore } from '@/stores/offline'
	import { useLoggerStore } from '@/stores/logger'
	import { initInterceptors } from '@/utils/api-interceptor'
	
	const globalLoading = ref(false)
	const loadingText = ref({
		contentdown: '上拉显示更多',
		contentrefresh: '正在加载...',
		contentnomore: '没有更多数据了'
	})
	
	const userStore = useUserStore()
	const offlineStore = useOfflineStore()
	const logger = useLoggerStore()
	
	onLaunch(async () => {
		console.log('🚀 App Launch - Start')
		
		// 暂时禁用日志功能，专注解决页面加载问题
		console.log('⚠️ Logger system temporarily disabled for debugging')
		
		// 暂时不初始化API拦截器
		console.log('⚠️ API interceptors temporarily disabled for debugging')
		
		try {
			// 初始化离线存储
			await offlineStore.initOfflineStorage()
			console.log('离线存储初始化完成')
			logger.logAction('OFFLINE_STORAGE_INIT', { status: 'success' })
		} catch (error) {
			console.error('离线存储初始化失败:', error)
			logger.logError(error, { context: 'offline_storage_init' })
		}
		
		// 检查用户登录状态
		userStore.checkLoginStatus()
		
		// 如果有token，验证其有效性
		if (userStore.token) {
			logger.logAction('TOKEN_VALIDATION_START')
			const isValid = await userStore.validateToken()
			if (!isValid) {
				console.log('Token已过期，跳转到登录页')
				logger.logAction('TOKEN_EXPIRED_REDIRECT_TO_LOGIN')
				uni.reLaunch({
					url: '/pages/login/login'
				})
			} else {
				logger.logAction('TOKEN_VALIDATION_SUCCESS')
			}
		}
	})
	
	onShow(() => {
		console.log('App Show')
		console.log('⚠️ Logger calls temporarily disabled in onShow for debugging')
		// logger.logAction('APP_SHOW', {
		// 	timestamp: new Date().toISOString()
		// })
	})
	
	onHide(() => {
		console.log('App Hide')
		console.log('⚠️ Logger calls temporarily disabled in onHide for debugging')
		// logger.logAction('APP_HIDE', {
		// 	timestamp: new Date().toISOString()
		// })
	})
</script>

<style lang="scss">
	/* 全局样式 */
	page {
		background-color: #f5f5f5;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
	}
	
	/* 橙色主题色彩 */
	.primary-color { color: #f97316; }
	.primary-bg { background-color: #f97316; }
	.secondary-color { color: #fb923c; }
	.secondary-bg { background-color: #fb923c; }
	
	/* 通用按钮样式 */
	.btn-primary {
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
		border: none;
		border-radius: 8px;
		padding: 12px 24px;
		font-weight: 600;
		box-shadow: 0 2px 8px rgba(249, 115, 22, 0.3);
	}
	
	.btn-primary:active {
		transform: translateY(1px);
		box-shadow: 0 1px 4px rgba(249, 115, 22, 0.3);
	}
	
	/* 卡片样式 */
	.card {
		background: white;
		border-radius: 12px;
		padding: 16px;
		margin: 8px;
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
	}
	
	/* 输入框样式 */
	.input-field {
		background: #f8f9fa;
		border: 1px solid #e9ecef;
		border-radius: 8px;
		padding: 12px 16px;
		font-size: 16px;
	}
	
	.input-field:focus {
		border-color: #f97316;
		box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
	}
	
	/* 状态颜色 */
	.status-planning { color: #6b7280; }
	.status-construction { color: #f59e0b; }
	.status-operational { color: #10b981; }
	.status-maintenance { color: #ef4444; }
</style>