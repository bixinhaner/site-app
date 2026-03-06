<template>
	<view class="login-container">
		<view v-if="showMenuMask" class="server-mask" @click="closeAllMenus"></view>

		<!-- 右上角：服务器切换 + 语言切换 -->
		<view class="top-actions" :style="{ top: topActionsOffset + 'px' }">
			<view class="server-wrapper">
				<view class="server-btn" @click.stop="toggleServerMenu">
					<image class="flag-icon" :src="currentServer.flagIcon" mode="aspectFit" />
				</view>
				
				<view v-if="showServerMenu" class="server-menu" @click.stop>
					<view
						v-for="server in otherServers"
						:key="server.key"
						class="server-option"
						@click="handleServerSelect(server)"
					>
						<image class="flag-icon" :src="server.flagIcon" mode="aspectFit" />
					</view>
				</view>
			</view>
			
			<view class="language-wrapper">
				<text class="language-btn" @click.stop="toggleLanguageMenu">{{ languageStore.currentLanguageName }}</text>

				<view v-if="showLanguageMenu" class="language-menu" @click.stop>
					<view
						v-for="lang in otherLanguages"
						:key="lang.code"
						class="language-option"
						@click="handleLanguageSelect(lang.code)"
					>
						<text>{{ lang.name }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<view class="login-header">
			<view class="logo">
				<text class="logo-text">{{ $t('login.title') }}</text>
			</view>
			<text class="subtitle">{{ $t('login.subtitle') }}</text>
		</view>
		
		<view class="login-form">
			<view class="form-group">
				<input 
					class="input-field"
					type="text" 
					:placeholder="$t('login.username')"
					v-model.trim="loginForm.username"
					:disabled="loading"
					confirm-type="next"
				/>
			</view>
			
			<view class="form-group">
				<input 
					class="input-field"
					type="password" 
					:placeholder="$t('login.password')"
					v-model.trim="loginForm.password"
					:disabled="loading"
					confirm-type="done"
					@confirm="handleLogin"
				/>
			</view>
			
			<button 
				class="login-btn"
				:class="{ 'loading': loading }"
				@click="handleLogin"
				:disabled="loading || !loginForm.username || !loginForm.password"
			>
				{{ loading ? $t('login.loggingIn') : $t('login.loginBtn') }}
			</button>
			
			<!-- 记住密码开关 -->
			<view class="remember-password" @click="rememberPassword = !rememberPassword">
				<view class="checkbox" :class="{ 'checked': rememberPassword }">
					<text v-if="rememberPassword" class="check-icon">✓</text>
				</view>
				<text class="remember-text">{{ $t('login.rememberPassword') }}</text>
			</view>
			
			<view class="support-text">
				<text>{{ $t('login.contactAdmin') }}</text>
			</view>
		</view>
		
		<!-- 版本信息 -->
		<view class="version-info">
			<text>{{ $t('login.version') }} {{ appVersion }}</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, reactive, onMounted, getCurrentInstance, computed } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useLoggerStore } from '@/stores/logger'
	import { useLanguageStore } from '@/stores/language'
	import { env, getVersion } from '@/config/env.js'
		import { API_SERVERS, getApiBaseUrl, normalizeApiBaseUrlForMatch, setApiBaseUrl } from '@/config/api.js'
	
	const userStore = useUserStore()
	const logger = useLoggerStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	
	const loading = ref(false)
	const appVersion = ref(env.APP_VERSION)
	const rememberPassword = ref(false)
	const showServerMenu = ref(false)
	const showLanguageMenu = ref(false)
	const currentBaseUrl = ref(getApiBaseUrl())
	const topActionsOffset = ref(16)
	
		const currentServer = computed(() => {
			const baseUrl = currentBaseUrl.value
			const normalized = normalizeApiBaseUrlForMatch(baseUrl)
			const hit = (API_SERVERS || []).find(s => normalizeApiBaseUrlForMatch(s.baseUrl) === normalized)
			return hit || API_SERVERS[0]
		})
	
	const otherServers = computed(() => {
		const currentKey = currentServer.value?.key
		return (API_SERVERS || []).filter(s => s.key !== currentKey)
	})

	const otherLanguages = computed(() => {
		const currentLocale = languageStore.currentLocale
		return (languageStore.supportedLocales || []).filter(l => l.code !== currentLocale)
	})

	const showMenuMask = computed(() => showServerMenu.value || showLanguageMenu.value)
	
	const loginForm = reactive({
		username: '',
		password: ''
	})

	const LOGIN_ERROR_KEY_MAP = {
		INVALID_CREDENTIALS: 'messages.invalidCredentials',
		'Incorrect username or password': 'messages.invalidCredentials',
		ACCOUNT_DISABLED: 'messages.accountDisabled',
		'Account disabled': 'messages.accountDisabled',
		WEB_LOGIN_FORBIDDEN: 'messages.webLoginForbidden',
		APP_LOGIN_FORBIDDEN: 'messages.appLoginForbidden',
		PERMISSION_DENIED: 'messages.permissionDenied',
	}
	
	const toggleServerMenu = () => {
		showLanguageMenu.value = false
		showServerMenu.value = !showServerMenu.value
	}

	const closeServerMenu = () => {
		showServerMenu.value = false
	}

	const toggleLanguageMenu = () => {
		closeServerMenu()
		showLanguageMenu.value = !showLanguageMenu.value
	}

	const closeAllMenus = () => {
		showServerMenu.value = false
		showLanguageMenu.value = false
	}
	
	const clearServerSensitiveStorage = () => {
		try {
			// 认证信息
			uni.removeStorageSync('token')
			uni.removeStorageSync('refreshToken')
			uni.removeStorageSync('userInfo')
			
			// 离线队列/数据
			uni.removeStorageSync('offlineQueue')
			
			// 日志队列
			uni.removeStorageSync('user_logs')
			
			// 批量清理前缀 key
			const keys = uni.getStorageInfoSync?.()?.keys || []
			const prefixes = [
				'mobile_client_log_queue_v1',
				'inspection_',
				'checkitem_',
				'photo_'
			]
			
			keys.forEach((key) => {
				if (prefixes.some(prefix => key.startsWith(prefix))) {
					uni.removeStorageSync(key)
				}
			})
			
			// H5 可能存在 IndexedDB（失败不影响）
			try {
				if (typeof indexedDB !== 'undefined' && typeof indexedDB.deleteDatabase === 'function') {
					indexedDB.deleteDatabase('SiteInspectionDB')
				}
			} catch (e) {
				// ignore
			}
		} catch (e) {
			// ignore
		}
	}
	
	const handleServerSelect = (server) => {
		try {
			if (!server?.baseUrl) return
			
			const next = server.baseUrl
			const current = currentBaseUrl.value
			if (next === current) {
				closeAllMenus()
				return
			}
			
			// 切换服务器前先清理跨服数据（保留 savedCredentials）
			clearServerSensitiveStorage()
			
			setApiBaseUrl(next)
			currentBaseUrl.value = getApiBaseUrl()
			
			closeAllMenus()
			
			uni.showToast({
				title: $t('messages.serverSwitched'),
				icon: 'none',
				duration: 2000
			})
		} catch (e) {
			closeAllMenus()
		}
	}
	
	// 读取保存的登录凭据
	const loadSavedCredentials = () => {
		try {
			const saved = uni.getStorageSync('savedCredentials')
			if (saved) {
				loginForm.username = saved.username || ''
				loginForm.password = saved.password || ''
				rememberPassword.value = true
				console.log('🔑 已加载保存的登录凭据')
			}
		} catch (e) {
			console.warn('加载保存的登录凭据失败:', e)
		}
	}
	
	// 保存登录凭据
	const saveCredentials = () => {
		try {
			if (rememberPassword.value) {
				uni.setStorageSync('savedCredentials', {
					username: loginForm.username,
					password: loginForm.password
				})
				console.log('💾 已保存登录凭据')
			} else {
				// 如果取消记住密码，则清除保存的凭据
				uni.removeStorageSync('savedCredentials')
				console.log('🗑️ 已清除保存的登录凭据')
			}
		} catch (e) {
			console.warn('保存登录凭据失败:', e)
		}
	}
	
	// 页面加载时记录日志
	onMounted(() => {
		console.log('🏠 Login page onMounted called')
		console.log('⚠️ Logger calls temporarily disabled for debugging')
		// try {
		// 	console.log('📊 Calling logger.logPageView...')
		// 	logger.logPageView('/pages/login/login')
		// 	console.log('✅ logPageView completed')
		// 	
		// 	console.log('📊 Calling logger.logAction...')
		// 	logger.logAction('LOGIN_PAGE_LOADED')
		// 	console.log('✅ LOGIN_PAGE_LOADED action completed')
		// } catch (error) {
		// 	console.error('❌ Error in login page onMounted:', error)
		// }
		
		// 加载保存的登录凭据
		loadSavedCredentials()
		
		// 初始化当前服务器（用于显示国旗）
		currentBaseUrl.value = getApiBaseUrl()
		
		// 适配状态栏高度，避免右上角按钮遮挡
		try {
			const sysInfo = uni.getSystemInfoSync?.()
			const statusBarHeight = Number(sysInfo?.statusBarHeight || 0)
			topActionsOffset.value = statusBarHeight > 0 ? (statusBarHeight + 12) : 16
		} catch (e) {
			topActionsOffset.value = 16
		}
	})
	
	// 处理登录
	const handleLogin = async () => {
		console.log('🔑 开始登录流程...', {
			username: loginForm.username,
			hasPassword: !!loginForm.password
		})
		
		if (!loginForm.username || !loginForm.password) {
			console.log('❌ 验证失败：用户名或密码为空')
			uni.showToast({
				title: $t('messages.usernamePasswordRequired'),
				icon: 'none'
			})
			return
		}
		
		loading.value = true
		console.log('⏰ 设置loading状态为true')
		
		const startTime = Date.now()
		
		try {
			console.log('📡 调用userStore.login...')
			const result = await userStore.login(loginForm.username, loginForm.password)
			const responseTime = Date.now() - startTime
			console.log('📥 登录结果:', result, '响应时间:', responseTime + 'ms')
			
			// 确保result存在并且有expected属性
			if (result && result.success) {
				// logger.logAction('LOGIN_SUCCESS', {
				// 	username: loginForm.username,
				// 	responseTime,
				// 	userRole: userStore.userInfo?.role
				// })
				
				uni.showToast({
					title: $t('messages.loginSuccess'),
					icon: 'success',
					duration: 1500
				})
				
				// 保存登录凭据（根据用户选择）
				saveCredentials()
				
				// 跳转到首页（自定义底部导航，使用 reLaunch 作为入口）
				setTimeout(() => {
					uni.reLaunch({
						url: '/pages/home/home'
					})
				}, 1500)
			} else {
				loading.value = false
				
				// 根据errorCode显示国际化错误信息
				let displayMessage = ''
				if (result?.errorCode) {
					const errorCodeKeyMap = {
						...LOGIN_ERROR_KEY_MAP,
						INVALID_CREDENTIALS: 'messages.invalidCredentials',
						NETWORK_TIMEOUT: 'messages.networkTimeout',
						NETWORK_FAIL: 'messages.networkFail',
						NETWORK_ERROR: 'messages.networkError',
						SERVER_ERROR: 'messages.loginFailed',
					}
					const key = errorCodeKeyMap[result.errorCode]
					displayMessage = (key ? $t(key) : '') || result?.error || $t('messages.loginFailed')
				} else {
					displayMessage = result?.error || $t('messages.loginFailed')
				}
				
				// logger.logAction('LOGIN_FAILED', {
				// 	username: loginForm.username,
				// 	error: displayMessage,
				// 	errorCode: result?.errorCode,
				// 	responseTime,
				// 	resultUndefined: !result
				// })
				
				uni.showToast({
					title: displayMessage,
					icon: 'none',
					duration: 2000
				})
			}
		} catch (error) {
			loading.value = false
			const responseTime = Date.now() - startTime
			
			// logger.logError(error, {
			// 	context: 'login_process',
			// 	username: loginForm.username,
			// 	responseTime
			// })
			
			console.error('登录异常:', error)
			uni.showToast({
				title: $t('messages.loginFailed'),
				icon: 'none',
				duration: 2000
			})
		}
	}
	
	const handleLanguageSelect = async (locale) => {
		try {
			await languageStore.setLocale(locale)
		} finally {
			closeAllMenus()
		}
	}
	
	// 初始化语言和版本号
	onMounted(() => {
		languageStore.initLocale()
		
		// 动态获取版本号（延迟确保plus已完全初始化）
		// #ifdef APP-PLUS
		setTimeout(() => {
			const version = getVersion()
			console.log('📱 Login页获取到App版本号:', version)
			appVersion.value = version
		}, 100)
		// #endif
		// #ifndef APP-PLUS
		appVersion.value = getVersion()
		// #endif
	})
