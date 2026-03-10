<template>
  <div class="site-map-page">
    <div class="page-header">
      <div class="page-title-wrap">
        <h1>站点地图</h1>
        <p>按区域与状态查看站点分布，支持筛选、联动定位与快速跳转详情。</p>
      </div>
      <div class="header-tags">
        <el-tag type="info">已加载 {{ rawSites.length }} 个站点</el-tag>
        <el-tag type="success">有坐标 {{ sitesWithCoordinates.length }} 个</el-tag>
        <el-tag v-if="sitesWithoutCoordinates.length" type="warning">无坐标 {{ sitesWithoutCoordinates.length }} 个</el-tag>
      </div>
    </div>

    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-grid">
        <el-input
          v-model="keyword"
          placeholder="搜索站点名称/编码/城市（自动检索）"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-select v-model="statusFilter" placeholder="站点状态" clearable filterable>
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <el-select v-model="siteTypeFilter" placeholder="站点类型" clearable filterable>
          <el-option
            v-for="item in siteTypeOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>

        <el-select v-model="provinceFilter" placeholder="省份" clearable filterable>
          <el-option
            v-for="item in provinceOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>

        <el-select v-model="cityFilter" placeholder="城市" clearable filterable :disabled="!cityOptions.length">
          <el-option
            v-for="item in cityOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>

        <el-select v-model="districtFilter" placeholder="区县" clearable filterable :disabled="!districtOptions.length">
          <el-option
            v-for="item in districtOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>

        <el-select v-model="coordinateFilter" placeholder="坐标状态">
          <el-option label="仅看有坐标" value="with" />
          <el-option label="仅看无坐标" value="without" />
          <el-option label="全部" value="all" />
        </el-select>

        <el-select v-model="ssvFilter" placeholder="SSV状态">
          <el-option label="全部 SSV" value="all" />
          <el-option label="仅已通过" value="passed" />
          <el-option label="仅未通过" value="failed" />
        </el-select>

        <el-checkbox v-model="onlyInView" class="in-view-check">仅看当前地图视野</el-checkbox>

        <div class="toolbar-actions">
          <el-button @click="resetFilters">
            <el-icon><Delete /></el-icon>
            重置
          </el-button>
          <el-button type="primary" :loading="loading" @click="reloadSites">
            <el-icon><RefreshRight /></el-icon>
            刷新站点
          </el-button>
        </div>
      </div>

      <div class="toolbar-tip">
        <span>关键词、状态、类型走后端检索；区域、SSV、坐标状态和视野筛选走本地秒级过滤。</span>
        <span v-if="hasTruncated" class="warning-text">数据量较大，当前仅加载前 {{ MAX_FETCH_LIMIT }} 个站点，请继续缩小筛选范围。</span>
      </div>
    </el-card>

    <el-card class="map-card" shadow="never" v-loading="loading">
      <template #header>
        <div class="map-card-header">
          <div class="map-card-title">
            <span>站点分布图</span>
            <el-tag size="small" type="info">筛选结果 {{ filteredSites.length }}</el-tag>
            <el-tag size="small" type="success">地图点位 {{ mapSites.length }}</el-tag>
          </div>
          <div class="map-card-actions">
            <el-button size="small" :disabled="!sitesWithCoordinates.length" @click="fitAllMarkers">
              <el-icon><Aim /></el-icon>
              适配全部点位
            </el-button>
            <el-button size="small" @click="toggleListPanel">
              <el-icon>
                <component :is="listCollapsed ? 'ArrowRightBold' : 'ArrowLeftBold'" />
              </el-icon>
              {{ listCollapsed ? '展开列表' : '收起列表' }}
            </el-button>
          </div>
        </div>
      </template>

      <div class="map-layout" :class="{ 'list-collapsed': listCollapsed }">
        <aside class="site-list-panel">
          <div class="list-header">
            <span>站点列表</span>
            <span>{{ filteredSites.length }}</span>
          </div>

          <el-scrollbar class="site-list-scroll">
            <div v-if="!filteredSites.length" class="list-empty">
              <el-empty description="当前筛选无站点" />
            </div>
            <div v-else class="site-items">
              <div
                v-for="site in filteredSites"
                :key="site.id"
                class="site-item"
                :class="{ active: selectedSiteId === site.id }"
                @click="focusSite(site)"
              >
                <div class="site-item-head">
                  <span class="site-name" :title="site.site_name">{{ site.site_name || '-' }}</span>
                  <span
                    class="status-pill"
                    :style="{ backgroundColor: getStatusMeta(site.status).color, color: getStatusMeta(site.status).textColor }"
                  >
                    <span
                      class="status-pill-shape"
                      :class="`shape-${getStatusMeta(site.status).shape}`"
                      :style="{ '--marker-color': getStatusMeta(site.status).textColor }"
                    />
                    {{ getStatusMeta(site.status).label }}
                  </span>
                </div>

                <div class="site-meta">{{ site.site_code || '-' }} · {{ formatArea(site) }}</div>

                <div class="site-tags">
                  <el-tag size="small" :type="site.ssv_passed ? 'success' : 'info'" effect="plain">
                    {{ site.ssv_passed ? 'SSV已通过' : 'SSV未通过' }}
                  </el-tag>
                  <el-tag size="small" :type="hasCoordinates(site) ? 'primary' : 'warning'" effect="plain">
                    {{ hasCoordinates(site) ? '有坐标' : '缺坐标' }}
                  </el-tag>
                </div>

                <div class="site-actions">
                  <el-button link type="primary" size="small" @click.stop="focusSite(site, true)">
                    <el-icon><Location /></el-icon>
                    定位
                  </el-button>
                  <el-button link type="success" size="small" @click.stop="openSiteDetail(site)">
                    <el-icon><View /></el-icon>
                    详情
                  </el-button>
                  <el-button link type="warning" size="small" @click.stop="openSitePlanning(site)">
                    <el-icon><Operation /></el-icon>
                    规划
                  </el-button>
                </div>
              </div>
            </div>
          </el-scrollbar>
        </aside>

        <section class="map-panel">
          <div ref="mapRef" class="map-canvas" />

          <div class="map-legend">
            <div class="legend-title">状态图例</div>
            <div class="legend-grid">
              <div
                v-for="item in legendItems"
                :key="item.value"
                class="legend-item"
              >
                <span
                  class="legend-shape"
                  :class="`shape-${item.shape}`"
                  :style="{ '--marker-color': item.color }"
                />
                <span>{{ item.label }}</span>
              </div>
            </div>
          </div>

          <div v-if="sitesWithoutCoordinates.length" class="coord-hint">
            当前筛选下有 {{ sitesWithoutCoordinates.length }} 个站点缺少坐标，仅在左侧列表展示。
          </div>
        </section>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import request from '@/utils/request'

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const router = useRouter()

