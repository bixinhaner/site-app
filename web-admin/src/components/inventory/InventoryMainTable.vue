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
              {{ row.row_type === 'group' ? row.equipment_name : warehouseName(row) }}
            </span>
          </template>
          <template v-else>
            <span v-if="row.row_type === 'child'" class="identity-code">{{ row.equipment_code }}</span>
            <span v-if="row.row_type === 'child'" class="identity-separator">/</span>
            <span class="identity-name">
              {{ row.row_type === 'group' ? warehouseName(row) : row.equipment_name }}
            </span>
          </template>
        </div>
      </template>
    </el-table-column>

    <el-table-column :label="distributionLabel" min-width="120" align="center">
      <template #default="{ row }">
        <span v-if="row.row_type === 'group'">
          {{ viewMode === 'equipment'
            ? warehouseDistributionText(row)
            : t('inventory.page.equipmentCount', { count: row.equipment_count || 0 }) }}
        </span>
        <span v-else class="muted">-</span>
      </template>
    </el-table-column>

    <el-table-column
      v-for="column in statusColumns"
      :key="column.key"
      :label="column.label"
      :min-width="column.width"
      align="center"
    >
      <template #default="{ row }">
        <button
          v-if="Number(row[column.key] || 0) > 0"
          type="button"
          class="count-link"
          @click.stop="$emit('open-instances', row, column.key)"
        >
          {{ formatNumber(row[column.key]) }}
        </button>
        <span v-else class="zero-value">0</span>
      </template>
    </el-table-column>

    <el-table-column :label="t('inventory.page.deviceTotal')" min-width="88" align="center">
      <template #default="{ row }">
        <button
          v-if="Number(row.device_total || 0) > 0"
          type="button"
          class="count-link count-link--total"
          @click.stop="$emit('open-instances', row, '')"
        >
          {{ formatNumber(row.device_total) }}
        </button>
        <span v-else class="zero-value">0</span>
      </template>
    </el-table-column>

    <el-table-column :label="t('inventory.page.unit')" min-width="60" align="center">
      <template #default="{ row }">{{ formatInventoryUnit(row.unit, t) }}</template>
    </el-table-column>

    <el-table-column fixed="right" :label="t('inventory.page.actions')" width="86" align="center">
      <template #default="{ row }">
        <div class="icon-actions">
          <el-tooltip :content="t('inventory.page.deviceDetails')" placement="top">
            <el-button
              class="icon-action"
              link
              type="primary"
              :aria-label="t('inventory.page.deviceDetails')"
              @click.stop="$emit('open-instances', row, '')"
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
              @click.stop="$emit('open-history', row)"
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

defineEmits(['open-instances', 'open-history'])

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
const statusColumns = computed(() => [
  { key: 'in_stock', label: t('inventory.page.status.in_stock'), width: 78 },
  { key: 'issued', label: t('inventory.page.status.issued'), width: 78 },
  { key: 'pending_inspection', label: t('inventory.page.status.pending_inspection'), width: 82 },
  { key: 'inspected', label: t('inventory.page.status.inspected'), width: 78 },
  { key: 'return_pending_receive', label: t('inventory.page.status.return_pending_receive'), width: 80 },
  { key: 'abnormal', label: t('inventory.page.status.abnormal'), width: 70 },
])

watch(
  () => props.rows.map(row => row.key),
  (keys) => {
    expandedKeys.value = expandedKeys.value.filter(key => keys.includes(key))
    if (!expandedKeys.value.length && keys.length) expandedKeys.value = [keys[0]]
  },
  { immediate: true },
)

const handleExpandChange = (row, expanded) => {
  const key = row.key
  if (expanded && !expandedKeys.value.includes(key)) {
    expandedKeys.value.push(key)
  } else if (!expanded) {
    expandedKeys.value = expandedKeys.value.filter(value => value !== key)
  }
}

const toggleGroup = (row) => {
  if (row.row_type !== 'group') return
  tableRef.value?.toggleRowExpansion(row, !expandedKeys.value.includes(row.key))
}

const formatNumber = (value) => new Intl.NumberFormat(locale.value).format(Number(value || 0))
const warehouseName = (row) => row.warehouse_name || t('inventory.page.unassignedWarehouse')
const warehouseDistributionText = (row) => (
  row.unassigned_count
    ? t('inventory.page.warehouseWithUnassigned', {
        count: row.warehouse_count || 0,
        unassigned: row.unassigned_count,
      })
    : t('inventory.page.warehouseCount', { count: row.warehouse_count || 0 })
)
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
.muted, .zero-value { color: #697180; }

.count-link {
  border: 0;
  background: transparent;
  color: #1677ff;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  padding: 4px 6px;
}

.count-link:hover,
.count-link:focus-visible {
  border-radius: 3px;
  background: #eaf3ff;
  outline: 2px solid transparent;
  text-decoration: underline;
}

.count-link--total { color: #303744; }

.icon-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.icon-action {
  width: 28px;
  height: 28px;
  margin: 0;
  font-size: 19px;
}

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
