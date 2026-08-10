<template>
  <div class="inventory-page">
    <el-tabs
      class="inventory-category-tabs"
      :model-value="category"
      @tab-change="changeCategory"
    >
      <el-tab-pane :label="t('inventory.page.mainDeviceInventory')" name="main_device" />
      <el-tab-pane :label="t('inventory.page.auxiliaryInventory')" name="auxiliary" />
    </el-tabs>

    <InventoryKpiStrip
      :category="category"
      :summary="summary"
      :loading="loading"
      :active-filter="statusFilter"
      @select="handleKpiSelect"
    />

    <section class="inventory-toolbar" :aria-label="t('inventory.page.filters')">
      <el-radio-group :model-value="viewMode" @change="value => updateQuery({ view: value, page: 1 })">
        <el-radio-button label="equipment">{{ t('inventory.page.byEquipment') }}</el-radio-button>
        <el-radio-button label="warehouse">{{ t('inventory.page.byWarehouse') }}</el-radio-button>
      </el-radio-group>

      <el-input
        v-model="searchInput"
        class="search-input"
        clearable
        :prefix-icon="Search"
        :placeholder="searchPlaceholder"
        @input="scheduleSearch"
        @keyup.enter="commitSearch"
        @clear="commitSearch"
      />

      <el-select
        :model-value="warehouseId"
        clearable
        :placeholder="t('inventory.page.warehouse')"
        @change="value => updateQuery({ warehouse: value || undefined, page: 1 })"
      >
        <el-option
          v-for="warehouse in warehouses"
          :key="warehouse.id"
          :label="warehouse.warehouse_name"
          :value="warehouse.id"
        />
      </el-select>

      <el-select
        :model-value="statusFilter"
        clearable
        :placeholder="category === 'main_device' ? t('inventory.page.deviceStatus') : t('inventory.page.stockStatus')"
        @change="value => updateQuery({ status: value || undefined, page: 1 })"
      >
        <el-option
          v-for="option in statusOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>

      <el-switch
        :model-value="includeZero"
        :active-text="t('inventory.page.showZeroStock')"
        @change="value => updateQuery({ zero: value ? '1' : undefined, page: 1 })"
      />
    </section>

    <div class="inventory-meta">
      <div class="inventory-meta__text">
        <span>{{ metaText }}</span>
        <span v-if="category === 'main_device' && meta.hidden_zero_record_count">
          · {{ t('inventory.page.hiddenZeroRecords', { count: meta.hidden_zero_record_count }) }}
        </span>
      </div>
      <div class="toolbar-actions">
        <el-button type="primary" :icon="Download" :loading="exporting" @click="exportInventory">
          {{ t('inventory.page.exportExcel') }}
        </el-button>
        <el-tooltip :content="t('inventory.page.refresh')" placement="top">
          <el-button :icon="Refresh" :loading="loading" @click="loadOverview" />
        </el-tooltip>
      </div>
    </div>

    <section class="inventory-results" aria-live="polite">
      <div v-if="errorMessage" class="result-state result-state--error">
        <el-icon><WarningFilled /></el-icon>
        <h3>{{ t('inventory.page.loadFailed') }}</h3>
        <p>{{ errorMessage }}</p>
        <el-button @click="loadOverview">{{ t('inventory.page.retry') }}</el-button>
      </div>

      <div v-else-if="!loading && !items.length" class="result-state">
        <el-icon><Search /></el-icon>
        <h3>{{ hasFilters ? t('inventory.page.noMatchingInventory') : t('inventory.page.noInventoryRecords') }}</h3>
        <p>{{ hasFilters ? t('inventory.page.adjustFilters') : t('inventory.page.inventoryEmptyHint') }}</p>
        <el-button v-if="hasFilters" @click="clearFilters">{{ t('inventory.page.clearFilters') }}</el-button>
      </div>

      <InventoryMainTable
        v-else-if="category === 'main_device'"
        :rows="items"
        :view-mode="viewMode"
        :loading="loading"
        @open-instances="openMainInstances"
        @open-history="openStockHistory"
      />

      <InventoryAuxiliaryTable
        v-else
        :rows="items"
        :view-mode="viewMode"
        :loading="loading"
        @open-details="openAuxiliaryDetails"
      />
    </section>

    <div v-if="total > pageSize" class="page-pagination">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="value => updateQuery({ page: value })"
        @size-change="value => updateQuery({ page_size: value, page: 1 })"
      />
    </div>

    <MainInstanceDrawer
      v-model="mainDrawerVisible"
      :context="drawerContext"
      :initial-status="mainDrawerStatus"
      :warehouses="warehouses"
    />

    <AuxiliaryDetailDrawer
      v-model="auxiliaryDrawerVisible"
      :context="drawerContext"
      :initial-mode="auxiliaryDrawerMode"
      :warehouses="warehouses"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, Refresh, Search, WarningFilled } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { stockApi } from '@/api/stock'
