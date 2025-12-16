<template>
	<view class="site-list-container" :key="languageStore.currentLocale">
		<!-- 自定义导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<text class="navbar-title">{{ $t('site.list') }}</text>
				<view class="navbar-actions">
					<view class="action-btn" @click="toggleSearch">
						<text class="action-icon">{{ showSearch ? '✕' : '🔍' }}</text>
					</view>
				</view>
			</view>
		</view>

		<!-- 可折叠搜索框 -->
		<view class="search-container" :class="{ 'search-container-open': showSearch }">
			<view class="search-box">
				<text class="search-icon">🔍</text>
				<input
					class="search-input"
					v-model="searchText"
					:placeholder="$t('site.searchPlaceholder')"
					@input="onSearchInput"
					@confirm="handleSearch"
					@blur="handleSearchBlur"
					confirm-type="search"
					:focus="showSearch"
				/>
				<text v-if="searchText" class="clear-icon" @click="clearSearch">✕</text>
			</view>
		</view>

		<view class="filter-tabs">
			<view
				class="tab"
				:class="{ active: currentFilter === filter.value }"
				v-for="filter in filters"
				:key="filter.value"
				@click="selectFilter(filter.value)"
			>
				{{ filter.label }}
			</view>
		</view>

		<scroll-view
			class="sites-scroll"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<!-- 站点列表 -->
			<view class="site-list">
				<!-- 空状态提示 - 只在有搜索或筛选条件时显示 -->
				<view v-if="filteredSites.length === 0 && (searchText || currentFilter !== 'all')" class="empty-state">
					<text class="empty-icon">📭</text>
					<text class="empty-text">{{ $t('messages.noData') }}</text>
				</view>
				<view
					class="site-item"
					v-for="site in filteredSites"
					:key="site.id"
					@click="viewSiteDetail(site)"
				>
				<view class="site-header">
					<view class="site-info">
						<text class="site-name">{{ site.site_name }}</text>
						<text class="site-code">{{ site.site_code }}</text>
					</view>
					<view class="site-status" :class="getStatusClass(site.status)">
						{{ getStatusText(site.status) }}
					</view>
				</view>
				
				<view class="site-details">
					<view class="detail-item" v-if="site.address">
						<text class="detail-icon">📍</text>
						<text class="detail-text">{{ site.address }}</text>
					</view>
					
					<view class="detail-item" v-if="site.site_type">
						<text class="detail-icon">🏗️</text>
						<text class="detail-text">{{ getSiteTypeText(site.site_type) }}</text>
					</view>
					
					<view class="detail-item" v-if="site.contact_person">
						<text class="detail-icon">👤</text>
						<text class="detail-text">{{ site.contact_person }}</text>
					</view>
				</view>
				
				<view class="site-actions">
					<text class="action-time">{{ formatTime(site.updated_at) }}</text>
					<text class="action-arrow">›</text>
				</view>
			</view>

				<!-- 加载状态 -->
				<view class="loading-container" v-if="siteStore.loading">
					<uni-load-more status="loading"></uni-load-more>
				</view>
			</view>
		</scroll-view>
		
		<!-- 浮动添加按钮 -->
		<view class="fab" @click="addSite" v-if="canAddSite">
			<text class="fab-icon">+</text>
		</view>

    <!-- 自定义底部导航栏 -->
    <custom-tabbar />
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, watch, getCurrentInstance } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useWorkOrderStore } from '@/stores/workorder'
	import { useLanguageStore } from '@/stores/language'

	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const workOrderStore = useWorkOrderStore()
	const languageStore = useLanguageStore()

	const searchText = ref('')
	const currentFilter = ref('all')
	const showSearch = ref(false)
	const refreshing = ref(false)

	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const filters = ref([
		{ label: $t('common.all'), value: 'all' },
		{ label: $t('site.planning'), value: 'planning' },
		{ label: $t('site.construction'), value: 'construction' },
		{ label: $t('site.operational'), value: 'operational' },
		{ label: $t('site.maintenance'), value: 'maintenance' }
	])
	
	// 过滤后的站点列表
	const filteredSites = computed(() => {
		let sites = siteStore.sites || []

		// inspector和surveyor角色：只显示工单关联的站点
		const userRole = userStore.userInfo?.role
		if (userRole === 'inspector' || userRole === 'surveyor') {
			// 获取工单关联的站点ID集合
			const workOrderSiteIds = new Set(
				(workOrderStore.list || [])
					.map(wo => wo.site_id)
					.filter(id => id)
			)

			// 只保留工单关联的站点
			sites = sites.filter(site => workOrderSiteIds.has(site.id))
		}

		// 按状态过滤
		if (currentFilter.value !== 'all') {
			sites = sites.filter(site => site.status === currentFilter.value)
		}

		// 按搜索文本过滤
		if (searchText.value) {
			const text = searchText.value.toLowerCase()
			sites = sites.filter(site =>
				site.site_name.toLowerCase().includes(text) ||
				site.site_code.toLowerCase().includes(text)
			)
		}

		return sites
	})
	
	// 是否可以添加站点（只有管理员和经理可以）
	const canAddSite = computed(() => {
		const role = userStore.userInfo?.role
		return role === 'admin' || role === 'manager'
	})

	// 实时搜索（防抖处理）
	const onSearchInput = () => {
		// 实时搜索已通过computed实现
	}

	// 执行搜索
	const handleSearch = () => {
		// 实时搜索已通过computed实现
	}

	// 清除搜索
	const clearSearch = () => {
		searchText.value = ''
	}

	// 切换搜索显示状态
	const toggleSearch = () => {
		showSearch.value = !showSearch.value
	}

	// 搜索框失去焦点时的处理
	const handleSearchBlur = () => {
		// 如果没有搜索内容，延迟收起搜索框
		if (!searchText.value.trim()) {
			setTimeout(() => {
				showSearch.value = false
			}, 200)
		}
	}

	// 选择过滤器
	const selectFilter = (filterValue) => {
		currentFilter.value = filterValue
	}
	
	// 查看站点详情
	const viewSiteDetail = (site) => {
		uni.navigateTo({
			url: `/pages/site/detail?id=${site.id}`
		})
	}
	
	// 添加站点
	const addSite = () => {
		uni.showModal({
			title: $t('site.addSite'),
			content: $t('messages.featureInDevelopment'),
			showCancel: false
		})
	}
	
	// 获取状态样式类
	const getStatusClass = (status) => {
		const classMap = {
			'planning': 'status-planning',
			'construction': 'status-construction', 
			'operational': 'status-operational',
			'maintenance': 'status-maintenance'
		}
		return classMap[status] || 'status-default'
	}
	
	// 获取状态文本
	const getStatusText = (status) => {
		const statusMap = {
			'planning': $t('site.planning'),
			'construction': $t('site.construction'),
			'operational': $t('site.operational'),
			'maintenance': $t('site.maintenance')
		}
		return statusMap[status] || status
	}
	
	// 获取站点类型文本
	const getSiteTypeText = (type) => {
		const typeMap = {
			'base_station': $t('site.baseStation'),
			'tower': $t('site.tower'),
			'indoor': $t('site.indoor'),
			'micro': $t('site.micro')
		}
		return typeMap[type] || type
	}
	
	// 格式化时间
	const formatTime = (timeStr) => {
		const date = new Date(timeStr)
		const now = new Date()
		const diff = now - date
		const locale = languageStore.currentLocale === 'zh' ? 'zh-CN' : 'en-US'
		
		if (diff < 86400000) { // 24小时内
			return date.toLocaleTimeString(locale, { 
				hour: '2-digit', 
				minute: '2-digit' 
			})
		}
		
		return date.toLocaleDateString(locale, {
			month: '2-digit',
			day: '2-digit'
		})
	}
	
	// 加载数据
	const loadData = async (showLoading = false) => {
		if (showLoading) {
			refreshing.value = true
		}

		if (!userStore.isLoggedIn) {
			uni.reLaunch({
				url: '/pages/login/login'
			})
			return
		}

		try {
			const userRole = userStore.userInfo?.role

			// inspector和surveyor角色需要先加载工单，用于过滤站点
			if (userRole === 'inspector' || userRole === 'surveyor') {
				await workOrderStore.getMyWorkOrders()
			}

			// 加载站点列表（所有角色都可以访问API）
			await siteStore.getSites()
		} catch (error) {
			console.error('Load sites error:', error)
			uni.showToast({
				title: $t('site.loadFailed'),
				icon: 'error'
			})
		} finally {
			if (showLoading) {
				refreshing.value = false
			}
		}
	}

	// 下拉刷新处理
	const handleRefresh = async () => {
		console.log('🔄 站点列表刷新中...')
		await loadData(true)
		console.log('✅ 站点列表刷新完成')
	}
	
	// 监听语言变化，更新页面标题
	watch(() => languageStore.currentLocale, () => {
		uni.setNavigationBarTitle({
			title: $t('site.list')
		})
	})
	
	onMounted(() => {
		// 动态设置页面标题
		uni.setNavigationBarTitle({
			title: $t('site.list')
		})
		loadData()
	})
