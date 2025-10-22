<template>
	<view class="detail-container">
		<!-- 导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="back-button" @click="goBack">
					<text class="back-icon">←</text>
				</view>
				<text class="navbar-title">{{ $t('inspection.detail') }}</text>
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
					<text class="score-label">{{ $t('inspection.score') }}</text>
				</view>
			</view>
			
			<!-- 进度条 -->
			<view class="progress-container">
				<view class="progress-info">
					<text class="progress-text">{{ workOrderProgress ? $t('workorder.progress') : $t('inspection.progress') }}</text>
					<text class="progress-rate">{{ workOrderProgress ? workOrderProgress.percentage : (inspectionData.completion_rate || 0) }}%</text>
				</view>
				<view class="progress-bar">
					<view 
						class="progress-fill" 
						:style="{ width: (workOrderProgress ? workOrderProgress.percentage : (inspectionData.completion_rate || 0)) + '%' }"
						:class="getProgressClass(workOrderProgress ? workOrderProgress.percentage : inspectionData.completion_rate)"
					></view>
				</view>
				<text class="progress-detail" v-if="workOrderProgress">
					{{ $t('workorder.currentStatus') }}: {{ workOrderProgress.status_text }}
				</text>
				<text class="progress-detail" v-else>
					{{ inspectionData.completed_items || 0 }}/{{ inspectionData.total_items || 0 }} {{ $t('inspection.itemsCompleted') }}
				</text>
			</view>
		</view>
		
		<!-- 详情内容 -->
		<scroll-view 
			class="detail-content" 
			scroll-y 
			v-if="inspectionData"
			refresher-enabled 
			:refresher-triggered="refreshing" 
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<!-- 基本信息卡片 -->
			<view class="detail-card">
				<view class="card-header">
					<text class="card-title">{{ $t('inspection.basicInfo') }}</text>
				</view>
				<view class="card-content">
					<view class="info-row">
						<text class="info-label">{{ $t('inspection.inspector') }}:</text>
						<text class="info-value">{{ getInspectorName() }}</text>
					</view>
					<view class="info-row">
						<text class="info-label">{{ $t('inspection.assignedTime') }}:</text>
						<text class="info-value">{{ getAssignedTime() }}</text>
					</view>
					<view class="info-row" v-if="workOrderData">
						<text class="info-label">{{ $t('inspection.workOrderTitle') }}:</text>
						<text class="info-value">{{ workOrderData.title || $t('inspection.unknownWorkOrder') }}</text>
					</view>
					<view class="info-row" v-if="workOrderData">
						<text class="info-label">{{ $t('inspection.workOrderPriority') }}:</text>
						<text class="info-value">{{ getPriorityText(workOrderData.priority) }}</text>
					</view>
					<view class="info-row" v-if="workOrderData">
						<text class="info-label">{{ $t('inspection.workOrderType') }}:</text>
						<text class="info-value">{{ getWorkOrderTypeText(workOrderData.task_type) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.start_time">
						<text class="info-label">{{ $t('inspection.startTime') }}:</text>
						<text class="info-value">{{ formatDateTime(inspectionData.start_time) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.end_time">
						<text class="info-label">{{ $t('inspection.endTime') }}:</text>
						<text class="info-value">{{ formatDateTime(inspectionData.end_time) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.location">
						<text class="info-label">{{ $t('inspection.location') }}:</text>
						<text class="info-value">{{ inspectionData.location }}</text>
					</view>
				</view>
			</view>
			
			<!-- GPS信息卡片 -->
			<view class="detail-card" v-if="inspectionData.latitude && inspectionData.longitude">
				<view class="card-header">
					<text class="card-title">{{ $t('inspection.gpsInfo') }}</text>
					<view class="card-action" @click="openMap">
						<text class="action-text">{{ $t('inspection.viewMap') }}</text>
					</view>
				</view>
				<view class="card-content">
					<view class="info-row">
						<text class="info-label">{{ $t('inspection.coordinates') }}:</text>
						<text class="info-value">{{ formatCoordinates(inspectionData.latitude, inspectionData.longitude) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.gps_accuracy">
						<text class="info-label">{{ $t('inspection.accuracy') }}:</text>
						<text class="info-value">{{ inspectionData.gps_accuracy }}m</text>
					</view>
					<view class="info-row" v-if="inspectionData.address">
						<text class="info-label">{{ $t('inspection.address') }}:</text>
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
			
			<!-- 未绑定设备提醒卡片 -->
			<view class="unbound-reminder" v-if="unboundCellsCount > 0 && inspectionData.status === 'in_progress'">
				<view class="reminder-header">
					<text class="reminder-icon">⚠️</text>
					<text class="reminder-title">{{ $t('inspection.pendingTasks') }}</text>
					<view class="reminder-badge">{{ unboundCellsCount }}</view>
				</view>
				<view class="reminder-content">
					<text class="reminder-text">
						{{ $t('inspection.unboundCellsHint').replace('{count}', unboundCellsCount) }}
					</text>
					<button class="reminder-action" @click="showUnboundList">
						{{ $t('inspection.viewDetails') }}
					</button>
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
										<text class="item-cell" v-if="item.cell_id">{{ item.cell_id }}</text>
									</view>
									
									<!-- 新增：设备绑定信息块 -->
									<view class="equipment-info" v-if="item.sector_id && item.band">
										<view v-if="item.equipment_sn" class="equipment-bound">
											<text class="equipment-icon">📱</text>
											<view class="equipment-detail">
												<text class="equipment-label">{{ $t('inspection.boundDevice') }}:</text>
												<text class="equipment-sn">{{ item.equipment_sn }}</text>
											</view>
											<button class="history-btn" @click.stop="showBindingHistory(item)">
												📜 {{ $t('inspection.viewHistory') }}
											</button>
										</view>
										<view v-else class="equipment-unbound">
											<text class="warning-icon">⚠️</text>
											<text class="warning-text">{{ $t('inspection.deviceNotBound') }}</text>
										</view>
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
		
		<!-- 未绑定设备列表弹窗 -->
		<view class="modal-overlay" v-if="showUnboundModal" @click="showUnboundModal = false">
			<view class="modal-content unbound-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">{{ $t('inspection.unboundDevicesList') }}</text>
					<text class="modal-close" @click="showUnboundModal = false">✕</text>
				</view>
				<scroll-view class="unbound-list" scroll-y>
					<view class="unbound-item" 
						  v-for="item in unboundCellsList" 
						  :key="item.id"
						  @click="goToCheckItem(item.id)">
						<view class="unbound-item-info">
							<text class="unbound-item-name">{{ item.name }}</text>
							<text class="unbound-item-cell">{{ item.cell_id }}</text>
						</view>
						<text class="unbound-item-arrow">→</text>
					</view>
				</scroll-view>
			</view>
		</view>
		
		<!-- 设备绑定历史记录弹窗 -->
		<view class="modal-overlay" v-if="showHistoryModal" @click="showHistoryModal = false">
			<view class="modal-content history-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">📜 {{ $t('inspection.bindingHistory') }}</text>
					<text class="modal-close" @click="showHistoryModal = false">✕</text>
				</view>
				
				<view v-if="loadingHistory" class="loading-container">
					<text class="loading-text">{{ $t('common.loading') }}...</text>
				</view>
				
				<scroll-view v-else class="history-list" scroll-y>
					<view v-if="bindingHistory.length === 0" class="empty-history">
						<text class="empty-icon">📭</text>
						<text class="empty-text">{{ $t('inspection.noHistory') }}</text>
					</view>
					
					<view v-for="(record, index) in bindingHistory" :key="record.id" class="history-item">
						<view class="history-timeline">
							<view class="timeline-dot" :class="getActionClass(record.action)"></view>
							<view v-if="index < bindingHistory.length - 1" class="timeline-line"></view>
						</view>
						
						<view class="history-content">
							<view class="history-header">
								<text class="history-action" :class="getActionClass(record.action)">
									{{ getActionText(record.action) }}
								</text>
								<text class="history-time">{{ formatTime(record.operated_at) }}</text>
							</view>
							
							<view class="history-body">
								<view class="history-row">
									<text class="history-label">{{ $t('inspection.equipmentSN') }}:</text>
									<text class="history-value sn">{{ record.equipment_sn }}</text>
								</view>
								
								<view v-if="record.previous_equipment_sn" class="history-row">
									<text class="history-label">{{ $t('inspection.previousSN') }}:</text>
									<text class="history-value sn">{{ record.previous_equipment_sn }}</text>
								</view>
								
								<view class="history-row">
									<text class="history-label">{{ $t('inspection.operator') }}:</text>
									<text class="history-value">{{ record.operator.name }}</text>
								</view>
								
								<view v-if="record.latitude && record.longitude" class="history-row">
									<text class="history-label">{{ $t('inspection.location') }}:</text>
									<text class="history-value location">
										{{ record.latitude }}, {{ record.longitude }}
									</text>
								</view>
								
								<view v-if="record.notes" class="history-row">
									<text class="history-label">{{ $t('inspection.notes') }}:</text>
									<text class="history-value notes">{{ record.notes }}</text>
								</view>
							</view>
						</view>
					</view>
				</scroll-view>
			</view>
		</view>
		
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
		
		<!-- 地图选择器 -->
		<view class="map-selector-overlay" v-if="showMapSelector" @click="showMapSelector = false">
			<view class="map-selector" @click.stop>
				<view class="selector-title">选择地图</view>
				<view class="map-options">
					<view 
						class="map-option" 
						@click="selectMapType('amap')"
					>
						<view class="option-icon">🗺️</view>
						<view class="option-info">
							<text class="option-name">高德地图</text>
							<text class="option-desc">国内定位精准</text>
						</view>
						<text class="option-arrow">›</text>
					</view>
					<view 
						class="map-option" 
						@click="selectMapType('google')"
					>
						<view class="option-icon">🌏</view>
						<view class="option-info">
							<text class="option-name">谷歌地图</text>
							<text class="option-desc">全球地图覆盖</text>
						</view>
						<text class="option-arrow">›</text>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, watch, getCurrentInstance } from 'vue'
	import { onLoad, onShow } from '@dcloudio/uni-app'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, createRequestConfig, getAuthHeaders, buildImageUrl } from '@/config/api.js'
	
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	
	// 页面参数
	const inspectionId = ref('')
	
	// 响应式数据
	const loading = ref(true)
	const exporting = ref(false)
	const inspectionData = ref(null)
	const workOrderProgress = ref(null)
	const workOrderData = ref(null)
	const inspectorInfo = ref(null)
	const checkItems = ref([])
	const currentFilter = ref('all')
	const currentItem = ref(null)
	const refreshing = ref(false)
	const isPageVisible = ref(false)
	const showMapSelector = ref(false)
	
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
			   (['admin', 'manager', 'reviewer'].includes(userStore.userInfo?.role))
	})
	
	// 计算未绑定小区数量
	const unboundCellsCount = computed(() => {
		if (!inspectionData.value || !inspectionData.value.check_items) {
			return 0
		}
		
		// 统计小区级且未绑定设备的检查项
		return inspectionData.value.check_items.filter(item => {
			return item.sector_id && item.band && !item.equipment_sn
		}).length
	})
	
	// 未绑定小区列表
	const unboundCellsList = computed(() => {
		if (!inspectionData.value || !inspectionData.value.check_items) {
			return []
		}
		
		return inspectionData.value.check_items
			.filter(item => item.sector_id && item.band && !item.equipment_sn)
			.map(item => ({
				id: item.id,
				name: item.item_name,
				cell_id: item.cell_id,
				sector_id: item.sector_id,
				band: item.band
			}))
	})
	
	// 未绑定弹窗控制
	const showUnboundModal = ref(false)
	
	// 设备绑定历史记录
	const showHistoryModal = ref(false)
	const loadingHistory = ref(false)
	const bindingHistory = ref([])
	const currentHistoryItem = ref(null)
	
	// 生命周期
	// 页面初次加载
	onLoad((options) => {
		console.log('📱 检查详情页面 onLoad', options)
		if (options.id) {
			inspectionId.value = options.id
			isPageVisible.value = true
			loadInspectionDetail()
		}
	})
	
	// 每次页面显示时刷新数据
	onShow(() => {
		console.log('👁️ 检查详情页面 onShow', { 
			inspectionId: inspectionId.value,
			isPageVisible: isPageVisible.value 
		})
		
		// 避免重复刷新（onLoad后立即触发onShow）
		if (isPageVisible.value && inspectionId.value) {
			console.log('🔄 页面重新显示，自动刷新数据')
			loadInspectionDetail()
		}
		isPageVisible.value = true
	})
	
	// 监听语言变化，更新页面标题
	watch(() => languageStore.currentLocale, () => {
		uni.setNavigationBarTitle({
			title: $t('inspection.detail')
		})
	})
	
	onMounted(() => {
		// 动态设置页面标题
		uni.setNavigationBarTitle({
			title: $t('inspection.detail')
		})
	})
	
	// 方法
	// 显示未绑定列表弹窗
	const showUnboundList = () => {
		showUnboundModal.value = true
	}
	
	// 跳转到检查清单并定位到指定检查项
	const goToCheckItem = (itemId) => {
		showUnboundModal.value = false
		// 跳转到检查清单页面，并传递高亮检查项ID
		uni.navigateTo({
			url: `/pages/inspection/checklist?inspectionId=${inspectionData.value.id}&highlightItemId=${itemId}`
		})
	}
	
	// 显示设备绑定历史记录
	const showBindingHistory = async (item) => {
		currentHistoryItem.value = item
		showHistoryModal.value = true
		loadingHistory.value = true
		bindingHistory.value = []
		
		try {
			const response = await uni.request({
				url: `${API_BASE_URL}/api/inspections/binding-history/${item.id}`,
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				}
			})
			
			if (response.statusCode === 200) {
				bindingHistory.value = response.data.history || []
			} else {
				throw new Error(response.data.detail || '获取历史记录失败')
			}
		} catch (error) {
			console.error('获取绑定历史失败:', error)
			uni.showToast({
				title: $t('common.loadFailed'),
				icon: 'none'
			})
			showHistoryModal.value = false
		} finally {
			loadingHistory.value = false
		}
	}
	
	// 获取操作类型的样式类
	const getActionClass = (action) => {
		const classMap = {
			'bind': 'action-bind',
			'unbind': 'action-unbind',
			'rebind': 'action-rebind'
		}
		return classMap[action] || ''
	}
	
	// 获取操作类型的文本
	const getActionText = (action) => {
		const textMap = {
			'bind': $t('inspection.actionBind'),
			'unbind': $t('inspection.actionUnbind'),
			'rebind': $t('inspection.actionRebind')
		}
		return textMap[action] || action
	}
	
	// 格式化时间
	const formatTime = (isoString) => {
		if (!isoString) return ''
		
		const date = new Date(isoString)
		const year = date.getFullYear()
		const month = String(date.getMonth() + 1).padStart(2, '0')
		const day = String(date.getDate()).padStart(2, '0')
		const hours = String(date.getHours()).padStart(2, '0')
		const minutes = String(date.getMinutes()).padStart(2, '0')
		
		return `${year}-${month}-${day} ${hours}:${minutes}`
	}
	
	// 加载工单进度信息
	const loadWorkOrderProgress = async (workOrderId) => {
		try {
			const response = await uni.request({
				url: buildApiUrl(`/api/work-orders/${workOrderId}`),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				workOrderData.value = response.data
				
				// 计算工单进度百分比
				const status = response.data.status
				let progressPercentage = 0
				
				switch (status) {
					case 'PENDING':
						progressPercentage = 0
						break
					case 'ACTIVE':
						// 如果是ACTIVE状态，根据检查项完成度动态计算
						const completionRate = inspectionData.value?.completion_rate || 0
						progressPercentage = Math.max(20, Math.min(65, 20 + (completionRate / 100) * 45))
						break
					case 'SUBMITTED':
						progressPercentage = 65
						break
					case 'UNDER_REVIEW':
						progressPercentage = 75
						break
					case 'APPROVED':
						progressPercentage = 85
						break
					case 'ACTIVATED':
						progressPercentage = 95
						break
					case 'COMPLETED':
						progressPercentage = 100
						break
					case 'REJECTED':
						progressPercentage = 50
						break
					default:
						progressPercentage = 0
				}
				
				workOrderProgress.value = {
					percentage: progressPercentage,
					status: status,
					status_text: getWorkOrderStatusText(status)
				}
			}
		} catch (error) {
			console.warn('获取工单进度失败:', error)
			// 如果获取工单进度失败，仍然显示检查进度
			workOrderProgress.value = null
		}
	}
	
	// 加载检查员信息
	const loadInspectorInfo = async (inspectorId) => {
		try {
			const response = await uni.request({
				url: buildApiUrl(`/api/users/${inspectorId}`),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				inspectorInfo.value = response.data
				console.log('✅ 检查员信息加载成功:', response.data)
			}
		} catch (error) {
			console.warn('获取检查员信息失败:', error)
		}
	}
	
	const loadInspectionDetail = async () => {
		try {
			console.log('🔄 检查详情页面加载中...', { inspectionId: inspectionId.value })
			loading.value = true
			refreshing.value = true
			
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
			
			// 加载工单进度信息（如果检查关联了工单）
			if (inspectionData.value && inspectionData.value.work_order_id) {
				await loadWorkOrderProgress(inspectionData.value.work_order_id)
			}
			
			// 加载检查员信息
			if (inspectionData.value && inspectionData.value.inspector_id) {
				await loadInspectorInfo(inspectionData.value.inspector_id)
			}
			
		} catch (error) {
			console.error('❌ 检查详情加载异常:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
			refreshing.value = false
			console.log('✅ 检查详情页面加载完成')
		}
	}
	
	// 下拉刷新处理
	const handleRefresh = async () => {
		await loadInspectionDetail()
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
		showMapSelector.value = true
	}
	
	// 选择地图类型并跳转
	const selectMapType = (mapType) => {
		showMapSelector.value = false
		uni.navigateTo({
			url: `/pages/map/view?latitude=${inspectionData.value.latitude}&longitude=${inspectionData.value.longitude}&name=${encodeURIComponent(inspectionData.value.site_name || '检查位置')}&address=${encodeURIComponent(inspectionData.value.address || '')}&mapType=${mapType}`
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
	
	// 获取检查员姓名
	const getInspectorName = () => {
		if (inspectorInfo.value) {
			return inspectorInfo.value.full_name || inspectorInfo.value.username || '未知检查员'
		}
		if (workOrderData.value && workOrderData.value.assigned_to_name) {
			return workOrderData.value.assigned_to_name
		}
		return '加载中...'
	}
	
	// 获取指派时间
	const getAssignedTime = () => {
		if (workOrderData.value && workOrderData.value.assigned_at) {
			return formatDateTime(workOrderData.value.assigned_at)
		}
		if (workOrderData.value && workOrderData.value.created_at) {
			return formatDateTime(workOrderData.value.created_at)
		}
		return '未知'
	}
	
	// 获取优先级文本
	const getPriorityText = (priority) => {
		const priorityMap = {
			low: '低',
			normal: '正常',
			high: '高',
			urgent: '紧急'
		}
		return priorityMap[priority] || '正常'
	}
	
	// 获取工单类型文本
	const getWorkOrderTypeText = (taskType) => {
		const typeMap = {
			opening_inspection: '新站开通检查',
			maintenance: '维护工单',
			power_issue: '电源问题',
			transmission_issue: '传输问题',
			gps_issue: 'GPS问题',
			signal_issue: '信号问题'
		}
		return typeMap[taskType] || '其他'
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
	
	const getWorkOrderStatusText = (status) => {
		const statusMap = {
			PENDING: '待处理',
			ACTIVE: '执行中',
			SUBMITTED: '已提交',
			UNDER_REVIEW: '审核中',
			APPROVED: '已审核',
			ACTIVATED: '已开通',
			COMPLETED: '已完成',
			REJECTED: '已驳回'
		}
		return statusMap[status] || status
	}
</script>

<style scoped>
    .detail-container {
        height: 100vh;
        background: var(--bg-page);
        display: flex;
        flex-direction: column;
    }
	
	/* 导航栏 */
    .custom-navbar {
        background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
        padding: 44rpx 30rpx 20rpx;
        color: #fff;
    }
	
	.navbar-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	
	.back-button, .share-button {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 44rpx;
		background: rgba(255, 255, 255, 0.2);
	}
	
	.back-icon, .share-icon {
		font-size: 36rpx;
		color: white;
		font-weight: bold;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
		flex: 1;
		text-align: center;
		color: white;
	}
	
	.navbar-actions { 
		width: 88rpx; 
		display: flex; 
		justify-content: flex-end; 
	}
	
	/* 检查头部 */
	.inspection-header {
		background: var(--bg-elevated);
		margin: 20rpx;
		border-radius: 20rpx;
		padding: 30rpx;
		box-shadow: var(--shadow-card);
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
		color: var(--text-primary);
		display: block;
		margin-bottom: 8rpx;
	}
	
	.inspection-type { font-size: 26rpx; color: #6b7280; }
	
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
		color: #6b7280;
	}
	
	.progress-rate {
		font-size: 26rpx;
		font-weight: bold;
		color: var(--text-primary);
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
		background: var(--bg-elevated);
		border-radius: 20rpx;
		margin-bottom: 20rpx;
		box-shadow: var(--shadow-card);
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
		border-bottom: 1rpx solid var(--border-soft);
	}
	
	.card-title {
		font-size: 30rpx;
		font-weight: bold;
		color: var(--text-primary);
	}
	
	.card-action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx;
		padding: 0 24rpx;
		background: #f8f9fa;
		border-radius: 22rpx;
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
		color: #6b7280;
		min-width: 140rpx;
	}
	
	.info-value {
		font-size: 28rpx;
		color: var(--text-primary);
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
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx; /* >=44px */
		padding: 0 24rpx;
		background: #f8f9fa;
		border-radius: 22rpx;
		font-size: 26rpx;
		color: #666;
		transition: all 0.3s ease;
	}
	
	.filter-tab.active { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light)); color: #fff; }
	
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
	
	.item-cell {
		padding: 4rpx 12rpx;
		background-color: #ede9fe;
		color: #7c3aed;
		border-radius: 6rpx;
		font-size: 20rpx;
		font-weight: 500;
		margin-left: 8rpx;
	}
	
	/* 设备绑定信息样式 */
	.equipment-info {
		margin-top: 12rpx;
		padding-top: 12rpx;
		border-top: 1rpx solid #f3f4f6;
	}

	.equipment-bound {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 12rpx;
		background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
		border-radius: 12rpx;
		border: 1rpx solid #86efac;
		
		.equipment-icon {
			font-size: 36rpx;
			margin-right: 12rpx;
		}
		
		.equipment-detail {
			display: flex;
			flex-direction: column;
			flex: 1;
		}
		
		.equipment-label {
			font-size: 22rpx;
			color: #16a34a;
			margin-bottom: 4rpx;
		}
		
		.equipment-sn {
			font-size: 26rpx;
			font-weight: 600;
			color: #15803d;
			font-family: 'Courier New', monospace;
		}
		
		.history-btn {
			padding: 8rpx 16rpx;
			background: #16a34a;
			color: white;
			border-radius: 8rpx;
			font-size: 22rpx;
			border: none;
			white-space: nowrap;
			flex-shrink: 0;
		}
	}

	.equipment-unbound {
		display: flex;
		align-items: center;
		padding: 12rpx;
		background-color: #fff7ed;
		border-radius: 12rpx;
		border: 1rpx solid #fdba74;
		
		.warning-icon {
			font-size: 32rpx;
			margin-right: 8rpx;
		}
		
		.warning-text {
			font-size: 22rpx;
			color: #ea580c;
		}
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
		background: var(--bg-elevated);
		padding: 20rpx calc(20rpx + env(safe-area-inset-bottom));
		border-top: 1rpx solid var(--border-soft);
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
		background: var(--bg-elevated);
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
		border-bottom: 1rpx solid var(--border-soft);
	}
	
	.modal-title {
		font-size: 32rpx;
		font-weight: bold;
		color: var(--text-primary);
		flex: 1;
		word-break: break-word;
		overflow-wrap: break-word;
		hyphens: auto;
		line-height: 1.4;
		padding-right: 20rpx;
		max-width: calc(100% - 80rpx);
	}
	
	.modal-close {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 44rpx;
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
	
	/* 地图选择器 */
	.map-selector-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 3000;
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}
	
	.map-selector {
		width: 100%;
		background: var(--bg-elevated);
		border-radius: 30rpx 30rpx 0 0;
		padding: 40rpx 30rpx;
		animation: slideUp 0.3s ease-out;
	}
	
	@keyframes slideUp {
		from {
			transform: translateY(100%);
		}
		to {
			transform: translateY(0);
		}
	}
	
	.selector-title { font-size: 32rpx; font-weight: 600; color: var(--text-primary); text-align: center; margin-bottom: 30rpx; }
	
	.map-options {
		display: flex;
		flex-direction: column;
		gap: 20rpx;
	}
	
	.map-option {
		display: flex;
		align-items: center;
		gap: 20rpx;
		padding: 30rpx;
		background: #f9fafb;
		border-radius: 20rpx;
		border: 2rpx solid transparent;
		transition: all 0.3s ease;
	}
	
	.map-option:active { background: #fef3e2; border-color: var(--color-primary); }
	
	.option-icon {
		font-size: 48rpx;
		flex-shrink: 0;
	}
	
	.option-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4rpx;
	}
	
	.option-name {
		font-size: 28rpx;
		font-weight: 600;
		color: #111827;
	}
	
	.option-desc {
		font-size: 22rpx;
		color: #6b7280;
	}
	
	.option-arrow {
		font-size: 32rpx;
		color: #9ca3af;
		font-weight: bold;
		flex-shrink: 0;
	}
	
	/* 未绑定设备提醒卡片样式 */
	.unbound-reminder {
		margin: 24rpx;
		padding: 24rpx;
		background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
		border: 2rpx solid #fdba74;
		border-radius: 16rpx;
		box-shadow: 0 4rpx 12rpx rgba(249, 115, 22, 0.15);
	}

	.reminder-header {
		display: flex;
		align-items: center;
		margin-bottom: 12rpx;
		
		.reminder-icon {
			font-size: 36rpx;
			margin-right: 12rpx;
		}
		
		.reminder-title {
			font-size: 30rpx;
			font-weight: 600;
			color: #ea580c;
			flex: 1;
		}
		
		.reminder-badge {
			background-color: #ea580c;
			color: white;
			padding: 4rpx 12rpx;
			border-radius: 20rpx;
			font-size: 24rpx;
			font-weight: 600;
		}
	}

	.reminder-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
		
		.reminder-text {
			font-size: 26rpx;
			color: #c2410c;
			flex: 1;
			margin-right: 16rpx;
		}
		
		.reminder-action {
			padding: 12rpx 24rpx;
			background-color: #f97316;
			color: white;
			border-radius: 8rpx;
			font-size: 26rpx;
			border: none;
		}
	}
	
	/* 未绑定列表弹窗样式 */
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

	.unbound-modal {
		background: white;
		border-radius: 20rpx;
		width: 100%;
		max-width: 700rpx;
		max-height: 70vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		
		.modal-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 30rpx;
			border-bottom: 1rpx solid #f3f4f6;
			
			.modal-title {
				font-size: 32rpx;
				font-weight: 600;
				color: #111827;
			}
			
			.modal-close {
				font-size: 48rpx;
				color: #9ca3af;
				cursor: pointer;
			}
		}
		
		.unbound-list {
			max-height: 500rpx;
			padding: 16rpx 0;
		}
		
		.unbound-item {
			display: flex;
			align-items: center;
			justify-content: space-between;
			padding: 24rpx;
			border-bottom: 1rpx solid #f3f4f6;
			
			&:active {
				background-color: #f9fafb;
			}
			
			.unbound-item-info {
				display: flex;
				flex-direction: column;
			}
			
			.unbound-item-name {
				font-size: 28rpx;
				color: #111827;
				font-weight: 500;
				margin-bottom: 8rpx;
			}
			
			.unbound-item-cell {
				font-size: 24rpx;
				color: #6b7280;
				font-family: 'Courier New', monospace;
			}
			
			.unbound-item-arrow {
				font-size: 32rpx;
				color: #f97316;
			}
		}
	}
	
	/* 设备绑定历史记录弹窗样式 */
	.history-modal {
		max-width: 700rpx;
		max-height: 80vh;
		
		.loading-container {
			padding: 80rpx 30rpx;
			text-align: center;
			
			.loading-text {
				font-size: 28rpx;
				color: #9ca3af;
			}
		}
		
		.history-list {
			max-height: 600rpx;
			padding: 16rpx 0;
		}
		
		.empty-history {
			padding: 80rpx 30rpx;
			text-align: center;
			
			.empty-icon {
				font-size: 80rpx;
				display: block;
				margin-bottom: 20rpx;
			}
			
			.empty-text {
				font-size: 28rpx;
				color: #9ca3af;
			}
		}
		
		.history-item {
			display: flex;
			padding: 0 30rpx;
			margin-bottom: 32rpx;
			
			&:last-child {
				margin-bottom: 0;
			}
			
			.history-timeline {
				display: flex;
				flex-direction: column;
				align-items: center;
				margin-right: 24rpx;
				padding-top: 6rpx;
				
				.timeline-dot {
					width: 24rpx;
					height: 24rpx;
					border-radius: 50%;
					flex-shrink: 0;
					
					&.action-bind {
						background-color: #10b981;
						box-shadow: 0 0 0 4rpx #d1fae5;
					}
					
					&.action-unbind {
						background-color: #ef4444;
						box-shadow: 0 0 0 4rpx #fee2e2;
					}
					
					&.action-rebind {
						background-color: #f59e0b;
						box-shadow: 0 0 0 4rpx #fef3c7;
					}
				}
				
				.timeline-line {
					width: 2rpx;
					flex: 1;
					background-color: #e5e7eb;
					margin-top: 8rpx;
				}
			}
			
			.history-content {
				flex: 1;
				
				.history-header {
					display: flex;
					justify-content: space-between;
					align-items: center;
					margin-bottom: 12rpx;
					
					.history-action {
						font-size: 28rpx;
						font-weight: 600;
						
						&.action-bind {
							color: #10b981;
						}
						
						&.action-unbind {
							color: #ef4444;
						}
						
						&.action-rebind {
							color: #f59e0b;
						}
					}
					
					.history-time {
						font-size: 24rpx;
						color: #6b7280;
					}
				}
				
				.history-body {
					background: #f9fafb;
					border-radius: 12rpx;
					padding: 16rpx;
					
					.history-row {
						display: flex;
						margin-bottom: 12rpx;
						
						&:last-child {
							margin-bottom: 0;
						}
						
						.history-label {
							font-size: 24rpx;
							color: #6b7280;
							min-width: 140rpx;
							flex-shrink: 0;
						}
						
						.history-value {
							font-size: 24rpx;
							color: #111827;
							flex: 1;
							word-break: break-all;
							
							&.sn {
								font-family: 'Courier New', monospace;
								font-weight: 600;
								color: #059669;
							}
							
							&.location {
								font-family: 'Courier New', monospace;
								font-size: 22rpx;
							}
							
							&.notes {
								font-style: italic;
								color: #6b7280;
							}
						}
					}
				}
			}
		}
	}
</style>
