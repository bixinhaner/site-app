<template>
  <el-table
    ref="tableRef"
    class="inventory-table"
    :data="rows"
    :row-key="row => row.key"
    :tree-props="{ children: 'children' }"
    :expand-row-keys="expandedKeys"
    v-loading="loading"
    @expand-change="handleExpandChange"
  >
    <el-table-column fixed="left" :label="primaryLabel" min-width="300">
      <template #default="{ row }">
        <div
          class="identity-cell"
          :class="{
            'is-child': row.row_type === 'child',
            'is-group': row.row_type === 'group',
          }"
          :role="row.row_type === 'group' ? 'button' : undefined"
          :tabindex="row.row_type === 'group' ? 0 : undefined"
          :aria-expanded="row.row_type === 'group' ? expandedKeys.includes(row.key) : undefined"
          @click.stop="toggleGroup(row)"
          @keydown.enter.prevent="toggleGroup(row)"
          @keydown.space.prevent="toggleGroup(row)"
        >
          <template v-if="viewMode === 'equipment'">
            <span v-if="row.row_type === 'group'" class="identity-code">{{ row.equipment_code }}</span>
            <span v-if="row.row_type === 'group'" class="identity-separator">/</span>
            <span class="identity-name">
              {{ row.row_type === 'group' ? row.equipment_name : row.warehouse_name }}
            </span>
          </template>
          <template v-else>
            <span v-if="row.row_type === 'child'" class="identity-code">{{ row.equipment_code }}</span>
            <span v-if="row.row_type === 'child'" class="identity-separator">/</span>
            <span class="identity-name">
              {{ row.row_type === 'group' ? row.warehouse_name : row.equipment_name }}
            </span>
          </template>
        </div>
      </template>
    </el-table-column>

    <el-table-column :label="distributionLabel" min-width="110" align="center">
      <template #default="{ row }">
        <span v-if="row.row_type === 'group'">
          {{ viewMode === 'equipment'
            ? t('inventory.page.warehouseCount', { count: row.warehouse_count || 0 })
            : t('inventory.page.equipmentCount', { count: row.equipment_count || 0 }) }}
        </span>
        <span v-else class="muted">-</span>
      </template>
    </el-table-column>

    <el-table-column :label="t('inventory.page.currentStock')" min-width="110" align="center">
      <template #default="{ row }">
        <button
          v-if="row.equipment_id && Number(row.current_stock || 0) > 0"
          type="button"
          class="count-link"
          @click.stop="$emit('open-details', row, 'distribution')"
        >
          {{ formatNumber(row.current_stock) }}
        </button>
        <span v-else class="zero-value">{{ row.equipment_id ? formatNumber(row.current_stock) : '-' }}</span>
      </template>
    </el-table-column>

    <el-table-column :label="t('inventory.page.outboundPending')" min-width="122" align="center">
      <template #default="{ row }">
        <button
          v-if="row.equipment_id && Number(row.allocated_stock || 0) > 0"
          type="button"
          class="count-link"
          @click.stop="$emit('open-details', row, 'outbound')"
        >
          {{ formatNumber(row.allocated_stock) }}
        </button>
        <span v-else class="zero-value">{{ row.equipment_id ? formatNumber(row.allocated_stock) : '-' }}</span>
      </template>
    </el-table-column>

    <el-table-column :label="t('inventory.page.unit')" min-width="65" align="center">
      <template #default="{ row }">{{ formatInventoryUnit(row.unit, t) }}</template>
    </el-table-column>

    <el-table-column :label="t('inventory.page.stockStatus')" min-width="130" align="center">
      <template #default="{ row }">
        <span class="stock-status" :class="statusClass(row)">{{ statusText(row) }}</span>
      </template>
    </el-table-column>

    <el-table-column fixed="right" :label="t('inventory.page.actions')" width="86" align="center">
      <template #default="{ row }">
        <div v-if="row.equipment_id" class="icon-actions">
          <el-tooltip :content="t('inventory.page.stockDetails')" placement="top">
            <el-button
              class="icon-action"
              link
              type="primary"
              :aria-label="t('inventory.page.stockDetails')"
              @click.stop="$emit('open-details', row, 'distribution')"
            >
              <el-icon><Tickets /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip :content="t('inventory.page.stockHistory')" placement="top">
            <el-button
              class="icon-action"
              link
              type="primary"
              :aria-label="t('inventory.page.stockHistory')"
              @click.stop="$emit('open-details', row, 'transactions')"
            >
              <el-icon><Document /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Document, Tickets } from '@element-plus/icons-vue'
import { formatInventoryUnit } from '@/utils/inventoryDisplay'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  viewMode: { type: String, default: 'equipment' },
  loading: { type: Boolean, default: false },
})

defineEmits(['open-details'])

const { t, locale } = useI18n()
const tableRef = ref()
const expandedKeys = ref([])

