<template>
  <el-card class="block-card" :body-style="{ padding: '12px' }">
    <template #header>
      <div class="card-header">
        <span class="card-title"><el-icon><List /></el-icon> 我的待办</span>
        <el-button text size="small" @click="emit('goto', { name: 'WorkOrderList' })">更多<el-icon><ArrowRight /></el-icon></el-button>
      </div>
    </template>

    <div class="section">
      <div class="section-title">我的工单</div>
      <el-empty v-if="!orders.length" description="暂无待办工单" :image-size="64" />
      <el-timeline v-else>
        <el-timeline-item
          v-for="o in orders"
          :key="o.id"
          :timestamp="formatDateTime(o.due_date)"
          placement="top"
        >
          <div class="item-row">
            <span class="title" @click="emit('goto', { name:'WorkOrderList' })">{{ o.title }}</span>
            <el-tag size="small">{{ statusText(o.status) }}</el-tag>
          </div>
          <div class="sub">站点：{{ o.site_name || o.site_id || '-' }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>

    <!-- 待审核的检查板块已移除按需展示，如需恢复请从 API 返回数据并渲染 -->
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ data: { type: Object, default: null }, loading: { type: Boolean, default: false } })
const emit = defineEmits(['goto'])

const orders = computed(() => props.data?.my_orders || [])
const reviewInspections = computed(() => [])

const statusText = (s) => ({ PENDING:'待分配', ACTIVE:'已分配', SUBMITTED:'已提交', UNDER_REVIEW:'审核中', APPROVED:'已通过', REJECTED:'已驳回', COMPLETED:'已完成' }[s] || s)
const formatDateTime = (v) => v ? new Date(v).toLocaleString() : ''
</script>

<style scoped>
.block-card { border-radius: 12px; border: 1px solid var(--border-color); }
.card-header { display:flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--text-primary); }
.section { padding: 4px 8px 12px; }
.section + .section { border-top: 1px solid #f2f3f5; padding-top: 12px; }
.section-title { font-weight: 600; color: var(--text-secondary); margin: 4px 0 8px; }
.item-row { display:flex; justify-content: space-between; align-items: center; gap: 8px; }
.title { color: var(--text-primary); cursor: pointer; }
.title:hover { text-decoration: underline; }
.sub { color: var(--text-light); font-size: 12px; margin-top: 2px; }
</style>
