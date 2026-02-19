<template>
  <div class="stats-grid">
    <!-- 工单概览 -->
    <div class="stat-card" @click="emit('card-click', { route: { name: 'WorkOrderList' } })">
      <div class="stat-header">
        <el-icon class="stat-icon info"><Tickets /></el-icon>
        <span class="stat-title">工单概览</span>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ data?.work_orders?.total || 0 }}</div>
        <div class="stat-description">
          待分配 {{ data?.work_orders?.status?.PENDING || 0 }} · 审核中 {{ data?.work_orders?.status?.UNDER_REVIEW || 0 }} · 已完成 {{ data?.work_orders?.status?.COMPLETED || 0 }}
        </div>
      </div>
    </div>

    <!-- 库存预警 -->
    <div class="stat-card" @click="emit('card-click', { route: { name: 'InventoryList' } })">
      <div class="stat-header">
        <el-icon class="stat-icon warning"><Warning /></el-icon>
        <span class="stat-title">库存预警</span>
      </div>
      <div class="stat-body">
        <div class="stat-value" :class="{ danger: (data?.inventory?.low_stock_count || 0) > 0 }">{{ data?.inventory?.low_stock_count || 0 }}</div>
        <div class="stat-description">需要补货的物料</div>
      </div>
    </div>

    <!-- 用户概览（仅当后端提供统计时显示） -->
    <div class="stat-card" v-if="data?.users?.total !== null && data?.users?.total !== undefined" @click="emit('card-click', { route: { name: 'UserList' } })">
      <div class="stat-header">
        <el-icon class="stat-icon success"><UserFilled /></el-icon>
        <span class="stat-title">用户概览</span>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ data?.users?.active || 0 }}/{{ data?.users?.total || 0 }}</div>
        <div class="stat-description">活跃 / 总用户</div>
      </div>
    </div>

    <!-- 待审工单 -->
    <div class="stat-card" @click="emit('card-click', { route: { name: 'WorkOrderReview' } })">
      <div class="stat-header">
        <el-icon class="stat-icon primary"><Stamp /></el-icon>
        <span class="stat-title">待审工单</span>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ data?.work_orders?.status?.UNDER_REVIEW || 0 }}</div>
        <div class="stat-description">审核中工单</div>
      </div>
    </div>

  </div>
</template>

<script setup>
const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['card-click'])
</script>

<style scoped lang="scss">
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}
.stat-card {
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all .2s ease;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.08); }
.stat-header { display:flex; align-items:center; gap: 10px; margin-bottom: 10px; }
.stat-icon { width: 40px; height: 40px; border-radius: 10px; display:flex; align-items:center; justify-content:center; color:#fff; }
.stat-icon.info { background: linear-gradient(45deg,#3b82f6,#60a5fa); }
.stat-icon.warning { background: linear-gradient(45deg,#f59e0b,#fbbf24); }
.stat-icon.success { background: linear-gradient(45deg,#10b981,#34d399); }
.stat-icon.primary { background: linear-gradient(45deg,#f97316,#fb923c); }
.stat-title { color: var(--text-secondary); font-weight: 600; }
.stat-value { font-size: 32px; font-weight: 700; color: var(--text-primary); line-height: 1; margin-bottom: 4px; }
.stat-value.danger { color: var(--danger-color); }
.stat-description { color: var(--text-light); }
</style>
