<template>
	<view class="sites-map-container">
		<!-- 顶部信息栏 -->
		<view class="map-header">
			<view class="back-btn" @click="goBack">
				<uni-icons class="back-icon" type="back" size="32rpx" color="#fff" />
			</view>
			<view class="location-info">
				<text class="location-name">{{ $t('map.sitesDistributionTitle') }}</text>
				<text class="coordinates">{{ $t('map.totalSitesCount', { count: totalSites }) }}</text>
			</view>
		</view>
		
		<!-- 使用iframe加载瓦片地图 -->
		<view class="map-view">
			<!-- #ifdef H5 -->
			<iframe 
				id="leafletMap"
				ref="leafletMapRef"
				class="map-iframe"
				:src="mapSrc"
				@load="onMapLoad"
			></iframe>
			<!-- #endif -->

			<!-- #ifdef APP-PLUS -->
			<web-view 
				ref="leafletWebViewRef"
				class="map-webview"
				:src="mapSrc"
				:key="mapSrc"
				:webview-styles="appWebviewStyles"
				@load="onWebViewLoad"
				@error="onWebViewError"
				@message="handleWebViewMessage"
			></web-view>
			<!-- #endif -->
		</view>
		
		<!-- 底部站点列表 -->
		<view class="sites-panel" :class="{ collapsed: panelCollapsed }">
			<view class="panel-header" @click="togglePanel">
				<view class="panel-title">
					<text class="title-text">{{ $t('map.siteListTitle') }}</text>
					<text class="count-badge">{{ filteredSites.length }}</text>
				</view>
				<text class="toggle-icon">{{ panelCollapsed ? '▲' : '▼' }}</text>
			</view>
			
				<scroll-view class="sites-list" scroll-y v-if="!panelCollapsed">
					<!-- 筛选器 -->
					<view class="filter-bar-wrap">
						<view class="filter-bar">
							<view
								class="filter-item"
								:class="{ active: currentFilter === filter.value }"
								v-for="filter in visibleStatusFilters"
								:key="filter.value"
								@click="setFilter(filter.value)"
							>
								<text>{{ filter.label }}</text>
							</view>
						</view>
						<view class="filter-more" @click="openStatusFilterSheet">
							<text class="filter-more-text">{{ $t('common.more') }}</text>
							<text class="filter-more-icon">⋯</text>
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
						<text class="site-address">{{ site.address || $t('map.noAddress') }}</text>
					</view>
					<view class="site-status" :class="getStatusClass(site.status)">
						{{ getStatusText(site.status) }}
					</view>
				</view>
				
				<view class="empty-state" v-if="filteredSites.length === 0">
					<text>{{ $t('map.noSites') }}</text>
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
	import { ref, computed, getCurrentInstance, watch } from 'vue'
	import { onLoad, onUnload, onReady } from '@dcloudio/uni-app'
	import { useSiteStore } from '@/stores/site'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { guardRouteAccess } from '@/utils/feature-access.js'
	
	const siteStore = useSiteStore()
	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const instance = getCurrentInstance()
	const { $t } = instance.appContext.config.globalProperties
	const t = (key, params = {}) => {
		const _ = languageStore.currentLocale
		return $t(key, params)
	}
	const ensureMapAccess = () => guardRouteAccess({
		userStore,
		route: 'pages/map/sites',
		t,
		redirectUrl: '/pages/home/home',
	})
	
	// 页面数据
	const sites = ref([])
	const loading = ref(true)
	const panelCollapsed = ref(false)
	const currentFilter = ref('all')
	const mapReady = ref(false)
	const leafletMapRef = ref(null)
	const leafletWebViewRef = ref(null)
	const appMapSrc = ref('/static/map/leaflet-map.html')
	const appMapSrcCandidates = ['/static/map/leaflet-map.html', 'static/map/leaflet-map.html']
	const appMapSrcIndex = ref(0)
	const appWebviewStyles = ref({
		left: '0px',
		right: '0px',
		top: '0px',
		bottom: '0px',
	})
	const markersApplied = ref(false)
	const webViewLoaded = ref(false)
	const pendingApplyMarkers = ref(false)
	let appMapWebview = null
	let loadMarkersRetryCount = 0
	let applyMarkersRetryCount = 0
	let applyMarkersTimer = null
	let webViewLoadFallbackTimer = null
	let lastWebviewInsets = { top: -1, bottom: -1 }
	let loggedMapWebviewUrl = ''

	// 计算属性
	const totalSites = computed(() => sites.value.length)

	const filteredSites = computed(() => {
		if (currentFilter.value === 'all') {
			return sites.value
		}
		return sites.value.filter(site => site.status === currentFilter.value)
	})

	const allStatusFilters = computed(() => {
		// 依赖语言，确保切换语言后能更新显示
		const _ = languageStore.currentLocale
		return [
			{ label: t('common.all'), value: 'all' },
			{ label: t('site.surveyPending'), value: 'survey_pending' },
			{ label: t('site.planning'), value: 'planning' },
			{ label: t('site.planned'), value: 'planned' },
			{ label: t('site.construction'), value: 'construction' },
			{ label: t('site.pendingOnline'), value: 'pending_online' },
			{ label: t('site.onlinePendingActivation'), value: 'online_pending_activation' },
			{ label: t('site.operational'), value: 'operational' },
			{ label: t('site.maintenance'), value: 'maintenance' },
		]
	})

	const visibleStatusFilters = computed(() => {
		const baseValues = ['all', 'survey_pending', 'planning', 'construction', 'operational', 'maintenance']
		const current = currentFilter.value
		const values = [...baseValues]

		if (current && current !== 'all' && !values.includes(current)) {
			values.splice(1, 0, current)
			if (values.length > baseValues.length) values.pop()
		}

		const filterMap = new Map(allStatusFilters.value.map(f => [f.value, f]))
		return values.map(v => filterMap.get(v)).filter(Boolean)
	})

	const openStatusFilterSheet = () => {
		const items = allStatusFilters.value
		uni.showActionSheet({
			title: t('messages.filterSiteStatus'),
			itemList: items.map(i => i.label),
			success: (res) => {
				const selected = items[res.tapIndex]
				if (!selected) return
				setFilter(selected.value)
			}
		})
	}

	// 地图文件路径 - 兼容不同环境
	const mapSrc = computed(() => {
		// #ifdef H5
		return './static/map/leaflet-map.html'
		// #endif

		// #ifdef APP-PLUS
		// App 中使用 /static/... 形式加载本地静态页（更稳定；避免 file:// 路径在部分机型被拼接导致打不开）
		return appMapSrc.value
		// #endif

		// 默认路径
		return './static/map/leaflet-map.html'
	})

	const buildMapI18nPayload = () => ({
		title: t('map.sitesDistributionTitle'),
		noAddress: t('map.noAddress'),
		statusTextMap: {
			survey_pending: t('site.surveyPending'),
			operational: t('site.operational'),
			construction: t('site.construction'),
			maintenance: t('site.maintenance'),
			planning: t('site.planning'),
			planned: t('site.planned'),
			pending_online: t('site.pendingOnline'),
			online_pending_activation: t('site.onlinePendingActivation')
		}
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

		// App端某些情况下收不到 iframe -> parent 的 mapReady（window.postMessage），这里用 load 事件兜底
		if (!mapReady.value) {
			console.log('未收到 mapReady，使用 iframe load 事件兜底标记地图已就绪')
			mapReady.value = true
		}

		loadMarkersToMap()
	}

	const normalizeMapMessage = (event) => {
		const payload = event?.data
		if (!payload) return null

		// iframe -> parent: window.parent.postMessage({ type, data }, '*')
		if (payload.type) return { type: payload.type, data: payload.data }

		// web-view -> uni: uni.postMessage({ data: { type, data } })
		if (payload.data && payload.data.type) return { type: payload.data.type, data: payload.data.data }

		return null
	}
	
	// 处理来自地图的消息
	const handleMapMessage = (event) => {
		const msg = normalizeMapMessage(event)
		if (!msg) return
		const { type, data } = msg
		
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

	const handleWebViewMessage = (event) => {
		const dataList = event?.detail?.data
		if (!Array.isArray(dataList) || dataList.length === 0) return

		dataList.forEach((payload) => {
			const { type, data } = payload || {}
			if (!type) return

			switch(type) {
				case 'mapReady':
					console.log('收到 mapReady')
					mapReady.value = true
					// 某些云打包/机型下 web-view 的 @load 不稳定，mapReady 可视为“已加载完成”的更可靠信号
					webViewLoaded.value = true
					if (webViewLoadFallbackTimer) {
						clearTimeout(webViewLoadFallbackTimer)
						webViewLoadFallbackTimer = null
					}
					requestApplyMarkers('mapReady')
					break
				case 'markersApplied':
					console.log('地图已应用标记:', data?.count)
					markersApplied.value = true
					if (applyMarkersTimer) {
						clearTimeout(applyMarkersTimer)
						applyMarkersTimer = null
					}
					break
				case 'markerClick':
					// 标记点击事件
					const site = sites.value.find(s => s.id === data?.siteId)
					if (site) {
						console.log('点击站点:', site.site_name)
					}
					break
			}
		})
	}

	const requestApplyMarkers = (reason = '') => {
		// #ifdef APP-PLUS
		if (!webViewLoaded.value) {
			pendingApplyMarkers.value = true
			return
		}
		if (sites.value.length === 0) {
			pendingApplyMarkers.value = true
			return
		}
		pendingApplyMarkers.value = false
		scheduleApplyMarkersToWebView(reason)
		// #endif
	}

	const tryNextAppMapSrc = (reason = '') => {
		// #ifdef APP-PLUS
		const nextIndex = appMapSrcIndex.value + 1
		if (nextIndex >= appMapSrcCandidates.length) return false

		appMapSrcIndex.value = nextIndex
		appMapSrc.value = appMapSrcCandidates[nextIndex]
		appMapWebview = null
		loggedMapWebviewUrl = ''
		webViewLoaded.value = false
		pendingApplyMarkers.value = true
		console.warn('切换地图 src 兜底:', { reason, src: appMapSrc.value })
		return true
		// #endif
		return false
	}

	const onWebViewLoad = () => {
		// App 端 web-view 加载完成（不代表内部 Leaflet 已初始化完成）
		console.log('web-view load', mapSrc.value)
		webViewLoaded.value = true
		if (webViewLoadFallbackTimer) {
			clearTimeout(webViewLoadFallbackTimer)
			webViewLoadFallbackTimer = null
		}
		// 触发一次样式更新，避免遮挡底部面板
		updateAppMapWebviewStyle().catch(() => {})
		// web-view load 后再开始找子 webview / evalJS 下发 marker
		if (pendingApplyMarkers.value || sites.value.length > 0) {
			requestApplyMarkers('webview load')
		}
	}

	const onWebViewError = (e) => {
		console.error('web-view 加载失败:', e, mapSrc.value)
		webViewLoaded.value = false
		// 若本地页加载失败，尝试切换候选路径兜底
		if (tryNextAppMapSrc('web-view error')) {
			setTimeout(() => {
				requestApplyMarkers('web-view error retry')
			}, 300)
		}
	}

	const getRect = (selector) => new Promise((resolve) => {
		try {
			const query = uni.createSelectorQuery().in(instance?.proxy)
			query.select(selector).boundingClientRect((data) => resolve(data || null)).exec()
		} catch (e) {
			resolve(null)
		}
	})

	const findAppMapWebview = (options = {}) => {
		// #ifdef APP-PLUS
		try {
			const requireEvalJS = options?.requireEvalJS === true

			if (appMapWebview) {
				if (!requireEvalJS || typeof appMapWebview?.evalJS === 'function') return appMapWebview
				// 缓存命中但不可 evalJS，清掉缓存重新找（部分机型/时序下会拿到“未就绪”的对象）
				appMapWebview = null
			}

			if (!plus?.webview?.currentWebview) return null

			const current = plus.webview.currentWebview()
			if (!current) return null

			const collected = []
			const visit = (wv) => {
				if (!wv) return
				collected.push(wv)
				try {
					const kids = typeof wv.children === 'function' ? wv.children() : []
					if (Array.isArray(kids)) kids.forEach(visit)
				} catch (e) {
					// ignore
				}
			}

			visit(current)

			const pickFromList = (list) => {
				let fallback = null
				for (const wv of list) {
					try {
						const url = typeof wv?.getURL === 'function' ? wv.getURL() : ''
						if (typeof url !== 'string' || !url.includes('leaflet-map.html')) continue

						if (typeof wv?.evalJS === 'function') return wv
						if (!fallback) fallback = wv
					} catch (e) {
						// ignore
					}
				}
				return requireEvalJS ? null : fallback
			}

			let target = pickFromList(collected)
			if (!target) {
				// 某些版本/机型下 web-view 不一定挂在 children()，兜底扫全量 webview
				try {
					const list = typeof plus?.webview?.all === 'function' ? plus.webview.all() : []
					target = pickFromList(Array.isArray(list) ? list : [])
				} catch (e) {
					// ignore
				}
			}

			if (target) {
				// 仅在可 evalJS 时缓存，避免缓存“半成品对象”
				if (typeof target?.evalJS === 'function') appMapWebview = target
				try {
					const url = typeof target?.getURL === 'function' ? target.getURL() : ''
					if (url && url !== loggedMapWebviewUrl) {
						loggedMapWebviewUrl = url
						console.log('已找到地图子 webview:', url)
					}
				} catch (e) {
					// ignore
				}
			}

			return target || null
		} catch (e) {
			return null
		}
		// #endif
		return null
	}

	const updateAppMapWebviewStyle = async () => {
		// #ifdef APP-PLUS
		const headerRect = await getRect('.map-header')
		const panelRect = await getRect('.sites-panel')

		const topPx = Math.max(0, Math.round(headerRect?.height || 0))
		const bottomPx = Math.max(0, Math.round(panelRect?.height || 0))

		if (topPx !== lastWebviewInsets.top || bottomPx !== lastWebviewInsets.bottom) {
			lastWebviewInsets = { top: topPx, bottom: bottomPx }
			console.log('更新地图 webview insets:', { topPx, bottomPx })
		}

		appWebviewStyles.value = {
			left: '0px',
			right: '0px',
			top: `${topPx}px`,
			bottom: `${bottomPx}px`,
		}

		const wv = findAppMapWebview()
		if (!wv || typeof wv.setStyle !== 'function') return true

		try {
			wv.setStyle({
				left: '0px',
				right: '0px',
				top: `${topPx}px`,
				bottom: `${bottomPx}px`,
			})
			return true
		} catch (error) {
			console.error('设置地图 webview 样式失败:', error)
			return false
		}
		// #endif
		return false
	}
	
	const getMapContentWindow = () => {
		const iframeEl = leafletMapRef.value || (typeof document !== 'undefined' ? document.getElementById('leafletMap') : null)
		return iframeEl?.contentWindow || null
	}

	const applyMarkersToWebView = () => {
		if (sites.value.length === 0) return false
		// #ifdef APP-PLUS
		const webview = findAppMapWebview({ requireEvalJS: true })
		if (!webview || typeof webview.evalJS !== 'function') return false
		// #endif
		// #ifndef APP-PLUS
		return false
		// #endif

		const i18nPayload = buildMapI18nPayload()
		const markerSites = sites.value
			.filter(s => s.latitude && s.longitude)
			.map(s => ({
				id: s.id,
				latitude: parseFloat(s.latitude),
				longitude: parseFloat(s.longitude),
				site_name: s.site_name,
				address: s.address,
				status: s.status
			}))

		const js = `window.setMapI18n && window.setMapI18n(${JSON.stringify(i18nPayload)});window.applySiteMarkers && window.applySiteMarkers(${JSON.stringify(markerSites)});`
		try {
			webview.evalJS(js)
			return true
		} catch (error) {
			console.error('evalJS 下发标记失败:', error)
			return false
		}
	}

	const scheduleApplyMarkersToWebView = (reason = '') => {
		// #ifdef APP-PLUS
		if (!webViewLoaded.value) {
			pendingApplyMarkers.value = true
			return
		}
		if (sites.value.length === 0) {
			pendingApplyMarkers.value = true
			return
		}
		markersApplied.value = false
		applyMarkersRetryCount = 0
		if (applyMarkersTimer) {
			clearTimeout(applyMarkersTimer)
			applyMarkersTimer = null
		}

		const startedAt = Date.now()
		let lastLogAt = 0
		let firstSentLogged = false

		const nextDelayMs = (attempt) => {
			if (attempt <= 10) return 1000
			if (attempt <= 20) return 2000
			if (attempt <= 40) return 3000
			if (attempt <= 80) return 5000
			if (attempt <= 120) return 8000
			return 10000
		}

		const tick = () => {
			if (markersApplied.value) return

			applyMarkersRetryCount += 1
			updateAppMapWebviewStyle().catch(() => {})
			const sent = applyMarkersToWebView()

			const now = Date.now()
			const elapsedMs = now - startedAt

			// 日志降噪：首次成功 evalJS 记录一次，之后每 30s 记录一次摘要
			if (sent && !firstSentLogged) {
				firstSentLogged = true
				console.log('已向地图下发站点标记(首次):', { reason, count: sites.value.length })
			}

			if (lastLogAt === 0 || now - lastLogAt >= 30000) {
				lastLogAt = now
				console.log('地图标记下发重试中:', {
					reason,
					attempt: applyMarkersRetryCount,
					elapsedSec: Math.round(elapsedMs / 1000),
					hasMapWebview: Boolean(appMapWebview),
					sent
				})
			}

			// 总超时 3 分钟：覆盖部分机型 web-view/离线瓦片延迟初始化
			if (elapsedMs < 180000) {
				applyMarkersTimer = setTimeout(tick, nextDelayMs(applyMarkersRetryCount))
			} else {
				console.warn('下发站点标记超时，停止重试:', {
					reason,
					attempt: applyMarkersRetryCount,
					elapsedSec: Math.round(elapsedMs / 1000)
				})
			}
		}

		tick()
		// #endif
	}

	// 向地图发送消息
	const sendMessageToMap = (action, data) => {
		if (!mapReady.value) {
			console.warn('地图未准备好')
			return
		}

		try {
			const contentWindow = getMapContentWindow()
			if (!contentWindow) {
				console.warn('地图窗口未就绪')
				return
			}
			contentWindow.postMessage({ action, data }, '*')
		} catch (error) {
			console.error('发送消息到地图失败:', error)
		}
	}
	
	// 加载站点标记到地图
	const loadMarkersToMap = () => {
		if (!mapReady.value) return

		// 避免 mapReady 先于 iframe 可用导致的空发
		if (!getMapContentWindow()) {
			if (loadMarkersRetryCount >= 10) {
				console.warn('地图窗口长时间未就绪，放弃加载标记')
				return
			}
			loadMarkersRetryCount += 1
			setTimeout(() => {
				loadMarkersToMap()
			}, 200)
			return
		}
		loadMarkersRetryCount = 0

		// 先下发 i18n 文案（用于地图弹窗状态/无地址等）
		sendMessageToMap('setI18n', buildMapI18nPayload())
		
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
		if (!ensureMapAccess()) return
		try {
			loading.value = true
			const result = await siteStore.getSites()
			
			if (result.success) {
				// 只显示有坐标的站点
				sites.value = result.data.filter(s => s.latitude && s.longitude)

				// #ifdef APP-PLUS
				if (sites.value.length > 0) requestApplyMarkers('sites loaded')
				// 站点列表渲染后面板高度会变化，需要再更新一次 insets，避免 web-view 盖住筛选栏/面板头部
				setTimeout(() => updateAppMapWebviewStyle().catch(() => {}), 60)
				setTimeout(() => updateAppMapWebviewStyle().catch(() => {}), 400)
				// #endif
				
				// 如果地图已就绪，加载标记
				if (mapReady.value) {
					// #ifdef H5
					loadMarkersToMap()
					// #endif
				}
			} else {
				uni.showToast({
					title: t('site.loadFailed'),
					icon: 'error'
				})
			}
		} catch (error) {
			console.error('Load sites error:', error)
			uni.showToast({
				title: t('site.loadFailed'),
				icon: 'error'
			})
		} finally {
			loading.value = false
		}
	}
	
	// 切换面板展开/收起
	const togglePanel = () => {
		panelCollapsed.value = !panelCollapsed.value
		// #ifdef APP-PLUS
		// 等待面板展开/收起动画后更新地图区域，避免遮挡
		setTimeout(() => {
			updateAppMapWebviewStyle().catch(() => {})
		}, 350)
		// #endif
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
			'survey_pending': 'status-survey-pending',
			'planned': 'status-planned',
			'operational': 'status-operational',
			'pending_online': 'status-pending-online',
			'online_pending_activation': 'status-online-pending-activation',
			'construction': 'status-construction',
			'maintenance': 'status-maintenance',
			'planning': 'status-planning'
		}
		return classMap[status] || 'status-default'
	}
	
	// 获取状态文本
	const getStatusText = (status) => {
		const statusMap = {
			survey_pending: t('site.surveyPending'),
			operational: t('site.operational'),
			construction: t('site.construction'),
			maintenance: t('site.maintenance'),
			planning: t('site.planning'),
			planned: t('site.planned'),
			pending_online: t('site.pendingOnline'),
			online_pending_activation: t('site.onlinePendingActivation')
		}
		return statusMap[status] || status
	}
	
	// 返回
	const goBack = () => {
		uni.navigateBack()
	}
	
	// 页面加载
	onLoad((options) => {
		if (!userStore.isLoggedIn) {
			uni.reLaunch({ url: '/pages/login/login' })
			return
		}
		if (!ensureMapAccess()) return
		// 设置页面标题
		uni.setNavigationBarTitle({
			title: t('map.sitesDistributionTitle')
		})

		// #ifdef APP-PLUS
		console.log('地图页面 mapSrc:', mapSrc.value)
		// 打包 APK 时用于排查本地资源是否存在
		try {
			plus.io.resolveLocalFileSystemURL(
				'_www/static/map/leaflet-map.html',
				() => console.log('地图文件存在: _www/static/map/leaflet-map.html'),
				(err) => console.warn('地图文件不存在或不可访问: _www/static/map/leaflet-map.html', err)
			)
		} catch (e) {
			console.warn('检查地图文件存在性失败:', e)
		}

		// 部分云打包/机型下 web-view 的 @load 不触发：增加超时兜底，确保能启动 marker 下发与样式更新
		if (webViewLoadFallbackTimer) clearTimeout(webViewLoadFallbackTimer)
		webViewLoadFallbackTimer = setTimeout(() => {
			if (webViewLoaded.value) return
			webViewLoaded.value = true
			console.warn('web-view @load 未触发，启用超时兜底启动标记下发')
			updateAppMapWebviewStyle().catch(() => {})
			requestApplyMarkers('webview load timeout')
		}, 2000)
		// #endif

		// #ifdef H5
		// 提前监听iframe消息，避免错过 mapReady
		try {
			if (typeof window !== 'undefined' && window.addEventListener) {
				window.addEventListener('message', handleMapMessage)
			}
		} catch (error) {
			console.error('添加消息监听器失败:', error)
		}
		// #endif
		
		// 加载站点数据
		loadSites()
	})

	watch(() => languageStore.currentLocale, () => {
		// 切换语言后需要同步更新 web-view 内弹窗/状态文案
		// #ifdef APP-PLUS
		if (sites.value.length > 0) requestApplyMarkers('locale changed')
		// #endif
		// #ifdef H5
		if (mapReady.value && sites.value.length > 0) loadMarkersToMap()
		// #endif
	})

	onReady(() => {
		// #ifdef APP-PLUS
		// 页面渲染完成后再量尺寸，避免取不到 header/panel 高度导致遮挡
		setTimeout(() => {
			updateAppMapWebviewStyle().catch(() => {})
		}, 50)
		// #endif
	})

	onUnload(() => {
		// #ifdef APP-PLUS
		if (applyMarkersTimer) {
			clearTimeout(applyMarkersTimer)
			applyMarkersTimer = null
		}
		if (webViewLoadFallbackTimer) {
			clearTimeout(webViewLoadFallbackTimer)
			webViewLoadFallbackTimer = null
		}
		appMapWebview = null
		loggedMapWebviewUrl = ''
		webViewLoaded.value = false
		pendingApplyMarkers.value = false
		// #endif

		// #ifdef H5
		try {
			if (typeof window !== 'undefined' && window.removeEventListener) {
				window.removeEventListener('message', handleMapMessage)
			}
		} catch (error) {
			console.error('移除消息监听器失败:', error)
		}
		// #endif
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
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding: 44rpx 20rpx 20rpx;
		display: flex;
		align-items: center;
		gap: 20rpx;
		box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.06);
		flex-shrink: 0;
	}
	
	.back-btn { width: 88rpx; height: 88rpx; border-radius: 44rpx; background: rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
	
	.back-icon {
		font-size: 32rpx;
		color: white;
	}
	
	.location-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	
	.location-name { font-size: 28rpx; font-weight: 600; color: #fff; margin-bottom: 4rpx; }
	
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

	.map-webview {
		width: 100%;
		height: 100%;
	}
	
	/* 底部站点面板 */
	.sites-panel {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		z-index: 1000;
		background: var(--bg-elevated);
		border-radius: 30rpx 30rpx 0 0;
		box-shadow: 0 -4rpx 20rpx rgba(0, 0, 0, 0.06);
		max-height: 60vh;
		transition: max-height 0.3s ease;
		
		&.collapsed { max-height: 120rpx; }
	}
	
.panel-header { display: flex; justify-content: space-between; align-items: center; min-height: 88rpx; padding: 0 30rpx; border-bottom: 1rpx solid var(--border-soft); }
	
	.panel-title {
		display: flex;
		align-items: center;
		gap: 15rpx;
	}
	
	.title-text { font-size: 30rpx; font-weight: 600; color: var(--text-primary); }
	
	.count-badge { background: var(--color-primary); color: #fff; font-size: 20rpx; padding: 4rpx 12rpx; border-radius: 12rpx; font-weight: 600; }
	
	.toggle-icon {
		font-size: 24rpx;
		color: #9ca3af;
	}
	
	.sites-list {
		max-height: calc(60vh - 120rpx);
		overflow-y: auto;
		padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
	}
	
		/* 筛选栏 */
		.filter-bar-wrap {
			position: relative;
		}

		.filter-bar {
			display: flex;
			gap: 15rpx;
			padding: 20rpx 140rpx 20rpx 30rpx;
			overflow-x: auto;
			white-space: nowrap;
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
	
	.filter-item {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx; /* >=44px */
		padding: 0 28rpx;
		background: #f3f4f6;
		border-radius: 24rpx;
		font-size: 26rpx;
		color: #6b7280;
		transition: all 0.3s ease;
		flex-shrink: 0;
		
		&.active { background: var(--color-primary); color: #fff; }
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
			
			&.status-survey-pending { filter: hue-rotate(180deg); }
			&.status-planned { filter: hue-rotate(210deg); }
			&.status-pending-online { filter: hue-rotate(20deg); }
			&.status-online-pending-activation { filter: hue-rotate(150deg); }
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
	
	.site-name { font-size: 28rpx; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	
	.site-address { font-size: 22rpx; color: #6b7280; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	
		.site-status {
			font-size: 22rpx;
			padding: 6rpx 16rpx;
			border-radius: 12rpx;
			flex-shrink: 0;

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
