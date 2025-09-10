<template>
	<view class="camera-container">
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
						<cover-text class="btn-icon">←</cover-text>
					</cover-view>
				</cover-view>
				
				<cover-view class="toolbar-center">
					<cover-text class="toolbar-title">{{ checkItem?.item_name || '拍照检查' }}</cover-text>
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
				<cover-text class="gps-accuracy">📊 精度: {{ gpsInfo.accuracy }}m</cover-text>
				<cover-text class="gps-address" v-if="gpsInfo.address">🏠 {{ gpsInfo.address }}</cover-text>
				<cover-text class="gps-time">🕐 {{ currentTime }}</cover-text>
			</cover-view>
			
			<!-- 拍照要求提示 -->
			<cover-view class="requirement-overlay" v-if="checkItem?.photo_requirements">
				<cover-view class="requirement-card">
					<cover-text class="requirement-title">📸 拍照要求</cover-text>
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
					<cover-text class="gallery-text">相册</cover-text>
					<cover-view class="disabled-overlay">
						<cover-text class="disabled-text">已禁用</cover-text>
					</cover-view>
				</cover-view>
			</cover-view>
			
			<!-- 拍照进度提示 -->
			<cover-view class="capture-progress" v-if="isCapturing">
				<cover-text class="progress-text">📸 拍照中...</cover-text>
				<cover-view class="progress-bar">
					<cover-view class="progress-fill" :style="{ width: captureProgress + '%' }"></cover-view>
				</cover-view>
			</cover-view>
		</camera>
		
		<!-- 照片预览弹窗 -->
		<view class="photo-preview-modal" v-if="showPreview" @click="hidePreview">
			<view class="preview-container" @click.stop>
				<view class="preview-header">
					<text class="preview-title">照片预览</text>
					<button class="preview-close" @click="hidePreview">✕</button>
				</view>
				
				<view class="preview-content">
					<image :src="previewPhoto.path" mode="aspectFit" class="preview-image"></image>
					
					<!-- 照片信息 -->
					<view class="photo-info">
						<view class="info-row">
							<text class="info-label">GPS坐标:</text>
							<text class="info-value">{{ formatGPS(previewPhoto.gps) }}</text>
						</view>
						<view class="info-row">
							<text class="info-label">拍摄时间:</text>
							<text class="info-value">{{ previewPhoto.timestamp }}</text>
						</view>
						<view class="info-row">
							<text class="info-label">文件大小:</text>
							<text class="info-value">{{ formatFileSize(previewPhoto.size) }}</text>
						</view>
						<view class="info-row" v-if="previewPhoto.gps.accuracy">
							<text class="info-label">GPS精度:</text>
							<text class="info-value">{{ previewPhoto.gps.accuracy }}m</text>
						</view>
					</view>
				</view>
				
				<view class="preview-actions">
					<button class="action-btn retry-btn" @click="retakePhoto">重新拍摄</button>
					<button class="action-btn confirm-btn" @click="confirmPhoto" :disabled="isUploading">
						{{ isUploading ? '上传中...' : '确认使用' }}
					</button>
				</view>
			</view>
		</view>
		
		<!-- 上传进度提示 -->
		<view class="upload-progress-modal" v-if="showUploadProgress">
			<view class="upload-container">
				<view class="upload-icon">📤</view>
				<text class="upload-title">正在上传照片</text>
				<view class="upload-progress-bar">
					<view class="upload-progress-fill" :style="{ width: uploadProgress + '%' }"></view>
				</view>
				<text class="upload-text">{{ uploadProgress }}% ({{ uploadSpeed }})</text>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, onUnmounted } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useInspectionStore } from '@/stores/inspection'
	import { useOfflineStore } from '@/stores/offline'
	
	const userStore = useUserStore()
	const inspectionStore = useInspectionStore()
	const offlineStore = useOfflineStore()
	
	// Props
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
		
		return true
	})
	
	const gpsStatusText = computed(() => {
		if (!gpsInfo.value.latitude) {
			return 'GPS定位中...'
		}
		
		if (gpsInfo.value.accuracy > 10) {
			return `GPS精度较低(${gpsInfo.value.accuracy}m)`
		}
		
		return `GPS良好(${gpsInfo.value.accuracy}m)`
	})
	
	// 生命周期
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
				title: '相机权限',
				content: '需要相机权限才能拍照，请在设置中开启',
				showCancel: false
			})
		}
	}
	
	const loadCheckItemInfo = async () => {
		try {
			if (props.inspectionId && props.checkItemId) {
				const result = await inspectionStore.getInspection(props.inspectionId)
				if (result.success) {
					const inspection = result.data
					currentSite.value = inspection.site
					
					// 查找检查项
					checkItem.value = inspection.check_items.find(
						item => item.id === props.checkItemId
					)
				}
			}
		} catch (error) {
			console.error('加载检查项信息失败:', error)
		}
	}
	
	const startGpsWatch = () => {
		// 立即获取一次位置
		getCurrentLocation()
		
		// 开始监听位置变化
		gpsWatcher.value = uni.onLocationChange((res) => {
			updateGpsInfo(res)
		})
		
		// 开始位置更新
		uni.startLocationUpdate({
			success: () => {
				console.log('开始位置更新')
			},
			fail: (error) => {
				console.error('开始位置更新失败:', error)
			}
		})
	}
	
	const stopGpsWatch = () => {
		if (gpsWatcher.value) {
			uni.offLocationChange(gpsWatcher.value)
		}
		
		uni.stopLocationUpdate()
	}
	
	const getCurrentLocation = () => {
		uni.getLocation({
			type: 'gcj02',
			altitude: true,
			success: (res) => {
				updateGpsInfo(res)
			},
			fail: (error) => {
				console.error('获取位置失败:', error)
				uni.showToast({
					title: 'GPS定位失败',
					icon: 'error'
				})
			}
		})
	}
	
	const updateGpsInfo = async (locationData) => {
		gpsInfo.value = {
			latitude: locationData.latitude,
			longitude: locationData.longitude,
			accuracy: locationData.accuracy,
			altitude: locationData.altitude,
			speed: locationData.speed
		}
		
		// 获取地址信息
		try {
			const address = await reverseGeocode(locationData.latitude, locationData.longitude)
			gpsInfo.value.address = address
		} catch (error) {
			console.error('逆地理编码失败:', error)
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
		currentTime.value = now.toLocaleString('zh-CN', {
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
		
		uni.showToast({
			title: `闪光灯: ${flashMode.value === 'on' ? '开启' : flashMode.value === 'auto' ? '自动' : '关闭'}`,
			icon: 'none'
		})
	}
	
	const switchCamera = () => {
		cameraPosition.value = cameraPosition.value === 'back' ? 'front' : 'back'
		
		uni.showToast({
			title: `切换到${cameraPosition.value === 'back' ? '后置' : '前置'}摄像头`,
			icon: 'none'
		})
	}
	
	const takePhoto = async () => {
		if (!canTakePhoto.value) return
		
		// 检查GPS要求
		if (checkItem.value?.photo_requirements?.gps_required && !gpsInfo.value.latitude) {
			uni.showModal({
				title: 'GPS定位',
				content: '此检查项需要GPS信息，请等待定位完成',
				showCancel: false
			})
			return
		}
		
		// 检查GPS精度
		if (gpsInfo.value.accuracy > 20) {
			const confirmResult = await uni.showModal({
				title: 'GPS精度',
				content: `当前GPS精度较低(${gpsInfo.value.accuracy}m)，可能影响照片质量，是否继续拍照？`,
				confirmText: '继续拍照',
				cancelText: '重新定位'
			})
			
			if (!confirmResult.confirm) {
				getCurrentLocation()
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
				title: '拍照失败',
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
			
			// 准备照片数据
			const photoData = {
				path: result.tempImagePath,
				timestamp: new Date().toISOString(),
				size: fileInfo.size,
				gps: { ...gpsInfo.value },
				checkItemId: props.checkItemId,
				inspectionId: props.inspectionId
			}
			
			// 显示预览
			previewPhoto.value = photoData
			showPreview.value = true
			
		} catch (error) {
			console.error('处理拍照结果失败:', error)
			uni.showToast({
				title: '处理照片失败',
				icon: 'error'
			})
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
				// 在线模式：直接上传
				await uploadPhotoOnline(previewPhoto.value)
			}
			
			hidePreview()
			
			// 返回上一页或继续下一项
			goBack()
			
		} catch (error) {
			console.error('确认照片失败:', error)
			uni.showToast({
				title: '保存失败',
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
				title: '已保存到离线',
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
				props.inspectionId,
				photoData.path,
				{
					checkItemId: props.checkItemId,
					gpsData: photoData.gps
				}
			)
			
			if (result.success) {
				uni.showToast({
					title: '上传成功',
					icon: 'success'
				})
			} else {
				throw new Error(result.error || '上传失败')
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
			title: '相机错误',
			content: '相机初始化失败，请检查权限设置',
			showCancel: false
		})
	}
	
	const onScanCode = (result) => {
		console.log('扫码结果:', result)
		// 如果需要扫码功能可以在这里处理
	}
	
	const showGalleryDisabledTip = () => {
		uni.showModal({
			title: '功能限制',
			content: '为确保照片真实性，现场检查必须实时拍照，不能选择相册中的照片',
			showCancel: false
		})
	}
	
	const getGpsStatusClass = () => {
		if (!gpsInfo.value.latitude) return 'gps-status-loading'
		if (gpsInfo.value.accuracy > 10) return 'gps-status-poor'
		return 'gps-status-good'
	}
	
	const formatGPS = (gps) => {
		if (!gps?.latitude) return 'GPS获取中...'
		
		return `${gps.latitude.toFixed(6)}, ${gps.longitude.toFixed(6)}`
	}
	
	const formatFileSize = (size) => {
		if (size < 1024) return size + 'B'
		if (size < 1024 * 1024) return (size / 1024).toFixed(1) + 'KB'
		return (size / (1024 * 1024)).toFixed(1) + 'MB'
	}
	
	const reverseGeocode = async (latitude, longitude) => {
		// 这里可以调用地图服务的逆地理编码API
		// 简化实现，返回坐标描述
		return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
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
		background: transparent;
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
		background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0) 100%);
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
	
	.tool-btn {
		width: 80rpx;
		height: 80rpx;
		border-radius: 40rpx;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		backdrop-filter: blur(10rpx);
	}
	
	.btn-icon {
		color: white;
		font-size: 36rpx;
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
		backdrop-filter: blur(10rpx);
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
		backdrop-filter: blur(15rpx);
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
		backdrop-filter: blur(15rpx);
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
		width: 60rpx;
		height: 60rpx;
		border-radius: 30rpx;
		background: #f5f5f5;
		border: none;
		font-size: 24rpx;
		color: #666;
	}
	
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