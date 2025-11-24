<template>
	<view class="site-detail-container">
		<!-- 自定义导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="navbar-left">
					<view class="nav-button back-button" @click="goBack">
						<text class="nav-icon">←</text>
					</view>
				</view>
				<view class="navbar-center">
					<text class="navbar-title">{{ $t('site.detail') }}</text>
				</view>
				<view class="navbar-right"></view>
			</view>
		</view>
		
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
				<view class="section-title">{{ $t('site.basicInfo') }}</view>
				<view class="info-grid">
					<view class="info-item">
						<text class="info-label">{{ $t('site.type') }}</text>
						<text class="info-value">{{ getSiteTypeText(site?.site_type) }}</text>
					</view>
					
					<view class="info-item">
						<text class="info-label">{{ $t('workorder.priority') }}</text>
						<text class="info-value" :class="getPriorityClass(site?.priority)">
							{{ getPriorityText(site?.priority) }}
						</text>
					</view>
					
					<view class="info-item">
						<text class="info-label">{{ $t('site.contact') }}</text>
						<text class="info-value">{{ site?.contact_person || '-' }}</text>
					</view>
					
					<view class="info-item">
						<text class="info-label">{{ $t('site.contactPhone') }}</text>
						<text class="info-value">{{ site?.contact_phone || '-' }}</text>
					</view>
				</view>
			</view>

			<!-- 设备状态（OMC） -->
			<view class="info-section">
				<view class="section-header">
					<view class="section-title">设备状态（OMC）</view>
					<button class="refresh-btn" @click="loadOmcStatus(true)" :disabled="omcLoading">
						{{ omcLoading ? '刷新中…' : '刷新' }}
					</button>
				</view>
				<view v-if="omcError" class="omc-error">{{ omcError }}</view>
				<view v-else-if="omcStatus?.devices && omcStatus.devices.length" class="device-cards">
					<view class="device-card" v-for="dev in omcStatus.devices" :key="dev.sn">
						<view class="device-header">
							<text class="device-sn">{{ dev.sn }}</text>
							<view class="device-tags">
								<text class="tag" :class="dev.online ? 'tag-online' : 'tag-offline'">{{ dev.online ? '在线' : '离线' }}</text>
								<text class="tag" :class="dev.activated ? 'tag-activated' : 'tag-inactive'">{{ dev.activated ? '已激活' : '未激活' }}</text>
							</view>
						</view>
						<view class="device-meta">
							<text v-if="dev.ever_online" class="meta">曾上线</text>
							<text v-if="dev.ever_activated" class="meta">曾激活</text>
						</view>
					</view>
					<view class="checked-at" v-if="omcStatus.checked_at">最近检测：{{ formatTime(omcStatus.checked_at) }}</view>
				</view>
				<view v-else class="omc-empty">暂无设备状态数据</view>
			</view>
			
			<!-- 位置信息 -->
			<view class="info-section">
				<view class="section-title">{{ $t('site.locationInfo') }}</view>
				<view class="location-info">
					<view class="address-item">
						<text class="address-label">{{ $t('site.detailedAddress') }}</text>
						<text class="address-text">{{ site?.address || '-' }}</text>
					</view>
					
					<view class="coordinates" v-if="site?.latitude && site?.longitude">
						<view class="coord-item">
							<text class="coord-label">{{ $t('site.latitude') }}</text>
							<text class="coord-value">{{ site?.latitude }}</text>
						</view>
						<view class="coord-item">
							<text class="coord-label">{{ $t('site.longitude') }}</text>
							<text class="coord-value">{{ site?.longitude }}</text>
						</view>
					</view>
					
					<button class="location-btn" @click="showLocation" v-if="site?.latitude && site?.longitude">
						<text class="btn-icon">📍</text>
						<text>{{ $t('site.viewOnMap') }}</text>
					</button>
				</view>
			</view>
			
			<!-- 描述信息 -->
			<view class="info-section" v-if="site?.description">
				<view class="section-title">{{ $t('site.description') }}</view>
				<text class="description-text">{{ site?.description }}</text>
			</view>

			<!-- 站点规划信息 -->
			<view class="info-section" v-if="planning">
				<view class="section-header expandable" @click="planningExpanded = !planningExpanded">
					<text class="section-title">站点规划</text>
					<text class="expand-icon">{{ planningExpanded ? '▼' : '▶' }}</text>
				</view>

				<view v-if="planningExpanded" class="planning-content">
					<!-- 基本信息 -->
					<view class="planning-basic">
						<view class="planning-item">
							<text class="planning-label">频段配置</text>
							<text class="planning-value">{{ planning.bands.join(', ') }}</text>
						</view>
						<view class="planning-item">
							<text class="planning-label">扇区数量</text>
							<text class="planning-value">{{ planning.sector_count }} 个</text>
						</view>
						<view class="planning-item" v-if="planning.notes">
							<text class="planning-label">备注</text>
							<text class="planning-value">{{ planning.notes }}</text>
						</view>
					</view>

					<!-- 扇区配置 -->
					<view class="planning-subsection" v-if="planning.sectors && planning.sectors.length > 0">
						<text class="subsection-title">扇区配置</text>
						<view class="sector-list">
							<view class="sector-card" v-for="sector in planning.sectors" :key="sector.sector_index">
								<view class="sector-header">
									<text class="sector-title">扇区 {{ sector.sector_index }}</text>
									<text class="sector-bands">{{ sector.bands.join(', ') }}</text>
								</view>
								<view class="sector-params">
									<view class="param-item">
										<text class="param-label">方位角</text>
										<text class="param-value">{{ sector.azimuth_deg }}°</text>
									</view>
									<view class="param-item">
										<text class="param-label">下倾角</text>
										<text class="param-value">{{ sector.downtilt_deg }}°</text>
									</view>
								</view>
							</view>
						</view>
					</view>

					<!-- 天线端口 -->
					<view class="planning-subsection" v-if="planning.antenna_ports && planning.antenna_ports.length > 0">
						<text class="subsection-title">天线端口</text>
						<view class="port-list">
							<view class="port-item" v-for="(port, index) in planning.antenna_ports" :key="index">
								<view class="port-header">
									<text class="port-label">{{ port.port_label }}</text>
									<text class="port-band">{{ port.band }}</text>
								</view>
								<view class="port-details">
									<text class="port-detail">扇区: {{ port.sector_index }}</text>
									<text class="port-detail" v-if="port.mimo_chain">MIMO: {{ port.mimo_chain }}</text>
									<text class="port-detail" v-if="port.remarks">{{ port.remarks }}</text>
								</view>
							</view>
						</view>
					</view>

					<!-- 交换机端口 -->
					<view class="planning-subsection" v-if="planning.switch_ports && planning.switch_ports.length > 0">
						<text class="subsection-title">交换机端口</text>
						<view class="port-list">
							<view class="port-item" v-for="(port, index) in planning.switch_ports" :key="index">
								<view class="port-header">
									<text class="port-label">{{ port.port_no }}</text>
									<view class="port-tags">
										<text class="port-tag uplink" v-if="port.is_uplink">上行</text>
										<text class="port-tag poe" v-if="port.poe">POE</text>
									</view>
								</view>
								<view class="port-details">
									<text class="port-detail" v-if="port.vlan_ids && port.vlan_ids.length > 0">
										VLAN: {{ port.vlan_ids.join(', ') }}
									</text>
									<text class="port-detail" v-if="port.description">{{ port.description }}</text>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<!-- 最近检查记录 -->
			<view class="info-section">
				<view class="section-title">{{ $t('site.recentInspections') }}</view>
				
				<view class="inspection-list">
					<view
						class="inspection-item"
						v-for="inspection in recentInspections"
						:key="inspection.id"
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
						<text>{{ $t('site.noInspectionRecords') }}</text>
					</view>
				</view>
			</view>
		</view>
		
		<!-- 加载状态 -->
		<view class="loading-container" v-if="loading">
			<uni-load-more status="loading"></uni-load-more>
		</view>
		
		<!-- 地图选择器 -->
		<view class="map-selector-overlay" v-if="showMapSelector" @click="showMapSelector = false">
			<view class="map-selector" @click.stop>
				<view class="selector-title">选择地图</view>
				<view class="map-options">
					<view 
						class="map-option" 
						@click="selectMapType('amap')"
					>
						<view class="option-icon">🗺️</view>
						<view class="option-info">
							<text class="option-name">高德地图</text>
							<text class="option-desc">国内定位精准</text>
						</view>
						<text class="option-arrow">›</text>
					</view>
					<view 
						class="map-option" 
						@click="selectMapType('google')"
					>
						<view class="option-icon">🌏</view>
						<view class="option-info">
							<text class="option-name">谷歌地图</text>
							<text class="option-desc">全球地图覆盖</text>
						</view>
						<text class="option-arrow">›</text>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, computed, getCurrentInstance, onMounted, watch } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useSiteStore } from '@/stores/site'
	import { useInspectionStore } from '@/stores/inspection'
	import { useLanguageStore } from '@/stores/language'
	import { API_ENDPOINTS, buildApiUrl, getAuthHeaders, createRequestConfig } from '@/config/api.js'
	
	const userStore = useUserStore()
	const siteStore = useSiteStore()
	const inspectionStore = useInspectionStore()
	const languageStore = useLanguageStore()
	
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	
	const loading = ref(false)
	const siteId = ref(null)
	const recentInspections = ref([])
	const planning = ref(null)
	const planningExpanded = ref(false)
	const showMapSelector = ref(false)
	const omcStatus = ref(null)
	const omcLoading = ref(false)
	const omcError = ref('')

	const site = computed(() => siteStore.currentSite)

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
			'pending': $t('inspection.pending'),
			'in_progress': $t('inspection.inProgress'),
			'completed': $t('inspection.completed'),
			'failed': $t('inspection.failed')
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
	
	// 返回上一页
	const goBack = () => {
		uni.navigateBack()
	}
	
	// 显示位置
	const showLocation = () => {
		showMapSelector.value = true
	}
	
	// 选择地图类型并跳转
	const selectMapType = (mapType) => {
		showMapSelector.value = false
		uni.navigateTo({
			url: `/pages/map/view?latitude=${site.value.latitude}&longitude=${site.value.longitude}&name=${encodeURIComponent(site.value.site_name)}&address=${encodeURIComponent(site.value.address || '')}&mapType=${mapType}`
		})
	}

	// 加载 OMC 设备状态
	const loadOmcStatus = async (refresh = false) => {
		if (!siteId.value) return
		omcLoading.value = true
		omcError.value = ''
		try {
			const baseUrl = buildApiUrl(API_ENDPOINTS.SITES.OMC_STATUS(siteId.value))
			const url = refresh ? `${baseUrl}?refresh=1` : baseUrl
			const res = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})
			if (res.statusCode === 200) {
				omcStatus.value = res.data
			} else {
				omcError.value = res.data?.detail || '获取设备状态失败'
			}
		} catch (error) {
			console.warn('获取站点设备状态失败:', error)
			omcError.value = '获取设备状态失败'
		} finally {
			omcLoading.value = false
		}
	}

	// 加载站点详情
	const loadSiteDetail = async () => {
		if (!siteId.value) return

		loading.value = true

		try {
			// 所有角色都直接调用API（已放开inspector权限）
			await siteStore.getSite(siteId.value)

			// 加载站点规划信息
			await loadPlanning()

			// 加载 OMC 设备状态（默认不强制刷新）
			await loadOmcStatus(false)

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

	// 加载站点规划信息
	const loadPlanning = async () => {
		try {
			const url = buildApiUrl(API_ENDPOINTS.SITES.PLANNING(siteId.value))
			const response = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token)
				})
			})

			if (response.statusCode === 200) {
				planning.value = response.data
			} else if (response.statusCode === 404) {
				// 没有规划信息，不显示
				planning.value = null
			}
		} catch (error) {
			console.warn('Load planning error:', error)
			// 规划信息加载失败不影响主流程
			planning.value = null
		}
	}
	
	onLoad((options) => {
		siteId.value = options.id
		if (siteId.value) {
			loadSiteDetail()
		} else {
			uni.showToast({
				title: $t('messages.operationFailed'),
				icon: 'error'
			})
			setTimeout(() => {
				uni.navigateBack()
			}, 1500)
		}
	})
	
	// 监听语言变化，更新页面标题
	watch(() => languageStore.currentLocale, () => {
		uni.setNavigationBarTitle({
			title: $t('site.detail')
		})
	})
	
	onMounted(() => {
		// 动态设置页面标题
		uni.setNavigationBarTitle({
			title: $t('site.detail')
		})
	})
