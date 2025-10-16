<template>
	<view class="sites-map-container">
		<!-- 顶部信息栏 -->
		<view class="map-header">
			<view class="back-btn" @click="goBack">
				<text class="back-icon">←</text>
			</view>
			<view class="location-info">
				<text class="location-name">站点分布地图</text>
				<text class="coordinates">共 {{ totalSites }} 个站点</text>
			</view>
		</view>
		
		<!-- 使用iframe加载瓦片地图 -->
		<view class="map-view">
			<iframe 
				id="leafletMap"
				class="map-iframe"
				src="/static/map/leaflet-map.html"
				@load="onMapLoad"
			></iframe>
		</view>
		
		<!-- 底部站点列表 -->
		<view class="sites-panel" :class="{ collapsed: panelCollapsed }">
			<view class="panel-header" @click="togglePanel">
				<view class="panel-title">
					<text class="title-text">站点列表</text>
					<text class="count-badge">{{ filteredSites.length }}</text>
				</view>
				<text class="toggle-icon">{{ panelCollapsed ? '▲' : '▼' }}</text>
			</view>
			
			<scroll-view class="sites-list" scroll-y v-if="!panelCollapsed">
				<!-- 筛选器 -->
				<view class="filter-bar">
					<view 
						class="filter-item" 
						:class="{ active: currentFilter === 'all' }"
						@click="setFilter('all')"
					>
						<text>全部</text>
					</view>
					<view 
						class="filter-item" 
						:class="{ active: currentFilter === 'operational' }"
						@click="setFilter('operational')"
					>
						<text>运营中</text>
					</view>
					<view 
						class="filter-item" 
						:class="{ active: currentFilter === 'construction' }"
						@click="setFilter('construction')"
					>
						<text>建设中</text>
					</view>
					<view 
						class="filter-item" 
						:class="{ active: currentFilter === 'maintenance' }"
						@click="setFilter('maintenance')"
					>
						<text>维护中</text>
					</view>
				</view>
				
				<!-- 站点列表项 -->
				<view 
					class="site-item" 
					v-for="site in filteredSites" 
					:key="site.id"
					@click="viewSiteDetail(site)"
				>
					<view class="site-icon" :class="getStatusClass(site.status)">
						📍
					</view>
					<view class="site-info">
						<text class="site-name">{{ site.site_name }}</text>
						<text class="site-address">{{ site.address || '暂无地址' }}</text>
					</view>
					<view class="site-status" :class="getStatusClass(site.status)">
						{{ getStatusText(site.status) }}
					</view>
				</view>
				
				<view class="empty-state" v-if="filteredSites.length === 0">
					<text>暂无站点</text>
				</view>
			</scroll-view>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-overlay" v-if="loading">
			<uni-load-more status="loading"></uni-load-more>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useSiteStore } from '@/stores/site'
	import { useUserStore } from '@/stores/user'
	
	const siteStore = useSiteStore()
	const userStore = useUserStore()
	
	// 页面数据
	const sites = ref([])
	const loading = ref(true)
	const panelCollapsed = ref(false)
	const currentFilter = ref('all')
	const mapReady = ref(false)
	let mapIframe = null
	
	// 计算属性
	const totalSites = computed(() => sites.value.length)
	
	const filteredSites = computed(() => {
		if (currentFilter.value === 'all') {
			return sites.value
		}
		return sites.value.filter(site => site.status === currentFilter.value)
	})
	
	// 生成地图中心点（所有站点的平均位置）
	const mapCenter = computed(() => {
		if (sites.value.length === 0) {
			return { lat: 39.9042, lon: 116.4074 } // 默认北京
		}
		
		const validSites = sites.value.filter(s => s.latitude && s.longitude)
		if (validSites.length === 0) {
			return { lat: 39.9042, lon: 116.4074 }
		}
		
		const avgLat = validSites.reduce((sum, s) => sum + parseFloat(s.latitude), 0) / validSites.length
		const avgLon = validSites.reduce((sum, s) => sum + parseFloat(s.longitude), 0) / validSites.length
		
		return { lat: avgLat, lon: avgLon }
	})
	
	// 地图加载完成
	const onMapLoad = () => {
		console.log('地图iframe加载完成')
		// H5环境中获取iframe引用
		// #ifdef H5
		mapIframe = document.getElementById('leafletMap')
		// #endif
		
		// 监听地图消息
		window.addEventListener('message', handleMapMessage)
	}
	
	// 处理来自地图的消息
	const handleMapMessage = (event) => {
		const { type, data } = event.data
		
		switch(type) {
			case 'mapReady':
				mapReady.value = true
				// 地图准备好后，加载所有站点标记
				loadMarkersToMap()
				break
			case 'markerClick':
				// 标记点击事件
				const site = sites.value.find(s => s.id === data.siteId)
				if (site) {
					console.log('点击站点:', site.site_name)
				}
				break
		}
	}
	
	// 向地图发送消息
	const sendMessageToMap = (action, data) => {
		if (!mapIframe || !mapReady.value) {
			console.warn('地图未准备好')
			return
		}
		
		// #ifdef H5
		if (mapIframe.contentWindow) {
			mapIframe.contentWindow.postMessage({
				action: action,
				data: data
			}, '*')
		}
		// #endif
	}
	
	// 加载站点标记到地图
	const loadMarkersToMap = () => {
		if (!mapReady.value) return
		
		// 清除现有标记
		sendMessageToMap('clearMarkers', {})
		
		// 添加所有站点标记
		sites.value.forEach(site => {
			sendMessageToMap('addMarker', {
				id: site.id,
				latitude: parseFloat(site.latitude),
				longitude: parseFloat(site.longitude),
				site_name: site.site_name,
				address: site.address,
				status: site.status
			})
		})
		
		// 自动适应所有标记
		setTimeout(() => {
			sendMessageToMap('fitBounds', {})
		}, 500)
	}
	
	// 加载站点数据
	const loadSites = async () => {
		try {
			loading.value = true
			const result = await siteStore.getSites()
			
			if (result.success) {
				// 只显示有坐标的站点
				sites.value = result.data.filter(s => s.latitude && s.longitude)
				
				// 如果地图已就绪，加载标记
				if (mapReady.value) {
					loadMarkersToMap()
				}
			} else {
				uni.showToast({
					title: '加载站点失败',
					icon: 'error'
				})
			}
		} catch (error) {
			console.error('Load sites error:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	// 切换面板展开/收起
	const togglePanel = () => {
		panelCollapsed.value = !panelCollapsed.value
	}
	
	// 设置筛选器
	const setFilter = (filter) => {
		currentFilter.value = filter
	}
	
	// 查看站点详情
	const viewSiteDetail = (site) => {
		uni.navigateTo({
			url: `/pages/site/detail?id=${site.id}`
		})
	}
	
	// 获取状态样式类
	const getStatusClass = (status) => {
		const classMap = {
			'operational': 'status-operational',
			'construction': 'status-construction',
			'maintenance': 'status-maintenance',
			'planning': 'status-planning'
		}
		return classMap[status] || 'status-default'
	}
	
	// 获取状态文本
	const getStatusText = (status) => {
		const statusMap = {
			'operational': '运营中',
			'construction': '建设中',
			'maintenance': '维护中',
			'planning': '规划中'
		}
		return statusMap[status] || status
	}
	
	// 返回
	const goBack = () => {
		uni.navigateBack()
	}
	
	// 页面加载
	onLoad((options) => {
		// 设置页面标题
		uni.setNavigationBarTitle({
			title: '站点分布地图'
		})
		
		// 加载站点数据
		loadSites()
	})
</script>

<style lang="scss" scoped>
	.sites-map-container {
		position: relative;
		width: 100vw;
		height: 100vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
	
	/* 地图头部信息栏 */
	.map-header {
		position: relative;
		z-index: 1000;
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 44rpx 20rpx 20rpx;
		display: flex;
		align-items: center;
		gap: 20rpx;
		box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.1);
		flex-shrink: 0;
	}
	
	.back-btn {
		width: 60rpx;
		height: 60rpx;
		border-radius: 30rpx;
		background: rgba(255, 255, 255, 0.2);
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
		color: white;
		margin-bottom: 4rpx;
	}
	
	.coordinates {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.9);
	}
	
	/* 地图视图 */
	.map-view {
		flex: 1;
		width: 100%;
		position: relative;
		overflow: hidden;
	}
	
	.map-iframe {
		width: 100%;
		height: 100%;
		border: none;
	}
	
	/* 底部站点面板 */
	.sites-panel {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		z-index: 1000;
		background: white;
		border-radius: 30rpx 30rpx 0 0;
		box-shadow: 0 -4rpx 20rpx rgba(0, 0, 0, 0.1);
		max-height: 60vh;
		transition: max-height 0.3s ease;
		
		&.collapsed {
			max-height: 120rpx;
		}
	}
	
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 30rpx;
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.panel-title {
		display: flex;
		align-items: center;
		gap: 15rpx;
	}
	
	.title-text {
		font-size: 30rpx;
		font-weight: 600;
		color: #111827;
	}
	
	.count-badge {
		background: #f97316;
		color: white;
		font-size: 20rpx;
		padding: 4rpx 12rpx;
		border-radius: 12rpx;
		font-weight: 600;
	}
	
	.toggle-icon {
		font-size: 24rpx;
		color: #9ca3af;
	}
	
	.sites-list {
		max-height: calc(60vh - 120rpx);
		overflow-y: auto;
	}
	
	/* 筛选栏 */
	.filter-bar {
		display: flex;
		gap: 15rpx;
		padding: 20rpx 30rpx;
		overflow-x: auto;
		white-space: nowrap;
	}
	
	.filter-item {
		padding: 10rpx 24rpx;
		background: #f3f4f6;
		border-radius: 20rpx;
		font-size: 24rpx;
		color: #6b7280;
		transition: all 0.3s ease;
		flex-shrink: 0;
		
		&.active {
			background: #f97316;
			color: white;
		}
	}
	
	/* 站点列表项 */
	.site-item {
		display: flex;
		align-items: center;
		gap: 20rpx;
		padding: 25rpx 30rpx;
		border-bottom: 1rpx solid #f3f4f6;
		transition: background 0.2s ease;
		
		&:active {
			background: #f9fafb;
		}
	}
	
	.site-icon {
		font-size: 40rpx;
		flex-shrink: 0;
		
		&.status-operational { filter: hue-rotate(90deg); }
		&.status-construction { filter: hue-rotate(30deg); }
		&.status-maintenance { filter: hue-rotate(-30deg); }
	}
	
	.site-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 6rpx;
		min-width: 0;
	}
	
	.site-name {
		font-size: 28rpx;
		font-weight: 600;
		color: #111827;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	.site-address {
		font-size: 22rpx;
		color: #6b7280;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	.site-status {
		font-size: 22rpx;
		padding: 6rpx 16rpx;
		border-radius: 12rpx;
		flex-shrink: 0;
		
		&.status-operational {
			background: #d1fae5;
			color: #059669;
		}
		
		&.status-construction {
			background: #fef3c7;
			color: #d97706;
		}
		
		&.status-maintenance {
			background: #fee2e2;
			color: #dc2626;
		}
		
		&.status-planning {
			background: #e5e7eb;
			color: #6b7280;
		}
	}
	
	.empty-state {
		text-align: center;
		padding: 60rpx 30rpx;
		color: #9ca3af;
		font-size: 26rpx;
	}
	
	/* 加载状态 */
	.loading-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(255, 255, 255, 0.9);
		z-index: 3000;
		display: flex;
		align-items: center;
		justify-content: center;
	}
</style>
