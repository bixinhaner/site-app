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
	
	const globalLoading = ref(false)
	const loadingText = ref({
		contentdown: '上拉显示更多',
		contentrefresh: '正在加载...',
		contentnomore: '没有更多数据了'
	})
	
	const userStore = useUserStore()
	const offlineStore = useOfflineStore()
	
	onLaunch(async () => {
		console.log('App Launch')
		
		try {
			// 初始化离线存储
			await offlineStore.initOfflineStorage()
			console.log('离线存储初始化完成')
		} catch (error) {
			console.error('离线存储初始化失败:', error)
		}
		
		// 检查用户登录状态
		userStore.checkLoginStatus()
		
		// 如果有token，验证其有效性
		if (userStore.token) {
			const isValid = await userStore.validateToken()
			if (!isValid) {
				console.log('Token已过期，跳转到登录页')
				uni.reLaunch({
					url: '/pages/login/login'
				})
			}
		}
	})
	
	onShow(() => {
		console.log('App Show')
	})
	
	onHide(() => {
		console.log('App Hide')
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