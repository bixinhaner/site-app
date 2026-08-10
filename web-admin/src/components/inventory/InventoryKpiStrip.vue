<template>
  <section
    class="kpi-strip"
    :aria-label="t('inventory.page.summary')"
    :style="{ '--kpi-columns': itemCount }"
  >
    <template v-if="loading && !hasSummary">
      <div v-for="index in itemCount" :key="index" class="kpi-item kpi-item--loading">
        <el-skeleton :rows="1" animated />
      </div>
    </template>
    <button
      v-for="item in items"
      v-else
      :key="item.key"
      type="button"
      class="kpi-item"
      :class="{ 'is-active': activeFilter && activeFilter === item.filter }"
      @click="$emit('select', item)"
    >
      <span class="kpi-label">{{ item.label }}</span>
      <strong class="kpi-value" :class="item.tone">{{ formatNumber(item.value) }}</strong>
    </button>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  category: { type: String, required: true },
  summary: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  activeFilter: { type: String, default: '' },
})

defineEmits(['select'])

const { t, locale } = useI18n()

const itemCount = computed(() => (props.category === 'main_device' ? 7 : 6))
const hasSummary = computed(() => Object.keys(props.summary || {}).length > 0)

const mainItems = computed(() => [
  { key: 'in_stock', label: t('inventory.page.status.in_stock'), value: props.summary.in_stock, filter: 'in_stock', tone: 'orange' },
  { key: 'issued', label: t('inventory.page.status.issued'), value: props.summary.issued, filter: 'issued', tone: 'blue' },
  { key: 'pending_inspection', label: t('inventory.page.status.pending_inspection'), value: props.summary.pending_inspection, filter: 'pending_inspection', tone: 'blue' },
  { key: 'inspected', label: t('inventory.page.status.inspected'), value: props.summary.inspected, filter: 'inspected', tone: 'blue' },
  { key: 'return_pending_receive', label: t('inventory.page.status.return_pending_receive'), value: props.summary.return_pending_receive, filter: 'return_pending_receive', tone: 'neutral' },
  { key: 'abnormal', label: t('inventory.page.status.abnormal'), value: props.summary.abnormal, filter: 'abnormal', tone: props.summary.abnormal ? 'danger' : 'neutral' },
  { key: 'device_total', label: t('inventory.page.deviceTotal'), value: props.summary.device_total, filter: '', tone: 'orange' },
])

const auxiliaryItems = computed(() => [
  { key: 'equipment_type_count', label: t('inventory.page.auxiliaryTypes'), value: props.summary.equipment_type_count, filter: '', tone: 'orange' },
  { key: 'warehouse_count', label: t('inventory.page.warehouses'), value: props.summary.warehouse_count, action: 'warehouse', tone: 'blue' },
  { key: 'inventory_record_count', label: t('inventory.page.inventoryRecords'), value: props.summary.inventory_record_count, action: 'warehouse', tone: 'blue' },
  { key: 'stocked_record_count', label: t('inventory.page.stockedRecords'), value: props.summary.stocked_record_count, filter: 'stocked', tone: 'blue' },
  { key: 'zero_stock_record_count', label: t('inventory.page.zeroRecords'), value: props.summary.zero_stock_record_count, filter: 'zero_stock', tone: 'neutral' },
  { key: 'needs_restock_count', label: t('inventory.page.needsRestock'), value: props.summary.needs_restock_count, filter: 'needs_restock', tone: props.summary.needs_restock_count ? 'danger' : 'neutral' },
])

const items = computed(() => (
  props.category === 'main_device' ? mainItems.value : auxiliaryItems.value
))

const formatNumber = (value) => new Intl.NumberFormat(locale.value).format(Number(value || 0))
</script>

<style scoped>
.kpi-strip {
  position: relative;
  display: grid;
  grid-template-columns: repeat(var(--kpi-columns, 7), minmax(0, 1fr));
  min-height: 72px;
  border: 1px solid #dfe3ea;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}

.kpi-item {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 70px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 0;
  border-right: 1px solid #e5e8ee;
  background: transparent;
  color: #303744;
  cursor: pointer;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.kpi-item:last-of-type {
  border-right: 0;
}

.kpi-item:hover,
.kpi-item:focus-visible,
.kpi-item.is-active {
  background: #f7faff;
  box-shadow: inset 0 -3px 0 #409eff;
  outline: none;
}

.kpi-label {
  max-width: 100%;
  padding: 0 8px;
  color: #505866;
  font-size: 13px;
  line-height: 18px;
  text-align: center;
  white-space: normal;
}

.kpi-value {
  font-size: 23px;
  line-height: 26px;
  letter-spacing: 0;
  font-variant-numeric: tabular-nums;
}

.kpi-value.orange { color: #ff5b14; }
.kpi-value.blue { color: #1677ff; }
.kpi-value.neutral { color: #4c5563; }
.kpi-value.danger { color: #e5484d; }

.kpi-item--loading {
  padding: 18px;
}

@media (max-width: 1200px) {
  .kpi-strip {
    overflow-x: auto;
    grid-template-columns: repeat(var(--kpi-columns, 7), minmax(100px, 1fr));
  }
}
</style>