import InventoryKpiStrip from '@/components/inventory/InventoryKpiStrip.vue'
import InventoryMainTable from '@/components/inventory/InventoryMainTable.vue'
import InventoryAuxiliaryTable from '@/components/inventory/InventoryAuxiliaryTable.vue'
import MainInstanceDrawer from '@/components/inventory/MainInstanceDrawer.vue'
import AuxiliaryDetailDrawer from '@/components/inventory/AuxiliaryDetailDrawer.vue'
import { formatInventoryUnit } from '@/utils/inventoryDisplay'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const category = ref('main_device')
const viewMode = ref('equipment')
const searchInput = ref('')
const keyword = ref('')
const warehouseId = ref(null)
const statusFilter = ref('')
const includeZero = ref(false)
const page = ref(1)
const pageSize = ref(100)
const summary = ref({})
const meta = ref({})
const items = ref([])
const total = ref(0)
const warehouses = ref([])
const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const mainDrawerVisible = ref(false)
const auxiliaryDrawerVisible = ref(false)
const drawerContext = ref({})
const mainDrawerStatus = ref('')
const auxiliaryDrawerMode = ref('distribution')
let searchTimer = null
let requestSequence = 0

const mainStatuses = ['in_stock', 'issued', 'pending_inspection', 'inspected', 'return_pending_receive', 'abnormal']
const auxiliaryStatuses = ['stocked', 'zero_stock', 'needs_restock']

const statusOptions = computed(() => (
  category.value === 'main_device'
    ? mainStatuses.map(value => ({ value, label: t(`inventory.page.status.${value}`) }))
    : auxiliaryStatuses.map(value => ({ value, label: t(`inventory.page.auxFilter.${value}`) }))
))

const searchPlaceholder = computed(() => (
  category.value === 'main_device'
    ? t('inventory.page.searchMain')
    : t('inventory.page.searchAuxiliary')
))

const hasFilters = computed(() => Boolean(
  keyword.value || warehouseId.value || statusFilter.value || includeZero.value,
))

const metaText = computed(() => {
  if (category.value === 'main_device') {
    return [
      t('inventory.page.equipmentCount', { count: meta.value.equipment_count || 0 }),
      t('inventory.page.warehouseCount', { count: meta.value.warehouse_count || 0 }),
    ].join(' · ')
  }
  return [
    t('inventory.page.auxiliaryCount', { count: meta.value.equipment_count || 0 }),
    t('inventory.page.inventoryRecordCount', { count: meta.value.record_count || 0 }),
    t('inventory.page.warehouseCount', { count: meta.value.warehouse_count || 0 }),
  ].join(' · ')
})

const normalizeQuery = (query) => {
  const nextCategory = ['main_device', 'auxiliary'].includes(query.category) ? query.category : 'main_device'
  const allowedStatuses = nextCategory === 'main_device' ? mainStatuses : auxiliaryStatuses
  return {
    category: nextCategory,
    view: ['equipment', 'warehouse'].includes(query.view) ? query.view : 'equipment',
    q: String(query.q || ''),
    warehouse: query.warehouse ? Number(query.warehouse) : null,
    status: allowedStatuses.includes(query.status) ? query.status : '',
    zero: query.zero === '1',
    page: Math.max(Number(query.page) || 1, 1),
    page_size: [20, 50, 100].includes(Number(query.page_size)) ? Number(query.page_size) : 100,
  }
}

