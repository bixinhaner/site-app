<template>
	<view class="home-container">
		<!-- 自定义导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<text class="navbar-title">站点管理系统</text>
				<view class="user-info" @click="showUserMenu">
					<text class="user-name">{{ userStore.userInfo?.full_name || userStore.userInfo?.username }}</text>
					<view class="avatar">
						<text class="avatar-text">{{ getAvatarText() }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 统计卡片 -->
		<view class="stats-container">
			<view class="stats-grid">
				<!-- 管理员和经理能查看和管理站点，检查员只能查看 -->
				<view class="stat-card" @click="goToSites">
					<view class="stat-icon site-icon">📍</view>
					<view class="stat-info">
						<text class="stat-number">{{ siteStats.total }}</text>
						<text class="stat-label">总站点数</text>
					</view>
				</view>
				
				<!-- 所有角色都能查看检查 -->
				<view class="stat-card" @click="goToInspections">
					<view class="stat-icon inspection-icon">🔍</view>
					<view class="stat-info">
						<text class="stat-number">{{ inspectionStats.pending }}</text>
						<text class="stat-label">{{ getInspectionLabel() }}</text>
					</view>
				</view>
				
				<!-- 管理员和经理可以看站点状态统计 -->
				<view class="stat-card" v-if="canViewStats">
					<view class="stat-icon operational-icon">✅</view>
					<view class="stat-info">
						<text class="stat-number">{{ siteStats.operational }}</text>
						<text class="stat-label">运营中</text>
					</view>
				</view>
				
				<view class="stat-card" v-if="canViewStats">
					<view class="stat-icon maintenance-icon">⚠️</view>
					<view class="stat-info">
						<text class="stat-number">{{ siteStats.maintenance }}</text>
						<text class="stat-label">维护中</text>
					</view>
				</view>
				
				<!-- 检查员显示我的任务 -->
				<view class="stat-card" v-if="isInspector" @click="goToMyTasks">
					<view class="stat-icon inspection-icon">📋</view>
					<view class="stat-info">
						<text class="stat-number">{{ myTaskStats.assigned }}</text>
						<text class="stat-label">我的任务</text>
					</view>
				</view>
				
				<view class="stat-card" v-if="isInspector">
					<view class="stat-icon operational-icon">✅</view>
					<view class="stat-info">
						<text class="stat-number">{{ myTaskStats.completed }}</text>
						<text class="stat-label">已完成</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 快捷操作 -->
		<view class="quick-actions">
			<view class="section-header">
				<text class="section-title">快捷操作</text>
			</view>
			
			<view class="actions-grid">
				<!-- 所有角色都能进行现场检查 -->
				<view class="action-item" @click="goToNewInspection">
					<view class="action-icon">📷</view>
					<text class="action-label">现场检查</text>
				</view>
				
				<!-- 所有角色都能查看站点列表 -->
				<view class="action-item" @click="goToSiteList">
					<view class="action-icon">📋</view>
					<text class="action-label">站点列表</text>
				</view>
				
				<!-- 管理员和经理专用功能 -->
				<view class="action-item" v-if="canManageTasks" @click="goToTaskManagement">
					<view class="action-icon">📝</view>
					<text class="action-label">任务管理</text>
				</view>
				
				<view class="action-item" v-if="canViewReports" @click="goToReports">
					<view class="action-icon">📊</view>
					<text class="action-label">数据报告</text>
				</view>
				
				<!-- 检查员专用功能 -->
				<view class="action-item" v-if="isInspector" @click="goToMyTasks">
					<view class="action-icon">📋</view>
					<text class="action-label">我的任务</text>
				</view>
				
				<!-- 扫码领料功能 -->
				<view class="action-item" @click="goToScanPickup">
					<view class="action-icon">📦</view>
					<text class="action-label">扫码领料</text>
				</view>
				
				<!-- 公共功能 -->
				<view class="action-item" @click="goToMap">
					<view class="action-icon">🗺️</view>
					<text class="action-label">地图查看</text>
				</view>
			</view>
		</view>
		
		<!-- 最近活动 -->
		<view class="recent-activities">
			<view class="section-header">
				<text class="section-title">最近活动</text>
				<text class="see-all" @click="goToInspections">查看全部</text>
			</view>
			
			<view class="activity-list">
				<view 
					class="activity-item" 
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
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, reactive, computed, onMounted } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useInspectionStore } from '@/stores/inspection'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	
	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const inspectionStore = useInspectionStore()
	
	// 统计数据
	const siteStats = reactive({
		total: 0,
		operational: 0,
		maintenance: 0,
		construction: 0
	})
	
	const inspectionStats = reactive({
		pending: 0,
		completed: 0,
		failed: 0
	})
	
	const recentActivities = ref([])
	
	// 我的任务统计（检查员专用）
	const myTaskStats = reactive({
		assigned: 0,
		completed: 0
	})
	
	// 权限控制计算属性
	const userRole = computed(() => {
		if (!userStore || !userStore.userInfo) return 'user'
		return userStore.userInfo.role || 'user'
	})
	const isAdmin = computed(() => userRole.value === 'admin')
	const isManager = computed(() => userRole.value === 'manager')
	const isInspector = computed(() => userRole.value === 'inspector')
	const canViewStats = computed(() => isAdmin.value || isManager.value)
	const canManageTasks = computed(() => isAdmin.value || isManager.value)
	const canViewReports = computed(() => isAdmin.value || isManager.value)
	
	// 获取用户头像文字
	const getAvatarText = () => {
		const name = userStore.userInfo?.full_name || userStore.userInfo?.username || ''
		return name.charAt(0).toUpperCase()
	}
	
	// 获取检查标签文字
	const getInspectionLabel = () => {
		if (isInspector.value) {
			return '待检查'
		} else {
			return '待审核'
		}
	}
	
	// 加载数据
	const loadData = async () => {
		// 检查登录状态
		if (!userStore || !userStore.isLoggedIn) {
			uni.reLaunch({
				url: '/pages/login/login'
			})
			return
		}
		
		try {
			// 加载站点数据
			const sitesResult = await siteStore.getSites()
			if (sitesResult.success) {
				const sites = sitesResult.data
				siteStats.total = sites.length
				siteStats.operational = sites.filter(s => s.status === 'operational').length
				siteStats.maintenance = sites.filter(s => s.status === 'maintenance').length
				siteStats.construction = sites.filter(s => s.status === 'construction').length
			}
			
			// 加载检查数据
			const inspectionsResult = await inspectionStore.getInspections()
			if (inspectionsResult.success) {
				const inspections = inspectionsResult.data
				inspectionStats.pending = inspections.filter(i => i.status === 'pending').length
				inspectionStats.completed = inspections.filter(i => i.status === 'completed').length
				inspectionStats.failed = inspections.filter(i => i.status === 'failed').length
				
				// 取最近5条活动
				recentActivities.value = inspections
					.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
					.slice(0, 5)
					.map(inspection => ({
						...inspection,
						title: `检查站点: ${inspection.site?.site_name || 'Unknown'}`,
						type: 'inspection'
					}))
			}
			
			// 如果是检查员，加载我的任务统计
			if (isInspector.value) {
				await loadMyTaskStats()
			}
		} catch (error) {
			console.error('Load data error:', error)
		}
	}
	
	// 加载我的任务统计
	const loadMyTaskStats = async () => {
		if (!userStore || !userStore.userInfo) return
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.LIST),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				},
				data: {
					assigned_to: userStore.userInfo.id
				}
			})
			
			if (response.statusCode === 200) {
				const tasks = response.data
				myTaskStats.assigned = tasks.filter(t => ['assigned', 'in_progress'].includes(t.status)).length
				myTaskStats.completed = tasks.filter(t => t.status === 'completed').length
			}
		} catch (error) {
			console.error('Load my task stats error:', error)
		}
	}
	
	// 格式化时间
	const formatTime = (timeStr) => {
		const time = new Date(timeStr)
		const now = new Date()
		const diff = now - time
		
		if (diff < 60000) return '刚刚'
		if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
		if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
		return `${Math.floor(diff / 86400000)}天前`
	}
	
	// 获取活动图标
	const getActivityIcon = (type) => {
		switch(type) {
			case 'inspection': return '🔍'
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
			'pending': '待处理',
			'in_progress': '进行中',
			'completed': '已完成',
			'failed': '失败'
		}
		return statusMap[status] || status
	}
	
	// 页面跳转方法
	const goToSites = () => {
		uni.switchTab({ url: '/pages/site/list' })
	}
	
	const goToInspections = () => {
		uni.switchTab({ url: '/pages/inspection/list' })
	}
	
	const goToNewInspection = () => {
		// 显示检查类型选择弹窗
		uni.showActionSheet({
			itemList: ['新站点设备安装', '维护检查'],
			success: (res) => {
				const typeMap = ['opening', 'maintenance']
				const selectedType = typeMap[res.tapIndex]
				uni.navigateTo({ 
					url: `/pages/inspection/site-select?type=${selectedType}` 
				})
			}
		})
	}
	
	const goToSiteList = () => {
		uni.switchTab({ url: '/pages/site/list' })
	}
	
	const goToMap = () => {
		uni.showToast({ title: '地图功能开发中', icon: 'none' })
	}
	
	const goToReports = () => {
		uni.showToast({ title: '报告功能开发中', icon: 'none' })
	}
	
	const goToTaskManagement = () => {
		uni.switchTab({ url: '/pages/task/list' })
	}
	
	const goToMyTasks = () => {
		// 跳转到我的任务列表，只显示分配给当前用户的任务
		uni.switchTab({ url: '/pages/task/list' })
	}
	
	const goToScanPickup = () => {
		// 跳转到扫码领料页面
		uni.navigateTo({ url: '/pages/stock/scan-pickup' })
	}
	
	const showUserMenu = () => {
		uni.showActionSheet({
			itemList: ['个人信息', '退出登录'],
			success: (res) => {
				if (res.tapIndex === 0) {
					uni.switchTab({ url: '/pages/profile/profile' })
				} else if (res.tapIndex === 1) {
					uni.showModal({
						title: '确认退出',
						content: '确定要退出登录吗？',
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
	})
</script>

<style lang="scss" scoped>
	.home-container {
		min-height: 100vh;
		background-color: #f5f5f5;
	}
	
	// 自定义导航栏
	.custom-navbar {
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 44px 20px 20px;
		color: white;
	}
	
	.navbar-content {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.navbar-title {
		font-size: 20px;
		font-weight: 600;
	}
	
	.user-info {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	
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
	.stats-container {
		padding: 20px;
		margin-top: -10px;
	}
	
	.stats-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	
	.stat-card {
		background: white;
		border-radius: 12px;
		padding: 16px;
		display: flex;
		align-items: center;
		gap: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
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
	
	.stat-number {
		font-size: 24px;
		font-weight: 600;
		color: #111827;
	}
	
	.stat-label {
		font-size: 12px;
		color: #6b7280;
	}
	
	// 快捷操作
	.quick-actions {
		margin: 20px;
	}
	
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
	}
	
	.section-title {
		font-size: 18px;
		font-weight: 600;
		color: #111827;
	}
	
	.see-all {
		font-size: 14px;
		color: #f97316;
	}
	
	.actions-grid {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr 1fr;
		gap: 16px;
	}
	
	.action-item {
		background: white;
		border-radius: 12px;
		padding: 20px 12px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
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
	.recent-activities {
		margin: 20px;
	}
	
	.activity-list {
		background: white;
		border-radius: 12px;
		overflow: hidden;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
	}
	
	.activity-item {
		display: flex;
		align-items: center;
		padding: 16px;
		border-bottom: 1px solid #f3f4f6;
		
		&:last-child {
			border-bottom: none;
		}
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
		
		&.icon-inspection { background: #dbeafe; }
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