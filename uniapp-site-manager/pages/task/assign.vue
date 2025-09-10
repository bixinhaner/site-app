<template>
	<view class="assign-container">
		<!-- 任务信息 -->
		<view class="task-info-section">
			<view class="section-title">任务信息</view>
			<view class="task-card">
				<view class="task-header">
					<text class="task-title">{{ task?.task_title }}</text>
					<view class="task-status" :class="getStatusClass(task?.status)">
						{{ getStatusText(task?.status) }}
					</view>
				</view>
				<view class="task-details">
					<view class="detail-row">
						<text class="detail-label">任务类型:</text>
						<text class="detail-value">{{ getTaskTypeText(task?.task_type) }}</text>
					</view>
					<view class="detail-row">
						<text class="detail-label">站点:</text>
						<text class="detail-value">{{ task?.site_name || '未知站点' }}</text>
					</view>
					<view class="detail-row">
						<text class="detail-label">优先级:</text>
						<text class="detail-value" :class="getPriorityClass(task?.priority)">
							{{ getPriorityText(task?.priority) }}
						</text>
					</view>
					<view class="detail-row" v-if="task?.task_description">
						<text class="detail-label">描述:</text>
						<text class="detail-value">{{ task?.task_description }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 分配表单 -->
		<view class="assign-section">
			<view class="section-title">分配任务</view>
			<view class="form-card">
				<view class="form-item">
					<text class="form-label">选择工程师</text>
					<picker :value="assignForm.engineerIndex" :range="engineerOptions" range-key="full_name" @change="onEngineerChange">
						<view class="picker-input">
							{{ engineerOptions[assignForm.engineerIndex]?.full_name || '请选择工程师' }}
						</view>
					</picker>
				</view>
				
				<view class="form-item">
					<text class="form-label">截止时间</text>
					<picker 
						mode="datetime" 
						:value="assignForm.dueDate" 
						:start="minDate"
						:end="maxDate"
						@change="onDueDateChange">
						<view class="picker-input">
							{{ formatDisplayDate(assignForm.dueDate) || '请选择截止时间' }}
						</view>
					</picker>
				</view>
				
				<view class="form-item">
					<text class="form-label">分配说明</text>
					<textarea 
						class="form-textarea" 
						v-model="assignForm.notes" 
						placeholder="请输入分配说明或特殊要求"
						maxlength="500"
					/>
					<text class="char-count">{{ assignForm.notes.length }}/500</text>
				</view>
			</view>
		</view>
		
		<!-- 历史分配记录 -->
		<view class="history-section" v-if="assignmentHistory.length > 0">
			<view class="section-title">分配历史</view>
			<view class="history-list">
				<view class="history-item" v-for="history in assignmentHistory" :key="history.id">
					<view class="history-header">
						<text class="assignee-name">{{ history.assigned_to_name }}</text>
						<text class="assign-time">{{ formatDateTime(history.created_at) }}</text>
					</view>
					<view class="history-details">
						<text class="assigner">分配人: {{ history.assigned_by_name }}</text>
						<text class="history-notes" v-if="history.notes">{{ history.notes }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 操作按钮 -->
		<view class="action-buttons">
			<button class="cancel-btn" @click="goBack">取消</button>
			<button 
				class="assign-btn" 
				@click="assignTask"
				:disabled="!canAssign"
			>
				确认分配
			</button>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-overlay" v-if="loading">
			<uni-load-more status="loading"></uni-load-more>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	
	const userStore = useUserStore()
	
	// 响应式数据
	const loading = ref(false)
	const taskId = ref(null)
	const task = ref(null)
	const engineerOptions = ref([])
	const assignmentHistory = ref([])
	
	const assignForm = ref({
		engineerIndex: 0,
		dueDate: '',
		notes: ''
	})
	
	// 日期范围设置
	const minDate = ref('')
	const maxDate = ref('')
	
	// 计算属性
	const canAssign = computed(() => {
		return assignForm.value.engineerIndex >= 0 && 
			   engineerOptions.value[assignForm.value.engineerIndex] &&
			   assignForm.value.dueDate
	})
	
	// 页面生命周期
	onLoad((options) => {
		taskId.value = options.taskId
		initializeDateRange()
		
		if (taskId.value) {
			loadTaskDetail()
			loadEngineers()
			loadAssignmentHistory()
		} else {
			uni.showToast({
				title: '参数错误',
				icon: 'error'
			})
			setTimeout(goBack, 1500)
		}
	})
	
	// 初始化日期范围
	const initializeDateRange = () => {
		const now = new Date()
		const currentYear = now.getFullYear()
		const currentMonth = String(now.getMonth() + 1).padStart(2, '0')
		const currentDay = String(now.getDate()).padStart(2, '0')
		const currentHour = String(now.getHours()).padStart(2, '0')
		const currentMinute = String(now.getMinutes()).padStart(2, '0')
		
		// 最小时间是当前时间
		minDate.value = `${currentYear}-${currentMonth}-${currentDay} ${currentHour}:${currentMinute}`
		
		// 最大时间是一年后
		const maxYear = currentYear + 1
		maxDate.value = `${maxYear}-${currentMonth}-${currentDay} ${currentHour}:${currentMinute}`
		
		// 设置默认截止时间为7天后
		const defaultDate = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
		const defaultYear = defaultDate.getFullYear()
		const defaultMonth = String(defaultDate.getMonth() + 1).padStart(2, '0')
		const defaultDay = String(defaultDate.getDate()).padStart(2, '0')
		assignForm.value.dueDate = `${defaultYear}-${defaultMonth}-${defaultDay} ${currentHour}:${currentMinute}`
	}
	
	// 方法
	const loadTaskDetail = async () => {
		try {
			loading.value = true
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.DETAIL(taskId.value)),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				}
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
	
	const loadEngineers = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.USERS.LIST),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				},
				data: {
					role: 'inspector'
				}
			})
			
			if (response.statusCode === 200) {
				engineerOptions.value = response.data
			}
		} catch (error) {
			console.error('加载工程师列表失败:', error)
		}
	}
	
	const loadAssignmentHistory = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.ASSIGNMENTS(taskId.value)),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				}
			})
			
			if (response.statusCode === 200) {
				assignmentHistory.value = response.data
			}
		} catch (error) {
			console.error('加载分配历史失败:', error)
		}
	}
	
	const onEngineerChange = (e) => {
		assignForm.value.engineerIndex = e.detail.value
	}
	
	const onDueDateChange = (e) => {
		assignForm.value.dueDate = e.detail.value
	}
	
	const assignTask = async () => {
		if (!canAssign.value) return
		
		try {
			loading.value = true
			
			const selectedEngineer = engineerOptions.value[assignForm.value.engineerIndex]
			
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.ASSIGN(taskId.value)),
				method: 'POST',
				header: {
					'Authorization': `Bearer ${userStore.token}`,
					'Content-Type': 'application/json'
				},
				data: {
					assigned_to: selectedEngineer.id,
					due_date: assignForm.value.dueDate,
					notes: assignForm.value.notes
				}
			})
			
			if (response.statusCode === 200 || response.statusCode === 201) {
				uni.showToast({
					title: '分配成功',
					icon: 'success'
				})
				
				// 发送事件通知
				uni.$emit('taskAssigned', {
					taskId: taskId.value,
					task: response.data
				})
				
				setTimeout(() => {
					uni.navigateBack()
				}, 1500)
			}
		} catch (error) {
			console.error('分配任务失败:', error)
			uni.showToast({
				title: '分配失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const goBack = () => {
		uni.navigateBack()
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
	
	const formatDateTime = (dateStr) => {
		if (!dateStr) return ''
		const date = new Date(dateStr)
		return date.toLocaleString('zh-CN', {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	const formatDisplayDate = (dateStr) => {
		if (!dateStr) return ''
		// 直接显示选择的日期时间
		const date = new Date(dateStr)
		const year = date.getFullYear()
		const month = String(date.getMonth() + 1).padStart(2, '0')
		const day = String(date.getDate()).padStart(2, '0')
		const hour = String(date.getHours()).padStart(2, '0')
		const minute = String(date.getMinutes()).padStart(2, '0')
		
		return `${year}-${month}-${day} ${hour}:${minute}`
	}
</script>

<style scoped>
	.assign-container {
		min-height: 100vh;
		background: #f5f5f5;
		padding-bottom: 120rpx;
	}
	
	/* 通用样式 */
	.section-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 20rpx;
		padding: 30rpx 30rpx 0;
	}
	
	/* 任务信息 */
	.task-info-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.task-card {
		margin: 0 30rpx 30rpx;
		padding: 30rpx;
		background: #f8f9fa;
		border-radius: 20rpx;
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
		flex: 1;
		margin-right: 20rpx;
	}
	
	.task-status {
		padding: 8rpx 16rpx;
		border-radius: 15rpx;
		font-size: 24rpx;
		font-weight: 500;
	}
	
	.status-pending {
		background: #fff3cd;
		color: #856404;
	}
	
	.task-details {
		
	}
	
	.detail-row {
		display: flex;
		margin-bottom: 12rpx;
		align-items: flex-start;
	}
	
	.detail-label {
		font-size: 26rpx;
		color: #666;
		width: 120rpx;
		flex-shrink: 0;
	}
	
	.detail-value {
		font-size: 26rpx;
		color: #333;
		flex: 1;
		word-break: break-all;
	}
	
	.priority-high {
		color: #dc2626 !important;
	}
	
	.priority-normal {
		color: #059669 !important;
	}
	
	.priority-low {
		color: #6b7280 !important;
	}
	
	.priority-urgent {
		color: #e91e63 !important;
	}
	
	/* 分配表单 */
	.assign-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.form-card {
		margin: 0 30rpx 30rpx;
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
	
	.picker-input {
		padding: 25rpx;
		background: #f8f9fa;
		border: 1rpx solid #e0e0e0;
		border-radius: 10rpx;
		font-size: 28rpx;
		color: #333;
		min-height: 60rpx;
		display: flex;
		align-items: center;
	}
	
	.form-textarea {
		width: 100%;
		padding: 25rpx;
		background: #f8f9fa;
		border: 1rpx solid #e0e0e0;
		border-radius: 10rpx;
		font-size: 28rpx;
		color: #333;
		min-height: 150rpx;
		box-sizing: border-box;
	}
	
	.char-count {
		font-size: 24rpx;
		color: #999;
		text-align: right;
		margin-top: 10rpx;
		display: block;
	}
	
	/* 历史记录 */
	.history-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.history-list {
		margin: 0 30rpx 30rpx;
	}
	
	.history-item {
		padding: 25rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
		margin-bottom: 15rpx;
	}
	
	.history-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10rpx;
	}
	
	.assignee-name {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
	}
	
	.assign-time {
		font-size: 24rpx;
		color: #999;
	}
	
	.history-details {
		
	}
	
	.assigner {
		font-size: 24rpx;
		color: #666;
		margin-bottom: 8rpx;
		display: block;
	}
	
	.history-notes {
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
		gap: 20rpx;
		box-shadow: 0 -4rpx 20rpx rgba(0, 0, 0, 0.1);
	}
	
	.cancel-btn {
		flex: 1;
		padding: 25rpx;
		background: #6c757d;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	.assign-btn {
		flex: 2;
		padding: 25rpx;
		background: #f97316;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	.assign-btn:disabled {
		background: #ccc;
		color: #999;
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