const syncStateFromRoute = () => {
  const state = normalizeQuery(route.query)
  category.value = state.category
  viewMode.value = state.view
  keyword.value = state.q
  searchInput.value = state.q
  warehouseId.value = state.warehouse
  statusFilter.value = state.status
  includeZero.value = state.zero
  page.value = state.page
  pageSize.value = state.page_size
}

const cleanQuery = (query) => Object.fromEntries(
  Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== '' && value !== false),
)

const updateQuery = (changes) => {
  router.replace({
    name: 'InventoryList',
    query: cleanQuery({
      category: category.value,
      view: viewMode.value,
      q: keyword.value || undefined,
      warehouse: warehouseId.value || undefined,
      status: statusFilter.value || undefined,
      zero: includeZero.value ? '1' : undefined,
      page: page.value > 1 ? page.value : undefined,
      page_size: pageSize.value !== 100 ? pageSize.value : undefined,
      ...changes,
    }),
  })
}

const overviewParams = (overrides = {}) => ({
  category: category.value,
  view_mode: viewMode.value,
  keyword: keyword.value,
  warehouse_id: warehouseId.value || undefined,
  status_filter: statusFilter.value,
  include_zero: includeZero.value,
  page: page.value,
  page_size: pageSize.value,
  ...overrides,
})

const loadOverview = async () => {
  const sequence = ++requestSequence
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await stockApi.getInventoryOverview(overviewParams())
    if (sequence !== requestSequence) return
    summary.value = response.summary || {}
    meta.value = response.meta || {}
    items.value = response.items || []
    total.value = response.total || 0
  } catch (error) {
    if (sequence !== requestSequence) return
    errorMessage.value = error.response?.data?.detail || error.message || t('inventory.page.loadFailed')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await stockApi.getWarehouses()
    warehouses.value = response.warehouses || []
  } catch (_error) {
    warehouses.value = []
  }
}

const changeCategory = (nextCategory) => {
  updateQuery({ category: nextCategory, status: undefined, page: 1 })
}

const scheduleSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(commitSearch, 300)
}

const commitSearch = () => {
  clearTimeout(searchTimer)
  updateQuery({ q: searchInput.value.trim() || undefined, page: 1 })
}

const clearFilters = () => updateQuery({
  q: undefined,
  warehouse: undefined,
  status: undefined,
  zero: undefined,
  page: 1,
})

const handleKpiSelect = (item) => {
  if (item.action === 'warehouse') {
    updateQuery({ view: 'warehouse', status: undefined, page: 1 })
    return
  }
  const nextStatus = statusFilter.value === item.filter ? undefined : item.filter || undefined
  updateQuery({ status: nextStatus, page: 1 })
}

const openMainInstances = (row, status) => {
  drawerContext.value = { ...row }
  mainDrawerStatus.value = status || ''
  mainDrawerVisible.value = true
}

const openAuxiliaryDetails = (row, mode) => {
  if (!row.equipment_id) return
  drawerContext.value = { ...row }
  auxiliaryDrawerMode.value = mode || 'distribution'
  auxiliaryDrawerVisible.value = true
}

const openStockHistory = (row) => {
  const query = { type: 'transaction' }
  if (row.equipment_code) query.keyword = row.equipment_code
  if (row.warehouse_id) query.warehouse_id = row.warehouse_id
  router.push({ name: 'StockHistory', query })
}

