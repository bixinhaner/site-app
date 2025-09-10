<template>
	<view class="task-container">
		<!-- 导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<text class="navbar-title">{{ getPageTitle() }}</text>
				<view class="navbar-actions">
					<view class="add-button" @click="showCreateTask" v-if="canCreateTask">
						<text class="add-icon">+</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 统计卡片 -->
		<view class="stats-container">
			<view class="stat-card">
				<text class="stat-number">{{ taskStats.total }}</text>
				<text class="stat-label">{{ isInspector ? '我的任务' : '总任务' }}</text>
			</view>
			<view class="stat-card" v-if="!isInspector">
				<text class="stat-number">{{ taskStats.pending }}</text>
				<text class="stat-label">待分配</text>
			</view>
			<view class="stat-card" v-if="isInspector">
				<text class="stat-number">{{ taskStats.pending }}</text>
				<text class="stat-label">待接受</text>
			</view>
			<view class="stat-card">
				<text class="stat-number">{{ taskStats.in_progress }}</text>
				<text class="stat-label">进行中</text>
			</view>
			<view class="stat-card">
				<text class="stat-number">{{ taskStats.completed }}</text>
				<text class="stat-label">已完成</text>
			</view>
		</view>
		
		<!-- 筛选器 -->
		<view class="filter-container">
			<scroll-view class="filter-scroll" scroll-x>
				<view class="filter-item" 
					:class="{ active: activeFilter === 'all' }"
					@click="setFilter('all')">
					<text>全部</text>
				</view>
				<!-- 管理员和经理看到的筛选选项 -->
				<view class="filter-item" v-if="!isInspector"
					:class="{ active: activeFilter === 'pending' }"
					@click="setFilter('pending')">
					<text>待分配</text>
				</view>
				<!-- 检查员看到的筛选选项 -->
				<view class="filter-item"
					:class="{ active: activeFilter === 'assigned' }"
					@click="setFilter('assigned')">
					<text>{{ isInspector ? '待接受' : '已分配' }}</text>
				</view>
				<view class="filter-item"
					:class="{ active: activeFilter === 'in_progress' }"
					@click="setFilter('in_progress')">
					<text>进行中</text>
				</view>
				<view class="filter-item"
					:class="{ active: activeFilter === 'under_review' }"
					@click="setFilter('under_review')">
					<text>待审核</text>
				</view>
				<view class="filter-item"
					:class="{ active: activeFilter === 'completed' }"
					@click="setFilter('completed')">
					<text>已完成</text>
				</view>
			</scroll-view>
		</view>
		
		<!-- 任务列表 -->
		<scroll-view class="task-list" scroll-y @scrolltolower="loadMore">
			<view class="task-item" 
				v-for="task in filteredTasks" 
				:key="task.id"
				@click="viewTaskDetail(task)">
				<view class="task-header">
					<view class="task-info">
						<text class="task-title">{{ task.task_title }}</text>
						<view class="task-meta">
							<text class="task-type">{{ getTaskTypeText(task.task_type) }}</text>
							<text class="task-priority" :class="getPriorityClass(task.priority)">
								{{ getPriorityText(task.priority) }}
							</text>
						</view>
					</view>
					<view class="task-status" :class="getStatusClass(task.status)">
						<text class="status-text">{{ getStatusText(task.status) }}</text>
					</view>
				</view>
				
				<view class="task-details">
					<view class="detail-row">
						<text class="detail-icon">📍</text>
						<text class="detail-text">{{ task.site_name || '未知站点' }}</text>
					</view>
					<view class="detail-row" v-if="task.assignee_name">
						<text class="detail-icon">👤</text>
						<text class="detail-text">分配给: {{ task.assignee_name }}</text>
					</view>
					<view class="detail-row">
						<text class="detail-icon">📅</text>
						<text class="detail-text">截止: {{ formatDate(task.due_date) }}</text>
					</view>
					<view class="detail-row" v-if="task.progress_notes">
						<text class="detail-icon">📝</text>
						<text class="detail-text">{{ task.progress_notes }}</text>
					</view>
				</view>
				
				<view class="task-actions" v-if="canManageTask(task)">
					<button class="action-btn assign-btn" 
						@click.stop="assignTask(task)"
						v-if="task.status === 'pending'">
						分配
					</button>
					<button class="action-btn review-btn" 
						@click.stop="reviewTask(task)"
						v-if="task.status === 'under_review'">
						审核
					</button>
					<button class="action-btn detail-btn" 
						@click.stop="viewTaskDetail(task)">
						详情
					</button>
					<button class="action-btn delete-btn" 
						@click.stop="deleteTask(task)"
						v-if="canDeleteTask(task)">
						删除
					</button>
				</view>
			</view>
			
			<!-- 空状态 -->
			<view class="empty-state" v-if="filteredTasks.length === 0 && !loading">
				<text class="empty-icon">📋</text>
				<text class="empty-title">暂无任务</text>
				<text class="empty-desc">当前筛选条件下没有找到任务</text>
			</view>
			
			<!-- 加载更多 -->
			<view class="load-more" v-if="hasMore">
				<uni-load-more :status="loadMoreStatus"></uni-load-more>
			</view>
		</scroll-view>
		
		<!-- 创建任务弹窗 -->
		<view class="modal-overlay" v-if="showCreateModal" @click="hideCreateTask">
			<view class="create-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">创建新任务</text>
					<view class="modal-close" @click="hideCreateTask">
						<text class="close-icon">×</text>
					</view>
				</view>
				<view class="modal-content">
					<view class="form-item">
						<text class="form-label">任务类型</text>
						<picker :value="createForm.typeIndex" :range="taskTypeOptions" @change="onTaskTypeChange">
							<view class="picker-input">
								{{ taskTypeOptions[createForm.typeIndex] }}
							</view>
						</picker>
					</view>
					<view class="form-item">
						<text class="form-label">站点选择</text>
						<picker :value="createForm.siteIndex" :range="siteOptions" range-key="site_name" @change="onSiteChange">
							<view class="picker-input">
								{{ siteOptions[createForm.siteIndex]?.site_name || '请选择站点' }}
							</view>
						</picker>
					</view>
					<view class="form-item">
						<text class="form-label">分配给</text>
						<picker :value="createForm.assigneeIndex" :range="engineerOptions" range-key="full_name" @change="onAssigneeChange">
							<view class="picker-input">
								{{ engineerOptions[createForm.assigneeIndex]?.full_name || '请选择工程师' }}
							</view>
						</picker>
					</view>
					<view class="form-item">
						<text class="form-label">任务标题</text>
						<input class="form-input" v-model="createForm.title" placeholder="请输入任务标题" />
					</view>
					<view class="form-item">
						<text class="form-label">任务描述</text>
						<textarea class="form-textarea" v-model="createForm.description" placeholder="请输入任务描述" />
					</view>
					<view class="form-item">
						<text class="form-label">优先级</text>
						<picker :value="createForm.priorityIndex" :range="priorityOptions" @change="onPriorityChange">
							<view class="picker-input">
								{{ priorityOptions[createForm.priorityIndex] }}
							</view>
						</picker>
					</view>
				</view>
				<view class="modal-actions">
					<button class="modal-cancel" @click="hideCreateTask">取消</button>
					<button class="modal-confirm" @click="createTask">创建</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, onUnmounted } from 'vue'
	import { onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	// import { usePageRefresh } from '@/utils/page-visibility.js'
	
	const userStore = useUserStore()
	
	// 响应式数据
	const tasks = ref([])
	const taskStats = ref({
		total: 0,
		pending: 0,
		in_progress: 0,
		completed: 0
	})
	const loading = ref(false)
	const hasMore = ref(true)
	const loadMoreStatus = ref('more')
	const activeFilter = ref('all')
	const page = ref(1)
	const pageSize = ref(20)
	
	// 创建任务相关
	const showCreateModal = ref(false)
	const createForm = ref({
		typeIndex: 0,
		siteIndex: 0,
		assigneeIndex: 0,
		priorityIndex: 1,
		title: '',
		description: ''
	})
	
	const taskTypeOptions = ['新站点设备安装', '维护检查']
	const priorityOptions = ['低', '普通', '高', '紧急']
	const siteOptions = ref([])
	const engineerOptions = ref([])
	
	// 权限检查
	const userRole = computed(() => userStore.userInfo?.role || 'user')
	const isAdmin = computed(() => userRole.value === 'admin')
	const isManager = computed(() => userRole.value === 'manager')
	const isInspector = computed(() => userRole.value === 'inspector')
	const canCreateTask = computed(() => isAdmin.value || isManager.value)
	
	const canManageTask = (task) => {
		const role = userStore.userInfo?.role
		if (role === 'admin' || role === 'manager') return true
		if (role === 'inspector' && task.assigned_to === userStore.userInfo?.id) return true
		return false
	}
	
	const canDeleteTask = (task) => {
		const role = userStore.userInfo?.role
		if (role !== 'admin') return false
		// 只能删除待分配、已分配或已驳回的任务
		return ['pending', 'assigned', 'rejected'].includes(task.status)
	}
	
	// 筛选后的任务
	const filteredTasks = computed(() => {
		if (activeFilter.value === 'all') return tasks.value
		return tasks.value.filter(task => task.status === activeFilter.value)
	})
	
	// 方法定义（提前声明避免初始化问题）
	const loadTasks = async (reset = false) => {
		try {
			loading.value = true
			
			if (reset) {
				page.value = 1
				tasks.value = []
			}
			
			// 根据用户角色构建请求参数
			let requestData = {
				skip: (page.value - 1) * pageSize.value,
				limit: pageSize.value
			}
			
			// 如果是检查员，只显示分配给自己的任务
			if (isInspector.value) {
				requestData.assigned_to = userStore.userInfo?.id
			}
			
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.LIST),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
					data: requestData
				})
			})
			
			if (response.statusCode === 200) {
				const newTasks = response.data
				
				if (reset) {
					tasks.value = newTasks
				} else {
					tasks.value.push(...newTasks)
				}
				
				hasMore.value = newTasks.length === pageSize.value
				loadMoreStatus.value = hasMore.value ? 'more' : 'no-more'
			}
		} catch (error) {
			console.error('加载任务失败:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const loadTaskStats = async () => {
		try {
			let url = buildApiUrl(API_ENDPOINTS.TASKS.STATISTICS.OVERVIEW)
			let requestData = {}
			
			// 如果是检查员，只统计分配给自己的任务
			if (isInspector.value) {
				url = buildApiUrl(API_ENDPOINTS.TASKS.LIST)
				requestData.assigned_to = userStore.userInfo?.id
			}
			
			const response = await uni.request({
				url: url,
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				},
				data: requestData
			})
			
			if (response.statusCode === 200) {
				if (isInspector.value) {
					// 为检查员计算统计数据
					const tasks = response.data
					taskStats.value = {
						total: tasks.length,
						pending: tasks.filter(t => t.status === 'assigned').length,
						in_progress: tasks.filter(t => t.status === 'in_progress').length,
						completed: tasks.filter(t => t.status === 'completed').length
					}
				} else {
					taskStats.value = response.data
				}
			}
		} catch (error) {
			console.error('加载统计失败:', error)
		}
	}
	
	const loadSites = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.SITES.LIST),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				siteOptions.value = response.data
			}
		} catch (error) {
			console.error('加载站点失败:', error)
		}
	}
	
	const loadEngineers = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.USERS.LIST),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
					data: {
						role: 'inspector'
					}
				})
			})
			
			if (response.statusCode === 200) {
				engineerOptions.value = response.data
			}
		} catch (error) {
			console.error('加载工程师列表失败:', error)
		}
	}
	
	// 生命周期
	onMounted(() => {
		loadTasks()
		loadTaskStats()
		loadSites()
		loadEngineers()
		
		// 监听任务相关事件
		uni.$on('taskCreated', handleTaskCreated)
		uni.$on('taskUpdated', handleTaskUpdated)
		uni.$on('taskDeleted', handleTaskDeleted)
		uni.$on('taskReviewed', handleTaskReviewed)
		uni.$on('taskAssigned', handleTaskAssigned)
	})
	
	// 页面显示时刷新数据
	onShow(() => {
		// 避免初次加载时重复刷新
		if (tasks.value.length > 0) {
			loadTasks(true)
			loadTaskStats()
		}
	})
	
	// 页面销毁时移除事件监听
	onUnmounted(() => {
		uni.$off('taskCreated', handleTaskCreated)
		uni.$off('taskUpdated', handleTaskUpdated)
		uni.$off('taskDeleted', handleTaskDeleted)
		uni.$off('taskReviewed', handleTaskReviewed)
		uni.$off('taskAssigned', handleTaskAssigned)
		// 注销页面刷新管理
		// unregister()
	})
	const setFilter = (filter) => {
		activeFilter.value = filter
	}
	
	const loadMore = async () => {
		if (!hasMore.value || loading.value) return
		
		loadMoreStatus.value = 'loading'
		page.value++
		await loadTasks()
	}
	
	const showCreateTask = () => {
		showCreateModal.value = true
	}
	
	const hideCreateTask = () => {
		showCreateModal.value = false
		resetCreateForm()
	}
	
	const resetCreateForm = () => {
		createForm.value = {
			typeIndex: 0,
			siteIndex: 0,
			assigneeIndex: 0,
			priorityIndex: 1,
			title: '',
			description: ''
		}
	}
	
	const onTaskTypeChange = (e) => {
		createForm.value.typeIndex = e.detail.value
	}
	
	const onSiteChange = (e) => {
		createForm.value.siteIndex = e.detail.value
	}
	
	const onAssigneeChange = (e) => {
		createForm.value.assigneeIndex = e.detail.value
	}
	
	const onPriorityChange = (e) => {
		createForm.value.priorityIndex = e.detail.value
	}
	
	const createTask = async () => {
		if (!createForm.value.title.trim()) {
			uni.showToast({
				title: '请输入任务标题',
				icon: 'error'
			})
			return
		}
		
		try {
			const taskTypeMap = {
				0: 'opening_inspection',
				1: 'maintenance'
			}
			
			const priorityMap = {
				0: 'low',
				1: 'normal', 
				2: 'high',
				3: 'urgent'
			}
			
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.CREATE),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token)
				}),
				data: {
					task_title: createForm.value.title,
					task_type: taskTypeMap[createForm.value.typeIndex],
					task_description: createForm.value.description,
					priority: priorityMap[createForm.value.priorityIndex],
					site_id: siteOptions.value[createForm.value.siteIndex]?.id,
					assigned_to: engineerOptions.value[createForm.value.assigneeIndex]?.id
				}
			})
			
			if (response.statusCode === 200 || response.statusCode === 201) {
				uni.showToast({
					title: '任务创建成功',
					icon: 'success'
				})
				hideCreateTask()
				loadTasks(true)
				loadTaskStats()
			}
		} catch (error) {
			console.error('创建任务失败:', error)
			uni.showToast({
				title: '创建失败',
				icon: 'error'
			})
		}
	}
	
	const assignTask = (task) => {
		// 跳转到任务分配页面
		uni.navigateTo({
			url: `/pages/task/assign?taskId=${task.id}`
		})
	}
	
	const reviewTask = (task) => {
		// 跳转到任务审核页面
		uni.navigateTo({
			url: `/pages/task/review?taskId=${task.id}`
		})
	}
	
	const viewTaskDetail = (task) => {
		// 跳转到任务详情页面
		uni.navigateTo({
			url: `/pages/task/detail?taskId=${task.id}`
		})
	}
	
	const deleteTask = async (task) => {
		// 显示确认对话框
		const res = await uni.showModal({
			title: '确认删除',
			content: `确定要删除任务"${task.task_title}"吗？此操作不可撤销。`,
			confirmText: '删除',
			cancelText: '取消',
			confirmColor: '#ff4d4f'
		})
		
		if (!res.confirm) return
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.DELETE(task.id)),
				...createRequestConfig({
					method: 'DELETE',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				uni.showToast({
					title: '删除成功',
					icon: 'success'
				})
				// 重新加载任务列表和统计
				loadTasks(true)
				loadTaskStats()
			}
		} catch (error) {
			console.error('删除任务失败:', error)
			uni.showToast({
				title: error.data?.detail || '删除失败',
				icon: 'error',
				duration: 3000
			})
		}
	}
	
	// 事件处理函数
	const handleTaskCreated = (data) => {
		console.log('任务已创建:', data)
		loadTasks(true)
		loadTaskStats()
	}
	
	const handleTaskUpdated = (data) => {
		console.log('任务已更新:', data)
		// 更新对应的任务数据
		const index = tasks.value.findIndex(task => task.id === data.taskId)
		if (index > -1 && data.task) {
			tasks.value[index] = { ...tasks.value[index], ...data.task }
		} else {
			// 如果没有完整任务数据，重新加载
			loadTasks(true)
		}
		loadTaskStats()
	}
	
	const handleTaskDeleted = (data) => {
		console.log('任务已删除:', data)
		// 从列表中移除删除的任务
		tasks.value = tasks.value.filter(task => task.id !== data.taskId)
		loadTaskStats()
	}
	
	const handleTaskReviewed = (data) => {
		console.log('任务已审核:', data)
		// 更新任务状态
		const index = tasks.value.findIndex(task => task.id === data.taskId)
		if (index > -1) {
			tasks.value[index].status = data.newStatus
		}
		loadTaskStats()
	}
	
	const handleTaskAssigned = (data) => {
		console.log('任务已分配:', data)
		loadTasks(true)
		loadTaskStats()
	}
	
	// 工具函数
	const getPageTitle = () => {
		if (isInspector.value) {
			return '我的任务'
		} else {
			return '任务管理'
		}
	}
	
	const getTaskTypeText = (type) => {
		const typeMap = {
			'opening_inspection': '新站点设备安装',
			'power_issue': '断电问题',
			'transmission_issue': '传输问题',
			'gps_issue': 'GPS问题',
			'signal_issue': '信号问题'
		}
		return typeMap[type] || type
	}
	
	const getStatusText = (status) => {
		const statusMap = {
			'pending': '待分配',
			'assigned': '已分配',
			'accepted': '已接受',
			'in_progress': '进行中',
			'submitted': '已提交',
			'under_review': '待审核',
			'approved': '已批准',
			'rejected': '已驳回',
			'completed': '已完成'
		}
		return statusMap[status] || status
	}
	
	const getStatusClass = (status) => {
		return `status-${status}`
	}
	
	const getPriorityText = (priority) => {
		const priorityMap = {
			'low': '低',
			'normal': '普通',
			'high': '高',
			'urgent': '紧急'
		}
		return priorityMap[priority] || priority
	}
	
	const getPriorityClass = (priority) => {
		return `priority-${priority}`
	}
	
	const formatDate = (dateStr) => {
		if (!dateStr) return ''
		const date = new Date(dateStr)
		return date.toLocaleDateString('zh-CN', {
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	// 页面刷新管理
	const refreshData = () => {
		console.log('页面可见性变化，刷新任务数据')
		loadTasks(true)
		loadTaskStats()
	}
	
	// 暂时注释页面可见性管理
	// const { unregister } = usePageRefresh('task-list', refreshData, {
	// 	threshold: 30000 // 30秒阈值
	// })
</script>

<style scoped>
	.task-container {
		height: 100vh;
		background: #f5f5f5;
		display: flex;
		flex-direction: column;
	}
	
	/* 导航栏 */
	.custom-navbar {
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 44rpx 30rpx 20rpx;
		color: white;
	}
	
	.navbar-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
		flex: 1;
		text-align: center;
	}
	
	.add-button {
		width: 60rpx;
		height: 60rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 30rpx;
		background: rgba(255, 255, 255, 0.2);
	}
	
	.add-icon {
		font-size: 32rpx;
		color: white;
	}
	
	/* 统计卡片 */
	.stats-container {
		display: flex;
		padding: 20rpx;
		gap: 20rpx;
		background: white;
		margin-bottom: 20rpx;
	}
	
	.stat-card {
		flex: 1;
		text-align: center;
		padding: 30rpx 20rpx;
		background: white;
		border-radius: 20rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.06);
	}
	
	.stat-number {
		font-size: 48rpx;
		font-weight: bold;
		display: block;
		margin-bottom: 10rpx;
		color: #111827;
	}
	
	.stat-label {
		font-size: 24rpx;
		color: #6b7280;
	}
	
	/* 筛选器 */
	.filter-container {
		background: white;
		padding: 20rpx 0;
		margin-bottom: 20rpx;
	}
	
	.filter-scroll {
		white-space: nowrap;
	}
	
	.filter-item {
		display: inline-block;
		padding: 15rpx 30rpx;
		margin: 0 10rpx;
		background: #f8f9fa;
		color: #666;
		border-radius: 25rpx;
		font-size: 26rpx;
		transition: all 0.3s ease;
	}
	
	.filter-item.active {
		background: #f97316;
		color: white;
	}
	
	/* 任务列表 */
	.task-list {
		flex: 1;
		padding: 0 20rpx;
	}
	
	.task-item {
		background: white;
		border-radius: 20rpx;
		margin-bottom: 20rpx;
		padding: 30rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
	}
	
	.task-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 20rpx;
	}
	
	.task-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 10rpx;
		display: block;
	}
	
	.task-meta {
		display: flex;
		gap: 15rpx;
	}
	
	.task-type {
		font-size: 24rpx;
		color: #f97316;
		background: #fef3c7;
		padding: 4rpx 12rpx;
		border-radius: 12rpx;
	}
	
	.task-priority {
		font-size: 24rpx;
		padding: 4rpx 12rpx;
		border-radius: 12rpx;
	}
	
	.priority-low {
		background: #e8f5e8;
		color: #4caf50;
	}
	
	.priority-normal {
		background: #fff3e0;
		color: #ff9800;
	}
	
	.priority-high {
		background: #ffebee;
		color: #f44336;
	}
	
	.priority-urgent {
		background: #fce4ec;
		color: #e91e63;
	}
	
	.task-status {
		padding: 8rpx 16rpx;
		border-radius: 15rpx;
		font-size: 24rpx;
	}
	
	.status-pending {
		background: #fff3cd;
		color: #856404;
	}
	
	.status-assigned {
		background: #cce5ff;
		color: #0066cc;
	}
	
	.status-in_progress {
		background: #e1f5fe;
		color: #0277bd;
	}
	
	.status-under_review {
		background: #f3e5f5;
		color: #7b1fa2;
	}
	
	.status-completed {
		background: #e8f5e8;
		color: #4caf50;
	}
	
	.task-details {
		margin-bottom: 20rpx;
	}
	
	.detail-row {
		display: flex;
		align-items: center;
		margin-bottom: 12rpx;
		gap: 15rpx;
	}
	
	.detail-icon {
		font-size: 26rpx;
		width: 40rpx;
	}
	
	.detail-text {
		font-size: 26rpx;
		color: #666;
		flex: 1;
	}
	
	.task-actions {
		display: flex;
		gap: 15rpx;
		justify-content: flex-end;
	}
	
	.action-btn {
		padding: 12rpx 24rpx;
		border-radius: 20rpx;
		font-size: 24rpx;
		border: none;
	}
	
	.assign-btn {
		background: #4caf50;
		color: white;
	}
	
	.review-btn {
		background: #ff9800;
		color: white;
	}
	
	.detail-btn {
		background: #2196f3;
		color: white;
	}
	
	.delete-btn {
		background: #ff4d4f;
		color: white;
	}
	
	/* 空状态 */
	.empty-state {
		text-align: center;
		padding: 100rpx 40rpx;
	}
	
	.empty-icon {
		font-size: 120rpx;
		margin-bottom: 30rpx;
		display: block;
	}
	
	.empty-title {
		font-size: 32rpx;
		color: #333;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.empty-desc {
		font-size: 26rpx;
		color: #999;
		display: block;
	}
	
	/* 创建任务弹窗 */
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 1000;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 40rpx;
	}
	
	.create-modal {
		background: white;
		border-radius: 20rpx;
		width: 100%;
		max-width: 700rpx;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
	}
	
	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 30rpx;
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.modal-title {
		font-size: 36rpx;
		font-weight: bold;
		color: #333;
	}
	
	.modal-close {
		width: 60rpx;
		height: 60rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 30rpx;
		background: #f8f9fa;
	}
	
	.close-icon {
		font-size: 36rpx;
		color: #666;
	}
	
	.modal-content {
		flex: 1;
		padding: 30rpx;
		overflow-y: auto;
	}
	
	.form-item {
		margin-bottom: 30rpx;
	}
	
	.form-label {
		font-size: 28rpx;
		color: #333;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.form-input, .form-textarea, .picker-input {
		width: 100%;
		padding: 20rpx;
		border: 1rpx solid #e0e0e0;
		border-radius: 10rpx;
		font-size: 28rpx;
		color: #333;
		background: #fafafa;
	}
	
	.form-textarea {
		height: 120rpx;
		resize: none;
	}
	
	.picker-input {
		display: flex;
		align-items: center;
		min-height: 60rpx;
		color: #666;
	}
	
	.modal-actions {
		display: flex;
		gap: 20rpx;
		padding: 30rpx;
		border-top: 1rpx solid #f0f0f0;
	}
	
	.modal-cancel {
		flex: 1;
		padding: 25rpx;
		background: #6c757d;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	.modal-confirm {
		flex: 1;
		padding: 25rpx;
		background: #f97316;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	/* 加载更多 */
	.load-more {
		padding: 40rpx;
	}
</style>