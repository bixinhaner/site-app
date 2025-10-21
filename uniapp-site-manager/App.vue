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
	import { useLanguageStore } from '@/stores/language'
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
	const languageStore = useLanguageStore()
	
	onLaunch(async () => {
		console.log('🚀 App Launch - Start')
		
		// 初始化语言设置和底部导航栏文本
		languageStore.initLocale()
		console.log('语言设置初始化完成')
		
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
		background-color: var(--bg-page);
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
		-webkit-font-smoothing: antialiased;
		-moz-osx-font-smoothing: grayscale;
		color: var(--text-primary);
	}
	
	/* 橙色主题色彩 */
	.primary-color { color: var(--color-primary); }
	.primary-bg { background-color: var(--color-primary); }
	.secondary-color { color: var(--color-primary-light); }
	.secondary-bg { background-color: var(--color-primary-light); }
	
	/* 通用按钮样式 */
	.btn-primary {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		color: #fff;
		border: none;
		border-radius: var(--radius-sm);
		padding: 12px 24px;
		font-weight: 600;
		box-shadow: 0 2px 10px rgba(249, 115, 22, 0.28);
	}
	
	.btn-primary:active {
		transform: translateY(1px);
		box-shadow: 0 1px 6px rgba(249, 115, 22, 0.24);
	}
	
	/* 卡片样式 */
	.card {
		background: var(--bg-elevated);
		border-radius: var(--radius-md);
		padding: 16px;
		margin: 8px;
		box-shadow: var(--shadow-card);
	}
	
	/* 输入框样式 */
	.input-field {
		background: #fafafa;
		border: 1px solid var(--border-color);
		border-radius: var(--radius-sm);
		padding: 12px 16px;
		font-size: 16px;
	}
	
	.input-field:focus {
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.12);
	}
	
	/* 状态颜色 */
	.status-planning { color: #6b7280; }
	.status-construction { color: #d97706; }
	.status-operational { color: var(--color-success); }
	.status-maintenance { color: var(--color-error); }
</style>