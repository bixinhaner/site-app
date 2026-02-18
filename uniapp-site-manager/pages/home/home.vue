<template>
	<view class="home-container" :key="languageStore.currentLocale">
		<!-- 自定义导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<text class="navbar-title">{{ $t('home.title') }}</text>
				<view class="user-info" @click="showUserMenu">
					<text class="user-name">{{ userStore.userInfo?.full_name || userStore.userInfo?.username }}</text>
					<view class="avatar">
						<text class="avatar-text">{{ getAvatarText() }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 滚动容器支持下拉刷新 -->
		<scroll-view 
			class="home-scroll" 
			scroll-y 
			refresher-enabled 
			:refresher-triggered="refreshing" 
			@refresherrefresh="handleRefresh"
		refresher-background="#f7f8fb"
		>
		
		<!-- 统计卡片 -->
		<view class="stats-container">
			<view class="stats-grid">
				<!-- 骨架屏加载状态 -->
				<template v-if="isLoading">
					<SkeletonCard mode="stat" />
					<SkeletonCard mode="stat" />
					<SkeletonCard mode="stat" v-if="canViewStats" />
					<SkeletonCard mode="stat" v-if="canViewStats" />
				</template>
				
				<!-- 实际内容 -->
				<template v-else>
					<!-- 管理员和经理能查看和管理站点，现场工程师只能查看自己的站点 -->
					<view class="stat-card u-pressable" @click="goToSites">
						<view class="stat-icon site-icon">📍</view>
						<view class="stat-info">
							<text class="stat-number">{{ siteStats.total }}</text>
							<text class="stat-label">{{ $t('home.totalSites') }}</text>
						</view>
					</view>
					
					<!-- 所有角色都能查看检查 -->
					<view class="stat-card u-pressable" @click="goToWorkOrders">
						<view class="stat-icon inspection-icon">🔍</view>
						<view class="stat-info">
							<text class="stat-number">{{ workOrderStats.assigned + workOrderStats.in_progress + workOrderStats.submitted }}</text>
							<text class="stat-label">{{ $t('home.myWorkOrders') }}</text>
						</view>
					</view>

					<!-- 管理员和经理可以看站点状态统计 -->
					<view class="stat-card" v-if="canViewStats">
						<view class="stat-icon operational-icon">✅</view>
						<view class="stat-info">
							<text class="stat-number">{{ siteStats.operational }}</text>
							<text class="stat-label">{{ $t('site.operational') }}</text>
						</view>
					</view>

					<view class="stat-card" v-if="canViewStats">
						<view class="stat-icon maintenance-icon">⚠️</view>
						<view class="stat-info">
							<text class="stat-number">{{ siteStats.maintenance }}</text>
							<text class="stat-label">{{ $t('site.maintenance') }}</text>
						</view>
					</view>

					<!-- 现场工程师显示活跃工单 -->
					<view class="stat-card u-pressable" v-if="isInspector || isSurveyor" @click="goToWorkOrders">
						<view class="stat-icon inspection-icon">📋</view>
						<view class="stat-info">
							<text class="stat-number">{{ workOrderStats.assigned }}</text>
							<text class="stat-label">{{ $t('home.activeWorkOrders') }}</text>
						</view>
					</view>
				</template>
				
			</view>
		</view>
		
		<!-- 快捷操作 -->
		<view class="quick-actions">
			<view class="section-header">
				<text class="section-title">{{ $t('home.dashboard') }}</text>
			</view>
			
			<view class="actions-grid">
				<!-- 骨架屏加载状态 -->
				<template v-if="isLoading">
					<SkeletonCard mode="action" />
					<SkeletonCard mode="action" />
					<SkeletonCard mode="action" />
					<SkeletonCard mode="action" />
				</template>
				
				<!-- 实际内容 -->
				<template v-else>
					<!-- 所有角色都能进行现场检查 -->
					<view class="action-item u-pressable" @click="goToNewInspection">
						<view class="action-icon">📷</view>
						<text class="action-label">{{ $t('inspection.title') }}</text>
					</view>
					
					<!-- 所有角色都能查看站点列表 -->
					<view class="action-item u-pressable" @click="goToSiteList">
						<view class="action-icon">📋</view>
						<text class="action-label">{{ $t('site.list') }}</text>
					</view>
					
					<!-- 我的设备 - 管理员/经理/检查员可用，勘察员不可用 -->
					<view class="action-item u-pressable" v-if="!isSurveyor" @click="goToScanPickup">
						<view class="action-icon">📦</view>
						<text class="action-label">{{ $t('stock.scanPickup') }}</text>
					</view>

					<!-- 物料申请（新流程） - 勘察员不可用 -->
					<view class="action-item u-pressable" v-if="!isSurveyor" @click="goToMaterialRequests">
						<view class="action-icon">🧾</view>
						<text class="action-label">{{ $t('stock.materialRequestEntry') }}</text>
					</view>

					<!-- 物料审批 - 仓库角色 -->
					<view class="action-item u-pressable" v-if="isWarehouseSide" @click="goToMaterialApprovalList">
						<view class="action-icon">✅</view>
						<text class="action-label">{{ $t('stock.materialApprovalEntry') }}</text>
					</view>

					<!-- 出库确认 - 仓库角色 -->
					<view class="action-item u-pressable" v-if="isWarehouseSide" @click="goToIssueConfirmList">
						<view class="action-icon">📤</view>
						<text class="action-label">{{ $t('stock.issueConfirmEntry') }}</text>
					</view>

					<!-- 退库申请（新流程） - 勘察员不可用 -->
					<view class="action-item u-pressable" v-if="!isSurveyor" @click="goToReturnRequests">
						<view class="action-icon">↩️</view>
						<text class="action-label">{{ $t('stock.returnEntry') }}</text>
					</view>

					<!-- 快速出库（无申请） - 仅管理员/经理 -->
					<view class="action-item u-pressable" v-if="isAdmin || isManager" @click="goToManualStockOut">
						<view class="action-icon">🚚</view>
						<text class="action-label">{{ $t('stock.manualStockOutTitle') }}</text>
					</view>
					
					<!-- 公共功能 -->
					<view class="action-item u-pressable" @click="goToMap">
						<view class="action-icon">🗺️</view>
						<text class="action-label">{{ $t('site.location') }}</text>
					</view>
				</template>
			</view>
		</view>
		
		<!-- 最近活动 -->
		<view class="recent-activities">
			<view class="section-header">
				<text class="section-title">{{ $t('home.recentActivities') }}</text>
				<text class="see-all" @click="goToWorkOrders">{{ $t('common.viewAll') }}</text>
			</view>
			
			<view class="activity-list">
				<!-- 骨架屏加载状态 -->
				<template v-if="isLoading">
					<SkeletonCard mode="activity" />
					<SkeletonCard mode="activity" />
					<SkeletonCard mode="activity" />
				</template>
				
				<!-- 空状态 -->
				<EmptyState 
					v-else-if="recentActivities.length === 0"
					icon="📋"
					:title="$t('messages.noData')"
					:description="$t('home.noRecentActivities')"
					:compact="true"
				/>
				
				<!-- 实际内容 -->
				<template v-else>
					<view 
						class="activity-item u-pressable-subtle" 
						v-for="activity in recentActivities" 
						:key="activity.id"
						@click="viewActivity(activity)"
					>
						<view class="activity-icon" :class="getActivityIconClass(activity.type)">
							{{ getActivityIcon(activity.type) }}
						</view>
						<view class="activity-content">
							<text class="activity-title">{{ activity.title }}</text>
							<text class="activity-time">{{ formatTime(activity.created_at) }}</text>
						</view>
						<view class="activity-status" :class="getStatusClass(activity.status)">
							{{ getStatusText(activity.status) }}
						</view>
					</view>
				</template>
			</view>
		</view>

		<!-- 预留底部空间，避免内容被自定义 tabbar 遮挡 -->
		<view class="tabbar-spacer" />
		
		</scroll-view>
		<!-- 自定义底部导航栏（替代原生 tabBar 图标） -->
		<custom-tabbar />
		
		<!-- 版本更新弹窗 -->
		<UpdateDialog 
			v-model:visible="showUpdateDialog"
			@close="handleDialogClose"
			@installed="handleUpdateInstalled"
		/>
	</view>
</template>

<script setup>
	import { ref, reactive, computed, onMounted, watch, getCurrentInstance } from 'vue'
	import { onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useWorkOrderStore } from '@/stores/workorder'
	import { useLoggerStore } from '@/stores/logger'
	import { useLanguageStore } from '@/stores/language'
	import { useUpgradeStore } from '@/stores/upgrade'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { formatTimeAgo } from '@/utils/time.js'
	import SkeletonCard from '@/components/SkeletonCard.vue'
	import EmptyState from '@/components/EmptyState.vue'
	import UpdateDialog from '@/components/UpdateDialog.vue'
	
	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const workOrderStore = useWorkOrderStore()
	const logger = useLoggerStore()
	const languageStore = useLanguageStore()
	const upgradeStore = useUpgradeStore()
	
	// 版本更新弹窗显示状态（与store同步）
	const showUpdateDialog = ref(false)
	
	// 监听全局弹窗状态，确保任何页面都能响应
	watch(() => upgradeStore.shouldShowDialog, (newVal) => {
		if (newVal) {
			console.log('📢 监听到全局更新弹窗状态变化，显示弹窗')
			showUpdateDialog.value = true
		}
	}, { immediate: true })
	
	const instance = getCurrentInstance()
	const t = (key, params = {}) => instance.appContext.config.globalProperties.$t(key, params)
	
	// 统计数据
	const siteStats = reactive({
		total: 0,
		operational: 0,
		maintenance: 0,
		construction: 0
	})
	
	const workOrderStats = reactive({
		assigned: 0,
		in_progress: 0,
		submitted: 0
	})
	
	const recentActivities = ref([])
	const refreshing = ref(false)
	const isLoading = ref(true)
	
	
	// 权限控制计算属性
	const userRole = computed(() => {
		if (!userStore || !userStore.userInfo) return 'user'
		return userStore.userInfo.role || 'user'
	})
	const isAdmin = computed(() => userRole.value === 'admin')
	const isManager = computed(() => userRole.value === 'manager')
	const isWarehouseManager = computed(() => userRole.value === 'warehouse_manager')
	const isInspector = computed(() => userRole.value === 'inspector')
	const isSurveyor = computed(() => userRole.value === 'surveyor')
	const isWarehouseSide = computed(() => isAdmin.value || isManager.value || isWarehouseManager.value)
	const canViewStats = computed(() => isAdmin.value || isManager.value)
// 报告占位入口已移除
	
	// 获取用户头像文字
	const getAvatarText = () => {
		const name = userStore.userInfo?.full_name || userStore.userInfo?.username || ''
		return name.charAt(0).toUpperCase()
	}

	// 加载数据
	const loadData = async (showLoading = false) => {
		if (showLoading) {
			refreshing.value = true
		}
		// 检查登录状态
		if (!userStore || !userStore.isLoggedIn) {
			uni.reLaunch({
				url: '/pages/login/login'
			})
			return
		}
		
		try {
			// 加载工单数据（先加载，用于统计站点）
			let wos = [] // 定义在外层作用域
			const woRes = await workOrderStore.getMyWorkOrders()
			if (woRes.success) {
				wos = woRes.data || []
				// 后端返回的状态是大写格式，需要匹配大写
				// 统计活跃工单：ASSIGNED + ACTIVE + IN_PROGRESS + ACCEPTED
				workOrderStats.assigned = wos.filter(w =>
					['ASSIGNED', 'ACTIVE', 'IN_PROGRESS', 'ACCEPTED'].includes(w.status)
				).length
				// 待审核工单：SUBMITTED + UNDER_REVIEW
				workOrderStats.in_progress = wos.filter(w =>
					['SUBMITTED', 'UNDER_REVIEW'].includes(w.status)
				).length
				// 已完成工单：APPROVED + COMPLETED
				workOrderStats.submitted = wos.filter(w =>
					['APPROVED', 'COMPLETED', 'ACTIVATED'].includes(w.status)
				).length
				recentActivities.value = wos
					.sort((a, b) => new Date(b.assigned_at) - new Date(a.assigned_at))
					.slice(0, 5)
					.map(wo => ({ id: wo.id, created_at: wo.assigned_at, title: `${t('workorder.title')}: ${wo.title}`, type: 'work_order', status: wo.status }))
			}

			// 加载站点数据（所有角色都可以访问API）
			const sitesResult = await siteStore.getSites()
			if (sitesResult.success) {
				let sites = sitesResult.data

				// inspector和surveyor角色：只统计工单关联的站点
				if (isInspector.value || isSurveyor.value) {
					const workOrderSiteIds = new Set(
						wos.map(wo => wo.site_id).filter(id => id)
					)
					sites = sites.filter(site => workOrderSiteIds.has(site.id))
				}

				siteStats.total = sites.length

				// 站点状态统计（仅admin和manager显示）
				if (canViewStats.value) {
					siteStats.operational = sites.filter(s => s.status === 'operational').length
					siteStats.maintenance = sites.filter(s => s.status === 'maintenance').length
					siteStats.construction = sites.filter(s => s.status === 'construction').length
				}
			}

		} catch (error) {
		console.error('Load data error:', error)
	} finally {
		isLoading.value = false
		if (showLoading) {
			refreshing.value = false
		}
	}
}
	
	// 下拉刷新处理
	const handleRefresh = async () => {
		console.log('🔄 首页数据刷新中...')
		await loadData(true)
		console.log('✅ 首页数据刷新完成')
	}
	

	
	// 格式化时间
	const formatTime = (timeStr) => {
		return formatTimeAgo(timeStr, t)
	}
	
	// 获取活动图标
	const getActivityIcon = (type) => {
		switch(type) {
			case 'work_order': return '📋'
			case 'site': return '📍'
			default: return '📋'
		}
	}
	
	const getActivityIconClass = (type) => {
		return `icon-${type}`
	}
	
	const getStatusClass = (status) => {
		return `status-${status}`
	}
	
	const getStatusText = (status) => {
		const statusMap = {
			ASSIGNED: t('workorder.assigned'),
			ACTIVE: t('workorder.inProgress'),
			IN_PROGRESS: t('workorder.inProgress'),
			ACCEPTED: t('workorder.accepted'),
			SUBMITTED: t('workorder.submitted'),
			UNDER_REVIEW: t('workorder.underReview'),
			APPROVED: t('workorder.approved'),
			REJECTED: t('workorder.rejected'),
			COMPLETED: t('workorder.completed'),
			ACTIVATED: t('workorder.completed'),
		}
		return statusMap[status] || status
	}
	
	// 页面跳转方法
	const goToSites = () => {
		uni.reLaunch({ url: '/pages/site/list' })
	}
	
	const goToWorkOrders = () => {
		uni.reLaunch({ url: '/pages/workorder/list' })
	}
	
	const goToNewInspection = () => { goToWorkOrders() }
	
	const goToSiteList = () => {
		uni.reLaunch({ url: '/pages/site/list' })
	}
	
	const goToMap = () => {
		uni.navigateTo({ url: '/pages/map/sites' })
	}
	
// 报告功能入口已移除
	
	
	const goToScanPickup = () => {
		// 跳转到扫码领料页面
		uni.navigateTo({ url: '/pages/stock/scan-pickup' })
	}

	const goToMaterialRequests = () => {
		uni.navigateTo({ url: '/pages/stock/material-requests/list' })
	}

	const goToMaterialApprovalList = () => {
		uni.navigateTo({ url: '/pages/stock/material-requests/approval-list' })
	}

	const goToIssueConfirmList = () => {
		uni.navigateTo({ url: '/pages/stock/issue-drafts/confirm-list' })
	}

	const goToReturnRequests = () => {
		uni.navigateTo({ url: '/pages/stock/returns/list' })
	}

	const goToManualStockOut = () => {
		uni.navigateTo({ url: '/pages/stock/manual-stock-out' })
	}
	
	const showUserMenu = () => {
		uni.showActionSheet({
			itemList: [t('profile.userInfo'), t('profile.logout')],
			success: (res) => {
				if (res.tapIndex === 0) {
					uni.reLaunch({ url: '/pages/profile/profile' })
				} else if (res.tapIndex === 1) {
					uni.showModal({
						title: t('common.hint'),
						content: t('messages.confirmLogout'),
						success: (res) => {
							if (res.confirm) {
								userStore.logout()
							}
						}
					})
				}
			}
		})
	}
	
	const viewActivity = (activity) => {
		// 最近活动目前主要是工单，点击时跳转到工单列表并聚焦对应工单卡片
		if (activity.type === 'work_order') {
			// 记录需要聚焦的工单ID
			workOrderStore.setFocusedWorkOrder(activity.id)
			uni.reLaunch({
				url: '/pages/workorder/list'
			})
			return
		}
		
		// 预留检查跳转
		if (activity.type === 'inspection') {
			uni.navigateTo({
				url: `/pages/inspection/detail?id=${activity.id}`
			})
		}
	}
	
	onMounted(async () => {
		// 确保用户store已初始化
		if (!userStore) {
			console.error('UserStore not initialized')
			return
		}
		
		// 检查登录状态，如果没有登录信息则先检查本地存储
		if (!userStore.userInfo) {
			userStore.checkLoginStatus()
		}
		
		// 延迟一下确保store状态更新
		setTimeout(() => {
			loadData()
		}, 100)
		
		// 版本检测由App.vue全局触发，这里通过watch监听upgradeStore.shouldShowDialog自动响应
	})
	
	// 更新安装完成处理
	const handleUpdateInstalled = () => {
		console.log('✅ 更新安装完成')
		showUpdateDialog.value = false
		upgradeStore.hideDialog()  // 同步清除全局状态
	}
	
	// 弹窗关闭处理
	const handleDialogClose = () => {
		showUpdateDialog.value = false
		upgradeStore.hideDialog()  // 同步清除全局状态
	}
	
	// 页面显示时刷新数据
	onShow(() => {
		console.log('📱 首页显示，刷新数据')
		loadData()
	})
</script>

<style lang="scss" scoped>
	.home-container {
		display: flex;
		flex-direction: column;
		height: 100vh;
		background-color: var(--bg-page);
		overflow: hidden;
	}
	
	// 滚动容器
	.home-scroll {
		flex: 1;
		height: 0;
		min-height: 0;
	}

	.tabbar-spacer {
		height: calc(64px + env(safe-area-inset-bottom));
	}

	// 自定义导航栏
	.custom-navbar {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding: 44rpx 30rpx 20rpx;
		color: #fff;
	}
	
	.navbar-content {
		display: flex;
		justify-content: space-between;
		align-items: center;
		height: 88rpx;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
	}
	
	.user-info { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 6px; border-radius: 12px; }
	
	.user-name {
		font-size: 14px;
	}
	
	.avatar {
		width: 32px;
		height: 32px;
		background: rgba(255, 255, 255, 0.2);
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		
		.avatar-text {
			font-size: 14px;
			font-weight: 600;
		}
	}
	
	// 统计卡片
	.stats-container { padding: 20px; margin-top: -10px; }
	
	.stats-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	
	.stat-card {
		background: var(--bg-elevated);
		border-radius: var(--radius-md);
		padding: 16px;
		display: flex;
		align-items: center;
		gap: 12px;
		box-shadow: var(--shadow-card);
	}
	
	.stat-icon {
		font-size: 24px;
		width: 48px;
		height: 48px;
		border-radius: 12px;
		display: flex;
		align-items: center;
		justify-content: center;
		
		&.site-icon { background: #fef3c7; }
		&.inspection-icon { background: #dbeafe; }
		&.operational-icon { background: #d1fae5; }
		&.maintenance-icon { background: #fee2e2; }
	}
	
	.stat-info {
		display: flex;
		flex-direction: column;
	}
	
	.stat-number { font-size: 24px; font-weight: 600; color: var(--text-primary); }
	
	.stat-label { font-size: 12px; color: var(--text-secondary); }
	
	// 快捷操作
	.quick-actions { margin: 20px; }
	
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
	}
	
	.section-title { font-size: 18px; font-weight: 600; color: var(--text-primary); }
	
	.see-all { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 0 10px; font-size: 14px; color: var(--color-primary); }
	
	.actions-grid {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr 1fr;
		gap: 16px;
	}
	
	.action-item {
		background: var(--bg-elevated);
		border-radius: var(--radius-md);
		padding: 20px 12px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		box-shadow: var(--shadow-card);
	}
	
	.action-icon {
		font-size: 28px;
		margin-bottom: 4px;
	}
	
	.action-label {
		font-size: 12px;
		color: #374151;
		text-align: center;
	}
	
	// 最近活动
	.recent-activities { margin: 20px; }
	
	.activity-list {
		background: var(--bg-elevated);
		border-radius: var(--radius-md);
		overflow: hidden;
		box-shadow: var(--shadow-card);
	}
	
	.activity-item {
		display: flex;
		align-items: center;
		padding: 16px;
		border-bottom: 1px solid var(--border-soft);
		
		&:last-child { border-bottom: none; }
	}
	
	.activity-icon {
		width: 40px;
		height: 40px;
		border-radius: 10px;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-right: 12px;
		font-size: 18px;
		
		&.icon-work_order { background: #dbeafe; }
		&.icon-site { background: #fef3c7; }
	}
	
	.activity-content {
		flex: 1;
		display: flex;
		flex-direction: column;
	}
	
	.activity-title {
		font-size: 14px;
		color: #111827;
		margin-bottom: 4px;
	}
	
	.activity-time {
		font-size: 12px;
		color: #6b7280;
	}
	
	.activity-status {
		padding: 4px 8px;
		border-radius: 6px;
		font-size: 12px;
		
		&.status-pending { background: #fef3c7; color: #d97706; }
		&.status-in_progress { background: #dbeafe; color: #2563eb; }
		&.status-completed { background: #d1fae5; color: #059669; }
		&.status-failed { background: #fee2e2; color: #dc2626; }
	}
</style>
