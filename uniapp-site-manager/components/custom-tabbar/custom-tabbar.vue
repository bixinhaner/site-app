<template>
	<view class="custom-tabbar">
		<view 
			class="tab-item"
			v-for="(item, index) in visibleTabs"
			:key="index"
			:class="{ active: currentPath === item.pagePath }"
			@click="switchTab(item)"
		>
			<view class="tab-icon">{{ item.icon }}</view>
			<text class="tab-text">{{ getTabText(item) }}</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { useUserStore } from '@/stores/user'
	
	const userStore = useUserStore()
	const currentPath = ref('')
	
	// 所有标签页配置
	const allTabs = [
		{
			pagePath: 'pages/home/home',
			icon: '🏠',
			text: '首页',
			roles: ['admin', 'manager', 'inspector'] // 所有角色可见
		},
		{
			pagePath: 'pages/site/list',
			icon: '📍',
			text: '站点',
			roles: ['admin'] // 只有管理员可以管理站点
		},
		{
			pagePath: 'pages/inspection/list',
			icon: '🔍',
			text: '检查',
			roles: ['admin', 'manager', 'inspector'] // 管理员、经理和检查员可见
		},
		{
			pagePath: 'pages/task/list',
			icon: '📋',
			text: '任务',
			roles: ['admin', 'manager', 'inspector'] // 管理员、经理可以管理任务，检查员可以查看自己的任务
		},
		{
			pagePath: 'pages/profile/profile',
			icon: '👤',
			text: '我的',
			roles: ['admin', 'manager', 'inspector'] // 所有角色可见
		}
	]
	
	// 根据用户角色筛选可见标签页
	const visibleTabs = computed(() => {
		const userRole = userStore.userInfo?.role || 'user'
		return allTabs.filter(tab => tab.roles.includes(userRole))
	})
	
	// 获取标签文本（根据用户角色调整）
	const getTabText = (item) => {
		const userRole = userStore.userInfo?.role
		
		// 为inspector角色调整特定标签的显示文本
		if (userRole === 'inspector') {
			if (item.pagePath === 'pages/task/list') {
				return '我的任务'
			}
		}
		
		return item.text
	}
	
	// 获取当前页面路径
	onMounted(() => {
		const pages = getCurrentPages()
		if (pages.length > 0) {
			currentPath.value = pages[pages.length - 1].route
		}
	})
	
	// 切换标签页
	const switchTab = (item) => {
		const targetPath = `/${item.pagePath}`
		uni.switchTab({
			url: targetPath
		})
	}
</script>

<style scoped>
	.custom-tabbar {
		display: flex;
		background: white;
		border-top: 1rpx solid #e5e5e5;
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		z-index: 1000;
		box-shadow: 0 -2rpx 10rpx rgba(0, 0, 0, 0.1);
	}
	
	.tab-item {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 10rpx 0 20rpx;
		color: #7a7e83;
		transition: color 0.2s;
	}
	
	.tab-item.active {
		color: #f97316;
	}
	
	.tab-icon {
		font-size: 44rpx;
		margin-bottom: 6rpx;
	}
	
	.tab-text {
		font-size: 20rpx;
	}
</style>