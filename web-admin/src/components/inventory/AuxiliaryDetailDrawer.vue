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
          <h2>{{ context.equipment_name || t('inventory.page.auxiliaryInventory') }}</h2>
          <p>
            {{ context.equipment_code || '-' }}
            <span>·</span>
            {{ t('inventory.page.unitValue', { unit: formatInventoryUnit(context.unit, t) }) }}
          </p>
        </div>
        <div class="drawer-actions">
          <el-button :icon="Download" :loading="exporting" @click="exportRows">
            {{ t('inventory.page.exportExcel') }}
          </el-button>
          <el-button :icon="Close" :aria-label="t('inventory.page.close')" @click="closeDrawer" />
        </div>
      </header>

      <section class="aux-summary">
        <button type="button" @click="selectMode('distribution')">
          <span>{{ t('inventory.page.currentStock') }}</span>
          <strong>{{ quantityWithUnit(summary.current_stock) }}</strong>
        </button>
        <button type="button" @click="selectMode('outbound')">
          <span>{{ t('inventory.page.outboundPending') }}</span>
          <strong class="blue">{{ quantityWithUnit(summary.allocated_stock) }}</strong>
        </button>
        <button type="button" @click="selectMode('distribution')">
          <span>{{ t('inventory.page.warehouses') }}</span>
          <strong>{{ formatNumber(summary.warehouse_count) }}</strong>
        </button>
      </section>

      <nav class="detail-tabs" :aria-label="t('inventory.page.auxiliaryDetails')">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="{ 'is-active': mode === tab.key }"
          @click="selectMode(tab.key)"
        >
          {{ tab.label }}
          <span v-if="tab.key === 'distribution'">{{ summary.warehouse_count || 0 }}</span>
        </button>
      </nav>

      <div class="drawer-toolbar" :class="{ 'is-distribution': mode === 'distribution' }">
        <el-input
          v-model="keyword"
          clearable
          :placeholder="searchPlaceholder"
          :prefix-icon="Search"
          @input="scheduleLoad"
          @keyup.enter="loadRows(true)"
          @clear="loadRows(true)"
        />
        <el-select
          v-if="mode !== 'distribution'"
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
        <el-switch
          v-if="mode === 'distribution'"
          v-model="includeZero"
          :active-text="t('inventory.page.showZeroStock')"
          @change="loadRows(true)"
        />
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
          v-else-if="mode === 'distribution'"
          :data="rows"
          v-loading="loading"
          :empty-text="t('inventory.page.noInventoryRecords')"
          height="100%"
          class="drawer-table"
        >
          <el-table-column prop="warehouse_name" :label="t('inventory.page.warehouse')" min-width="210" show-overflow-tooltip />
          <el-table-column :label="t('inventory.page.currentStock')" width="118" align="center">
            <template #default="{ row }"><span class="number blue">{{ formatNumber(row.current_stock) }}</span></template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.outboundPending')" width="126" align="center">
            <template #default="{ row }"><span class="number blue">{{ formatNumber(row.allocated_stock) }}</span></template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.reorderPoint')" width="112" align="center">
            <template #default="{ row }">
              <span :class="{ warning: !row.reorder_configured }">
                {{ row.reorder_configured ? formatNumber(row.min_stock) : t('inventory.page.notConfigured') }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.stockStatus')" width="106" align="center">
            <template #default="{ row }">
              <span class="stock-status" :class="`is-${row.stock_status}`">{{ t(`inventory.page.auxStatus.${row.stock_status}`) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.lastUpdated')" width="144">
            <template #default="{ row }">{{ formatDateTime(row.last_updated_at) }}</template>
          </el-table-column>
          <el-table-column fixed="right" :label="t('inventory.page.actions')" width="72" align="center">
            <template #default="{ row }">
              <el-tooltip :content="t('inventory.page.viewStockHistory')" placement="top">
                <el-button link type="primary" :icon="Document" @click="openHistory(row)" />
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>

        <el-table
          v-else-if="mode === 'outbound'"
          :data="rows"
          v-loading="loading"
          :empty-text="mode === 'outbound' ? t('inventory.page.noOutboundPending') : t('inventory.page.noTransactions')"
          height="100%"
          class="drawer-table"
        >
          <el-table-column :label="t('inventory.page.documentRequest')" min-width="220">
            <template #default="{ row }">
              <button class="document-link" type="button" @click="openDocument(row)">{{ row.document_number || '-' }}</button>
              <button v-if="row.material_request_no" class="document-link secondary" type="button" @click="openRequest(row)">{{ row.material_request_no }}</button>
            </template>
          </el-table-column>
          <el-table-column prop="warehouse_name" :label="t('inventory.page.sourceWarehouse')" min-width="150" show-overflow-tooltip />
          <el-table-column prop="issued_to_name" :label="t('inventory.page.owner')" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.issued_to_name || '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.outboundQuantity')" width="86" align="center">
            <template #default="{ row }">{{ formatNumber(row.quantity) }}</template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.returnedQuantity')" width="78" align="center">
            <template #default="{ row }">{{ formatNumber(row.returned_quantity) }}</template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.pendingQuantity')" width="78" align="center">
            <template #default="{ row }"><strong>{{ formatNumber(row.pending_quantity) }}</strong></template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.operationTime')" width="144">
            <template #default="{ row }">{{ formatDateTime(row.operation_time) }}</template>
          </el-table-column>
          <el-table-column fixed="right" :label="t('inventory.page.actions')" width="72" align="center">
            <template #default="{ row }">
              <el-tooltip :content="t('inventory.page.viewDocument')" placement="top">
                <el-button link type="primary" :icon="Document" @click="openDocument(row)" />
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>

        <el-table
          v-else
          :data="rows"
          v-loading="loading"
          :empty-text="t('inventory.page.noTransactions')"
          height="100%"
          class="drawer-table"
        >
          <el-table-column :label="t('inventory.page.documentNumber')" min-width="210">
            <template #default="{ row }">
              <button class="document-link" type="button" @click="openDocument(row)">{{ row.document_number || '-' }}</button>
            </template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.transactionType')" width="112" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="transactionTagType(row.transaction_type)">
                {{ t(`inventory.page.transactionTypes.${row.transaction_type}`) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="warehouse_name" :label="t('inventory.page.warehouse')" min-width="150" show-overflow-tooltip />
          <el-table-column prop="issued_to_name" :label="t('inventory.page.owner')" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.issued_to_name || '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.quantity')" width="94" align="center">
            <template #default="{ row }">{{ formatNumber(row.quantity) }}</template>
          </el-table-column>
          <el-table-column :label="t('inventory.page.operationTimeGeneric')" width="150">
            <template #default="{ row }">{{ formatDateTime(row.operation_time) }}</template>
          </el-table-column>
          <el-table-column fixed="right" :label="t('inventory.page.actions')" width="72" align="center">
            <template #default="{ row }">
              <el-tooltip :content="t('inventory.page.viewDocument')" placement="top">
                <el-button link type="primary" :icon="Document" @click="openDocument(row)" />
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
import { Close, Document, Download, Refresh, Search } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { stockApi } from '@/api/stock'
import { formatInventoryUnit } from '@/utils/inventoryDisplay'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  context: { type: Object, default: () => ({}) },
  initialMode: { type: String, default: 'distribution' },
  warehouses: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])
const { t, locale } = useI18n()
const router = useRouter()

const rows = ref([])
const summary = ref({})
const mode = ref('distribution')
const keyword = ref('')
const selectedWarehouseId = ref(null)
const includeZero = ref(false)
const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
let debounceTimer = null

const drawerSize = computed(() => (window.innerWidth < 1150 ? '95%' : '1080px'))
const tabs = computed(() => [
  { key: 'distribution', label: t('inventory.page.stockDistribution') },
  { key: 'outbound', label: t('inventory.page.outboundPending') },
  { key: 'transactions', label: t('inventory.page.stockTransactions') },
])
const searchPlaceholder = computed(() => (
  mode.value === 'distribution'
    ? t('inventory.page.searchWarehouse')
    : t('inventory.page.searchDocumentOwner')
))

const requestParams = (overrides = {}) => ({
  mode: mode.value,
  keyword: keyword.value.trim(),
  warehouse_id: selectedWarehouseId.value || undefined,
  include_zero: includeZero.value,
  page: page.value,
  page_size: pageSize.value,
  ...overrides,
})

const loadRows = async (resetPage = false) => {
  if (!props.modelValue || !props.context.equipment_id) return
  if (resetPage) page.value = 1
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await stockApi.getAuxiliaryInventoryDetails(
      props.context.equipment_id,
      requestParams(),
    )
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

const selectMode = (nextMode) => {
  mode.value = nextMode
  keyword.value = ''
  page.value = 1
  loadRows(false)
}

const scheduleLoad = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadRows(true), 300)
}

