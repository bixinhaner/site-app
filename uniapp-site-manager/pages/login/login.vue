<template>
	<view class="login-container">
		<view class="login-header">
			<view class="logo">
				<text class="logo-text">站点管理</text>
			</view>
			<text class="subtitle">现代化的站点信息管理系统</text>
		</view>
		
		<view class="login-form">
			<view class="form-group">
				<input 
					class="input-field"
					type="text" 
					placeholder="用户名"
					v-model="loginForm.username"
					:disabled="loading"
				/>
			</view>
			
			<view class="form-group">
				<input 
					class="input-field"
					type="password" 
					placeholder="密码"
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
				{{ loading ? '登录中...' : '登录' }}
			</button>
			
			<view class="register-link">
				<text>还没有账号？</text>
				<text class="link" @click="goToRegister">立即注册</text>
			</view>
		</view>
		
		<!-- 版本信息 -->
		<view class="version-info">
			<text>版本 1.0.0</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, reactive } from 'vue'
	import { useUserStore } from '@/stores/user'
	
	const userStore = useUserStore()
	
	const loading = ref(false)
	const loginForm = reactive({
		username: '',
		password: ''
	})
	
	// 处理登录
	const handleLogin = async () => {
		if (!loginForm.username || !loginForm.password) {
			uni.showToast({
				title: '请填写用户名和密码',
				icon: 'none'
			})
			return
		}
		
		loading.value = true
		
		try {
			const result = await userStore.login(loginForm.username, loginForm.password)
			
			if (result.success) {
				uni.showToast({
					title: '登录成功',
					icon: 'success'
				})
				
				// 跳转到首页
				setTimeout(() => {
					uni.switchTab({
						url: '/pages/home/home'
					})
				}, 1500)
			} else {
				loading.value = false // 登录失败时立即解除loading状态
				uni.showToast({
					title: result.error || '登录失败',
					icon: 'none',
					duration: 2000
				})
			}
		} catch (error) {
			loading.value = false // 发生异常时立即解除loading状态
			console.error('登录异常:', error)
			uni.showToast({
				title: '登录异常，请重试',
				icon: 'none',
				duration: 2000
			})
		}
	}
	
	// 跳转到注册页
	const goToRegister = () => {
		uni.showModal({
			title: '注册功能',
			content: '注册功能正在开发中，请联系管理员获取账号',
			showCancel: false
		})
	}
</script>

<style lang="scss" scoped>
	.login-container {
		min-height: 100vh;
		background: linear-gradient(135deg, #f97316, #fb923c);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 40px 20px;
	}
	
	.login-header {
		text-align: center;
		margin-bottom: 60px;
	}
	
	.logo {
		margin-bottom: 16px;
	}
	
	.logo-text {
		font-size: 32px;
		font-weight: bold;
		color: white;
		text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
	}
	
	.subtitle {
		font-size: 16px;
		color: rgba(255, 255, 255, 0.9);
	}
	
	.login-form {
		width: 100%;
		max-width: 320px;
		background: white;
		border-radius: 16px;
		padding: 32px 24px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
	}
	
	.form-group {
		margin-bottom: 20px;
	}
	
	.input-field {
		width: 100%;
		height: 48px;
		padding: 0 16px;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		font-size: 16px;
		transition: all 0.3s ease;
		box-sizing: border-box;
		
		&:focus {
			border-color: #f97316;
			box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
		}
		
		&:disabled {
			background-color: #f9fafb;
			color: #6b7280;
		}
	}
	
	.login-btn {
		width: 100%;
		height: 48px;
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
		border: none;
		border-radius: 8px;
		font-size: 16px;
		font-weight: 600;
		margin-bottom: 20px;
		transition: all 0.3s ease;
		box-sizing: border-box;
		
		&:not(:disabled):active {
			transform: translateY(1px);
		}
		
		&:disabled {
			opacity: 0.6;
			cursor: not-allowed;
		}
		
		&.loading {
			opacity: 0.8;
		}
	}
	
	.register-link {
		text-align: center;
		font-size: 14px;
		color: #6b7280;
	}
	
	.link {
		color: #f97316;
		margin-left: 8px;
	}
	
	.version-info {
		position: absolute;
		bottom: 20px;
		font-size: 12px;
		color: rgba(255, 255, 255, 0.7);
	}
</style>