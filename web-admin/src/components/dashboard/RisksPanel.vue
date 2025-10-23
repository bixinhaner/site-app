<template>
  <el-card class="block-card" :body-style="{ padding: '12px' }">
    <template #header>
      <div class="card-header">
        <span class="card-title"><el-icon><Warning /></el-icon> 风险与预警</span>
      </div>
    </template>

    <div class="section">
      <div class="section-title">低库存（Top5）</div>
      <el-empty v-if="!lowStock.length" description="暂无低库存" :image-size="64" />
      <div v-else>
        <div class="warning-item" v-for="item in lowStock" :key="item.id">
          <div class="warning-info">
            <span class="equipment-name">{{ item.equipment_name }}</span>
            <span class="stock-info">{{ item.current_stock || 0 }} / {{ item.min_threshold || 0 }}</span>
          </div>
          <el-tag type="danger" size="small" @click="emit('goto', { name: 'InventoryList' })">查看</el-tag>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">逾期工单</div>
      <el-empty v-if="!overdue.length" description="暂无逾期" :image-size="64" />
      <el-timeline v-else>
        <el-timeline-item v-for="o in overdue" :key="o.id" :timestamp="formatDateTime(o.due_date)">
          <div class="item-row">
            <span class="title" @click="emit('goto', { name:'WorkOrderList' })">{{ o.title }}</span>
            <el-tag size="small" type="danger">逾期</el-tag>
          </div>
          <div class="sub">站点：{{ o.site_name || o.site_id || '-' }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>

    <div class="section">
      <div class="section-title">近7天将到期</div>
      <el-empty v-if="!dueSoon.length" description="暂无将到期工单" :image-size="64" />
      <el-timeline v-else>
        <el-timeline-item v-for="o in dueSoon" :key="o.id" :timestamp="formatDateTime(o.due_date)">
          <div class="item-row">
            <span class="title" @click="emit('goto', { name:'WorkOrderList' })">{{ o.title }}</span>
            <el-tag size="small" type="warning">将到期</el-tag>
          </div>
          <div class="sub">站点：{{ o.site_name || o.site_id || '-' }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ data: { type: Object, default: null }, loading: { type: Boolean, default: false } })
const emit = defineEmits(['goto'])

const lowStock = computed(() => props.data?.low_stock || [])
const overdue = computed(() => props.data?.overdue || [])
const dueSoon = computed(() => props.data?.due_soon || [])

const formatDateTime = (v) => v ? new Date(v).toLocaleString() : ''
</script>

<style scoped>
.block-card { border-radius: 12px; border: 1px solid var(--border-color); }
.card-header { display:flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--text-primary); }
.section { padding: 4px 8px 12px; }
.section + .section { border-top: 1px solid #f2f3f5; padding-top: 12px; }
.section-title { font-weight: 600; color: var(--text-secondary); margin: 4px 0 8px; }
.warning-item { display:flex; justify-content: space-between; align-items:center; padding: 8px 0; border-bottom: 1px solid #f6f7fb; }
.warning-item:last-child { border-bottom: none; }
.warning-info { display:flex; flex-direction: column; gap: 2px; }
.equipment-name { color: var(--text-primary); font-weight: 500; }
.stock-info { color: var(--text-light); font-size: 12px; }
.item-row { display:flex; justify-content: space-between; align-items: center; gap: 8px; }
.title { color: var(--text-primary); cursor: pointer; }
.title:hover { text-decoration: underline; }
.sub { color: var(--text-light); font-size: 12px; margin-top: 2px; }
</style>

