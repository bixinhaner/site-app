<template>
	<view class="checklist-container">
		<!-- 导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="back-button" @click="goBack">
					<text class="back-icon">←</text>
				</view>
				<text class="navbar-title">{{ inspectionData?.site_name || $t('inspection.checklist') }}</text>
				<view class="navbar-actions">
					<view class="save-button" @click="saveInspection">
						<text class="save-icon">💾</text>
					</view>
				</view>
			</view>
		</view>
		
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
					:class="getCheckItemClass(item.status)"
					@click="openCheckItem(item)"
				>
					<view class="item-header">
						<view class="item-status">
							<text class="status-icon">{{ getStatusIcon(item.status) }}</text>
						</view>
						<view class="item-info">
							<text class="item-name">{{ item.item_name }}</text>
							<text class="item-id" v-if="item.sector_id">{{ $t('inspection.sector') }} {{ item.sector_id }}</text>
							<text class="equipment-binding" v-if="item.sector_id && isCellBound(item)">
								📱 {{ $t('inspection.bound') }}: {{ getCellEquipmentSn(item) }}
							</text>
							<text class="equipment-binding pending" v-else-if="item.sector_id && !isCellBound(item)">
								🔗 {{ $t('inspection.needBinding') }}
							</text>
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
							<text class="detail-value error">{{ item.validation_result.errors.join(', ') }}</text>
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
					<text class="modal-title">{{ currentItem.item_name }}</text>
					<view class="modal-close" @click="closeItemModal">
						<text class="close-icon">×</text>
					</view>
				</view>
				
				<scroll-view class="modal-content" scroll-y>
					<!-- 设备绑定部分 (仅小区级检查项显示) -->
					<view class="modal-section" v-if="currentItem.sector_id">
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
						<view class="item-description" v-if="currentItem.description">
							<view class="description-header">
								<text class="description-icon">💡</text>
								<text class="description-title">{{ $t('inspection.checkItemDescription') || '检查说明' }}</text>
							</view>
							<text class="description-content">{{ currentItem.description }}</text>
						</view>
					</view>
					
					<!-- 照片部分 -->
					<view class="modal-section" v-if="['photo', 'both'].includes(currentItem.required_type)">
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
								@click="previewPhoto(photo)"
							>
								<image class="photo-thumb" :src="buildImageUrl(photo.file_path)" mode="aspectFill"></image>
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
								class="form-item"
								v-for="(dataField, index) in currentItem.dataFields"
								:key="index"
							>
								<text class="form-label">{{ dataField.label }}</text>
								<input 
									class="form-input"
									:type="dataField.type === 'number' ? 'digit' : 'text'"
									:placeholder="dataField.placeholder"
									v-model="dataField.value"
									@input="onDataChange"
								/>
								<text class="form-unit" v-if="dataField.unit">{{ dataField.unit }}</text>
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
									v-for="error in currentItem.validation_result.errors"
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
					<button class="modal-btn save-btn" @click="saveCurrentItem" :disabled="savingItem || (currentItem?.sector_id && !currentItem?.equipment_sn)">
						{{ savingItem ? $t('inspection.savingInProgress') : $t('inspection.save') }}
					</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, watch, getCurrentInstance } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	import { useWorkOrderStore } from '@/stores/workorder'
	import { useLanguageStore } from '@/stores/language'
	import { buildImageUrl, buildApiUrl, getAuthHeaders } from '@/config/api.js'
	import { parseBarcode, formatMacAddress, isValidParseResult } from '@/utils/barcode-parser.js'
	
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	const workOrderStore = useWorkOrderStore()
	const languageStore = useLanguageStore()
	
	// 获取翻译函数
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	
	// 页面参数
	const inspectionId = ref('')
	
	// 响应式数据
	const inspectionData = ref(null)
	const checkItems = ref([])
	const categories = ref([])
	const currentCategory = ref('all')
	const currentItem = ref(null)
	const saving = ref(false)
	const submitting = ref(false)
	const savingItem = ref(false)
	
	// Canvas尺寸（用于水印处理）
	const canvasWidth = ref(400)
	const canvasHeight = ref(300)
	
	// 计算属性
	const filteredCheckItems = computed(() => {
		if (currentCategory.value === 'all') {
			return checkItems.value
		}
		return checkItems.value.filter(item => item.category_id === currentCategory.value)
	})
	
	const groupedCheckItems = computed(() => {
		const groups = {}
		
		filteredCheckItems.value.forEach(item => {
			const categoryId = item.category_id
			if (!groups[categoryId]) {
				groups[categoryId] = {
					categoryId,
					categoryName: item.category_name || categoryId,
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
	
	// 方法
	const loadInspectionData = async () => {
		console.log('🚀 loadInspectionData函数开始执行')
		try {
			// 加载检查数据
			const inspectionResult = await inspectionStore.getInspectionDetail(inspectionId.value)
			if (inspectionResult.success) {
				inspectionData.value = inspectionResult.data
				
				// 如果检查数据中没有站点名称，通过work_order_id获取工单信息
				if (!inspectionData.value.site_name && inspectionData.value.work_order_id) {
					console.log('检查数据缺少站点名称，尝试通过work_order_id获取:', inspectionData.value.work_order_id)
					try {
						// 调用工单详情API获取站点名称
						const workOrderResult = await workOrderStore.getWorkOrder(inspectionData.value.work_order_id)
						
						if (workOrderResult.success && workOrderResult.data?.site_name) {
							console.log('成功从工单获取站点信息:', workOrderResult.data.site_name)
							inspectionData.value.site_name = workOrderResult.data.site_name
						} else {
							console.warn('工单中没有站点名称，尝试通过site_id获取')
							// 备用方案：通过site_id获取
							if (inspectionData.value.site_id) {
								const siteResponse = await uni.request({
									url: buildApiUrl(`/api/sites/${inspectionData.value.site_id}`),
									method: 'GET',
									header: getAuthHeaders(userStore.token)
								})
								
								if (siteResponse.statusCode === 200 && siteResponse.data?.site_name) {
									console.log('成功通过site_id获取站点信息:', siteResponse.data.site_name)
									inspectionData.value.site_name = siteResponse.data.site_name
								}
							}
						}
					} catch (error) {
						console.warn('获取工单站点信息失败:', error)
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
					dataFields: generateDataFields(item),
					notes: item.notes || ''
				}))
				
				// 提取分类信息
				extractCategories()
			}
			
		} catch (error) {
			console.error('加载检查数据失败:', error)
			uni.showToast({
				title: $t('messages.dataLoadFailed'),
				icon: 'error'
			})
		}
	}
	
	const generateDataFields = (item) => {
		// 根据检查项类型生成数据字段
		const fields = []
		
		switch (item.item_id) {
			// 基本信息检查
			case 'tower_id':
				fields.push({
					label: '铁塔编号',
					type: 'text',
					unit: '',
					placeholder: '请输入铁塔编号',
					value: ''
				})
				break
			case 'site_coordinates':
				fields.push(
					{
						label: '纬度',
						type: 'number',
						unit: '度',
						placeholder: '请输入纬度坐标',
						value: ''
					},
					{
						label: '经度',
						type: 'number',
						unit: '度',
						placeholder: '请输入经度坐标',
						value: ''
					}
				)
				break
			
			// 天线相关检查
			case 'antenna_installation':
				fields.push(
					{
						label: '天线型号',
						type: 'text',
						unit: '',
						placeholder: '请输入天线型号',
						value: ''
					},
					{
						label: '安装高度',
						type: 'number',
						unit: '米',
						placeholder: '请输入安装高度',
						value: ''
					}
				)
				break
			case 'antenna_downtilt':
				fields.push({
					label: '下倾角',
					type: 'number',
					unit: '度',
					placeholder: '请输入下倾角度数',
					value: '',
					min: 0,
					max: 20
				})
				break
			case 'azimuth_check':
				fields.push({
					label: '方位角',
					type: 'number',
					unit: '度',
					placeholder: '请输入方位角度数',
					value: '',
					min: 0,
					max: 360
				})
				break
			case 'tower_height_check':
				fields.push({
					label: '天线挂高',
					type: 'number',
					unit: '米',
					placeholder: '请输入天线挂高',
					value: '',
					min: 0,
					max: 100
				})
				break
			case 'vswr_check':
				fields.push({
					label: '驻波比',
					type: 'number',
					unit: '',
					placeholder: '请输入驻波比值',
					value: '',
					min: 1.0,
					max: 2.0
				})
				break
			
			// 设备检查
			case 'cabinet_environment':
				fields.push(
					{
						label: '机柜温度',
						type: 'number',
						unit: '℃',
						placeholder: '请输入机柜温度',
						value: ''
					},
					{
						label: '湿度',
						type: 'number',
						unit: '%',
						placeholder: '请输入湿度',
						value: ''
					}
				)
				break
			case 'air_breaker':
				fields.push({
					label: '空开容量',
					type: 'text',
					unit: 'A',
					placeholder: '请输入空开容量',
					value: ''
				})
				break
			case 'rectifier_capacity':
				fields.push({
					label: '整流器容量',
					type: 'text',
					unit: 'A',
					placeholder: '请输入整流器容量',
					value: ''
				})
				break
			
			// 通用数据字段 - 对于未明确定义的检查项，如果需要数据输入，提供通用字段
			default:
				if (item.required_type === 'data' || item.required_type === 'both') {
					fields.push({
						label: '检查结果',
						type: 'text',
						unit: '',
						placeholder: '请输入检查结果',
						value: ''
					})
				}
				break
		}
		
		// 从已有数据中恢复值
		if (item.data_value && item.data_value.length > 0) {
			item.data_value.forEach(dataItem => {
				const field = fields.find(f => f.label === dataItem.field_name)
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
				categoryMap.set(item.category_id, {
					id: item.category_id,
					name: item.category_name || item.category_id
				})
			}
		})
		
		categories.value = Array.from(categoryMap.values())
	}
	
	const switchCategory = (categoryId) => {
		currentCategory.value = categoryId
	}
	
	const getCategoryCount = (categoryId) => {
		return checkItems.value.filter(item => item.category_id === categoryId).length
	}
	
	// 检查小区是否已绑定设备
	const isCellBound = (item) => {
		if (!item.sector_id) return true // 站点级检查项不需要绑定
		
		// 检查同一小区的任意检查项是否已绑定设备
		const cellItems = checkItems.value.filter(checkItem => 
			checkItem.sector_id === item.sector_id && 
			checkItem.band === item.band
		)
		
		return cellItems.some(cellItem => cellItem.equipment_sn)
	}
	
	// 获取小区绑定的设备序列号
	const getCellEquipmentSn = (item) => {
		if (!item.sector_id) return null
		
		const cellItems = checkItems.value.filter(checkItem => 
			checkItem.sector_id === item.sector_id && 
			checkItem.band === item.band
		)
		
		const boundItem = cellItems.find(cellItem => cellItem.equipment_sn)
		return boundItem?.equipment_sn || null
	}

	const openCheckItem = async (item) => {
		// 如果是小区级检查项且该小区未绑定设备，先要求绑定设备
		if (item.sector_id && !isCellBound(item)) {
			const cellId = item.band ? `${item.sector_id}_${item.band}` : item.sector_id
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
						currentItem.value.equipment_sn = getCellEquipmentSn(item)
					}
				}
			})
		} else {
			// 正常打开检查项
			currentItem.value = { ...item }
			// 如果是小区级检查项，确保显示正确的绑定状态
			if (item.sector_id) {
				currentItem.value.equipment_sn = getCellEquipmentSn(item)
			}
		}
	}
	
	const closeItemModal = () => {
		currentItem.value = null
	}
	
	const takePhoto = async () => {
		// 显示操作选择弹窗
		uni.showActionSheet({
			itemList: [$t('common.takePhoto'), $t('common.selectFromAlbum')],
			success: async function (res) {
				const sourceType = res.tapIndex === 0 ? ['camera'] : ['album']
				const isCamera = res.tapIndex === 0
				
				try {
					// 如果是拍照，先获取GPS坐标
					let gpsData = { latitude: 0, longitude: 0, accuracy: 0, address: '' }
					
					if (isCamera) {
						uni.showLoading({ title: $t('inspection.gettingLocation') || 'Getting location...' })
						
				try {
					gpsData = await getHighAccuracyLocation()
					// 验证GPS坐标的有效性
					if (gpsData.latitude === 0 && gpsData.longitude === 0) {
						throw new Error($t('inspection.gpsFetchFailedShort') || 'GPS fetch failed')
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
								
								// 如果是拍照，添加水印
								if (isCamera) {
									console.log('拍照模式，添加GPS水印')
									
									// 显示水印添加加载提示
									uni.showLoading({
										title: $t('inspection.addingGpsWatermark') || 'Adding GPS watermark...',
										mask: true
									})
									
									try {
										const watermarkTool = getWatermarkTool()
										finalImagePath = await watermarkTool.addWatermark(
											finalImagePath,
											gpsData.latitude,
											gpsData.longitude,
											gpsData.address,
											userStore.userInfo?.username || ($t('inspection.unknownUser') || 'Unknown'),
											currentItem.value.item_name || ($t('inspection.inspectionItem') || 'Inspection Item')
										)
										console.log('水印添加成功，最终图片路径:', finalImagePath)
										
										// 隐藏加载提示
										uni.hideLoading()
										
									} catch (watermarkError) {
										console.warn('水印添加失败，使用原图:', watermarkError)
										
										// 隐藏加载提示
										uni.hideLoading()
										
										// 显示错误提示
										uni.showToast({
											title: $t('inspection.watermarkFailedUseOriginal') || 'Watermark failed, using original',
											icon: 'none',
											duration: 2000
										})
									}
								}
								
								// 创建照片对象
								const photo = {
									file_path: finalImagePath,
									taken_at: new Date().toISOString(),
									latitude: gpsData.latitude,
									longitude: gpsData.longitude,
									gps_accuracy: gpsData.accuracy,
									address: gpsData.address,
									has_watermark: isCamera,
									watermark_data: isCamera ? {
										timestamp: new Date().toISOString(),
										coordinates: `${gpsData.latitude},${gpsData.longitude}`,
										accuracy: gpsData.accuracy,
									inspector: userStore.userInfo?.username || ($t('inspection.unknownUser') || 'Unknown'),
									item_name: currentItem.value.item_name || ($t('inspection.inspectionItem') || 'Inspection Item')
									} : null
								}
								
								if (!currentItem.value.photos) {
									currentItem.value.photos = []
								}
								currentItem.value.photos.push(photo)
								
									uni.showToast({
										title: $t('inspection.photoAdded') || 'Photo added',
										icon: 'success'
									})
								
							} catch (processError) {
								console.error('照片处理失败:', processError)
									uni.showToast({
										title: $t('inspection.photoProcessFailed') || 'Photo processing failed',
										icon: 'error'
									})
							}
						},
						fail: (chooseError) => {
							console.error('选择照片失败:', chooseError)
								uni.showToast({
									title: $t('inspection.photoChooseFailed') || 'Select photo failed',
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
		const title = $t('inspection.gpsFetchFailedTitle') || 'GPS failed'
		const content = $t('inspection.gpsFetchFailedContent') || 'GPS fetch failed, cannot add location watermark. Check permission or move to better signal and retry.'

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
				title: $t('inspection.locationPermissionGranted') || 'Location permission enabled, please retry.',
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
				confirmText: allowSettings ? ($t('inspection.enableLocationPermissionConfirm') || 'Open settings') : ($t('common.ok') || 'OK'),
				success: (res) => {
					if (allowSettings && res.confirm) {
						openAppLocationSettings()
					}
					resolve()
				},
				fail: () => resolve()
			}

			if (allowSettings) {
				modalOptions.cancelText = $t('common.cancel') || 'Cancel'
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

	// 使用原生插件的GPS高精度定位函数
	const getHighAccuracyLocation = () => {
		return new Promise((resolve, reject) => {
			try {
				console.log('使用原生插件获取高精度定位...')
				
				// 获取原生定位插件
				const locationPlugin = uni.requireNativePlugin('my-location-plugin')
				
				if (!locationPlugin) {
					throw new Error('原生定位插件未加载')
				}
				
				// 调用插件的异步定位方法
				locationPlugin.getLocationWithAddress((result) => {
					console.log('原生插件定位结果:', result)
					
					// 解析结果
					let parsedResult = result
					if (typeof result === 'string') {
						try {
							parsedResult = JSON.parse(result)
						} catch (parseError) {
							console.error('解析原生插件结果失败:', parseError)
							reject(new Error('解析原生插件结果失败'))
							return
						}
					}
					
					if (parsedResult && parsedResult.success && parsedResult.data) {
						const data = parsedResult.data
						const address = parsedResult.address
						
						// 构建地址字符串
						let addressString = ''
						if (address && typeof address === 'object') {
							const addressParts = [
								address.country,
								address.province,
								address.city,
								address.district,
								address.street,
								address.streetNum
							].filter(part => part && part.trim())
							
							if (addressParts.length > 0) {
								addressString = addressParts.join('')
							}
						}
						
						resolve({
							latitude: data.latitude,
							longitude: data.longitude,
							accuracy: data.accuracy || 0,
							address: addressString,
							provider: 'native-plugin'
						})
					} else {
						reject(new Error(parsedResult?.message || '原生插件定位失败'))
					}
				})
				
			} catch (error) {
				console.error('原生插件定位调用失败:', error)
				reject(error)
			}
		})
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
	
	// 获取水印工具
	const getWatermarkTool = () => {
		return {
			addWatermark: async (imagePath, latitude, longitude, address, inspector, itemName) => {
				try {
					console.log('使用增强GPS地址水印功能')
					
					// 先获取图片信息并设置canvas尺寸
					const imageInfo = await new Promise((resolve, reject) => {
						uni.getImageInfo({
							src: imagePath,
							success: resolve,
							fail: reject
						})
					})
					
					// 更新canvas尺寸
					canvasWidth.value = imageInfo.width
					canvasHeight.value = imageInfo.height
					console.log('设置Canvas尺寸:', imageInfo.width, imageInfo.height)
					
					// 等待DOM更新
					await new Promise(resolve => setTimeout(resolve, 100))
					
					// 导入增强水印工具
					const { watermarkTool } = await import('@/utils/watermark.js')
					
					// 准备水印数据，尝试多种站点名称获取方式
					const siteName = inspectionData.value?.site_name || 
									 inspectionData.value?.site?.site_name || 
									 inspectionData.value?.work_order?.site_name ||
									 '检查站点'
					
					const watermarkData = {
						inspector: inspector || userStore.userInfo?.username || '检查员',
						checkItem: itemName || currentItem.value?.item_name || '检查项',
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
					
					// 使用新的增强水印功能，使用页面中的canvas
					const watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, watermarkData, {
						showAddressDetails: true,
						showPOI: false,
						canvasId: 'watermarkCanvas'  // 使用页面中已有的canvas
					})
					
					console.log('增强水印添加完成:', watermarkedPath)
					return watermarkedPath
					
				} catch (error) {
					console.error('增强水印失败，使用原方案:', error)
					
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
								
								// 更新canvas尺寸
								canvasWidth.value = imgWidth
								canvasHeight.value = imgHeight
								
								console.log('兜底方案更新Canvas尺寸:', imgWidth, imgHeight)
								
								// 等待DOM更新后再绘制
								setTimeout(() => {
									// 重新创建canvas上下文
									const ctx = uni.createCanvasContext('watermarkCanvas')
									
									// 设置canvas尺寸并绘制图片
									ctx.drawImage(imagePath, 0, 0, imgWidth, imgHeight)
								
								// 添加水印文字
								const watermarkText = [
									`时间: ${new Date().toLocaleString('zh-CN')}`,
									`坐标: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
									`地址: ${address || '获取地址失败'}`,
									`检查员: ${inspector}`,
									`检查项: ${itemName}`
								]
								
									// 设置水印样式
									ctx.setFillStyle('rgba(0, 0, 0, 0.7)')
									ctx.fillRect(10, imgHeight - 140, imgWidth - 20, 130)
									
									ctx.setFillStyle('#ffffff')
									ctx.setFontSize(18)
									
									// 绘制水印文字
									watermarkText.forEach((text, index) => {
										ctx.fillText(text, 20, imgHeight - 115 + index * 25)
									})
								
									// 导出处理后的图片
									ctx.draw(false, () => {
										uni.canvasToTempFilePath({
											canvasId: 'watermarkCanvas',
											destWidth: imgWidth,
											destHeight: imgHeight,
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
	
	const previewPhoto = (photo) => {
		const imageUrl = buildImageUrl(photo.file_path)
		uni.previewImage({
			urls: [imageUrl],
			current: imageUrl
		})
	}
	
	const deletePhoto = (index) => {
		uni.showModal({
			title: $t('inspection.confirmDeleteTitle') || 'Confirm Delete',
			content: $t('inspection.confirmDeleteContent') || 'Delete this photo?',
			success: (res) => {
				if (res.confirm) {
					currentItem.value.photos.splice(index, 1)
				}
			}
		})
	}
	
	const onDataChange = () => {
		// 验证数据
		validateCurrentItem()
	}
	
	const onNotesChange = () => {
		// 备注变化处理
	}
	
	const validateCurrentItem = () => {
		if (!currentItem.value || !currentItem.value.dataFields) return
		
		const validationResult = {
			valid: true,
			errors: []
		}
		
		currentItem.value.dataFields.forEach(field => {
			if (!field.value) return
			
			const value = parseFloat(field.value)
			
			if (field.type === 'number') {
				if (isNaN(value)) {
					validationResult.valid = false
					validationResult.errors.push(`${field.label}必须为数字`)
					return
				}
				
				if (field.min !== undefined && value < field.min) {
					validationResult.valid = false
					validationResult.errors.push(`${field.label}不能小于${field.min}${field.unit}`)
				}
				
				if (field.max !== undefined && value > field.max) {
					validationResult.valid = false
					validationResult.errors.push(`${field.label}不能大于${field.max}${field.unit}`)
				}
			}
		})
		
		currentItem.value.validation_result = validationResult
	}
	
	const saveCurrentItem = async () => {
		// 小区级检查项必须先绑定设备，防止误保存
		if (currentItem.value?.sector_id && !currentItem.value?.equipment_sn) {
			uni.showModal({
				title: $t('inspection.needBindTitle') || '需要绑定设备',
				content: $t('inspection.needBindContent') || '需要先绑定设备才能进行检查，是否现在扫码绑定？',
				confirmText: $t('inspection.scanBindButton') || '扫码绑定',
				cancelText: $t('inspection.laterBindButton') || '稍后绑定',
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
			const dataValue = currentItem.value.dataFields?.map(field => ({
				field_name: field.label,
				value: field.value,
				unit: field.unit
			})).filter(item => item.value) || []
			
			// 确定状态
			let status = 'pending'
			const hasRequiredPhotos = currentItem.value.required_type === 'data' || 
									 (currentItem.value.photos && currentItem.value.photos.length > 0)
			const hasRequiredData = currentItem.value.required_type === 'photo' || 
								   dataValue.length > 0
			
			if (currentItem.value.required_type === 'both') {
				if (hasRequiredPhotos && hasRequiredData) {
					status = currentItem.value.validation_result?.valid !== false ? 'completed' : 'failed'
				} else {
					status = 'in_progress'
				}
			} else if (currentItem.value.required_type === 'photo') {
				status = hasRequiredPhotos ? 'completed' : 'pending'
			} else if (currentItem.value.required_type === 'data') {
				status = hasRequiredData ? 
					(currentItem.value.validation_result?.valid !== false ? 'completed' : 'failed') : 'pending'
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
				uni.showLoading({ title: '上传照片中...' })
				
				try {
					for (const photo of currentItem.value.photos) {
						console.log('检查照片路径:', photo.file_path)
						// 上传所有照片（可能是新拍摄的临时文件）
						// UniApp的临时文件路径通常包含 temp、tmp、_tmp_ 等标识
						if (photo.file_path && (
							photo.file_path.includes('temp') || 
							photo.file_path.includes('tmp') ||
							photo.file_path.includes('_tmp_') ||
							photo.file_path.includes('wxfile://') ||
							!photo.uploaded // 如果有uploaded标记，则跳过已上传的
						)) {
							console.log('开始上传照片:', photo.file_path)
							
							// 将参数分解为单独的字段，适配后端Form参数接收方式
							const photoData = {
								check_item_id: currentItem.value.id,
								gps_latitude: photo.latitude,
								gps_longitude: photo.longitude,
								gps_accuracy: photo.gps_accuracy,
								has_watermark: photo.has_watermark || false
								// 其他复杂数据暂时不传，后端会自动处理
							}
							
							console.log('照片上传数据:', photoData)
							
							const uploadResult = await inspectionStore.uploadPhoto(
								inspectionId.value,
								photo.file_path,
								photoData
							)
							
							console.log('照片上传结果:', uploadResult)
							
							if (!uploadResult.success) {
								throw new Error(`照片上传失败: ${uploadResult.error}`)
							}
							
							// 标记为已上传
							photo.uploaded = true
							
						} else {
							console.log('跳过照片（已上传或非临时文件）:', photo.file_path)
						}
					}
				} catch (photoError) {
					console.error('照片上传失败:', photoError)
					uni.hideLoading()
					uni.showToast({
						title: `照片上传失败: ${photoError.message}`,
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
				// 更新本地数据
				const itemIndex = checkItems.value.findIndex(item => item.id === currentItem.value.id)
				if (itemIndex > -1) {
					checkItems.value[itemIndex] = {
						...checkItems.value[itemIndex],
						...currentItem.value,
						...updateData
					}
				}
				
				// 更新检查进度
				await updateInspectionProgress()
				
				uni.showToast({
					title: '保存成功',
					icon: 'success'
				})
				
				closeItemModal()
			}
			
		} catch (error) {
			console.error('保存检查项失败:', error)
			uni.showToast({
				title: '保存失败',
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
					title: '草稿已保存',
					icon: 'success'
				})
			}
			
		} catch (error) {
			console.error('保存草稿失败:', error)
			uni.showToast({
				title: '保存失败',
				icon: 'error'
			})
		} finally {
			saving.value = false
		}
	}
	
	const submitInspection = async () => {
		if (!canSubmit.value) {
			uni.showModal({
				title: $t('common.hint') || 'Hint',
				content: $t('inspection.pleaseCompleteAll') || 'Please complete all required inspection items before submitting',
				showCancel: false
			})
			return
		}
		
		uni.showModal({
			title: $t('inspection.confirmSubmitTitle') || 'Confirm Submit',
			content: $t('inspection.confirmSubmitContent') || 'After submission it cannot be modified. Submit?',
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
					title: '提交成功',
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
				title: '提交失败',
				icon: 'error'
			})
		} finally {
			submitting.value = false
		}
	}
	
	const saveInspection = async () => {
		await saveDraft()
	}
	
	const goBack = () => {
		uni.navigateBack()
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
	
	// 扫码绑定设备功能
	const scanEquipmentForBinding = async (item = null) => {
		const targetItem = item || currentItem.value
		if (!targetItem || !targetItem.sector_id) {
			uni.showToast({
				title: $t('inspection.invalidCheckItem') || 'Invalid check item',
				icon: 'none'
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
				title: $t('inspection.validatingEquipment') || 'Validating device...',
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
					throw new Error(checkResponse.data?.detail || ($t('inspection.equipmentValidateFailed') || 'Device validation failed'))
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
						title: '绑定冲突',
						content: bindResponse.data?.detail || `设备 ${parsedBarcode.sn} 已绑定至其他小区，请先解绑后再操作`,
						showCancel: false
					})
				}
				if (bindResponse.statusCode === 403) {
					uni.hideLoading()
					return uni.showToast({ title: bindResponse.data?.detail || '设备未被当前用户领料', icon: 'none', duration: 3000 })
				}
				if (bindResponse.statusCode === 400) {
					uni.hideLoading()
					return uni.showToast({ title: bindResponse.data?.detail || '设备绑定失败', icon: 'none', duration: 3000 })
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
					uni.showModal({
						title: $t('inspection.bindSuccessTitle'),
						content: $t('inspection.bindSuccessContent') || `设备 ${parsedBarcode.sn} 已成功绑定到小区 ${targetItem.band ? `${targetItem.sector_id}_${targetItem.band}` : targetItem.sector_id}`,
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
					throw new Error(bindResponse.data?.detail || ($t('inspection.bindFailed') || 'Bind failed'))
				}
				
			} catch (error) {
				uni.hideLoading()
				console.error('设备绑定失败:', error)
				uni.showToast({
					title: error.message || ($t('inspection.bindFailed') || 'Bind failed'),
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
		if (!currentItem.value || !currentItem.value.equipment_sn) {
			return
		}
		
		uni.showModal({
			title: $t('inspection.unbindConfirmTitle') || 'Confirm Unbind',
			content: ($t('inspection.unbindConfirmContent') || 'Unbind device {sn}?').replace('{sn}', currentItem.value.equipment_sn),
			success: async (res) => {
				if (res.confirm) {
					try {
						uni.showLoading({
							title: '解绑中...',
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
								title: '解绑成功',
								icon: 'success'
							})
						} else {
							throw new Error('解绑失败')
						}
						
					} catch (error) {
						uni.hideLoading()
						console.error('解绑失败:', error)
						uni.showToast({
							title: '解绑失败',
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
		background: #f5f5f5;
		display: flex;
		flex-direction: column;
		overflow-x: hidden;
		box-sizing: border-box;
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
	
	.back-button {
		width: 60rpx;
		height: 60rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 30rpx;
		background: rgba(255, 255, 255, 0.2);
	}
	
	.back-icon {
		font-size: 36rpx;
		color: white;
	}
	
	.navbar-title {
		font-size: 32rpx;
		font-weight: bold;
		flex: 1;
		text-align: center;
	}
	
	.navbar-actions {
		width: 60rpx;
		display: flex;
		justify-content: flex-end;
	}
	
	.save-button {
		width: 60rpx;
		height: 60rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 30rpx;
		background: rgba(255, 255, 255, 0.2);
	}
	
	.save-icon {
		font-size: 32rpx;
		color: white;
	}
	
	/* 检查信息 */
	.inspection-info {
		background: white;
		margin: 20rpx;
		border-radius: 20rpx;
		padding: 30rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
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
		background: linear-gradient(135deg, #f97316, #fb923c);
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
		display: inline-block;
		padding: 25rpx 30rpx;
		margin: 0 5rpx;
		border-radius: 15rpx;
		transition: all 0.3s ease;
	}
	
	.tab-item.active {
		background: #28a745;
		color: white;
	}
	
	.tab-text {
		font-size: 26rpx;
		white-space: nowrap;
	}
	
	/* 检查内容 */
	.checklist-content {
		flex: 1;
		padding: 0 20rpx;
		margin-bottom: 120rpx;
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
	
	.section-title {
		font-size: 30rpx;
		font-weight: bold;
		color: #333;
	}
	
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
		background: linear-gradient(135deg, #f97316, #fb923c);
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
		background: white;
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
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.modal-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		flex: 1;
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
		display: flex;
		align-items: center;
		gap: 10rpx;
		padding: 15rpx 20rpx;
		background: #007bff;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 24rpx;
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
		border-left: 4rpx solid #f97316;
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
		color: #f97316;
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
	
	.photo-thumb {
		width: 100%;
		height: 200rpx;
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
	
	/* 数据表单 */
	.data-form {
		display: flex;
		flex-direction: column;
		gap: 25rpx;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
	}
	
	.form-item {
		display: flex;
		align-items: stretch;
		gap: 15rpx;
		width: 100%;
		max-width: 100%;
		min-width: 0;
		box-sizing: border-box;
		overflow: hidden;
		min-height: 80rpx;
	}
	
	.form-label {
		font-size: 28rpx;
		color: #333;
		min-width: 120rpx;
		max-width: 150rpx;
		flex-shrink: 0;
		word-break: break-word;
		overflow-wrap: break-word;
		box-sizing: border-box;
		display: flex;
		align-items: center;
		height: 80rpx;
	}
	
	.form-input {
		flex: 1;
		padding: 24rpx;
		border: 2rpx solid #e9ecef;
		border-radius: 12rpx;
		font-size: 28rpx;
		background: #f8f9fa;
		min-width: 0;
		max-width: 100%;
		box-sizing: border-box;
		min-height: 80rpx;
		height: 80rpx;
		line-height: 1.4;
		cursor: text;
	}
	
	.form-input:focus {
		border-color: #28a745;
		background: white;
		outline: none;
		box-shadow: 0 0 0 3rpx rgba(40, 167, 69, 0.1);
		transform: none;
	}
	
	.form-unit {
		font-size: 26rpx;
		color: #666;
		min-width: 40rpx;
		display: flex;
		align-items: center;
		height: 80rpx;
		flex-shrink: 0;
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
	.modal-actions {
		display: flex;
		gap: 20rpx;
		padding: 30rpx;
		border-top: 1rpx solid #f0f0f0;
	}
	
	.modal-btn {
		flex: 1;
		padding: 25rpx;
		border-radius: 15rpx;
		font-size: 30rpx;
		border: none;
	}
	
	.cancel-btn {
		background: #6c757d;
		color: white;
	}
	
	.save-btn {
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
	}
	
	.save-btn:disabled {
		background: #adb5bd;
	}
	
	/* 设备绑定相关样式 */
	.equipment-binding {
		font-size: 22rpx;
		margin-top: 4rpx;
		
		&.pending {
			color: #f59e0b;
		}
		
		&:not(.pending) {
			color: #10b981;
		}
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
	
	.unbind-btn {
		background: #fee2e2;
		color: #dc2626;
		border: 1rpx solid #fca5a5;
		padding: 12rpx 20rpx;
		border-radius: 8rpx;
		font-size: 24rpx;
	}
	
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
	
	.bind-btn {
		background: linear-gradient(135deg, #f97316, #ea580c);
		color: white;
		border: none;
		padding: 12rpx 20rpx;
		border-radius: 8rpx;
		font-size: 24rpx;
		display: flex;
		align-items: center;
		gap: 8rpx;
	}
	
	.btn-icon {
		font-size: 24rpx;
	}
</style>
