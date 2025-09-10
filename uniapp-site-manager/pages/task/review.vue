<template>
	<view class="review-container">
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
						<text class="detail-label">分配给:</text>
						<text class="detail-value">{{ task?.assignee_name || '-' }}</text>
					</view>
					<view class="detail-row">
						<text class="detail-label">优先级:</text>
						<text class="detail-value" :class="getPriorityClass(task?.priority)">
							{{ getPriorityText(task?.priority) }}
						</text>
					</view>
					<view class="detail-row">
						<text class="detail-label">提交时间:</text>
						<text class="detail-value">{{ formatDateTime(task?.submitted_at) }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 提交内容 -->
		<view class="submission-section">
			<view class="section-title">提交内容</view>
			<view class="submission-card">
				<view class="progress-notes" v-if="task?.progress_notes">
					<text class="notes-label">工作说明:</text>
					<text class="notes-content">{{ task?.progress_notes }}</text>
				</view>
				
				<!-- 检查记录 -->
				<view class="inspection-records" v-if="inspectionRecords.length > 0">
					<text class="records-label">检查记录:</text>
					<view class="records-list">
						<view class="record-item" v-for="record in inspectionRecords" :key="record.id">
							<view class="record-header">
								<text class="record-type">{{ getInspectionTypeText(record.inspection_type) }}</text>
								<text class="record-time">{{ formatDateTime(record.created_at) }}</text>
							</view>
							<view class="record-status" :class="getInspectionStatusClass(record.status)">
								{{ getInspectionStatusText(record.status) }}
							</view>
						</view>
					</view>
				</view>
				
				<!-- 照片记录 -->
				<view class="photos-section" v-if="taskPhotos.length > 0">
					<text class="photos-label">现场照片:</text>
					<scroll-view class="photos-scroll" scroll-x>
						<view class="photo-item" v-for="photo in taskPhotos" :key="photo.id" @click="previewPhoto(photo)">
							<image class="photo-image" :src="photo.photo_url" mode="aspectFill"></image>
							<text class="photo-desc">{{ photo.description || '无描述' }}</text>
						</view>
					</scroll-view>
				</view>
			</view>
		</view>
		
		<!-- 审核表单 -->
		<view class="review-section">
			<view class="section-title">任务审核</view>
			<view class="form-card">
				<view class="form-item">
					<text class="form-label">审核结果</text>
					<view class="radio-group">
						<view class="radio-item" @click="setReviewResult('approved')">
							<view class="radio-icon" :class="{ active: reviewForm.result === 'approved' }">
								<text v-if="reviewForm.result === 'approved'">✓</text>
							</view>
							<text class="radio-text">通过</text>
						</view>
						<view class="radio-item" @click="setReviewResult('rejected')">
							<view class="radio-icon" :class="{ active: reviewForm.result === 'rejected' }">
								<text v-if="reviewForm.result === 'rejected'">✓</text>
							</view>
							<text class="radio-text">驳回</text>
						</view>
					</view>
				</view>
				
				<view class="form-item">
					<text class="form-label">审核意见</text>
					<textarea 
						class="form-textarea" 
						v-model="reviewForm.comments" 
						:placeholder="reviewForm.result === 'approved' ? '请输入审核通过的确认意见' : '请详细说明驳回原因'"
						maxlength="500"
					/>
					<text class="char-count">{{ reviewForm.comments.length }}/500</text>
				</view>
				
				<view class="form-item" v-if="reviewForm.result === 'rejected'">
					<text class="form-label">需要重新检查</text>
					<switch :checked="reviewForm.requireRecheck" @change="onRecheckChange" color="#f97316" />
					<text class="switch-desc">开启后任务将重新分配给工程师</text>
				</view>
			</view>
		</view>
		
		<!-- 审核历史 -->
		<view class="history-section" v-if="reviewHistory.length > 0">
			<view class="section-title">审核历史</view>
			<view class="history-list">
				<view class="history-item" v-for="history in reviewHistory" :key="history.id">
					<view class="history-header">
						<text class="reviewer-name">{{ history.reviewer_name }}</text>
						<text class="review-time">{{ formatDateTime(history.created_at) }}</text>
					</view>
					<view class="history-content">
						<view class="review-result" :class="getReviewResultClass(history.result)">
							{{ getReviewResultText(history.result) }}
						</view>
						<text class="review-comments" v-if="history.comments">{{ history.comments }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 操作按钮 -->
		<view class="action-buttons">
			<button class="cancel-btn" @click="goBack">取消</button>
			<button 
				class="review-btn" 
				@click="submitReview"
				:disabled="!canSubmitReview"
			>
				提交审核
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
	import { onLoad } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	
	const userStore = useUserStore()
	
	// 响应式数据
	const loading = ref(false)
	const taskId = ref(null)
	const task = ref(null)
	const inspectionRecords = ref([])
	const taskPhotos = ref([])
	const reviewHistory = ref([])
	
	const reviewForm = ref({
		result: '',
		comments: '',
		requireRecheck: false
	})
	
	// 计算属性
	const canSubmitReview = computed(() => {
		return reviewForm.value.result && reviewForm.value.comments.trim()
	})
	
	// 页面生命周期
	onLoad((options) => {
		taskId.value = options.taskId
		if (taskId.value) {
			loadTaskDetail()
			loadInspectionRecords()
			loadTaskPhotos()
			loadReviewHistory()
		} else {
			uni.showToast({
				title: '参数错误',
				icon: 'error'
			})
			setTimeout(goBack, 1500)
		}
	})
	
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
	
	const loadInspectionRecords = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.INSPECTIONS.LIST),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				},
				data: {
					task_id: taskId.value
				}
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
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				}
			})
			
			if (response.statusCode === 200) {
				taskPhotos.value = response.data
			}
		} catch (error) {
			console.error('加载任务照片失败:', error)
		}
	}
	
	const loadReviewHistory = async () => {
		try {
			const response = await uni.request({
				url: buildApiUrl('/api/tasks/' + taskId.value + '/reviews'),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				}
			})
			
			if (response.statusCode === 200) {
				reviewHistory.value = response.data
			}
		} catch (error) {
			console.error('加载审核历史失败:', error)
		}
	}
	
	const setReviewResult = (result) => {
		reviewForm.value.result = result
		reviewForm.value.comments = ''
		reviewForm.value.requireRecheck = false
	}
	
	const onRecheckChange = (e) => {
		reviewForm.value.requireRecheck = e.detail.value
	}
	
	const previewPhoto = (photo) => {
		uni.previewImage({
			urls: [photo.photo_url],
			current: photo.photo_url
		})
	}
	
	const submitReview = async () => {
		if (!canSubmitReview.value) return
		
		try {
			loading.value = true
			
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.TASKS.REVIEW(taskId.value)),
				method: 'POST',
				header: {
					'Authorization': `Bearer ${userStore.token}`,
					'Content-Type': 'application/json'
				},
				data: {
					result: reviewForm.value.result,
					comments: reviewForm.value.comments,
					require_recheck: reviewForm.value.requireRecheck
				}
			})
			
			if (response.statusCode === 200 || response.statusCode === 201) {
				uni.showToast({
					title: '审核成功',
					icon: 'success'
				})
				
				setTimeout(() => {
					// 通知上一页数据需要刷新
					uni.$emit('taskReviewed', {
						taskId: taskId.value,
						newStatus: response.data.status
					})
					uni.navigateBack()
				}, 1500)
			}
		} catch (error) {
			console.error('提交审核失败:', error)
			uni.showToast({
				title: '审核失败',
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
	
	const getReviewResultText = (result) => {
		const resultMap = {
			'approved': '通过',
			'rejected': '驳回'
		}
		return resultMap[result] || result
	}
	
	const getReviewResultClass = (result) => {
		return `review-result-${result}`
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
	.review-container {
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
	
	.status-under_review {
		background: #f3e5f5;
		color: #7b1fa2;
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
	
	/* 提交内容 */
	.submission-section {
		background: white;
		margin-bottom: 20rpx;
	}
	
	.submission-card {
		margin: 0 30rpx 30rpx;
	}
	
	.progress-notes {
		margin-bottom: 30rpx;
	}
	
	.notes-label {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.notes-content {
		font-size: 26rpx;
		color: #666;
		line-height: 1.6;
		padding: 20rpx;
		background: #f8f9fa;
		border-radius: 10rpx;
	}
	
	/* 检查记录 */
	.inspection-records {
		margin-bottom: 30rpx;
	}
	
	.records-label {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.records-list {
		
	}
	
	.record-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20rpx;
		background: #f8f9fa;
		border-radius: 10rpx;
		margin-bottom: 10rpx;
	}
	
	.record-header {
		
	}
	
	.record-type {
		font-size: 26rpx;
		color: #333;
		margin-bottom: 5rpx;
		display: block;
	}
	
	.record-time {
		font-size: 24rpx;
		color: #999;
	}
	
	.record-status {
		padding: 6rpx 12rpx;
		border-radius: 10rpx;
		font-size: 24rpx;
	}
	
	.inspection-status-completed {
		background: #d1fae5;
		color: #059669;
	}
	
	.inspection-status-in_progress {
		background: #dbeafe;
		color: #2563eb;
	}
	
	/* 照片部分 */
	.photos-section {
		
	}
	
	.photos-label {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.photos-scroll {
		white-space: nowrap;
		height: 200rpx;
	}
	
	.photo-item {
		display: inline-block;
		width: 150rpx;
		margin-right: 15rpx;
		text-align: center;
	}
	
	.photo-image {
		width: 150rpx;
		height: 150rpx;
		border-radius: 10rpx;
		margin-bottom: 8rpx;
	}
	
	.photo-desc {
		font-size: 22rpx;
		color: #666;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	/* 审核表单 */
	.review-section {
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
	
	.radio-group {
		display: flex;
		gap: 30rpx;
	}
	
	.radio-item {
		display: flex;
		align-items: center;
		gap: 10rpx;
	}
	
	.radio-icon {
		width: 40rpx;
		height: 40rpx;
		border: 2rpx solid #ddd;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: white;
		font-size: 24rpx;
	}
	
	.radio-icon.active {
		background: #f97316;
		border-color: #f97316;
	}
	
	.radio-text {
		font-size: 28rpx;
		color: #333;
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
	
	.switch-desc {
		font-size: 24rpx;
		color: #666;
		margin-left: 20rpx;
	}
	
	/* 审核历史 */
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
	
	.reviewer-name {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
	}
	
	.review-time {
		font-size: 24rpx;
		color: #999;
	}
	
	.history-content {
		
	}
	
	.review-result {
		padding: 6rpx 12rpx;
		border-radius: 10rpx;
		font-size: 24rpx;
		margin-bottom: 10rpx;
		display: inline-block;
	}
	
	.review-result-approved {
		background: #d1fae5;
		color: #059669;
	}
	
	.review-result-rejected {
		background: #fee2e2;
		color: #dc2626;
	}
	
	.review-comments {
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
	
	.review-btn {
		flex: 2;
		padding: 25rpx;
		background: #f97316;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	.review-btn:disabled {
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