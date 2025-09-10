<template>
	<view class="site-detail-container">
		<view class="site-header">
			<view class="site-basic">
				<text class="site-name">{{ site?.site_name }}</text>
				<text class="site-code">{{ site?.site_code }}</text>
				<view class="site-status" :class="getStatusClass(site?.status)">
					{{ getStatusText(site?.status) }}
				</view>
			</view>
		</view>
		
		<view class="site-content">
			<!-- 基本信息 -->
			<view class="info-section">
				<view class="section-title">基本信息</view>
				<view class="info-grid">
					<view class="info-item">
						<text class="info-label">站点类型</text>
						<text class="info-value">{{ getSiteTypeText(site?.site_type) }}</text>
					</view>
					
					<view class="info-item">
						<text class="info-label">优先级</text>
						<text class="info-value" :class="getPriorityClass(site?.priority)">
							{{ getPriorityText(site?.priority) }}
						</text>
					</view>
					
					<view class="info-item">
						<text class="info-label">联系人</text>
						<text class="info-value">{{ site?.contact_person || '-' }}</text>
					</view>
					
					<view class="info-item">
						<text class="info-label">联系电话</text>
						<text class="info-value">{{ site?.contact_phone || '-' }}</text>
					</view>
				</view>
			</view>
			
			<!-- 位置信息 -->
			<view class="info-section">
				<view class="section-title">位置信息</view>
				<view class="location-info">
					<view class="address-item">
						<text class="address-label">详细地址</text>
						<text class="address-text">{{ site?.address || '-' }}</text>
					</view>
					
					<view class="coordinates" v-if="site?.latitude && site?.longitude">
						<view class="coord-item">
							<text class="coord-label">纬度</text>
							<text class="coord-value">{{ site?.latitude }}</text>
						</view>
						<view class="coord-item">
							<text class="coord-label">经度</text>
							<text class="coord-value">{{ site?.longitude }}</text>
						</view>
					</view>
					
					<button class="location-btn" @click="showLocation" v-if="site?.latitude && site?.longitude">
						<text class="btn-icon">📍</text>
						<text>在地图中查看</text>
					</button>
				</view>
			</view>
			
			<!-- 描述信息 -->
			<view class="info-section" v-if="site?.description">
				<view class="section-title">描述信息</view>
				<text class="description-text">{{ site?.description }}</text>
			</view>
			
			<!-- 操作按钮 -->
			<view class="action-buttons">
				<button class="action-btn primary" @click="startInspection">
					<text class="btn-icon">📷</text>
					<text>现场检查</text>
				</button>
				
				<button class="action-btn secondary" @click="viewHistory">
					<text class="btn-icon">📋</text>
					<text>检查历史</text>
				</button>
				
				<button class="action-btn secondary" @click="editSite" v-if="canEdit">
					<text class="btn-icon">✏️</text>
					<text>编辑站点</text>
				</button>
			</view>
			
			<!-- 最近检查记录 -->
			<view class="info-section">
				<view class="section-header">
					<text class="section-title">最近检查</text>
					<text class="see-all" @click="viewHistory">查看全部</text>
				</view>
				
				<view class="inspection-list">
					<view 
						class="inspection-item"
						v-for="inspection in recentInspections"
						:key="inspection.id"
						@click="viewInspection(inspection)"
					>
						<view class="inspection-info">
							<text class="inspection-type">{{ getInspectionTypeText(inspection.inspection_type) }}</text>
							<text class="inspection-time">{{ formatTime(inspection.created_at) }}</text>
						</view>
						<view class="inspection-status" :class="getInspectionStatusClass(inspection.status)">
							{{ getInspectionStatusText(inspection.status) }}
						</view>
					</view>
					
					<view class="empty-inspections" v-if="recentInspections.length === 0">
						<text>暂无检查记录</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-container" v-if="loading">
			<uni-load-more status="loading"></uni-load-more>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useInspectionStore } from '@/stores/inspection'
	
	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const inspectionStore = useInspectionStore()
	
	const loading = ref(false)
	const siteId = ref(null)
	const recentInspections = ref([])
	
	const site = computed(() => siteStore.currentSite)
	
	// 是否可以编辑
	const canEdit = computed(() => {
		return userStore.userInfo?.role !== 'user' || 
			   site.value?.created_by === userStore.userInfo?.id
	})
	
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
			'planning': '规划中',
			'construction': '建设中',
			'operational': '运营中',
			'maintenance': '维护中'
		}
		return statusMap[status] || status
	}
	
	// 获取站点类型文本
	const getSiteTypeText = (type) => {
		const typeMap = {
			'base_station': '基站',
			'tower': '铁塔',
			'indoor': '室内分布',
			'micro': '微基站'
		}
		return typeMap[type] || type
	}
	
	// 获取优先级样式类
	const getPriorityClass = (priority) => {
		const classMap = {
			'high': 'priority-high',
			'normal': 'priority-normal',
			'low': 'priority-low'
		}
		return classMap[priority] || 'priority-normal'
	}
	
	// 获取优先级文本
	const getPriorityText = (priority) => {
		const priorityMap = {
			'high': '高',
			'normal': '普通',
			'low': '低'
		}
		return priorityMap[priority] || '普通'
	}
	
	// 获取检查类型文本
	const getInspectionTypeText = (type) => {
		const typeMap = {
			'opening': '新站点设备安装',
			'installation': '安装检查',
			'maintenance': '维护检查'
		}
		return typeMap[type] || type
	}
	
	// 获取检查状态样式类
	const getInspectionStatusClass = (status) => {
		const classMap = {
			'pending': 'status-pending',
			'in_progress': 'status-progress',
			'completed': 'status-completed',
			'failed': 'status-failed'
		}
		return classMap[status] || 'status-default'
	}
	
	// 获取检查状态文本
	const getInspectionStatusText = (status) => {
		const statusMap = {
			'pending': '待处理',
			'in_progress': '进行中',
			'completed': '已完成',
			'failed': '失败'
		}
		return statusMap[status] || status
	}
	
	// 格式化时间
	const formatTime = (timeStr) => {
		const date = new Date(timeStr)
		return date.toLocaleDateString('zh-CN', {
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		})
	}
	
	// 显示位置
	const showLocation = () => {
		uni.openLocation({
			latitude: site.value.latitude,
			longitude: site.value.longitude,
			name: site.value.site_name,
			address: site.value.address
		})
	}
	
	// 开始检查
	const startInspection = () => {
		uni.navigateTo({
			url: `/pages/inspection/camera?siteId=${siteId.value}`
		})
	}
	
	// 查看检查历史
	const viewHistory = () => {
		uni.navigateTo({
			url: `/pages/inspection/list?siteId=${siteId.value}`
		})
	}
	
	// 编辑站点
	const editSite = () => {
		uni.showModal({
			title: '编辑站点',
			content: '编辑站点功能正在开发中',
			showCancel: false
		})
	}
	
	// 查看检查详情
	const viewInspection = (inspection) => {
		uni.navigateTo({
			url: `/pages/inspection/detail?id=${inspection.id}`
		})
	}
	
	// 加载站点详情
	const loadSiteDetail = async () => {
		if (!siteId.value) return
		
		loading.value = true
		
		try {
			// 加载站点详情
			await siteStore.getSite(siteId.value)
			
			// 加载相关的检查记录
			const result = await inspectionStore.getInspections({
				site_id: siteId.value
			})
			
			if (result.success) {
				// 取最近5条记录
				recentInspections.value = result.data
					.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
					.slice(0, 5)
			}
		} catch (error) {
			console.error('Load site detail error:', error)
			uni.showToast({
				title: '加载失败',
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	onLoad((options) => {
		siteId.value = options.id
		if (siteId.value) {
			loadSiteDetail()
		} else {
			uni.showToast({
				title: '参数错误',
				icon: 'error'
			})
			setTimeout(() => {
				uni.navigateBack()
			}, 1500)
		}
	})
</script>

<style lang="scss" scoped>
	.site-detail-container {
		min-height: 100vh;
		background-color: #f5f5f5;
	}
	
	// 站点头部
	.site-header {
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 20px;
		color: white;
	}
	
	.site-basic {
		position: relative;
	}
	
	.site-name {
		font-size: 22px;
		font-weight: 600;
		display: block;
		margin-bottom: 4px;
	}
	
	.site-code {
		font-size: 14px;
		opacity: 0.9;
		display: block;
		margin-bottom: 12px;
	}
	
	.site-status {
		position: absolute;
		top: 0;
		right: 0;
		padding: 6px 12px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: 500;
		background: rgba(255, 255, 255, 0.2);
		
		&.status-operational {
			background: rgba(16, 185, 129, 0.2);
		}
		
		&.status-maintenance {
			background: rgba(239, 68, 68, 0.2);
		}
		
		&.status-construction {
			background: rgba(245, 158, 11, 0.2);
		}
		
		&.status-planning {
			background: rgba(107, 114, 128, 0.2);
		}
	}
	
	// 内容区域
	.site-content {
		padding: 0;
	}
	
	.info-section {
		background: white;
		margin-bottom: 12px;
		padding: 20px;
	}
	
	.section-title {
		font-size: 16px;
		font-weight: 600;
		color: #111827;
		margin-bottom: 16px;
	}
	
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
	}
	
	.see-all {
		font-size: 14px;
		color: #f97316;
	}
	
	// 基本信息网格
	.info-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}
	
	.info-item {
		display: flex;
		flex-direction: column;
	}
	
	.info-label {
		font-size: 12px;
		color: #6b7280;
		margin-bottom: 4px;
	}
	
	.info-value {
		font-size: 14px;
		color: #111827;
		
		&.priority-high { color: #dc2626; }
		&.priority-normal { color: #059669; }
		&.priority-low { color: #6b7280; }
	}
	
	// 位置信息
	.location-info {
		
	}
	
	.address-item {
		margin-bottom: 16px;
	}
	
	.address-label {
		font-size: 12px;
		color: #6b7280;
		display: block;
		margin-bottom: 4px;
	}
	
	.address-text {
		font-size: 14px;
		color: #111827;
		line-height: 1.5;
	}
	
	.coordinates {
		display: flex;
		gap: 20px;
		margin-bottom: 16px;
	}
	
	.coord-item {
		flex: 1;
	}
	
	.coord-label {
		font-size: 12px;
		color: #6b7280;
		display: block;
		margin-bottom: 4px;
	}
	
	.coord-value {
		font-size: 14px;
		color: #111827;
		font-family: 'Courier New', monospace;
	}
	
	.location-btn {
		background: #f8f9fa;
		border: 1px solid #e9ecef;
		border-radius: 8px;
		padding: 12px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		font-size: 14px;
		color: #374151;
	}
	
	.btn-icon {
		font-size: 16px;
	}
	
	// 描述信息
	.description-text {
		font-size: 14px;
		color: #374151;
		line-height: 1.6;
	}
	
	// 操作按钮
	.action-buttons {
		display: flex;
		gap: 12px;
		padding: 20px;
		background: white;
		margin-bottom: 12px;
	}
	
	.action-btn {
		flex: 1;
		height: 44px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		font-size: 14px;
		font-weight: 500;
		border: none;
		
		&.primary {
			background: linear-gradient(135deg, #f97316, #fb923c);
			color: white;
		}
		
		&.secondary {
			background: #f8f9fa;
			color: #374151;
			border: 1px solid #e9ecef;
		}
	}
	
	// 检查列表
	.inspection-list {
		
	}
	
	.inspection-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 0;
		border-bottom: 1px solid #f3f4f6;
		
		&:last-child {
			border-bottom: none;
		}
	}
	
	.inspection-info {
		display: flex;
		flex-direction: column;
	}
	
	.inspection-type {
		font-size: 14px;
		color: #111827;
		margin-bottom: 2px;
	}
	
	.inspection-time {
		font-size: 12px;
		color: #6b7280;
	}
	
	.inspection-status {
		padding: 4px 8px;
		border-radius: 6px;
		font-size: 12px;
		
		&.status-pending { background: #fef3c7; color: #d97706; }
		&.status-progress { background: #dbeafe; color: #2563eb; }
		&.status-completed { background: #d1fae5; color: #059669; }
		&.status-failed { background: #fee2e2; color: #dc2626; }
	}
	
	.empty-inspections {
		text-align: center;
		padding: 20px;
		color: #9ca3af;
		font-size: 14px;
	}
	
	// 加载状态
	.loading-container {
		padding: 40px 20px;
		text-align: center;
	}
</style>