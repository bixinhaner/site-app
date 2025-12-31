<template>
	<view class="camera-container" :key="languageStore.currentLocale">
		<!-- 状态栏占位 -->
		<view class="status-bar"></view>
		
		<!-- 相机视图 -->
		<camera 
			class="camera-view"
			:device-position="cameraPosition"
			:flash="flashMode"
			@error="onCameraError"
			@scancode="onScanCode"
		>
			<!-- 顶部工具栏 -->
			<cover-view class="top-toolbar">
				<cover-view class="toolbar-left">
					<cover-view class="tool-btn back-btn" @tap="goBack">
						<cover-text class="btn-icon uniicon-font">&#xe6b9;</cover-text>
					</cover-view>
				</cover-view>
				
				<cover-view class="toolbar-center">
					<cover-text class="toolbar-title">{{ getDisplayItemName(getI18nText(checkItem?.item_name, checkItem?.item_name_i18n)) || $t('inspection.photoInspection') }}</cover-text>
					<cover-text class="toolbar-subtitle" v-if="currentSite">{{ currentSite.site_name }}</cover-text>
				</cover-view>
				
				<cover-view class="toolbar-right">
					<cover-view class="tool-btn flash-btn" @tap="toggleFlash">
						<cover-text class="btn-icon">{{ flashMode === 'on' ? '💡' : '🔦' }}</cover-text>
					</cover-view>
					<cover-view class="tool-btn switch-btn" @tap="switchCamera">
						<cover-text class="btn-icon">🔄</cover-text>
					</cover-view>
				</cover-view>
			</cover-view>
			
			<!-- GPS信息显示 -->
			<cover-view class="gps-overlay" v-if="gpsInfo.latitude">
				<cover-text class="gps-text">📍 {{ formatGPS(gpsInfo) }}</cover-text>
				<cover-text class="gps-accuracy">📊 {{ $t('inspection.accuracy') }}: {{ gpsInfo.accuracy }}m</cover-text>
				<cover-text class="gps-address" v-if="gpsInfo.address">🏠 {{ gpsInfo.address }}</cover-text>
				<cover-text class="gps-time">🕐 {{ currentTime }}</cover-text>
			</cover-view>
			
			<!-- 拍照要求提示 -->
			<cover-view class="requirement-overlay" v-if="checkItem?.photo_requirements">
				<cover-view class="requirement-card">
					<cover-text class="requirement-title">📸 {{ $t('inspection.photoRequirementsTitle') }}</cover-text>
					<cover-text class="requirement-desc">{{ checkItem.photo_requirements.description }}</cover-text>
					<cover-view class="requirement-list" v-if="checkItem.photo_requirements.include">
						<cover-text 
							class="requirement-item"
							v-for="item in checkItem.photo_requirements.include"
							:key="item"
						>• {{ item }}</cover-text>
					</cover-view>
				</cover-view>
			</cover-view>
			
			<!-- 底部控制栏 -->
			<cover-view class="bottom-controls">
				<!-- GPS状态指示 -->
				<cover-view class="gps-status" :class="getGpsStatusClass()">
					<cover-text class="gps-icon">📡</cover-text>
					<cover-text class="gps-status-text">{{ gpsStatusText }}</cover-text>
				</cover-view>
				
				<!-- 拍照按钮 -->
				<cover-view class="capture-group">
					<cover-view class="capture-ring">
						<cover-view 
							class="capture-btn" 
							:class="{ disabled: !canTakePhoto }"
							@tap="takePhoto"
						>
							<cover-text class="capture-icon">📸</cover-text>
						</cover-view>
					</cover-view>
				</cover-view>
				
				<!-- 相册按钮（禁用状态） -->
				<cover-view class="gallery-btn disabled" @tap="showGalleryDisabledTip">
					<cover-text class="gallery-icon">🖼️</cover-text>
					<cover-text class="gallery-text">{{ $t('inspection.album') }}</cover-text>
					<cover-view class="disabled-overlay">
						<cover-text class="disabled-text">{{ $t('inspection.disabled') }}</cover-text>
					</cover-view>
				</cover-view>
			</cover-view>
			
			<!-- 拍照进度提示 -->
			<cover-view class="capture-progress" v-if="isCapturing">
				<cover-text class="progress-text">📸 {{ $t('inspection.capturing') }}</cover-text>
				<cover-view class="progress-bar">
					<cover-view class="progress-fill" :style="{ width: captureProgress + '%' }"></cover-view>
				</cover-view>
			</cover-view>
		</camera>
		
		<!-- 隐藏的canvas用于水印处理 -->
		<canvas 
			v-if="canvasId" 
			:canvas-id="canvasId" 
			:style="{ 
				position: 'fixed', 
				top: '-9999px', 
				left: '-9999px',
				width: canvasWidth + 'px',
				height: canvasHeight + 'px'
			}"
		></canvas>
		
		<!-- 照片预览弹窗 -->
		<view class="photo-preview-modal" v-if="showPreview" @click="hidePreview">
			<view class="preview-container" @click.stop>
				<view class="preview-header">
					<text class="preview-title">{{ $t('inspection.photoPreview') }}</text>
					<button class="preview-close" @click="hidePreview">
						<uni-icons type="closeempty" size="20" color="#6b7280" />
					</button>
				</view>
				
				<view class="preview-content">
					<image :src="previewPhoto.path" mode="aspectFit" class="preview-image"></image>
					
					<!-- 照片信息 -->
					<view class="photo-info">
						<view class="info-row">
							<text class="info-label">{{ $t('inspection.gpsCoordinatesLabel') }}:</text>
							<text class="info-value">{{ formatGPS(previewPhoto.gps) }}</text>
						</view>
						<view class="info-row">
							<text class="info-label">{{ $t('inspection.shootTimeLabel') }}:</text>
							<text class="info-value">{{ previewPhoto.timestamp }}</text>
						</view>
						<view class="info-row">
							<text class="info-label">{{ $t('inspection.fileSizeLabel') }}:</text>
							<text class="info-value">{{ formatFileSize(previewPhoto.size) }}</text>
						</view>
						<view class="info-row" v-if="previewPhoto.gps.accuracy">
							<text class="info-label">{{ $t('inspection.gpsAccuracyLabel') }}:</text>
							<text class="info-value">{{ previewPhoto.gps.accuracy }}m</text>
						</view>
					</view>
				</view>
				
				<view class="preview-actions">
					<button class="action-btn retry-btn" @click="retakePhoto">{{ $t('inspection.retakePhoto') }}</button>
					<button class="action-btn confirm-btn" @click="confirmPhoto" :disabled="isUploading">
						{{ isUploading ? $t('messages.uploading') : $t('inspection.confirmUse') }}
					</button>
				</view>
			</view>
		</view>
		
		<!-- 上传进度提示 -->
		<view class="upload-progress-modal" v-if="showUploadProgress">
			<view class="upload-container">
				<view class="upload-icon">📤</view>
				<text class="upload-title">{{ $t('inspection.uploadingPhotoTitle') }}</text>
				<view class="upload-progress-bar">
					<view class="upload-progress-fill" :style="{ width: uploadProgress + '%' }"></view>
				</view>
				<text class="upload-text">{{ uploadProgress }}% ({{ uploadSpeed }})</text>
			</view>
		</view>
	</view>
