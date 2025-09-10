<template>
	<view class="checklist-container">
		<!-- 导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="back-button" @click="goBack">
					<text class="back-icon">←</text>
				</view>
				<text class="navbar-title">{{ inspectionData?.site_name || '检查清单' }}</text>
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
				<text class="info-label">站点:</text>
				<text class="info-value">{{ inspectionData?.site_name }}</text>
			</view>
			<view class="info-row">
				<text class="info-label">类型:</text>
				<text class="info-value">{{ getInspectionTypeText(inspectionData?.inspection_type) }}</text>
			</view>
			<view class="info-row">
				<text class="info-label">进度:</text>
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
					<text class="tab-text">全部 ({{ checkItems.length }})</text>
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
					<text class="section-count">{{ section.items.length }}项</text>
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
							<text class="item-id" v-if="item.sector_id">扇区 {{ item.sector_id }}</text>
						</view>
						<view class="item-actions">
							<text class="required-badge" v-if="item.required_type === 'both'">照片+数据</text>
							<text class="required-badge" v-else-if="item.required_type === 'photo'">照片</text>
							<text class="required-badge" v-else-if="item.required_type === 'data'">数据</text>
							<text class="action-arrow">›</text>
						</view>
					</view>
					
					<view class="item-details" v-if="item.status !== 'pending'">
						<view class="detail-row" v-if="item.checked_at">
							<text class="detail-label">检查时间:</text>
							<text class="detail-value">{{ formatDateTime(item.checked_at) }}</text>
						</view>
						
						<view class="detail-row" v-if="item.photos && item.photos.length > 0">
							<text class="detail-label">照片:</text>
							<text class="detail-value">{{ item.photos.length }}张</text>
						</view>
						
						<view class="detail-row" v-if="item.data_value && item.data_value.length > 0">
							<text class="detail-label">数据:</text>
							<text class="detail-value">{{ item.data_value.length }}项</text>
						</view>
						
						<view class="detail-row" v-if="item.validation_result && !item.validation_result.valid">
							<text class="detail-label">验证结果:</text>
							<text class="detail-value error">{{ item.validation_result.errors.join(', ') }}</text>
						</view>
					</view>
				</view>
			</view>
			
			<!-- 空状态 -->
			<view class="empty-state" v-if="filteredCheckItems.length === 0">
				<text class="empty-icon">📝</text>
				<text class="empty-title">暂无检查项</text>
				<text class="empty-desc">请等待检查模板加载</text>
			</view>
		</scroll-view>
		
		<!-- 底部操作栏 -->
		<view class="bottom-actions">
			<button 
				class="action-btn draft-btn" 
				@click="saveDraft"
				:disabled="saving"
			>
				{{ saving ? '保存中...' : '保存草稿' }}
			</button>
			
			<button 
				class="action-btn submit-btn" 
				@click="submitInspection"
				:disabled="!canSubmit || submitting"
			>
				{{ submitting ? '提交中...' : '提交检查' }}
			</button>
		</view>
		
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
					<!-- 检查项基本信息 -->
					<view class="modal-section">
						<text class="section-label">基本信息</text>
						<view class="info-grid">
							<view class="grid-item">
								<text class="grid-label">检查类型:</text>
								<text class="grid-value">{{ getRequiredTypeText(currentItem.required_type) }}</text>
							</view>
							<view class="grid-item" v-if="currentItem.sector_id">
								<text class="grid-label">扇区:</text>
								<text class="grid-value">{{ currentItem.sector_id }}</text>
							</view>
							<view class="grid-item">
								<text class="grid-label">状态:</text>
								<text class="grid-value" :class="getStatusClass(currentItem.status)">
									{{ getStatusText(currentItem.status) }}
								</text>
							</view>
						</view>
					</view>
					
					<!-- 照片部分 -->
					<view class="modal-section" v-if="['photo', 'both'].includes(currentItem.required_type)">
						<view class="section-header">
							<text class="section-label">照片 ({{ currentItem.photos?.length || 0 }})</text>
							<button class="add-photo-btn" @click="takePhoto">
								<text class="btn-icon">📷</text>
								<text class="btn-text">拍照</text>
							</button>
						</view>
						
						<view class="photo-grid" v-if="currentItem.photos && currentItem.photos.length > 0">
							<view 
								class="photo-item" 
								v-for="(photo, index) in currentItem.photos" 
								:key="index"
								@click="previewPhoto(photo)"
							>
								<image class="photo-thumb" :src="photo.file_path" mode="aspectFill"></image>
								<view class="photo-info">
									<text class="photo-time">{{ formatTime(photo.taken_at) }}</text>
									<view class="photo-actions">
										<text class="delete-photo" @click.stop="deletePhoto(index)">🗑️</text>
									</view>
								</view>
							</view>
						</view>
						
						<view class="no-photos" v-else>
							<text class="no-photos-text">暂无照片，点击拍照按钮添加</text>
						</view>
					</view>
					
					<!-- 数据填写部分 -->
					<view class="modal-section" v-if="['data', 'both'].includes(currentItem.required_type)">
						<text class="section-label">数据填写</text>
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
								<text class="result-title">验证结果</text>
								<text 
									class="result-status"
									:class="currentItem.validation_result.valid ? 'valid' : 'invalid'"
								>
									{{ currentItem.validation_result.valid ? '✅ 通过' : '❌ 不通过' }}
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
						<text class="section-label">备注</text>
						<textarea 
							class="note-textarea"
							placeholder="添加检查备注..."
							v-model="currentItem.notes"
							@input="onNotesChange"
						></textarea>
					</view>
				</scroll-view>
				
				<view class="modal-actions">
					<button class="modal-btn cancel-btn" @click="closeItemModal">取消</button>
					<button class="modal-btn save-btn" @click="saveCurrentItem" :disabled="savingItem">
						{{ savingItem ? '保存中...' : '保存' }}
					</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	
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
		if (options.inspectionId) {
			inspectionId.value = options.inspectionId
			loadInspectionData()
		}
	})
	
	// 方法
	const loadInspectionData = async () => {
		try {
			// 加载检查数据
			const inspectionResult = await inspectionStore.getInspectionDetail(inspectionId.value)
			if (inspectionResult.success) {
				inspectionData.value = inspectionResult.data
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
				title: '加载失败',
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
	
	const openCheckItem = (item) => {
		currentItem.value = { ...item }
	}
	
	const closeItemModal = () => {
		currentItem.value = null
	}
	
	const takePhoto = () => {
		uni.chooseImage({
			count: 1,
			sourceType: ['camera'],
			success: (res) => {
				// 模拟上传照片
				const photo = {
					file_path: res.tempFilePaths[0],
					taken_at: new Date().toISOString(),
					latitude: 0,
					longitude: 0,
					gps_accuracy: 5.0
				}
				
				if (!currentItem.value.photos) {
					currentItem.value.photos = []
				}
				currentItem.value.photos.push(photo)
				
				uni.showToast({
					title: '照片已添加',
					icon: 'success'
				})
			},
			fail: (error) => {
				console.error('拍照失败:', error)
				uni.showToast({
					title: '拍照失败',
					icon: 'error'
				})
			}
		})
	}
	
	const previewPhoto = (photo) => {
		uni.previewImage({
			urls: [photo.file_path],
			current: photo.file_path
		})
	}
	
	const deletePhoto = (index) => {
		uni.showModal({
			title: '确认删除',
			content: '确定要删除这张照片吗？',
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
				title: '提示',
				content: '请完成所有必需的检查项后再提交',
				showCancel: false
			})
			return
		}
		
		uni.showModal({
			title: '确认提交',
			content: '提交后将无法修改，确定要提交检查吗？',
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
			installation: '安装检查',
			opening: '新站点设备安装',
			maintenance: '维护检查'
		}
		return typeMap[type] || '检查'
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
			pending: '待处理',
			in_progress: '进行中',
			completed: '已完成',
			failed: '失败',
			skipped: '跳过'
		}
		return statusMap[status] || '未知'
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
</script>

<style scoped>
	.checklist-container {
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
	}
	
	.check-section {
		margin-bottom: 30rpx;
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
		padding: 30rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
		transition: transform 0.2s ease;
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
		gap: 20rpx;
	}
	
	.item-status {
		flex-shrink: 0;
	}
	
	.status-icon {
		font-size: 36rpx;
	}
	
	.item-info {
		flex: 1;
	}
	
	.item-name {
		font-size: 30rpx;
		font-weight: 500;
		color: #333;
		display: block;
		margin-bottom: 8rpx;
	}
	
	.item-id {
		font-size: 24rpx;
		color: #007bff;
	}
	
	.item-actions {
		display: flex;
		align-items: center;
		gap: 15rpx;
	}
	
	.required-badge {
		font-size: 22rpx;
		padding: 6rpx 12rpx;
		background: #e9ecef;
		color: #495057;
		border-radius: 12rpx;
	}
	
	.action-arrow {
		font-size: 32rpx;
		color: #ccc;
	}
	
	.item-details {
		margin-top: 20rpx;
		padding-top: 20rpx;
		border-top: 1rpx solid #f0f0f0;
	}
	
	.detail-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10rpx;
	}
	
	.detail-label {
		font-size: 24rpx;
		color: #666;
	}
	
	.detail-value {
		font-size: 24rpx;
		color: #333;
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
	}
	
	.modal-section {
		margin-bottom: 40rpx;
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
	}
	
	.grid-item {
		display: flex;
		flex-direction: column;
		gap: 8rpx;
	}
	
	.grid-label {
		font-size: 24rpx;
		color: #666;
	}
	
	.grid-value {
		font-size: 26rpx;
		color: #333;
		font-weight: 500;
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
	
	/* 照片网格 */
	.photo-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200rpx, 1fr));
		gap: 15rpx;
	}
	
	.photo-item {
		position: relative;
		border-radius: 12rpx;
		overflow: hidden;
		background: #f8f9fa;
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
	}
	
	.form-item {
		display: flex;
		align-items: center;
		gap: 15rpx;
	}
	
	.form-label {
		font-size: 26rpx;
		color: #333;
		min-width: 120rpx;
	}
	
	.form-input {
		flex: 1;
		padding: 20rpx;
		border: 2rpx solid #e9ecef;
		border-radius: 12rpx;
		font-size: 26rpx;
		background: #f8f9fa;
	}
	
	.form-input:focus {
		border-color: #28a745;
		background: white;
	}
	
	.form-unit {
		font-size: 24rpx;
		color: #666;
		min-width: 40rpx;
	}
	
	/* 验证结果 */
	.validation-result {
		margin-top: 20rpx;
		padding: 20rpx;
		border-radius: 12rpx;
		background: #f8f9fa;
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
	}
	
	.error-item {
		font-size: 24rpx;
		color: #dc3545;
	}
	
	/* 备注 */
	.note-textarea {
		width: 100%;
		min-height: 120rpx;
		padding: 20rpx;
		border: 2rpx solid #e9ecef;
		border-radius: 12rpx;
		font-size: 26rpx;
		background: #f8f9fa;
		resize: vertical;
	}
	
	.note-textarea:focus {
		border-color: #28a745;
		background: white;
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
</style>