const exportInventory = async () => {
  exporting.value = true
  try {
    const groups = []
    let exportPage = 1
    let exportTotal = 0
    let batch = []
    do {
      const response = await stockApi.getInventoryOverview(overviewParams({ page: exportPage, page_size: 1000 }))
      batch = response.items || []
      groups.push(...batch)
      exportTotal = response.total || 0
      exportPage += 1
    } while (batch.length > 0 && groups.length < exportTotal)

    const children = groups.flatMap(group => group.children || [])
    const data = category.value === 'main_device'
      ? children.map(row => ({
          [t('inventory.page.equipmentCode')]: row.equipment_code,
          [t('inventory.page.equipmentName')]: row.equipment_name,
          [t('inventory.page.warehouse')]: row.warehouse_name || t('inventory.page.unassignedWarehouse'),
          [t('inventory.page.status.in_stock')]: row.in_stock,
          [t('inventory.page.status.issued')]: row.issued,
          [t('inventory.page.status.pending_inspection')]: row.pending_inspection,
          [t('inventory.page.status.inspected')]: row.inspected,
          [t('inventory.page.status.return_pending_receive')]: row.return_pending_receive,
          [t('inventory.page.status.abnormal')]: row.abnormal,
          [t('inventory.page.deviceTotal')]: row.device_total,
          [t('inventory.page.unit')]: formatInventoryUnit(row.unit, t),
        }))
      : children.map(row => ({
          [t('inventory.page.equipmentCode')]: row.equipment_code,
          [t('inventory.page.equipmentName')]: row.equipment_name,
          [t('inventory.page.warehouse')]: row.warehouse_name,
          [t('inventory.page.currentStock')]: row.current_stock,
          [t('inventory.page.outboundPending')]: row.allocated_stock,
          [t('inventory.page.unit')]: formatInventoryUnit(row.unit, t),
          [t('inventory.page.reorderPoint')]: row.reorder_configured ? row.min_stock : t('inventory.page.notConfigured'),
          [t('inventory.page.stockStatus')]: t(`inventory.page.auxStatus.${row.stock_status}`),
        }))
    const worksheet = XLSX.utils.json_to_sheet(data)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, category.value === 'main_device' ? 'Main devices' : 'Auxiliary')
    XLSX.writeFile(workbook, `inventory-${category.value}-${Date.now()}.xlsx`)
    ElMessage.success(t('inventory.page.exportSuccess', { count: data.length }))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('inventory.page.exportFailed'))
  } finally {
    exporting.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    syncStateFromRoute()
    loadOverview()
  },
  { immediate: true },
)

onMounted(loadWarehouses)
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>

<style scoped>
.inventory-page {
  min-width: 0;
  padding: 14px 24px 24px;
  color: #202733;
  background: #fff;
}

.inventory-category-tabs { margin: 0 0 10px; }
.inventory-category-tabs :deep(.el-tabs__header) { margin: 0; }
.inventory-category-tabs :deep(.el-tabs__content) { display: none; }
.inventory-category-tabs :deep(.el-tabs__item) { height: 40px; padding: 0 18px; font-size: 16px; }

.inventory-toolbar {
  display: grid;
  grid-template-columns: auto minmax(220px, 1fr) 150px 140px auto;
  gap: 12px;
  align-items: center;
  padding-top: 12px;
}

.inventory-toolbar :deep(.el-radio-button__inner) { min-width: 112px; }
.search-input { width: 100%; }
.toolbar-actions { display: flex; justify-content: flex-end; gap: 10px; }
.toolbar-actions .el-button + .el-button { margin-left: 0; }

.inventory-meta {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: #4f5867;
  font-size: 14px;
}
.inventory-meta__text { min-width: 0; }

.inventory-results { min-height: 360px; }
.result-state {
  display: flex;
  min-height: 360px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid #dfe3ea;
  border-radius: 6px;
  background: #fff;
  text-align: center;
}
.result-state .el-icon { color: #a4acb9; font-size: 44px; }
.result-state h3 { margin: 18px 0 0; font-size: 17px; letter-spacing: 0; }
.result-state p { margin: 9px 0 20px; color: #7a8391; }
.result-state--error .el-icon { color: #e5484d; }
.page-pagination { display: flex; justify-content: flex-end; padding-top: 18px; }

@media (max-width: 1100px) {
  .inventory-toolbar {
    grid-template-columns: auto minmax(180px, 1fr) 140px 140px;
    gap: 12px;
  }
  .inventory-toolbar > .el-switch { grid-column: 1 / -1; }
}

@media (max-width: 920px) {
  .inventory-page { padding: 16px; }
  .inventory-toolbar { grid-template-columns: 1fr 1fr; }
  .inventory-toolbar > * { width: 100%; }
  .search-input { grid-column: 1 / -1; }
  .inventory-meta { align-items: flex-start; flex-direction: column; padding: 10px 0; }
  .toolbar-actions { width: 100%; justify-content: flex-start; }
}
</style>