</template>

<script>
export default {
	onLoad(options) {
		console.log('Camera页面onLoad接收参数:', options)
		// 这里会在组件setup之后被调用
		this.$nextTick(() => {
			if (this.setupOnLoad) {
				this.setupOnLoad(options)
			}
		})
	}
}
</script>

<script setup>
	import { ref, computed, onMounted, onUnmounted, getCurrentInstance } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useInspectionStore } from '@/stores/inspection'
	import { useOfflineStore } from '@/stores/offline'
	import { useLanguageStore } from '@/stores/language'
	import { watermarkTool } from '@/utils/watermark.js'
	import { watermarkConfig, securityUtils } from '@/config/watermark.js'
	import { getLocationMode, getLocationWithAddressStrategy } from '@/utils/locationStrategy.js'
	
	const userStore = useUserStore()
	const inspectionStore = useInspectionStore()
	const offlineStore = useOfflineStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	const t = (key, params = {}) => {
		// 依赖当前语言，确保切换语言后能更新显示
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
	
	// URL参数 (在UniApp中通过onLoad接收)
	const urlParams = ref({
		inspectionId: '',
		checkItemId: '',
		itemIndex: 0
	})
	
	// Props (保持兼容性)
	const props = defineProps({
		inspectionId: String,
		checkItemId: String,
		itemIndex: {
			type: Number,
			default: 0
		}
	})
	
	// 响应式数据
	const cameraPosition = ref('back') // back, front
	const flashMode = ref('off') // on, off, auto
	const gpsInfo = ref({
		latitude: null,
		longitude: null,
		accuracy: null,
		address: ''
	})
	const currentTime = ref('')
	const isCapturing = ref(false)
	const captureProgress = ref(0)
	const showPreview = ref(false)
	const previewPhoto = ref({})
	const isUploading = ref(false)
	const showUploadProgress = ref(false)
	const uploadProgress = ref(0)
	const uploadSpeed = ref('')
	const currentSite = ref(null)
	const checkItem = ref(null)
	const gpsWatcher = ref(null)
	const timeInterval = ref(null)
	
	// 水印相关状态
	const isProcessingWatermark = ref(false)
	const canvasId = ref(null)
	const canvasWidth = ref(0)
	const canvasHeight = ref(0)
	
	// 计算属性
	const canTakePhoto = computed(() => {
		// 需要GPS且GPS未获取时不能拍照
		if (checkItem.value?.photo_requirements?.gps_required && !gpsInfo.value.latitude) {
			return false
		}
		
		// 正在拍照时不能拍照
		if (isCapturing.value) {
			return false
		}
		
		// 正在处理水印时不能拍照
		if (isProcessingWatermark.value) {
			return false
		}
		
		return true
	})
	
	const gpsStatusText = computed(() => {
		if (!gpsInfo.value.latitude) {
			return t('messages.gettingLocation')
		}
		
		if (gpsInfo.value.accuracy > 10) {
			return t('messages.lowGPSAccuracy', { accuracy: gpsInfo.value.accuracy })
		}
		
		return t('messages.gpsAccuracyGood', { accuracy: gpsInfo.value.accuracy })
	})
	
	// 处理URL参数的函数
	const setupOnLoad = (options) => {
		console.log('Camera页面setup接收参数:', options)
		
		// 更新URL参数
		urlParams.value = {
			inspectionId: options.inspectionId || props.inspectionId || '',
			checkItemId: options.checkItemId || props.checkItemId || '',
			itemIndex: parseInt(options.itemIndex || props.itemIndex || '0')
		}
		
		console.log('解析后的参数:', urlParams.value)
		
		// 参数更新后重新加载检查项信息
		loadCheckItemInfo()
	}
	
	// 暴露setupOnLoad给外部script调用
	defineExpose({
		setupOnLoad
	})
	
	// Vue生命周期
	onMounted(() => {
		initCamera()
		loadCheckItemInfo()
		startGpsWatch()
		startTimeUpdate()
	})
	
	onUnmounted(() => {
		stopGpsWatch()
		stopTimeUpdate()
	})
	
	// 初始化方法
	
	const initCamera = async () => {
		try {
			// 检查相机权限
			const authResult = await uni.authorize({
				scope: 'scope.camera'
			})
			
			console.log('相机权限获取成功')
		} catch (error) {
			console.error('相机权限获取失败:', error)
			uni.showModal({
				title: t('inspection.cameraPermissionTitle'),
				content: t('inspection.cameraPermissionContent'),
				showCancel: false
			})
		}
	}
	
	const loadCheckItemInfo = async () => {
		try {
			const inspectionId = urlParams.value.inspectionId || props.inspectionId
			const checkItemId = urlParams.value.checkItemId || props.checkItemId
			
			if (inspectionId && checkItemId) {
				console.log('开始加载检查项信息:', { inspectionId, checkItemId })
				
				const result = await inspectionStore.getInspection(inspectionId)
				if (result.success) {
					const inspection = result.data
					currentSite.value = inspection.site
					
					// 查找检查项
					checkItem.value = inspection.check_items.find(
						item => item.id === checkItemId
					)
					
					console.log('检查项信息加载成功:', { 
						site: currentSite.value?.site_name, 
						checkItem: checkItem.value?.item_name 
					})
				} else {
					console.error('获取检查信息失败:', result.error)
				}
			} else {
				console.warn('缺少必要参数:', { inspectionId, checkItemId })
			}
		} catch (error) {
			console.error('加载检查项信息失败:', error)
		}
	}
	
	const startGpsWatch = async () => {
		const mode = getLocationMode()
		console.log('Camera 页面启动GPS监听，当前模式:', mode)

		if (mode === 'baidu') {
			// Baidu 模式下使用 uni 的持续定位能力
			getCurrentLocationWithUni()

			gpsWatcher.value = uni.onLocationChange((res) => {
				updateGpsInfoFromUni(res)
			})

			uni.startLocationUpdate({
				success: () => {
					console.log('开始位置更新 (Baidu 模式)')
				},
				fail: (error) => {
					console.error('开始位置更新失败:', error)
				}
			})
		} else {
			// 原生模式下使用定位策略获取一次位置（不启用 uni 持续监听）
			await getCurrentLocationWithStrategy()
		}
	}
	
	const stopGpsWatch = () => {
		if (gpsWatcher.value) {
			uni.offLocationChange(gpsWatcher.value)
			gpsWatcher.value = null
		}
		
		try {
			uni.stopLocationUpdate()
		} catch (error) {
			console.warn('停止位置更新失败:', error)
		}
	}
	
	const getCurrentLocationWithUni = () => {
		uni.getLocation({
			type: 'wgs84',
			altitude: true,
			success: (res) => {
				updateGpsInfoFromUni(res)
			},
			fail: (error) => {
				console.error('获取位置失败:', error)
				uni.showToast({
					title: t('messages.gpsLocationFailed'),
					icon: 'error'
				})
			}
		})
	}

	const updateGpsInfoFromUni = async (locationData) => {
		const lat = Number(locationData.latitude)
		const lon = Number(locationData.longitude)
		gpsInfo.value = {
			latitude: lat,
			longitude: lon,
			accuracy: Number(locationData.accuracy || 0),
			altitude: Number(locationData.altitude || 0),
			speed: Number(locationData.speed || 0),
			address: gpsInfo.value.address || ''
		}
	}

	const getCurrentLocationWithStrategy = async () => {
		try {
			console.log('Camera 页面通过定位策略获取当前位置...')
			const result = await getLocationWithAddressStrategy()
			console.log('Camera 页面定位策略结果:', result)

			if (!result || !result.success || !result.data) {
				console.warn('Camera 页面定位失败:', result?.message)
				return
			}

			const data = result.data
			const lat = Number(data.latitude)
			const lon = Number(data.longitude)
			let addressStr = ''

			const addressObj = result.address
			if (addressObj && typeof addressObj === 'object') {
				const parts = [
					addressObj.country,
					addressObj.province,
					addressObj.city,
					addressObj.district,
					addressObj.street,
					addressObj.streetNumber
				].filter(part => part && String(part).trim())
				if (parts.length > 0) {
					addressStr = parts.join('')
				}
			}

			gpsInfo.value = {
				latitude: lat,
				longitude: lon,
				accuracy: Number(data.accuracy || 0),
				altitude: Number(data.altitude || 0),
				speed: Number(data.speed || 0),
				address: addressStr
			}
		} catch (error) {
			console.error('Camera 页面通过定位策略获取位置失败:', error)
		}
	}
	
	const startTimeUpdate = () => {
		updateCurrentTime()
		timeInterval.value = setInterval(updateCurrentTime, 1000)
	}
	
	const stopTimeUpdate = () => {
		if (timeInterval.value) {
			clearInterval(timeInterval.value)
		}
	}
	
	const updateCurrentTime = () => {
		const now = new Date()
		const locale = languageStore.currentLocaleTag
		currentTime.value = now.toLocaleString(locale, {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		})
	}
	
	// 相机控制方法
	const toggleFlash = () => {
		const modes = ['off', 'on', 'auto']
		const currentIndex = modes.indexOf(flashMode.value)
		flashMode.value = modes[(currentIndex + 1) % modes.length]

		const modeText =
			flashMode.value === 'on'
				? t('inspection.flashOn')
				: flashMode.value === 'auto'
					? t('inspection.flashAuto')
					: t('inspection.flashOff')
		
		uni.showToast({
			title: t('inspection.flashModeToast', { mode: modeText }),
			icon: 'none'
		})
	}
	
	const switchCamera = () => {
		cameraPosition.value = cameraPosition.value === 'back' ? 'front' : 'back'

		const cameraText =
			cameraPosition.value === 'back' ? t('inspection.backCamera') : t('inspection.frontCamera')
		
		uni.showToast({
			title: t('inspection.switchCameraToast', { camera: cameraText }),
			icon: 'none'
		})
	}
	
	const takePhoto = async () => {
		if (!canTakePhoto.value) return
		
		// 检查GPS要求
		if (checkItem.value?.photo_requirements?.gps_required && !gpsInfo.value.latitude) {
			uni.showModal({
				title: t('inspection.gpsRequiredTitle'),
				content: t('inspection.gpsRequiredContent'),
				showCancel: false
			})
			return
		}
		
		// 检查GPS精度
		if (gpsInfo.value.accuracy > 20) {
			const confirmResult = await uni.showModal({
				title: t('inspection.gpsAccuracyLabel'),
				content: t('inspection.lowGpsAccuracyPrompt', { accuracy: gpsInfo.value.accuracy }),
				confirmText: t('inspection.continueTakePhoto'),
				cancelText: t('inspection.relocate')
			})
			
			if (!confirmResult.confirm) {
				getCurrentLocationFromNativePlugin()
				return
			}
		}
		
		try {
			isCapturing.value = true
			captureProgress.value = 0
			
			// 模拟拍照进度
			const progressInterval = setInterval(() => {
				captureProgress.value += 20
				if (captureProgress.value >= 100) {
					clearInterval(progressInterval)
				}
			}, 100)
			
			// 获取相机上下文并拍照
			const ctx = uni.createCameraContext()
			
			const result = await new Promise((resolve, reject) => {
				ctx.takePhoto({
					quality: 'high',
					success: resolve,
					fail: reject
				})
			})
			
			// 处理拍照结果
			await handleCaptureResult(result)
			
		} catch (error) {
			console.error('拍照失败:', error)
			uni.showToast({
				title: t('messages.takePhotoFailed'),
				icon: 'error'
			})
		} finally {
			isCapturing.value = false
			captureProgress.value = 0
		}
	}
	
	const handleCaptureResult = async (result) => {
		try {
			// 获取文件信息
			const fileInfo = await uni.getFileInfo({
				filePath: result.tempImagePath
			})
			
			// 开始处理水印
			isProcessingWatermark.value = true
			
			uni.showLoading({
				title: t('messages.addingGPSWatermark'),
				mask: true
			})
			
			// 添加水印
			const watermarkedPath = await addWatermarkToPhoto(result.tempImagePath, fileInfo)
			
			// 准备照片数据
			const photoData = {
				path: watermarkedPath, // 使用带水印的照片
				originalPath: result.tempImagePath, // 保留原始路径
				timestamp: new Date().toISOString(),
				size: fileInfo.size,
				gps: { ...gpsInfo.value },
				checkItemId: urlParams.value.checkItemId || props.checkItemId,
				inspectionId: urlParams.value.inspectionId || props.inspectionId,
				hasWatermark: true
			}
			
			// 生成照片哈希值和数字签名
			if (watermarkConfig.security.enableHash) {
				photoData.hash = await generateSecureHash(watermarkedPath, watermarkData)
			}
			
			if (watermarkConfig.security.enableSignature) {
				photoData.signature = securityUtils.generateSignature(photoData)
			}
			
			// 显示预览
			previewPhoto.value = photoData
			showPreview.value = true
			
		} catch (error) {
			console.error('处理拍照结果失败:', error)
			uni.showToast({
				title: t('messages.photoProcessFailed'),
				icon: 'error'
			})
		} finally {
			isProcessingWatermark.value = false
			uni.hideLoading()
		}
	}
	
	const confirmPhoto = async () => {
		try {
			isUploading.value = true
			showUploadProgress.value = true
			uploadProgress.value = 0
			
			// 检查网络状态
			const networkType = await uni.getNetworkType()
			
			if (networkType.networkType === 'none') {
				// 离线模式：保存到本地
				await savePhotoOffline(previewPhoto.value)
			} else {
				// 在线模式：统一使用检查系统上传
				await uploadPhotoOnline(previewPhoto.value)
			}
			
			hidePreview()
			
			// 返回上一页或继续下一项
			goBack()
			
		} catch (error) {
			console.error('确认照片失败:', error)
			uni.showToast({
				title: t('messages.saveFailed'),
				icon: 'error'
			})
		} finally {
			isUploading.value = false
			showUploadProgress.value = false
		}
	}
	
	const savePhotoOffline = async (photoData) => {
		try {
			// 保存到离线存储
			const offlineData = {
				type: 'photo',
				data: photoData,
				timestamp: new Date().toISOString()
			}
			
			await offlineStore.saveOfflineData(offlineData)
			
			uni.showToast({
				title: t('messages.savedOffline'),
				icon: 'success'
			})
			
		} catch (error) {
			throw new Error('离线保存失败: ' + error.message)
		}
	}
	
	const uploadPhotoOnline = async (photoData) => {
		try {
			// 模拟上传进度
			const uploadInterval = setInterval(() => {
				uploadProgress.value += 10
				updateUploadSpeed()
				
				if (uploadProgress.value >= 100) {
					clearInterval(uploadInterval)
				}
			}, 200)
			
			// 调用上传接口
			const result = await inspectionStore.uploadPhoto(
				urlParams.value.inspectionId || props.inspectionId,
				photoData.path,
				{
					checkItemId: urlParams.value.checkItemId || props.checkItemId,
					gpsData: photoData.gps
				}
			)
			
			if (result.success) {
				uni.showToast({
					title: t('messages.uploadSuccess'),
					icon: 'success'
				})
			} else {
				throw new Error(result.error || t('messages.uploadFailed'))
			}
			
		} catch (error) {
			// 上传失败时保存到离线
			await savePhotoOffline(photoData)
			throw error
		}
	}
	
	const updateUploadSpeed = () => {
		// 模拟上传速度计算
		const speeds = ['1.2MB/s', '800KB/s', '1.5MB/s', '600KB/s']
		uploadSpeed.value = speeds[Math.floor(Math.random() * speeds.length)]
	}
	
	const retakePhoto = () => {
		hidePreview()
	}
	
	const hidePreview = () => {
		showPreview.value = false
		previewPhoto.value = {}
	}
	
	// 工具方法
	const goBack = () => {
		uni.navigateBack()
	}
	
	const onCameraError = (error) => {
		console.error('相机错误:', error)
		uni.showModal({
			title: t('messages.cameraErrorTitle'),
			content: t('messages.cameraInitFailedContent'),
			showCancel: false
		})
	}
	
	const onScanCode = (result) => {
		console.log('扫码结果:', result)
		// 如果需要扫码功能可以在这里处理
	}
	
	const showGalleryDisabledTip = () => {
		uni.showModal({
			title: t('messages.featureLimitTitle'),
			content: t('messages.albumSelectionDisabledContent'),
			showCancel: false
		})
	}
	
	const getGpsStatusClass = () => {
		if (!gpsInfo.value.latitude) return 'gps-status-loading'
		if (gpsInfo.value.accuracy > 10) return 'gps-status-poor'
		return 'gps-status-good'
	}
	
	const formatGPS = (gps) => {
		if (!gps?.latitude) return t('messages.gettingLocation')
		
		return `${gps.latitude.toFixed(6)}, ${gps.longitude.toFixed(6)}`
	}
	
	const formatFileSize = (size) => {
		if (size < 1024) return size + 'B'
		if (size < 1024 * 1024) return (size / 1024).toFixed(1) + 'KB'
		return (size / (1024 * 1024)).toFixed(1) + 'MB'
	}
	
	// 移除reverseGeocode函数，因为原生插件已经包含地址解析功能
	
	// 水印处理函数
	const addWatermarkToPhoto = async (imagePath, fileInfo) => {
		try {
			console.log('开始添加GPS地址水印:', imagePath)
			
			// 使用新的增强水印功能，自动获取GPS和地址信息
			// 获取图片信息并设置canvas
			const imageInfo = await getImageInfo(imagePath)

			const originWidth = imageInfo.width
			const originHeight = imageInfo.height
			const originLongEdge = Math.max(originWidth, originHeight)
			
			// 优先用定位策略取一次（含地址）；失败则使用页面实时GPS（只带坐标），避免多次重试时重复走网络
			let gpsOverride = null
			try {
				const result = await getLocationWithAddressStrategy()
				if (result && result.success && result.data) {
					gpsOverride = result
				}
			} catch (e) {
				// ignore
			}
			if (!gpsOverride) {
				gpsOverride = {
					latitude: gpsInfo.value?.latitude || 0,
					longitude: gpsInfo.value?.longitude || 0,
					accuracy: gpsInfo.value?.accuracy || 0,
					address: gpsInfo.value?.address || ''
				}
			}

			canvasId.value = 'watermark-canvas-' + Date.now()
			
			console.log('设置Camera页面Canvas:', {
				canvasId: canvasId.value,
				origin: { width: originWidth, height: originHeight }
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

			let lastError = null
			for (const edge of uniqueEdges) {
				const target = buildTargetSize(edge)

				// 设置canvas尺寸
				canvasWidth.value = target.width
				canvasHeight.value = target.height

				console.log('Camera水印Canvas尺寸:', {
					origin: { width: originWidth, height: originHeight },
					target: { width: target.width, height: target.height, maxEdge: target.maxEdge, scale: target.scale }
				})

				// 等待canvas元素渲染
				await new Promise(resolve => setTimeout(resolve, 120))

				try {
					const watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, {
						inspector: userStore.userInfo?.username || t('messages.unknownInspector'),
						checkItem: checkItem.value?.item_name || t('inspection.checkItem'),
						siteName: currentSite.value?.site_name || t('site.unknownSite')
					}, {
						showAddressDetails: true,  // 显示详细地址信息
						showPOI: false,           // 不显示POI信息
						canvasId: canvasId.value,  // 使用页面中的canvas
						gpsOverride,
						renderWidth: target.width,
						renderHeight: target.height,
						maxEdge: target.maxEdge,
						validateRender: true,
						postDrawDelayMs: 30,
					})

					console.log('GPS地址水印添加完成:', watermarkedPath)
					return watermarkedPath
				} catch (e) {
					lastError = e
					console.warn('Camera水印生成失败，尝试降级尺寸:', {
						maxEdge: target.maxEdge,
						target: { width: target.width, height: target.height },
						error: e?.message || e
					})
				}
			}

			throw lastError || new Error('水印添加失败')
			
		} catch (error) {
			console.error('原生插件水印添加失败:', error)
			
			// 不再提供兜底方案，直接抛出错误
			// 确保只使用原生插件定位，不使用任何备用方案
			uni.showToast({
				title: t('messages.nativeWatermarkFailed'),
				icon: 'error'
			})
			
			throw error
		}
	}
	
	const getImageInfo = async (imagePath) => {
		return new Promise((resolve, reject) => {
			uni.getImageInfo({
				src: imagePath,
				success: resolve,
				fail: reject
			})
		})
	}
	
	const addWatermarkWithCanvas = async (imagePath, watermarkData, imageInfo) => {
		return new Promise((resolve, reject) => {
			const ctx = uni.createCanvasContext(canvasId.value)
			
			// 绘制原始图片
			ctx.drawImage(imagePath, 0, 0, imageInfo.width, imageInfo.height)
			
			// 准备水印文本
			const watermarkLines = prepareWatermarkText(watermarkData)
			
			// 绘制水印
			drawWatermarkOnCanvas(ctx, watermarkLines, imageInfo)
			
			// 渲染canvas
			ctx.draw(true, () => {
				// 保存canvas为图片
				uni.canvasToTempFilePath({
					canvasId: canvasId.value,
					destWidth: imageInfo.width,
					destHeight: imageInfo.height,
					quality: 0.9,
					fileType: 'jpg',
					success: (res) => {
						resolve(res.tempFilePath)
					},
					fail: (error) => {
						reject(new Error('保存canvas失败: ' + error.errMsg))
					}
				})
			})
		})
	}
	
	const prepareWatermarkText = (watermarkData) => {
		const formatWatermarkTimestamp = (input = new Date()) => {
			const date = input instanceof Date ? input : new Date(input)
			if (!Number.isFinite(date.getTime())) return String(input || '')
			const pad2 = (v) => String(v).padStart(2, '0')
			return (
				`${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}` +
				` ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`
			)
		}

		const lines = []
		
		// GPS坐标信息
		if (watermarkData.gps && watermarkData.gps.latitude) {
			lines.push(`📍 ${watermarkData.gps.latitude.toFixed(6)}, ${watermarkData.gps.longitude.toFixed(6)}`)
			
			if (watermarkData.gps.accuracy) {
				lines.push(`📊 ${watermarkData.gps.accuracy.toFixed(1)}m`)
			}
		}
		
		// 时间信息
		if (watermarkData.timestamp) {
			lines.push(`🕐 ${formatWatermarkTimestamp(watermarkData.timestamp)}`)
		}
		
		// 检查员信息
		if (watermarkData.inspector) {
			lines.push(`👤 ${watermarkData.inspector}`)
		}
		
		// 检查项信息
		if (watermarkData.checkItem) {
			lines.push(`📋 ${watermarkData.checkItem}`)
		}
		
		// 站点信息
		if (watermarkData.siteName) {
			lines.push(`🏗️ ${watermarkData.siteName}`)
		}
		
		return lines
	}
	
	const drawWatermarkOnCanvas = (ctx, lines, imageInfo) => {
		const config = watermarkConfig.style
		
		// 基于图片短边按 2.5% 计算动态字号，并对缩放比例做限制
		const baseFontSize = config.fontSize
		const basePadding = config.padding
		const baseMargin = config.margin
		const baseLineHeight = config.lineHeight

		const shortEdge = Math.min(imageInfo.width || 0, imageInfo.height || 0)
		const targetFontSize = shortEdge * 0.025
		let scale = baseFontSize > 0 ? targetFontSize / baseFontSize : 1
		const minScale = 0.8
		const maxScale = 3.0
		if (!isFinite(scale) || scale <= 0) scale = 1
		scale = Math.max(minScale, Math.min(maxScale, scale))

		const fontSize = baseFontSize * scale
		const padding = basePadding * scale
		const margin = baseMargin * scale
		const lineHeight = baseLineHeight * scale
		const backgroundColor = config.backgroundColor
		const textColor = config.textColor
		
		// 计算水印尺寸
		ctx.setFontSize(fontSize)
		let maxWidth = 0
		lines.forEach(line => {
			const width = ctx.measureText(line).width
			maxWidth = Math.max(maxWidth, width)
		})
		
		const watermarkWidth = maxWidth + padding * 2
		const watermarkHeight = lines.length * lineHeight + padding * 2
		
		// 计算水印位置
		const position = watermarkConfig.position.default
		let x, y
		
		switch (position) {
			case 'topLeft':
				x = margin
				y = margin
				break
			case 'topRight':
				x = imageInfo.width - watermarkWidth - margin
				y = margin
				break
			case 'bottomRight':
				x = imageInfo.width - watermarkWidth - margin
				y = imageInfo.height - watermarkHeight - margin
				break
			case 'center':
				x = (imageInfo.width - watermarkWidth) / 2
				y = (imageInfo.height - watermarkHeight) / 2
				break
			case 'bottomLeft':
			default:
				x = margin
				y = imageInfo.height - watermarkHeight - margin
				break
		}
		
		// 绘制背景
		ctx.setFillStyle(backgroundColor)
		drawRoundedRect(ctx, x, y, watermarkWidth, watermarkHeight, 8)
		ctx.fill()
		
		// 绘制文本
		ctx.setFillStyle(textColor)
		ctx.setFontSize(fontSize)
		ctx.setTextAlign('left')
		
		lines.forEach((line, index) => {
			const textX = x + padding
			const textY = y + padding + (index + 1) * lineHeight - 8
			ctx.fillText(line, textX, textY)
		})
	}
	
	const drawRoundedRect = (ctx, x, y, width, height, radius) => {
		ctx.beginPath()
		ctx.moveTo(x + radius, y)
		ctx.lineTo(x + width - radius, y)
		ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
		ctx.lineTo(x + width, y + height - radius)
		ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height)
		ctx.lineTo(x + radius, y + height)
		ctx.quadraticCurveTo(x, y + height, x, y + height - radius)
		ctx.lineTo(x, y + radius)
		ctx.quadraticCurveTo(x, y, x + radius, y)
		ctx.closePath()
	}
	
	// 安全相关函数
	const generateSecureHash = async (imagePath, watermarkData) => {
		try {
			// 获取文件信息
			const fileInfo = await uni.getFileInfo({
				filePath: imagePath
			})
			
			// 组合数据用于哈希
			const hashData = {
				filePath: imagePath,
				fileSize: fileInfo.size,
				watermarkData,
				timestamp: new Date().toISOString(),
				version: watermarkConfig.security.watermarkVersion
			}
			
			// 生成哈希值
			return securityUtils.generateSimpleHash(hashData)
		} catch (error) {
			console.error('生成哈希失败:', error)
			return securityUtils.generateTimestamp()
		}
	}
	
	// 验证照片完整性
	const verifyPhotoIntegrity = (photoData) => {
		if (!watermarkConfig.security.enableTamperDetection) {
			return true
		}
		
		try {
			// 验证哈希值
			if (photoData.hash) {
				const expectedHash = securityUtils.generateSimpleHash({
					path: photoData.path,
					size: photoData.size,
					timestamp: photoData.timestamp,
					gps: photoData.gps
				})
				
				if (expectedHash !== photoData.hash) {
					console.warn('照片哈希验证失败')
					return false
				}
			}
			
			// 验证签名
			if (photoData.signature) {
				const expectedSignature = securityUtils.generateSignature(photoData)
				if (expectedSignature !== photoData.signature) {
					console.warn('照片签名验证失败')
					return false
				}
			}
			
			return true
		} catch (error) {
			console.error('完整性验证失败:', error)
			return false
		}
	}
</script>

<style scoped>
	.camera-container {
		height: 100vh;
		width: 100vw;
		position: relative;
		background: #000;
	}
	
	.status-bar {
		height: 44rpx;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
	}
	
	.camera-view {
		width: 100%;
		height: 100%;
		position: absolute;
		top: 0;
		left: 0;
	}
	
	/* 顶部工具栏 */
	.top-toolbar {
		position: absolute;
		top: 44rpx;
		left: 0;
		right: 0;
		height: 120rpx;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		display: flex;
		align-items: center;
		padding: 0 30rpx;
		z-index: 100;
	}
	
	.toolbar-left,
	.toolbar-right {
		display: flex;
		align-items: center;
		gap: 20rpx;
	}
	
	.toolbar-center {
		flex: 1;
		text-align: center;
		margin: 0 20rpx;
	}
	
	.toolbar-title {
		color: white;
		font-size: 32rpx;
		font-weight: bold;
		display: block;
		margin-bottom: 5rpx;
	}
	
	.toolbar-subtitle {
		color: rgba(255, 255, 255, 0.8);
		font-size: 24rpx;
		display: block;
	}
	
	.tool-btn { width: 88rpx; height: 88rpx; border-radius: 44rpx; background: rgba(255, 255, 255, 0.2); border: 2rpx solid rgba(255, 255, 255, 0.28); display: flex; align-items: center; justify-content: center; }
	
	.btn-icon {
		color: white;
		font-size: 36rpx;
	}

	.uniicon-font {
		font-family: uniicons;
	}
	
	/* GPS信息覆盖层 */
	.gps-overlay {
		position: absolute;
		top: 200rpx;
		left: 30rpx;
		right: 30rpx;
		background: rgba(0, 0, 0, 0.8);
		border-radius: 15rpx;
		padding: 20rpx;
	}
	
	.gps-text,
	.gps-accuracy,
	.gps-address,
	.gps-time {
		color: white;
		font-size: 24rpx;
		line-height: 1.5;
		display: block;
		margin-bottom: 5rpx;
	}
	
	/* 拍照要求覆盖层 */
	.requirement-overlay {
		position: absolute;
		top: 50%;
		left: 30rpx;
		right: 30rpx;
		transform: translateY(-50%);
	}
	
	.requirement-card {
		background: rgba(0, 0, 0, 0.9);
		border-radius: 20rpx;
		padding: 30rpx;
	}
	
	.requirement-title {
		color: #fff;
		font-size: 32rpx;
		font-weight: bold;
		margin-bottom: 15rpx;
		display: block;
	}
	
	.requirement-desc {
		color: rgba(255, 255, 255, 0.9);
		font-size: 28rpx;
		line-height: 1.5;
		margin-bottom: 20rpx;
		display: block;
	}
	
	.requirement-item {
		color: rgba(255, 255, 255, 0.8);
		font-size: 26rpx;
		line-height: 1.6;
		display: block;
		margin-bottom: 8rpx;
	}
	
	/* 底部控制栏 */
	.bottom-controls {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 300rpx;
		background: linear-gradient(0deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 100%);
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 50rpx 50rpx;
	}
	
	.gps-status {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10rpx;
		min-width: 140rpx;
	}
	
	.gps-icon {
		font-size: 48rpx;
	}
	
	.gps-status-text {
		font-size: 22rpx;
		text-align: center;
		line-height: 1.3;
	}
	
	.gps-status-loading .gps-icon,
	.gps-status-loading .gps-status-text {
		color: #ffc107;
	}
	
	.gps-status-poor .gps-icon,
	.gps-status-poor .gps-status-text {
		color: #dc3545;
	}
	
	.gps-status-good .gps-icon,
	.gps-status-good .gps-status-text {
		color: #28a745;
	}
	
	/* 拍照按钮 */
	.capture-group {
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	
	.capture-ring {
		width: 160rpx;
		height: 160rpx;
		border: 8rpx solid rgba(255, 255, 255, 0.3);
		border-radius: 80rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 20rpx;
	}
	
	.capture-btn {
		width: 120rpx;
		height: 120rpx;
		background: white;
		border-radius: 60rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: transform 0.1s ease;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.3);
	}
	
	.capture-btn:active {
		transform: scale(0.95);
	}
	
	.capture-btn.disabled {
		background: #666;
		opacity: 0.5;
	}
	
	.capture-icon {
		font-size: 48rpx;
		color: #333;
	}
	
	/* 相册按钮 */
	.gallery-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10rpx;
		min-width: 140rpx;
		position: relative;
	}
	
	.gallery-icon {
		font-size: 48rpx;
		color: #666;
	}
	
	.gallery-text {
		font-size: 22rpx;
		color: #666;
	}
	
	.disabled-overlay {
		position: absolute;
		top: -10rpx;
		right: 20rpx;
		background: #dc3545;
		color: white;
		padding: 4rpx 8rpx;
		border-radius: 8rpx;
		font-size: 18rpx;
	}
	
	.disabled-text {
		font-size: 18rpx;
		color: white;
	}
	
	/* 拍照进度 */
	.capture-progress {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: rgba(0, 0, 0, 0.9);
		border-radius: 20rpx;
		padding: 30rpx 40rpx;
		min-width: 300rpx;
		text-align: center;
	}
	
	.progress-text {
		color: white;
		font-size: 28rpx;
		margin-bottom: 20rpx;
		display: block;
	}
	
	.progress-bar {
		height: 8rpx;
		background: rgba(255, 255, 255, 0.3);
		border-radius: 4rpx;
		overflow: hidden;
	}
	
	.progress-fill {
		height: 100%;
		background: #007bff;
		border-radius: 4rpx;
		transition: width 0.3s ease;
	}
	
	/* 照片预览弹窗 */
	.photo-preview-modal {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.9);
		z-index: 1000;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 40rpx;
	}
	
	.preview-container {
		background: white;
		border-radius: 20rpx;
		width: 100%;
		max-width: 700rpx;
		max-height: 90vh;
		overflow: hidden;
	}
	
	.preview-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 30rpx;
		border-bottom: 1rpx solid #eee;
	}
	
	.preview-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
	}
	
	.preview-close {
		width: 88rpx;
		height: 88rpx;
		border-radius: 44rpx;
		background: var(--bg-page);
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
	}

	.preview-close::after { border: none; }

	.preview-close:active { opacity: 0.9; }
	
	.preview-content {
		padding: 30rpx;
	}
	
	.preview-image {
		width: 100%;
		height: 400rpx;
		border-radius: 15rpx;
		margin-bottom: 30rpx;
	}
	
	.photo-info {
		background: #f8f9fa;
		border-radius: 15rpx;
		padding: 25rpx;
	}
	
	.info-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 15rpx;
	}
	
	.info-row:last-child {
		margin-bottom: 0;
	}
	
	.info-label {
		font-size: 26rpx;
		color: #666;
	}
	
	.info-value {
		font-size: 26rpx;
		color: #333;
		font-family: monospace;
	}
	
	.preview-actions {
		display: flex;
		gap: 20rpx;
		padding: 30rpx;
		border-top: 1rpx solid #eee;
	}
	
	.action-btn {
		flex: 1;
		padding: 25rpx;
		border-radius: 15rpx;
		border: none;
		font-size: 30rpx;
		font-weight: bold;
	}
	
	.retry-btn {
		background: #6c757d;
		color: white;
	}
	
	.confirm-btn {
		background: #007bff;
		color: white;
	}
	
	.confirm-btn:disabled {
		background: #ccc;
		color: #666;
	}
	
	/* 上传进度弹窗 */
	.upload-progress-modal {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.8);
		z-index: 1100;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	
	.upload-container {
		background: white;
		border-radius: 20rpx;
		padding: 50rpx 40rpx;
		min-width: 400rpx;
		text-align: center;
	}
	
	.upload-icon {
		font-size: 80rpx;
		margin-bottom: 20rpx;
	}
	
	.upload-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 30rpx;
	}
	
	.upload-progress-bar {
		height: 12rpx;
		background: #e9ecef;
		border-radius: 6rpx;
		overflow: hidden;
		margin-bottom: 20rpx;
	}
	
	.upload-progress-fill {
		height: 100%;
		background: #007bff;
		border-radius: 6rpx;
		transition: width 0.3s ease;
	}
	
	.upload-text {
		font-size: 26rpx;
		color: #666;
	}
</style>
