<template>
	<view class="detail-container">
		<CustomNavbar :title="$t('inspection.detail')" :showBack="true" variant="brand" />
		
		<!-- 检查基础信息 -->
		<view class="inspection-header" v-if="inspectionData">
			<view class="header-content">
				<view class="status-badge" :class="getStatusClass(inspectionData.status)">
					<text class="status-text">{{ getStatusText(inspectionData.status) }}</text>
				</view>
				
				<view class="header-info">
					<text class="site-name">{{ inspectionData.site_name }}</text>
					<text class="inspection-type">{{ getInspectionTypeText(inspectionData.inspection_type) }}</text>
					<!-- 开站工单：设备上线/激活（ever）状态（不触发 OMC 实时查询） -->
					<view v-if="shouldShowOmcTags" class="omc-tags-row">
						<text class="omc-tag" :class="omcOnlineTagClass">{{ omcOnlineTagText }}</text>
						<text class="omc-tag" :class="omcActivatedTagClass">{{ omcActivatedTagText }}</text>
					</view>
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
						<text class="progress-rate">{{ $formatPercentInt(workOrderProgress ? workOrderProgress.percentage : (inspectionData.completion_rate || 0)) }}</text>
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
			<view class="detail-content-inner">
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
			
			<!-- 驳回意见卡片 -->
			<view class="detail-card reject-card" v-if="inspectionData.status === 'rejected' && inspectionData.review_comments">
				<view class="card-header">
					<text class="card-title reject-title">🚫 {{ $t('inspection.rejectOpinion') }}</text>
				</view>
				<view class="card-content">
					<view class="reject-content">
						<text class="reject-text">{{ getI18nText(inspectionData.review_comments, inspectionData.review_comments_i18n) }}</text>
					</view>
					<view class="reject-tip">
						<text class="tip-text">📝 {{ $t('inspection.rejectTip') }}</text>
					</view>
				</view>
			</view>
			
			<!-- 未绑定设备提醒卡片（仅设备级检查项需要绑定） -->
			<view class="unbound-reminder" v-if="unboundDevicesCount > 0 && inspectionData.status === 'in_progress'">
				<view class="reminder-header">
					<text class="reminder-icon">⚠️</text>
					<text class="reminder-title">{{ $t('inspection.pendingTasks') }}</text>
					<view class="reminder-badge">{{ unboundDevicesCount }}</view>
				</view>
				<view class="reminder-content">
					<text class="reminder-text">
						{{ $t('inspection.unboundCellsHint').replace('{count}', unboundDevicesCount) }}
					</text>
					<button class="reminder-action" @click="showUnboundList">
						{{ $t('inspection.viewDetails') }}
					</button>
				</view>
			</view>
			
			<!-- 检查项详情 -->
			<view class="detail-card">
				<view class="card-header check-items-header">
					<text class="card-title">{{ $t('inspection.checkItems') }}</text>
					<view class="filter-trigger u-pressable-subtle" :class="getFilterChipClass(currentFilter)" @click="openFilterSheet">
						<text class="filter-trigger-text">{{ currentFilterMeta.label }}</text>
						<view class="filter-trigger-badge">
							<text class="filter-trigger-badge-text">{{ currentFilterMeta.count }}</text>
						</view>
						<text class="filter-trigger-icon">▾</text>
					</view>
				</view>
				<view class="card-content">
					<view class="filter-chips">
						<view
							class="filter-chip u-pressable-subtle"
							v-for="filter in statusFilters"
							:key="filter.value"
							:class="[getFilterChipClass(filter.value), { active: currentFilter === filter.value }]"
							@click="switchFilter(filter.value)"
						>
							<text class="filter-chip-label">{{ filter.label }}</text>
							<view class="filter-chip-badge" :class="getFilterBadgeClass(filter.value)">
								<text class="filter-chip-badge-text">{{ getFilterCount(filter.value) }}</text>
							</view>
						</view>
					</view>
					<view class="check-items-list">
							<view 
								class="check-item"
								v-for="item in filteredCheckItems"
								:key="item.id"
								:class="[getCheckItemClass(item.status), getIssueHighlightClass(item)]"
							>
								<view class="item-header">
									<view class="item-status">
										<text class="status-icon">{{ getStatusIcon(item.status) }}</text>
									</view>
									<view class="item-info">
										<text class="item-name">{{ getCheckItemDisplayTitle(item) }}</text>
										<view class="item-meta">
											<text class="item-category">{{ getI18nText(item.category_name || item.category_id, item.category_name_i18n) }}</text>
											<text class="item-sector" v-if="item.sector_id">{{ $t('inspection.sector') }}{{ item.sector_id }}</text>
											<text class="item-cell" v-if="item.cell_id">{{ item.cell_id }}</text>
										</view>

										<!-- 问题项提示（审核不通过/警告/现场不合格） -->
										<view v-if="isIssueItem(item)" class="issue-hint">
											<text class="issue-badge" :class="'issue-badge-' + (item.review_status || item.status)">
												{{ item.review_status === 'fail' ? $t('inspection.fail') : (item.review_status === 'warning' ? $t('inspection.warning') : $t('inspection.failed')) }}
											</text>
											<text v-if="item.review_comments" class="issue-comment">{{ getI18nText(item.review_comments, item.review_comments_i18n) }}</text>
										</view>
										
										<!-- 设备绑定信息块：仅设备级检查项显示（小区级不需要绑定） -->
										<view class="equipment-info" v-if="isDeviceLevelItem(item)">
											<view v-if="item.equipment_sn" class="equipment-bound">
												<text class="equipment-icon">📱</text>
											<view class="equipment-detail">
												<text class="equipment-label">{{ $t('inspection.boundDevice') }}:</text>
												<text class="equipment-sn">{{ item.equipment_sn }}</text>
											</view>
										</view>
										<view v-else class="equipment-unbound">
											<text class="warning-icon">⚠️</text>
											<text class="warning-text">{{ $t('inspection.deviceNotBound') }}</text>
										</view>
									</view>
								</view>
								<view class="item-result" @click.stop="viewCheckItem(item)">
									<text class="review-status" v-if="item.review_status" :class="'review-'+item.review_status">
										{{ getReviewStatusText(item.review_status) }}
									</text>
									<text class="result-icon" v-if="item.validation_result && !item.validation_result.valid">⚠️</text>
									<text class="action-arrow">›</text>
								</view>
							</view>
							
							<view class="item-summary" v-if="item.status !== 'pending'">
								<text class="summary-text" v-if="item.photos && item.photos.length > 0">
									📷 {{ item.photos.length }}{{ $t('inspection.photosUnit') }}
								</text>
								<text class="summary-text" v-if="item.data_value && item.data_value.length > 0">
									📊 {{ item.data_value.length }}{{ $t('inspection.itemsUnit') }}
								</text>
								<text class="summary-text" v-if="item.checked_at">
									⏰ {{ formatTime(item.checked_at) }}
								</text>
							</view>
						</view>
					</view>
					
					<!-- 空状态 -->
					<view class="empty-items" v-if="filteredCheckItems.length === 0">
						<text class="empty-text">
							{{ $t('inspection.noInspectionItems') }}
						</text>
					</view>
				</view>
			</view>
			
			<!-- 审核信息 -->
			<view class="detail-card" v-if="inspectionData.reviewed_by || inspectionData.review_comments">
				<view class="card-header">
					<text class="card-title">{{ $t('inspection.reviewInfo') }}</text>
				</view>
				<view class="card-content">
					<view class="info-row" v-if="inspectionData.reviewer_name">
						<text class="info-label">{{ $t('inspection.reviewer') }}:</text>
						<text class="info-value">{{ inspectionData.reviewer_name }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.reviewed_at">
						<text class="info-label">{{ $t('inspection.reviewTime') }}:</text>
						<text class="info-value">{{ formatDateTime(inspectionData.reviewed_at) }}</text>
					</view>
					<view class="info-row" v-if="inspectionData.review_comments">
						<text class="info-label">{{ $t('inspection.reviewComments') }}:</text>
						<text class="info-value">{{ getI18nText(inspectionData.review_comments, inspectionData.review_comments_i18n) }}</text>
					</view>
				</view>
			</view>
			
			<!-- 备注信息 -->
			<view class="detail-card" v-if="inspectionData.notes || inspectionData.issues_found || inspectionData.recommendations">
				<view class="card-header">
					<text class="card-title">{{ $t('inspection.noteInfo') }}</text>
				</view>
				<view class="card-content">
					<view class="note-section" v-if="inspectionData.notes">
						<text class="note-label">{{ $t('inspection.notes') }}:</text>
						<text class="note-content">{{ inspectionData.notes }}</text>
					</view>
					<view class="note-section" v-if="inspectionData.issues_found">
						<text class="note-label">{{ $t('inspection.issuesFound') }}:</text>
						<text class="note-content">{{ inspectionData.issues_found }}</text>
					</view>
					<view class="note-section" v-if="inspectionData.recommendations">
						<text class="note-label">{{ $t('inspection.recommendations') }}:</text>
						<text class="note-content">{{ inspectionData.recommendations }}</text>
					</view>
				</view>
			</view>
			</view>
		</scroll-view>
		
		<!-- 未绑定设备列表弹窗 -->
		<view class="modal-overlay" v-if="showUnboundModal" @click="showUnboundModal = false">
			<view class="modal-content unbound-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">{{ $t('inspection.unboundDevicesList') }}</text>
					<view class="modal-close" @click="showUnboundModal = false">
						<uni-icons class="close-icon" type="closeempty" size="36rpx" color="#666" />
					</view>
				</view>
				<scroll-view class="unbound-list" scroll-y>
					<view class="unbound-item" 
						  v-for="item in unboundDevicesList" 
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

		<!-- 检查项筛选弹窗 -->
		<view class="filter-sheet-overlay" v-if="showFilterSheet" @click="closeFilterSheet">
			<view class="filter-sheet" @click.stop>
				<view class="filter-sheet-header">
					<text class="filter-sheet-title">{{ $t('inspection.status') }}</text>
					<view class="filter-sheet-close u-pressable-subtle" @click="closeFilterSheet">
						<text class="filter-sheet-close-icon">×</text>
					</view>
				</view>
				<view class="filter-sheet-list">
					<view
						class="filter-sheet-item u-pressable-subtle"
						v-for="filter in statusFilters"
						:key="filter.value"
						:class="[{ active: currentFilter === filter.value }, getFilterChipClass(filter.value)]"
						@click="selectFilterFromSheet(filter.value)"
					>
						<view class="filter-sheet-item-left">
							<text class="filter-sheet-item-label">{{ filter.label }}</text>
						</view>
						<view class="filter-sheet-item-right">
							<view class="filter-sheet-badge" :class="getFilterBadgeClass(filter.value)">
								<text class="filter-sheet-badge-text">{{ getFilterCount(filter.value) }}</text>
							</view>
							<text v-if="currentFilter === filter.value" class="filter-sheet-check">✓</text>
						</view>
					</view>
				</view>
				<view class="filter-sheet-safe"></view>
			</view>
		</view>
		
		<!-- 设备绑定历史记录弹窗 -->
		<view class="modal-overlay" v-if="showHistoryModal" @click="showHistoryModal = false">
			<view class="modal-content history-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">📜 {{ $t('inspection.bindingHistory') }}</text>
					<view class="modal-close" @click="showHistoryModal = false">
						<uni-icons class="close-icon" type="closeempty" size="36rpx" color="#666" />
					</view>
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
				{{ inspectionData.status === 'rejected' ? $t('inspection.modifyResult') : $t('inspection.continueInspection') }}
			</button>
			
			<button 
				class="action-btn review-btn" 
				v-if="canReview"
				@click="reviewInspection"
			>
				{{ $t('inspection.review') }}
			</button>
			
			<!-- 导出报告按钮为占位功能，已移除 -->
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-container" v-if="loading">
			<uni-load-more
				status="loading"
				:content-text="{
					contentdown: $t('messages.loadingInspection'),
					contentrefresh: $t('messages.loadingInspection'),
					contentnomore: $t('messages.loadFailed')
				}"
			></uni-load-more>
		</view>
		
		<!-- 检查项详情弹窗 -->
		<view class="item-detail-overlay" v-if="currentItem" @click="closeItemDetail">
			<view class="item-detail-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">{{ getCheckItemDisplayTitle(currentItem) }}</text>
					<view class="modal-close" @click="closeItemDetail">
						<uni-icons class="close-icon" type="closeempty" size="36rpx" color="#666" />
					</view>
				</view>
				
				<scroll-view class="modal-content" scroll-y>
					<!-- 检查项基本信息 -->
					<view class="modal-section">
						<text class="section-title">{{ $t('inspection.basicInfo') }}</text>
						<view class="info-grid">
							<view class="grid-item">
								<text class="grid-label">{{ $t('inspection.status') }}:</text>
								<text class="grid-value" :class="getStatusClass(currentItem.status)">
									{{ getStatusText(currentItem.status) }}
								</text>
							</view>
							<view class="grid-item" v-if="currentItem.sector_id">
								<text class="grid-label">{{ $t('inspection.sector') }}:</text>
								<text class="grid-value">{{ currentItem.sector_id }}</text>
							</view>
							<view class="grid-item">
								<text class="grid-label">{{ $t('inspection.checkType') }}:</text>
								<text class="grid-value">{{ getRequiredTypeText(currentItem.required_type) }}</text>
							</view>
						</view>
					</view>
					
					<!-- 检查数据 -->
					<view class="modal-section" v-if="currentItem.data_value && currentItem.data_value.length > 0">
						<text class="section-title">{{ $t('inspection.data') }}</text>
						<view class="data-list">
							<view 
								class="data-item"
								v-for="(dataItem, index) in currentItem.data_value"
								:key="dataItem.field_name || index"
							>
								<text class="data-label">{{ getDataFieldDisplayName(dataItem, index) }}:</text>
								<text class="data-value">{{ dataItem.value }}{{ dataItem.unit || '' }}</text>
							</view>
						</view>
					</view>
					
					<!-- 照片 -->
					<view class="modal-section" v-if="currentItem.photos && currentItem.photos.length > 0">
						<text class="section-title">{{ $t('inspection.photos') }} ({{ currentItem.photos.length }})</text>
						<view class="photo-grid">
							<view 
								class="photo-item" 
								v-for="(photo, index) in currentItem.photos" 
								:key="index"
								@click="onPhotoTap(currentItem.photos, index)"
							>
								<view class="photo-thumb-wrapper">
									<image
										v-if="getPhotoThumbSrc(photo)"
										class="photo-thumb"
										:src="getPhotoThumbSrc(photo)"
										mode="aspectFill"
										@error.stop="handlePhotoError(photo)"
									></image>
									<view v-else class="photo-thumb-placeholder"></view>
									<view
										v-if="getPhotoDisplayStatus(photo) !== 'ready'"
										class="photo-status-overlay"
										:class="'photo-status-' + getPhotoDisplayStatus(photo)"
										@click.stop="onPhotoStatusTap(photo)"
									>
											<text v-if="getPhotoDisplayStatus(photo) === 'downloading'" class="photo-status-text">
												{{ $formatPercentInt(getPhotoProgress(photo)) }}
											</text>
										<view v-else-if="getPhotoDisplayStatus(photo) === 'error'" class="photo-status-error">
											<text class="photo-status-text">{{ $t('site.loadFailed') }}</text>
											<text class="photo-status-sub">{{ $t('releaseNotes.retry') }}</text>
										</view>
									</view>
								</view>
							</view>
						</view>
					</view>
					
					<!-- 验证结果 -->
					<view class="modal-section" v-if="currentItem.validation_result">
						<text class="section-title">{{ $t('inspection.validationResult') }}</text>
						<view class="validation-info">
							<view class="validation-status" :class="currentItem.validation_result.valid ? 'valid' : 'invalid'">
								<text class="status-icon">{{ currentItem.validation_result.valid ? '✅' : '❌' }}</text>
								<text class="status-text">
									{{ currentItem.validation_result.valid ? $t('inspection.validationPassed') : $t('inspection.validationFailed') }}
								</text>
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
						<text class="section-title">{{ $t('inspection.reviewInfo') }}</text>
						<view class="review-info">
							<view class="review-status-item" v-if="currentItem.review_status">
								<text class="review-label">{{ $t('inspection.reviewStatus') }}:</text>
								<text class="review-value" :class="'review-'+currentItem.review_status">
									{{ getReviewStatusText(currentItem.review_status) }}
								</text>
							</view>
							<view class="review-comments-item" v-if="currentItem.review_comments">
								<text class="review-label">{{ $t('inspection.reviewComments') }}:</text>
								<text class="review-comments-text">{{ getI18nText(currentItem.review_comments, currentItem.review_comments_i18n) }}</text>
							</view>
							<view class="review-time-item" v-if="currentItem.reviewed_at">
								<text class="review-label">{{ $t('inspection.reviewTime') }}:</text>
								<text class="review-time">{{ formatDateTime(currentItem.reviewed_at) }}</text>
							</view>
						</view>
					</view>
					
					<!-- 备注 -->
					<view class="modal-section" v-if="currentItem.notes">
						<text class="section-title">{{ $t('inspection.notes') }}</text>
						<text class="note-text">{{ currentItem.notes }}</text>
					</view>
				</scroll-view>
			</view>
		</view>
		
		<!-- 地图选择器 -->
		<view class="map-selector-overlay" v-if="showMapSelector" @click="showMapSelector = false">
			<view class="map-selector" @click.stop>
				<view class="selector-title">{{ $t('site.mapSelectorTitle') }}</view>
				<view class="map-options">
					<view 
						class="map-option" 
						@click="selectMapType('amap')"
					>
						<view class="option-icon">🗺️</view>
						<view class="option-info">
							<text class="option-name">{{ $t('site.mapAmapName') }}</text>
							<text class="option-desc">{{ $t('site.mapAmapDesc') }}</text>
						</view>
						<text class="option-arrow">›</text>
					</view>
					<view 
						class="map-option" 
						@click="selectMapType('google')"
					>
						<view class="option-icon">🌏</view>
						<view class="option-info">
							<text class="option-name">{{ $t('site.mapGoogleName') }}</text>
							<text class="option-desc">{{ $t('site.mapGoogleDesc') }}</text>
						</view>
						<text class="option-arrow">›</text>
					</view>
				</view>
			</view>
		</view>

		<!-- 大图预览准备中（缓存/下载）：非阻塞展示 -->
		<view class="preview-loading-overlay" v-if="previewPreparing">
			<view class="preview-loading-card">
				<text class="preview-loading-title">{{ $t('common.loading') }}</text>
				<text class="preview-loading-sub">{{ previewProgress.done }}/{{ previewProgress.total }}</text>
				<view class="preview-loading-bar">
					<view class="preview-loading-bar-fill" :style="{ width: previewProgress.percent + '%' }"></view>
				</view>
					<text class="preview-loading-percent">{{ $formatPercentInt(previewProgress.percent) }}</text>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, watch, getCurrentInstance, onUnmounted } from 'vue'
	import { onLoad, onShow, onHide } from '@dcloudio/uni-app'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, createRequestConfig, getAuthHeaders, buildImageUrl, API_ENDPOINTS } from '@/config/api.js'
	import { createPhotoCacheContext, ensurePhotoCached } from '@/utils/photoCache.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	
	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const normalizeLocale = (value) => {
		const s = String(value || '').trim().toLowerCase().replace('_', '-')
		if (!s) return 'zh'
		if (s === 'zh' || s === 'zh-cn' || s === 'zh-hans') return 'zh'
		if (s === 'en' || s === 'en-us' || s === 'en-gb') return 'en'
		if (s === 'id' || s === 'id-id') return 'id'
		return s
	}

	const getI18nText = (baseText, i18nMap) => {
		const locale = normalizeLocale(languageStore.currentLocale)
		const base = baseText === null || baseText === undefined ? '' : String(baseText)
		if (!locale || locale === 'zh') return base
		if (i18nMap && typeof i18nMap === 'object') {
			const translated = i18nMap[locale]
			if (translated !== null && translated !== undefined && String(translated).trim() !== '') {
				return String(translated)
			}
		}
		return base
	}
	
	// 页面参数
	const inspectionId = ref('')
	
	// 响应式数据
	const loading = ref(true)
