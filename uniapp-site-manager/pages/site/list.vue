<template>
	<view class="site-list-container" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('site.list')" variant="brand">
			<template #right>
				<view class="u-nav-btn u-nav-btn--brand" @click="toggleSearch">
					<uni-icons :type="showSearch ? 'closeempty' : 'search'" size="36rpx" color="#fff" />
				</view>
			</template>
		</CustomNavbar>

		<!-- 可折叠搜索框 -->
		<view class="search-container" :class="{ 'search-container-open': showSearch }">
			<view class="search-box">
				<uni-icons class="search-icon" type="search" size="32rpx" color="#6b7280" />
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
				<uni-icons v-if="searchText" class="clear-icon" type="clear" size="32rpx" color="#6b7280" @click="clearSearch" />
			</view>
		</view>

			<view class="filter-tabs">
				<view class="filter-tabs-wrapper">
					<scroll-view class="filter-tabs-scroll" scroll-x :show-scrollbar="false">
						<view class="filter-tabs-row">
							<view
								class="tab"
								:class="{ active: currentFilter === filter.value }"
								v-for="filter in visibleFilters"
								:key="filter.value"
								@click="selectFilter(filter.value)"
							>
								{{ filter.label }}
							</view>
						</view>
					</scroll-view>
					<view class="filter-more" @click="openStatusFilterSheet">
						<text class="filter-more-text">{{ $t('common.more') }}</text>
						<text class="filter-more-icon">⋯</text>
					</view>
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
				<!-- 骨架屏加载状态 -->
				<template v-if="isLoading">
					<SkeletonCard mode="list" />
					<SkeletonCard mode="list" />
					<SkeletonCard mode="list" />
				</template>
				
				<!-- 空状态 -->
				<EmptyState 
					v-else-if="filteredSites.length === 0"
					:icon="searchText || currentFilter !== 'all' ? '🔍' : '📍'"
					:title="searchText || currentFilter !== 'all' ? $t('messages.noSearchResults') : $t('messages.noData')"
					:description="searchText ? $t('messages.tryDifferentKeyword') : $t('site.noSites')"
					:actionText="searchText ? $t('common.clearSearch') : ''"
					@action="clearSearch"
				/>
				
				<!-- 实际内容 -->
				<template v-else>
					<view
						class="site-item u-pressable-subtle"
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
							<uni-icons class="detail-icon" type="location" size="28rpx" color="#6b7280" />
							<text class="detail-text">{{ site.address }}</text>
						</view>
						
						<view class="detail-item" v-if="site.site_type">
							<uni-icons class="detail-icon" type="home" size="28rpx" color="#6b7280" />
							<text class="detail-text">{{ getSiteTypeText(site.site_type) }}</text>
						</view>
						
						<view class="detail-item" v-if="site.contact_person">
							<uni-icons class="detail-icon" type="person" size="28rpx" color="#6b7280" />
							<text class="detail-text">{{ site.contact_person }}</text>
						</view>
					</view>
					
					<view class="site-actions">
						<text class="action-time">{{ formatTime(site.updated_at) }}</text>
						<text class="action-arrow">›</text>
					</view>
					</view>
				</template>
			</view>

			<!-- 预留底部空间，避免内容被自定义 tabbar 遮挡 -->
			<view class="tabbar-spacer" />
		</scroll-view>
		
		<!-- 浮动添加按钮 -->
		<view class="fab" @click="addSite" v-if="canAddSite">
			<text class="fab-icon">+</text>
		</view>

    <!-- 自定义底部导航栏 -->
    <custom-tabbar />
    
    <!-- 版本更新弹窗 -->
    <UpdateDialog 
      v-model:visible="showUpdateDialog"
      @close="handleDialogClose"
      @installed="handleUpdateInstalled"
    />
	</view>
</template>