const primaryLabel = computed(() => (
  props.viewMode === 'equipment'
    ? t('inventory.page.equipmentCodeName')
    : t('inventory.page.warehouse')
))
const distributionLabel = computed(() => (
  props.viewMode === 'equipment'
    ? t('inventory.page.warehouseDistribution')
    : t('inventory.page.equipmentTypes')
))
watch(
  () => props.rows.map(row => row.key),
  (keys) => {
    expandedKeys.value = expandedKeys.value.filter(key => keys.includes(key))
    if (!expandedKeys.value.length && keys.length) expandedKeys.value = [keys[0]]
  },
  { immediate: true },
)

const handleExpandChange = (row, expanded) => {
  if (expanded && !expandedKeys.value.includes(row.key)) {
    expandedKeys.value.push(row.key)
  } else if (!expanded) {
    expandedKeys.value = expandedKeys.value.filter(key => key !== row.key)
  }
}

const toggleGroup = (row) => {
  if (row.row_type !== 'group') return
  tableRef.value?.toggleRowExpansion(row, !expandedKeys.value.includes(row.key))
}

const normalizedStatus = (row) => {
  if (row.stock_status) return row.stock_status
  if (Number(row.needs_restock_count || 0) > 0) return 'needs_restock'
  if (Number(row.zero_stock_warehouse_count || 0) > 0) return 'partial_zero'
  if (Number(row.zero_stock_equipment_count || 0) > 0) {
    return Number(row.stocked_equipment_count || 0) > 0 ? 'partial_zero' : 'zero_stock'
  }
  return 'stocked'
}

const statusClass = (row) => `is-${normalizedStatus(row)}`
const statusText = (row) => {
  const status = normalizedStatus(row)
  if (status === 'needs_restock' && row.row_type === 'group' && row.needs_restock_count) {
    return t('inventory.page.restockWarehouseCount', { count: row.needs_restock_count })
  }
  if (status === 'partial_zero' && row.row_type === 'group') {
    if (props.viewMode === 'warehouse') {
      return t('inventory.page.zeroEquipmentCount', { count: row.zero_stock_equipment_count })
    }
    return t('inventory.page.zeroWarehouseCount', { count: row.zero_stock_warehouse_count })
  }
  if (status === 'zero_stock' && row.row_type === 'group' && props.viewMode === 'warehouse') {
    return t('inventory.page.zeroEquipmentCount', { count: row.zero_stock_equipment_count })
  }
  return t(`inventory.page.auxStatus.${status}`)
}

const formatNumber = (value) => new Intl.NumberFormat(locale.value).format(Number(value || 0))
</script>

<style scoped>
.inventory-table {
  width: 100%;
  border: 1px solid #dfe3ea;
  border-radius: 6px;
  overflow: hidden;
  --el-table-header-bg-color: #f7f8fa;
  --el-table-row-hover-bg-color: #f7faff;
  --el-table-border-color: #e5e8ee;
  --el-table-text-color: #303744;
  --el-table-header-text-color: #202733;
}

.identity-cell {
  display: flex;
  min-width: 0;
  min-height: 28px;
  align-items: center;
  gap: 8px;
  line-height: 20px;
}
.identity-cell.is-group { cursor: pointer; }
.identity-cell.is-group:hover .identity-code,
.identity-cell.is-group:hover .identity-name { color: #1677ff; }
.identity-cell.is-group:focus-visible {
  border-radius: 3px;
  outline: 2px solid #91caff;
  outline-offset: 2px;
}
.identity-cell.is-child { color: #424a57; }
.identity-code { flex: 0 0 auto; font-variant-numeric: tabular-nums; }
.identity-separator { color: #9aa1ad; }
.identity-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted, .zero-value { color: #697180; font-variant-numeric: tabular-nums; }

.count-link {
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #1677ff;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  padding: 4px 6px;
}

.count-link:hover,
.count-link:focus-visible { background: #eaf3ff; outline: none; text-decoration: underline; }

.stock-status { font-weight: 500; }
.stock-status.is-stocked { color: #24a36a; }
.stock-status.is-zero_stock,
.stock-status.is-partial_zero { color: #d46b08; }
.stock-status.is-needs_restock { color: #f05225; font-weight: 600; }

.icon-actions { display: flex; align-items: center; justify-content: center; gap: 8px; }
.icon-action { width: 28px; height: 28px; margin: 0; font-size: 19px; }

:deep(.el-table__cell) { height: 60px; padding: 8px 0; }
:deep(.el-table__header .el-table__cell) { height: 48px; }
:deep(.el-table__body td:first-child > .cell) {
  display: flex;
  min-height: 40px;
  align-items: center;
}
:deep(.el-table__expand-icon) {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  align-items: center;
  justify-content: center;
  margin-right: 4px;
  border-radius: 50%;
  color: #697180;
  transition: background-color 160ms ease, color 160ms ease, transform 160ms ease;
}
:deep(.el-table__expand-icon:hover) {
  background: #eaf3ff;
  color: #1677ff;
}
:deep(.el-table__expand-icon .el-icon) { font-size: 15px; }
:deep(.el-table__indent) { padding-left: 16px !important; }
</style>
