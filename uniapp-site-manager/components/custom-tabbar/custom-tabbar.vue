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
	import { ref, computed, onMounted, getCurrentInstance } from 'vue'
	import { useUserStore } from '@/stores/user'
	
	const userStore = useUserStore()
	const currentPath = ref('')
	
	// 所有标签页配置
	const allTabs = [
		{
			pagePath: 'pages/home/home',
			icon: '🏠',
			text: 'navigation.home',
			roles: ['admin', 'manager', 'inspector'] // 所有角色可见
		},
		{
			pagePath: 'pages/site/list',
			icon: '📍',
			text: 'navigation.sites',
			roles: ['admin', 'manager'] // 管理员与项目经理可管理站点
		},
		{
			pagePath: 'pages/inspection/list',
			icon: '🔍',
			text: 'navigation.inspection',
			roles: ['admin', 'manager', 'inspector'] // 管理员、经理和检查员可见
		},
		{
			pagePath: 'pages/task/list',
			icon: '📋',
			text: 'navigation.workorders',
			roles: ['admin', 'manager', 'inspector'] // 管理员、经理可以管理任务，检查员可以查看自己的任务
		},
		{
			pagePath: 'pages/profile/profile',
			icon: '👤',
			text: 'navigation.profile',
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
		const { $t } = getCurrentInstance().appContext.config.globalProperties
		const userRole = userStore.userInfo?.role
		
		// 为inspector角色调整特定标签的显示文本
		if (userRole === 'inspector') {
			if (item.pagePath === 'pages/task/list') {
				return $t('navigation.myTasks')
			}
		}
		
		return $t(item.text)
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
        background: rgba(255, 255, 255, 0.86);
        -webkit-backdrop-filter: saturate(180%) blur(12px);
        backdrop-filter: saturate(180%) blur(12px);
        border-top: 1px solid var(--border-soft);
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 1000;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.06);
        padding-bottom: env(safe-area-inset-bottom);
    }
    
    .tab-item {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 6px 0 10px;
        color: #7a7e83;
        transition: color 0.2s ease, transform 0.2s ease;
        min-height: 54px;
    }
    
    .tab-item.active {
        color: var(--color-primary);
    }
    
    .tab-item.active .tab-icon {
        transform: scale(1.05);
    }
    
    .tab-icon {
        font-size: 22px;
        margin-bottom: 4px;
    }
    
    .tab-text {
        font-size: 12px;
    }
</style>
