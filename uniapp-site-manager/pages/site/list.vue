<template>
	<view class="site-list-container" :key="languageStore.currentLocale">
		<!-- 搜索和过滤 -->
		<view class="search-filter">
			<view class="search-box">
				<input 
					class="search-input"
					type="text" 
					:placeholder="$t('site.searchPlaceholder')"
					v-model="searchText"
					@input="handleSearch"
				/>
			</view>
			
			<view class="filter-tabs">
				<view 
					class="filter-tab"
					:class="{ active: currentFilter === filter.value }"
					v-for="filter in filters.value"
					:key="filter.value"
					@click="selectFilter(filter.value)"
				>
					{{ filter.label }}
				</view>
			</view>
		</view>
		
		<!-- 站点列表 -->
		<view class="site-list">
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
			
			<!-- 空状态 -->
			<view class="empty-state" v-if="filteredSites.length === 0 && !siteStore.loading">
				<text class="empty-icon">📍</text>
				<text class="empty-text">{{ $t('messages.noData') }}</text>
			</view>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-container" v-if="siteStore.loading">
			<uni-load-more status="loading"></uni-load-more>
		</view>
		
		<!-- 浮动添加按钮 -->
		<view class="fab" @click="addSite" v-if="canAddSite">
			<text class="fab-icon">+</text>
		</view>
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
	
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	
	const filters = computed(() => [
		{ label: $t('common.all'), value: 'all' },
		{ label: $t('site.planning'), value: 'planning' },
		{ label: $t('site.construction'), value: 'construction' },
		{ label: $t('site.operational'), value: 'operational' },
		{ label: $t('site.maintenance'), value: 'maintenance' }
	])
	
	// 过滤后的站点列表
	const filteredSites = computed(() => {
		let sites = siteStore.sites || []

		// inspector角色：只显示工单关联的站点
		const userRole = userStore.userInfo?.role
		if (userRole === 'inspector') {
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
	
	// 选择过滤器
	const selectFilter = (filterValue) => {
		currentFilter.value = filterValue
	}
	
	// 处理搜索
	const handleSearch = () => {
		// 实时搜索已通过computed实现
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
		
		if (diff < 86400000) { // 24小时内
			return date.toLocaleTimeString('zh-CN', { 
				hour: '2-digit', 
				minute: '2-digit' 
			})
		}
		
		return date.toLocaleDateString('zh-CN', {
			month: '2-digit',
			day: '2-digit'
		})
	}
	
	// 加载数据
	const loadData = async () => {
		if (!userStore.isLoggedIn) {
			uni.reLaunch({
				url: '/pages/login/login'
			})
			return
		}

		try {
			const userRole = userStore.userInfo?.role

			// inspector角色需要先加载工单，用于过滤站点
			if (userRole === 'inspector') {
				await workOrderStore.getMyWorkOrders()
			}

			// 加载站点列表（所有角色都可以访问API）
			await siteStore.getSites()
		} catch (error) {
			console.error('Load sites error:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		}
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
	}
	
	// 搜索和过滤
	.search-filter {
		background: var(--bg-elevated);
		padding: 16px;
		border-bottom: 1px solid var(--border-soft);
	}
	
	.search-box {
		margin-bottom: 16px;
	}
	
	.search-input {
		width: 100%;
		height: 40px;
		padding: 0 16px;
		background: #fafafa;
		border: 1px solid var(--border-color);
		border-radius: 20px;
		font-size: 14px;
		
		&:focus {
			border-color: var(--color-primary);
			background: #fff;
		}
	}
	
	.filter-tabs {
		display: flex;
		gap: 8px;
	}
	
	.filter-tab {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 44px; /* iOS touch target */
		padding: 0 16px;
		background: #f8f9fa;
		border-radius: 18px;
		font-size: 14px;
		color: #6b7280;
		white-space: nowrap;
		transition: background-color .2s ease, color .2s ease;
		
		&.active {
			background: var(--color-primary);
			color: #fff;
		}
	}
	
	// 站点列表
	.site-list {
		padding: 16px;
	}
	
	.site-item {
		background: var(--bg-elevated);
		border-radius: var(--radius-md);
		padding: 16px;
		margin-bottom: 12px;
		box-shadow: var(--shadow-card);
		transition: transform .1s ease;
	}
	
	.site-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 12px;
	}
	
	.site-info {
		flex: 1;
	}
	
	.site-name {
		font-size: 16px;
		font-weight: 600;
		color: var(--text-primary);
		display: block;
		margin-bottom: 4px;
	}
	
	.site-code { font-size: 12px; color: var(--text-secondary); }
	
	.site-status {
		padding: 4px 12px;
		border-radius: 12px;
		font-size: 12px;
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
		margin-bottom: 12px;
	}
	
	.detail-item {
		display: flex;
		align-items: center;
		margin-bottom: 6px;
		
		&:last-child {
			margin-bottom: 0;
		}
	}
	
	.detail-icon {
		width: 16px;
		margin-right: 8px;
		font-size: 12px;
	}
	
	.detail-text { font-size: 13px; color: #4b5563; flex: 1; }
	
	.site-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 12px;
		border-top: 1px solid var(--border-soft);
	}
	
	.action-time { font-size: 12px; color: #9ca3af; }
	
	.action-arrow { font-size: 18px; color: #d1d5db; }
	
	// 空状态
	.empty-state { text-align: center; padding: 60px 20px; }
	
	.empty-icon { font-size: 48px; display: block; margin-bottom: 16px; opacity: 0.3; }
	
	.empty-text { font-size: 14px; color: #9ca3af; }
	
	// 加载状态
	.loading-container { padding: 20px; text-align: center; }
	
	// 浮动按钮
	.fab {
		position: fixed;
		bottom: calc(100px + env(safe-area-inset-bottom));
		right: 20px;
		width: 56px;
		height: 56px;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 4px 16px rgba(249, 115, 22, 0.28);
		z-index: 100;
	}
	
	.fab-icon { font-size: 24px; color: #fff; font-weight: 300; }
</style>