<template>
	<view class="custom-tabbar">
		<view
      class="tab-item"
      v-for="(item, index) in visibleTabs"
      :key="index"
      :class="{ active: currentPath === item.pagePath }"
      @click="switchTab(item)"
    >
			<view class="tab-icon">
        <uni-icons
          :type="getIconType(item.icon)"
          :size="20"
          :color="currentPath === item.pagePath ? ACTIVE_COLOR : INACTIVE_COLOR"
        />
      </view>
			<text class="tab-text">{{ getTabText(item) }}</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, getCurrentInstance } from 'vue'
	import { useUserStore } from '@/stores/user'
	
	const userStore = useUserStore()
	const currentPath = ref('')

  const ALL_ROLES = ['admin', 'manager', 'inspector', 'surveyor', 'user']
  const ACTIVE_COLOR = 'var(--color-primary)'
  const INACTIVE_COLOR = '#9ca3af'

	// 所有标签页配置（使用图标名称，而非图片文件）
	const allTabs = [
		{
			pagePath: 'pages/home/home',
			icon: 'home',
			text: 'navigation.home',
			roles: ALL_ROLES
		},
		{
			pagePath: 'pages/site/list',
			icon: 'site',
			text: 'navigation.sites',
			roles: ALL_ROLES
		},
		{
			pagePath: 'pages/workorder/list',
			icon: 'workorder',
			text: 'navigation.inspection',
			roles: ALL_ROLES
		},
		{
			pagePath: 'pages/profile/profile',
			icon: 'profile',
			text: 'navigation.profile',
			roles: ALL_ROLES
		}
	]

	// 根据用户角色筛选可见标签页
	const visibleTabs = computed(() => {
		const userRole = userStore.userInfo?.role || 'user'
		return allTabs.filter(tab => tab.roles.includes(userRole))
	})

  // 将图标名称映射为 uni-icons 的 type
  const getIconType = (name) => {
    const map = {
      home: 'home-filled',
      site: 'location-filled',
      workorder: 'list',
      profile: 'person-filled',
    }
    return map[name] || 'circle'
  }
	
	// 获取标签文本
	const getTabText = (item) => {
		const { $t } = getCurrentInstance().appContext.config.globalProperties
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
		// 使用 reLaunch 模拟 tab 切换，不依赖原生 tabBar 图标
		uni.reLaunch({
			url: targetPath
		})
	}
</script>

<style scoped>
    .custom-tabbar {
        display: flex;
        background: rgba(255, 255, 255, 0.92);
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
        padding: 4px 0 6px;
        color: #9ca3af; /* 默认灰色文字 + 图标 */
        transition: color 0.2s ease, transform 0.2s ease;
        min-height: 48px;
    }
    
    .tab-item.active {
        color: var(--color-primary);
    }
    
    .tab-item.active .tab-icon {
        transform: scale(1.03);
    }
    
    .tab-icon {
        font-size: 18px;
        margin-bottom: 2px;
        line-height: 1;
    }
    
    .tab-text {
        font-size: 11px;
    }
</style>