// 导出占位功能已移除
	const inspectionData = ref(null)
	const workOrderProgress = ref(null)
	const workOrderData = ref(null)
	const deviceStatus = ref({ checked_at: null, devices: [] })
	const deviceStatusLoading = ref(false)
	const omcEverSummary = ref(null)
	const omcEverLoading = ref(false)
	const inspectorInfo = ref(null)
	const checkItems = ref([])
	const currentFilter = ref('all')
	const currentItem = ref(null)
	const refreshing = ref(false)
	const isPageVisible = ref(false)
	const showMapSelector = ref(false)
	const showFilterSheet = ref(false)

	// 图片缓存/加载状态（按 photo.id 或 file_path）
	const photoCacheCtx = computed(() => createPhotoCacheContext(userStore.userInfo))
	const photoStateMap = ref({})
	const previewPreparing = ref(false)
	const previewProgress = ref({
		total: 0,
		done: 0,
		percent: 0
	})
	
	const isIssueItem = (item) => {
		const status = item?.status
		const reviewStatus = item?.review_status
		return status === 'failed' || reviewStatus === 'fail' || reviewStatus === 'warning'
	}

	// 筛选选项
	const statusFilters = [
		{ label: $t('inspection.allChecks'), value: 'all' },
		{ label: $t('inspection.completedChecks'), value: 'completed' },
		{ label: $t('inspection.issueChecks'), value: 'issue' },
		{ label: $t('inspection.inProgress'), value: 'in_progress' },
		{ label: $t('inspection.pendingChecks'), value: 'pending' }
	]

	const filterCounts = computed(() => {
		const items = checkItems.value || []
		const counts = {
			all: items.length,
			completed: 0,
			issue: 0,
			in_progress: 0,
			pending: 0
		}

		items.forEach(item => {
			if (!item) return
			if (item.status === 'completed') counts.completed += 1
			if (item.status === 'in_progress') counts.in_progress += 1
			if (item.status === 'pending') counts.pending += 1
			if (isIssueItem(item)) counts.issue += 1
		})

		return counts
	})

	const getFilterCount = (filterValue) => {
		return filterCounts.value?.[filterValue] ?? 0
	}

	const getFilterChipClass = (filterValue) => {
		const mapping = {
			all: 'filter-chip--all',
			completed: 'filter-chip--completed',
			issue: 'filter-chip--issue',
			in_progress: 'filter-chip--in-progress',
			pending: 'filter-chip--pending'
		}
		return mapping[filterValue] || 'filter-chip--all'
	}

	const getFilterBadgeClass = (filterValue) => {
		const mapping = {
			all: 'filter-badge--all',
			completed: 'filter-badge--completed',
			issue: 'filter-badge--issue',
			in_progress: 'filter-badge--in-progress',
			pending: 'filter-badge--pending'
		}
		return mapping[filterValue] || 'filter-badge--all'
	}

	const currentFilterMeta = computed(() => {
		const filter = statusFilters.find(f => f.value === currentFilter.value)
		return {
			label: filter ? filter.label : $t('common.all'),
			count: getFilterCount(currentFilter.value)
		}
	})
	
	// 计算属性
	const filteredCheckItems = computed(() => {
		if (currentFilter.value === 'all') {
			return checkItems.value
		}
		if (currentFilter.value === 'issue') {
			return checkItems.value.filter(isIssueItem)
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
	
	const getDeviceKey = (item) => {
		if (!item?.sector_id || !item?.band) return null
		return `${item.sector_id}_${item.band}`
	}
	
	// 设备级：cell_id === 扇区_频段（需要扫码绑定）
	const isDeviceLevelItem = (item) => {
		if (!item?.sector_id || !item?.band) return false
		const key = getDeviceKey(item)
		if (!key) return false
		// 防御：若 cell_id 缺失，按“设备级”处理（避免误放开绑定要求）
		if (!item.cell_id) return true
		return item.cell_id === key
	}
	
	// 未绑定设备（设备级）代表项列表（按 扇区×频段 去重）
	const unboundDeviceRepresentatives = computed(() => {
		const items = inspectionData.value?.check_items || []
		const deviceMap = new Map()
		
		items.forEach(it => {
			if (!isDeviceLevelItem(it)) return
			const key = getDeviceKey(it)
			if (!key) return
			if (!deviceMap.has(key)) deviceMap.set(key, [])
			deviceMap.get(key).push(it)
		})
		
		const unbound = []
		deviceMap.forEach(list => {
			const bound = list.some(x => x.equipment_sn)
			if (!bound && list.length) {
				unbound.push(list[0])
			}
		})
		
		return unbound
	})
	
	const unboundDevicesCount = computed(() => unboundDeviceRepresentatives.value.length)
	
	const unboundDevicesList = computed(() => {
		return unboundDeviceRepresentatives.value.map(item => ({
			id: item.id,
			name: item.item_name,
			cell_id: item.cell_id || getDeviceKey(item),
			sector_id: item.sector_id,
			band: item.band
		}))
	})

	const isOpeningInspection = computed(() => String(workOrderData.value?.type || '') === 'opening_inspection')
	const hasBoundDevicesHint = computed(() => (checkItems.value || []).some((it) => !!it?.equipment_sn))

	const shouldShowOmcTags = computed(() => {
		if (!isOpeningInspection.value) return false
		const s = omcEverSummary.value
		return !!(s && s.hasDevices)
	})

	const omcOnlineTagText = computed(() => {
		const s = omcEverSummary.value
		if (!s || !s.hasDevices) return ''
		if (s.error) return $t('common.unknown')
		return s.allEverOnline ? $t('site.omcEverOnlineYes') : $t('site.omcEverOnlineNo')
	})

	const omcActivatedTagText = computed(() => {
		const s = omcEverSummary.value
		if (!s || !s.hasDevices) return ''
		if (s.error) return $t('common.unknown')
		return s.allEverActivated ? $t('site.omcEverActivatedYes') : $t('site.omcEverActivatedNo')
	})

	const omcOnlineTagClass = computed(() => {
		const s = omcEverSummary.value
		if (!s || !s.hasDevices) return ''
		if (s.error) return 'omc-tag--unknown'
		return s.allEverOnline ? 'omc-tag--ok' : 'omc-tag--no'
	})

	const omcActivatedTagClass = computed(() => {
		const s = omcEverSummary.value
		if (!s || !s.hasDevices) return ''
		if (s.error) return 'omc-tag--unknown'
		return s.allEverActivated ? 'omc-tag--ok' : 'omc-tag--no'
	})

	const loadOmcEverSummary = async () => {
		const siteId = workOrderData.value?.site_id || inspectionData.value?.site_id
		if (!isOpeningInspection.value || !siteId || !userStore.token) {
			omcEverSummary.value = null
			return
		}
		if (omcEverLoading.value) return

		omcEverLoading.value = true
		try {
			const response = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.SITES.OMC_STATUS_EVER(siteId)),
				...createRequestConfig({ method: 'GET', headers: getAuthHeaders(userStore.token) })
			})
			if (response.statusCode === 200) {
				const sns = Array.isArray(response.data?.sns) ? response.data.sns : []
				omcEverSummary.value = {
					loaded: true,
					error: false,
					hasDevices: sns.length > 0,
					allEverOnline: !!response.data?.all_ever_online,
					allEverActivated: !!response.data?.all_ever_activated
				}
				return
			}
			throw new Error(response.data?.detail || 'load failed')
		} catch (e) {
			// 接口失败：仅在“能确认站点有绑定设备”时显示未知
			if (hasBoundDevicesHint.value) {
				omcEverSummary.value = {
					loaded: true,
					error: true,
					hasDevices: true,
					allEverOnline: false,
					allEverActivated: false
				}
				return
			}
			omcEverSummary.value = null
		} finally {
			omcEverLoading.value = false
		}
	}

	const OMC_EVER_AUTO_REFRESH_MS = 30 * 1000
	let omcEverTimer = null

	const startOmcEverAutoRefresh = () => {
		stopOmcEverAutoRefresh()
		omcEverTimer = setInterval(() => {
			void loadOmcEverSummary()
		}, OMC_EVER_AUTO_REFRESH_MS)
	}

	const stopOmcEverAutoRefresh = () => {
		if (omcEverTimer) {
			clearInterval(omcEverTimer)
			omcEverTimer = null
		}
	}
	
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
		startOmcEverAutoRefresh()
		isPageVisible.value = true
	})

	onHide(() => {
		stopOmcEverAutoRefresh()
	})

	onUnmounted(() => {
		stopOmcEverAutoRefresh()
	})

	const pickDefaultFilter = () => {
		if (inspectionData.value?.status === 'rejected') {
			currentFilter.value = 'issue'
			return
		}
		if (currentFilter.value !== 'issue') return
		currentFilter.value = 'all'
	}
	
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
				url: buildApiUrl(`/api/inspections/binding-history/${item.id}`),
				method: 'GET',
				header: {
					'Authorization': `Bearer ${userStore.token}`
				}
			})
			
			if (response.statusCode === 200) {
				bindingHistory.value = response.data.history || []
			} else {
				throw new Error(response.data.detail || $t('messages.dataLoadFailed'))
			}
		} catch (error) {
			console.error('获取绑定历史失败:', error)
			uni.showToast({
				title: $t('messages.dataLoadFailed'),
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
				
				const isOpening = response.data.type === 'opening_inspection'
				
				switch (status) {
					case 'PENDING':
						progressPercentage = 0
						break
					case 'ACTIVE': {
						// 如果是ACTIVE状态，根据检查项完成度动态计算
						const completionRate = inspectionData.value?.completion_rate || 0
						progressPercentage = Math.max(20, Math.min(65, 20 + (completionRate / 100) * 45))
						break
					}
					case 'SUBMITTED':
						progressPercentage = 65
						break
					case 'UNDER_REVIEW':
						progressPercentage = 75
						break
					case 'APPROVED':
						progressPercentage = isOpening ? 80 : 85
						break
					case 'ACTIVATED':
						progressPercentage = isOpening ? 90 : 95
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
	
	// 加载站点设备在线/激活状态（调用统一接口）
	const loadSiteDevices = async (refresh = false) => {
		if (!workOrderData.value || !workOrderData.value.site_id) {
			deviceStatus.value = { checked_at: null, devices: [] }
			return
		}
		try {
			deviceStatusLoading.value = true
			const response = await uni.request({
				url: buildApiUrl(`/api/sites/${workOrderData.value.site_id}/omc/devices${refresh ? '?refresh=1' : ''}`),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			
			if (response.statusCode === 200) {
				deviceStatus.value = {
					checked_at: response.data.checked_at || null,
					devices: Array.isArray(response.data.devices) ? response.data.devices : []
				}
			}
		} catch (error) {
			console.warn('获取站点设备状态失败:', error)
		} finally {
			deviceStatusLoading.value = false
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
						inspectionData.value.site_name = $t('site.siteWithId', { id: inspectionData.value.site_id })
					}
				}
			}
			
				// 加载检查项
				const itemsResult = await inspectionStore.getInspectionItems(inspectionId.value)
				if (itemsResult.success) {
					checkItems.value = itemsResult.data
				}

				// 设置默认筛选（驳回优先展示“问题项”）
				pickDefaultFilter()
				
					// 加载工单进度信息（如果检查关联了工单）
					if (inspectionData.value && inspectionData.value.work_order_id) {
						await loadWorkOrderProgress(inspectionData.value.work_order_id)
					}

					// 开站工单：加载站点设备 ever 状态（只读后端缓存）
					await loadOmcEverSummary()
				
				// 加载检查员信息
				if (inspectionData.value && inspectionData.value.inspector_id) {
					await loadInspectorInfo(inspectionData.value.inspector_id)
				}
			
		} catch (error) {
			console.error('❌ 检查详情加载异常:', error)
			uni.showToast({
				title: $t('messages.dataLoadFailed'),
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

	const openFilterSheet = () => {
		showFilterSheet.value = true
	}

	const closeFilterSheet = () => {
		showFilterSheet.value = false
	}

	const selectFilterFromSheet = (filterValue) => {
		switchFilter(filterValue)
		closeFilterSheet()
	}
	
	const viewCheckItem = (item) => {
		console.log('ViewCheckItem - Review data:', {
			review_status: item.review_status,
			review_comments: item.review_comments,
			reviewed_at: item.reviewed_at
		})
		currentItem.value = item
		primeCurrentItemPhotoCache()
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
	
// 分享功能已移除
	
// exportReport 已删除
	
	const openMap = () => {
		if (!inspectionData.value.latitude || !inspectionData.value.longitude) return
		showMapSelector.value = true
	}
	
	// 选择地图类型并跳转
	const selectMapType = (mapType) => {
		showMapSelector.value = false
		uni.navigateTo({
			url: `/pages/map/view?latitude=${inspectionData.value.latitude}&longitude=${inspectionData.value.longitude}&name=${encodeURIComponent(inspectionData.value.site_name || $t('inspection.inspectionLocation'))}&address=${encodeURIComponent(inspectionData.value.address || '')}&mapType=${mapType}`
		})
	}
	
	const getPhotoStateKey = (photo) => {
		if (!photo) return ''
		if (photo.id) return String(photo.id)
		const path = String(photo.file_path || '').trim()
		return path
	}

	const getPhotoRemoteUrl = (photo) => buildImageUrl(photo?.file_path || '')

	const isRemotePhoto = (photo) => {
		const url = getPhotoRemoteUrl(photo)
		return typeof url === 'string' && url.startsWith('http')
	}

	const ensurePhotoState = (photo) => {
		const key = getPhotoStateKey(photo)
		if (!key) return null
		if (!photoStateMap.value[key]) {
			photoStateMap.value[key] = {
				status: 'idle',
				progress: 0,
				src: '',
				error: ''
			}
		}
		return photoStateMap.value[key]
	}

	const setPhotoReady = (photo, localPath) => {
		const key = getPhotoStateKey(photo)
		if (!key) return
		photoStateMap.value[key] = {
			status: 'ready',
			progress: 100,
			src: String(localPath || '').trim(),
			error: ''
		}
	}

	const setPhotoError = (photo, error) => {
		const key = getPhotoStateKey(photo)
		if (!key) return
		photoStateMap.value[key] = {
			status: 'error',
			progress: 0,
			src: '',
			error: error ? String(error) : ''
		}
	}

	const cachePhotoIfNeeded = async (photo) => {
		if (!photo) return { ok: false, reason: 'no_photo' }

		// 本地临时照片：直接展示，不做缓存
		if (!photo.id || !isRemotePhoto(photo)) {
			return { ok: true, localPath: getPhotoRemoteUrl(photo), persisted: false, fromCache: true }
		}

		const state = ensurePhotoState(photo)
		if (state?.status === 'ready' && state?.src) {
			return { ok: true, localPath: state.src, persisted: true, fromCache: true }
		}

		if (state) {
			state.status = 'downloading'
			state.progress = 0
			state.src = ''
			state.error = ''
		}

		const remoteUrl = getPhotoRemoteUrl(photo)
		// downloadFile 不支持时：直接回退到网络图片展示（不做持久化缓存）
		if (typeof uni.downloadFile !== 'function') {
			setPhotoReady(photo, remoteUrl)
			return { ok: true, localPath: remoteUrl, persisted: false, fromCache: false }
		}

		const res = await ensurePhotoCached({
			photoId: photo.id,
			remoteUrl,
			ctx: photoCacheCtx.value,
			onProgress: (p) => {
				const s = ensurePhotoState(photo)
				if (s && s.status !== 'ready') s.progress = p
			}
		})

		if (res?.ok && res.localPath) {
			setPhotoReady(photo, res.localPath)
			return res
		}

		setPhotoError(photo, res?.error?.message || res?.reason || 'load_failed')
		return res
	}

	const primeCurrentItemPhotoCache = async () => {
		const photos = currentItem.value?.photos || []
		if (!Array.isArray(photos) || photos.length === 0) return

		const targets = photos.filter(p => p?.id && isRemotePhoto(p))
		if (targets.length === 0) return

		const concurrency = 2
		const queue = targets.slice()
		const workers = Array.from({ length: Math.min(concurrency, queue.length) }).map(async () => {
			while (queue.length) {
				const p = queue.shift()
				try {
					await cachePhotoIfNeeded(p)
				} catch (e) {
					// ignore
				}
			}
		})

		await Promise.all(workers)
	}

	const getPhotoThumbSrc = (photo) => {
		if (!photo) return ''
		if (!photo.id || !isRemotePhoto(photo)) return getPhotoRemoteUrl(photo)
		const key = getPhotoStateKey(photo)
		const state = key ? photoStateMap.value[key] : null
		return state?.status === 'ready' && state?.src ? state.src : ''
	}

	const getPhotoDisplayStatus = (photo) => {
		if (!photo) return 'ready'
		if (!photo.id || !isRemotePhoto(photo)) return 'ready'
		const key = getPhotoStateKey(photo)
		const state = key ? photoStateMap.value[key] : null
		if (!state) return 'downloading'
		if (state.status === 'ready') return 'ready'
		if (state.status === 'error') return 'error'
		return 'downloading'
	}

	const getPhotoProgress = (photo) => {
		const key = getPhotoStateKey(photo)
		const state = key ? photoStateMap.value[key] : null
		return typeof state?.progress === 'number' ? state.progress : 0
	}

	const onPhotoStatusTap = async (photo) => {
		const status = getPhotoDisplayStatus(photo)
		if (status !== 'error') return
		await cachePhotoIfNeeded(photo)
	}

	const handlePhotoError = async (photo) => {
		if (!photo?.id || !isRemotePhoto(photo)) return
		await cachePhotoIfNeeded(photo)
	}

	const buildPreviewUrls = (photos) => {
		const list = Array.isArray(photos) ? photos : []
		return list.map((p) => {
			if (!p?.id || !isRemotePhoto(p)) return getPhotoRemoteUrl(p)
			const key = getPhotoStateKey(p)
			const s = key ? photoStateMap.value[key] : null
			return (s?.status === 'ready' && s?.src) ? s.src : getPhotoRemoteUrl(p)
		})
	}

	const openPreview = (urls, currentIndex) => {
		const safeUrls = (urls || []).filter(Boolean)
		if (safeUrls.length === 0) return
		const idx = Math.min(Math.max(0, Number(currentIndex) || 0), safeUrls.length - 1)
		const current = safeUrls[idx]
		uni.previewImage({
			urls: safeUrls,
			current
		})
	}

	const onPhotoTap = async (photos, currentIndex) => {
		const list = Array.isArray(photos) ? photos : []
		if (list.length === 0) return

		// 若该图处于错误态，触发重试但不阻塞预览
		const idx = Math.min(Math.max(0, Number(currentIndex) || 0), list.length - 1)
		const currentPhoto = list[idx]
		if (getPhotoDisplayStatus(currentPhoto) === 'error') {
			cachePhotoIfNeeded(currentPhoto).catch(() => {})
		}

		// 不再等待“全部缓存完成”才允许预览：已缓存的用本地路径，其它用网络 URL
		const urls = buildPreviewUrls(list)
		openPreview(urls, idx)

		// 继续后台缓存，不阻塞预览
		primeCurrentItemPhotoCache().catch(() => {})
	}
	
	// 工具函数
	const getInspectionTypeText = (type) => {
		const typeMap = {
			installation: $t('inspection.installation'),
			opening: $t('inspection.opening'),
			maintenance: $t('inspection.maintenance')
		}
		return typeMap[type] || $t('inspection.check')
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
			return inspectorInfo.value.full_name || inspectorInfo.value.username || $t('messages.unknownInspector')
		}
		if (workOrderData.value && workOrderData.value.assigned_to_name) {
			return workOrderData.value.assigned_to_name
		}
		return $t('common.loading')
	}
	
	// 获取指派时间
	const getAssignedTime = () => {
		if (workOrderData.value && workOrderData.value.assigned_at) {
			return formatDateTime(workOrderData.value.assigned_at)
		}
		if (workOrderData.value && workOrderData.value.created_at) {
			return formatDateTime(workOrderData.value.created_at)
		}
		return $t('inspection.unknown')
	}
	
	// 获取优先级文本
	const getPriorityText = (priority) => {
		const priorityMap = {
			low: $t('inspection.priorityLow'),
			normal: $t('inspection.priorityNormal'),
			high: $t('inspection.priorityHigh'),
			urgent: $t('inspection.priorityUrgent')
		}
		return priorityMap[priority] || $t('inspection.priorityNormal')
	}
	
	// 获取工单类型文本
	const getWorkOrderTypeText = (taskType) => {
		const typeMap = {
			opening_inspection: $t('inspection.opening'),
			maintenance: $t('inspection.maintenance'),
			power_issue: $t('workorder.types.power_issue'),
			transmission_issue: $t('workorder.types.transmission_issue'),
			gps_issue: $t('workorder.types.gps_issue'),
			signal_issue: $t('workorder.types.signal_issue')
		}
		return typeMap[taskType] || $t('workorder.types.other')
	}

	const getStatusText = (status) => {
		const statusMap = {
			draft: $t('inspection.draft'),
			in_progress: $t('inspection.inProgress'),
			submitted: $t('inspection.submitted') || $t('inspection.completed'),
			under_review: $t('inspection.inReview'),
			approved: $t('inspection.approved') || $t('inspection.completed'),
			rejected: $t('inspection.rejected') || $t('inspection.failed'),
			completed: $t('inspection.completed'),
			pending: $t('inspection.pending'),
			failed: $t('inspection.failed')
		}
		return statusMap[status] || $t('inspection.unknown')
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
			photo: $t('inspection.photoOnly'),
			data: $t('inspection.dataOnly'),
			both: $t('inspection.photoAndData')
		}
		return typeMap[type] || $t('inspection.unknown')
	}

	const getDisplayItemName = (name) => {
		// 依赖当前语言，确保切换语言后能更新显示
		const _ = languageStore.currentLocale
		const raw = String(name || '').trim()
		if (!raw) return ''

		const sectorLabel = $t('inspection.sector')
		const deviceLabel = $t('inspection.device')
		const cellLabel = $t('inspection.cell')

		return raw
			.replace(/-\s*扇区\s*/g, `- ${sectorLabel} `)
			.replace(/-\s*设备\s*/g, `- ${deviceLabel} `)
			.replace(/-\s*小区\s*/g, `- ${cellLabel} `)
			.trim()
	}

	const getCheckItemDisplayTitle = (item) => {
		const name = getDisplayItemName(getI18nText(item?.item_name, item?.item_name_i18n))
		// 若 item_name 异常（例如 field_...），尝试从 fields 中找一个可读的 label 作为标题
		if (!name || /^field_\\d+/.test(name)) {
			const fields = item?.fields
			if (Array.isArray(fields) && fields.length > 0) {
				const firstLabel = fields
					.map(f => String(getI18nText(f?.label || '', f?.label_i18n) || '').trim())
					.find(v => v)
				if (firstLabel) return firstLabel
			}
			return name || $t('inspection.checkItem')
		}
		return name
	}

	const getDataFieldDisplayName = (dataItem, index) => {
		const rawName = String(dataItem?.field_name || '').trim()
		const fallback = $t('inspection.fieldNumber', { index: Number(index) + 1 })
		if (!rawName) return fallback

		const fields = currentItem.value?.fields
		if (Array.isArray(fields) && fields.length > 0) {
			const matchedById = fields.find(f => {
				const fid = String(f?.field_id || f?.id || f?.key || '').trim()
				return fid && fid === rawName
			})
			const labelFromId = String(getI18nText(matchedById?.label || matchedById?.name || matchedById?.title || '', matchedById?.label_i18n) || '').trim()
			if (labelFromId) return labelFromId

			const matchedByLabel = fields.find(f => {
				const label = String(f?.label || f?.name || f?.title || '').trim()
				return label && label === rawName
			})
			const labelFromLabel = String(getI18nText(matchedByLabel?.label || matchedByLabel?.name || matchedByLabel?.title || '', matchedByLabel?.label_i18n) || '').trim()
			if (labelFromLabel) return labelFromLabel
		}

		// field_xxx 兜底不展示原始ID，按顺序编号
		if (/^field_\\d+/.test(rawName)) return fallback
		return rawName
	}
	
	const formatDateTime = (dateTime) => {
		if (!dateTime) return ''
		const date = new Date(dateTime)
		const locale = languageStore.currentLocaleTag
		return date.toLocaleString(locale)
	}
	
	const formatCoordinates = (lat, lon) => {
		return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
	}
	
	const getReviewStatusText = (status) => {
		const statusMap = {
			pass: `✅ ${$t('inspection.pass')}`,
			fail: `❌ ${$t('inspection.fail')}`,
			warning: `⚠️ ${$t('inspection.warning')}`
		}
		return statusMap[status] || status
	}

	const getIssueHighlightClass = (item) => {
		if (item?.review_status === 'fail') return 'issue-fail'
		if (item?.review_status === 'warning') return 'issue-warning'
		if (item?.status === 'failed') return 'issue-failed'
		return ''
	}
	
	const getWorkOrderStatusText = (status) => {
		const type = workOrderData.value?.type
		// 开站检查看成一条单独文案（如果有）
		if (type === 'opening_inspection') {
			const openingMap = {
				PENDING: $t('workorder.pending'),
				ACTIVE: $t('workorder.inProgress'),
				SUBMITTED: $t('workorder.submitted'),
				UNDER_REVIEW: $t('workorder.underReview'),
				APPROVED: $t('workorder.approved'),
				ACTIVATED: $t('workorder.activated'),
				COMPLETED: $t('workorder.completed'),
				REJECTED: $t('workorder.rejected')
			}
			return openingMap[status] || status
		}
		const statusMap = {
			PENDING: $t('workorder.pending'),
			ACTIVE: $t('workorder.inProgress'),
			SUBMITTED: $t('workorder.submitted'),
			UNDER_REVIEW: $t('workorder.underReview'),
			APPROVED: $t('workorder.approved'),
			ACTIVATED: $t('workorder.activated'),
			COMPLETED: $t('workorder.completed'),
			REJECTED: $t('workorder.rejected')
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
        overflow: hidden;
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

	/* 开站工单：设备上线/激活状态标签 */
	.omc-tags-row {
		display: flex;
		gap: 12rpx;
		flex-wrap: wrap;
		margin-top: 12rpx;
	}

	.omc-tag {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 44rpx;
		padding: 0 16rpx;
		border-radius: 999rpx;
		font-size: 22rpx;
		font-weight: 600;
		border: 1rpx solid transparent;
	}

	.omc-tag--ok {
		background: rgba(34, 197, 94, 0.12);
		color: #16a34a;
		border-color: rgba(34, 197, 94, 0.24);
	}

	.omc-tag--no {
		background: rgba(107, 114, 128, 0.12);
		color: #6b7280;
		border-color: rgba(107, 114, 128, 0.24);
	}

	.omc-tag--unknown {
		background: rgba(148, 163, 184, 0.14);
		color: #64748b;
		border-color: rgba(148, 163, 184, 0.28);
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
		height: 0;
		min-height: 0;
	}

	.detail-content-inner {
		padding: 0 20rpx;
		padding-bottom: calc(160rpx + env(safe-area-inset-bottom));
		box-sizing: border-box;
	}
	
	.detail-card {
		background: var(--bg-elevated);
		border-radius: 20rpx;
		margin-bottom: 20rpx;
		box-shadow: var(--shadow-card);
		overflow: hidden;
		width: 100%;
		box-sizing: border-box;
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

	/* 检查项：统计 + 筛选（合并） */
	.check-items-header {
		gap: 16rpx;
	}

	.filter-trigger {
		display: inline-flex;
		align-items: center;
		gap: 10rpx;
		max-width: 60%;
		padding: 10rpx 14rpx;
		border-radius: 999rpx;
		background: rgba(var(--color-primary-rgb), 0.10);
		border: 1rpx solid rgba(var(--color-primary-rgb), 0.18);
		box-sizing: border-box;
	}

	.filter-trigger-text {
		font-size: 24rpx;
		font-weight: 700;
		color: var(--color-primary);
		max-width: 100%;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.filter-trigger-badge {
		flex-shrink: 0;
		min-width: 44rpx;
		padding: 4rpx 10rpx;
		border-radius: 999rpx;
		background: rgba(var(--color-primary-rgb), 0.18);
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.filter-trigger-badge-text {
		font-size: 22rpx;
		font-weight: 800;
		color: var(--color-primary);
	}

	.filter-trigger-icon {
		flex-shrink: 0;
		font-size: 24rpx;
		color: var(--color-primary);
		opacity: 0.85;
	}

	.filter-trigger.filter-chip--completed {
		background: rgba(34, 197, 94, 0.10);
		border-color: rgba(34, 197, 94, 0.18);
	}

	.filter-trigger.filter-chip--completed .filter-trigger-text,
	.filter-trigger.filter-chip--completed .filter-trigger-icon,
	.filter-trigger.filter-chip--completed .filter-trigger-badge-text { color: #16a34a; }

	.filter-trigger.filter-chip--completed .filter-trigger-badge { background: rgba(34, 197, 94, 0.18); }

	.filter-trigger.filter-chip--issue {
		background: rgba(239, 68, 68, 0.10);
		border-color: rgba(239, 68, 68, 0.18);
	}

	.filter-trigger.filter-chip--issue .filter-trigger-text,
	.filter-trigger.filter-chip--issue .filter-trigger-icon,
	.filter-trigger.filter-chip--issue .filter-trigger-badge-text { color: #dc2626; }

	.filter-trigger.filter-chip--issue .filter-trigger-badge { background: rgba(239, 68, 68, 0.18); }

	.filter-trigger.filter-chip--in-progress {
		background: rgba(59, 130, 246, 0.10);
		border-color: rgba(59, 130, 246, 0.18);
	}

	.filter-trigger.filter-chip--in-progress .filter-trigger-text,
	.filter-trigger.filter-chip--in-progress .filter-trigger-icon,
	.filter-trigger.filter-chip--in-progress .filter-trigger-badge-text { color: #2563eb; }

	.filter-trigger.filter-chip--in-progress .filter-trigger-badge { background: rgba(59, 130, 246, 0.18); }

	.filter-trigger.filter-chip--pending {
		background: rgba(100, 116, 139, 0.10);
		border-color: rgba(100, 116, 139, 0.18);
	}

	.filter-trigger.filter-chip--pending .filter-trigger-text,
	.filter-trigger.filter-chip--pending .filter-trigger-icon,
	.filter-trigger.filter-chip--pending .filter-trigger-badge-text { color: #475569; }

	.filter-trigger.filter-chip--pending .filter-trigger-badge { background: rgba(100, 116, 139, 0.18); }

	.filter-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 12rpx;
		padding-bottom: 24rpx;
		margin-bottom: 24rpx;
		border-bottom: 1rpx solid var(--border-soft);
	}

	.filter-chip {
		display: inline-flex;
		align-items: center;
		gap: 10rpx;
		padding: 10rpx 14rpx;
		border-radius: 999rpx;
		background: rgba(15, 23, 42, 0.03);
		border: 1rpx solid rgba(15, 23, 42, 0.08);
		box-sizing: border-box;
		max-width: 100%;
	}

	.filter-chip-label {
		font-size: 24rpx;
		font-weight: 700;
		color: #374151;
		white-space: nowrap;
	}

	.filter-chip-badge,
	.filter-sheet-badge {
		min-width: 44rpx;
		padding: 4rpx 10rpx;
		border-radius: 999rpx;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.filter-chip-badge-text,
	.filter-sheet-badge-text {
		font-size: 22rpx;
		font-weight: 800;
		color: #fff;
	}

	.filter-badge--all { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light)); }
	.filter-badge--completed { background: linear-gradient(135deg, #22c55e, #16a34a); }
	.filter-badge--issue { background: linear-gradient(135deg, #ef4444, #dc2626); }
	.filter-badge--in-progress { background: linear-gradient(135deg, #3b82f6, #2563eb); }
	.filter-badge--pending { background: linear-gradient(135deg, #64748b, #475569); }

	.filter-chip--all.active {
		background: rgba(var(--color-primary-rgb), 0.10);
		border-color: rgba(var(--color-primary-rgb), 0.18);
	}

	.filter-chip--completed.active {
		background: rgba(34, 197, 94, 0.10);
		border-color: rgba(34, 197, 94, 0.18);
	}

	.filter-chip--issue.active {
		background: rgba(239, 68, 68, 0.10);
		border-color: rgba(239, 68, 68, 0.18);
	}

	.filter-chip--in-progress.active {
		background: rgba(59, 130, 246, 0.10);
		border-color: rgba(59, 130, 246, 0.18);
	}

	.filter-chip--pending.active {
		background: rgba(100, 116, 139, 0.10);
		border-color: rgba(100, 116, 139, 0.18);
	}

	.filter-chip.active .filter-chip-label { color: #111827; }
	.filter-chip--all.active .filter-chip-label { color: var(--color-primary); }
	.filter-chip--completed.active .filter-chip-label { color: #16a34a; }
	.filter-chip--issue.active .filter-chip-label { color: #dc2626; }
	.filter-chip--in-progress.active .filter-chip-label { color: #2563eb; }
	.filter-chip--pending.active .filter-chip-label { color: #475569; }

	/* 筛选弹窗（自定义） */
	.filter-sheet-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.48);
		z-index: 1200;
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}

	.filter-sheet {
		width: 100%;
		max-width: 750rpx;
		background: var(--bg-elevated);
		border-radius: 28rpx 28rpx 0 0;
		padding: 24rpx 24rpx 0;
		box-sizing: border-box;
		box-shadow: 0 -24rpx 80rpx rgba(0, 0, 0, 0.22);
	}

	.filter-sheet-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16rpx;
		margin-bottom: 16rpx;
	}

	.filter-sheet-title {
		font-size: 30rpx;
		font-weight: 800;
		color: var(--text-primary);
	}

	.filter-sheet-close {
		width: 72rpx;
		height: 72rpx;
		border-radius: 36rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(15, 23, 42, 0.04);
		border: 1rpx solid rgba(15, 23, 42, 0.06);
	}

	.filter-sheet-close-icon {
		font-size: 44rpx;
		line-height: 1;
		color: #6b7280;
	}

	.filter-sheet-list {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
		max-height: 62vh;
		overflow-y: auto;
		padding-bottom: 20rpx;
	}

	.filter-sheet-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16rpx;
		padding: 18rpx 18rpx;
		border-radius: 18rpx;
		background: rgba(15, 23, 42, 0.03);
		border: 1rpx solid rgba(15, 23, 42, 0.06);
	}

	.filter-sheet-item-left {
		flex: 1;
		min-width: 0;
	}

	.filter-sheet-item-label {
		font-size: 28rpx;
		font-weight: 700;
		color: #111827;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.filter-sheet-item-right {
		display: inline-flex;
		align-items: center;
		gap: 12rpx;
		flex-shrink: 0;
	}

	.filter-sheet-check {
		font-size: 30rpx;
		font-weight: 800;
		color: var(--color-primary);
	}

	.filter-sheet-item.filter-chip--completed.active .filter-sheet-check { color: #16a34a; }
	.filter-sheet-item.filter-chip--issue.active .filter-sheet-check { color: #dc2626; }
	.filter-sheet-item.filter-chip--in-progress.active .filter-sheet-check { color: #2563eb; }
	.filter-sheet-item.filter-chip--pending.active .filter-sheet-check { color: #475569; }

	.filter-sheet-safe {
		height: calc(24rpx + env(safe-area-inset-bottom));
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

	.check-item.issue-fail,
	.check-item.issue-failed {
		background: #fef2f2;
		border-left-color: #dc2626;
	}

	.check-item.issue-warning {
		background: #fffbeb;
		border-left-color: #d97706;
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

	.issue-hint {
		margin-top: 8rpx;
		display: flex;
		gap: 10rpx;
		align-items: flex-start;
		flex-wrap: wrap;
	}

	.issue-badge {
		font-size: 22rpx;
		padding: 4rpx 10rpx;
		border-radius: 10rpx;
		font-weight: 600;
		flex-shrink: 0;
	}

	.issue-badge-fail {
		background: #fee2e2;
		color: #dc2626;
	}

	.issue-badge-warning {
		background: #fef3c7;
		color: #b45309;
	}

	.issue-badge-failed {
		background: #fee2e2;
		color: #dc2626;
	}

	.issue-comment {
		font-size: 24rpx;
		color: #6b7280;
		line-height: 1.4;
		flex: 1;
		min-width: 0;
		word-break: break-word;
		overflow-wrap: break-word;
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
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
	}
	
	.review-btn {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
	}
	
/* .export-btn 已废弃 */
	
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
		background: rgba(0, 0, 0, 0.55);
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
		box-shadow: 0 24rpx 80rpx rgba(0, 0, 0, 0.25);
		animation: modalIn 180ms ease-out;
	}
	
	@keyframes modalIn {
		from {
			transform: translateY(20rpx) scale(0.98);
			opacity: 0;
		}
		to {
			transform: translateY(0) scale(1);
			opacity: 1;
		}
	}
	
	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 28rpx 28rpx 22rpx;
		border-bottom: 1rpx solid var(--border-soft);
		background: rgba(255, 255, 255, 0.92);
		backdrop-filter: blur(8px);
	}
	
	.modal-title {
		font-size: 34rpx;
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
		background: rgba(0, 0, 0, 0.04);
	}
	
	.close-icon {
		font-size: 36rpx;
		color: #666;
	}
	
	.modal-content {
		flex: 1;
		padding: 22rpx;
		padding-bottom: 36rpx;
		overflow-y: auto;
		box-sizing: border-box;
		width: 100%;
		background: #f6f7fb;
	}
	
	.modal-section {
		margin-bottom: 22rpx;
		background: #fff;
		border-radius: 16rpx;
		padding: 22rpx;
		border: 1rpx solid rgba(0, 0, 0, 0.05);
		box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.06);
	}
	
	.section-title {
		font-size: 28rpx;
		font-weight: bold;
		color: var(--text-primary);
		margin-bottom: 18rpx;
		display: block;
		position: relative;
		padding-left: 16rpx;
	}
	
	.section-title::before {
		content: '';
		position: absolute;
		left: 0;
		top: 50%;
		transform: translateY(-50%);
		width: 6rpx;
		height: 24rpx;
		border-radius: 3rpx;
		background: var(--color-primary);
	}
	
	.info-grid {
		display: flex;
		flex-direction: column;
		gap: 16rpx;
	}
	
	.grid-item {
		display: flex;
		flex-direction: row;
		align-items: flex-start;
		gap: 14rpx;
		padding: 14rpx 16rpx;
		background: #f7f8fa;
		border-radius: 12rpx;
		width: 100%;
		box-sizing: border-box;
		min-width: 0;
		border: 1rpx solid rgba(0, 0, 0, 0.04);
	}
	
	.grid-label {
		font-size: 24rpx;
		color: #666;
		min-width: 140rpx;
		max-width: 240rpx;
		flex-shrink: 0;
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		display: inline-block;
		line-height: 1.4;
	}
	
	.grid-value {
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
	
	/* 数据列表 */
	.data-list {
		display: flex;
		flex-direction: column;
		gap: 14rpx;
	}
	
	.data-item {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 14rpx 16rpx;
		background: #f7f8fa;
		border-radius: 12rpx;
		gap: 14rpx;
		width: 100%;
		box-sizing: border-box;
		min-width: 0;
		border: 1rpx solid rgba(0, 0, 0, 0.04);
	}
	
	.data-label {
		font-size: 24rpx;
		color: #666;
		min-width: 140rpx;
		max-width: 240rpx;
		flex-shrink: 0;
		font-weight: 500;
		line-height: 1.4;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		display: inline-block;
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
		gap: 14rpx;
	}
	
	.photo-item {
		border-radius: 12rpx;
		overflow: hidden;
		background: #f7f8fa;
		border: 1rpx solid rgba(0, 0, 0, 0.04);
	}

	.photo-thumb-wrapper {
		position: relative;
		width: 100%;
		height: 150rpx;
	}

	.photo-thumb {
		width: 100%;
		height: 150rpx;
	}

	.photo-thumb-placeholder {
		width: 100%;
		height: 150rpx;
		background: linear-gradient(135deg, #eef2f7, #f7f8fb);
	}

	.photo-status-overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.45);
	}

	.photo-status-text {
		color: #fff;
		font-size: 26rpx;
		font-weight: 600;
	}

	.photo-status-error {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8rpx;
	}

	.photo-status-sub {
		color: rgba(255, 255, 255, 0.9);
		font-size: 22rpx;
	}

	/* 大图预览准备中 */
	.preview-loading-overlay {
		position: fixed;
		top: 24rpx;
		right: 24rpx;
		z-index: 3000;
		pointer-events: none;
	}

	.preview-loading-card {
		width: 420rpx;
		background: rgba(255, 255, 255, 0.96);
		border-radius: 18rpx;
		padding: 36rpx 32rpx;
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		gap: 18rpx;
		box-shadow: 0 16rpx 40rpx rgba(0, 0, 0, 0.18);
	}

	.preview-loading-title {
		font-size: 30rpx;
		font-weight: 600;
		color: #111827;
	}

	.preview-loading-sub {
		font-size: 24rpx;
		color: #6b7280;
	}

	.preview-loading-bar {
		width: 100%;
		height: 12rpx;
		background: #eef2f7;
		border-radius: 999rpx;
		overflow: hidden;
	}

	.preview-loading-bar-fill {
		height: 100%;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		border-radius: 999rpx;
	}

	.preview-loading-percent {
		font-size: 26rpx;
		font-weight: 600;
		color: #374151;
		align-self: flex-end;
	}
	
	/* 验证信息 */
	.validation-info {
		background: #f7f8fa;
		border-radius: 12rpx;
		padding: 18rpx;
		border: 1rpx solid rgba(0, 0, 0, 0.04);
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
		box-shadow: 0 4rpx 12rpx rgba(var(--color-primary-rgb), 0.14);
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
			background-color: var(--color-primary);
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
				color: var(--color-primary);
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
