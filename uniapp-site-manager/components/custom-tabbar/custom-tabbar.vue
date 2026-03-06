<template>
	<view class="custom-tabbar">
		<view
      class="tab-item u-pressable-subtle"
      v-for="(item, index) in visibleTabs"
      :key="index"
      :class="{ active: currentPath === item.pagePath }"
      @click="switchTab(item)"
    >
			<view class="tab-icon-wrapper">
        <uni-icons
          :type="getIconType(item.icon)"
          :size="20"
          :color="currentPath === item.pagePath ? ACTIVE_COLOR : INACTIVE_COLOR"
        />
        <!-- 角标 -->
        <view 
          v-if="getBadgeCount(item.icon) > 0" 
          class="tab-badge"
          :class="{ 'tab-badge-dot': getBadgeCount(item.icon) > 99 }"
        >
          <text class="badge-text" v-if="getBadgeCount(item.icon) <= 99">
            {{ getBadgeCount(item.icon) }}
          </text>
        </view>
      </view>
			<text class="tab-text">{{ getTabText(item) }}</text>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, getCurrentInstance, watch } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useWorkOrderStore } from '@/stores/workorder'
		
	const userStore = useUserStore()
	const workOrderStore = useWorkOrderStore()
	const currentPath = ref('')
  const ACTIVE_COLOR = 'var(--color-primary)'
  const INACTIVE_COLOR = '#9ca3af'

	// 所有标签页配置（使用图标名称，而非图片文件）
		const allTabs = [
			{
				pagePath: 'pages/home/home',
				icon: 'home',
				text: 'navigation.home',
				feature: 'home',
			},
			{
				pagePath: 'pages/site/list',
				icon: 'site',
				text: 'navigation.sites',
				feature: 'sites',
			},
			{
				pagePath: 'pages/workorder/list',
				icon: 'workorder',
				text: 'navigation.workorders',
				feature: 'workorders',
			},
			{
				pagePath: 'pages/profile/profile',
				icon: 'profile',
				text: 'navigation.profile',
				feature: 'profile',
			}
		]

		// 根据权限筛选可见标签页
		const visibleTabs = computed(() => {
			return allTabs.filter(tab => !tab.feature || userStore.can(tab.feature))
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
	
	// 获取角标数量
	const getBadgeCount = (icon) => {
		if (icon === 'workorder') {
			// 返回待处理工单数量（PENDING + ACTIVE 状态）
			return pendingWorkOrderCount.value
		}
		return 0
	}
	
	// 待处理工单数量
	const pendingWorkOrderCount = computed(() => {
		const list = workOrderStore.list || []
		return list.filter(wo => 
			['PENDING', 'ACTIVE', 'ASSIGNED', 'IN_PROGRESS', 'ACCEPTED'].includes(wo.status)
		).length
	})
	
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
        background: rgba(255, 255, 255, 0.98);
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
    
    .tab-item.active .tab-icon-wrapper {
        transform: scale(1.03);
    }
    
    .tab-icon-wrapper {
        position: relative;
        font-size: 18px;
        margin-bottom: 2px;
        line-height: 1;
    }
    
    .tab-badge {
        position: absolute;
        top: -6px;
        right: -10px;
        min-width: 16px;
        height: 16px;
        padding: 0 4px;
        background: var(--color-error);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1.5px solid #fff;
    }
    
    .tab-badge-dot {
        width: 8px;
        height: 8px;
        min-width: 8px;
        padding: 0;
    }
    
    .badge-text {
        font-size: 10px;
        font-weight: 600;
        color: #fff;
        line-height: 1;
    }
    
    .tab-text {
        font-size: 11px;
    }
</style>