const closeDrawer = () => emit('update:modelValue', false)
const openHistory = (row) => router.push({
  name: 'StockHistory',
  query: { type: 'transaction', keyword: props.context.equipment_code, warehouse_id: row.warehouse_id },
})
const openDocument = (row) => router.push({
  name: 'StockHistory',
  query: { type: 'transaction', keyword: row.document_number },
})
const openRequest = (row) => {
  if (row.material_request_id) {
    router.push({ name: 'MaterialRequestDetail', params: { id: row.material_request_id } })
  } else {
    router.push({ name: 'StockHistory', query: { keyword: row.material_request_no } })
  }
}

const exportRows = async () => {
  exporting.value = true
  try {
    const exportRows = []
    let exportPage = 1
    let exportTotal = 0
    let batch = []
    do {
      const response = await stockApi.getAuxiliaryInventoryDetails(
        props.context.equipment_id,
        requestParams({ page: exportPage, page_size: 1000 }),
      )
      batch = response.items || []
      exportRows.push(...batch)
      exportTotal = response.total || 0
      exportPage += 1
    } while (batch.length > 0 && exportRows.length < exportTotal)

    const data = exportRows.map(row => (
      mode.value === 'distribution'
        ? {
            [t('inventory.page.warehouse')]: row.warehouse_name,
            [t('inventory.page.currentStock')]: row.current_stock,
            [t('inventory.page.outboundPending')]: row.allocated_stock,
            [t('inventory.page.reorderPoint')]: row.reorder_configured ? row.min_stock : t('inventory.page.notConfigured'),
            [t('inventory.page.stockStatus')]: t(`inventory.page.auxStatus.${row.stock_status}`),
          }
        : {
            [t('inventory.page.documentNumber')]: row.document_number,
            [t('inventory.page.requestNumber')]: row.material_request_no || '',
            [t('inventory.page.sourceWarehouse')]: row.warehouse_name,
            [t('inventory.page.owner')]: row.issued_to_name || '',
            [t('inventory.page.outboundQuantity')]: row.quantity,
            [t('inventory.page.returnedQuantity')]: row.returned_quantity,
            [t('inventory.page.pendingQuantity')]: row.pending_quantity,
            [t('inventory.page.operationTime')]: formatDateTime(row.operation_time),
          }
    ))
    const worksheet = XLSX.utils.json_to_sheet(data)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Auxiliary')
    XLSX.writeFile(workbook, `inventory-auxiliary-${Date.now()}.xlsx`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('inventory.page.exportFailed'))
  } finally {
    exporting.value = false
  }
}

