<template>
	<view class="checklist-container">
		<CustomNavbar :title="inspectionData?.site_name || $t('inspection.checklist')" :showBack="true" variant="brand">
			<template #right>
				<view class="u-nav-btn u-nav-btn--brand" @click="saveInspection">
					<uni-icons type="checkmarkempty" size="36rpx" color="#fff" />
				</view>
			</template>
		</CustomNavbar>
		
		<!-- 检查信息卡片 -->
		<view class="inspection-info">
			<view class="info-row">
				<text class="info-label">{{ $t('site.name') }}:</text>
				<text class="info-value">{{ inspectionData?.site_name }}</text>
			</view>
			<view class="info-row">
				<text class="info-label">{{ $t('site.type') }}:</text>
				<text class="info-value">{{ getInspectionTypeText(inspectionData?.inspection_type) }}</text>
			</view>
			<!-- 开站工单：设备上线/激活（ever）状态（不触发 OMC 实时查询） -->
			<view v-if="shouldShowOmcTags" class="omc-tags-row">
				<text class="omc-tag" :class="omcOnlineTagClass">{{ omcOnlineTagText }}</text>
				<text class="omc-tag" :class="omcActivatedTagClass">{{ omcActivatedTagText }}</text>
			</view>
			<view class="info-row">
				<text class="info-label">{{ $t('inspection.progress') }}:</text>
				<text class="info-value">{{ inspectionData?.completed_items || 0 }}/{{ inspectionData?.total_items || 0 }}</text>
				<view class="progress-bar">
					<view 
						class="progress-fill" 
						:style="{ width: (inspectionData?.completion_rate || 0) + '%' }"
					></view>
				</view>
			</view>
		</view>
		
		<!-- 分类标签 -->
		<view class="category-tabs">
			<scroll-view class="tabs-scroll" scroll-x>
				<view 
					class="tab-item"
					:class="{ active: currentCategory === 'all' }"
					@click="switchCategory('all')"
				>
					<text class="tab-text">{{ $t('inspection.allChecks') }} ({{ checkItems.length }})</text>
				</view>
				<view
					v-if="issueCount > 0"
					class="tab-item issue-tab"
					:class="{ active: currentCategory === 'issue' }"
					@click="switchCategory('issue')"
				>
					<text class="tab-text">{{ $t('inspection.issueChecks') }} ({{ issueCount }})</text>
				</view>
				<view 
					class="tab-item"
					:class="{ active: currentCategory === category.id }"
					v-for="category in categories"
					:key="category.id"
					@click="switchCategory(category.id)"
				>
					<text class="tab-text">{{ category.name }} ({{ getCategoryCount(category.id) }})</text>
				</view>
			</scroll-view>
		</view>
		
		<!-- 检查项列表 -->
		<scroll-view class="checklist-content" scroll-y>
			<view class="check-section" v-for="section in groupedCheckItems" :key="section.categoryId">
				<view class="section-header" v-if="currentCategory === 'all'">
					<text class="section-title">{{ section.categoryName }}</text>
					<text class="section-count">{{ section.items.length }}{{ $t('inspection.itemsUnit') }}</text>
				</view>
				
					<view 
						class="check-item"
						v-for="item in section.items"
						:key="item.id"
						:class="[getCheckItemClass(item.status), getIssueHighlightClass(item)]"
						@click="openCheckItem(item)"
					>
					<view class="item-header">
						<view class="item-status">
							<text class="status-icon">{{ getStatusIcon(item.status) }}</text>
						</view>
						<view class="item-info">
							<text class="item-name">{{ getDisplayItemName(getI18nText(item.item_name, item.item_name_i18n)) }}</text>
							<text class="item-id" v-if="item.sector_id">{{ $t('inspection.sector') }} {{ item.sector_id }}</text>

							<!-- 问题项提示（审核不通过/警告/现场不合格） -->
							<view v-if="isIssueItem(item)" class="issue-hint">
								<text class="issue-badge" :class="'issue-badge-' + (item.review_status || item.status)">
									{{ item.review_status === 'fail' ? $t('inspection.fail') : (item.review_status === 'warning' ? $t('inspection.warning') : $t('inspection.failed')) }}
								</text>
								<text v-if="item.review_comments" class="issue-comment">{{ getI18nText(item.review_comments, item.review_comments_i18n) }}</text>
							</view>
							
							<!-- 设备级检查项：显示绑定状态（小区级不需要绑定） -->
							<view class="equipment-binding-badge" v-if="isDeviceLevelItem(item)">
								<view v-if="isDeviceBound(item)" class="binding-status bound">
									<text class="binding-icon">✅</text>
									<view class="binding-info">
										<text class="binding-label">{{ $t('inspection.boundDevice') }}</text>
										<text class="binding-sn">{{ getDeviceEquipmentSn(item) }}</text>
									</view>
								</view>
								<view v-else class="binding-status unbound">
									<text class="binding-icon">⚠️</text>
									<text class="binding-label">{{ $t('inspection.needBinding') }}</text>
								</view>
							</view>
						</view>
						<view class="item-actions">
							<text class="required-badge" v-if="item.required_type === 'both'">{{ $t('inspection.photos') }}+{{ $t('inspection.data') }}</text>
							<text class="required-badge" v-else-if="item.required_type === 'photo'">{{ $t('inspection.photos') }}</text>
							<text class="required-badge" v-else-if="item.required_type === 'data'">{{ $t('inspection.data') }}</text>
							<text class="action-arrow">›</text>
						</view>
					</view>
					
					<view class="item-details" v-if="item.status !== 'pending'">
						<view class="detail-row" v-if="item.checked_at">
							<text class="detail-label">{{ $t('inspection.checkTime') }}:</text>
							<text class="detail-value">{{ formatDateTime(item.checked_at) }}</text>
						</view>
						
						<view class="detail-row" v-if="item.photos && item.photos.length > 0">
							<text class="detail-label">{{ $t('inspection.photos') }}:</text>
							<text class="detail-value">{{ item.photos.length }}{{ $t('inspection.photosUnit') }}</text>
						</view>
						
						<view class="detail-row" v-if="item.data_value && item.data_value.length > 0">
							<text class="detail-label">{{ $t('inspection.data') }}:</text>
							<text class="detail-value">{{ item.data_value.length }}{{ $t('inspection.itemsUnit') }}</text>
						</view>
						
							<view class="detail-row" v-if="item.validation_result && !item.validation_result.valid">
								<text class="detail-label">{{ $t('inspection.validationResult') }}:</text>
								<text class="detail-value error">{{ formatValidationErrors(item.validation_result) }}</text>
							</view>
						</view>
					</view>
				</view>
			
			<!-- 空状态 -->
			<view class="empty-state" v-if="filteredCheckItems.length === 0">
				<text class="empty-icon">📝</text>
				<text class="empty-title">{{ $t('inspection.noInspectionItems') }}</text>
				<text class="empty-desc">{{ $t('inspection.pleaseWaitTemplate') }}</text>
			</view>
		</scroll-view>
		
		<!-- 底部操作栏 -->
		<view class="bottom-actions">
			<button 
				class="action-btn draft-btn" 
				@click="saveDraft"
				:disabled="saving"
			>
				{{ saving ? $t('inspection.savingInProgress') : $t('inspection.saveDraft') }}
			</button>
			
			<button 
				class="action-btn submit-btn" 
				@click="submitInspection"
				:disabled="!canSubmit || submitting"
			>
				{{ submitting ? $t('inspection.submitInProgress') : $t('inspection.submitInspection') }}
			</button>
		</view>
		
		<!-- 隐藏的canvas用于水印处理 -->
		<canvas 
			canvas-id="watermarkCanvas" 
			style="position: absolute; left: -9999px; top: -9999px;" 
			:style="{ width: canvasWidth + 'px', height: canvasHeight + 'px' }"
		></canvas>
		
		<!-- 检查项详情弹窗 -->
		<view class="item-modal-overlay" v-if="currentItem" @click="closeItemModal">
			<view class="item-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">{{ getDisplayItemName(getI18nText(currentItem.item_name, currentItem.item_name_i18n)) }}</text>
					<view class="modal-close" @click="closeItemModal">
						<uni-icons class="close-icon" type="closeempty" size="36rpx" color="#666" />
					</view>
				</view>
				
				<scroll-view class="modal-content" scroll-y>
					<!-- 设备绑定部分（仅设备级检查项显示，小区级不需要绑定） -->
					<view class="modal-section" v-if="currentItem && isDeviceLevelItem(currentItem)">
						<text class="section-label">{{ $t('inspection.equipmentBinding') }}</text>
						<view class="equipment-binding-section">
							<view v-if="currentItem.equipment_sn" class="bound-equipment">
								<text class="bound-icon">✅</text>
								<view class="bound-info">
									<text class="bound-text">{{ $t('inspection.boundEquipment') }}</text>
									<text class="bound-sn">{{ currentItem.equipment_sn }}</text>
								</view>
								<button class="unbind-btn" @click="unbindEquipment">
									<text>{{ $t('inspection.unbind') }}</text>
								</button>
							</view>
							<view v-else class="unbind-equipment">
								<text class="unbind-icon">⚠️</text>
								<view class="unbind-info">
									<text class="unbind-text">{{ $t('inspection.pleaseBindFirst') }}</text>
									<text class="unbind-desc">{{ $t('inspection.sector') }} {{ currentItem.band ? `${currentItem.sector_id}_${currentItem.band}` : currentItem.sector_id }} {{ $t('inspection.needBindDesc') }}</text>
								</view>
								<button class="bind-btn" @click="scanEquipmentForBinding">
									<text class="btn-icon">📷</text>
									<text>{{ $t('inspection.scanBind') }}</text>
								</button>
							</view>
						</view>
					</view>
					
					<!-- 检查项基本信息 -->
					<view class="modal-section">
						<text class="section-label">{{ $t('inspection.basicInfo') }}</text>
						<view class="info-grid">
							<view class="grid-item">
								<text class="grid-label">{{ $t('inspection.checkType') }}:</text>
								<text class="grid-value">{{ getRequiredTypeText(currentItem.required_type) }}</text>
							</view>
							<view class="grid-item" v-if="currentItem.sector_id">
								<text class="grid-label">{{ $t('inspection.sector') }}:</text>
								<text class="grid-value">{{ currentItem.sector_id }}</text>
							</view>
							<view class="grid-item">
								<text class="grid-label">{{ $t('inspection.status') }}:</text>
								<text class="grid-value" :class="getStatusClass(currentItem.status)">
									{{ getStatusText(currentItem.status) }}
								</text>
							</view>
						</view>
						
						<!-- 检查项描述 -->
						<view class="item-description" v-if="getI18nText(currentItem.description, currentItem.description_i18n)">
							<view class="description-header">
								<text class="description-icon">💡</text>
								<text class="description-title">{{ $t('inspection.descriptionTitle') }}</text>
							</view>
							<text class="description-content">{{ getI18nText(currentItem.description, currentItem.description_i18n) }}</text>
						</view>
					</view>
					
						<!-- 照片部分（字段未启用拍照时走“未关联照片”模式） -->
						<view
							class="modal-section"
							v-if="currentItem.required_type === 'photo' || (currentItem.required_type === 'both' && !isFieldPhotoMode())"
						>
							<view class="section-header">
								<text class="section-label">{{ $t('inspection.photos') }} ({{ currentItem.photos?.length || 0 }})</text>
								<button class="add-photo-btn" @click="takePhoto">
								<text class="btn-icon">📷</text>
								<text class="btn-text">{{ $t('inspection.takePhoto') }}</text>
							</button>
						</view>
						
						<view class="photo-grid" v-if="currentItem.photos && currentItem.photos.length > 0">
							<view 
								class="photo-item" 
								v-for="(photo, index) in currentItem.photos" 
								:key="index"
								@click="onPhotoTap(photo)"
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
											{{ getPhotoProgress(photo) }}%
										</text>
										<view v-else-if="getPhotoDisplayStatus(photo) === 'error'" class="photo-status-error">
											<text class="photo-status-text">{{ $t('site.loadFailed') }}</text>
											<text class="photo-status-sub">{{ $t('releaseNotes.retry') }}</text>
										</view>
									</view>
								</view>
								<view class="photo-info">
									<text class="photo-time">{{ formatTime(photo.taken_at) }}</text>
									<view class="photo-actions">
										<text class="delete-photo" @click.stop="deletePhoto(index)">🗑️</text>
									</view>
								</view>
							</view>
						</view>
						
						<view class="no-photos" v-else>
							<text class="no-photos-text">{{ $t('inspection.noPhotosText') }}</text>
						</view>
					</view>
					
					<!-- 数据填写部分 -->
					<view class="modal-section" v-if="['data', 'both'].includes(currentItem.required_type)">
						<text class="section-label">{{ $t('inspection.dataEntry') }}</text>
						<view class="data-form">
							<view 
								class="form-item-wrapper"
								v-for="(dataField, index) in currentItem.dataFields"
								:key="index"
								v-show="shouldShowField(dataField)"
							>
								<view class="form-label-row">
									<view class="form-label-left">
										<text class="form-label">
											{{ dataField.label }}
											<text v-if="dataField.required" class="required-mark">*</text>
										</text>
										<!-- 显示约束提示 -->
										<text class="form-hint-inline" v-if="dataField.min !== undefined || dataField.max !== undefined">
											({{ dataField.min }} - {{ dataField.max }}{{ dataField.unit || '' }})
										</text>
									</view>
									<view
										v-if="dataField.help_text && String(dataField.help_text).trim() !== ''"
										class="field-help-icon"
										@click.stop="() => showFieldHelp(dataField)"
									>
										<uni-icons type="help" size="32rpx" color="#999" />
									</view>
									<button
										v-if="isFieldPhotoMode() && dataField.allow_photo === true"
										class="field-photo-btn"
										@click.stop="() => takePhotoForField(dataField)"
									>
										<text class="btn-icon">📷</text>
										<text class="btn-text">{{ $t('inspection.takePhoto') }}</text>
										<text v-if="dataField.photo_required" class="photo-required-mark">*</text>
										<text class="btn-count" v-if="getPhotosForField(dataField).length > 0">{{ getPhotosForField(dataField).length }}</text>
									</button>
								</view>
								
								<view class="form-input-row">
									<!-- 单选下拉框 -->
									<picker
										v-if="dataField.type === 'select_single'"
										class="form-picker-field"
										:range="dataField.options"
										range-key="label"
										:value="getPickerIndex(dataField)"
										@change="(e) => { onPickerChange(e, dataField); validateSingleField(dataField); }"
									>
										<view class="picker-display-value">
											<text class="picker-text" :class="{'placeholder-text': !dataField.value}">
												{{ getPickerDisplayValue(dataField) || $t('common.pleaseSelect') }}
											</text>
											<text class="picker-arrow">▼</text>
										</view>
									</picker>
									
									<!-- 多选框组 -->
									<checkbox-group 
										v-else-if="dataField.type === 'select_multi'"
										@change="(e) => { onCheckboxChange(e, dataField); validateSingleField(dataField); }"
										class="checkbox-group"
									>
										<label 
											v-for="option in dataField.options" 
											:key="option.value"
											class="checkbox-item"
										>
											<checkbox 
												:value="option.value" 
												:checked="isChecked(dataField.value, option.value)"
												color="var(--color-primary)"
											/>
											<text class="checkbox-label">{{ option.label }}</text>
										</label>
									</checkbox-group>
									
									<!-- 布尔开关 -->
									<view v-else-if="dataField.type === 'boolean'" class="switch-wrapper">
										<switch 
											:checked="dataField.value === true || dataField.value === 'true'"
											@change="(e) => { onSwitchChange(e, dataField); validateSingleField(dataField); }"
											color="var(--color-primary)"
											class="form-switch-field"
										/>
										<text class="switch-label">
											{{ (dataField.value === true || dataField.value === 'true') ? $t('common.yes') : $t('common.no') }}
										</text>
									</view>
									
									<!-- 日期选择器 -->
									<picker
										v-else-if="dataField.type === 'date'"
										mode="date"
										:value="dataField.value || getCurrentDate()"
										@change="(e) => { onDateChange(e, dataField); validateSingleField(dataField); }"
										class="form-picker-field"
									>
										<view class="picker-display-value">
											<text class="picker-text" :class="{'placeholder-text': !dataField.value}">
												{{ dataField.value || $t('common.pleaseSelectDate') }}
											</text>
											<text class="picker-icon">📅</text>
										</view>
									</picker>
									
									<!-- 时间选择器 -->
									<picker
										v-else-if="dataField.type === 'time'"
										mode="time"
										:value="dataField.value || getCurrentTime()"
										@change="(e) => { onTimeChange(e, dataField); validateSingleField(dataField); }"
										class="form-picker-field"
									>
										<view class="picker-display-value">
											<text class="picker-text" :class="{'placeholder-text': !dataField.value}">
												{{ dataField.value || $t('common.pleaseSelectTime') }}
											</text>
											<text class="picker-icon">🕐</text>
										</view>
									</picker>
									
									<!-- 日期时间选择器 -->
									<view v-else-if="dataField.type === 'datetime'" class="datetime-picker-group">
										<picker
											mode="date"
											:value="getDatePart(dataField.value)"
											@change="(e) => { onDatetimeChange(e, 'date', dataField); validateSingleField(dataField); }"
											class="datetime-date-picker"
										>
											<view class="picker-display-value small">
												<text class="picker-text" :class="{'placeholder-text': !getDatePart(dataField.value)}">
													{{ getDatePart(dataField.value) || $t('common.date') }}
												</text>
												<text class="picker-icon">📅</text>
											</view>
										</picker>
										
										<picker
											mode="time"
											:value="getTimePart(dataField.value)"
											@change="(e) => { onDatetimeChange(e, 'time', dataField); validateSingleField(dataField); }"
											class="datetime-time-picker"
										>
											<view class="picker-display-value small">
												<text class="picker-text" :class="{'placeholder-text': !getTimePart(dataField.value)}">
													{{ getTimePart(dataField.value) || $t('common.time') }}
												</text>
												<text class="picker-icon">🕐</text>
											</view>
										</picker>
									</view>
									
									<!-- 富文本区域 -->
									<textarea 
										v-else-if="dataField.type === 'rich_text'"
										class="form-textarea-field"
										:placeholder="$t('common.pleaseEnterField', { field: dataField.label })"
										v-model="dataField.value"
										@input="onDataChange(dataField)"
										@blur="validateSingleField(dataField)"
										:maxlength="dataField.constraints?.max_length || -1"
									/>
									
									<!-- 数字输入框 -->
									<view v-else-if="dataField.type === 'number'" class="input-with-unit">
										<input 
											class="form-input-field"
											type="number"
											:placeholder="$t('common.pleaseEnterField', { field: dataField.label })"
											v-model="dataField.value"
											@input="onDataChange(dataField)"
											@blur="validateSingleField(dataField)"
										/>
										<text class="input-unit" v-if="dataField.unit">{{ dataField.unit }}</text>
									</view>
									
									<!-- 文本输入框（默认） -->
									<input 
										v-else
										class="form-input-field"
										type="text"
										:placeholder="$t('common.pleaseEnterField', { field: dataField.label })"
										v-model="dataField.value"
										@input="onDataChange(dataField)"
										@blur="validateSingleField(dataField)"
									/>
								</view>
								
								<!-- 字段错误提示 -->
								<text class="field-error" v-if="dataField.error">
									⚠️ {{ dataField.error }}
								</text>
								
									<!-- 字段帮助提示 -->
									<text class="field-hint" v-if="getFieldHint(dataField)">
										💡 {{ getFieldHint(dataField) }}
									</text>

									<!-- 字段照片（按 field_id 归属） -->
									<view
										class="photo-grid field-photo-grid"
										v-if="isFieldPhotoMode() && getPhotosForField(dataField).length > 0"
									>
										<view
											class="photo-item"
											v-for="(photo, pIndex) in getPhotosForField(dataField)"
											:key="photo.id || pIndex"
											@click="onPhotoTap(photo)"
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
														{{ getPhotoProgress(photo) }}%
													</text>
													<view v-else-if="getPhotoDisplayStatus(photo) === 'error'" class="photo-status-error">
														<text class="photo-status-text">{{ $t('site.loadFailed') }}</text>
														<text class="photo-status-sub">{{ $t('releaseNotes.retry') }}</text>
													</view>
												</view>
											</view>
											<view class="photo-info">
												<text class="photo-time">{{ formatTime(photo.taken_at) }}</text>
												<view class="photo-actions">
													<text class="delete-photo" @click.stop="deletePhoto(photo)">🗑️</text>
												</view>
											</view>
										</view>
									</view>
								</view>
							</view>

							<!-- 未关联字段的历史照片（只读展示/可删除） -->
							<view
								class="unlinked-photos"
								v-if="isFieldPhotoMode() && getUnlinkedPhotos().length > 0"
							>
								<text class="section-label">未关联照片 ({{ getUnlinkedPhotos().length }})</text>
								<view class="photo-grid">
									<view
										class="photo-item"
										v-for="(photo, pIndex) in getUnlinkedPhotos()"
										:key="photo.id || pIndex"
										@click="onPhotoTap(photo)"
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
													{{ getPhotoProgress(photo) }}%
												</text>
												<view v-else-if="getPhotoDisplayStatus(photo) === 'error'" class="photo-status-error">
													<text class="photo-status-text">{{ $t('site.loadFailed') }}</text>
													<text class="photo-status-sub">{{ $t('releaseNotes.retry') }}</text>
												</view>
											</view>
										</view>
										<view class="photo-info">
											<text class="photo-time">{{ formatTime(photo.taken_at) }}</text>
											<view class="photo-actions">
												<text class="delete-photo" @click.stop="deletePhoto(photo)">🗑️</text>
											</view>
										</view>
									</view>
								</view>
							</view>
							
							<!-- 验证结果 -->
							<view class="validation-result" v-if="currentItem.validation_result">
								<view class="result-header">
								<text class="result-title">{{ $t('inspection.validationResult') }}</text>
								<text 
									class="result-status"
									:class="currentItem.validation_result.valid ? 'valid' : 'invalid'"
								>
									{{ currentItem.validation_result.valid ? `✅ ${$t('inspection.pass')}` : `❌ ${$t('inspection.fail')}` }}
								</text>
							</view>
								<view class="result-errors" v-if="!currentItem.validation_result.valid">
									<text 
										class="error-item" 
										v-for="error in getValidationErrorList(currentItem.validation_result)"
										:key="error"
									>
										• {{ error }}
									</text>
								</view>
						</view>
					</view>
					
					<!-- 备注 -->
					<view class="modal-section">
						<text class="section-label">{{ $t('inspection.remarks') }}</text>
						<textarea 
							class="note-textarea"
							:placeholder="$t('inspection.addCheckNote')"
							v-model="currentItem.notes"
							@input="onNotesChange"
						></textarea>
					</view>
				</scroll-view>
				
				<view class="modal-actions">
					<button class="modal-btn cancel-btn" @click="closeItemModal">{{ $t('inspection.cancel') }}</button>
					<button class="modal-btn save-btn" @click="saveCurrentItem" :disabled="savingItem">
						{{ savingItem ? $t('inspection.savingInProgress') : $t('inspection.save') }}
					</button>
				</view>
			</view>
		</view>
		
		<!-- 提交前核查弹窗 -->
		<view class="modal-overlay" v-if="showPreSubmitCheckModal" @click="showPreSubmitCheckModal = false">
			<view class="modal-content pre-submit-modal" @click.stop>
				<view class="modal-header">
					<text class="modal-title">⚠️ {{ $t('inspection.preSubmitCheck') }}</text>
					<view class="modal-close" @click="showPreSubmitCheckModal = false">
						<uni-icons class="close-icon" type="closeempty" size="36rpx" color="#666" />
					</view>
				</view>
				
				<view class="warning-section">
					<text class="warning-text">
						{{ $t('inspection.unboundCellsWarning').replace('{count}', preSubmitUnboundList.length) }}
					</text>
				</view>
				
				<scroll-view class="checklist-scroll" scroll-y>
					<view class="checklist-item" 
						  v-for="item in preSubmitUnboundList" 
						  :key="item.id">
						<view class="checklist-item-info">
							<text class="checklist-item-name">{{ getDisplayItemName(getI18nText(item.item_name, item.item_name_i18n)) }}</text>
							<text class="checklist-item-cell">{{ item.cell_id || `${item.sector_id}_${item.band}` }}</text>
						</view>
						<button class="bind-quick-btn" @click="quickBindDevice(item)">
							{{ $t('inspection.quickBind') }}
						</button>
					</view>
				</scroll-view>
				
					<view class="modal-actions">
						<button class="cancel-btn" @click="showPreSubmitCheckModal = false">
							{{ $t('inspection.backToCheck') }}
						</button>
						<button class="force-submit-btn" @click="forceSubmitWithWarning">
							{{ $t('inspection.ignoreAndSubmit') }}
						</button>
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
				<text class="preview-loading-percent">{{ previewProgress.percent }}%</text>
			</view>
		</view>
	</template>

	<script setup>
		import { ref, computed, onMounted, watch, getCurrentInstance, onUnmounted } from 'vue'
		import { onLoad, onShow, onHide } from '@dcloudio/uni-app'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	import { useWorkOrderStore } from '@/stores/workorder'
	import { useLanguageStore } from '@/stores/language'
		import { buildImageUrl, buildApiUrl, getAuthHeaders, createRequestConfig, API_ENDPOINTS } from '@/config/api.js'
	import { createPhotoCacheContext, ensurePhotoCached, saveLocalPhotoToCache, removeCachedPhoto } from '@/utils/photoCache.js'
	import { parseBarcode, formatMacAddress, isValidParseResult } from '@/utils/barcode-parser.js'
	import { validateField, validateAllFields } from '@/utils/field-validator.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import { 
		processFieldDependencies, 
		initializeFieldDependencies,
		shouldShowField 
	} from '@/utils/field-dependency.js'
	
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	const workOrderStore = useWorkOrderStore()
	const languageStore = useLanguageStore()
	
	// 获取翻译函数
	const { $t } = getCurrentInstance().appContext.config.globalProperties

		const t = (key, params = {}) => {
			const _ = languageStore.currentLocale
			return $t(key, params)
		}

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

		const hasChinese = (value) => /[\u4e00-\u9fff]/.test(String(value || ''))

		const normalizeUnit = (unit) => {
			const raw = String(unit || '').trim()
			if (!raw) return ''
			if (raw === '度') return '°'
			if (raw === '米') return 'm'
			return raw
		}

		const getKnownFieldMapping = (rawLabel) => {
			const label = String(rawLabel || '').trim()
			const map = {
				'铁塔编号': { labelKey: 'inspection.fields.towerId', fieldId: 'tower_id' },
				'纬度': { labelKey: 'site.latitude', fieldId: 'latitude' },
				'经度': { labelKey: 'site.longitude', fieldId: 'longitude' },
				'天线型号': { labelKey: 'inspection.fields.antennaModel', fieldId: 'antenna_model' },
				'安装高度': { labelKey: 'inspection.fields.installHeight', fieldId: 'install_height' },
				'下倾角': { labelKey: 'site.downtilt', fieldId: 'downtilt' },
				'方位角': { labelKey: 'site.azimuth', fieldId: 'azimuth' },
				'天线挂高': { labelKey: 'inspection.fields.antennaHeight', fieldId: 'antenna_height' },
				'驻波比': { labelKey: 'inspection.fields.vswr', fieldId: 'vswr' },
				'机柜温度': { labelKey: 'inspection.fields.cabinetTemperature', fieldId: 'cabinet_temperature' },
				'湿度': { labelKey: 'inspection.fields.humidity', fieldId: 'humidity' },
				'空开容量': { labelKey: 'inspection.fields.airBreakerCapacity', fieldId: 'air_breaker_capacity' },
				'整流器容量': { labelKey: 'inspection.fields.rectifierCapacity', fieldId: 'rectifier_capacity' },
				'检查结果': { labelKey: 'inspection.checkResult', fieldId: 'check_result' }
			}
			return map[label] || null
		}

		const translateFieldLabel = (rawLabel) => {
			const label = String(rawLabel || '').trim()
			const mapping = getKnownFieldMapping(label)
			if (mapping) return t(mapping.labelKey)
			return label
		}

		const buildPlaceholder = (labelText) => {
			const label = String(labelText || '').trim()
			return label ? t('common.pleaseEnterField', { field: label }) : t('common.pleaseEnter')
		}

		const getDisplayItemName = (name) => {
			const raw = String(name || '').trim()
			if (!raw) return ''

		const sectorLabel = t('inspection.sector')
		const deviceLabel = t('inspection.device')
		const cellLabel = t('inspection.cell')

		return raw
			.replace(/-\s*扇区\s*/g, `- ${sectorLabel} `)
			.replace(/-\s*设备\s*/g, `- ${deviceLabel} `)
			.replace(/-\s*小区\s*/g, `- ${cellLabel} `)
			.trim()
	}
		
	// 页面参数
	const inspectionId = ref('')
	
	// 响应式数据
		const inspectionData = ref(null)
		const checkItems = ref([])
		const categories = ref([])
		const currentCategory = ref('all')
		const workOrderData = ref(null)
		const currentItem = ref(null)
		const saving = ref(false)
		const submitting = ref(false)
		const savingItem = ref(false)
		const omcEverSummary = ref(null)
		const omcEverLoading = ref(false)

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

	const issueCount = computed(() => checkItems.value.filter(isIssueItem).length)
	
	// 提交前核查弹窗控制
	const showPreSubmitCheckModal = ref(false)
	const preSubmitUnboundList = ref([])
	
	// Canvas尺寸（用于水印处理）
	const canvasWidth = ref(400)
	const canvasHeight = ref(300)
	
	// 计算属性
	const filteredCheckItems = computed(() => {
		if (currentCategory.value === 'all') {
			return checkItems.value
		}
		if (currentCategory.value === 'issue') {
			return checkItems.value.filter(isIssueItem)
		}
		return checkItems.value.filter(item => item.category_id === currentCategory.value)
	})
	
	const groupedCheckItems = computed(() => {
		const groups = {}
		
		filteredCheckItems.value.forEach(item => {
			const categoryId = item.category_id
			if (!groups[categoryId]) {
				const baseName = item.category_name || categoryId
				groups[categoryId] = {
					categoryId,
					categoryName: getI18nText(baseName, item.category_name_i18n),
					items: []
				}
			}
			groups[categoryId].items.push(item)
		})
		
		return Object.values(groups)
	})
	
		const canSubmit = computed(() => {
			const requiredItems = checkItems.value.filter(item => item.required_type)
			const completedItems = checkItems.value.filter(item => item.status === 'completed')
			return requiredItems.length > 0 && completedItems.length === requiredItems.length
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
		
		// 生命周期
		onLoad((options) => {
			console.log('Checklist页面加载，参数:', options)
			if (options.inspectionId) {
			inspectionId.value = options.inspectionId
			console.log('开始加载检查数据，inspectionId:', options.inspectionId)
			loadInspectionData()
		} else {
			console.log('⚠️ 缺少inspectionId参数')
		}
	})

	const pickDefaultCategory = () => {
		if (inspectionData.value?.status === 'rejected' && issueCount.value > 0) {
			currentCategory.value = 'issue'
		}
	}
	
	// 方法
	const loadInspectionData = async () => {
		console.log('🚀 loadInspectionData函数开始执行')
		try {
			// 加载检查数据
			const inspectionResult = await inspectionStore.getInspectionDetail(inspectionId.value)
			if (inspectionResult.success) {
				inspectionData.value = inspectionResult.data
				
					// 关联工单：用于获取站点名称 & 判断 opening_inspection
					if (inspectionData.value.work_order_id) {
						const workOrderResult = await workOrderStore.getWorkOrder(inspectionData.value.work_order_id)
						if (workOrderResult.success) {
							workOrderData.value = workOrderResult.data
							if (!inspectionData.value.site_name && workOrderResult.data?.site_name) {
								inspectionData.value.site_name = workOrderResult.data.site_name
							}
						}
					}

					// 备用方案：通过site_id获取站点名称
					if (!inspectionData.value.site_name && inspectionData.value.site_id) {
						try {
							const siteResponse = await uni.request({
								url: buildApiUrl(`/api/sites/${inspectionData.value.site_id}`),
								...createRequestConfig({
									method: 'GET',
									headers: getAuthHeaders(userStore.token)
								})
							})
							if (siteResponse.statusCode === 200) {
								inspectionData.value.site_name = siteResponse.data?.name || inspectionData.value.site_name
							}
						} catch (siteErr) {
							console.warn('通过site_id获取站点信息失败:', siteErr)
						}
					}
				
				// 调试检查数据结构
				console.log('检查数据调试信息:', {
					完整检查数据: inspectionData.value,
					所有字段名: Object.keys(inspectionData.value || {}),
					site_name字段: inspectionData.value?.site_name,
					site_id字段: inspectionData.value?.site_id,
					站点相关字段: Object.keys(inspectionData.value || {}).filter(key => 
						key.toLowerCase().includes('site') || key.toLowerCase().includes('站点')
					)
				})
			}
			
				// 加载检查项
				const itemsResult = await inspectionStore.getInspectionItems(inspectionId.value)
				if (itemsResult.success) {
					checkItems.value = itemsResult.data.map(item => ({
						...item,
						photos: item.photos || [],
						dataFields: generateDataFieldsFromBackend(item),
						notes: item.notes || ''
					}))
					
					// 提取分类信息
					extractCategories()
				}

					pickDefaultCategory()

					// 开站工单：加载站点设备 ever 状态（只读后端缓存）
					await loadOmcEverSummary()
					
				} catch (error) {
					console.error('加载检查数据失败:', error)
					uni.showToast({
					title: $t('messages.dataLoadFailed'),
				icon: 'error'
			})
		}
	}
	
	const generateDataFieldsFromBackend = (item) => {
		// 优先使用后端返回的fields配置
		if (item.fields && Array.isArray(item.fields) && item.fields.length > 0) {
			console.log(`使用后端返回的fields配置: ${item.item_name}`, item.fields)
			
			// 将后端fields格式转换为前端dataFields格式
				const fields = item.fields.map(field => {
					const rawLabel = String(getI18nText(field.label || '', field.label_i18n) || '').trim()
					const mapping = getKnownFieldMapping(rawLabel)
					const label = mapping ? t(mapping.labelKey) : rawLabel

					const rawPlaceholder = String(getI18nText(field.placeholder || '', field.placeholder_i18n) || '').trim()
					const placeholder = rawPlaceholder
						? (normalizeLocale(languageStore.currentLocale) === 'zh' || !hasChinese(rawPlaceholder) ? rawPlaceholder : buildPlaceholder(label))
						: buildPlaceholder(label)

					const dataField = {
						label,
						type: field.type || 'text',
						unit: normalizeUnit(field.unit || ''),
						placeholder,
						value: '',
						field_id: field.field_id ?? mapping?.fieldId,
						allow_photo: field.allow_photo === true,
						photo_required: field.photo_required === true
					}

					if (!field.field_id && mapping) dataField.legacyLabel = rawLabel
				
				// 处理约束条件
				if (field.constraints) {
					if (field.constraints.min !== undefined) {
						dataField.min = field.constraints.min
					}
					if (field.constraints.max !== undefined) {
						dataField.max = field.constraints.max
					}
					if (field.constraints.min_length !== undefined) {
						dataField.min_length = field.constraints.min_length
					}
					if (field.constraints.max_length !== undefined) {
						dataField.max_length = field.constraints.max_length
					}
					if (field.constraints.pattern) {
						dataField.pattern = field.constraints.pattern
					}
				}
				
				// 处理帮助文本
				const helpText = String(getI18nText(field.help_text || '', field.help_text_i18n) || '').trim()
				if (helpText) dataField.help_text = helpText
				
				// 处理依赖关系
				if (field.dependencies) {
					dataField.dependencies = field.dependencies
				}
				
				// 处理选项（下拉框等）
				if (field.options && Array.isArray(field.options)) {
					dataField.options = field.options.map(opt => {
						if (!opt || typeof opt !== 'object') return opt
						return {
							...opt,
							label: getI18nText(opt.label || '', opt.label_i18n)
						}
					})
				}
				
				// 处理必填项
				if (field.required !== undefined) {
					dataField.required = field.required
				}
				
					return dataField
				})
			
				// 从已有数据中恢复值
				if (item.data_value && item.data_value.length > 0) {
					item.data_value.forEach(dataItem => {
						// 优先按 field_id 匹配（后端会把 field_name 规范化为 field_id）
						const field = fields.find(f =>
							f.field_id !== undefined &&
							f.field_id !== null &&
							String(f.field_id) === String(dataItem.field_name)
						) || fields.find(f => f.legacyLabel && f.legacyLabel === dataItem.field_name) || fields.find(f => f.label === dataItem.field_name)
						if (field) {
							field.value = dataItem.value
						}
					})
				}
			
			return fields
		}
		
		// 回退到硬编码映射（兼容旧数据）
		return generateDataFieldsFallback(item)
	}
	
		const generateDataFieldsFallback = (item) => {
			// 根据检查项类型生成数据字段
			const fields = []

			const makeField = (legacyLabel, { type = 'text', unit = '', min, max } = {}) => {
				const mapping = getKnownFieldMapping(legacyLabel)
				const label = mapping ? t(mapping.labelKey) : String(legacyLabel || '').trim()

				const field = {
					label,
					type,
					unit,
					placeholder: buildPlaceholder(label),
					value: '',
					field_id: mapping?.fieldId,
					allow_photo: false,
					photo_required: false,
					legacyLabel: String(legacyLabel || '').trim()
				}
				if (min !== undefined) field.min = min
				if (max !== undefined) field.max = max
				return field
			}
			
			switch (item.item_id) {
				// 基本信息检查
				case 'tower_id':
					fields.push(makeField('铁塔编号', { type: 'text' }))
					break
				case 'site_coordinates':
					fields.push(
						makeField('纬度', { type: 'number', unit: '°' }),
						makeField('经度', { type: 'number', unit: '°' })
					)
					break
				
				// 天线相关检查
				case 'antenna_installation':
					fields.push(
						makeField('天线型号', { type: 'text' }),
						makeField('安装高度', { type: 'number', unit: 'm' })
					)
					break
				case 'antenna_downtilt':
					fields.push(makeField('下倾角', { type: 'number', unit: '°', min: 0, max: 20 }))
					break
				case 'azimuth_check':
					fields.push(makeField('方位角', { type: 'number', unit: '°', min: 0, max: 360 }))
					break
				case 'tower_height_check':
					fields.push(makeField('天线挂高', { type: 'number', unit: 'm', min: 0, max: 100 }))
					break
				case 'vswr_check':
					fields.push(makeField('驻波比', { type: 'number', min: 1.0, max: 2.0 }))
					break
				
				// 设备检查
				case 'cabinet_environment':
					fields.push(
						makeField('机柜温度', { type: 'number', unit: '℃' }),
						makeField('湿度', { type: 'number', unit: '%' })
					)
					break
				case 'air_breaker':
					fields.push(makeField('空开容量', { type: 'text', unit: 'A' }))
					break
				case 'rectifier_capacity':
					fields.push(makeField('整流器容量', { type: 'text', unit: 'A' }))
					break
				
				// 通用数据字段 - 对于未明确定义的检查项，如果需要数据输入，提供通用字段
				default:
					if (item.required_type === 'data' || item.required_type === 'both') {
						fields.push(makeField('检查结果', { type: 'text' }))
					}
					break
			}
			
			// 从已有数据中恢复值
			if (item.data_value && item.data_value.length > 0) {
				item.data_value.forEach(dataItem => {
					const field =
						fields.find(f => f.field_id && String(f.field_id) === String(dataItem.field_name)) ||
						fields.find(f => f.legacyLabel && f.legacyLabel === dataItem.field_name) ||
						fields.find(f => f.label === dataItem.field_name)
					if (field) {
						field.value = dataItem.value
					}
				})
			}
		
		return fields
	}
	
	const extractCategories = () => {
		const categoryMap = new Map()
		
		checkItems.value.forEach(item => {
			if (!categoryMap.has(item.category_id)) {
				const baseName = item.category_name || item.category_id
				categoryMap.set(item.category_id, {
					id: item.category_id,
					name: getI18nText(baseName, item.category_name_i18n)
				})
			}
		})

		onShow(() => {
			startOmcEverAutoRefresh()
		})

		onHide(() => {
			stopOmcEverAutoRefresh()
		})

		onUnmounted(() => {
			stopOmcEverAutoRefresh()
		})
		
		categories.value = Array.from(categoryMap.values())
	}

	watch(
		() => languageStore.currentLocale,
		() => {
			// 语言切换时，重建动态字段展示文案（label/placeholder/help_text/options）
			checkItems.value = checkItems.value.map(item => ({
				...item,
				dataFields: generateDataFieldsFromBackend(item)
			}))
			if (currentItem.value?.id) {
				const matched = checkItems.value.find(it => it.id === currentItem.value.id)
				if (matched) currentItem.value = matched
			}
			extractCategories()
		}
	)
	
	const switchCategory = (categoryId) => {
		currentCategory.value = categoryId
	}
	
	const getCategoryCount = (categoryId) => {
		return checkItems.value.filter(item => item.category_id === categoryId).length
	}
	
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
	
	// 小区级：cell_id === 扇区_频段_EARFCN（不需要绑定）
	const isCellEarfcnLevelItem = (item) => {
		if (!item?.sector_id || !item?.band) return false
		const key = getDeviceKey(item)
		if (!key || !item?.cell_id) return false
		return String(item.cell_id).startsWith(`${key}_`)
	}
	
	// 检查设备是否已绑定
	const isDeviceBound = (item) => {
		if (!isDeviceLevelItem(item)) return true
		
		const deviceItems = checkItems.value.filter(checkItem => 
			checkItem.sector_id === item.sector_id && 
			checkItem.band === item.band
		)
		
		return deviceItems.some(deviceItem => deviceItem.equipment_sn)
	}
	
	// 获取设备绑定的序列号
	const getDeviceEquipmentSn = (item) => {
		if (!isDeviceLevelItem(item)) return null
		
		const deviceItems = checkItems.value.filter(checkItem => 
			checkItem.sector_id === item.sector_id && 
			checkItem.band === item.band
		)
		
		const boundItem = deviceItems.find(deviceItem => deviceItem.equipment_sn)
		return boundItem?.equipment_sn || null
	}

	const openCheckItem = async (item) => {
		// 仅设备级检查项要求绑定设备
		if (isDeviceLevelItem(item) && !isDeviceBound(item)) {
			// 显示绑定设备提示
			uni.showModal({
				title: $t('inspection.needBindTitle'),
				content: $t('inspection.needBindContent'),
				confirmText: $t('inspection.scanBindButton'),
				cancelText: $t('inspection.laterBindButton'),
				success: (res) => {
					if (res.confirm) {
						// 直接调用扫码绑定
						scanEquipmentForBinding(item)
					} else {
						// 仍然打开检查项，但用户需要手动绑定
						currentItem.value = { ...item }
						// 确保显示绑定状态
						currentItem.value.equipment_sn = getDeviceEquipmentSn(item)
						primeCurrentItemPhotoCache()
					}
				}
			})
		} else {
			// 正常打开检查项
			currentItem.value = { ...item }
			// 如果是设备级检查项，确保显示正确的绑定状态
			if (isDeviceLevelItem(item)) {
				currentItem.value.equipment_sn = getDeviceEquipmentSn(item)
			}
			
			// 初始化字段依赖（保存原始状态）
			if (currentItem.value.dataFields) {
				currentItem.value.dataFields = initializeFieldDependencies(currentItem.value.dataFields)
			}
			
			// 尝试恢复自动保存的数据
			restoreAutoSavedData(currentItem.value)
			
			// 处理初始依赖关系
			processFieldDependenciesForCurrentItem()

			primeCurrentItemPhotoCache()
		}
	}
	
		const closeItemModal = () => {
			currentItem.value = null
		}

		// 字段拍照模式：仅 required_type=both 且至少存在一个 allow_photo=true 的字段时启用
		const isFieldPhotoMode = () => {
			if (!currentItem.value) return false
			if (currentItem.value.required_type !== 'both') return false
			const fields = currentItem.value.dataFields || []
			return fields.some(f => f?.allow_photo === true)
		}

		const getAllowedPhotoFieldIdSet = () => {
			const set = new Set()
			if (!currentItem.value) return set
			const fields = currentItem.value.dataFields || []
			fields.forEach(f => {
				if (f?.allow_photo !== true) return
				const fid = f?.field_id
				if (fid === undefined || fid === null || String(fid).trim() === '') return
				set.add(String(fid))
			})
			return set
		}
		
		const getPhotosForField = (dataField) => {
			if (!currentItem.value || !dataField) return []
			const fid = dataField.field_id
		if (fid === undefined || fid === null || String(fid).trim() === '') return []
		const photos = currentItem.value.photos || []
		return photos.filter(p => p && p.field_id !== undefined && p.field_id !== null && String(p.field_id) === String(fid))
	}

	const getUnlinkedPhotos = () => {
		if (!currentItem.value) return []
		const photos = currentItem.value.photos || []
		const known = new Set(
			(currentItem.value.dataFields || [])
				.map(f => f?.field_id)
				.filter(v => v !== undefined && v !== null && String(v).trim() !== '')
				.map(v => String(v))
		)
		return photos.filter(p => {
			const fid = p?.field_id
			if (fid === undefined || fid === null || String(fid).trim() === '') return true
			return !known.has(String(fid))
		})
		}

		const takePhotoForField = async (dataField) => {
			if (dataField?.allow_photo !== true) {
				uni.showToast({
					title: '该字段禁止拍照',
					icon: 'none',
					duration: 2500
				})
				return
			}

			const fid = dataField?.field_id
			if (fid === undefined || fid === null || String(fid).trim() === '') {
				uni.showToast({
					title: '该字段缺少字段ID，无法关联照片',
				icon: 'none',
				duration: 2500
			})
			return
		}

		await takePhotoInternal({
			fieldId: String(fid),
			fieldLabel: dataField?.label
		})
	}

	const takePhoto = async () => {
		await takePhotoInternal()
	}

	const takePhotoInternal = async ({ fieldId = null, fieldLabel = '' } = {}) => {
		// 根据移动端配置决定是否允许本地上传
		const { getAllowLocalPhotoUpload, getLocalUploadWatermarkWithGeo } = await import('@/utils/locationStrategy.js')
		const allowAlbum = getAllowLocalPhotoUpload()
		const localUploadWatermarkWithGeo = getLocalUploadWatermarkWithGeo()

		const itemList = allowAlbum
			? [$t('common.takePhoto'), $t('common.selectFromAlbum')]
			: [$t('common.takePhoto')]

		// 显示操作选择弹窗
		uni.showActionSheet({
			itemList,
			success: async function (res) {
				const isCamera = !allowAlbum || res.tapIndex === 0
				const sourceType = isCamera ? ['camera'] : ['album']
				
				try {
					// 如果是拍照，先获取GPS坐标
					let gpsData = { latitude: 0, longitude: 0, accuracy: 0, address: '' }
					
					if (isCamera) {
						uni.showLoading({ title: $t('messages.gettingLocation') })
						
				try {
					gpsData = await getHighAccuracyLocation()
					// 验证GPS坐标的有效性
					if (gpsData.latitude === 0 && gpsData.longitude === 0) {
						throw new Error($t('messages.gpsNotObtained'))
					}
				} catch (gpsError) {
					await handleGpsFailure(gpsError)
					return // 直接返回，不继续拍照流程
				} finally {
					uni.hideLoading()
				}
					}
					
					// 选择图片
					uni.chooseImage({
						count: 1,
						sizeType: ['original'],
						sourceType: sourceType,
						success: async (chooseRes) => {
								try {
									let finalImagePath = chooseRes.tempFilePaths[0]
									let usedWatermark = false
									let gpsUsed = { ...gpsData }
									
									// 拍照/相册均添加GPS水印，确保上传后端校验通过
									console.log(
										isCamera
											? '拍照模式，添加GPS水印'
											: (localUploadWatermarkWithGeo ? '相册模式，添加GPS水印' : '相册模式，添加本地上传水印（不带经纬度/地址）')
									)
									uni.showLoading({
										title: (!isCamera && !localUploadWatermarkWithGeo)
											? $t('messages.addingWatermark')
											: $t('messages.addingGPSWatermark'),
										mask: true
									})
									try {
										// 相册模式需要现取一次定位
										if (!isCamera) {
											if (localUploadWatermarkWithGeo) {
												try {
													gpsUsed = await getHighAccuracyLocation()
												} catch (gpsErr) {
													await handleGpsFailure(gpsErr)
													return
												}
											} else {
												// 本地/相册上传且配置为不携带经纬度/地址：不调用定位和逆地理
												gpsUsed = { latitude: 0, longitude: 0, accuracy: 0, address: '' }
											}
										}
										const watermarkTool = getWatermarkTool()
										const wmFieldLabel = String(fieldLabel || '').trim()
										const wmItemName = wmFieldLabel
											? `${currentItem.value.item_name || $t('inspection.checkItem')} - ${wmFieldLabel}`
											: (currentItem.value.item_name || $t('inspection.checkItem'))
										finalImagePath = await watermarkTool.addWatermark(
											finalImagePath,
											gpsUsed.latitude,
											gpsUsed.longitude,
											gpsUsed.address,
											userStore.userInfo?.username || $t('messages.unknownInspector'),
											wmItemName,
											gpsUsed,
											(!isCamera && !localUploadWatermarkWithGeo)
												? { skipLocation: true, localUploadNote: $t('messages.localUploadPhotoWatermark') }
												: {}
										)
										usedWatermark = true
										console.log('水印添加成功，最终图片路径:', finalImagePath)
									} catch (watermarkError) {
										console.warn('水印添加失败，使用原图:', watermarkError)
										// 相册模式若无法添加水印，则不允许继续，避免后端400
										if (!isCamera) {
											uni.hideLoading()
											uni.showToast({
												title: (!localUploadWatermarkWithGeo)
													? $t('messages.photoProcessFailed')
													: $t('messages.gpsNotObtained'),
												icon: 'error'
											})
											return
										}
									} finally {
										uni.hideLoading()
									}
									
									// 创建照片对象
									const photo = {
										field_id: (fieldId !== undefined && fieldId !== null && String(fieldId).trim() !== '') ? String(fieldId) : undefined,
										file_path: finalImagePath,
										taken_at: new Date().toISOString(),
										latitude: gpsUsed.latitude,
										longitude: gpsUsed.longitude,
										gps_accuracy: gpsUsed.accuracy,
										address: gpsUsed.address,
										has_watermark: usedWatermark,
										local_upload_without_geo: (!isCamera && !localUploadWatermarkWithGeo),
										watermark_data: usedWatermark ? {
											timestamp: new Date().toISOString(),
											coordinates: (!isCamera && !localUploadWatermarkWithGeo) ? '' : `${gpsUsed.latitude},${gpsUsed.longitude}`,
											accuracy: (!isCamera && !localUploadWatermarkWithGeo) ? undefined : gpsUsed.accuracy,
										inspector: userStore.userInfo?.username || $t('messages.unknownInspector'),
										item_name: currentItem.value.item_name || $t('inspection.checkItem')
										} : null
									}
								
								if (!currentItem.value.photos) {
									currentItem.value.photos = []
								}
								currentItem.value.photos.push(photo)
								
									uni.showToast({
										title: $t('inspection.photoAdded'),
										icon: 'success'
									})
								
							} catch (processError) {
								console.error('照片处理失败:', processError)
									uni.showToast({
										title: $t('messages.photoProcessFailed'),
										icon: 'error'
									})
							}
						},
						fail: (chooseError) => {
							console.error('选择照片失败:', chooseError)
								uni.showToast({
									title: $t('messages.photoChooseFailed'),
									icon: 'error'
								})
						}
					})
					
				} catch (error) {
					console.error('拍照流程失败:', error)
						uni.showToast({
							title: $t('messages.operationFailed'),
							icon: 'error'
						})
				}
			}
		})
	}

	const handleGpsFailure = async (error) => {
		console.warn('GPS获取失败:', error)
		const title = $t('inspection.gpsFetchFailedTitle')
		const content = $t('inspection.gpsFetchFailedContent')

		const permissionReady = await ensureLocationAuthorization()

		if (!permissionReady) {
			await showLocationPermissionModal(title, content, true)
			return
		}

		await showLocationPermissionModal(title, content, false)
	}

	const ensureLocationAuthorization = async () => {
		const granted = await isLocationPermissionGranted()
		if (granted) {
			return true
		}

		const authorized = await requestLocationPermission()
		if (authorized) {
			uni.showToast({
				title: $t('messages.locationPermissionGranted'),
				icon: 'none',
				duration: 2000
			})
			return true
		}

		return false
	}

	const isLocationPermissionGranted = () => {
		return new Promise((resolve) => {
			if (typeof uni.getSetting !== 'function') {
				resolve(false)
				return
			}

			uni.getSetting({
				success: (res) => {
					const authSetting = res && res.authSetting ? res.authSetting : {}
					const foreground = authSetting['scope.userLocation'] === true
					const background = authSetting['scope.userLocationBackground'] === true
					resolve(foreground || background)
				},
				fail: () => resolve(false)
			})
		})
	}

	const requestLocationPermission = () => {
		return new Promise((resolve) => {
			if (typeof uni.authorize !== 'function') {
				resolve(false)
				return
			}

			uni.authorize({
				scope: 'scope.userLocation',
				success: () => resolve(true),
				fail: () => resolve(false)
			})
		})
	}

	const showLocationPermissionModal = (title, content, allowSettings) => {
		return new Promise((resolve) => {
			const modalOptions = {
				title,
				content,
				showCancel: allowSettings,
				confirmText: allowSettings ? $t('common.openSettings') : $t('common.ok'),
				success: (res) => {
					if (allowSettings && res.confirm) {
						openAppLocationSettings()
					}
					resolve()
				},
				fail: () => resolve()
			}

			if (allowSettings) {
				modalOptions.cancelText = $t('common.cancel')
			}

			uni.showModal(modalOptions)
		})
	}

	const openAppLocationSettings = () => {
		let handled = false

		// #ifdef APP-PLUS
		handled = true
		try {
			const systemInfo = uni.getSystemInfoSync()
			const platform = systemInfo && systemInfo.platform ? systemInfo.platform : 'android'

			if (platform === 'ios') {
				const UIApplication = plus.ios.import('UIApplication')
				const application = UIApplication.sharedApplication()
				const NSURL = plus.ios.import('NSURL')
				const settingsURL = NSURL.URLWithString('app-settings:')
				application.openURL(settingsURL)
				plus.ios.deleteObject(settingsURL)
				plus.ios.deleteObject(application)
			} else {
				const mainActivity = plus.android.runtimeMainActivity()
				const Intent = plus.android.importClass('android.content.Intent')
				const Settings = plus.android.importClass('android.provider.Settings')
				const Uri = plus.android.importClass('android.net.Uri')
				const intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
				const uri = Uri.fromParts('package', mainActivity.getPackageName(), null)
				intent.setData(uri)
				mainActivity.startActivity(intent)
			}
		} catch (nativeError) {
			console.error('打开系统定位设置失败:', nativeError)
		}
		// #endif

		if (!handled && typeof uni.openSetting === 'function') {
			uni.openSetting({})
		}
	}

	// 通过定位策略获取高精度定位（支持原生插件 / Baidu 模式）
	const getHighAccuracyLocation = async () => {
		try {
			console.log('使用定位策略封装获取高精度定位...')
			
			const { getLocationWithAddressStrategy } = await import('@/utils/locationStrategy.js')
			const result = await getLocationWithAddressStrategy()
			console.log('定位策略结果:', result)

			if (!result || !result.success || !result.data) {
				throw new Error(result?.message || $t('messages.nativePluginLocationFailed'))
			}

			const data = result.data
			const latitude = Number(data.latitude)
			const longitude = Number(data.longitude)

			if (!isFinite(latitude) || !isFinite(longitude) || (latitude === 0 && longitude === 0)) {
				throw new Error($t('messages.invalidCoordinates'))
			}

			const addressObj = result.address
			let addressString = ''
			if (addressObj && typeof addressObj === 'object') {
				const addressParts = [
					addressObj.country,
					addressObj.province,
					addressObj.city,
					addressObj.district,
					addressObj.street,
					addressObj.streetNum,
					addressObj.streetNumber
				].filter(part => part && String(part).trim())

				if (addressParts.length > 0) {
					addressString = addressParts.join('')
				}
			}

			return {
				latitude,
				longitude,
				accuracy: Number(data.accuracy || 0),
				address: addressString,
				addressInfo: addressObj || null,
				provider: data.provider || 'native-plugin'
			}
		} catch (error) {
			console.error('定位策略获取高精度位置失败:', error)
			throw error
		}
	}
	
	// 逆地理编码函数
	const getAddressFromCoords = (latitude, longitude) => {
		return new Promise((resolve) => {
			// 这里可以调用真实的逆地理编码API
			// 暂时返回格式化的坐标信息作为地址
			const formattedAddress = `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
			resolve(formattedAddress)
		})
	}

	const formatWatermarkTimestamp = (input = new Date()) => {
		const date = input instanceof Date ? input : new Date(input)
		if (!Number.isFinite(date.getTime())) return ''
		const pad2 = (v) => String(v).padStart(2, '0')
		return (
			`${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}` +
			` ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`
		)
	}
	
	// 获取水印工具
		const getWatermarkTool = () => {
			return {
				addWatermark: async (imagePath, latitude, longitude, address, inspector, itemName, gpsExtra = null, watermarkOptions = {}) => {
					try {
						console.log('使用增强GPS地址水印功能')
						const skipLocation = watermarkOptions && watermarkOptions.skipLocation === true
						const localUploadNote = watermarkOptions && watermarkOptions.localUploadNote
					
					// 先获取图片信息
					const imageInfo = await new Promise((resolve, reject) => {
						uni.getImageInfo({
							src: imagePath,
							success: resolve,
							fail: reject
						})
					})
					const originWidth = imageInfo.width
					const originHeight = imageInfo.height
					const originLongEdge = Math.max(originWidth, originHeight)

					// 导入增强水印工具
					const { watermarkTool } = await import('@/utils/watermark.js')
					
					// 准备水印数据，尝试多种站点名称获取方式
					const siteName = inspectionData.value?.site_name || 
									 inspectionData.value?.site?.site_name || 
									 inspectionData.value?.work_order?.site_name ||
									 $t('site.unknownSite')
					
					const watermarkData = {
						inspector: inspector || userStore.userInfo?.username || $t('messages.unknownInspector'),
						checkItem: itemName || currentItem.value?.item_name || $t('inspection.checkItem'),
						siteName: siteName
					}
					
					console.log('水印数据准备:', {
						传入的inspector: inspector,
						用户store状态: userStore.isLoggedIn,
						用户完整信息: userStore.userInfo,
						用户名字段: userStore.userInfo?.username,
						传入的itemName: itemName,
						当前项目名称: currentItem.value?.item_name,
						检查数据完整: inspectionData.value,
						检查数据所有字段: Object.keys(inspectionData.value || {}),
						站点名称尝试1_site_name: inspectionData.value?.site_name,
						站点名称尝试2_site对象: inspectionData.value?.site,
						站点名称尝试3_workorder: inspectionData.value?.work_order,
						最终站点名称: siteName,
						最终水印数据: watermarkData
					})

					// Android canvas 大图偶发渲染不全：优先保持原尺寸（但不超过4K），失败则自动降级尺寸重试
					const candidateEdges = []
					const firstEdge = Math.min(4096, originLongEdge)
					candidateEdges.push(firstEdge)
					if (firstEdge > 2560) candidateEdges.push(2560)
					if (firstEdge > 2048) candidateEdges.push(2048)
					const uniqueEdges = [...new Set(candidateEdges.filter(Boolean))]

					const buildTargetSize = (maxEdge) => {
						const edge = Number(maxEdge || 0)
						const scale = (originLongEdge > edge && edge > 0) ? (edge / originLongEdge) : 1
						return {
							width: Math.max(1, Math.round(originWidth * scale)),
							height: Math.max(1, Math.round(originHeight * scale)),
							maxEdge: edge,
							scale,
						}
					}

					const fixedTimestamp = formatWatermarkTimestamp()
					let lastError = null
					for (const edge of uniqueEdges) {
						const target = buildTargetSize(edge)

						// 更新canvas尺寸
						canvasWidth.value = target.width
						canvasHeight.value = target.height
						console.log('设置Canvas尺寸:', {
							origin: { width: originWidth, height: originHeight },
							target: { width: target.width, height: target.height, maxEdge: target.maxEdge, scale: target.scale }
						})

						// 等待DOM更新
						await new Promise(resolve => setTimeout(resolve, 120))

						try {
							let watermarkedPath = null
							if (skipLocation) {
								// 本地/相册上传且不携带定位信息：不调用定位与逆地理，仅添加标注水印
								watermarkedPath = await watermarkTool.addWatermark(imagePath, {
									...watermarkData,
									localUploadNote: localUploadNote || $t('messages.localUploadPhotoWatermark'),
									timestamp: fixedTimestamp
								}, 'watermarkCanvas', {
									renderWidth: target.width,
									renderHeight: target.height,
									maxEdge: target.maxEdge,
									validateRender: true,
									postDrawDelayMs: 30,
								})
							} else {
								// 使用新的增强水印功能，使用页面中的canvas，并复用已获取的GPS
								watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, watermarkData, {
									showAddressDetails: true,
									showPOI: false,
									canvasId: 'watermarkCanvas',  // 使用页面中已有的canvas
									gpsOverride: gpsExtra,
									renderWidth: target.width,
									renderHeight: target.height,
									maxEdge: target.maxEdge,
									validateRender: true,
									postDrawDelayMs: 30,
								})
							}

							console.log('增强水印添加完成:', watermarkedPath)
							return watermarkedPath
						} catch (e) {
							lastError = e
							console.warn('水印生成失败，尝试降级尺寸:', {
								maxEdge: target.maxEdge,
								target: { width: target.width, height: target.height },
								error: e?.message || e
							})
						}
					}

					throw lastError || new Error('水印添加失败')
					
				} catch (error) {
					console.error('增强水印失败，使用原方案:', error)
					const skipLocation = watermarkOptions && watermarkOptions.skipLocation === true
					const localUploadNote = watermarkOptions && watermarkOptions.localUploadNote
					
					// 兜底方案：使用原有的canvas水印方法
					return new Promise((resolve, reject) => {
						// 创建canvas进行水印处理
						const ctx = uni.createCanvasContext('watermarkCanvas')
						
						// 加载图片
						uni.getImageInfo({
							src: imagePath,
							success: (imageInfo) => {
								const imgWidth = imageInfo.width
								const imgHeight = imageInfo.height
								const longEdge = Math.max(imgWidth, imgHeight)
								const maxEdge = Math.min(4096, longEdge)
								const scale = (longEdge > maxEdge && maxEdge > 0) ? (maxEdge / longEdge) : 1
								const outW = Math.max(1, Math.round(imgWidth * scale))
								const outH = Math.max(1, Math.round(imgHeight * scale))
								
								// 更新canvas尺寸
								canvasWidth.value = outW
								canvasHeight.value = outH
								
								console.log('兜底方案更新Canvas尺寸:', { origin: { imgWidth, imgHeight }, target: { outW, outH, scale } })
								
								// 等待DOM更新后再绘制
								setTimeout(() => {
									// 重新创建canvas上下文
									const ctx = uni.createCanvasContext('watermarkCanvas')
									
									// 设置canvas尺寸并绘制图片
									ctx.drawImage(imagePath, 0, 0, outW, outH)
								
								// 添加水印文字
								const ts = formatWatermarkTimestamp()
								const watermarkText = skipLocation
									? [
										`🕐 ${ts}`,
										(localUploadNote || $t('messages.localUploadPhotoWatermark')),
										`👤 ${inspector}`,
										`📋 ${itemName}`
									]
									: [
										`🕐 ${ts}`,
										`📍 ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
										...(address ? [`🏠 ${address}`] : []),
										`👤 ${inspector}`,
										`📋 ${itemName}`
									]
								
									// 设置水印样式
									ctx.setFillStyle('rgba(0, 0, 0, 0.7)')
									const lineHeight = 25
									const boxPaddingTop = 18
									const boxPaddingBottom = 18
									const boxHeight = watermarkText.length * lineHeight + boxPaddingTop + boxPaddingBottom
									const boxY = Math.max(10, outH - boxHeight - 10)
									ctx.fillRect(10, boxY, outW - 20, boxHeight)
									
									ctx.setFillStyle('#ffffff')
									ctx.setFontSize(18)
									
									// 绘制水印文字
									watermarkText.forEach((text, index) => {
										ctx.fillText(text, 20, boxY + boxPaddingTop + (index + 1) * lineHeight - 8)
									})
								
									// 导出处理后的图片
									ctx.draw(false, () => {
										uni.canvasToTempFilePath({
											canvasId: 'watermarkCanvas',
											destWidth: outW,
											destHeight: outH,
											success: (canvasRes) => {
												console.log('兜底水印处理成功:', canvasRes.tempFilePath)
												resolve(canvasRes.tempFilePath)
											},
											fail: (canvasError) => {
												console.error('Canvas导出失败:', canvasError)
												reject(canvasError)
											}
										})
									})
								}, 100) // setTimeout结束
							},
							fail: (error) => {
								// 如果水印处理失败，返回原图
								console.error('兜底水印处理失败:', error)
								resolve(imagePath)
							}
						})
					})
				}
			}
		}
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

		// 仅缓存服务器图片（有 id 且为 http URL）
		const targets = photos.filter(p => p?.id && isRemotePhoto(p))
		if (targets.length === 0) return

		// 控制并发，避免同时拉太多
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
		// 本地临时图片：直接展示
		if (!photo.id || !isRemotePhoto(photo)) {
			return getPhotoRemoteUrl(photo)
		}
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
		// 本地缓存被系统清理/文件损坏：自动重新从服务器拉取并缓存
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

	const onPhotoTap = async (photo) => {
		const photos = currentItem.value?.photos || []
		if (!Array.isArray(photos) || photos.length === 0) return

		const currentIndex = photos.findIndex(p =>
			(photo?.id && p?.id && String(p.id) === String(photo.id)) ||
			(photo?.file_path && p?.file_path && String(p.file_path) === String(photo.file_path))
		)

		// 若该图处于错误态，触发重试但不阻塞预览
		const status = getPhotoDisplayStatus(photo)
		if (status === 'error') {
			cachePhotoIfNeeded(photo).catch(() => {})
		}

		// 不再等待“全部缓存完成”才允许预览：已缓存的用本地路径，其它用网络 URL
		const urls = buildPreviewUrls(photos)
		openPreview(urls, currentIndex >= 0 ? currentIndex : 0)

		// 继续后台缓存，不阻塞预览
		primeCurrentItemPhotoCache().catch(() => {})
	}
	
	const deletePhoto = async (photoOrIndex) => {
		if (!currentItem.value || !currentItem.value.photos || currentItem.value.photos.length === 0) return

		const index = (typeof photoOrIndex === 'number')
			? photoOrIndex
			: currentItem.value.photos.findIndex(p =>
				(photoOrIndex?.id && p?.id && p.id === photoOrIndex.id) || p === photoOrIndex
			)
		if (index < 0) return

		const photo = currentItem.value.photos[index]
		
		uni.showModal({
			title: $t('inspection.confirmDeleteTitle'),
			content: $t('inspection.confirmDeleteContent'),
			success: async (res) => {
				if (res.confirm) {
					// 如果是已上传的照片（有photo.id），需要调用后端API删除
					if (photo && photo.id) {
						uni.showLoading({ title: $t('messages.deletingPhoto') })
						
						try {
							const result = await inspectionStore.deleteInspectionPhoto(photo.id)
							
							if (result.success) {
								// 从数组中移除
								currentItem.value.photos.splice(index, 1)
								// 同步清理本地缓存
								try {
									await removeCachedPhoto({ photoId: photo.id, ctx: photoCacheCtx.value })
								} catch (e) {
									// ignore
								}
								uni.showToast({
									title: $t('inspection.photoDeleteSuccess'),
									icon: 'success'
								})
							} else {
								throw new Error(result.error || $t('messages.deleteFailed'))
							}
						} catch (error) {
							console.error('删除照片失败:', error)
							uni.showToast({
								title: $t('messages.deleteFailedWithReason', { reason: error.message }),
								icon: 'error',
								duration: 3000
							})
						} finally {
							uni.hideLoading()
						}
					} else {
						// 未上传的临时照片，直接从数组移除
						currentItem.value.photos.splice(index, 1)
						uni.showToast({
							title: $t('inspection.photoDeleteSuccess'),
							icon: 'success'
						})
					}
				}
			}
		})
	}
	
	/**
	 * 字段值变更处理（实时验证 + 依赖处理）
	 * @param {Object} field - 可选，指定验证的字段（用于单字段实时验证）
	 */
	const onDataChange = (field = null) => {
		// 如果指定了字段，进行单字段实时验证（内部会调用updateValidationResult）
		if (field) {
			validateSingleField(field)
		} else {
			// 验证所有字段
			validateCurrentItem()
		}
		
		// 处理字段依赖关系（字段值变化可能影响其他字段）
		processFieldDependenciesForCurrentItem()
		
		// 自动保存到本地存储（防止数据丢失）
		autoSaveFieldData()
	}
	
	/**
	 * 处理当前检查项的字段依赖关系
	 */
	const processFieldDependenciesForCurrentItem = () => {
		if (!currentItem.value || !currentItem.value.dataFields) return
		
		// 构建字段值映射
		const fieldValues = {}
		currentItem.value.dataFields.forEach(field => {
			fieldValues[field.field_id || field.label] = field.value
		})
		
		// 处理依赖关系，更新字段状态
		currentItem.value.dataFields = processFieldDependencies(
			currentItem.value.dataFields,
			fieldValues
		)
	}
	
	const onNotesChange = () => {
		// 备注变化处理 - 也触发自动保存
		autoSaveFieldData()
	}
	
	/**
	 * 验证单个字段（实时验证）
	 * @param {Object} field - 字段对象
	 */
	const validateSingleField = (field) => {
		if (!field) return
		
		// 使用验证工具进行验证（非严格模式，允许部分填写）
		const result = validateField(field, field.value, false)
		
		// 将验证结果存储在字段对象上
		field.error = result.error
		
		// 如果有错误，也更新到整体验证结果中
		if (!result.valid) {
			console.log(`字段 ${field.label} 验证失败:`, result.error)
		}
		
		// 更新整体验证结果
		updateValidationResult()
	}
	
	/**
	 * 更新整体验证结果（汇总所有字段的错误）
	 */
		const updateValidationResult = () => {
			if (!currentItem.value || !currentItem.value.dataFields) return
		
		// 收集所有字段的错误
		const errors = []
		let hasError = false
		
		currentItem.value.dataFields.forEach(field => {
			if (field.error) {
				errors.push(field.error)
				hasError = true
			}
		})
		
		// 更新整体验证结果
			currentItem.value.validation_result = {
				valid: !hasError,
				errors: errors
			}
		}

		const getValidationErrorList = (validationResult) => {
			if (!validationResult) return []
			const errors = validationResult.errors
			if (!errors) return []
			if (Array.isArray(errors)) return errors.filter(Boolean).map(e => String(e))
			if (errors && typeof errors === 'object') return Object.values(errors).filter(Boolean).map(e => String(e))
			return [String(errors)]
		}

		const formatValidationErrors = (validationResult) => {
			return getValidationErrorList(validationResult).join(', ')
		}

		const isEmptyFieldValue = (value) => {
			if (value === undefined || value === null) return true
			if (typeof value === 'string') return value.trim() === ''
			if (Array.isArray(value)) return value.length === 0
			return false
		}

		// 保存时使用严格校验（required生效），且隐藏字段不参与校验
		const validateCurrentItemStrictVisible = () => {
			if (!currentItem.value || !Array.isArray(currentItem.value.dataFields)) {
				return { valid: true, requiredMissing: false, hasAnyValue: false }
			}

			let requiredMissing = false
			let hasAnyValue = false

			currentItem.value.dataFields.forEach(field => {
				const visible = shouldShowField(field)
				if (!visible) {
					field.error = null
					return
				}

				const empty = isEmptyFieldValue(field.value)
				if (!empty) hasAnyValue = true
				if (field.required === true && empty) requiredMissing = true

				const result = validateField(field, field.value, true)
				field.error = result.error
			})

			updateValidationResult()
			return {
				valid: currentItem.value.validation_result?.valid !== false,
				requiredMissing,
				hasAnyValue
			}
		}
		
		/**
		 * 验证当前检查项的所有字段（提交前验证）
		 */
	const validateCurrentItem = () => {
		if (!currentItem.value || !currentItem.value.dataFields) return
		
		// 准备数据值数组
		const dataValues = currentItem.value.dataFields.map(field => ({
			field_name: field.field_id || field.label,
			value: field.value
		}))
		
		// 使用验证工具进行批量验证（非严格模式）
		const validationResult = validateAllFields(
			currentItem.value.dataFields,
			dataValues,
			false // 非严格模式，允许部分填写
		)
		
		// 更新每个字段的错误信息
		currentItem.value.dataFields.forEach(field => {
			const fieldId = field.field_id || field.label
			field.error = validationResult.errors[fieldId] || null
		})
		
		// 更新整体验证结果
		currentItem.value.validation_result = {
			valid: validationResult.valid,
			errors: Object.values(validationResult.errors)
		}
		
		return validationResult
	}
	
	/**
	 * 自动保存字段数据到本地存储（防止数据丢失）
	 */
	let autoSaveTimer = null
	const autoSaveFieldData = () => {
		// 使用防抖，避免频繁保存
		if (autoSaveTimer) {
			clearTimeout(autoSaveTimer)
		}
		
		autoSaveTimer = setTimeout(() => {
			if (!currentItem.value || !inspectionId.value) return
			
			try {
				const autoSaveKey = `inspection_autosave_${inspectionId.value}_${currentItem.value.id}`
				const saveData = {
					itemId: currentItem.value.id,
					dataFields: currentItem.value.dataFields,
					notes: currentItem.value.notes,
					timestamp: new Date().toISOString()
				}
				
				uni.setStorageSync(autoSaveKey, saveData)
				console.log('✅ 字段数据已自动保存:', autoSaveKey)
			} catch (e) {
				console.error('自动保存失败:', e)
			}
		}, 1000) // 1秒后保存
	}
	
	/**
	 * 恢复自动保存的数据
	 * @param {Object} item - 检查项
	 */
	const restoreAutoSavedData = (item) => {
		try {
			const autoSaveKey = `inspection_autosave_${inspectionId.value}_${item.id}`
			const savedData = uni.getStorageSync(autoSaveKey)
			
			if (savedData && savedData.dataFields) {
				// 恢复字段数据
				item.dataFields = savedData.dataFields
				item.notes = savedData.notes || item.notes
				
				console.log('✅ 已恢复自动保存的数据:', autoSaveKey)
				
				// 提示用户
				uni.showToast({
					title: $t('inspection.autoSavedRestored'),
					icon: 'none',
					duration: 2000
				})
			}
		} catch (e) {
			console.error('恢复自动保存数据失败:', e)
		}
	}
	
	/**
	 * 清除自动保存的数据
	 * @param {String} itemId - 检查项ID
	 */
	const clearAutoSavedData = (itemId) => {
		try {
			const autoSaveKey = `inspection_autosave_${inspectionId.value}_${itemId}`
			uni.removeStorageSync(autoSaveKey)
			console.log('✅ 已清除自动保存数据:', autoSaveKey)
		} catch (e) {
			console.error('清除自动保存数据失败:', e)
		}
	}
		
		const saveCurrentItem = async () => {
		// 设备级检查项必须先绑定设备，防止误保存
		if (isDeviceLevelItem(currentItem.value) && !currentItem.value?.equipment_sn) {
			uni.showModal({
				title: $t('inspection.needBindTitle'),
				content: $t('inspection.needBindContent'),
				confirmText: $t('inspection.scanBindButton'),
				cancelText: $t('inspection.laterBindButton'),
				success: (res) => {
					if (res.confirm) {
						scanEquipmentForBinding()
					}
				}
			})
			return
		}

			try {
				savingItem.value = true
				
				// 准备数据
				const dataValue = (currentItem.value.dataFields || [])
					.map(field => ({
						// 后端期望 field_name=field_id；兼容旧逻辑无field_id时使用label
						field_name: field.field_id || field.label,
						value: field.value,
						unit: field.unit
					}))
					// 仅过滤真正“未填写”的值，保留 0/false
					.filter(item => {
						if (!item.field_name) return false
						const v = item.value
						if (v === undefined || v === null) return false
						if (typeof v === 'string') return v.trim() !== ''
						if (Array.isArray(v)) return v.length > 0
						return true
					})
			
				// 确定状态
				let status = 'pending'
				const reqType = currentItem.value.required_type

				let hasRequiredPhotos = reqType === 'data' ||
					(currentItem.value.photos && currentItem.value.photos.length > 0)
				let hasRequiredData = reqType === 'photo'

				// data/both：完成态严格校验（required生效，隐藏字段不参与）
				const strictCheck = (reqType === 'data' || reqType === 'both')
					? validateCurrentItemStrictVisible()
					: { valid: true, requiredMissing: false, hasAnyValue: false }

				if (reqType === 'data' || reqType === 'both') {
					const visibleFields = (currentItem.value.dataFields || []).filter(f => shouldShowField(f))
					const requiredVisible = visibleFields.filter(f => f?.required === true)
					hasRequiredData = requiredVisible.length > 0
						? !strictCheck.requiredMissing
						: strictCheck.hasAnyValue
				}

				if (reqType === 'both') {
					// both + 字段拍照模式：按 allow_photo / photo_required 判断
					if (isFieldPhotoMode()) {
						const visibleRequiredPhotoFields = (currentItem.value.dataFields || [])
							.filter(f => f?.allow_photo === true && f?.photo_required === true && shouldShowField(f))

						if (visibleRequiredPhotoFields.length > 0) {
							hasRequiredPhotos = visibleRequiredPhotoFields.every(f => getPhotosForField(f).length > 0)
						} else {
							const allowedPhotoFields = (currentItem.value.dataFields || []).filter(f => f?.allow_photo === true)
							const linkedTotal = allowedPhotoFields.reduce((sum, f) => sum + getPhotosForField(f).length, 0)
							hasRequiredPhotos = linkedTotal > 0
						}
					} else {
						// both 但字段未启用拍照：走“未关联照片”模式
						hasRequiredPhotos = currentItem.value.photos && currentItem.value.photos.length > 0
					}

					if (hasRequiredPhotos && hasRequiredData) {
						status = strictCheck.valid ? 'completed' : 'failed'
					} else {
						const hasAnyPhoto = (currentItem.value.photos && currentItem.value.photos.length > 0)
						status = (hasAnyPhoto || strictCheck.hasAnyValue) ? 'in_progress' : 'pending'
					}
				} else if (reqType === 'photo') {
					status = hasRequiredPhotos ? 'completed' : 'pending'
				} else if (reqType === 'data') {
					if (!hasRequiredData) {
						status = strictCheck.hasAnyValue ? 'in_progress' : 'pending'
					} else {
						status = strictCheck.valid ? 'completed' : 'failed'
					}
				}
			
			// 更新检查项
			const updateData = {
				status,
				data_value: dataValue,
				notes: currentItem.value.notes,
				checked_at: new Date().toISOString(),
				validation_result: currentItem.value.validation_result
			}
			
			// 先上传照片（如果有新照片的话）
			if (currentItem.value.photos && currentItem.value.photos.length > 0) {
				console.log('开始上传照片，照片数量:', currentItem.value.photos.length)
				uni.showLoading({ title: $t('messages.uploadingPhoto') })
				
					try {
						const fieldPhotoMode = isFieldPhotoMode()
						const allowedPhotoFieldIdSet = fieldPhotoMode ? getAllowedPhotoFieldIdSet() : new Set()

						for (let i = 0; i < currentItem.value.photos.length; i++) {
							const photo = currentItem.value.photos[i]
							console.log('检查照片路径:', photo.file_path)
						
						// 跳过已上传的照片（有photo.id或已是服务器路径）
						if (
							photo?.id ||
							(photo.file_path && (
								photo.file_path.startsWith('uploads/') ||
								photo.file_path.startsWith('/uploads') ||
								photo.file_path.startsWith('http')
							))
						) {
							console.log('跳过已上传的照片:', photo.file_path, photo?.id)
							continue
						}
						
						// 上传新拍摄/选择的本地文件
						if (photo.file_path) {
							const localFilePath = photo.file_path
							console.log('开始上传照片:', photo.file_path)
							
							// 构建照片上传数据，只传递有效字段（过滤undefined）
							const photoData = {
								check_item_id: currentItem.value.id,
								has_watermark: photo.has_watermark || false
							}

								if (photo.local_upload_without_geo) {
									photoData.local_upload_without_geo = true
								}

								// 字段级照片：仅在“字段拍照模式”下才允许传 field_id（且必须属于 allow_photo=true 的字段）
								if (fieldPhotoMode) {
									const fidStr = (photo.field_id !== undefined && photo.field_id !== null) ? String(photo.field_id).trim() : ''
									if (!fidStr) {
										throw new Error('字段照片缺少field_id，无法上传')
									}
									if (!allowedPhotoFieldIdSet.has(fidStr)) {
										throw new Error('field_id无效或该字段禁止拍照')
									}
									photoData.field_id = fidStr
								}
								
								// 只在有效时添加GPS相关字段
								if (photo.latitude !== undefined && photo.latitude !== null) {
								photoData.gps_latitude = photo.latitude
							}
							if (photo.longitude !== undefined && photo.longitude !== null) {
								photoData.gps_longitude = photo.longitude
							}
							if (photo.gps_accuracy !== undefined && photo.gps_accuracy !== null) {
								photoData.gps_accuracy = photo.gps_accuracy
							}
							
							console.log('照片上传数据:', photoData)
							
							const uploadResult = await inspectionStore.uploadPhoto(
								inspectionId.value,
								photo.file_path,
								photoData
							)
							
							console.log('照片上传结果:', uploadResult)
							
							if (!uploadResult.success) {
								throw new Error(uploadResult.error || $t('inspection.photoUploadFailed'))
							}
							
							// 用后端返回结果替换本地占位，确保后续删除/展示使用photo.id与服务器路径
							currentItem.value.photos[i] = uploadResult.data

							// 上传成功后：将本地原图持久化缓存（下次优先本地展示）
							try {
								const cacheRes = await saveLocalPhotoToCache({
									photoId: uploadResult.data?.id,
									localFilePath,
									ctx: photoCacheCtx.value
								})
								if (cacheRes?.ok && cacheRes?.localPath) {
									setPhotoReady(uploadResult.data, cacheRes.localPath)
								}
							} catch (e) {
								// ignore：不影响业务保存
							}
						} else {
							console.log('跳过照片（无有效路径）:', photo.file_path)
						}
					}
				} catch (photoError) {
					console.error('照片上传失败:', photoError)
					uni.hideLoading()
					uni.showToast({
						title: $t('messages.photoUploadFailedWithReason', { reason: photoError.message }),
						icon: 'error',
						duration: 3000
					})
					return
				} finally {
					uni.hideLoading()
				}
			}

			const result = await inspectionStore.updateInspectionItem(
				inspectionId.value, 
				currentItem.value.id, 
				updateData
				)
				
				if (result.success) {
					const updatedItem = result.data || {}
					// 更新本地数据
					const itemIndex = checkItems.value.findIndex(item => item.id === currentItem.value.id)
					if (itemIndex > -1) {
						checkItems.value[itemIndex] = {
							...checkItems.value[itemIndex],
							...updatedItem,
							// 保留前端编辑态字段（后端不一定返回）
							dataFields: currentItem.value.dataFields,
							notes: currentItem.value.notes,
							checked_at: updateData.checked_at,
							validation_result: currentItem.value.validation_result,
							// 确保照片使用后端最新结果（含photo.id、服务器路径）
							photos: updatedItem.photos || currentItem.value.photos || []
						}
					}
					
					// 更新检查进度
					await updateInspectionProgress()
				
				// 清除自动保存的数据（保存成功后）
				clearAutoSavedData(currentItem.value.id)
				
				uni.showToast({
					title: $t('inspection.saveSuccess'),
					icon: 'success'
				})
				
				closeItemModal()
			}
			
			} catch (error) {
				console.error('保存检查项失败:', error)
				const reason = String(error?.message || '').trim()
				uni.showToast({
					title: reason
						? $t('messages.saveFailedWithReason', { reason })
						: $t('inspection.saveFailed'),
					icon: 'error'
				})
			} finally {
				savingItem.value = false
			}
		}
	
	const updateInspectionProgress = async () => {
		const totalItems = checkItems.value.length
		const completedItems = checkItems.value.filter(item => item.status === 'completed').length
		const completionRate = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0
		
		inspectionData.value = {
			...inspectionData.value,
			total_items: totalItems,
			completed_items: completedItems,
			completion_rate: completionRate
		}
	}
	
	const saveDraft = async () => {
		try {
			saving.value = true
			
			const result = await inspectionStore.updateInspection(inspectionId.value, {
				status: 'draft'
			})
			
			if (result.success) {
				uni.showToast({
					title: $t('inspection.draftSaved'),
					icon: 'success'
				})
			}
			
			} catch (error) {
				console.error('保存草稿失败:', error)
				const reason = String(error?.message || '').trim()
				uni.showToast({
					title: reason
						? $t('messages.saveFailedWithReason', { reason })
						: $t('inspection.saveFailed'),
					icon: 'error'
				})
			} finally {
				saving.value = false
			}
		}
	
	const submitInspection = async () => {
		if (!canSubmit.value) {
			uni.showModal({
				title: $t('common.hint'),
				content: $t('inspection.pleaseCompleteAll'),
				showCancel: false
			})
			return
		}
		
		// 检查是否有未绑定的“设备级”检查项（按 扇区×频段 去重）
		const deviceMap = new Map()
		checkItems.value.forEach(it => {
			if (!isDeviceLevelItem(it)) return
			const key = getDeviceKey(it)
			if (!key) return
			if (!deviceMap.has(key)) deviceMap.set(key, [])
			deviceMap.get(key).push(it)
		})
		
		const unboundDevices = []
		deviceMap.forEach(items => {
			const bound = items.some(x => x.equipment_sn)
			if (!bound && items.length) {
				unboundDevices.push(items[0])
			}
		})
		
		if (unboundDevices.length > 0) {
			showPreSubmitCheckModal.value = true
			preSubmitUnboundList.value = unboundDevices
			return
		}
		
		uni.showModal({
			title: $t('inspection.confirmSubmitTitle'),
			content: $t('inspection.confirmSubmitContent'),
			success: async (res) => {
				if (res.confirm) {
					await doSubmitInspection()
				}
			}
		})
	}
	
	const doSubmitInspection = async () => {
		try {
			submitting.value = true
			
			const result = await inspectionStore.updateInspection(inspectionId.value, {
				status: 'submitted',
				end_time: new Date().toISOString()
			})
			
			if (result.success) {
				uni.showToast({
					title: $t('inspection.submitSuccess'),
					icon: 'success'
				})
				
				// 延迟跳转
				setTimeout(() => {
					uni.redirectTo({
						url: `/pages/inspection/detail?id=${inspectionId.value}`
					})
				}, 1500)
			}
			
		} catch (error) {
			console.error('提交检查失败:', error)
			uni.showToast({
				title: $t('inspection.submitFailed'),
				icon: 'error'
			})
		} finally {
			submitting.value = false
		}
	}
	
	// 快速绑定设备
	const quickBindDevice = async (item) => {
		// 关闭核查弹窗，打开该检查项的绑定界面
		showPreSubmitCheckModal.value = false
		currentItem.value = { ...item }
		
		// 自动触发扫码
		await uni.nextTick()
		scanEquipmentForBinding(item)
	}
	
	// 强制提交（忽略未绑定警告）
	const forceSubmitWithWarning = async () => {
		uni.showModal({
			title: $t('inspection.confirmSubmitTitle'),
			content: $t('inspection.forceSubmitWarning'),
			confirmText: $t('common.confirm'),
			cancelText: $t('common.cancel'),
			success: async (res) => {
				if (res.confirm) {
					showPreSubmitCheckModal.value = false
					await doSubmitInspection()
				}
			}
		})
	}
	
	const saveInspection = async () => {
		await saveDraft()
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
	
	const getCheckItemClass = (status) => {
		return `status-${status}`
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
	
	const getStatusClass = (status) => {
		return `status-${status}`
	}

	const getIssueHighlightClass = (item) => {
		if (item?.review_status === 'fail') return 'issue-fail'
		if (item?.review_status === 'warning') return 'issue-warning'
		if (item?.status === 'failed') return 'issue-failed'
		return ''
	}

	const getStatusText = (status) => {
		const statusMap = {
			pending: $t('inspection.pending'),
			in_progress: $t('inspection.inProgress'),
			completed: $t('inspection.completed'),
			failed: $t('inspection.failed'),
			skipped: $t('inspection.skipped')
		}
		return statusMap[status] || $t('inspection.unknown')
	}
	
	const getRequiredTypeText = (type) => {
		const typeMap = {
			photo: $t('inspection.photoOnly'),
			data: $t('inspection.dataOnly'),
			both: $t('inspection.photoAndData')
		}
		return typeMap[type] || $t('inspection.unknown')
	}
	
	const formatDateTime = (dateTime) => {
		if (!dateTime) return ''
		const date = new Date(dateTime)
		return date.toLocaleString(languageStore.currentLocaleTag)
	}
	
	const formatTime = (dateTime) => {
		if (!dateTime) return ''
		const date = new Date(dateTime)
		return date.toLocaleTimeString(languageStore.currentLocaleTag, {
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	// Picker相关辅助函数
	const getPickerIndex = (dataField) => {
		if (!dataField.options || !dataField.value) return 0
		const index = dataField.options.findIndex(opt => opt.value === dataField.value)
		return index >= 0 ? index : 0
	}
	
	const getPickerDisplayValue = (dataField) => {
		if (!dataField.options || !dataField.value) return ''
		const option = dataField.options.find(opt => opt.value === dataField.value)
		return option ? option.label : ''
	}
	
	const onPickerChange = (event, dataField) => {
		const index = event.detail.value
		if (dataField.options && dataField.options[index]) {
			dataField.value = dataField.options[index].value
			onDataChange()
		}
	}
	
	// 多选框组变更
	const onCheckboxChange = (event, dataField) => {
		dataField.value = event.detail.value // 数组
		onDataChange()
	}
	
	// 开关变更
	const onSwitchChange = (event, dataField) => {
		dataField.value = event.detail.value
		onDataChange()
	}
	
	// 日期变更
	const onDateChange = (event, dataField) => {
		dataField.value = event.detail.value // YYYY-MM-DD
		onDataChange()
	}
	
	// 时间变更
	const onTimeChange = (event, dataField) => {
		dataField.value = event.detail.value // HH:MM
		onDataChange()
	}
	
	// 日期时间变更
	const onDatetimeChange = (event, type, dataField) => {
		const currentValue = dataField.value || ''
		let datePart = getDatePart(currentValue)
		let timePart = getTimePart(currentValue)
		
		if (type === 'date') {
			datePart = event.detail.value
		} else {
			timePart = event.detail.value
		}
		
		// 组合日期和时间
		if (datePart && timePart) {
			dataField.value = `${datePart} ${timePart}`
		} else if (datePart) {
			dataField.value = datePart
		} else if (timePart) {
			dataField.value = timePart
		}
		
		onDataChange()
	}
	
	// 辅助函数：获取当前日期
	const getCurrentDate = () => {
		const now = new Date()
		const year = now.getFullYear()
		const month = String(now.getMonth() + 1).padStart(2, '0')
		const day = String(now.getDate()).padStart(2, '0')
		return `${year}-${month}-${day}`
	}
	
	// 辅助函数：获取当前时间
	const getCurrentTime = () => {
		const now = new Date()
		const hours = String(now.getHours()).padStart(2, '0')
		const minutes = String(now.getMinutes()).padStart(2, '0')
		return `${hours}:${minutes}`
	}
	
	// 辅助函数：从日期时间字符串中提取日期部分
	const getDatePart = (datetime) => {
		if (!datetime) return ''
		// 支持格式: YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS 或 YYYY-MM-DD HH:MM:SS
		const parts = String(datetime).split(/[T ]/)[0]
		return parts || ''
	}
	
	// 辅助函数：从日期时间字符串中提取时间部分
	const getTimePart = (datetime) => {
		if (!datetime) return ''
		// 支持格式: YYYY-MM-DDTHH:MM:SS 或 YYYY-MM-DD HH:MM:SS
		const parts = String(datetime).split(/[T ]/)
		if (parts.length > 1) {
			// 提取HH:MM部分
			const timePart = parts[1].substring(0, 5)
			return timePart
		}
		return ''
	}
	
	// 辅助函数：检查多选值是否包含目标值
	const isChecked = (values, targetValue) => {
		return Array.isArray(values) && values.includes(targetValue)
	}
	
		// 获取字段帮助提示
		const getFieldHint = (field) => {
			const hints = []
		
		// 数字约束提示
		if (field.type === 'number' && field.constraints) {
			if (field.constraints.min !== undefined && field.constraints.max !== undefined) {
				hints.push($t('common.rangeWithMinMax', { min: field.constraints.min, max: field.constraints.max }))
			} else if (field.constraints.min !== undefined) {
				hints.push($t('common.minWithValue', { min: field.constraints.min }))
			} else if (field.constraints.max !== undefined) {
				hints.push($t('common.maxWithValue', { max: field.constraints.max }))
			}
		}
		
		// 文本长度提示
		if ((field.type === 'text' || field.type === 'rich_text') && field.constraints) {
			if (field.constraints.max_length) {
				hints.push($t('common.maxChars', { count: field.constraints.max_length }))
			}
		}
		
			return hints.join(' | ')
		}

		const showFieldHelp = (field) => {
			const content = String(field?.help_text || '').trim()
			if (!content) return
			const title = `${field?.label || field?.field_id || $t('inspection.dataEntry')} 描述/注意事项`
			uni.showModal({
				title,
				content,
				showCancel: false,
				confirmText: $t('common.ok')
			})
		}
	
	// 扫码绑定设备功能
	const scanEquipmentForBinding = async (item = null) => {
		const targetItem = item || currentItem.value
		// 只有设备级检查项才需要绑定设备
		if (!targetItem || !isDeviceLevelItem(targetItem)) {
			uni.showToast({
				title: $t('inspection.invalidCheckItem'),
				icon: 'none',
				duration: 3000
			})
			return
		}
		
		try {
			console.log('开始扫码绑定设备...')
			
			// 执行扫码
			const result = await new Promise((resolve, reject) => {
				uni.scanCode({
					scanType: ['barCode', 'qrCode'],
					success: resolve,
					fail: reject
				})
			})
			
			console.log('扫码结果:', result.result)
			
			// 解析条码
			const parsedBarcode = parseBarcode(result.result)
			console.log('解析结果:', parsedBarcode)
			
			if (!parsedBarcode.success || !isValidParseResult(parsedBarcode)) {
				uni.showToast({
					title: parsedBarcode.error || $t('stock.invalidBarcode'),
					icon: 'none'
				})
				return
			}
			
			uni.showLoading({
				title: $t('inspection.validatingEquipment'),
				mask: true
			})
			
			try {
				// 验证设备是否已被当前用户领料
				const checkResponse = await new Promise((resolve, reject) => {
					uni.request({
						url: buildApiUrl(`/api/inspections/equipment/check-pickup/${parsedBarcode.sn}`),
						method: 'GET',
						header: getAuthHeaders(userStore.token),
						success: resolve,
						fail: reject
					})
				})
				
				console.log('设备验证结果:', checkResponse.data)
				
				if (checkResponse.statusCode !== 200) {
					throw new Error(checkResponse.data?.detail || $t('inspection.equipmentValidateFailed'))
				}
				
				// 绑定设备到小区
				const bindResponse = await new Promise((resolve, reject) => {
					uni.request({
						url: buildApiUrl(`/api/inspections/detail/${inspectionData.value.id}/bind-equipment`),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: {
							equipment_sn: parsedBarcode.sn,
							sector_id: targetItem.sector_id,
							band: targetItem.band
						},
						success: resolve,
						fail: reject
					})
				})
				
				console.log('设备绑定结果:', bindResponse.data)
				
				// 冲突与权限等错误的前置友好提示
				if (bindResponse.statusCode === 409) {
					uni.hideLoading()
					return uni.showModal({
						title: $t('inspection.bindConflictTitle'),
						content: bindResponse.data?.detail || $t('inspection.bindConflictContent', { sn: parsedBarcode.sn }),
						showCancel: false
					})
				}
				if (bindResponse.statusCode === 403) {
					uni.hideLoading()
					return uni.showToast({ title: bindResponse.data?.detail || $t('inspection.equipmentNotPickedUp'), icon: 'none', duration: 3000 })
				}
				if (bindResponse.statusCode === 400) {
					uni.hideLoading()
					return uni.showToast({ title: bindResponse.data?.detail || $t('inspection.bindFailed'), icon: 'none', duration: 3000 })
				}
				
				if (bindResponse.statusCode === 200 && bindResponse.data.success) {
					// 更新本地检查项数据
					const updatedItems = checkItems.value.map(checkItem => {
						if (checkItem.sector_id === targetItem.sector_id && 
							(!targetItem.band || checkItem.band === targetItem.band)) {
							return {
								...checkItem,
								equipment_sn: parsedBarcode.sn
							}
						}
						return checkItem
					})
					
					checkItems.value = updatedItems
					
					// 如果当前正在查看该检查项，也更新当前项
					if (currentItem.value && currentItem.value.id === targetItem.id) {
						currentItem.value = {
							...currentItem.value,
							equipment_sn: parsedBarcode.sn
						}
					}
					
					uni.hideLoading()
					const bindTarget = targetItem.band ? `${targetItem.sector_id}_${targetItem.band}` : targetItem.sector_id
					uni.showModal({
						title: $t('inspection.bindSuccessTitle'),
						content: $t('inspection.bindSuccessDetail', { sn: parsedBarcode.sn, target: bindTarget }),
						showCancel: false,
						confirmText: $t('common.confirm'),
						success: () => {
							// 如果是从外部调用，打开检查项详情
							if (item && !currentItem.value) {
								currentItem.value = { ...targetItem, equipment_sn: parsedBarcode.sn }
							}
						}
					})
				} else {
					throw new Error(bindResponse.data?.detail || $t('inspection.bindFailed'))
				}
				
			} catch (error) {
				uni.hideLoading()
				console.error('设备绑定失败:', error)
				uni.showToast({
					title: error.message || $t('inspection.bindFailed'),
					icon: 'none',
					duration: 3000
				})
			}
			
		} catch (error) {
			console.error('扫码失败:', error)
			uni.showToast({
				title: $t('stock.scanFailed'),
				icon: 'none'
			})
		}
	}
	
	// 解绑设备
	const unbindEquipment = async () => {
		if (!currentItem.value || !isDeviceLevelItem(currentItem.value) || !currentItem.value.equipment_sn) {
			return
		}
		
		uni.showModal({
			title: $t('inspection.unbindConfirmTitle'),
			content: $t('inspection.unbindConfirmContent', { sn: currentItem.value.equipment_sn }),
			success: async (res) => {
				if (res.confirm) {
					try {
						uni.showLoading({
							title: $t('messages.unbinding'),
							mask: true
						})
						
						// 调用绑定接口，传空的设备SN实现解绑
						const response = await new Promise((resolve, reject) => {
							uni.request({
								url: buildApiUrl(`/api/inspections/detail/${inspectionData.value.id}/bind-equipment`),
								method: 'POST',
								header: getAuthHeaders(userStore.token),
								data: {
									equipment_sn: '',  // 空字符串表示解绑
									sector_id: currentItem.value.sector_id,
									band: currentItem.value.band
								},
								success: resolve,
								fail: reject
							})
						})
						
						if (response.statusCode === 200) {
							// 更新本地数据
							const updatedItems = checkItems.value.map(checkItem => {
								if (checkItem.sector_id === currentItem.value.sector_id && 
									(!currentItem.value.band || checkItem.band === currentItem.value.band)) {
									return {
										...checkItem,
										equipment_sn: null
									}
								}
								return checkItem
							})
							
							checkItems.value = updatedItems
							currentItem.value = {
								...currentItem.value,
								equipment_sn: null
							}
							
							uni.hideLoading()
							uni.showToast({
								title: $t('inspection.unbindSuccessTitle'),
								icon: 'success'
							})
						} else {
							throw new Error($t('inspection.unbindFailedTitle'))
						}
						
					} catch (error) {
						uni.hideLoading()
						console.error('解绑失败:', error)
						uni.showToast({
							title: $t('inspection.unbindFailedTitle'),
							icon: 'none'
						})
					}
				}
			}
		})
	}
</script>

<style scoped>
    .checklist-container {
        height: 100vh;
        width: 100vw;
        max-width: 100vw;
        background: var(--bg-page);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        box-sizing: border-box;
    }
	
	/* 检查信息 */
	.inspection-info {
		background: var(--bg-elevated);
		margin: 20rpx;
		border-radius: 20rpx;
		padding: 30rpx;
		box-shadow: var(--shadow-card);
	}
	
	.info-row {
		display: flex;
		align-items: center;
		margin-bottom: 15rpx;
		gap: 20rpx;
	}
	
		.info-row:last-child {
			margin-bottom: 0;
		}

		/* 开站工单：设备上线/激活状态标签 */
		.omc-tags-row {
			display: flex;
			gap: 12rpx;
			flex-wrap: wrap;
			margin-bottom: 15rpx;
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
		
		.info-label {
			font-size: 28rpx;
			color: #666;
			min-width: 80rpx;
	}
	
	.info-value {
		font-size: 28rpx;
		color: #333;
		font-weight: 500;
	}
	
	.progress-bar {
		flex: 1;
		height: 12rpx;
		background: #e9ecef;
		border-radius: 6rpx;
		overflow: hidden;
		margin-left: 20rpx;
	}
	
	.progress-fill {
		height: 100%;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		border-radius: 6rpx;
		transition: width 0.3s ease;
	}
	
	/* 分类标签 */
	.category-tabs {
		background: white;
		margin: 0 20rpx 20rpx;
		border-radius: 20rpx;
		overflow: hidden;
	}
	
	.tabs-scroll {
		white-space: nowrap;
	}
	
	.tab-item {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx;
		padding: 0 30rpx;
		margin: 0 5rpx;
		border-radius: 22rpx;
		background: #f8f9fa;
		color: #666;
		transition: all 0.3s ease;
	}

	.tab-item.active {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		color: #fff;
	}

	.tab-item.issue-tab {
		background: #fef2f2;
		color: #dc2626;
	}

	.tab-item.issue-tab.active {
		background: linear-gradient(135deg, #dc2626, #ef4444);
		color: #fff;
	}
	
	.tab-text {
		font-size: 26rpx;
		white-space: nowrap;
	}
	
	/* 检查内容 */
	.checklist-content {
		flex: 1;
		height: 0;
		min-height: 0;
		padding: 0 20rpx calc(140rpx + env(safe-area-inset-bottom));
		width: 100%;
		max-width: 100vw;
		box-sizing: border-box;
		overflow-x: hidden;
	}
	
	.check-section {
		margin-bottom: 30rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 15rpx;
		padding: 0 10rpx;
	}
	
	.section-title { font-size: 30rpx; font-weight: bold; color: var(--text-primary); }
	
	.section-count {
		font-size: 24rpx;
		color: #999;
	}
	
	/* 检查项 */
	.check-item {
		background: white;
		border-radius: 20rpx;
		margin-bottom: 15rpx;
		padding: 25rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
		transition: transform 0.2s ease;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.check-item:active {
		transform: scale(0.98);
	}
	
	.check-item.status-pending {
		border-left: 6rpx solid #6c757d;
	}
	
	.check-item.status-in_progress {
		border-left: 6rpx solid #007bff;
	}
	
	.check-item.status-completed {
		border-left: 6rpx solid #28a745;
	}
	
	.check-item.status-failed {
		border-left: 6rpx solid #dc3545;
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
	
	.item-header {
		display: flex;
		align-items: center;
		gap: 15rpx;
		width: 100%;
		max-width: 100%;
		min-width: 0;
		box-sizing: border-box;
		overflow: hidden;
		min-height: 50rpx;
	}
	
	.item-status {
		flex-shrink: 0;
	}
	
	.status-icon {
		font-size: 36rpx;
	}
	
	.item-info {
		flex: 1;
		min-width: 0;
		max-width: calc(100% - 200rpx);
		overflow: hidden;
	}
	
	.item-name {
		font-size: 30rpx;
		font-weight: 500;
		color: #333;
		display: flex;
		align-items: center;
		margin-bottom: 8rpx;
		word-break: break-word;
		overflow-wrap: break-word;
		line-height: 1.4;
		max-width: 100%;
		min-height: 40rpx;
	}
	
	.item-id {
		font-size: 24rpx;
		color: #007bff;
		max-width: 100%;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		display: flex;
		align-items: center;
		min-height: 32rpx;
	}

	.issue-hint {
		margin-top: 10rpx;
		display: flex;
		gap: 10rpx;
		align-items: flex-start;
		flex-wrap: wrap;
	}

	.issue-badge {
		font-size: 22rpx;
		padding: 6rpx 10rpx;
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
	
	.item-actions {
		display: flex;
		align-items: center;
		gap: 10rpx;
		flex-shrink: 0;
		max-width: 180rpx;
		justify-content: flex-end;
	}
	
	.required-badge {
		font-size: 22rpx;
		padding: 6rpx 10rpx;
		background: #e9ecef;
		color: #495057;
		border-radius: 10rpx;
		max-width: 120rpx;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 32rpx;
	}
	
	.action-arrow {
		font-size: 28rpx;
		color: #ccc;
		flex-shrink: 0;
	}
	
	.item-details {
		margin-top: 15rpx;
		padding-top: 15rpx;
		border-top: 1rpx solid #f0f0f0;
		width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.detail-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 8rpx;
		gap: 10rpx;
		width: 100%;
		min-width: 0;
		box-sizing: border-box;
	}
	
	.detail-label {
		font-size: 24rpx;
		color: #666;
		min-width: 100rpx;
		max-width: 120rpx;
		flex-shrink: 0;
		white-space: nowrap;
		display: flex;
		align-items: center;
		min-height: 36rpx;
	}
	
	.detail-value {
		font-size: 24rpx;
		color: #333;
		flex: 1;
		min-width: 0;
		max-width: 100%;
		word-break: break-word;
		overflow-wrap: break-word;
		text-align: right;
		line-height: 1.4;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		min-height: 36rpx;
	}
	
	.detail-value.error {
		color: #dc3545;
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
	
	/* 底部操作栏 */
	.bottom-actions {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: var(--bg-elevated);
		padding: 20rpx 20rpx calc(20rpx + env(safe-area-inset-bottom));
		border-top: 1rpx solid var(--border-soft);
		display: flex;
		gap: 20rpx;
		z-index: 100;
	}
	
	.action-btn {
		flex: 1;
		padding: 25rpx;
		border-radius: 15rpx;
		font-size: 30rpx;
		border: none;
		transition: all 0.3s ease;
	}
	
	.draft-btn {
		background: #6c757d;
		color: white;
	}
	
	.draft-btn:disabled {
		background: #adb5bd;
	}
	
	.submit-btn {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		color: white;
	}
	
	.submit-btn:disabled {
		background: #adb5bd;
	}
	
	/* 检查项详情弹窗 */
	.item-modal-overlay {
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
	
	.item-modal {
		background: var(--bg-elevated);
		border-radius: 20rpx;
		width: 100%;
		max-width: 700rpx;
		max-height: 90vh;
		display: flex;
		flex-direction: column;
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
		padding: 30rpx;
		overflow-y: auto;
		overflow-x: hidden;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
	}
	
	.modal-section {
		margin-bottom: 40rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.section-label {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 20rpx;
		display: block;
	}
	
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20rpx;
	}
	
	.add-photo-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 12rpx;
		min-height: 88rpx;
		padding: 0 24rpx;
		background: #007bff;
		color: #fff;
		border: none;
		border-radius: 22rpx;
		font-size: 26rpx;
	}

	.form-label-left {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 12rpx;
		flex: 1;
		min-width: 0;
	}

	.field-help-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 6rpx;
	}

	.field-photo-btn {
		display: inline-flex;
		align-items: center;
		gap: 10rpx;
		padding: 0 18rpx;
		min-height: 64rpx;
		background: rgba(var(--color-primary-rgb), 0.08);
		color: var(--color-primary);
		border: 2rpx solid rgba(var(--color-primary-rgb), 0.25);
		border-radius: 16rpx;
		font-size: 24rpx;
	}

	.field-photo-btn .btn-count {
		margin-left: 4rpx;
		padding: 0 10rpx;
		min-width: 32rpx;
		height: 32rpx;
		line-height: 32rpx;
		text-align: center;
		border-radius: 16rpx;
		background: var(--color-primary);
		color: #fff;
		font-size: 22rpx;
	}

	.field-photo-grid {
		margin-top: 10rpx;
	}

	.unlinked-photos {
		margin-top: 24rpx;
	}

	.photo-required-mark {
		color: #ff4757;
		margin-left: 2rpx;
		font-weight: bold;
	}
	
	.info-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.grid-item {
		display: flex;
		flex-direction: column;
		gap: 8rpx;
		width: 100%;
		max-width: 100%;
		min-width: 0;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.grid-label {
		font-size: 24rpx;
		color: #666;
	}
	
	.grid-value {
		font-size: 26rpx;
		color: #333;
		font-weight: 500;
		word-break: break-word;
		overflow-wrap: break-word;
		max-width: 100%;
		box-sizing: border-box;
	}
	
	.grid-value.status-pending {
		color: #6c757d;
	}
	
	.grid-value.status-completed {
		color: #28a745;
	}
	
	.grid-value.status-failed {
		color: #dc3545;
	}
	
	/* 检查项描述 */
	.item-description {
		margin-top: 25rpx;
		padding: 20rpx;
		background: linear-gradient(135deg, #fff9e6, #fff5d9);
		border-left: 4rpx solid var(--color-primary);
		border-radius: 12rpx;
	}
	
	.description-header {
		display: flex;
		align-items: center;
		gap: 10rpx;
		margin-bottom: 15rpx;
	}
	
	.description-icon {
		font-size: 32rpx;
	}
	
	.description-title {
		font-size: 28rpx;
		font-weight: bold;
		color: var(--color-primary);
	}
	
	.description-content {
		font-size: 26rpx;
		line-height: 1.6;
		color: #666;
		word-break: break-word;
		white-space: pre-wrap;
	}
	
	/* 照片网格 */
	.photo-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200rpx, 1fr));
		gap: 15rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.photo-item {
		position: relative;
		border-radius: 12rpx;
		overflow: hidden;
		background: #f8f9fa;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
	}

	.photo-thumb-wrapper {
		position: relative;
		width: 100%;
		height: 200rpx;
	}

	.photo-thumb {
		width: 100%;
		height: 200rpx;
	}

	.photo-thumb-placeholder {
		width: 100%;
		height: 200rpx;
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
		font-size: 28rpx;
		font-weight: 600;
	}

	.photo-status-error {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10rpx;
	}

	.photo-status-sub {
		color: rgba(255, 255, 255, 0.9);
		font-size: 24rpx;
	}
	
	.photo-info {
		padding: 15rpx;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.photo-time {
		font-size: 22rpx;
		color: #666;
	}
	
	.delete-photo {
		font-size: 28rpx;
		color: #dc3545;
	}
	
	.no-photos {
		text-align: center;
		padding: 60rpx 20rpx;
		color: #999;
	}
	
	.no-photos-text {
		font-size: 26rpx;
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
	
	/* 数据表单 */
	.data-form {
		display: flex;
		flex-direction: column;
		gap: 32rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.form-item-wrapper {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 16rpx;
		box-sizing: border-box;
	}
	
	.form-label-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 12rpx;
		width: 100%;
	}
	
	.form-input-row {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 16rpx;
	}
	
	.form-label {
		font-size: 30rpx;
		color: #333;
		font-weight: 600;
		display: flex;
		align-items: center;
		line-height: 1.5;
	}
	
	.form-hint-inline {
		font-size: 24rpx;
		color: #999;
		margin-left: 8rpx;
	}
	
	.form-input-field {
		flex: 1;
		width: 100%;
		padding: 28rpx 24rpx;
		border: 2rpx solid #ddd;
		border-radius: 12rpx;
		font-size: 30rpx;
		background: white;
		color: #333;
		box-sizing: border-box;
		min-height: 88rpx;
		line-height: 1.5;
	}
	
	.form-input-field:focus {
		border-color: var(--color-primary);
		background: white;
		outline: none;
		box-shadow: 0 0 0 3rpx rgba(var(--color-primary-rgb), 0.1);
	}
	
	.input-with-unit {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 12rpx;
		width: 100%;
	}
	
	.input-unit {
		font-size: 28rpx;
		color: #666;
		flex-shrink: 0;
		font-weight: 500;
	}
	
	.form-picker-field {
		flex: 1;
		width: 100%;
		background: white;
		border: 2rpx solid #ddd;
		border-radius: 12rpx;
		min-height: 88rpx;
		box-sizing: border-box;
	}
	
	.picker-display-value {
		padding: 28rpx 24rpx;
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 88rpx;
		box-sizing: border-box;
	}
	
	.picker-text {
		flex: 1;
		font-size: 30rpx;
		color: #333;
		line-height: 1.5;
	}
	
	.picker-text.placeholder-text {
		color: #999;
	}
	
	.picker-arrow {
		font-size: 20rpx;
		color: #999;
		margin-left: 12rpx;
		flex-shrink: 0;
	}
	
	.picker-icon {
		margin-left: 12rpx;
		font-size: 32rpx;
		flex-shrink: 0;
	}
	
	.required-mark {
		color: #ff4757;
		margin-left: 4rpx;
		font-weight: bold;
		font-size: 32rpx;
	}
	
	/* 多选框组 */
	.checkbox-group {
		display: flex;
		flex-direction: column;
		gap: 20rpx;
	}
	
	.checkbox-item {
		display: flex;
		align-items: center;
		padding: 24rpx;
		background: #f8f9fa;
		border-radius: 12rpx;
		border: 2rpx solid #e0e0e0;
	}
	
	.checkbox-item checkbox {
		margin-right: 16rpx;
		transform: scale(1.1);
	}
	
	.checkbox-label {
		font-size: 28rpx;
		color: #333;
		flex: 1;
	}
	
	/* 布尔开关 */
	.switch-wrapper {
		display: flex;
		align-items: center;
		padding: 24rpx;
		background: white;
		border: 2rpx solid #ddd;
		border-radius: 12rpx;
	}
	
	.form-switch-field {
		transform: scale(1.2);
		margin-right: 20rpx;
	}
	
	.switch-label {
		font-size: 28rpx;
		color: #333;
		font-weight: 500;
	}
	
	/* 日期时间组合选择器 */
	.datetime-picker-group {
		display: flex;
		gap: 16rpx;
	}
	
	.datetime-date-picker,
	.datetime-time-picker {
		flex: 1;
	}
	
	.picker-display-value.small {
		padding: 20rpx 16rpx;
		min-height: 70rpx;
	}
	
	.picker-display-value.small .picker-text {
		font-size: 26rpx;
	}
	
	.picker-display-value.small .picker-icon {
		font-size: 28rpx;
	}
	
	/* 富文本区域 */
	.form-textarea-field {
		width: 100%;
		min-height: 200rpx;
		padding: 24rpx;
		background: white;
		border: 2rpx solid #ddd;
		border-radius: 12rpx;
		font-size: 28rpx;
		line-height: 1.6;
		box-sizing: border-box;
	}
	
	.form-textarea-field:focus {
		border-color: var(--color-primary);
	}
	
	/* 字段错误提示 */
	.field-error {
		display: block;
		margin-top: 12rpx;
		padding: 12rpx 20rpx;
		background: #ffebee;
		border-left: 4rpx solid #f44336;
		color: #c62828;
		font-size: 24rpx;
		line-height: 1.4;
		border-radius: 6rpx;
	}
	
	/* 字段帮助提示 */
	.field-hint {
		display: block;
		margin-top: 12rpx;
		padding: 12rpx 20rpx;
		background: #e3f2fd;
		border-left: 4rpx solid #2196f3;
		color: #1565c0;
		font-size: 24rpx;
		line-height: 1.4;
		border-radius: 6rpx;
	}
	
	/* 验证结果 */
	.validation-result {
		margin-top: 20rpx;
		padding: 20rpx;
		border-radius: 12rpx;
		background: #f8f9fa;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.result-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 15rpx;
	}
	
	.result-title {
		font-size: 26rpx;
		font-weight: bold;
		color: #333;
	}
	
	.result-status.valid {
		color: #28a745;
	}
	
	.result-status.invalid {
		color: #dc3545;
	}
	
	.result-errors {
		display: flex;
		flex-direction: column;
		gap: 8rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.error-item {
		font-size: 24rpx;
		color: #dc3545;
	}
	
	/* 备注 */
	.note-textarea {
		width: 100%;
		max-width: 100%;
		min-height: 150rpx;
		height: 150rpx;
		padding: 24rpx;
		border: 2rpx solid #e9ecef;
		border-radius: 12rpx;
		font-size: 28rpx;
		background: #f8f9fa;
		resize: vertical;
		box-sizing: border-box;
		overflow: auto;
		line-height: 1.4;
		cursor: text;
	}
	
	.note-textarea:focus {
		border-color: #28a745;
		background: white;
		outline: none;
		box-shadow: 0 0 0 3rpx rgba(40, 167, 69, 0.1);
		transform: none;
	}
	
	/* 弹窗操作 */
	.modal-actions { display: flex; gap: 20rpx; padding: 30rpx; border-top: 1rpx solid var(--border-soft); }
	
	.modal-btn { flex: 1; min-height: 88rpx; padding: 0 24rpx; border-radius: 22rpx; font-size: 30rpx; border: none; display: inline-flex; align-items: center; justify-content: center; }
	
	.cancel-btn {
		background: #6c757d;
		color: white;
	}
	
	.save-btn {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		color: white;
	}
	
	.save-btn:disabled {
		background: #adb5bd;
	}
	
	/* 设备绑定相关样式 - 增强版 */
	.equipment-binding-badge {
		margin-top: 8rpx;
	}

	.binding-status {
		display: flex;
		align-items: center;
		padding: 8rpx 12rpx;
		border-radius: 8rpx;
		font-size: 24rpx;
		
		&.bound {
			background-color: #f0fdf4;
			border: 1rpx solid #86efac;
			
			.binding-info {
				display: flex;
				flex-direction: column;
				margin-left: 8rpx;
			}
			
			.binding-label {
				color: #16a34a;
				font-size: 22rpx;
			}
			
			.binding-sn {
				color: #15803d;
				font-weight: 600;
				font-size: 26rpx;
				margin-top: 2rpx;
				font-family: 'Courier New', monospace;
			}
		}
		
		&.unbound {
			background-color: #fff7ed;
			border: 1rpx solid #fdba74;
			
			.binding-label {
				color: #ea580c;
				margin-left: 6rpx;
			}
		}
	}

	.binding-icon {
		font-size: 28rpx;
	}
	
	.equipment-binding-section {
		margin-top: 10rpx;
	}
	
	.bound-equipment {
		display: flex;
		align-items: center;
		gap: 15rpx;
		padding: 20rpx;
		background: #f0f9ff;
		border: 1rpx solid #0ea5e9;
		border-radius: 12rpx;
	}
	
	.bound-icon {
		font-size: 32rpx;
	}
	
	.bound-info {
		flex: 1;
	}
	
	.bound-text {
		font-size: 28rpx;
		color: #0f172a;
		font-weight: 500;
		display: block;
	}
	
	.bound-sn {
		font-size: 24rpx;
		color: #0ea5e9;
		font-family: monospace;
		margin-top: 4rpx;
		display: block;
	}
	
	.unbind-btn { background: #fee2e2; color: #dc2626; border: 1rpx solid #fca5a5; display: inline-flex; align-items: center; justify-content: center; min-height: 88rpx; padding: 0 24rpx; border-radius: 16rpx; font-size: 26rpx; }
	
	.unbind-equipment {
		display: flex;
		align-items: center;
		gap: 15rpx;
		padding: 20rpx;
		background: #fef3c7;
		border: 1rpx solid #f59e0b;
		border-radius: 12rpx;
	}
	
	.unbind-icon {
		font-size: 32rpx;
	}
	
	.unbind-info {
		flex: 1;
	}
	
	.unbind-text {
		font-size: 28rpx;
		color: #0f172a;
		font-weight: 500;
		display: block;
	}
	
	.unbind-desc {
		font-size: 24rpx;
		color: #f59e0b;
		margin-top: 4rpx;
		display: block;
	}
	
	.bind-btn { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark)); color: #fff; border: none; display: inline-flex; align-items: center; justify-content: center; gap: 10rpx; min-height: 88rpx; padding: 0 24rpx; border-radius: 16rpx; font-size: 26rpx; }
	
	.btn-icon {
		font-size: 24rpx;
	}
	
	/* 提交前核查弹窗样式 */
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 2000;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 40rpx;
	}

	.pre-submit-modal {
		background: white;
		border-radius: 20rpx;
		width: 100%;
		max-width: 700rpx;
		max-height: 80vh;
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
				color: #ea580c;
			}
			
			.modal-close {
				font-size: 48rpx;
				color: #9ca3af;
				cursor: pointer;
			}
		}
		
		.warning-section {
			padding: 24rpx 30rpx;
			background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
			border-bottom: 2rpx solid #fdba74;
			
			.warning-text {
				font-size: 28rpx;
				color: #c2410c;
				line-height: 1.6;
			}
		}
		
		.checklist-scroll {
			max-height: 400rpx;
			padding: 16rpx 0;
		}
		
		.checklist-item {
			display: flex;
			align-items: center;
			justify-content: space-between;
			padding: 24rpx 30rpx;
			border-bottom: 1rpx solid #f3f4f6;
			
			&:active {
				background-color: #f9fafb;
			}
			
			.checklist-item-info {
				display: flex;
				flex-direction: column;
				flex: 1;
				margin-right: 20rpx;
			}
			
			.checklist-item-name {
				font-size: 28rpx;
				color: #111827;
				font-weight: 500;
				margin-bottom: 8rpx;
			}
			
			.checklist-item-cell {
				font-size: 24rpx;
				color: #6b7280;
				font-family: 'Courier New', monospace;
			}
			
			.bind-quick-btn {
				padding: 12rpx 24rpx;
				background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
				color: white;
				border-radius: 8rpx;
				font-size: 24rpx;
				border: none;
			}
		}
		
		.modal-actions {
			display: flex;
			gap: 20rpx;
			padding: 30rpx;
			border-top: 1rpx solid #f3f4f6;
			
			button {
				flex: 1;
				padding: 24rpx;
				border-radius: 12rpx;
				font-size: 28rpx;
				border: none;
			}
			
			.cancel-btn {
				background: #f3f4f6;
				color: #6b7280;
			}
			
			.force-submit-btn {
				background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
				color: white;
			}
		}
	}
</style>