</script>

<style lang="scss" scoped>
	.site-detail-container {
		min-height: 100vh;
		background-color: var(--bg-page);
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
		position: relative;
	}
	
	.navbar-left,
	.navbar-right {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	
	.navbar-right {
		justify-content: flex-end;
	}
	
	.nav-button {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 44rpx;
		background: rgba(255, 255, 255, 0.2);
		transition: all 0.3s ease;
	}
	
	.nav-button:active {
		background: rgba(255, 255, 255, 0.3);
		transform: scale(0.95);
	}
	
	.nav-icon {
		font-size: 36rpx;
		color: white;
		font-weight: bold;
	}
	
	.navbar-center {
		position: absolute;
		left: 88rpx;
		right: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		pointer-events: none;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
		color: white;
		text-align: center;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	// 站点头部
	.site-header {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding: 20px;
		color: #fff;
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
		background: var(--bg-elevated);
		margin-bottom: 12px;
		padding: 20px;
		border-radius: var(--radius-md);
		box-shadow: var(--shadow-card);
	}
	
	.section-title { font-size: 16px; font-weight: 600; color: var(--text-primary); margin-bottom: 16px; }
	
.section-header { display: flex; justify-content: space-between; align-items: center; min-height: 44px; margin-bottom: 16px; }
	
	.see-all { font-size: 14px; color: var(--color-primary); }
	
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
	
	.info-label { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
	
	.info-value { font-size: 14px; color: var(--text-primary);
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
	
	.address-label { font-size: 12px; color: #6b7280; display: block; margin-bottom: 4px; }
	
	.address-text { font-size: 14px; color: var(--text-primary); line-height: 1.5; }
	
	.coordinates {
		display: flex;
		gap: 20px;
		margin-bottom: 16px;
	}
	
	.coord-item {
		flex: 1;
	}
	
	.coord-label { font-size: 12px; color: #6b7280; display: block; margin-bottom: 4px; }
	
	.coord-value { font-size: 14px; color: var(--text-primary); font-family: 'Courier New', monospace; }
	
	.location-btn { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 0 14px; gap: 8px; font-size: 14px; color: #374151; }
	
	.btn-icon {
		font-size: 16px;
	}
	
	// 描述信息
	.description-text { font-size: 14px; color: #374151; line-height: 1.6; }

	/* OMC 设备状态 */
	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}
	.refresh-btn {
		padding: 6px 12px;
		background: var(--color-primary);
		color: #fff;
		border: none;
		border-radius: 8px;
		font-size: 13px;
	}
	.refresh-btn:disabled {
		opacity: 0.6;
	}
	.omc-error { color: #f56c6c; font-size: 14px; }
	.omc-empty { color: #909399; font-size: 14px; }
	.device-cards { display: flex; flex-direction: column; gap: 10px; }
	.device-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; background: #fff; }
	.device-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
	.device-sn { font-size: 15px; font-weight: 600; }
	.device-tags { display: flex; gap: 6px; }
	.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
	.tag-online { background: #e6f9f0; color: #2f9e5f; }
	.tag-offline { background: #fdecec; color: #d93030; }
	.tag-activated { background: #e8f5ff; color: #1e80ff; }
	.tag-inactive { background: #f4f4f5; color: #606266; }
	.device-meta { display: flex; gap: 10px; color: #606266; font-size: 13px; }
	.checked-at { margin-top: 6px; font-size: 12px; color: #909399; }

	// 站点规划样式
	.expandable {
		display: flex;
		justify-content: space-between;
		align-items: center;
		cursor: pointer;
		padding: 12px 0;
	}

	.expand-icon {
		font-size: 12px;
		color: #9ca3af;
		transition: transform 0.3s;
	}

	.planning-content {
		margin-top: 16px;
	}

	.planning-basic { background: #f9fafb; border-radius: 8px; padding: 12px; margin-bottom: 16px; }

	.planning-item {
		display: flex;
		justify-content: space-between;
		padding: 8px 0;
		border-bottom: 1px solid #e5e7eb;

		&:last-child {
			border-bottom: none;
		}
	}

	.planning-label {
		font-size: 14px;
		color: #6b7280;
	}

	.planning-value {
		font-size: 14px;
		color: #111827;
		font-weight: 500;
	}

	.planning-subsection {
		margin-bottom: 16px;
	}

	.subsection-title {
		font-size: 15px;
		font-weight: 600;
		color: #111827;
		margin-bottom: 12px;
		display: block;
	}

	// 扇区卡片
	.sector-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.sector-card { background: #f8f9fa; border-radius: 8px; padding: 12px; border-left: 3px solid var(--color-primary); }

	.sector-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}

	.sector-title {
		font-size: 14px;
		font-weight: 600;
		color: #111827;
	}

	.sector-bands { font-size: 12px; color: var(--color-primary-dark); background: #fed7aa; padding: 2px 8px; border-radius: 4px; }

	.sector-params {
		display: flex;
		gap: 16px;
	}

	.param-item {
		display: flex;
		flex-direction: column;
	}

	.param-label {
		font-size: 12px;
		color: #6b7280;
		margin-bottom: 2px;
	}

	.param-value {
		font-size: 14px;
		color: #111827;
		font-weight: 500;
	}

	// 端口列表
	.port-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.port-item { background: #f9fafb; border-radius: 6px; padding: 10px; border: 1px solid #e5e7eb; }

	.port-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 6px;
	}

	.port-label {
		font-size: 14px;
		font-weight: 600;
		color: #111827;
	}

	.port-band {
		font-size: 12px;
		color: #059669;
		background: #d1fae5;
		padding: 2px 8px;
		border-radius: 4px;
	}

	.port-tags {
		display: flex;
		gap: 4px;
	}

	.port-tag {
		font-size: 11px;
		padding: 2px 6px;
		border-radius: 4px;

		&.uplink {
			background: #dbeafe;
			color: #2563eb;
		}

		&.poe {
			background: #d1fae5;
			color: #059669;
		}
	}

	.port-details {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.port-detail {
		font-size: 12px;
		color: #6b7280;
		line-height: 1.4;
	}

	// 检查列表
	.inspection-list {
		
	}
	
	.inspection-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 0;
		border-bottom: 1px solid var(--border-soft);
		
		&:last-child {
			border-bottom: none;
		}
	}
	
	.inspection-info {
		display: flex;
		flex-direction: column;
	}
	
	.inspection-type { font-size: 14px; color: var(--text-primary); margin-bottom: 2px; }
	
	.inspection-time { font-size: 12px; color: #6b7280; }
	
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
	.loading-container { padding: 40px 20px; text-align: center; }
	
	// 地图选择器
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
	
	.map-selector { width: 100%; background: var(--bg-elevated); border-radius: 30rpx 30rpx 0 0; padding: 40rpx 30rpx; animation: slideUp 0.3s ease-out; }
	
	@keyframes slideUp {
		from {
			transform: translateY(100%);
		}
		to {
			transform: translateY(0);
		}
	}
	
	.selector-title { font-size: 32rpx; font-weight: 600; color: var(--text-primary); text-align: center; margin-bottom: 30rpx; }
	
	.map-options {
		display: flex;
		flex-direction: column;
		gap: 20rpx;
	}
	
.map-option { display: flex; align-items: center; gap: 20rpx; min-height: 88rpx; padding: 0 30rpx; background: #f9fafb; border-radius: 20rpx; border: 2rpx solid transparent; transition: all 0.3s ease; &:active { background: #fef3e2; border-color: var(--color-primary); } }
	
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
	
	.option-arrow {
		font-size: 32rpx;
		color: #9ca3af;
		font-weight: bold;
		flex-shrink: 0;
	}
</style>
