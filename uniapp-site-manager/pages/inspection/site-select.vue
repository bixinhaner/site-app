<template>
	<view class="site-select-container">
		<!-- 导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="back-button" @click="goBack">
					<text class="back-icon">←</text>
				</view>
				<text class="navbar-title">选择站点</text>
				<view class="navbar-right">
					<text class="inspection-type">{{ getInspectionTypeText(inspectionType) }}</text>
				</view>
			</view>
		</view>
		
		<!-- 搜索和筛选 -->
		<view class="search-container">
			<view class="search-box">
				<text class="search-icon">🔍</text>
				<input 
					class="search-input" 
					placeholder="搜索站点名称或编号" 
					v-model="searchKeyword"
					@input="onSearch"
				/>
				<view class="clear-button" v-if="searchKeyword" @click="clearSearch">
					<text class="clear-icon">×</text>
				</view>
			</view>
			
			<view class="filter-button" @click="showFilterModal">
				<text class="filter-icon">🎯</text>
				<text class="filter-text">筛选</text>
				<text class="filter-count" v-if="activeFilterCount > 0">({{ activeFilterCount }})</text>
			</view>
		</view>
		
		<!-- 站点列表 -->
		<scroll-view class="site-list" scroll-y @scrolltolower="loadMore">
			<view 
				class="site-item"
				v-for="site in filteredSites"
				:key="site.id"
				@click="selectSite(site)"
			>
				<view class="site-header">
					<view class="site-info">
						<text class="site-name">{{ site.site_name }}</text>
						<text class="site-code">{{ site.site_code }}</text>
					</view>
					<view class="site-status" :class="getSiteStatusClass(site.status)">
						<text class="status-text">{{ getSiteStatusText(site.status) }}</text>
					</view>
				</view>
				
				<view class="site-details">
					<view class="detail-row">
						<text class="detail-icon">📍</text>
						<text class="detail-text">{{ site.location || '位置信息未提供' }}</text>
					</view>
					
					<view class="detail-row" v-if="site.coordinates">
						<text class="detail-icon">🗺️</text>
						<text class="detail-text">{{ formatCoordinates(site.coordinates) }}</text>
					</view>
					
					<view class="detail-row">
						<text class="detail-icon">🏢</text>
						<text class="detail-text">{{ site.operator || '未知运营商' }}</text>
					</view>
					
					<view class="detail-row" v-if="site.last_inspection">
						<text class="detail-icon">📋</text>
						<text class="detail-text">上次检查: {{ formatDate(site.last_inspection) }}</text>
					</view>
				</view>
				
				<!-- 站点操作 -->
				<view class="site-actions">
					<view class="site-distance" v-if="site.distance">
						<text class="distance-icon">📏</text>
						<text class="distance-text">距离: {{ formatDistance(site.distance) }}</text>
					</view>
					<text class="select-arrow">→</text>
				</view>
			</view>
			
			<!-- 空状态 -->
			<view class="empty-state" v-if="filteredSites.length === 0 && !loading">
				<text class="empty-icon">🏗️</text>
				<text class="empty-title">暂无可检查的站点</text>
				<text class="empty-desc">请联系管理员分配站点或调整筛选条件</text>
			</view>
			
			<!-- 加载更多 -->
			<view class="load-more" v-if="hasMore">
				<uni-load-more :status="loadMoreStatus"></uni-load-more>
			</view>
		</scroll-view>
		
		<!-- 筛选弹窗 -->
		<view class="filter-overlay" v-if="showFilter" @click="hideFilterModal">
			<view class="filter-modal" @click.stop>
				<view class="filter-header">
					<text class="filter-title">筛选条件</text>
					<view class="filter-close" @click="hideFilterModal">
						<text class="close-icon">×</text>
					</view>
				</view>
				
				<view class="filter-content">
					<!-- 状态筛选 -->
					<view class="filter-section">
						<text class="section-title">站点状态</text>
						<view class="filter-options">
							<view 
								class="filter-option"
								:class="{ active: filters.status.includes(status.value) }"
								v-for="status in statusOptions"
								:key="status.value"
								@click="toggleFilter('status', status.value)"
							>
								<text class="option-text">{{ status.label }}</text>
							</view>
						</view>
					</view>
					
					<!-- 运营商筛选 -->
					<view class="filter-section">
						<text class="section-title">运营商</text>
						<view class="filter-options">
							<view 
								class="filter-option"
								:class="{ active: filters.operator.includes(operator) }"
								v-for="operator in operatorOptions"
								:key="operator"
								@click="toggleFilter('operator', operator)"
							>
								<text class="option-text">{{ operator }}</text>
							</view>
						</view>
					</view>
					
					<!-- 距离筛选 -->
					<view class="filter-section">
						<text class="section-title">距离范围</text>
						<view class="distance-slider">
							<slider 
								:value="filters.maxDistance" 
								:max="50" 
								:min="1"
								@change="onDistanceChange"
								activeColor="#007bff"
							/>
							<text class="distance-value">{{ filters.maxDistance }}km 内</text>
						</view>
					</view>
				</view>
				
				<view class="filter-actions">
					<button class="filter-reset" @click="resetFilters">重置</button>
					<button class="filter-apply" @click="applyFilters">应用</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, onMounted } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useSiteStore } from '@/stores/site'
	import { useInspectionStore } from '@/stores/inspection'
	import { useUserStore } from '@/stores/user'
	
	const siteStore = useSiteStore()
	const inspectionStore = useInspectionStore()
	const userStore = useUserStore()
	
	// 页面参数
	const inspectionType = ref('opening')
	
	// 响应式数据
	const sites = ref([])
	const loading = ref(false)
	const hasMore = ref(true)
	const loadMoreStatus = ref('more')
	const page = ref(1)
	const pageSize = ref(20)
	
	// 搜索和筛选
	const searchKeyword = ref('')
	const showFilter = ref(false)
	const filters = ref({
		status: [],
		operator: [],
		maxDistance: 10
	})
	
	// 筛选选项
	const statusOptions = [
		{ label: '已分配', value: 'assigned' },
		{ label: '施工中', value: 'under_construction' },
		{ label: '待验收', value: 'pending_acceptance' },
		{ label: '运行中', value: 'operational' }
	]
	
	const operatorOptions = ref([])
	
	// 计算属性
	const filteredSites = computed(() => {
		let result = sites.value
		
		// 搜索过滤
		if (searchKeyword.value) {
			const keyword = searchKeyword.value.toLowerCase()
			result = result.filter(site => 
				site.site_name?.toLowerCase().includes(keyword) ||
				site.site_code?.toLowerCase().includes(keyword)
			)
		}
		
		// 状态过滤
		if (filters.value.status.length > 0) {
			result = result.filter(site => 
				filters.value.status.includes(site.status)
			)
		}
		
		// 运营商过滤
		if (filters.value.operator.length > 0) {
			result = result.filter(site => 
				filters.value.operator.includes(site.operator)
			)
		}
		
		// 距离过滤
		if (filters.value.maxDistance < 50) {
			result = result.filter(site => 
				!site.distance || site.distance <= filters.value.maxDistance * 1000
			)
		}
		
		return result
	})
	
	const activeFilterCount = computed(() => {
		return filters.value.status.length + 
			   filters.value.operator.length + 
			   (filters.value.maxDistance < 50 ? 1 : 0)
	})
	
	// 生命周期
	onLoad((options) => {
		if (options.type) {
			inspectionType.value = options.type
		}
		loadSites()
		getCurrentLocation()
	})
	
	// 方法
	const loadSites = async (reset = false) => {
		try {
			loading.value = true
			
			if (reset) {
				page.value = 1
				sites.value = []
			}
			
			// 根据检查类型和用户角色获取站点
			const params = {
				skip: (page.value - 1) * pageSize.value,
				limit: pageSize.value
			}
			
			// 根据检查类型设置筛选条件
			if (inspectionType.value === 'opening' || inspectionType.value === 'installation') {
				// 新站点设备安装：获取规划中或建设中的站点
				// 管理员和检查员可以看到所有这类站点，普通用户只能看分配给自己的
				if (userStore.userInfo?.role === 'user') {
					params.assigned_to = userStore.userInfo.id
				}
				// 不限制status，让后端根据权限返回合适的站点
			} else if (inspectionType.value === 'maintenance') {
				// 维护检查：获取运行中的站点
				params.status = 'operational'
				if (userStore.userInfo?.role === 'user') {
					params.assigned_to = userStore.userInfo.id
				}
			}
			
			const result = await siteStore.getSites(params)
			
			if (result.success) {
				if (reset) {
					sites.value = result.data
				} else {
					sites.value.push(...result.data)
				}
				
				// 更新运营商选项
				updateOperatorOptions()
				
				hasMore.value = result.data.length === pageSize.value
				loadMoreStatus.value = hasMore.value ? 'more' : 'no-more'
			}
			
		} catch (error) {
			console.error('加载站点失败:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	const getCurrentLocation = () => {
		uni.getLocation({
			type: 'gcj02',
			success: (res) => {
				// 计算站点距离
				calculateDistances(res.latitude, res.longitude)
			},
			fail: (err) => {
				console.warn('获取位置失败:', err)
			}
		})
	}
	
	const calculateDistances = (userLat, userLon) => {
		sites.value.forEach(site => {
			if (site.coordinates) {
				const coords = site.coordinates.split(',')
				if (coords.length === 2) {
					const siteLat = parseFloat(coords[0])
					const siteLon = parseFloat(coords[1])
					site.distance = calculateDistance(userLat, userLon, siteLat, siteLon)
				}
			}
		})
		
		// 按距离排序
		sites.value.sort((a, b) => (a.distance || Infinity) - (b.distance || Infinity))
	}
	
	const calculateDistance = (lat1, lon1, lat2, lon2) => {
		const R = 6371000 // 地球半径（米）
		const dLat = (lat2 - lat1) * Math.PI / 180
		const dLon = (lon2 - lon1) * Math.PI / 180
		const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
				  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
				  Math.sin(dLon/2) * Math.sin(dLon/2)
		const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
		return R * c
	}
	
	const updateOperatorOptions = () => {
		const operators = [...new Set(sites.value.map(site => site.operator).filter(Boolean))]
		operatorOptions.value = operators
	}
	
	const selectSite = async (site) => {
		try {
			// 创建新的检查记录
			const inspectionData = {
				site_id: site.id,
				inspection_type: inspectionType.value.toUpperCase(), // 转换为大写
				location: site.location,
				weather: '晴天', // 可以后续集成天气API
				temperature: '25°C'
			}
			
			// 如果有GPS坐标，添加到检查数据
			if (site.coordinates) {
				const coords = site.coordinates.split(',')
				if (coords.length === 2) {
					inspectionData.gps_info = {
						latitude: parseFloat(coords[0]),
						longitude: parseFloat(coords[1]),
						accuracy: 5.0
					}
				}
			}
			
			const result = await inspectionStore.createInspection(inspectionData)
			
			if (result.success) {
				uni.showToast({
					title: '检查已创建',
					icon: 'success'
				})
				
				// 跳转到检查清单页面
				uni.redirectTo({
					url: `/pages/inspection/checklist?inspectionId=${result.data.id}`
				})
			} else {
				throw new Error(result.message || '创建检查失败')
			}
			
		} catch (error) {
			console.error('创建检查失败:', error)
			uni.showToast({
				title: '创建失败',
				icon: 'error'
			})
		}
	}
	
	const loadMore = async () => {
		if (!hasMore.value || loading.value) return
		
		loadMoreStatus.value = 'loading'
		page.value++
		await loadSites()
	}
	
	const onSearch = () => {
		// 搜索逻辑由计算属性自动处理
	}
	
	const clearSearch = () => {
		searchKeyword.value = ''
	}
	
	const showFilterModal = () => {
		showFilter.value = true
	}
	
	const hideFilterModal = () => {
		showFilter.value = false
	}
	
	const toggleFilter = (type, value) => {
		const filterArray = filters.value[type]
		const index = filterArray.indexOf(value)
		
		if (index > -1) {
			filterArray.splice(index, 1)
		} else {
			filterArray.push(value)
		}
	}
	
	const onDistanceChange = (e) => {
		filters.value.maxDistance = e.detail.value
	}
	
	const resetFilters = () => {
		filters.value = {
			status: [],
			operator: [],
			maxDistance: 10
		}
	}
	
	const applyFilters = () => {
		hideFilterModal()
		// 过滤逻辑由计算属性自动处理
	}
	
	const goBack = () => {
		uni.navigateBack()
	}
	
	// 工具函数
	const getInspectionTypeText = (type) => {
		const typeMap = {
			opening: '新站点设备安装',
			installation: '安装检查', // 保留兼容性
			maintenance: '维护检查'
		}
		return typeMap[type] || '检查'
	}
	
	const getSiteStatusClass = (status) => {
		const classMap = {
			planning: 'status-planning',
			construction: 'status-construction',
			operational: 'status-operational',
			maintenance: 'status-maintenance',
			assigned: 'status-assigned',
			under_construction: 'status-construction',
			pending_acceptance: 'status-pending'
		}
		return classMap[status] || 'status-default'
	}
	
	const getSiteStatusText = (status) => {
		const statusMap = {
			planning: '规划中',
			construction: '建设中',
			operational: '运行中',
			maintenance: '维护中',
			assigned: '已分配',
			under_construction: '施工中',
			pending_acceptance: '待验收'
		}
		return statusMap[status] || '未知'
	}
	
	const formatCoordinates = (coordinates) => {
		if (!coordinates) return ''
		const coords = coordinates.split(',')
		if (coords.length === 2) {
			const lat = parseFloat(coords[0]).toFixed(6)
			const lon = parseFloat(coords[1]).toFixed(6)
			return `${lat}, ${lon}`
		}
		return coordinates
	}
	
	const formatDistance = (distance) => {
		if (distance < 1000) {
			return `${Math.round(distance)}m`
		} else {
			return `${(distance / 1000).toFixed(1)}km`
		}
	}
	
	const formatDate = (dateStr) => {
		if (!dateStr) return ''
		const date = new Date(dateStr)
		return date.toLocaleDateString('zh-CN')
	}
</script>

<style scoped>
	.site-select-container {
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
		font-size: 36rpx;
		font-weight: bold;
		flex: 1;
		text-align: center;
	}
	
	.navbar-right {
		width: 60rpx;
		display: flex;
		justify-content: flex-end;
	}
	
	.inspection-type {
		font-size: 24rpx;
		padding: 8rpx 16rpx;
		background: rgba(255, 255, 255, 0.2);
		border-radius: 16rpx;
		white-space: nowrap;
	}
	
	/* 搜索和筛选 */
	.search-container {
		display: flex;
		padding: 20rpx;
		gap: 20rpx;
		background: white;
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.search-box {
		flex: 1;
		display: flex;
		align-items: center;
		background: #f8f9fa;
		border-radius: 25rpx;
		padding: 0 20rpx;
		height: 70rpx;
	}
	
	.search-icon {
		font-size: 28rpx;
		color: #999;
		margin-right: 15rpx;
	}
	
	.search-input {
		flex: 1;
		height: 100%;
		font-size: 28rpx;
		color: #333;
	}
	
	.clear-button {
		width: 40rpx;
		height: 40rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-left: 10rpx;
	}
	
	.clear-icon {
		font-size: 32rpx;
		color: #999;
	}
	
	.filter-button {
		display: flex;
		align-items: center;
		gap: 10rpx;
		padding: 0 20rpx;
		background: #007bff;
		color: white;
		border-radius: 25rpx;
		height: 70rpx;
		white-space: nowrap;
	}
	
	.filter-icon {
		font-size: 28rpx;
	}
	
	.filter-text {
		font-size: 26rpx;
	}
	
	.filter-count {
		font-size: 22rpx;
		opacity: 0.8;
	}
	
	/* 站点列表 */
	.site-list {
		flex: 1;
		padding: 0 20rpx;
	}
	
	.site-item {
		background: white;
		border-radius: 20rpx;
		margin: 15rpx 0;
		padding: 30rpx;
		box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);
		transition: transform 0.2s ease;
	}
	
	.site-item:active {
		transform: scale(0.98);
	}
	
	.site-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 20rpx;
	}
	
	.site-name {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 8rpx;
	}
	
	.site-code {
		font-size: 26rpx;
		color: #666;
	}
	
	.site-status {
		padding: 8rpx 16rpx;
		border-radius: 15rpx;
		font-size: 24rpx;
	}
	
	.status-planning {
		background: #e7f3ff;
		color: #1890ff;
	}
	
	.status-assigned {
		background: #e3f2fd;
		color: #1976d2;
	}
	
	.status-construction {
		background: #fff3cd;
		color: #856404;
	}
	
	.status-pending {
		background: #f8d7da;
		color: #721c24;
	}
	
	.status-operational {
		background: #d4edda;
		color: #155724;
	}
	
	.status-maintenance {
		background: #ffebcc;
		color: #cc7a00;
	}
	
	.site-details {
		margin-bottom: 20rpx;
	}
	
	.detail-row {
		display: flex;
		align-items: center;
		margin-bottom: 12rpx;
		gap: 15rpx;
	}
	
	.detail-icon {
		font-size: 26rpx;
		width: 40rpx;
	}
	
	.detail-text {
		font-size: 26rpx;
		color: #666;
		flex: 1;
	}
	
	.site-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 20rpx;
		border-top: 1rpx solid #f0f0f0;
	}
	
	.site-distance {
		display: flex;
		align-items: center;
		gap: 10rpx;
	}
	
	.distance-icon {
		font-size: 24rpx;
		color: #007bff;
	}
	
	.distance-text {
		font-size: 24rpx;
		color: #007bff;
		font-weight: 500;
	}
	
	.select-arrow {
		font-size: 32rpx;
		color: #007bff;
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
	
	/* 筛选弹窗 */
	.filter-overlay {
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
	
	.filter-modal {
		background: white;
		border-radius: 20rpx;
		width: 100%;
		max-width: 700rpx;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
	}
	
	.filter-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 30rpx;
		border-bottom: 1rpx solid #f0f0f0;
	}
	
	.filter-title {
		font-size: 36rpx;
		font-weight: bold;
		color: #333;
	}
	
	.filter-close {
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
	
	.filter-content {
		flex: 1;
		padding: 30rpx;
		overflow-y: auto;
	}
	
	.filter-section {
		margin-bottom: 40rpx;
	}
	
	.section-title {
		font-size: 30rpx;
		font-weight: bold;
		color: #333;
		margin-bottom: 20rpx;
		display: block;
	}
	
	.filter-options {
		display: flex;
		flex-wrap: wrap;
		gap: 15rpx;
	}
	
	.filter-option {
		padding: 15rpx 25rpx;
		background: #f8f9fa;
		color: #666;
		border-radius: 25rpx;
		font-size: 26rpx;
		transition: all 0.3s ease;
	}
	
	.filter-option.active {
		background: #007bff;
		color: white;
	}
	
	.distance-slider {
		margin-top: 20rpx;
	}
	
	.distance-value {
		font-size: 26rpx;
		color: #007bff;
		text-align: center;
		display: block;
		margin-top: 15rpx;
	}
	
	.filter-actions {
		display: flex;
		gap: 20rpx;
		padding: 30rpx;
		border-top: 1rpx solid #f0f0f0;
	}
	
	.filter-reset {
		flex: 1;
		padding: 25rpx;
		background: #6c757d;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	.filter-apply {
		flex: 1;
		padding: 25rpx;
		background: #007bff;
		color: white;
		border: none;
		border-radius: 15rpx;
		font-size: 30rpx;
	}
	
	/* 加载更多 */
	.load-more {
		padding: 40rpx;
	}
</style>