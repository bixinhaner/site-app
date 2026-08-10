<template>
  <el-drawer
    :model-value="modelValue"
    :size="drawerSize"
    :with-header="false"
    class="inventory-drawer"
    @close="closeDrawer"
  >
    <div class="drawer-shell">
      <header class="drawer-header">
        <div class="drawer-heading">
          <h2>{{ title }}</h2>
          <p>{{ subtitle }}</p>
        </div>
        <div class="drawer-actions">
          <el-tooltip :content="t('inventory.page.exportExcel')" placement="bottom">
            <el-button :icon="Download" :loading="exporting" @click="exportRows" />
          </el-tooltip>
          <el-button :icon="Close" :aria-label="t('inventory.page.close')" @click="closeDrawer" />
        </div>
      </header>

      <nav class="status-tabs" :aria-label="t('inventory.page.deviceStatus')">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="{ 'is-active': activeStatus === tab.key }"
          @click="selectStatus(tab.key)"
        >
          <span>{{ tab.label }}</span>
          <strong>{{ formatNumber(tab.count) }}</strong>
        </button>
      </nav>

      <div class="drawer-toolbar">
        <el-input
          v-model="keyword"
          clearable
          :placeholder="t('inventory.page.searchSnSite')"
          :prefix-icon="Search"
          @input="scheduleLoad"
          @keyup.enter="loadRows(true)"
          @clear="loadRows(true)"
        />
        <el-select
          v-model="selectedWarehouseId"
          clearable
          :placeholder="t('inventory.page.allWarehouses')"
          @change="loadRows(true)"
        >
          <el-option
            v-for="warehouse in warehouses"
            :key="warehouse.id"
            :label="warehouse.warehouse_name"
            :value="warehouse.id"
          />
        </el-select>
        <el-tooltip :content="t('inventory.page.refresh')" placement="top">
          <el-button :icon="Refresh" :loading="loading" @click="loadRows(false)" />
        </el-tooltip>
      </div>

      <div class="drawer-content">
        <el-alert
          v-if="errorMessage"
          type="error"
          :title="errorMessage"
          :closable="false"
          show-icon
        >
          <template #default>
            <el-button link type="primary" @click="loadRows(false)">{{ t('inventory.page.retry') }}</el-button>
          </template>
        </el-alert>

        <el-table
          v-else
          :data="rows"
          v-loading="loading"
          :empty-text="t('inventory.page.noDeviceInstances')"
          height="100%"
          class="drawer-table"
        >
          <el-table-column prop="serial_number" label="SN" min-width="178" show-overflow-tooltip />
          <el-table-column :label="t('inventory.page.statusLabel')" width="98">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status_bucket)">
                {{ t(`inventory.page.status.${row.status_bucket}`) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.sourceWarehouse')" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.warehouse_name || t('inventory.page.unassignedWarehouse') }}</template>
          </el-table-column>
          <el-table-column prop="issued_to_name" :label="t('inventory.page.owner')" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.issued_to_name || '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.siteSector')" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.site_code">
                {{ row.site_code }}<template v-if="row.sector_id"> / {{ t('inventory.page.sectorValue', { value: row.sector_id }) }}</template>
              </span>
              <span v-else class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.statusTime')" width="148">
            <template #default="{ row }">{{ formatDateTime(row.status_time) }}</template>
          </el-table-column>
          <el-table-column fixed="right" :label="t('inventory.page.actions')" width="72" align="center">
            <template #default="{ row }">
              <el-tooltip :content="t('inventory.page.deviceTracking')" placement="top">
                <el-button link type="primary" :icon="DocumentChecked" @click="trackDevice(row.serial_number)" />
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <footer class="drawer-footer">
        <span>{{ t('inventory.page.totalRows', { count: total }) }}</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="prev, pager, next, sizes"
          @current-change="loadRows(false)"
          @size-change="loadRows(true)"
        />
      </footer>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Close, DocumentChecked, Download, Refresh, Search } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { stockApi } from '@/api/stock'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  context: { type: Object, default: () => ({}) },
  initialStatus: { type: String, default: '' },
  warehouses: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])
const { t, locale } = useI18n()
const router = useRouter()

const rows = ref([])
const summary = ref({})
const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const activeStatus = ref('')
const keyword = ref('')
const selectedWarehouseId = ref(null)
const page = ref(1)
const pageSize = ref(20)
let debounceTimer = null

const drawerSize = computed(() => (window.innerWidth < 1150 ? '95%' : '1080px'))
const title = computed(() => {
  const identity = props.context.equipment_name || props.context.warehouse_name || t('inventory.page.mainDeviceInventory')
  const status = activeStatus.value ? t(`inventory.page.status.${activeStatus.value}`) : t('inventory.page.allDevices')
  return `${identity} · ${status}`
})
const subtitle = computed(() => {
  const parts = [props.context.equipment_code, props.context.warehouse_name]
  return parts.filter(Boolean).join(' · ') || t('inventory.page.deviceInstanceDetails')
})

const tabs = computed(() => [
  { key: '', label: t('inventory.page.all'), count: summary.value.device_total },
  { key: 'in_stock', label: t('inventory.page.status.in_stock'), count: summary.value.in_stock },
  { key: 'issued', label: t('inventory.page.status.issued'), count: summary.value.issued },
  { key: 'pending_inspection', label: t('inventory.page.status.pending_inspection'), count: summary.value.pending_inspection },
  { key: 'inspected', label: t('inventory.page.status.inspected'), count: summary.value.inspected },
  { key: 'return_pending_receive', label: t('inventory.page.status.return_pending_receive'), count: summary.value.return_pending_receive },
  { key: 'abnormal', label: t('inventory.page.status.abnormal'), count: summary.value.abnormal },
])

