<template>
	<view class="map-container">
		<!-- 使用 web-view 显示在线地图 -->
		<web-view :src="mapUrl" @message="handleMessage"></web-view>
		
		<!-- 顶部信息栏 -->
		<view class="map-header">
			<view class="back-btn" @click="goBack">
				<text class="back-icon">←</text>
			</view>
			<view class="location-info">
				<text class="location-name">{{ locationName }}</text>
				<text class="coordinates">{{ formatCoordinates(latitude, longitude) }}</text>
			</view>
			<view class="switch-map-btn" @click="showMapTypeSelector">
				<text class="switch-icon">🗺️</text>
			</view>
		</view>
		
		<!-- 地图切换选择器 -->
		<view class="map-selector-overlay" v-if="showSelector" @click="showSelector = false">
			<view class="map-selector" @click.stop>
				<view class="selector-title">选择地图</view>
				<view class="map-options">
					<view 
						class="map-option" 
						:class="{ active: mapType === 'amap' }"
						@click="switchMapType('amap')"
					>
						<view class="option-icon">🗺️</view>
						<view class="option-info">
							<text class="option-name">高德地图</text>
							<text class="option-desc">国内定位精准</text>
						</view>
						<view class="option-check" v-if="mapType === 'amap'">✓</view>
					</view>
					<view 
						class="map-option" 
						:class="{ active: mapType === 'google' }"
						@click="switchMapType('google')"
					>
						<view class="option-icon">🌏</view>
						<view class="option-info">
							<text class="option-name">谷歌地图</text>
							<text class="option-desc">全球地图覆盖</text>
						</view>
						<view class="option-check" v-if="mapType === 'google'">✓</view>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	
	// 页面参数
	const latitude = ref(0)
	const longitude = ref(0)
	const locationName = ref('位置')
	const address = ref('')
	const mapType = ref('amap') // 默认使用高德地图
	const showSelector = ref(false)
	
	// 生成地图URL
	const mapUrl = computed(() => {
		const lat = latitude.value
		const lon = longitude.value
		const name = encodeURIComponent(locationName.value)
		
		if (mapType.value === 'google') {
			// 谷歌地图 URL
			// 格式：https://www.google.com/maps?q=纬度,经度&z=15
			return `https://www.google.com/maps?q=${lat},${lon}&z=15&output=embed`
		} else {
			// 高德地图 URI API scheme（不需要key）
			// 格式：https://uri.amap.com/marker?position=经度,纬度&name=名称&src=appname&coordinate=gaode&callnative=0
			// callnative=0 表示不调用客户端，直接在网页中打开
			return `https://uri.amap.com/marker?position=${lon},${lat}&name=${name}&src=站点管理&coordinate=gaode&callnative=0`
		}
	})
	
	// 格式化坐标显示
	const formatCoordinates = (lat, lon) => {
		if (!lat || !lon) return ''
		return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
	}
	
	// 显示地图类型选择器
	const showMapTypeSelector = () => {
		showSelector.value = true
	}
	
	// 切换地图类型
	const switchMapType = (type) => {
		mapType.value = type
		showSelector.value = false
		
		uni.showToast({
			title: type === 'google' ? '已切换至谷歌地图' : '已切换至高德地图',
			icon: 'success',
			duration: 1500
		})
	}
	
	// 处理 web-view 消息
	const handleMessage = (e) => {
		console.log('收到地图消息:', e)
	}
	
	// 返回
	const goBack = () => {
		uni.navigateBack()
	}
	
	// 页面加载
	onLoad((options) => {
		console.log('地图页面参数:', options)
		
		if (options.latitude && options.longitude) {
			latitude.value = parseFloat(options.latitude)
			longitude.value = parseFloat(options.longitude)
		}
		
		if (options.name) {
			locationName.value = decodeURIComponent(options.name)
		}
		
		if (options.address) {
			address.value = decodeURIComponent(options.address)
		}
		
		if (options.mapType) {
			mapType.value = options.mapType
		}
		
		// 设置页面标题
		uni.setNavigationBarTitle({
			title: locationName.value || '地图'
		})
	})
</script>

<style lang="scss" scoped>
	.map-container {
		position: relative;
		width: 100vw;
		height: 100vh;
		overflow: hidden;
	}
	
	/* 地图头部信息栏 */
	.map-header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 1000;
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(10px);
		padding: 44rpx 20rpx 20rpx;
		display: flex;
		align-items: center;
		gap: 20rpx;
		box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.1);
	}
	
	.back-btn {
		width: 60rpx;
		height: 60rpx;
		border-radius: 30rpx;
		background: #f97316;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	
	.back-icon {
		font-size: 32rpx;
		color: white;
		font-weight: bold;
	}
	
	.location-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	
	.location-name {
		font-size: 28rpx;
		font-weight: 600;
		color: #111827;
		margin-bottom: 4rpx;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	.coordinates {
		font-size: 22rpx;
		color: #6b7280;
		font-family: 'Courier New', monospace;
	}
	
	.switch-map-btn {
		width: 60rpx;
		height: 60rpx;
		border-radius: 30rpx;
		background: rgba(249, 115, 22, 0.1);
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border: 2rpx solid #f97316;
	}
	
	.switch-icon {
		font-size: 28rpx;
	}
	
	/* 地图选择器 */
	.map-selector-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 2000;
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}
	
	.map-selector {
		width: 100%;
		background: white;
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
	
	.selector-title {
		font-size: 32rpx;
		font-weight: 600;
		color: #111827;
		text-align: center;
		margin-bottom: 30rpx;
	}
	
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
	
	.map-option.active {
		background: #fef3e2;
		border-color: #f97316;
	}
	
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
	
	.option-check {
		font-size: 32rpx;
		color: #f97316;
		font-weight: bold;
		flex-shrink: 0;
	}
</style>