<script setup>
	import { ref, computed, onMounted, watch, getCurrentInstance } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useWorkOrderStore } from '@/stores/workorder'
	import { useLanguageStore } from '@/stores/language'
	import { useUpgradeStore } from '@/stores/upgrade'
	import { createDebouncedTracker } from '@/utils/operationTrack.js'
	import { guardFeatureAccess, resolvePermissionDeniedMessage } from '@/utils/feature-access.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import SkeletonCard from '@/components/SkeletonCard.vue'
	import EmptyState from '@/components/EmptyState.vue'
	import UpdateDialog from '@/components/UpdateDialog.vue'

	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const workOrderStore = useWorkOrderStore()
	const languageStore = useLanguageStore()
	const upgradeStore = useUpgradeStore()

	const searchText = ref('')
	const currentFilter = ref('all')
	const showSearch = ref(false)
	const refreshing = ref(false)
	const isLoading = ref(true)
	
	// 版本更新弹窗状态
	const showUpdateDialog = ref(false)
	
	// 监听全局弹窗状态
	watch(() => upgradeStore.shouldShowDialog, (newVal) => {
		if (newVal) {
			showUpdateDialog.value = true
		}
	}, { immediate: true })
	
	const handleDialogClose = () => {
		showUpdateDialog.value = false
		upgradeStore.hideDialog()
	}
	
	const handleUpdateInstalled = () => {
		showUpdateDialog.value = false
		upgradeStore.hideDialog()
	}

	const trackSearchDebounced = createDebouncedTracker(800)
	const trackSearch = () => {
		trackSearchDebounced({
			module: '站点管理',
			action: '查询',
			object_type: '站点',
			data: {
				keyword: searchText.value || undefined,
				status: currentFilter.value !== 'all' ? currentFilter.value : undefined,
			}
		})
	}

	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const allFilters = computed(() => {
		// 依赖语言，确保切换语言后能更新显示
		const _ = languageStore.currentLocale
		return [
			{ label: $t('common.all'), value: 'all' },
			{ label: $t('site.surveyPending'), value: 'survey_pending' },
			{ label: $t('site.planning'), value: 'planning' },
			{ label: $t('site.planned'), value: 'planned' },
			{ label: $t('site.construction'), value: 'construction' },
			{ label: $t('site.pendingOnline'), value: 'pending_online' },
			{ label: $t('site.onlinePendingActivation'), value: 'online_pending_activation' },
			{ label: $t('site.operational'), value: 'operational' },
			{ label: $t('site.maintenance'), value: 'maintenance' },
		]
	})

	const visibleFilters = computed(() => {
		const baseValues = ['all', 'survey_pending', 'planning', 'construction', 'operational', 'maintenance']
		const current = currentFilter.value
		const values = [...baseValues]

		if (current && current !== 'all' && !values.includes(current)) {
			values.splice(1, 0, current)
			if (values.length > baseValues.length) values.pop()
		}

		const filterMap = new Map(allFilters.value.map(f => [f.value, f]))
		return values.map(v => filterMap.get(v)).filter(Boolean)
	})

	const openStatusFilterSheet = () => {
		const items = allFilters.value
		uni.showActionSheet({
			title: $t('messages.filterSiteStatus'),
			itemList: items.map(i => i.label),
			success: (res) => {
				const selected = items[res.tapIndex]
				if (!selected) return
				selectFilter(selected.value)
			}
		})
	}
	
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
				(site.site_name || '').toLowerCase().includes(text) ||
				(site.site_code || '').toLowerCase().includes(text)
			)
		}

		return sites
	})
	
		const canAddSite = computed(() => userStore.hasPermission('sites:create:write'))
		const ensureSitesAccess = () => guardFeatureAccess({
			userStore,
			feature: 'sites',
			deniedMessage: resolvePermissionDeniedMessage(userStore, $t),
			redirectUrl: '/pages/home/home',
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
			'survey_pending': 'status-survey-pending',
			'planning': 'status-planning',
			'planned': 'status-planned',
			'construction': 'status-construction', 
			'pending_online': 'status-pending-online',
			'online_pending_activation': 'status-online-pending-activation',
			'operational': 'status-operational',
			'maintenance': 'status-maintenance'
		}
		return classMap[status] || 'status-default'
	}
	
	// 获取状态文本
	const getStatusText = (status) => {
		const statusMap = {
			'survey_pending': $t('site.surveyPending'),
			'planning': $t('site.planning'),
			'planned': $t('site.planned'),
			'construction': $t('site.construction'),
			'pending_online': $t('site.pendingOnline'),
			'online_pending_activation': $t('site.onlinePendingActivation'),
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
		const locale = languageStore.currentLocaleTag
		
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
			if (!ensureSitesAccess()) {
				if (showLoading) refreshing.value = false
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
			isLoading.value = false
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

	// 记录搜索/筛选条件（防抖，避免输入过程产生大量日志）
	watch([searchText, currentFilter], () => {
		trackSearch()
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
		height: 100vh;
		background-color: var(--bg-page);
		display: flex;
		flex-direction: column;
		overflow: hidden;
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
			background: var(--bg-elevated);
			box-shadow: var(--shadow-card);
		}

		.filter-tabs-wrapper {
			position: relative;
		}

		.filter-tabs-scroll {
			white-space: nowrap;
		}

		.filter-tabs-row {
			display: flex;
			gap: 12rpx;
			padding: 16rpx 140rpx 16rpx 24rpx;
		}

		.filter-more {
			position: absolute;
			right: 0;
			top: 0;
			height: 100%;
			display: flex;
			align-items: center;
			padding: 0 20rpx;
			background: var(--bg-elevated);
			border-left: 1rpx solid var(--border-soft);
		}

		.filter-more-text {
			font-size: 24rpx;
			color: #6b7280;
			margin-right: 8rpx;
		}

		.filter-more-icon {
			font-size: 32rpx;
			color: #6b7280;
			line-height: 1;
		}

		.tab {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			flex-shrink: 0;
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
				box-shadow: 0 2rpx 8rpx rgba(var(--color-primary-rgb), 0.24);
			}
		}
	
	// 滚动容器
	.sites-scroll {
		flex: 1;
		height: 0;
		min-height: 0;
	}

	.tabbar-spacer {
		height: calc(64px + env(safe-area-inset-bottom));
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

			&.status-default {
				background: #f3f4f6;
				color: #6b7280;
			}

			&.status-survey-pending {
				background: #e0f2fe;
				color: #0369a1;
			}

			&.status-planned {
				background: #ede9fe;
				color: #6d28d9;
			}

			&.status-pending-online {
				background: #ffedd5;
				color: #c2410c;
			}

			&.status-online-pending-activation {
				background: #ccfbf1;
				color: #0f766e;
			}
			
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
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32rpx;
		margin-right: 12rpx;
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
		box-shadow: 0 4px 16px rgba(var(--color-primary-rgb), 0.24);
		z-index: 100;
	}

	.fab-icon {
		font-size: 48rpx;
		color: #fff;
		font-weight: 300;
	}
</style>
