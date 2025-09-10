<template>
	<view class="detail-container">
		<!-- 任务基本信息 -->
		<view class="task-info-section">
			<view class="task-header">
				<text class="task-title">{{ task?.task_title }}</text>
				<view class="task-status" :class="getStatusClass(task?.status)">
					{{ getStatusText(task?.status) }}
				</view>
			</view>
			
			<view class="task-meta">
				<view class="meta-row">
					<text class="meta-label">任务类型:</text>
					<text class="meta-value">{{ getTaskTypeText(task?.task_type) }}</text>
				</view>
				<view class="meta-row">
					<text class="meta-label">站点:</text>
					<text class="meta-value">{{ task?.site_name || '未知站点' }}</text>
				</view>
				<view class="meta-row">
					<text class="meta-label">优先级:</text>
					<text class="meta-value" :class="getPriorityClass(task?.priority)">
						{{ getPriorityText(task?.priority) }}
					</text>
				</view>
				<view class="meta-row">
					<text class="meta-label">分配给:</text>
					<text class="meta-value">{{ task?.assignee_name || '未分配' }}</text>
				</view>
				<view class="meta-row">
					<text class="meta-label">创建时间:</text>
					<text class="meta-value">{{ formatDateTime(task?.created_at) }}</text>
				</view>
				<view class="meta-row" v-if="task?.due_date">
					<text class="meta-label">截止时间:</text>
					<text class="meta-value" :class="getDueDateClass(task?.due_date)">
						{{ formatDateTime(task?.due_date) }}
					</text>
				</view>
			</view>
			
			<view class="task-description" v-if="task?.task_description">
				<text class="desc-label">任务描述:</text>
				<text class="desc-content">{{ task?.task_description }}</text>
			</view>
		</view>
		
		<!-- 任务进度 -->
		<view class="progress-section">
			<view class="section-title">
				<text>任务进度</text>
				<text class="progress-percent">{{ getProgressPercent() }}%</text>
			</view>
			<view class="progress-bar">
				<view class="progress-fill" :style="{ width: getProgressPercent() + '%' }"></view>
			</view>
			<view class="progress-steps">
				<view class="step-item" 
					v-for="step in progressSteps" 
					:key="step.key"
					:class="getStepClass(step.key)">
					<view class="step-dot"></view>
					<text class="step-text">{{ step.text }}</text>
				</view>
			</view>
		</view>
		
		<!-- 工作记录 -->
		<view class="work-section" v-if="task?.progress_notes">
			<view class="section-title">工作记录</view>
			<view class="work-content">
				<text class="work-text">{{ task?.progress_notes }}</text>
				<text class="work-time" v-if="task?.updated_at">
					更新时间: {{ formatDateTime(task?.updated_at) }}
				</text>
			</view>
		</view>
		
		<!-- 检查记录 -->
		<view class="inspection-section" v-if="inspectionRecords.length > 0">
			<view class="section-title">检查记录</view>
			<view class="inspection-list">
				<view class="inspection-item" 
					v-for="record in inspectionRecords" 
					:key="record.id"
					@click="viewInspection(record)">
					<view class="inspection-info">
						<text class="inspection-type">{{ getInspectionTypeText(record.inspection_type) }}</text>
						<text class="inspection-time">{{ formatDateTime(record.created_at) }}</text>
					</view>
					<view class="inspection-status" :class="getInspectionStatusClass(record.status)">
						{{ getInspectionStatusText(record.status) }}
					</view>
				</view>
			</view>
		</view>
		
		<!-- 现场照片 -->
		<view class="photos-section" v-if="taskPhotos.length > 0">
			<view class="section-title">现场照片</view>
			<view class="photos-grid">
				<view class="photo-item" 
					v-for="photo in taskPhotos" 
					:key="photo.id"
					@click="previewPhoto(photo)">
					<image class="photo-image" :src="photo.photo_url" mode="aspectFill"></image>
					<view class="photo-overlay">
						<text class="photo-desc">{{ photo.description || '无描述' }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 操作历史 -->
		<view class="history-section" v-if="taskHistory.length > 0">
			<view class="section-title">操作历史</view>
			<view class="history-timeline">
				<view class="timeline-item" v-for="history in taskHistory" :key="history.id">
					<view class="timeline-dot" :class="getHistoryTypeClass(history.action)"></view>
					<view class="timeline-content">
						<view class="timeline-header">
							<text class="timeline-action">{{ getHistoryActionText(history.action) }}</text>
							<text class="timeline-time">{{ formatDateTime(history.created_at) }}</text>
						</view>
						<text class="timeline-user">{{ history.operator_name }}</text>
						<text class="timeline-notes" v-if="history.notes">{{ history.notes }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 操作按钮 -->
		<view class="action-buttons" v-if="showActionButtons">
			<button class="action-btn secondary" @click="goBack">返回</button>
			<button class="action-btn assign" 
				@click="assignTask" 
				v-if="canAssign">
				分配任务
			</button>
			<button class="action-btn review" 
				@click="reviewTask" 
				v-if="canReview">
				审核任务
			</button>
			<button class="action-btn accept" 
				@click="acceptTask" 
				v-if="canAccept">
				接受任务
			</button>
			<button class="action-btn start" 
				@click="startTask" 
				v-if="canStart">
				开始执行
			</button>
			<button class="action-btn inspect" 
				@click="startInspection" 
				v-if="canInspect">
				开始检查
			</button>
			<button class="action-btn submit" 
				@click="submitTask" 
				v-if="canSubmit">
				提交任务
			</button>
			<button class="action-btn progress" 
				@click="updateProgress" 
				v-if="canUpdateProgress">
				更新进度
			</button>
			<button class="action-btn delete" 
				@click="deleteTask" 
				v-if="canDelete">
				删除任务
			</button>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-overlay" v-if="loading">
			<uni-load-more status="loading"></uni-load-more>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed } from 'vue'
	import { onLoad, onShow, onUnload } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	
	const userStore = useUserStore()
	
	// 响应式数据
	const loading = ref(false)
	const taskId = ref(null)
	const task = ref(null)
	const inspectionRecords = ref([])
	const taskPhotos = ref([])
	const taskHistory = ref([])
	
	const progressSteps = [
		{ key: 'created', text: '已创建' },
		{ key: 'assigned', text: '已分配' },
		{ key: 'in_progress', text: '进行中' },
		{ key: 'submitted', text: '已提交' },
		{ key: 'completed', text: '已完成' }
	]
	
	// 计算属性
	const showActionButtons = computed(() => {
		return canAssign.value || canReview.value || canUpdateProgress.value || canDelete.value || 
			   canAccept.value || canStart.value || canInspect.value || canSubmit.value
	})
	
	const canAssign = computed(() => {
		const role = userStore.userInfo?.role
		return (role === 'admin' || role === 'manager') && task.value?.status === 'pending'
	})
	
	const canReview = computed(() => {
		const role = userStore.userInfo?.role
		return (role === 'admin' || role === 'manager') && 
		       (task.value?.status === 'under_review' || task.value?.status === 'submitted')
	})
	
	const canUpdateProgress = computed(() => {
		const role = userStore.userInfo?.role
		const userId = userStore.userInfo?.id
		return (role === 'inspector' && task.value?.assigned_to === userId) ||
			   (role === 'admin' || role === 'manager')
	})
	
	const canDelete = computed(() => {
		const role = userStore.userInfo?.role
		if (role !== 'admin') return false
		// 只能删除待分配、已分配或已驳回的任务
		return task.value && ['pending', 'assigned', 'rejected'].includes(task.value.status)
	})
	
	const canAccept = computed(() => {
		const role = userStore.userInfo?.role
		const userId = userStore.userInfo?.id
		return role === 'inspector' && 
			   task.value?.assigned_to === userId && 
			   task.value?.status === 'assigned'
	})
	
	const canStart = computed(() => {
		const role = userStore.userInfo?.role
		const userId = userStore.userInfo?.id
		return role === 'inspector' && 
			   task.value?.assigned_to === userId && 
			   (task.value?.status === 'accepted' || task.value?.status === 'rejected')
	})
	
	const canInspect = computed(() => {
		const role = userStore.userInfo?.role
		const userId = userStore.userInfo?.id
		return role === 'inspector' && 
			   task.value?.assigned_to === userId && 
			   (task.value?.status === 'in_progress' || task.value?.status === 'rejected')
	})
	
	const canSubmit = computed(() => {
		const role = userStore.userInfo?.role
		const userId = userStore.userInfo?.id
		return role === 'inspector' && 
			   task.value?.assigned_to === userId && 
			   task.value?.status === 'in_progress'
	})
	
	// 页面生命周期
	onLoad((options) => {
		taskId.value = options.taskId
		if (taskId.value) {
			loadTaskDetail()
			loadInspectionRecords()
			loadTaskPhotos()
			loadTaskHistory()
		} else {
			uni.showToast({
				title: '参数错误',
				icon: 'error'
			})
			setTimeout(goBack, 1500)
		}
	})
	
	// 页面显示时刷新数据
	onShow(() => {
		// 避免初次加载时重复刷新
		if (task.value && taskId.value) {
			loadTaskDetail()
			loadInspectionRecords()
		}
	})
	
	// 页面销毁时发送事件通知上级页面
	onUnload(() => {
		if (task.value) {
			uni.$emit('taskDetailClosed', {
				taskId: taskId.value,
				task: task.value
			})
		}
	})
	
	// 方法
	const loadTaskDetail = async () => {
		try {
			loading.value = true
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.DETAIL(taskId.value)),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				task.value = response.data
			}
		} catch (error) {
			console.error('加载任务详情失败:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const loadInspectionRecords = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.LIST),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
					data: {
						task_id: taskId.value
					}
				})
			})
			
			if (response.statusCode === 200) {
				inspectionRecords.value = response.data
			}
		} catch (error) {
			console.error('加载检查记录失败:', error)
		}
	}
	
	const loadTaskPhotos = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.PHOTOS(taskId.value)),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				taskPhotos.value = response.data
			}
		} catch (error) {
			console.error('加载任务照片失败:', error)
		}
	}
	
	const loadTaskHistory = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.HISTORY(taskId.value)),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				taskHistory.value = response.data
			}
		} catch (error) {
			console.error('加载任务历史失败:', error)
		}
	}
	
	const getProgressPercent = () => {
		if (!task.value?.status) return 0
		
		const statusProgress = {
			'pending': 0,
			'assigned': 20,
			'accepted': 25,
			'in_progress': 50,
			'submitted': 75,
			'under_review': 85,
			'approved': 95,
			'completed': 100,
			'rejected': 50
		}
		
		return statusProgress[task.value.status] || 0
	}
	
	const getStepClass = (stepKey) => {
		const currentStatus = task.value?.status
		const statusOrder = ['pending', 'assigned', 'in_progress', 'submitted', 'completed']
		const stepOrder = ['created', 'assigned', 'in_progress', 'submitted', 'completed']
		
		const currentIndex = statusOrder.indexOf(currentStatus)
		const stepIndex = stepOrder.indexOf(stepKey)
		
		if (stepIndex <= currentIndex) {
			return 'step-completed'
		} else {
			return 'step-pending'
		}
	}
	
	const getDueDateClass = (dueDate) => {
		if (!dueDate) return ''
		
		const now = new Date()
		const due = new Date(dueDate)
		const diff = due.getTime() - now.getTime()
		const hours = diff / (1000 * 60 * 60)
		
		if (hours < 0) return 'due-overdue'
		if (hours < 24) return 'due-urgent'
		if (hours < 72) return 'due-warning'
		return ''
	}
	
	const previewPhoto = (photo) => {
		const urls = taskPhotos.value.map(p => p.photo_url)
		const current = photo.photo_url
		
		uni.previewImage({
			urls: urls,
			current: current
		})
	}
	
	const viewInspection = (record) => {
		uni.navigateTo({
			url: `/pages/inspection/detail?id=${record.id}`
		})
	}
	
	const assignTask = () => {
		uni.navigateTo({
			url: `/pages/task/assign?taskId=${taskId.value}`
		})
	}
	
	const reviewTask = () => {
		uni.navigateTo({
			url: `/pages/task/review?taskId=${taskId.value}`
		})
	}
	
	const updateProgress = () => {
		uni.showModal({
			title: '更新进度',
			content: '进度更新功能正在开发中',
			showCancel: false
		})
	}
	
	const goBack = () => {
		uni.navigateBack()
	}
	
	const acceptTask = async () => {
		try {
			loading.value = true
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.STATUS(taskId.value)),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: {
						status: 'accepted',
						comments: '接受任务'
					}
				})
			})
			
			if (response.statusCode === 200) {
				uni.showToast({
					title: '任务已接受',
					icon: 'success'
				})
				// 重新加载任务详情
				await loadTaskDetail()
				// 发送事件通知
				uni.$emit('taskUpdated', {
					taskId: taskId.value,
					task: response.data
				})
			}
		} catch (error) {
			console.error('接受任务失败:', error)
			uni.showToast({
				title: error.data?.detail || '操作失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const startTask = async () => {
		try {
			loading.value = true
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.STATUS(taskId.value)),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: {
						status: 'in_progress',
						comments: '开始执行任务'
					}
				})
			})
			
			if (response.statusCode === 200) {
				uni.showToast({
					title: '任务已开始',
					icon: 'success'
				})
				// 重新加载任务详情
				await loadTaskDetail()
				// 发送事件通知
				uni.$emit('taskUpdated', {
					taskId: taskId.value,
					task: response.data
				})
			}
		} catch (error) {
			console.error('开始任务失败:', error)
			uni.showToast({
				title: error.data?.detail || '操作失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const startInspection = async () => {
		try {
			// 检查是否已经有检查记录
			if (inspectionRecords.value.length === 0) {
				// 创建新的检查记录
				loading.value = true
				const response = await uni.request({
					url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.CREATE),
					...createRequestConfig({
						method: 'POST',
						headers: getAuthHeaders(userStore.token),
						data: {
							site_id: task.value.site_id,
							inspection_type: 'OPENING',
							task_id: taskId.value,
							notes: '开始检查任务',
							location: '现场检查',
							weather: '正常'
						}
					})
				})
				
				if (response.statusCode === 200) {
					const inspection = response.data
					uni.showToast({
						title: '检查记录已创建',
						icon: 'success'
					})
					
					// 跳转到检查详情页面
					setTimeout(() => {
						uni.navigateTo({
							url: `/pages/inspection/detail?id=${inspection.id}`
						})
					}, 1000)
				} else {
					throw new Error(response.data?.detail || '创建检查记录失败')
				}
			} else {
				// 已有检查记录
				const latestInspection = inspectionRecords.value[0]
				
				// 如果任务被驳回且检查记录已提交，需要重置检查记录
				if (task.value?.status === 'rejected' && latestInspection.status === 'submitted') {
					loading.value = true
					
					// 调用重置API
					const resetResponse = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.DETAIL(latestInspection.id) + '/reset'),
						...createRequestConfig({
							method: 'POST',
							headers: getAuthHeaders(userStore.token)
						})
					})
					
					if (resetResponse.statusCode === 200) {
						uni.showToast({
							title: '检查记录已重置，可重新编辑',
							icon: 'success'
						})
						
						// 重新加载检查记录
						await loadInspectionRecords()
						
						// 跳转到检查详情页面
						setTimeout(() => {
							uni.navigateTo({
								url: `/pages/inspection/detail?id=${latestInspection.id}`
							})
						}, 1000)
					} else {
						throw new Error(resetResponse.data?.detail || '重置检查记录失败')
					}
				} else {
					// 直接跳转到最新的检查记录
					uni.navigateTo({
						url: `/pages/inspection/detail?id=${latestInspection.id}`
					})
				}
			}
		} catch (error) {
			console.error('开始检查失败:', error)
			uni.showToast({
				title: error.message || '操作失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const submitTask = async () => {
		// 检查是否有已完成的检查记录
		const completedInspections = inspectionRecords.value.filter(
			record => record.status === 'completed' || record.status === 'submitted'
		)
		
		if (completedInspections.length === 0) {
			uni.showModal({
				title: '提交失败',
				content: '请先完成检查记录再提交任务',
				showCancel: false
			})
			return
		}
		
		try {
			loading.value = true
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.STATUS(taskId.value)),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: {
						status: 'submitted',
						comments: '任务检查完成，提交审核'
					}
				})
			})
			
			if (response.statusCode === 200) {
				uni.showToast({
					title: '任务已提交',
					icon: 'success'
				})
				// 重新加载任务详情
				await loadTaskDetail()
				// 发送事件通知
				uni.$emit('taskUpdated', {
					taskId: taskId.value,
					task: response.data
				})
			}
		} catch (error) {
			console.error('提交任务失败:', error)
			uni.showToast({
				title: error.data?.detail || '操作失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const deleteTask = async () => {
		// 显示确认对话框
		const res = await uni.showModal({
			title: '确认删除',
			content: `确定要删除任务"${task.value?.task_title}"吗？此操作不可撤销。`,
			confirmText: '删除',
			cancelText: '取消',
			confirmColor: '#ff4d4f'
		})
		
		if (!res.confirm) return
		
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.DELETE(taskId.value)),
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
				// 发送事件通知
				uni.$emit('taskDeleted', {
					taskId: taskId.value
				})
				// 返回任务列表
				setTimeout(() => {
					uni.navigateBack()
				}, 1500)
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
	
	// 工具函数
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
	
	const getInspectionTypeText = (type) => {
		const typeMap = {
			'OPENING': '新站点设备安装',
			'MAINTENANCE': '维护检查'
		}
		return typeMap[type] || type
	}
	
	const getInspectionStatusText = (status) => {
		const statusMap = {
			'pending': '待处理',
			'in_progress': '进行中',
			'completed': '已完成',
			'failed': '失败'
		}
		return statusMap[status] || status
	}
	
	const getInspectionStatusClass = (status) => {
		return `inspection-status-${status}`
	}
	
	const getHistoryTypeClass = (action) => {
		return `history-${action}`
	}
	
	const getHistoryActionText = (action) => {
		const actionMap = {
			'created': '创建任务',
			'assigned': '分配任务',
			'accepted': '接受任务',
			'started': '开始执行',
			'submitted': '提交完成',
			'reviewed': '审核任务',
			'approved': '批准任务',
			'rejected': '驳回任务',
			'completed': '完成任务'
		}
		return actionMap[action] || action
	}
	
	const formatDateTime = (dateStr) => {
		if (!dateStr) return '-'
		const date = new Date(dateStr)
		return date.toLocaleString('zh-CN', {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		})
	}
</script>

<style scoped>
	.detail-container {
		min-height: 100vh;
		background: #f5f5f5;
		padding-bottom: 120rpx;
	}
	
	/* 任务信息 */
	.task-info-section {
		background: white;
		margin-bottom: 20rpx;
		padding: 30rpx;
	}
	
	.task-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 30rpx;
	}
	
	.task-title {
		font-size: 36rpx;
		font-weight: bold;
		color: #333;
		flex: 1;
		margin-right: 20rpx;
	}
	
	.task-status {
		padding: 10rpx 20rpx;
		border-radius: 20rpx;
		font-size: 24rpx;
		font-weight: 500;
	}
	
	.status-pending { background: #fff3cd; color: #856404; }
	.status-assigned { background: #cce5ff; color: #0066cc; }
	.status-in_progress { background: #e1f5fe; color: #0277bd; }
	.status-under_review { background: #f3e5f5; color: #7b1fa2; }
	.status-completed { background: #e8f5e8; color: #4caf50; }
	
	.task-meta {
		margin-bottom: 30rpx;
	}
	
	.meta-row {
		display: flex;
		margin-bottom: 15rpx;
		align-items: flex-start;
	}
	
	.meta-label {
		font-size: 28rpx;
		color: #666;
		width: 150rpx;
		flex-shrink: 0;
	}
	
	.meta-value {
		font-size: 28rpx;
		color: #333;
		flex: 1;
		word-break: break-all;
	}
	
	.priority-high { color: #dc2626 !important; }
	.priority-normal { color: #059669 !important; }
	.priority-low { color: #6b7280 !important; }
	.priority-urgent { color: #e91e63 !important; }
	
	.due-overdue { color: #dc2626 !important; }
	.due-urgent { color: #f59e0b !important; }
	.due-warning { color: #eab308 !important; }
	
	.task-description {
		
	}
	
	.desc-label {
		font-size: 28rpx;
		color: #666;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.desc-content {
		font-size: 28rpx;
		color: #333;
		line-height: 1.6;
		padding: 20rpx;
		background: #f8f9fa;
		border-radius: 10rpx;
	}
	
	/* 通用样式 */
	.section-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 20rpx;
		padding: 30rpx 30rpx 0;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.progress-percent {
		font-size: 28rpx;
		color: #667eea;
	}
	
	/* 进度部分 */
	.progress-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.progress-bar {
		margin: 0 30rpx 30rpx;
		height: 8rpx;
		background: #f0f0f0;
		border-radius: 4rpx;
		overflow: hidden;
	}
	
	.progress-fill {
		height: 100%;
		background: linear-gradient(135deg, #f97316, #fb923c);
		transition: width 0.3s ease;
	}
	
	.progress-steps {
		display: flex;
		justify-content: space-between;
		margin: 0 30rpx 30rpx;
		padding-top: 20rpx;
	}
	
	.step-item {
		flex: 1;
		text-align: center;
		position: relative;
	}
	
	.step-dot {
		width: 20rpx;
		height: 20rpx;
		border-radius: 50%;
		margin: 0 auto 10rpx;
	}
	
	.step-completed .step-dot {
		background: #f97316;
	}
	
	.step-pending .step-dot {
		background: #ddd;
	}
	
	.step-text {
		font-size: 22rpx;
		color: #666;
	}
	
	.step-completed .step-text {
		color: #333;
	}
	
	/* 工作记录 */
	.work-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.work-content {
		margin: 0 30rpx 30rpx;
		padding: 25rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
	}
	
	.work-text {
		font-size: 28rpx;
		color: #333;
		line-height: 1.6;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.work-time {
		font-size: 24rpx;
		color: #999;
	}
	
	/* 检查记录 */
	.inspection-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.inspection-list {
		margin: 0 30rpx 30rpx;
	}
	
	.inspection-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 25rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
		margin-bottom: 15rpx;
	}
	
	.inspection-info {
		
	}
	
	.inspection-type {
		font-size: 28rpx;
		color: #333;
		margin-bottom: 8rpx;
		display: block;
	}
	
	.inspection-time {
		font-size: 24rpx;
		color: #999;
	}
	
	.inspection-status {
		padding: 8rpx 16rpx;
		border-radius: 12rpx;
		font-size: 24rpx;
	}
	
	.inspection-status-completed { background: #d1fae5; color: #059669; }
	.inspection-status-in_progress { background: #dbeafe; color: #2563eb; }
	.inspection-status-pending { background: #fff3cd; color: #856404; }
	
	/* 照片网格 */
	.photos-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.photos-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 15rpx;
		margin: 0 30rpx 30rpx;
	}
	
	.photo-item {
		position: relative;
		aspect-ratio: 1;
		border-radius: 15rpx;
		overflow: hidden;
	}
	
	.photo-image {
		width: 100%;
		height: 100%;
	}
	
	.photo-overlay {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
		padding: 20rpx 15rpx 15rpx;
	}
	
	.photo-desc {
		font-size: 22rpx;
		color: white;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	/* 操作历史 */
	.history-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.history-timeline {
		margin: 0 30rpx 30rpx;
		position: relative;
	}
	
	.history-timeline::before {
		content: '';
		position: absolute;
		left: 25rpx;
		top: 0;
		bottom: 0;
		width: 4rpx;
		background: #e0e0e0;
	}
	
	.timeline-item {
		position: relative;
		padding-left: 80rpx;
		margin-bottom: 40rpx;
	}
	
	.timeline-dot {
		position: absolute;
		left: 15rpx;
		top: 15rpx;
		width: 20rpx;
		height: 20rpx;
		border-radius: 50%;
		background: #f97316;
		border: 4rpx solid white;
		box-shadow: 0 0 0 2rpx #e0e0e0;
	}
	
	.timeline-content {
		
	}
	
	.timeline-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8rpx;
	}
	
	.timeline-action {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
	}
	
	.timeline-time {
		font-size: 24rpx;
		color: #999;
	}
	
	.timeline-user {
		font-size: 26rpx;
		color: #666;
		margin-bottom: 8rpx;
		display: block;
	}
	
	.timeline-notes {
		font-size: 26rpx;
		color: #333;
		line-height: 1.4;
	}
	
	/* 操作按钮 */
	.action-buttons {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: white;
		padding: 30rpx;
		display: flex;
		gap: 15rpx;
		box-shadow: 0 -4rpx 20rpx rgba(0, 0, 0, 0.1);
	}
	
	.action-btn {
		flex: 1;
		padding: 25rpx;
		border: none;
		border-radius: 15rpx;
		font-size: 28rpx;
		font-weight: 500;
	}
	
	.action-btn.secondary {
		background: #6c757d;
		color: white;
	}
	
	.action-btn.assign {
		background: #28a745;
		color: white;
	}
	
	.action-btn.review {
		background: #ff9800;
		color: white;
	}
	
	.action-btn.progress {
		background: #f97316;
		color: white;
	}
	
	.action-btn.accept {
		background: #52c41a;
		color: white;
	}
	
	.action-btn.start {
		background: #1890ff;
		color: white;
	}
	
	.action-btn.inspect {
		background: #722ed1;
		color: white;
	}
	
	.action-btn.submit {
		background: #f5222d;
		color: white;
	}
	
	.action-btn.delete {
		background: #ff4d4f;
		color: white;
	}
	
	/* 加载状态 */
	.loading-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(255, 255, 255, 0.8);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}
</style>