</script>

<style lang="scss" scoped>
	.site-list-container {
		min-height: 100vh;
		background-color: var(--bg-page);
		padding-bottom: 80px;
		display: flex;
		flex-direction: column;
	}
	
	// 自定义导航栏
	.custom-navbar {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding: 44rpx 30rpx 20rpx;
		color: #fff;
	}
	
	.navbar-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 88rpx;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
	}

	.navbar-actions {
		display: flex;
		gap: 20rpx;
	}

	.action-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 68rpx;
		height: 68rpx;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.2);
		transition: all 0.3s ease;
	}

	.action-btn:active {
		background: rgba(255, 255, 255, 0.3);
		transform: scale(0.95);
	}

	.action-icon {
		font-size: 40rpx;
	}

	// 搜索框样式 - 可折叠
	.search-container {
		height: 0;
		overflow: hidden;
		opacity: 0;
		transform: translateY(-20rpx);
		transition: all 0.3s ease;
	}

	.search-container-open {
		height: auto;
		opacity: 1;
		transform: translateY(0);
		padding: 16rpx 32rpx;
		background: var(--bg-elevated);
		box-shadow: var(--shadow-card);
		border-bottom: 1rpx solid #f0f0f0;
	}

	.search-box {
		display: flex;
		align-items: center;
		background: #f8f9fa;
		border-radius: 50rpx;
		padding: 0 24rpx;
		height: 80rpx;
	}

	.search-icon {
		font-size: 32rpx;
		margin-right: 16rpx;
		color: #6b7280;
	}

	.search-input {
		flex: 1;
		height: 80rpx;
		font-size: 28rpx;
		color: var(--text-primary);
	}

	.clear-icon {
		font-size: 32rpx;
		color: #6b7280;
		padding: 8rpx;
	}

	// 筛选标签 - 紧凑布局
	.filter-tabs {
		display: flex;
		gap: 12rpx;
		padding: 16rpx 24rpx;
		background: var(--bg-elevated);
		box-shadow: var(--shadow-card);
	}

	.tab {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 68rpx;
		padding: 0 20rpx;
		border-radius: 20rpx;
		background: #f8f9fa;
		color: #6b7280;
		font-size: 26rpx;
		transition: all 0.3s ease;

		&.active {
			background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
			color: #fff;
			box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.28);
		}
	}
	
	// 滚动容器
	.sites-scroll {
		height: calc(100vh - 180rpx);
	}

	// 站点列表
	.site-list {
		padding: 0 20rpx;
	}
	
	.site-item {
		background: var(--bg-elevated);
		margin: 16rpx 0;
		padding: 24rpx;
		border-radius: 24rpx;
		box-shadow: var(--shadow-card);
		transition: transform 0.2s ease;

		&:active { transform: translateY(2rpx); }
	}

	.site-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16rpx;
	}
	
	.site-info {
		flex: 1;
	}
	
	.site-name {
		font-size: 32rpx;
		font-weight: 600;
		color: var(--text-primary);
		margin-right: 16rpx;
	}

	.site-code { font-size: 24rpx; color: var(--text-secondary); }

	.site-status {
		font-size: 24rpx;
		padding: 8rpx 16rpx;
		border-radius: 16rpx;
		font-weight: 500;
		
		&.status-planning {
			background: #f3f4f6;
			color: #6b7280;
		}
		
		&.status-construction {
			background: #fef3c7;
			color: #d97706;
		}
		
		&.status-operational {
			background: #d1fae5;
			color: #059669;
		}
		
		&.status-maintenance {
			background: #fee2e2;
			color: #dc2626;
		}
	}
	
	.site-details {
		margin-bottom: 16rpx;
	}

	.detail-item {
		display: flex;
		align-items: center;
		margin-bottom: 8rpx;

		&:last-child {
			margin-bottom: 0;
		}
	}

	.detail-icon {
		width: 32rpx;
		margin-right: 12rpx;
		font-size: 24rpx;
	}

	.detail-text {
		font-size: 26rpx;
		color: #4b5563;
		flex: 1;
	}

	.site-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 16rpx;
		border-top: 1rpx solid var(--border-soft);
	}

	.action-time {
		font-size: 24rpx;
		color: #9ca3af;
	}

	.action-arrow {
		font-size: 36rpx;
		color: #d1d5db;
	}

	// 空状态提示
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 120rpx 40rpx;
		color: var(--text-secondary);
	}

	.empty-icon {
		font-size: 120rpx;
		margin-bottom: 32rpx;
		opacity: 0.5;
	}

	.empty-text {
		font-size: 28rpx;
		color: var(--text-secondary);
	}

	// 加载状态
	.loading-container {
		padding: 20rpx;
		text-align: center;
	}

	// 浮动按钮
	.fab {
		position: fixed;
		bottom: calc(100rpx + env(safe-area-inset-bottom));
		right: 20px;
		width: 112rpx;
		height: 112rpx;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 4px 16px rgba(249, 115, 22, 0.28);
		z-index: 100;
	}

	.fab-icon {
		font-size: 48rpx;
		color: #fff;
		font-weight: 300;
	}
</style>
