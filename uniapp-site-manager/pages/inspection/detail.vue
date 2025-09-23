<template>
	<view class="detail-container">
		<!-- 导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="back-button" @click="goBack">
					<text class="back-icon">←</text>
				</view>
				<text class="navbar-title">检查详情</text>
				<view class="navbar-actions">
					<view class="share-button" @click="shareInspection" v-if="inspectionData">
						<text class="share-icon">📤</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 检查基础信息 -->
		<view class="inspection-header" v-if="inspectionData">
			<view class="header-content">
				<view class="status-badge" :class="getStatusClass(inspectionData.status)">
					<text class="status-text">{{ getStatusText(inspectionData.status) }}</text>
				</view>
				
				<view class="header-info">
					<text class="site-name">{{ inspectionData.site_name }}</text>
					<text class="inspection-type">{{ getInspectionTypeText(inspectionData.inspection_type) }}</text>
				</view>
				
				<view class="header-score" v-if="inspectionData.score">
					<text class="score-value">{{ inspectionData.score }}</text>
					<text class="score-label">分</text>
				</view>
			</view>
			
			<!-- 进度条 -->
			<view class="progress-container">
				<view class="progress-info">
					<text class="progress-text">完成进度</text>
					<text class="progress-rate">{{ inspectionData.completion_rate || 0 }}%</text>
				</view>
				<view class="progress-bar">
					<view 
						class="progress-fill" 
						:style="{ width: (inspectionData.completion_rate || 0) + '%' }"
						:class="getProgressClass(inspectionData.completion_rate)"
					></view>
				</view>
				<text class="progress-detail">
					{{ inspectionData.completed_items || 0 }}/{{ inspectionData.total_items || 0 }} 项已完成
				</text>
			</view>
		</view>
		
		<!-- 详情内容 -->
		<scroll-view class="detail-content" scroll-y v-if="inspectionData">
			<!-- 基本信息卡片 -->
			<view class="detail-card">
				<view class="card-header">
					<text class="card-title">基本信息</text>
				</view>
				<view class="card-content">
					<view class="info-row">
						<text class="info-label">检查员:</text>
						<text class="info-value">{{ inspectionData.inspector_name || '未知' }}</text>
					</view>
					<view class="info-row">
						<text class="info-label">开始时间:</text>
						<text class="info-value">{{ formatDateTime(inspectionData.start_time) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.end_time">
						<text class="info-label">结束时间:</text>
						<text class="info-value">{{ formatDateTime(inspectionData.end_time) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.location">
						<text class="info-label">位置:</text>
						<text class="info-value">{{ inspectionData.location }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.weather">
						<text class="info-label">天气:</text>
						<text class="info-value">{{ inspectionData.weather }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.temperature">
						<text class="info-label">温度:</text>
						<text class="info-value">{{ inspectionData.temperature }}</text>
					</view>
				</view>
			</view>
			
			<!-- GPS信息卡片 -->
			<view class="detail-card" v-if="inspectionData.latitude && inspectionData.longitude">
				<view class="card-header">
					<text class="card-title">GPS信息</text>
					<view class="card-action" @click="openMap">
						<text class="action-text">查看地图</text>
					</view>
				</view>
				<view class="card-content">
					<view class="info-row">
						<text class="info-label">经纬度:</text>
						<text class="info-value">{{ formatCoordinates(inspectionData.latitude, inspectionData.longitude) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.gps_accuracy">
						<text class="info-label">精度:</text>
						<text class="info-value">{{ inspectionData.gps_accuracy }}m</text>
					</view>
					<view class="info-row" v-if="inspectionData.address">
						<text class="info-label">地址:</text>
						<text class="info-value">{{ inspectionData.address }}</text>
					</view>
				</view>
			</view>
			
			<!-- 检查项统计 -->
			<view class="detail-card">
				<view class="card-header">
					<text class="card-title">检查项统计</text>
				</view>
				<view class="card-content">
					<view class="stats-grid">
						<view class="stat-item">
							<text class="stat-number">{{ inspectionData.total_items || 0 }}</text>
							<text class="stat-label">总检查项</text>
						</view>
						<view class="stat-item">
							<text class="stat-number success">{{ inspectionData.completed_items || 0 }}</text>
							<text class="stat-label">已完成</text>
						</view>
						<view class="stat-item">
							<text class="stat-number warning">{{ inspectionData.failed_items || 0 }}</text>
							<text class="stat-label">失败项</text>
						</view>
						<view class="stat-item">
							<text class="stat-number info">{{ (inspectionData.total_items || 0) - (inspectionData.completed_items || 0) - (inspectionData.failed_items || 0) }}</text>
							<text class="stat-label">待处理</text>
						</view>
					</view>
				</view>
			</view>
			
			<!-- 驳回意见卡片 -->
			<view class="detail-card reject-card" v-if="inspectionData.status === 'rejected' && inspectionData.review_comments">
				<view class="card-header">
					<text class="card-title reject-title">🚫 驳回意见</text>
				</view>
				<view class="card-content">
					<view class="reject-content">
						<text class="reject-text">{{ inspectionData.review_comments }}</text>
					</view>
					<view class="reject-tip">
						<text class="tip-text">📝 请根据上述意见修改检查结果后重新提交</text>
					</view>
				</view>
			</view>
			
			<!-- 检查项详情 -->
			<view class="detail-card">
				<view class="card-header">
					<text class="card-title">检查项详情</text>
					<view class="filter-tabs">
						<view 
							class="filter-tab"
							:class="{ active: currentFilter === filter.value }"
							v-for="filter in statusFilters"
							:key="filter.value"
							@click="switchFilter(filter.value)"
						>
							<text class="tab-text">{{ filter.label }}</text>
						</view>
					</view>
				</view>
				<view class="card-content">
					<view class="check-items-list">
						<view 
							class="check-item"
							v-for="item in filteredCheckItems"
							:key="item.id"
							:class="getCheckItemClass(item.status)"
							@click="viewCheckItem(item)"
						>
							<view class="item-header">
								<view class="item-status">
									<text class="status-icon">{{ getStatusIcon(item.status) }}</text>
								</view>
								<view class="item-info">
									<text class="item-name">{{ item.item_name }}</text>
									<view class="item-meta">
										<text class="item-category">{{ item.category_name }}</text>
										<text class="item-sector" v-if="item.sector_id">扇区{{ item.sector_id }}</text>
									</view>
								</view>
								<view class="item-result">
									<text class="review-status" v-if="item.review_status" :class="'review-'+item.review_status">
										{{ getReviewStatusText(item.review_status) }}
									</text>
									<text class="result-icon" v-if="item.validation_result && !item.validation_result.valid">⚠️</text>
									<text class="action-arrow">›</text>
								</view>
							</view>
							
							<view class="item-summary" v-if="item.status !== 'pending'">
								<text class="summary-text" v-if="item.photos && item.photos.length > 0">
									📷 {{ item.photos.length }}张照片
								</text>
								<text class="summary-text" v-if="item.data_value && item.data_value.length > 0">
									📊 {{ item.data_value.length }}项数据
								</text>
								<text class="summary-text" v-if="item.checked_at">
									⏰ {{ formatTime(item.checked_at) }}
								</text>
							</view>
						</view>
					</view>
					
					<!-- 空状态 -->
					<view class="empty-items" v-if="filteredCheckItems.length === 0">
						<text class="empty-text">暂无{{ getCurrentFilterText() }}检查项</text>
					</view>
				</view>
			</view>
			
			<!-- 审核信息 -->
			<view class="detail-card" v-if="inspectionData.reviewed_by || inspectionData.review_comments">
				<view class="card-header">
					<text class="card-title">审核信息</text>
				</view>
				<view class="card-content">
					<view class="info-row" v-if="inspectionData.reviewer_name">
						<text class="info-label">审核人:</text>
						<text class="info-value">{{ inspectionData.reviewer_name }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.reviewed_at">
						<text class="info-label">审核时间:</text>
						<text class="info-value">{{ formatDateTime(inspectionData.reviewed_at) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.review_comments">
						<text class="info-label">审核意见:</text>
						<text class="info-value">{{ inspectionData.review_comments }}</text>
					</view>
				</view>
			</view>
			
			<!-- 备注信息 -->
			<view class="detail-card" v-if="inspectionData.notes || inspectionData.issues_found || inspectionData.recommendations">
				<view class="card-header">
					<text class="card-title">备注信息</text>
				</view>
				<view class="card-content">
					<view class="note-section" v-if="inspectionData.notes">
						<text class="note-label">检查备注:</text>
						<text class="note-content">{{ inspectionData.notes }}</text>
					</view>
					<view class="note-section" v-if="inspectionData.issues_found">
						<text class="note-label">发现问题:</text>
						<text class="note-content">{{ inspectionData.issues_found }}</text>
					</view>
					<view class="note-section" v-if="inspectionData.recommendations">
						<text class="note-label">建议措施:</text>
						<text class="note-content">{{ inspectionData.recommendations }}</text>
					</view>
				</view>
			</view>
		</scroll-view>
		
		<!-- 底部操作栏 -->
		<view class="bottom-actions" v-if="inspectionData">
			<button 
				class="action-btn continue-btn" 
				v-if="canContinue"
				@click="continueInspection"
			>
				{{ inspectionData.status === 'rejected' ? '修改检查结果' : '继续检查' }}
			</button>
			
			<button 
				class="action-btn review-btn" 
				v-if="canReview"
				@click="reviewInspection"
			>
				审核
			</button>
			
			<button 
				class="action-btn export-btn" 
				@click="exportReport"
				:disabled="exporting"
			>
				{{ exporting ? '导出中...' : '导出报告' }}
			</button>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-container" v-if="loading">
			<uni-load-more status="loading" :content-text="{ contentdown: '加载中...', contentrefresh: '加载中...', contentnomore: '加载完成' }"></uni-load-more>
		</view>
		
		<!-- 检查项详情弹窗 -->
		<view class="item-detail-overlay" v-if="currentItem" @click="closeItemDetail">
			<view class="item-detail-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">{{ currentItem.item_name }}</text>
					<view class="modal-close" @click="closeItemDetail">
						<text class="close-icon">×</text>
					</view>
				</view>
				
				<scroll-view class="modal-content" scroll-y>
					<!-- 检查项基本信息 -->
					<view class="modal-section">
						<text class="section-title">基本信息</text>
						<view class="info-grid">
							<view class="grid-item">
								<text class="grid-label">状态:</text>
								<text class="grid-value" :class="getStatusClass(currentItem.status)">
									{{ getStatusText(currentItem.status) }}
								</text>
							</view>
							<view class="grid-item" v-if="currentItem.sector_id">
								<text class="grid-label">扇区:</text>
								<text class="grid-value">{{ currentItem.sector_id }}</text>
							</view>
							<view class="grid-item">
								<text class="grid-label">类型:</text>
								<text class="grid-value">{{ getRequiredTypeText(currentItem.required_type) }}</text>
							</view>
						</view>
					</view>
					
					<!-- 检查数据 -->
					<view class="modal-section" v-if="currentItem.data_value && currentItem.data_value.length > 0">
						<text class="section-title">检查数据</text>
						<view class="data-list">
							<view 
								class="data-item"
								v-for="dataItem in currentItem.data_value"
								:key="dataItem.field_name"
							>
								<text class="data-label">{{ dataItem.field_name }}:</text>
								<text class="data-value">{{ dataItem.value }}{{ dataItem.unit || '' }}</text>
							</view>
						</view>
					</view>
					
					<!-- 照片 -->
					<view class="modal-section" v-if="currentItem.photos && currentItem.photos.length > 0">
						<text class="section-title">照片 ({{ currentItem.photos.length }})</text>
						<view class="photo-grid">
							<view 
								class="photo-item" 
								v-for="(photo, index) in currentItem.photos" 
								:key="index"
								@click="previewPhoto(currentItem.photos, index)"
							>
								<image class="photo-thumb" :src="buildImageUrl(photo.file_path)" mode="aspectFill"></image>
							</view>
						</view>
					</view>
					
					<!-- 验证结果 -->
					<view class="modal-section" v-if="currentItem.validation_result">
						<text class="section-title">验证结果</text>
						<view class="validation-info">
							<view class="validation-status" :class="currentItem.validation_result.valid ? 'valid' : 'invalid'">
								<text class="status-icon">{{ currentItem.validation_result.valid ? '✅' : '❌' }}</text>
								<text class="status-text">{{ currentItem.validation_result.valid ? '验证通过' : '验证失败' }}</text>
							</view>
							<view class="validation-errors" v-if="!currentItem.validation_result.valid">
								<text 
									class="error-item" 
									v-for="error in currentItem.validation_result.errors"
									:key="error"
								>
									• {{ error }}
								</text>
							</view>
						</view>
					</view>
					
					<!-- 审核信息 -->
					<view class="modal-section" v-if="currentItem.review_status || currentItem.review_comments">
						<text class="section-title">审核信息</text>
						<view class="review-info">
							<view class="review-status-item" v-if="currentItem.review_status">
								<text class="review-label">审核状态:</text>
								<text class="review-value" :class="'review-'+currentItem.review_status">
									{{ getReviewStatusText(currentItem.review_status) }}
								</text>
							</view>
							<view class="review-comments-item" v-if="currentItem.review_comments">
								<text class="review-label">审核意见:</text>
								<text class="review-comments-text">{{ currentItem.review_comments }}</text>
							</view>
							<view class="review-time-item" v-if="currentItem.reviewed_at">
								<text class="review-label">审核时间:</text>
								<text class="review-time">{{ formatDateTime(currentItem.reviewed_at) }}</text>
							</view>
						</view>
					</view>
					
					<!-- 备注 -->
					<view class="modal-section" v-if="currentItem.notes">
						<text class="section-title">备注</text>
						<text class="note-text">{{ currentItem.notes }}</text>
					</view>
				</scroll-view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	import { buildApiUrl, createRequestConfig, getAuthHeaders, buildImageUrl } from '@/config/api.js'
	
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	
	// 页面参数
	const inspectionId = ref('')
	
	// 响应式数据
	const loading = ref(true)
	const exporting = ref(false)
	const inspectionData = ref(null)
	const checkItems = ref([])
	const currentFilter = ref('all')
	const currentItem = ref(null)
	
	// 筛选选项
	const statusFilters = [
		{ label: '全部', value: 'all' },
		{ label: '已完成', value: 'completed' },
		{ label: '失败', value: 'failed' },
		{ label: '进行中', value: 'in_progress' },
		{ label: '待处理', value: 'pending' }
	]
	
	// 计算属性
	const filteredCheckItems = computed(() => {
		if (currentFilter.value === 'all') {
			return checkItems.value
		}
		return checkItems.value.filter(item => item.status === currentFilter.value)
	})
	
	const canContinue = computed(() => {
		return inspectionData.value && 
			   ['draft', 'in_progress', 'rejected'].includes(inspectionData.value.status) &&
			   inspectionData.value.inspector_id === userStore.userInfo?.id
	})
	
	const canReview = computed(() => {
		return inspectionData.value && 
			   inspectionData.value.status === 'submitted' &&
			   ['admin', 'reviewer'].includes(userStore.userInfo?.role)
	})
	
	// 生命周期
	onLoad((options) => {
		if (options.id) {
			inspectionId.value = options.id
			loadInspectionDetail()
		}
	})
	
	// 方法
	const loadInspectionDetail = async () => {
		try {
			loading.value = true
			
			// 加载检查详情
			const inspectionResult = await inspectionStore.getInspectionDetail(inspectionId.value)
			if (inspectionResult.success) {
				inspectionData.value = inspectionResult.data
				
				// 如果没有site_name，尝试通过site_id获取站点信息
				if (!inspectionData.value.site_name && inspectionData.value.site_id) {
					try {
						const response = await uni.request({
							url: buildApiUrl(`/api/sites/${inspectionData.value.site_id}`),
							...createRequestConfig({
								method: 'GET',
								headers: getAuthHeaders(userStore.token)
							})
						})
						if (response.statusCode === 200) {
							inspectionData.value.site_name = response.data.name
							inspectionData.value.address = response.data.address || inspectionData.value.address
						}
					} catch (siteError) {
						console.warn('获取站点信息失败:', siteError)
						// 设置默认站点名称
						inspectionData.value.site_name = `站点 ${inspectionData.value.site_id}`
					}
				}
			}
			
			// 加载检查项
			const itemsResult = await inspectionStore.getInspectionItems(inspectionId.value)
			if (itemsResult.success) {
				checkItems.value = itemsResult.data
			}
			
		} catch (error) {
			console.error('加载检查详情失败:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const switchFilter = (filterValue) => {
		currentFilter.value = filterValue
	}
	
	const getCurrentFilterText = () => {
		const filter = statusFilters.find(f => f.value === currentFilter.value)
		return filter ? filter.label : '全部'
	}
	
	const viewCheckItem = (item) => {
		console.log('ViewCheckItem - Review data:', {
			review_status: item.review_status,
			review_comments: item.review_comments,
			reviewed_at: item.reviewed_at
		})
		currentItem.value = item
	}
	
	const closeItemDetail = () => {
		currentItem.value = null
	}
	
	const continueInspection = () => {
		uni.navigateTo({
			url: `/pages/inspection/checklist?inspectionId=${inspectionId.value}`
		})
	}
	
	const reviewInspection = () => {
		uni.navigateTo({
			url: `/pages/inspection/review?id=${inspectionId.value}`
		})
	}
	
	const shareInspection = () => {
		const shareData = {
			title: `${inspectionData.value.site_name} - 检查报告`,
			path: `/pages/inspection/detail?id=${inspectionId.value}`
		}
		
		uni.showShareMenu({
			withShareTicket: true,
			menus: ['shareAppMessage', 'shareTimeline'],
			success: () => {
				console.log('分享菜单显示成功')
			}
		})
	}
	
	const exportReport = async () => {
		try {
			exporting.value = true
			
			// 这里可以调用导出API
			// const result = await inspectionStore.exportInspectionReport(inspectionId.value)
			
			// 模拟导出过程
			await new Promise(resolve => setTimeout(resolve, 2000))
			
			uni.showToast({
				title: '导出成功',
				icon: 'success'
			})
			
		} catch (error) {
			console.error('导出失败:', error)
			uni.showToast({
				title: '导出失败',
				icon: 'error'
			})
		} finally {
			exporting.value = false
		}
	}
	
	const openMap = () => {
		if (!inspectionData.value.latitude || !inspectionData.value.longitude) return
		
		uni.openLocation({
			latitude: inspectionData.value.latitude,
			longitude: inspectionData.value.longitude,
			name: inspectionData.value.site_name,
			address: inspectionData.value.address || '',
			scale: 15
		})
	}
	
	const previewPhoto = (photos, current) => {
		const urls = photos.map(photo => buildImageUrl(photo.file_path))
		uni.previewImage({
			urls,
			current: current || 0
		})
	}
	
	const goBack = () => {
		uni.navigateBack()
	}
	
	// 工具函数
	const getInspectionTypeText = (type) => {
		const typeMap = {
			installation: '安装检查',
			opening: '新站点设备安装',
			maintenance: '维护检查'
		}
		return typeMap[type] || '检查'
	}
	
	const getStatusClass = (status) => {
		const classMap = {
			draft: 'status-draft',
			in_progress: 'status-progress',
			submitted: 'status-submitted',
			under_review: 'status-review',
			approved: 'status-approved',
			rejected: 'status-rejected',
			completed: 'status-completed',
			pending: 'status-pending',
			failed: 'status-failed'
		}
		return classMap[status] || 'status-default'
	}
	
	const getStatusText = (status) => {
		const statusMap = {
			draft: '草稿',
			in_progress: '进行中',
			submitted: '已提交',
			under_review: '审核中',
			approved: '已通过',
			rejected: '已驳回',
			completed: '已完成',
			pending: '待处理',
			failed: '失败'
		}
		return statusMap[status] || '未知'
	}
	
	const getCheckItemClass = (status) => {
		return `check-item-${status}`
	}
	
	const getStatusIcon = (status) => {
		const iconMap = {
			pending: '⭕',
			in_progress: '🔄',
			completed: '✅',
			failed: '❌',
			skipped: '⏭️'
		}
		return iconMap[status] || '⭕'
	}
	
	const getProgressClass = (rate) => {
		if (rate >= 100) return 'progress-complete'
		if (rate >= 80) return 'progress-high'
		if (rate >= 50) return 'progress-medium'
		return 'progress-low'
	}
	
	const getRequiredTypeText = (type) => {
		const typeMap = {
			photo: '仅照片',
			data: '仅数据',
			both: '照片+数据'
		}
		return typeMap[type] || '未知'
	}
	
	const formatDateTime = (dateTime) => {
		if (!dateTime) return ''
		const date = new Date(dateTime)
		return date.toLocaleString('zh-CN')
	}
	
	const formatTime = (dateTime) => {
		if (!dateTime) return ''
		const date = new Date(dateTime)
		return date.toLocaleTimeString('zh-CN', {
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	const formatCoordinates = (lat, lon) => {
		return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
	}
	
	const getReviewStatusText = (status) => {
		const statusMap = {
			pass: '✅ 通过',
			fail: '❌ 不合格', 
			warning: '⚠️ 警告'
		}
		return statusMap[status] || status
	}
</script>

<style scoped>
	.detail-container {
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
	
	.back-button, .share-button {
		width: 60rpx;
		height: 60rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 30rpx;
		background: rgba(255, 255, 255, 0.2);
	}
	
	.back-icon, .share-icon {
		font-size: 36rpx;
		color: white;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
		flex: 1;
		text-align: center;
	}
	
	.navbar-actions {
		width: 60rpx;
		display: flex;
		justify-content: flex-end;
	}
	
	/* 检查头部 */
	.inspection-header {
		background: white;
		margin: 20rpx;
		border-radius: 20rpx;
		padding: 30rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
	}
	
	.header-content {
		display: flex;
		align-items: center;
		margin-bottom: 25rpx;
		gap: 20rpx;
	}
	
	.status-badge {
		padding: 8rpx 16rpx;
		border-radius: 15rpx;
		font-size: 24rpx;
		font-weight: 500;
	}
	
	.status-draft {
		background: #e9ecef;
		color: #6c757d;
	}
	
	.status-progress {
		background: #e3f2fd;
		color: #1976d2;
	}
	
	.status-submitted {
		background: #fff3cd;
		color: #856404;
	}
	
	.status-approved {
		background: #d4edda;
		color: #155724;
	}
	
	.status-rejected {
		background: #f8d7da;
		color: #721c24;
	}
	
	.status-completed {
		background: #d1fae5;
		color: #059669;
	}
	
	.header-info {
		flex: 1;
	}
	
	.site-name {
		font-size: 36rpx;
		font-weight: bold;
		color: #333;
		display: block;
		margin-bottom: 8rpx;
	}
	
	.inspection-type {
		font-size: 26rpx;
		color: #666;
	}
	
	.header-score {
		text-align: center;
		min-width: 120rpx;
	}
	
	.score-value {
		font-size: 48rpx;
		font-weight: bold;
		color: #ff6b6b;
		display: block;
	}
	
	.score-label {
		font-size: 24rpx;
		color: #666;
	}
	
	/* 进度条 */
	.progress-container {
		margin-top: 25rpx;
	}
	
	.progress-info {
		display: flex;
		justify-content: space-between;
		margin-bottom: 15rpx;
	}
	
	.progress-text {
		font-size: 26rpx;
		color: #666;
	}
	
	.progress-rate {
		font-size: 26rpx;
		font-weight: bold;
		color: #333;
	}
	
	.progress-bar {
		height: 12rpx;
		background: #e9ecef;
		border-radius: 6rpx;
		overflow: hidden;
		margin-bottom: 15rpx;
	}
	
	.progress-fill {
		height: 100%;
		border-radius: 6rpx;
		transition: width 0.3s ease;
	}
	
	.progress-low {
		background: #dc3545;
	}
	
	.progress-medium {
		background: #ffc107;
	}
	
	.progress-high {
		background: #28a745;
	}
	
	.progress-complete {
		background: #20c997;
	}
	
	.progress-detail {
		font-size: 24rpx;
		color: #999;
		text-align: center;
		display: block;
	}
	
	/* 详情内容 */
	.detail-content {
		flex: 1;
		padding: 0 20rpx 120rpx;
	}
	
	.detail-card {
		background: white;
		border-radius: 20rpx;
		margin-bottom: 20rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
		overflow: hidden;
	}
	
	/* 驳回意见卡片特殊样式 */
	.reject-card {
		border-left: 6rpx solid #dc2626;
		background: linear-gradient(135deg, #fef2f2, #fff);
	}
	
	.reject-title {
		color: #dc2626 !important;
		font-weight: 600;
	}
	
	.reject-content {
		padding: 20rpx;
		background: #fef2f2;
		border-radius: 15rpx;
		margin-bottom: 20rpx;
	}
	
	.reject-text {
		font-size: 28rpx;
		line-height: 1.6;
		color: #374151;
	}
	
	.reject-tip {
		padding: 15rpx 20rpx;
		background: #fffbeb;
		border-radius: 15rpx;
		border: 1rpx solid #f59e0b;
	}
	
	.tip-text {
		font-size: 26rpx;
		color: #b45309;
		line-height: 1.5;
	}
	
	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 30rpx;
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.card-title {
		font-size: 30rpx;
		font-weight: bold;
		color: #333;
	}
	
	.card-action {
		padding: 10rpx 20rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
	}
	
	.action-text {
		font-size: 24rpx;
		color: #007bff;
	}
	
	.card-content {
		padding: 30rpx;
	}
	
	/* 信息行 */
	.info-row {
		display: flex;
		align-items: center;
		margin-bottom: 20rpx;
		gap: 20rpx;
	}
	
	.info-row:last-child {
		margin-bottom: 0;
	}
	
	.info-label {
		font-size: 28rpx;
		color: #666;
		min-width: 140rpx;
	}
	
	.info-value {
		font-size: 28rpx;
		color: #333;
		flex: 1;
	}
	
	/* 统计网格 */
	.stats-grid {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr 1fr;
		gap: 20rpx;
	}
	
	.stat-item {
		text-align: center;
		padding: 20rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
	}
	
	.stat-number {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		display: block;
		margin-bottom: 8rpx;
	}
	
	.stat-number.success {
		color: #28a745;
	}
	
	.stat-number.warning {
		color: #ffc107;
	}
	
	.stat-number.info {
		color: #17a2b8;
	}
	
	.stat-label {
		font-size: 24rpx;
		color: #666;
	}
	
	/* 筛选标签 */
	.filter-tabs {
		display: flex;
		gap: 10rpx;
	}
	
	.filter-tab {
		padding: 8rpx 16rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
		font-size: 24rpx;
		color: #666;
		transition: all 0.3s ease;
	}
	
	.filter-tab.active {
		background: #6c5ce7;
		color: white;
	}
	
	.tab-text {
		white-space: nowrap;
	}
	
	/* 检查项列表 */
	.check-items-list {
		display: flex;
		flex-direction: column;
		gap: 15rpx;
		width: 100%;
		box-sizing: border-box;
	}
	
	.check-item {
		padding: 20rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
		border-left: 6rpx solid #e9ecef;
		transition: transform 0.2s ease;
		width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.check-item:active {
		transform: scale(0.98);
	}
	
	.check-item-completed {
		border-left-color: #28a745;
	}
	
	.check-item-failed {
		border-left-color: #dc3545;
	}
	
	.check-item-in_progress {
		border-left-color: #007bff;
	}
	
	.check-item-pending {
		border-left-color: #6c757d;
	}
	
	.item-header {
		display: flex;
		align-items: flex-start;
		gap: 12rpx;
		width: 100%;
		min-width: 0;
		box-sizing: border-box;
	}
	
	.item-status {
		flex-shrink: 0;
	}
	
	.status-icon {
		font-size: 28rpx;
	}
	
	.item-info {
		flex: 1;
		min-width: 0;
		max-width: calc(100% - 140rpx);
		overflow: hidden;
	}
	
	.item-name {
		font-size: 26rpx;
		font-weight: 500;
		color: #333;
		margin-bottom: 5rpx;
		word-break: break-word;
		overflow-wrap: break-word;
		line-height: 1.4;
		max-width: 100%;
		display: block;
	}
	
	.item-meta {
		display: flex;
		gap: 10rpx;
		flex-wrap: wrap;
		max-width: 100%;
		overflow: hidden;
	}
	
	.item-category {
		font-size: 20rpx;
		color: #666;
		max-width: 200rpx;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex-shrink: 0;
	}
	
	.item-sector {
		font-size: 20rpx;
		color: #007bff;
		max-width: 100rpx;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex-shrink: 0;
	}
	
	.item-result {
		display: flex;
		align-items: center;
		gap: 8rpx;
		flex-shrink: 0;
		max-width: 120rpx;
		justify-content: flex-end;
	}
	
	.result-icon {
		font-size: 24rpx;
	}
	
	.action-arrow {
		font-size: 28rpx;
		color: #ccc;
	}
	
	.item-summary {
		margin-top: 12rpx;
		display: flex;
		gap: 15rpx;
		flex-wrap: wrap;
		width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.summary-text {
		font-size: 20rpx;
		color: #666;
		max-width: 150rpx;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex-shrink: 0;
	}
	
	.empty-items {
		text-align: center;
		padding: 60rpx 20rpx;
	}
	
	.empty-text {
		font-size: 26rpx;
		color: #999;
	}
	
	/* 备注信息 */
	.note-section {
		margin-bottom: 25rpx;
	}
	
	.note-section:last-child {
		margin-bottom: 0;
	}
	
	.note-label {
		font-size: 26rpx;
		font-weight: bold;
		color: #333;
		display: block;
		margin-bottom: 10rpx;
	}
	
	.note-content {
		font-size: 26rpx;
		color: #666;
		line-height: 1.6;
	}
	
	/* 底部操作栏 */
	.bottom-actions {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: white;
		padding: 20rpx;
		border-top: 1rpx solid #f0f0f0;
		display: flex;
		gap: 20rpx;
		z-index: 100;
	}
	
	.action-btn {
		flex: 1;
		padding: 25rpx;
		border-radius: 15rpx;
		font-size: 28rpx;
		border: none;
		color: white;
		transition: all 0.3s ease;
	}
	
	.continue-btn {
		background: linear-gradient(135deg, #f97316, #fb923c);
	}
	
	.review-btn {
		background: linear-gradient(135deg, #f97316, #fb923c);
	}
	
	.export-btn {
		background: linear-gradient(135deg, #f97316, #fb923c);
	}
	
	.action-btn:disabled {
		background: #adb5bd;
	}
	
	/* 加载状态 */
	.loading-container {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	
	/* 检查项详情弹窗 */
	.item-detail-overlay {
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
		padding: 20rpx;
	}
	
	.item-detail-modal {
		background: white;
		border-radius: 20rpx;
		width: calc(100vw - 40rpx);
		max-width: 680rpx;
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		min-width: 280rpx;
		overflow: hidden;
		box-sizing: border-box;
	}
	
	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 30rpx;
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.modal-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		flex: 1;
		word-break: break-word;
		overflow-wrap: break-word;
		hyphens: auto;
		line-height: 1.4;
		padding-right: 20rpx;
		max-width: calc(100% - 80rpx);
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
		padding: 20rpx;
		overflow-y: auto;
		box-sizing: border-box;
		width: 100%;
	}
	
	.modal-section {
		margin-bottom: 40rpx;
	}
	
	.section-title {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 20rpx;
		display: block;
	}
	
	.info-grid {
		display: flex;
		flex-direction: column;
		gap: 20rpx;
	}
	
	.grid-item {
		display: flex;
		flex-direction: row;
		align-items: flex-start;
		gap: 10rpx;
		padding: 12rpx 15rpx;
		background: #f8f9fa;
		border-radius: 12rpx;
		width: 100%;
		box-sizing: border-box;
		min-width: 0;
	}
	
	.grid-label {
		font-size: 24rpx;
		color: #666;
		min-width: 80rpx;
		max-width: 100rpx;
		flex-shrink: 0;
		font-weight: 500;
		word-break: keep-all;
		white-space: nowrap;
		line-height: 1.4;
	}
	
	.grid-value {
		font-size: 24rpx;
		color: #333;
		font-weight: 500;
		flex: 1;
		word-break: break-all;
		overflow-wrap: break-word;
		hyphens: auto;
		line-height: 1.4;
		max-width: 100%;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	
	/* 数据列表 */
	.data-list {
		display: flex;
		flex-direction: column;
		gap: 15rpx;
	}
	
	.data-item {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 15rpx;
		background: #f8f9fa;
		border-radius: 12rpx;
		gap: 10rpx;
		width: 100%;
		box-sizing: border-box;
		min-width: 0;
	}
	
	.data-label {
		font-size: 24rpx;
		color: #666;
		min-width: 80rpx;
		max-width: 100rpx;
		flex-shrink: 0;
		font-weight: 500;
		line-height: 1.4;
		word-break: keep-all;
		white-space: nowrap;
	}
	
	.data-value {
		font-size: 24rpx;
		color: #333;
		font-weight: 500;
		flex: 1;
		text-align: right;
		word-break: break-all;
		overflow-wrap: break-word;
		hyphens: auto;
		line-height: 1.4;
		max-width: 100%;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	
	/* 照片网格 */
	.photo-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150rpx, 1fr));
		gap: 15rpx;
	}
	
	.photo-item {
		border-radius: 12rpx;
		overflow: hidden;
		background: #f8f9fa;
	}
	
	.photo-thumb {
		width: 100%;
		height: 150rpx;
	}
	
	/* 验证信息 */
	.validation-info {
		background: #f8f9fa;
		border-radius: 12rpx;
		padding: 20rpx;
	}
	
	.validation-status {
		display: flex;
		align-items: center;
		gap: 15rpx;
		margin-bottom: 15rpx;
	}
	
	.validation-status.valid {
		color: #28a745;
	}
	
	.validation-status.invalid {
		color: #dc3545;
	}
	
	.validation-errors {
		display: flex;
		flex-direction: column;
		gap: 8rpx;
	}
	
	.error-item {
		font-size: 24rpx;
		color: #dc3545;
	}
	
	.note-text {
		font-size: 26rpx;
		color: #666;
		line-height: 1.6;
	}
	
	/* 审核状态样式 */
	.review-status {
		font-size: 20rpx;
		padding: 2rpx 6rpx;
		border-radius: 6rpx;
		margin-right: 4rpx;
		font-weight: 500;
		max-width: 80rpx;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex-shrink: 0;
	}
	
	.review-pass {
		background: #d1fae5;
		color: #059669;
	}
	
	.review-fail {
		background: #fee2e2;
		color: #dc2626;
	}
	
	.review-warning {
		background: #fef3c7;
		color: #b45309;
	}
	
	/* 审核信息区域样式 */
	.review-info {
		background: #f8f9fa;
		border-radius: 12rpx;
		padding: 20rpx;
	}
	
	.review-status-item,
	.review-comments-item,
	.review-time-item {
		display: flex;
		margin-bottom: 12rpx;
		align-items: flex-start;
		gap: 10rpx;
		width: 100%;
		min-width: 0;
		box-sizing: border-box;
	}
	
	.review-status-item:last-child,
	.review-comments-item:last-child,
	.review-time-item:last-child {
		margin-bottom: 0;
	}
	
	.review-label {
		font-size: 24rpx;
		color: #666;
		min-width: 80rpx;
		max-width: 100rpx;
		font-weight: 500;
		flex-shrink: 0;
		word-break: keep-all;
		white-space: nowrap;
		line-height: 1.4;
	}
	
	.review-value {
		font-size: 26rpx;
		font-weight: 500;
		padding: 6rpx 12rpx;
		border-radius: 10rpx;
		flex: 1;
		min-width: 0;
		max-width: 100%;
		word-break: break-word;
		overflow-wrap: break-word;
	}
	
	.review-comments-text {
		font-size: 24rpx;
		color: #333;
		line-height: 1.5;
		flex: 1;
		background: white;
		padding: 12rpx;
		border-radius: 8rpx;
		border: 1rpx solid #e5e7eb;
		word-break: break-word;
		white-space: pre-wrap;
		max-width: 100%;
		min-width: 0;
		overflow-wrap: break-word;
		box-sizing: border-box;
	}
	
	.review-time {
		font-size: 26rpx;
		color: #666;
		flex: 1;
		min-width: 0;
		max-width: 100%;
		word-break: break-word;
		overflow-wrap: break-word;
	}
</style>