const MAX_FETCH_LIMIT = 5000
const SERVER_PAGE_SIZE = 100
const DEFAULT_MAP_CENTER = [34.26, 108.95]
const DEFAULT_MAP_ZOOM = 4

const STATUS_META = {
  survey_pending: { label: '勘察中', color: '#64748b', textColor: '#ffffff', shape: 'bar' },
  planning: { label: '规划中', color: '#0ea5e9', textColor: '#ffffff', shape: 'circle' },
  planned: { label: '规划完成', color: '#4f46e5', textColor: '#ffffff', shape: 'square' },
  construction: { label: '施工中', color: '#f97316', textColor: '#ffffff', shape: 'diamond' },
  pending_online: { label: '待上线', color: '#c026d3', textColor: '#ffffff', shape: 'triangle' },
  online_pending_activation: { label: '已上线待激活', color: '#dc2626', textColor: '#ffffff', shape: 'hexagon' },
  operational: { label: '已开通', color: '#16a34a', textColor: '#ffffff', shape: 'pentagon' },
  maintenance: { label: '维护中', color: '#a16207', textColor: '#ffffff', shape: 'star' },
}

const statusOptions = Object.keys(STATUS_META).map((status) => ({
  value: status,
  label: STATUS_META[status].label,
}))

const keyword = ref('')
const statusFilter = ref('')
const siteTypeFilter = ref('')
const provinceFilter = ref('')
const cityFilter = ref('')
const districtFilter = ref('')
const coordinateFilter = ref('with')
const ssvFilter = ref('all')
const onlyInView = ref(false)

