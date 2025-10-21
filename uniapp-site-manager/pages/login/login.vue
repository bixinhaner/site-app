<template>
	<view class="login-container">
		<!-- 语言切换按钮 -->
		<view class="language-switch">
			<text @click="toggleLanguage" class="language-btn">
				{{ languageStore.currentLanguageName }}
			</text>
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
					v-model="loginForm.username"
					:disabled="loading"
				/>
			</view>
			
			<view class="form-group">
				<input 
					class="input-field"
					type="password" 
					:placeholder="$t('login.password')"
					v-model="loginForm.password"
					:disabled="loading"
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
			
			<view class="support-text">
				<text>{{ $t('login.contactAdmin') }}</text>
			</view>
		</view>
		
		<!-- 版本信息 -->
		<view class="version-info">
			<text>{{ $t('login.version') }} 1.0.0</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, reactive, onMounted } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useLoggerStore } from '@/stores/logger'
	import { useLanguageStore } from '@/stores/language'
	
	const userStore = useUserStore()
	const logger = useLoggerStore()
	const languageStore = useLanguageStore()
	
	const loading = ref(false)
	const loginForm = reactive({
		username: '',
		password: ''
	})
	
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
				title: languageStore.isZh ? '请填写用户名和密码' : 'Please enter username and password',
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
					title: languageStore.isZh ? '登录成功' : 'Success',
					icon: 'success',
					duration: 1500
				})
				
				// 跳转到首页
				setTimeout(() => {
					// logger.logAction('LOGIN_REDIRECT_TO_HOME')
					uni.switchTab({
						url: '/pages/home/home'
					})
				}, 1500)
			} else {
				loading.value = false
				
				// 根据errorCode显示国际化错误信息
				let displayMessage = ''
				if (result?.errorCode) {
					const errorCodeMap = {
						'INVALID_CREDENTIALS': languageStore.isZh ? '用户名或密码错误' : 'Invalid username or password',
						'NETWORK_TIMEOUT': languageStore.isZh ? '请求超时，请检查网络连接' : 'Request timeout, please check your network connection',
						'NETWORK_FAIL': languageStore.isZh ? '网络连接失败，请检查服务器状态' : 'Network connection failed, please check server status',
						'NETWORK_ERROR': languageStore.isZh ? '网络错误' : 'Network error',
						'SERVER_ERROR': result?.error || (languageStore.isZh ? '服务器错误' : 'Server error')
					}
					displayMessage = errorCodeMap[result.errorCode] || (result?.error || (languageStore.isZh ? '登录失败，请重试' : 'Login failed, please try again'))
				} else {
					displayMessage = result?.error || (languageStore.isZh ? '登录失败，请重试' : 'Login failed, please try again')
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
				title: languageStore.isZh ? '登录异常，请重试' : 'Login error, please try again',
				icon: 'none',
				duration: 2000
			})
		}
	}
	
	// 切换语言
	const toggleLanguage = () => {
		languageStore.toggleLocale()
	}
	
	// 初始化语言
	onMounted(() => {
		languageStore.initLocale()
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
	
	.language-switch {
		position: absolute;
		top: 50px;
		right: 30px;
		z-index: 100;
	}
	
	.language-btn { background: rgba(255, 255, 255, 0.2); color: #fff; padding: 0 16px; min-height: 44px; display: inline-flex; align-items: center; border-radius: 22px; font-size: 14px; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.3); cursor: pointer; transition: all 0.3s ease; &:hover { background: rgba(255, 255, 255, 0.3); transform: scale(1.05); } &:active { transform: scale(0.95); } }
	
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
		
		&:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(249,115,22,0.12); background: #fff; }
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
		margin-bottom: 20px;
		transition: all 0.2s ease;
		box-sizing: border-box;
		box-shadow: 0 2px 10px rgba(249,115,22,0.28);
		
		&:not(:disabled):active { transform: translateY(1px); }
		&:disabled { opacity: 0.6; cursor: not-allowed; }
		&.loading { opacity: 0.8; }
	}
	
	.support-text { text-align: center; font-size: 14px; color: var(--text-secondary); }
	
	.version-info { position: absolute; bottom: 20px; font-size: 12px; color: rgba(255,255,255,0.7); }
</style>