const requestParams = (overrides = {}) => ({
  equipment_id: props.context.equipment_id || undefined,
  warehouse_id: selectedWarehouseId.value || undefined,
  status_filter: activeStatus.value,
  keyword: keyword.value.trim(),
  page: page.value,
  page_size: pageSize.value,
  ...overrides,
})

const loadRows = async (resetPage = false) => {
  if (!props.modelValue) return
  if (resetPage) page.value = 1
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await stockApi.getMainInventoryInstances(requestParams())
    rows.value = response.items || []
    summary.value = response.summary || {}
    total.value = response.total || 0
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error.response?.data?.detail || error.message || t('inventory.page.loadFailed')
  } finally {
    loading.value = false
  }
}

const total = ref(0)

const selectStatus = (status) => {
  activeStatus.value = status
  loadRows(true)
}

const scheduleLoad = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadRows(true), 300)
}

const closeDrawer = () => emit('update:modelValue', false)

const trackDevice = (serialNumber) => {
  router.push({ name: 'EquipmentLifecycle', query: { sn: serialNumber } })
}

const exportRows = async () => {
  exporting.value = true
  try {
    const exportRows = []
    let exportPage = 1
    let exportTotal = 0
    let batch = []
    do {
      const response = await stockApi.getMainInventoryInstances(
        requestParams({ page: exportPage, page_size: 1000 }),
      )
      batch = response.items || []
      exportRows.push(...batch)
      exportTotal = response.total || 0
      exportPage += 1
    } while (batch.length > 0 && exportRows.length < exportTotal)

    const data = exportRows.map(row => ({
      SN: row.serial_number,
      [t('inventory.page.statusLabel')]: t(`inventory.page.status.${row.status_bucket}`),
      [t('inventory.page.sourceWarehouse')]: row.warehouse_name || '',
      [t('inventory.page.owner')]: row.issued_to_name || '',
      [t('inventory.page.site')]: row.site_code || '',
      [t('inventory.page.sector')]: row.sector_id || '',
      [t('inventory.page.statusTime')]: formatDateTime(row.status_time),
    }))
    const worksheet = XLSX.utils.json_to_sheet(data)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'SN')
    XLSX.writeFile(workbook, `inventory-sn-${Date.now()}.xlsx`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('inventory.page.exportFailed'))
  } finally {
    exporting.value = false
  }
}

const statusTagType = (status) => ({
  in_stock: 'success',
  issued: 'info',
  pending_inspection: 'warning',
  inspected: 'success',
  return_pending_receive: 'warning',
  abnormal: 'danger',
}[status] || 'info')

const formatNumber = (value) => new Intl.NumberFormat(locale.value).format(Number(value || 0))
const formatDateTime = (value) => value ? new Intl.DateTimeFormat(locale.value, {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
}).format(new Date(value)) : '-'

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    activeStatus.value = props.initialStatus || ''
    keyword.value = ''
    selectedWarehouseId.value = props.context.warehouse_id || null
    page.value = 1
    loadRows(false)
  },
)

onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>

<style scoped>
.drawer-shell { display: grid; min-width: 0; height: 100%; overflow: hidden; grid-template-rows: auto auto auto minmax(0, 1fr) auto; }
.drawer-shell > * { min-width: 0; box-sizing: border-box; }
.drawer-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 22px 28px 18px; border-bottom: 1px solid #e5e8ee; }
.drawer-heading { min-width: 0; }
.drawer-heading h2 { margin: 0; color: #171d27; font-size: 20px; line-height: 28px; letter-spacing: 0; }
.drawer-heading p { margin: 5px 0 0; color: #697180; font-size: 14px; }
.drawer-actions { display: flex; flex: 0 0 auto; gap: 8px; }
.status-tabs { display: flex; gap: 10px; overflow-x: auto; padding: 18px 28px 0; border-bottom: 1px solid #e5e8ee; }
.status-tabs button { display: flex; flex: 0 0 auto; align-items: center; gap: 6px; min-height: 42px; padding: 0 10px 10px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #616a78; cursor: pointer; font: inherit; }
.status-tabs button:hover, .status-tabs button:focus-visible, .status-tabs button.is-active { color: #1677ff; border-bottom-color: #1677ff; outline: none; }
.status-tabs strong { font-weight: 500; }
.drawer-toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) 220px 40px; gap: 14px; padding: 20px 28px; }
.drawer-content { min-height: 0; overflow: hidden; padding: 0 28px; }
.drawer-table { height: 100%; border: 1px solid #dfe3ea; border-radius: 5px; overflow: hidden; --el-table-header-bg-color: #f7f8fa; }
.drawer-footer { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 74px; padding: 14px 28px; color: #596273; }
.muted { color: #8a929f; }
:deep(.el-drawer__body) { padding: 0; }
:deep(.drawer-table .el-table__cell) { height: 58px; }
@media (max-width: 720px) {
  .drawer-toolbar { grid-template-columns: 1fr 44px; }
  .drawer-toolbar .el-select { grid-column: 1 / -1; grid-row: 2; }
  .drawer-footer { align-items: flex-start; flex-direction: column; }
}
</style>