const loading = ref(false)
const rawSites = ref([])
const selectedSiteId = ref(null)
const hasTruncated = ref(false)
const listCollapsed = ref(false)
const lastMapBounds = ref(null)

const mapRef = ref(null)
let mapInstance = null
let markerLayer = null
let searchTimer = null
const suppressRemoteWatch = ref(false)
const markerMap = new Map()

const normalizeText = (value) => String(value || '').trim()

const normalizeStatus = (status) => normalizeText(status)

const getStatusMeta = (status) => {
  const normalized = normalizeStatus(status)
  return STATUS_META[normalized] || { label: normalized || '未知状态', color: '#334155', textColor: '#ffffff', shape: 'circle' }
}

const hasCoordinates = (site) => {
  if (!site) return false
  const lat = Number(site.latitude)
  const lng = Number(site.longitude)
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
}

const escapeHtml = (value) => {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const formatArea = (site) => {
  const parts = [site?.province, site?.city, site?.district]
    .map((item) => normalizeText(item))
    .filter(Boolean)
  return parts.length ? parts.join('/') : '区域未设置'
}

const filteredSites = computed(() => {
  const list = rawSites.value.filter((site) => {
    if (provinceFilter.value && normalizeText(site.province) !== provinceFilter.value) return false
    if (cityFilter.value && normalizeText(site.city) !== cityFilter.value) return false
    if (districtFilter.value && normalizeText(site.district) !== districtFilter.value) return false

    const hasCoord = hasCoordinates(site)
    if (coordinateFilter.value === 'with' && !hasCoord) return false
    if (coordinateFilter.value === 'without' && hasCoord) return false

    if (ssvFilter.value === 'passed' && !site.ssv_passed) return false
    if (ssvFilter.value === 'failed' && site.ssv_passed) return false

    return true
  })

  return [...list].sort((a, b) => {
    const aCode = normalizeText(a.site_code)
    const bCode = normalizeText(b.site_code)
    return aCode.localeCompare(bCode, 'zh-Hans-CN')
  })
})

const sitesWithCoordinates = computed(() => {
  return filteredSites.value.filter((site) => hasCoordinates(site))
})

const mapSites = computed(() => {
  if (!onlyInView.value || !lastMapBounds.value) {
    return sitesWithCoordinates.value
  }

  return sitesWithCoordinates.value.filter((site) => {
    return lastMapBounds.value.contains([Number(site.latitude), Number(site.longitude)])
  })
})

const sitesWithoutCoordinates = computed(() => {
  return filteredSites.value.filter((site) => !hasCoordinates(site))
})

const siteTypeOptions = computed(() => {
  const set = new Set()
  rawSites.value.forEach((site) => {
    const type = normalizeText(site.site_type)
    if (type) set.add(type)
  })
  return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
})

const provinceOptions = computed(() => {
  const set = new Set()
  rawSites.value.forEach((site) => {
    const value = normalizeText(site.province)
    if (value) set.add(value)
  })
  return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
})

const cityOptions = computed(() => {
  const set = new Set()
  rawSites.value.forEach((site) => {
    if (provinceFilter.value && normalizeText(site.province) !== provinceFilter.value) return
    const value = normalizeText(site.city)
    if (value) set.add(value)
  })
  return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
})

const districtOptions = computed(() => {
  const set = new Set()
  rawSites.value.forEach((site) => {
    if (provinceFilter.value && normalizeText(site.province) !== provinceFilter.value) return
    if (cityFilter.value && normalizeText(site.city) !== cityFilter.value) return
    const value = normalizeText(site.district)
    if (value) set.add(value)
  })
  return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
})

const legendItems = computed(() => {
  return Object.keys(STATUS_META).map((value) => ({
    value,
    label: STATUS_META[value].label,
    color: STATUS_META[value].color,
    shape: STATUS_META[value].shape,
  }))
})

const buildMarkerIcon = (site) => {
  const statusMeta = getStatusMeta(site.status)
  const selected = selectedSiteId.value === site.id
  const className = [
    'site-status-marker',
    `shape-${statusMeta.shape}`,
    selected ? 'is-selected' : '',
  ].filter(Boolean).join(' ')

  return L.divIcon({
    className: 'site-status-marker-wrapper',
    html: `<span class="${className}" style="--marker-color: ${statusMeta.color};"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -10],
  })
}

const buildPopupContent = (site) => {
  const area = escapeHtml(formatArea(site))
  const status = getStatusMeta(site.status)
  const address = escapeHtml(site.address || '-')
  const siteCode = escapeHtml(site.site_code || '-')
  const siteName = escapeHtml(site.site_name || '-')
  const siteType = escapeHtml(site.site_type || '-')

  return `
    <div class="site-popup">
      <div class="popup-title">${siteName}</div>
      <div class="popup-line"><span>站点编码：</span>${siteCode}</div>
      <div class="popup-line"><span>站点状态：</span>${escapeHtml(status.label)}</div>
      <div class="popup-line"><span>站点类型：</span>${siteType}</div>
      <div class="popup-line"><span>区域：</span>${area}</div>
      <div class="popup-line"><span>SSV：</span>${site.ssv_passed ? '已通过' : '未通过'}</div>
      <div class="popup-line"><span>地址：</span>${address}</div>
    </div>
  `
}

const clearMarkers = () => {
  markerMap.clear()
  if (markerLayer) {
    markerLayer.clearLayers()
  }
}

const updateMarkerSelection = () => {
  const siteMapById = new Map(mapSites.value.map((site) => [site.id, site]))
  markerMap.forEach((marker, siteId) => {
    const site = siteMapById.get(siteId)
    if (!site) return
    marker.setIcon(buildMarkerIcon(site))
  })
}

const fitBoundsBySites = (sites) => {
  if (!mapInstance) return
  if (!sites.length) {
    mapInstance.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM)
    return
  }

  const latlngs = sites.map((site) => [Number(site.latitude), Number(site.longitude)])
  const bounds = L.latLngBounds(latlngs)
  mapInstance.fitBounds(bounds.pad(0.16), { maxZoom: 13 })
}

const renderMarkers = ({ fitBounds = false } = {}) => {
  if (!mapInstance || !markerLayer) return

  clearMarkers()

  mapSites.value.forEach((site) => {
    const marker = L.marker(
      [Number(site.latitude), Number(site.longitude)],
      { icon: buildMarkerIcon(site) },
    )
    marker.bindPopup(buildPopupContent(site), { maxWidth: 300 })
    marker.on('click', () => {
      selectedSiteId.value = site.id
    })
    marker.addTo(markerLayer)
    markerMap.set(site.id, marker)
  })

  updateMarkerSelection()

  if (fitBounds) {
    fitBoundsBySites(sitesWithCoordinates.value)
  }
}

const ensureMap = async () => {
  if (mapInstance || !mapRef.value) return

  mapInstance = L.map(mapRef.value, {
    center: DEFAULT_MAP_CENTER,
    zoom: DEFAULT_MAP_ZOOM,
    zoomControl: true,
    minZoom: 3,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18,
  }).addTo(mapInstance)

  markerLayer = L.layerGroup().addTo(mapInstance)
  lastMapBounds.value = mapInstance.getBounds()

  mapInstance.on('moveend', () => {
    lastMapBounds.value = mapInstance.getBounds()
    if (onlyInView.value) {
      renderMarkers()
    }
  })

  await nextTick()
  mapInstance.invalidateSize()
}

const loadSites = async ({ fitBounds = false, silent = false } = {}) => {
  try {
    loading.value = true
    hasTruncated.value = false

    const allSites = []
    let total = 0
    let skip = 0

    while (true) {
      const params = {
        skip,
        limit: SERVER_PAGE_SIZE,
        sort_by: 'updated_at',
        sort_order: 'desc',
      }
      if (normalizeText(keyword.value)) params.keyword = normalizeText(keyword.value)
      if (statusFilter.value) params.status = statusFilter.value
      if (siteTypeFilter.value) params.site_type = siteTypeFilter.value

      const res = await request.get('/api/sites/search', { params })
      const list = Array.isArray(res?.sites) ? res.sites : []

      if (typeof res?.total === 'number') {
        total = res.total
      }

      allSites.push(...list)

      if (!list.length) break
      if (total > 0 && allSites.length >= total) break
      if (allSites.length >= MAX_FETCH_LIMIT) {
        hasTruncated.value = true
        break
      }

      skip += list.length
    }

    rawSites.value = allSites.slice(0, MAX_FETCH_LIMIT)

    const stillVisible = rawSites.value.some((item) => item.id === selectedSiteId.value)
    if (!stillVisible) {
      selectedSiteId.value = rawSites.value[0]?.id || null
    }

    await nextTick()
    await ensureMap()
    renderMarkers({ fitBounds })

    if (!silent) {
      ElMessage.success(`已加载 ${rawSites.value.length} 个站点`)
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('站点地图加载失败')
  } finally {
    loading.value = false
  }
}

const scheduleRemoteReload = () => {
  if (suppressRemoteWatch.value) return
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    loadSites({ fitBounds: true, silent: true })
  }, 420)
}

const focusSite = (site, forcePopup = false) => {
  selectedSiteId.value = site.id

  if (!hasCoordinates(site)) {
    ElMessage.warning('该站点暂无经纬度，无法在地图定位')
    return
  }

  const marker = markerMap.get(site.id)
  if (!marker || !mapInstance) {
    ElMessage.warning('当前站点不在地图视野，请调整筛选条件')
    return
  }

  const targetZoom = Math.max(mapInstance.getZoom(), 12)
  mapInstance.flyTo(marker.getLatLng(), targetZoom, { duration: 0.45 })
  if (forcePopup || !marker.isPopupOpen()) {
    marker.openPopup()
  }
}

const openSiteDetail = (site) => {
  router.push({ name: 'SiteDetail', params: { id: site.id } })
}

const openSitePlanning = (site) => {
  router.push({ name: 'SitePlanningLld', params: { id: site.id } })
}

const fitAllMarkers = () => {
  fitBoundsBySites(sitesWithCoordinates.value)
}

const toggleListPanel = async () => {
  listCollapsed.value = !listCollapsed.value
  await nextTick()
  if (mapInstance) {
    mapInstance.invalidateSize()
  }
}

const resetFilters = async () => {
  suppressRemoteWatch.value = true
  keyword.value = ''
  statusFilter.value = ''
  siteTypeFilter.value = ''
  provinceFilter.value = ''
  cityFilter.value = ''
  districtFilter.value = ''
  coordinateFilter.value = 'with'
  ssvFilter.value = 'all'
  onlyInView.value = false
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  try {
    await loadSites({ fitBounds: true, silent: true })
  } finally {
    suppressRemoteWatch.value = false
  }
}

const reloadSites = async () => {
  await loadSites({ fitBounds: true, silent: false })
}

watch(keyword, () => {
  scheduleRemoteReload()
})

watch([statusFilter, siteTypeFilter], () => {
  if (suppressRemoteWatch.value) return
  loadSites({ fitBounds: true, silent: true })
})

watch(provinceFilter, () => {
  cityFilter.value = ''
  districtFilter.value = ''
})

watch(cityFilter, () => {
  districtFilter.value = ''
})

watch(mapSites, () => {
  renderMarkers()
})

watch(selectedSiteId, () => {
  updateMarkerSelection()
})

watch(listCollapsed, async () => {
  await nextTick()
  if (mapInstance) {
    mapInstance.invalidateSize()
  }
})

onMounted(async () => {
  await ensureMap()
  await loadSites({ fitBounds: true, silent: true })
})

onBeforeUnmount(() => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  clearMarkers()
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
  markerLayer = null
})
</script>

<style scoped lang="scss">
.site-map-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-title-wrap h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-title-wrap p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.header-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  align-items: center;
}

.in-view-check {
  padding-left: 6px;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.toolbar-tip {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.warning-text {
  color: #b45309;
}

.map-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.map-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.map-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.map-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.map-layout {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 12px;
  min-height: 620px;
}

.map-layout.list-collapsed {
  grid-template-columns: 0 minmax(0, 1fr);
}

.site-list-panel {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  transition: width 0.2s ease, opacity 0.2s ease;
}

.map-layout.list-collapsed .site-list-panel {
  width: 0;
  opacity: 0;
  border: 0;
}

.list-header {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  border-bottom: 1px solid var(--border-color);
}

.site-list-scroll {
  height: 560px;
}

.site-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.site-item {
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  padding: 10px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.site-item:hover {
  border-color: #60a5fa;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.site-item.active {
  border-color: #2563eb;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.16);
}

.site-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.site-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  color: #fff;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 12px;
  line-height: 1.5;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-pill-shape {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  background: var(--marker-color);
  border: 1px solid rgba(255, 255, 255, 0.92);
}

.site-meta {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.site-tags {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.site-actions {
  margin-top: 6px;
  display: flex;
  gap: 4px;
}

.list-empty {
  height: 560px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-panel {
  position: relative;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
}

.map-canvas {
  width: 100%;
  height: 620px;
}

.map-legend {
  position: absolute;
  right: 12px;
  top: 12px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
  padding: 10px;
  z-index: 600;
  width: 220px;
}

.legend-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.legend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.legend-shape {
  width: 12px;
  height: 12px;
  flex: 0 0 12px;
  background: var(--marker-color);
  border: 1px solid rgba(15, 23, 42, 0.16);
}

.coord-hint {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 400;
  background: rgba(255, 251, 235, 0.95);
  color: #92400e;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
}

:deep(.site-popup) {
  font-size: 12px;
  color: #334155;
  min-width: 220px;
}

:deep(.site-popup .popup-title) {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
}

:deep(.site-popup .popup-line) {
  line-height: 1.6;
  word-break: break-all;
}

:deep(.site-popup .popup-line span) {
  color: #64748b;
}

:deep(.site-status-marker-wrapper) {
  background: transparent;
  border: 0;
}

:deep(.site-status-marker) {
  display: block;
  width: 16px;
  height: 16px;
  background: var(--marker-color);
  border: 2px solid #ffffff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.24);
}

:deep(.site-status-marker.is-selected) {
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.98), 0 0 0 4px rgba(17, 24, 39, 0.35), 0 8px 14px rgba(15, 23, 42, 0.26);
}

.shape-circle,
:deep(.shape-circle) {
  border-radius: 50%;
}

.shape-square,
:deep(.shape-square) {
  border-radius: 2px;
}

.shape-diamond,
:deep(.shape-diamond) {
  clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%);
}

.shape-triangle,
:deep(.shape-triangle) {
  clip-path: polygon(50% 0, 0 100%, 100% 100%);
}

.shape-hexagon,
:deep(.shape-hexagon) {
  clip-path: polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%);
}

.shape-pentagon,
:deep(.shape-pentagon) {
  clip-path: polygon(50% 0, 100% 38%, 82% 100%, 18% 100%, 0 38%);
}

.shape-star,
:deep(.shape-star) {
  clip-path: polygon(50% 0, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
}

.shape-bar,
:deep(.shape-bar) {
  clip-path: polygon(6% 35%, 94% 35%, 94% 65%, 6% 65%);
}

@media (max-width: 1360px) {
  .toolbar-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 1140px) {
  .toolbar-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .map-layout {
    grid-template-columns: 300px minmax(0, 1fr);
  }
}

@media (max-width: 960px) {
  .site-map-page {
    padding: 16px;
  }

  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .toolbar-actions {
    justify-content: flex-start;
  }

  .map-layout,
  .map-layout.list-collapsed {
    display: flex;
    flex-direction: column;
    min-height: auto;
  }

  .site-list-panel {
    width: 100%;
    opacity: 1;
    border: 1px solid var(--border-color);
  }

  .site-list-scroll {
    height: 300px;
  }

  .list-empty {
    height: 300px;
  }

  .map-canvas {
    height: 480px;
  }
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
  }

  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .map-card-title,
  .map-card-actions {
    width: 100%;
  }

  .map-card-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .legend-grid {
    grid-template-columns: 1fr;
  }

  .map-legend {
    right: 8px;
    width: 180px;
  }
}
</style>
