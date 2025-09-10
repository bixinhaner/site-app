<template>
	<view class="inspection-list-container">
		<!-- 自定义导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<text class="navbar-title">现场检查</text>
				<view class="navbar-actions">
					<view class="sync-status" @click="checkSyncStatus">
						<text class="sync-icon" :class="{ syncing: isSyncing }">🔄</text>
						<text class="sync-text">{{ syncStatusText }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 统计卡片 -->
		<view class="stats-container">
			<view class="stat-item">
				<text class="stat-number">{{ statistics.total_inspections || 0 }}</text>
				<text class="stat-label">总检查数</text>
			</view>
			<view class="stat-item">
				<text class="stat-number">{{ statistics.pending_inspections || 0 }}</text>
				<text class="stat-label">待处理</text>
			</view>
			<view class="stat-item">
				<text class="stat-number">{{ statistics.completed_inspections || 0 }}</text>
				<text class="stat-label">已完成</text>
			</view>
			<view class="stat-item">
				<text class="stat-number">{{ statistics.average_score || 0 }}分</text>
				<text class="stat-label">平均分</text>
			</view>
		</view>
		
		<!-- 筛选器 -->
		<view class="filter-container">
			<scroll-view class="filter-scroll" scroll-x>
				<view class="filter-tabs">
					<view 
						class="filter-tab"
						:class="{ active: currentFilter === filter.value }"
						v-for="filter in filters"
						:key="filter.value"
						@click="selectFilter(filter.value)"
					>
						{{ filter.label }}
						<text class="filter-count" v-if="filter.count > 0">({{ filter.count }})</text>
					</view>
				</view>
			</scroll-view>
		</view>
		
		<!-- 检查列表 -->
		<scroll-view class="inspection-scroll" scroll-y @scrolltolower="loadMore">
			<view class="inspection-list">
				<!-- 检查项 -->
				<view 
					class="inspection-item"
					v-for="inspection in filteredInspections"
					:key="inspection.id"
					@click="viewInspectionDetail(inspection)"
					@longpress="showInspectionOptions(inspection)"
				>
					<!-- 检查卡片头部 -->
					<view class="inspection-header">
						<view class="site-info">
							<text class="site-name">{{ inspection.site_name || '未知站点' }}</text>
							<text class="site-code">{{ inspection.site_code || inspection.site_id }}</text>
						</view>
						<view class="status-badge" :class="getStatusClass(inspection.status)">
							<text class="status-text">{{ getStatusText(inspection.status) }}</text>
						</view>
					</view>
					
					<!-- 检查详情 -->
					<view class="inspection-content">
						<view class="content-row">
							<text class="content-icon">📋</text>
							<text class="content-text">{{ getInspectionTypeText(inspection.inspection_type) }}</text>
						</view>
						
						<view class="content-row">
							<text class="content-icon">👤</text>
							<text class="content-text">{{ inspection.inspector_name || '检查员' }}</text>
						</view>
						
						<view class="content-row" v-if="inspection.start_time">
							<text class="content-icon">⏰</text>
							<text class="content-text">{{ formatDateTime(inspection.start_time) }}</text>
						</view>
						
						<view class="content-row" v-if="inspection.location">
							<text class="content-icon">📍</text>
							<text class="content-text">{{ inspection.location }}</text>
						</view>
						
						<!-- 进度条 -->
						<view class="progress-container" v-if="inspection.total_items > 0">
							<view class="progress-info">
								<text class="progress-text">完成进度</text>
								<text class="progress-rate">{{ inspection.completion_rate }}%</text>
							</view>
							<view class="progress-bar">
								<view 
									class="progress-fill" 
									:style="{ width: inspection.completion_rate + '%' }"
									:class="getProgressClass(inspection.completion_rate)"
								></view>
							</view>
							<text class="progress-detail">
								{{ inspection.completed_items }}/{{ inspection.total_items }} 项已完成
							</text>
						</view>
						
						<!-- 评分显示 -->
						<view class="score-container" v-if="inspection.score">
							<text class="score-label">质量评分:</text>
							<view class="score-stars">
								<text 
									class="star" 
									v-for="i in 5" 
									:key="i"
									:class="{ filled: i <= Math.round(inspection.score / 20) }"
								>⭐</text>
							</view>
							<text class="score-value">{{ inspection.score }}分</text>
						</view>
					</view>
					
					<!-- 检查操作 -->
					<view class="inspection-actions">
						<view class="action-info">
							<text class="create-time">{{ formatCreateTime(inspection.created_at) }}</text>
							<text class="offline-indicator" v-if="isOfflineInspection(inspection)">📴 离线</text>
						</view>
						<view class="action-buttons">
							<button 
								class="action-btn continue-btn" 
								v-if="canContinue(inspection)"
								@click.stop="continueInspection(inspection)"
							>
								继续检查
							</button>
							<button 
								class="action-btn review-btn" 
								v-if="canReview(inspection)"
								@click.stop="reviewInspection(inspection)"
							>
								审核
							</button>
							<text class="action-arrow">›</text>
						</view>
					</view>
				</view>
				
				<!-- 空状态 -->
				<view class="empty-state" v-if="filteredInspections.length === 0 && !loading">
					<text class="empty-icon">🔍</text>
					<text class="empty-title">暂无检查记录</text>
					<text class="empty-desc">点击右下角按钮开始新的检查</text>
				</view>
				
				<!-- 加载更多 -->
				<view class="load-more" v-if="hasMore">
					<uni-load-more :status="loadMoreStatus"></uni-load-more>
				</view>
			</view>
		</scroll-view>
		
		<!-- 浮动操作按钮 -->
		<view class="fab-container">
			<view class="fab" @click="showCreateOptions">
				<text class="fab-icon">＋</text>
			</view>
		</view>
		
		<!-- 创建选项弹窗 -->
		<view class="create-options-overlay" v-if="showCreateModal" @click="hideCreateOptions">
			<view class="create-options" @click.stop>
				<view class="create-title">开始新检查</view>
				<view class="create-list">
					<view class="create-item" @click="startNewInspection('installation')">
						<text class="create-icon">🔧</text>
						<view class="create-info">
							<text class="create-name">安装检查</text>
							<text class="create-desc">新站点安装验收检查</text>
						</view>
					</view>
					<view class="create-item" @click="startNewInspection('maintenance')">
						<text class="create-icon">🔨</text>
						<view class="create-info">
							<text class="create-name">维护检查</text>
							<text class="create-desc">定期维护检查</text>
						</view>
					</view>
				</view>
				<button class="create-cancel" @click="hideCreateOptions">取消</button>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useInspectionStore } from '@/stores/inspection'
	import { useOfflineStore } from '@/stores/offline'
	
	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const inspectionStore = useInspectionStore()
	const offlineStore = useOfflineStore()
	
	// 响应式数据
	const currentFilter = ref('all')
	const loading = ref(false)
	const loadMoreStatus = ref('more')
	const hasMore = ref(true)
	const page = ref(1)
	const pageSize = ref(20)
	const showCreateModal = ref(false)
	const isSyncing = ref(false)
	const statistics = ref({})
	
	// 筛选器配置
	const filters = ref([
		{ label: '全部', value: 'all', count: 0 },
		{ label: '草稿', value: 'draft', count: 0 },
		{ label: '进行中', value: 'in_progress', count: 0 },
		{ label: '已提交', value: 'submitted', count: 0 },
		{ label: '待审核', value: 'under_review', count: 0 },
		{ label: '已通过', value: 'approved', count: 0 },
		{ label: '已驳回', value: 'rejected', count: 0 }
	])
	
	// 计算属性
	const filteredInspections = computed(() => {
		let inspections = inspectionStore.inspections || []
		
		if (currentFilter.value !== 'all') {
			inspections = inspections.filter(inspection => 
				inspection.status === currentFilter.value
			)
		}
		
		return inspections.sort((a, b) => 
			new Date(b.updated_at) - new Date(a.updated_at)
		)
	})
	
	const syncStatusText = computed(() => {
		if (isSyncing.value) return '同步中...'
		
		const pendingCount = offlineStore.getPendingDataCount()
		if (pendingCount > 0) {
			return `${pendingCount}条待同步`
		}
		
		return '已同步'
	})
	
	// 方法声明 - 必须在生命周期hooks之前定义
	const loadInspections = async (reset = false) => {
		try {
			loading.value = true
			
			if (reset) {
				page.value = 1
				inspectionStore.inspections = []
			}
			
			const result = await inspectionStore.getInspections({
				skip: (page.value - 1) * pageSize.value,
				limit: pageSize.value
			})
			
			if (result.success) {
				updateFilterCounts()
				
				// 检查是否还有更多数据
				hasMore.value = result.data.length === pageSize.value
				loadMoreStatus.value = hasMore.value ? 'more' : 'no-more'
			}
			
		} catch (error) {
			console.error('加载检查列表失败:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const loadStatistics = async () => {
		try {
			const result = await inspectionStore.getStatistics()
			if (result.success) {
				statistics.value = result.data
			}
		} catch (error) {
			console.error('加载统计信息失败:', error)
		}
	}
	
	const refresh = async () => {
		await Promise.all([
			loadInspections(true),
			loadStatistics(),
			syncOfflineData()
		])
	}
	
	const loadMore = async () => {
		if (!hasMore.value || loading.value) return
		
		loadMoreStatus.value = 'loading'
		page.value++
		
		await loadInspections()
	}
	
	const selectFilter = (filterValue) => {
		currentFilter.value = filterValue
	}
	
	const updateFilterCounts = () => {
		const inspections = inspectionStore.inspections || []
		
		filters.value.forEach(filter => {
			if (filter.value === 'all') {
				filter.count = inspections.length
			} else {
				filter.count = inspections.filter(
					inspection => inspection.status === filter.value
				).length
			}
		})
	}
	
	// 检查操作
	const viewInspectionDetail = (inspection) => {
		uni.navigateTo({
			url: `/pages/inspection/detail?id=${inspection.id}`
		})
	}
	
	const continueInspection = (inspection) => {
		uni.navigateTo({
			url: `/pages/inspection/checklist?inspectionId=${inspection.id}`
		})
	}
	
	const reviewInspection = (inspection) => {
		uni.navigateTo({
			url: `/pages/inspection/review?id=${inspection.id}`
		})
	}
	
	const showCreateOptions = () => {
		showCreateModal.value = true
	}
	
	const hideCreateOptions = () => {
		showCreateModal.value = false
	}
	
	const startNewInspection = async (inspectionType) => {
		hideCreateOptions()
		
		// 选择站点
		const sites = await siteStore.getSites({ status: 'assigned' })
		
		if (!sites.success || sites.data.length === 0) {
			uni.showModal({
				title: '提示',
				content: '没有可检查的站点，请先分配站点',
				showCancel: false
			})
			return
		}
		
		// 跳转到站点选择页面
		uni.navigateTo({
			url: `/pages/inspection/site-select?type=${inspectionType}`
		})
	}
	
	const showInspectionOptions = (inspection) => {
		const actions = []
		
		if (canContinue(inspection)) {
			actions.push('继续检查')
		}
		
		if (canReview(inspection)) {
			actions.push('审核')
		}
		
		if (inspection.status === 'draft') {
			actions.push('删除')
		}
		
		actions.push('查看详情')
		
		uni.showActionSheet({
			itemList: actions,
			success: (res) => {
				const action = actions[res.tapIndex]
				
				switch (action) {
					case '继续检查':
						continueInspection(inspection)
						break
					case '审核':
						reviewInspection(inspection)
						break
					case '删除':
						deleteInspection(inspection)
						break
					case '查看详情':
						viewInspectionDetail(inspection)
						break
				}
			}
		})
	}
	
	const deleteInspection = (inspection) => {
		uni.showModal({
			title: '确认删除',
			content: '确定要删除这个检查记录吗？',
			success: async (res) => {
				if (res.confirm) {
					const result = await inspectionStore.deleteInspection(inspection.id)
					if (result.success) {
						uni.showToast({
							title: '删除成功',
							icon: 'success'
						})
						await loadInspections(true)
					} else {
						uni.showToast({
							title: '删除失败',
							icon: 'error'
						})
					}
				}
			}
		})
	}
	
	// 离线数据管理
	const checkOfflineData = async () => {
		const pendingData = await offlineStore.getPendingData()
		
		if (pendingData.length > 0 && navigator.onLine) {
			// 有离线数据且网络可用，提示同步
			uni.showModal({
				title: '数据同步',
				content: `发现${pendingData.length}条离线数据，是否立即同步？`,
				success: (res) => {
					if (res.confirm) {
						syncOfflineData()
					}
				}
			})
		}
	}
	
	const syncOfflineData = async () => {
		try {
			isSyncing.value = true
			const result = await offlineStore.syncAllData()
			
			if (result.success) {
				uni.showToast({
					title: `同步成功 ${result.synced}条`,
					icon: 'success'
				})
				
				// 重新加载数据
				await loadInspections(true)
			} else {
				uni.showToast({
					title: '同步失败',
					icon: 'error'
				})
			}
		} catch (error) {
			console.error('同步失败:', error)
		} finally {
			isSyncing.value = false
		}
	}
	
	const checkSyncStatus = () => {
		const pendingCount = offlineStore.getPendingDataCount()
		
		if (pendingCount > 0) {
			uni.showModal({
				title: '离线数据',
				content: `有${pendingCount}条数据待同步，是否立即同步？`,
				success: (res) => {
					if (res.confirm) {
						syncOfflineData()
					}
				}
			})
		} else {
			uni.showToast({
				title: '数据已同步',
				icon: 'success'
			})
		}
	}
	
	// 工具函数
	const canContinue = (inspection) => {
		return ['draft', 'in_progress'].includes(inspection.status) &&
			inspection.inspector_id === userStore.userInfo?.id
	}
	
	const canReview = (inspection) => {
		return inspection.status === 'submitted' &&
			['admin', 'reviewer'].includes(userStore.userInfo?.role)
	}
	
	const isOfflineInspection = (inspection) => {
		return inspection.id && typeof inspection.id === 'string' && inspection.id.startsWith('offline_')
	}
	
	const getStatusClass = (status) => {
		const statusMap = {
			draft: 'status-draft',
			in_progress: 'status-progress',
			submitted: 'status-submitted',
			under_review: 'status-review',
			approved: 'status-approved',
			rejected: 'status-rejected'
		}
		return statusMap[status] || 'status-default'
	}
	
	const getStatusText = (status) => {
		const statusMap = {
			draft: '草稿',
			in_progress: '进行中',
			submitted: '已提交',
			under_review: '审核中',
			approved: '已通过',
			rejected: '已驳回'
		}
		return statusMap[status] || '未知'
	}
	
	const getInspectionTypeText = (type) => {
		const typeMap = {
			installation: '安装检查',
			opening: '新站点设备安装',
			maintenance: '维护检查'
		}
		return typeMap[type] || '检查'
	}
	
	const getProgressClass = (rate) => {
		if (rate >= 100) return 'progress-complete'
		if (rate >= 80) return 'progress-high'
		if (rate >= 50) return 'progress-medium'
		return 'progress-low'
	}
	
	const formatDateTime = (dateTime) => {
		if (!dateTime) return ''
		
		const date = new Date(dateTime)
		const now = new Date()
		const diff = now - date
		
		// 小于1小时显示分钟
		if (diff < 60 * 60 * 1000) {
			return `${Math.floor(diff / (60 * 1000))}分钟前`
		}
		
		// 小于24小时显示小时
		if (diff < 24 * 60 * 60 * 1000) {
			return `${Math.floor(diff / (60 * 60 * 1000))}小时前`
		}
		
		// 显示具体时间
		return date.toLocaleDateString() + ' ' + date.toLocaleTimeString('zh-CN', {
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	const formatCreateTime = (dateTime) => {
		if (!dateTime) return ''
		
		const date = new Date(dateTime)
		return date.toLocaleDateString() + ' ' + date.toLocaleTimeString('zh-CN', {
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	// 生命周期hooks
	onMounted(async () => {
		await loadInspections()
		await loadStatistics()
		checkOfflineData()
	})
	
	onPullDownRefresh(async () => {
		await refresh()
		uni.stopPullDownRefresh()
	})
	
	onReachBottom(() => {
		loadMore()
	})
</script>

<style scoped>
	.inspection-list-container {
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
		justify-content: space-between;
		align-items: center;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
	}
	
	.sync-status {
		display: flex;
		align-items: center;
		gap: 10rpx;
		padding: 10rpx 20rpx;
		background: rgba(255, 255, 255, 0.2);
		border-radius: 20rpx;
		font-size: 24rpx;
	}
	
	.sync-icon {
		font-size: 28rpx;
	}
	
	.sync-icon.syncing {
		animation: rotate 1s linear infinite;
	}
	
	@keyframes rotate {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}
	
	/* 统计卡片 */
	.stats-container {
		display: flex;
		background: white;
		margin: 20rpx;
		border-radius: 20rpx;
		padding: 30rpx 20rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.1);
	}
	
	.stat-item {
		flex: 1;
		text-align: center;
		display: flex;
		flex-direction: column;
		gap: 10rpx;
	}
	
	.stat-number {
		font-size: 48rpx;
		font-weight: bold;
		color: #333;
	}
	
	.stat-label {
		font-size: 24rpx;
		color: #999;
	}
	
	/* 筛选器 */
	.filter-container {
		background: white;
		margin: 0 20rpx 20rpx;
		border-radius: 20rpx;
		overflow: hidden;
	}
	
	.filter-scroll {
		white-space: nowrap;
	}
	
	.filter-tabs {
		display: flex;
		padding: 20rpx;
		gap: 20rpx;
	}
	
	.filter-tab {
		padding: 15rpx 25rpx;
		background: #f8f9fa;
		color: #666;
		border-radius: 25rpx;
		font-size: 28rpx;
		white-space: nowrap;
		transition: all 0.3s ease;
	}
	
	.filter-tab.active {
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
	}
	
	.filter-count {
		margin-left: 5rpx;
		font-size: 24rpx;
		opacity: 0.8;
	}
	
	/* 检查列表 */
	.inspection-scroll {
		flex: 1;
		padding: 0 20rpx;
	}
	
	.inspection-item {
		background: white;
		border-radius: 20rpx;
		margin-bottom: 20rpx;
		padding: 30rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
		transition: transform 0.2s ease;
	}
	
	.inspection-item:active {
		transform: scale(0.98);
	}
	
	.inspection-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 20rpx;
	}
	
	.site-name {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 5rpx;
	}
	
	.site-code {
		font-size: 24rpx;
		color: #999;
	}
	
	.status-badge {
		padding: 8rpx 16rpx;
		border-radius: 15rpx;
		font-size: 24rpx;
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
	
	/* 检查内容 */
	.content-row {
		display: flex;
		align-items: center;
		margin-bottom: 15rpx;
		gap: 15rpx;
	}
	
	.content-icon {
		font-size: 28rpx;
		width: 40rpx;
	}
	
	.content-text {
		font-size: 28rpx;
		color: #666;
		flex: 1;
	}
	
	/* 进度条 */
	.progress-container {
		margin-top: 20rpx;
		padding: 20rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
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
		height: 8rpx;
		background: #e9ecef;
		border-radius: 4rpx;
		overflow: hidden;
		margin-bottom: 10rpx;
	}
	
	.progress-fill {
		height: 100%;
		border-radius: 4rpx;
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
	}
	
	/* 评分 */
	.score-container {
		display: flex;
		align-items: center;
		gap: 15rpx;
		margin-top: 15rpx;
	}
	
	.score-label {
		font-size: 26rpx;
		color: #666;
	}
	
	.score-stars {
		display: flex;
		gap: 5rpx;
	}
	
	.star {
		font-size: 28rpx;
		color: #ddd;
	}
	
	.star.filled {
		color: #ffd700;
	}
	
	.score-value {
		font-size: 26rpx;
		font-weight: bold;
		color: #333;
	}
	
	/* 操作区域 */
	.inspection-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 25rpx;
		padding-top: 20rpx;
		border-top: 1rpx solid #f0f0f0;
	}
	
	.action-info {
		display: flex;
		align-items: center;
		gap: 15rpx;
	}
	
	.create-time {
		font-size: 24rpx;
		color: #999;
	}
	
	.offline-indicator {
		font-size: 22rpx;
		color: #dc3545;
		padding: 4rpx 8rpx;
		background: #f8d7da;
		border-radius: 8rpx;
	}
	
	.action-buttons {
		display: flex;
		align-items: center;
		gap: 15rpx;
	}
	
	.action-btn {
		padding: 10rpx 20rpx;
		border-radius: 15rpx;
		font-size: 24rpx;
		border: none;
	}
	
	.continue-btn {
		background: #007bff;
		color: white;
	}
	
	.review-btn {
		background: #28a745;
		color: white;
	}
	
	.action-arrow {
		font-size: 32rpx;
		color: #ccc;
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
	
	/* 浮动按钮 */
	.fab-container {
		position: fixed;
		bottom: 40rpx;
		right: 40rpx;
		z-index: 999;
	}
	
	.fab {
		width: 120rpx;
		height: 120rpx;
		border-radius: 60rpx;
		background: linear-gradient(135deg, #f97316, #fb923c);
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 8rpx 24rpx rgba(102, 126, 234, 0.4);
		transition: transform 0.2s ease;
	}
	
	.fab:active {
		transform: scale(0.95);
	}
	
	.fab-icon {
		font-size: 48rpx;
		color: white;
		font-weight: bold;
	}
	
	/* 创建选项弹窗 */
	.create-options-overlay {
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
	
	.create-options {
		background: white;
		border-radius: 20rpx;
		padding: 40rpx;
		width: 100%;
		max-width: 600rpx;
	}
	
	.create-title {
		font-size: 36rpx;
		font-weight: bold;
		text-align: center;
		margin-bottom: 40rpx;
		color: #333;
	}
	
	.create-item {
		display: flex;
		align-items: center;
		padding: 30rpx;
		margin-bottom: 20rpx;
		background: #f8f9fa;
		border-radius: 15rpx;
		gap: 25rpx;
	}
	
	.create-icon {
		font-size: 48rpx;
	}
	
	.create-info {
		flex: 1;
	}
	
	.create-name {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 8rpx;
		display: block;
	}
	
	.create-desc {
		font-size: 26rpx;
		color: #666;
		display: block;
	}
	
	.create-cancel {
		width: 100%;
		padding: 25rpx;
		background: #6c757d;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
		margin-top: 20rpx;
	}
	
	/* 加载更多 */
	.load-more {
		padding: 40rpx;
	}
</style>