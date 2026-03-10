<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h1>仪表盘</h1>
      <div class="header-actions">
        <el-button @click="refresh" :loading="loading" type="primary">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <!-- 站点概况（新卡组，置顶） -->
    <SiteProgressOverview :progress="topStats?.site_progress" @goto="handleGoto" />

    <!-- 站点事件趋势（按日/周/月 + 新增/累计） -->
    <SiteProgressTrend ref="siteProgressTrendRef" class="mt-24 mb-24" />

    <!-- 顶部概览（保留原工单/库存等卡片） -->
    <StatsOverview :data="topStats" :loading="loading" @card-click="handleCardClick" />

    <!-- 中部：待办 + 风险预警 -->
    <el-row :gutter="24" class="mt-24">
      <el-col :xl="14" :lg="14" :md="24" :sm="24">
        <MyTodos :data="todos" :loading="loading" @goto="handleGoto" />
      </el-col>
      <el-col :xl="10" :lg="10" :md="24" :sm="24">
        <RisksPanel :data="risks" :loading="loading" @goto="handleGoto" />
      </el-col>
    </el-row>

    <!-- 底部：最近动态 -->
    <ActivityFeed :data="activity" :loading="loading" @goto="handleGoto" class="mt-24" />

    <!-- 快捷操作（保留并扩展） -->
    <el-card class="quick-actions mt-24">
      <template #header>
        <span class="card-title">
          <el-icon><Operation /></el-icon>
          快捷操作
        </span>
      </template>

      <div class="action-buttons">
        <el-button type="primary" @click="$router.push('/inventory/equipment')">
          <el-icon><Box /></el-icon>
          设备类型管理
        </el-button>
        <el-button type="success" @click="$router.push('/inventory/packages')">
          <el-icon><Collection /></el-icon>
          设备套装配置
        </el-button>
        <el-button type="info" @click="$router.push('/inventory/stock-in')">
          <el-icon><Upload /></el-icon>
          设备入库
        </el-button>
        <el-button type="warning" @click="$router.push('/inventory/list')">
          <el-icon><TakeawayBox /></el-icon>
          设备库存管理
        </el-button>
        <el-button @click="$router.push('/work-orders/list')">
          <el-icon><Tickets /></el-icon>
          工单列表
        </el-button>
      </div>
    </el-card>
  </div>
  
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import StatsOverview from '@/components/dashboard/StatsOverview.vue'
import SiteProgressOverview from '@/components/dashboard/SiteProgressOverview.vue'
import SiteProgressTrend from '@/components/dashboard/SiteProgressTrend.vue'
import MyTodos from '@/components/dashboard/MyTodos.vue'
import RisksPanel from '@/components/dashboard/RisksPanel.vue'
import ActivityFeed from '@/components/dashboard/ActivityFeed.vue'
import { fetchTopStats, fetchTodos, fetchRisks, fetchActivity } from '@/api/dashboard'

const router = useRouter()
const loading = ref(false)
const topStats = ref(null)
const todos = ref(null)
const risks = ref(null)
const activity = ref(null)
const siteProgressTrendRef = ref(null)

const loadAll = async () => {
  try {
    loading.value = true
    const [ts, td, rk, act] = await Promise.all([
      fetchTopStats(),
      fetchTodos(),
      fetchRisks(),
      fetchActivity(),
    ])
    topStats.value = ts
    todos.value = td
    risks.value = rk
    activity.value = act
  } catch (e) {
    console.error(e)
    ElMessage.error('加载仪表盘失败')
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  await Promise.all([
    loadAll(),
    siteProgressTrendRef.value?.refresh?.() || Promise.resolve(),
  ])
  ElMessage.success('数据已刷新')
}

const handleGoto = (route) => {
  if (!route) return
  router.push(route)
}

const handleCardClick = (payload) => {
  if (!payload) return
  handleGoto(payload.route)
}

onMounted(loadAll)
</script>

<style scoped lang="scss">
.dashboard-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h1 {
    color: var(--text-primary);
    font-size: 28px;
    font-weight: 700;
    margin: 0;
  }
}

.mt-24 { margin-top: 24px; }
.mb-24 { margin-bottom: 24px; }

.quick-actions {
  border-radius: 12px;
  border: 1px solid var(--border-color);

  .action-buttons {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;

    .el-button {
      min-height: 44px;
      height: auto;
      font-weight: 500;
      border-radius: 8px;
      white-space: normal;
      line-height: 1.2;
      text-align: center;
      padding: 10px 12px;

      .el-icon { margin-right: 8px; }
    }
  }
}

@media (max-width: 768px) {
  .dashboard-page { padding: 16px; }
}
</style>