const formatNumber = (value) => new Intl.NumberFormat(locale.value).format(Number(value || 0))
const transactionTagType = (type) => ({
  stock_in: 'success',
  stock_out: 'warning',
  return: 'primary',
  transfer: 'info',
  adjustment: '',
  damage: 'danger',
}[type] || 'info')
const quantityWithUnit = (value) => {
  const unit = formatInventoryUnit(props.context.unit, t)
  return `${formatNumber(value)}${unit === '-' ? '' : unit}`
}
const formatDateTime = (value) => value ? new Intl.DateTimeFormat(locale.value, {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
}).format(new Date(value)) : '-'

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    mode.value = props.initialMode || 'distribution'
    keyword.value = ''
    selectedWarehouseId.value = props.context.warehouse_id || null
    includeZero.value = false
    page.value = 1
    loadRows(false)
  },
)

onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>

<style scoped>
.drawer-shell { display: grid; min-width: 0; height: 100%; overflow: hidden; grid-template-rows: auto auto auto auto minmax(0, 1fr) auto; }
.drawer-shell > * { min-width: 0; box-sizing: border-box; }
.drawer-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 22px 24px 18px; border-bottom: 1px solid #e5e8ee; }
.drawer-heading { min-width: 0; }
.drawer-heading h2 { margin: 0; color: #171d27; font-size: 19px; line-height: 28px; letter-spacing: 0; }
.drawer-heading p { display: flex; gap: 8px; margin: 5px 0 0; color: #697180; font-size: 14px; }
.drawer-actions { display: flex; flex: 0 0 auto; gap: 8px; }
.aux-summary { display: grid; grid-template-columns: repeat(3, 1fr); margin: 20px 24px 0; border: 1px solid #dfe3ea; border-radius: 5px; }
.aux-summary button { display: flex; min-height: 90px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; border: 0; border-right: 1px solid #e5e8ee; background: #fff; cursor: pointer; font: inherit; }
.aux-summary button:last-child { border-right: 0; }
.aux-summary button:hover, .aux-summary button:focus-visible { background: #f7faff; outline: none; }
.aux-summary span { color: #4f5867; }
.aux-summary strong { color: #202733; font-size: 19px; font-variant-numeric: tabular-nums; }
.blue { color: #1677ff !important; }
.detail-tabs { display: flex; gap: 10px; margin: 12px 24px 0; border-bottom: 1px solid #e5e8ee; }
.detail-tabs button { min-height: 48px; padding: 0 14px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #4d5665; cursor: pointer; font: inherit; }
.detail-tabs button:hover, .detail-tabs button:focus-visible, .detail-tabs button.is-active { color: #1677ff; border-bottom-color: #1677ff; outline: none; }
.detail-tabs span { margin-left: 4px; border-radius: 10px; background: #eef1f5; color: #697180; font-size: 12px; padding: 1px 6px; }
.drawer-toolbar { display: grid; grid-template-columns: minmax(240px, 1fr) 210px 40px; gap: 14px; padding: 18px 24px; }
.drawer-toolbar.is-distribution { grid-template-columns: minmax(240px, 1fr) 180px 40px; align-items: center; }
.drawer-content { min-height: 0; overflow: hidden; padding: 0 24px; }
.drawer-table { height: 100%; border: 1px solid #dfe3ea; border-radius: 5px; overflow: hidden; --el-table-header-bg-color: #f7f8fa; }
.drawer-footer { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 72px; padding: 12px 24px; color: #596273; }
.number { font-weight: 600; font-variant-numeric: tabular-nums; }
.warning { color: #f05225; }
.stock-status.is-stocked { color: #24a36a; }
.stock-status.is-zero_stock { color: #d46b08; }
.stock-status.is-needs_restock { color: #f05225; font-weight: 600; }
.document-link { display: block; max-width: 100%; overflow: hidden; padding: 2px 0; border: 0; background: transparent; color: #1677ff; cursor: pointer; font: inherit; text-overflow: ellipsis; white-space: nowrap; }
.document-link:hover, .document-link:focus-visible { text-decoration: underline; outline: none; }
.document-link.secondary { font-size: 12px; }
:deep(.el-drawer__body) { padding: 0; }
:deep(.drawer-table .el-table__cell) { height: 58px; }
@media (max-width: 720px) {
  .drawer-header { align-items: stretch; flex-direction: column; }
  .drawer-toolbar, .drawer-toolbar.is-distribution { grid-template-columns: 1fr 44px; }
  .drawer-toolbar .el-select, .drawer-toolbar .el-switch { grid-column: 1 / -1; grid-row: 2; }
  .drawer-footer { align-items: flex-start; flex-direction: column; }
}
</style>
