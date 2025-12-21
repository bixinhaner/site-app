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
	import { useUpgradeStore } from '@/stores/upgrade'
	import { initInterceptors } from '@/utils/api-interceptor'
	import { initLocationMode } from '@/utils/locationStrategy.js'
	// UpdateDialog已移至home.vue渲染，因为App.vue的template在UniApp App端不会渲染
	
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
	const upgradeStore = useUpgradeStore()

	const setAndroidNavigationBarWhite = () => {
		// #ifdef APP-PLUS
		try {
			const systemInfo = uni.getSystemInfoSync()
			if (systemInfo.platform !== 'android') return

			const mainActivity = plus.android.runtimeMainActivity()
			const window = mainActivity.getWindow()
			// 某些机型/运行态需要先 importClass 才能访问 window 方法
			try {
				plus.android.importClass(window)
			} catch (e) {
				// ignore
			}

			const Color = plus.android.importClass('android.graphics.Color')
			const navColor = Color.parseColor('#FFFFFF')
			if (window && typeof window.setNavigationBarColor === 'function') {
				window.setNavigationBarColor(navColor)
			} else {
				// 兜底：通过 invoke 反射调用，避免方法未挂载导致 TypeError
				try {
					plus.android.invoke(window, 'setNavigationBarColor', navColor)
				} catch (e) {
					console.warn('setNavigationBarColor 不支持或调用失败:', e)
				}
			}

			// Android 8.0+ 可设置导航栏按钮为深色（白底更清爽）
			try {
				const Build = plus.android.importClass('android.os.Build')
				if (Build.VERSION.SDK_INT >= 26) {
					const View = plus.android.importClass('android.view.View')
					const decorView = window.getDecorView()
					try {
						plus.android.importClass(decorView)
					} catch (e) {
						// ignore
					}
					const flags = decorView.getSystemUiVisibility()
					decorView.setSystemUiVisibility(flags | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR)
				}
			} catch (e) {
				// ignore
			}
		} catch (error) {
			console.warn('设置Android导航栏颜色失败:', error)
		}
		// #endif
	}
	
	onLaunch(async () => {
		console.log('🚀 App Launch - Start')
		
		// 初始化语言设置和底部导航栏文本
		languageStore.initLocale()
		console.log('语言设置初始化完成')
		
		// 暂时禁用日志功能，专注解决页面加载问题
		console.log('⚠️ Logger system temporarily disabled for debugging')
		
		// 暂时不初始化API拦截器
		console.log('⚠️ API interceptors temporarily disabled for debugging')
		
		// 初始化移动端定位模式（native / baidu），失败时默认使用 baidu
		try {
			await initLocationMode()
		} catch (error) {
			console.warn('初始化定位模式失败，将使用默认模式 baidu:', error)
		}
		
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

		// 设置 Android 底部导航栏为白色，修复底部黑边
		setAndroidNavigationBarWhite()
		
		// 全局版本检测（延迟执行，避免阻塞启动）
		// 检测后store会自动设置shouldShowDialog状态，由页面级组件处理弹窗显示
		// #ifdef APP-PLUS
		const checkVersionWithRetry = async () => {
			try {
				console.log('🔄 App启动：开始检测版本更新...')
				const hasUpdate = await upgradeStore.checkUpdate(true)
				// checkUpdate内部会自动设置shouldShowDialog状态
				return hasUpdate
			} catch (error) {
				console.warn('版本检测失败，5分钟后重试:', error)
				// 网络失败时5分钟后重试一次
				setTimeout(() => {
					console.log('🔄 重试版本检测...')
					upgradeStore.checkUpdate(true).catch(e => console.warn('重试版本检测失败:', e))
				}, 5 * 60 * 1000) // 5分钟
				return false
			}
		}
		setTimeout(checkVersionWithRetry, 2000)
		// #endif
	})
	
	onShow(() => {
		console.log('App Show')
		setAndroidNavigationBarWhite()
		
		// App从后台恢复时检测更新
		// #ifdef APP-PLUS
		const ONE_HOUR = 60 * 60 * 1000
		const lastCheck = upgradeStore.lastCheckTime || 0
		if (Date.now() - lastCheck > ONE_HOUR) {
			console.log('🔄 App恢复：距离上次检测超过1小时，重新检测版本更新...')
			upgradeStore.checkUpdate(true)
		}
		// #endif
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
		box-shadow: 0 2px 10px rgba(var(--color-primary-rgb), 0.26);
	}
	
	.btn-primary:active {
		transform: translateY(1px);
		box-shadow: 0 1px 6px rgba(var(--color-primary-rgb), 0.22);
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
		box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.12);
	}
	
	/* 状态颜色 */
	.status-planning { color: #6b7280; }
	.status-construction { color: #d97706; }
	.status-operational { color: var(--color-success); }
	.status-maintenance { color: var(--color-error); }
</style>