</script>

<style lang="scss" scoped>
	.login-container {
		min-height: 100vh;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 40px 20px;
		position: relative;
	}
	
	.top-actions {
		position: absolute;
		top: 16px;
		right: 30px;
		z-index: 100;
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.server-mask {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		left: 0;
		background: transparent;
		z-index: 90;
	}
	
	.language-btn {
		background: rgba(255, 255, 255, 0.22);
		color: #fff;
		padding: 0 16px;
		min-height: 44px;
		display: inline-flex;
		align-items: center;
		border-radius: 22px;
		font-size: 14px;
		border: 1px solid rgba(255, 255, 255, 0.32);
		transition: transform 0.15s ease, background-color 0.2s ease, opacity 0.2s ease;
		
		&:active {
			transform: scale(0.96);
			background: rgba(255, 255, 255, 0.28);
		}
	}

	.language-wrapper { position: relative; }

	.language-menu {
		position: absolute;
		top: 52px;
		right: 0;
		background: transparent;
		border: none;
		border-radius: 0;
		backdrop-filter: none;
	}

	.language-option {
		min-height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0 16px;
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.22);
		border: 1px solid rgba(255, 255, 255, 0.32);
		color: #fff;
		font-size: 14px;
		white-space: nowrap;

		&:active {
			transform: scale(0.96);
			background: rgba(255, 255, 255, 0.28);
		}
	}
	
	.server-wrapper { position: relative; }
	
	.server-btn {
		width: 44px;
		height: 44px;
		border-radius: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.22);
		border: 1px solid rgba(255, 255, 255, 0.32);
		transition: transform 0.15s ease, background-color 0.2s ease, opacity 0.2s ease;
		
		&:active {
			transform: scale(0.96);
			background: rgba(255, 255, 255, 0.28);
		}
	}
	
	.flag-icon {
		width: 26px;
		height: 18px;
		border-radius: 3px;
		overflow: hidden;
	}
	
	.server-menu {
		position: absolute;
		top: 52px;
		right: 0;
		padding: 0;
		background: transparent;
		border: none;
		border-radius: 0;
		backdrop-filter: none;
	}
	
	.server-option {
		width: 44px;
		height: 44px;
		border-radius: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.22);
		border: 1px solid rgba(255, 255, 255, 0.32);
		
		&:active {
			transform: scale(0.96);
			background: rgba(255, 255, 255, 0.28);
		}
	}
	
	.login-header {
		text-align: center;
		margin-bottom: 60px;
	}
	
	.logo {
		margin-bottom: 16px;
	}
	
	.logo-text { font-size: 32px; font-weight: bold; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
	
	.subtitle { font-size: 16px; color: rgba(255, 255, 255, 0.9); }
	
	.login-form {
		width: 100%;
		max-width: 320px;
		background: var(--bg-elevated);
		border-radius: var(--radius-lg);
		padding: 32px 24px;
		box-shadow: var(--shadow-soft);
	}
	
	.form-group {
		margin-bottom: 20px;
	}
	
	.input-field {
		width: 100%;
		height: 48px;
		padding: 0 16px;
		border: 1px solid var(--border-color);
		border-radius: var(--radius-sm);
		font-size: 16px;
		transition: all 0.3s ease;
		box-sizing: border-box;
		background: #fafafa;
		
		&:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.12); background: #fff; }
		&:disabled { background-color: #f9fafb; color: #6b7280; }
	}
	
	.login-btn {
		width: 100%;
		height: 48px;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		color: #fff;
		border: none;
		border-radius: var(--radius-sm);
		font-size: 16px;
		font-weight: 600;
		margin-bottom: 16px;
		transition: all 0.2s ease;
		box-sizing: border-box;
		box-shadow: 0 2px 10px rgba(var(--color-primary-rgb), 0.26);
		
		&:not(:disabled):active { transform: translateY(1px); }
		&:disabled { opacity: 0.6; cursor: not-allowed; }
		&.loading { opacity: 0.8; }
	}
	
	.remember-password {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		margin-bottom: 20px;
		
		.checkbox {
			width: 22px;
			height: 22px;
			border: 2px solid #d1d5db;
			border-radius: 4px;
			display: flex;
			align-items: center;
			justify-content: center;
			transition: all 0.2s ease;
			background: #fff;
			
			&.checked {
				background: var(--color-primary);
				border-color: var(--color-primary);
			}
			
			.check-icon {
				color: #fff;
				font-size: 14px;
				font-weight: 700;
			}
		}
		
		.remember-text {
			color: #6b7280;
			font-size: 14px;
		}
	}
	
	.support-text { text-align: center; font-size: 14px; color: var(--text-secondary); }
	
	.version-info { position: absolute; bottom: 20px; font-size: 12px; color: rgba(255,255,255,0.7); }
</style>
