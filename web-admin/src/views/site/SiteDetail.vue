<template>
  <div class="page">
    <div class="page-header">
      <h1>站点详情</h1>
      <div class="header-actions">
        <el-button @click="$router.back()"><el-icon><Back /></el-icon>返回</el-button>
        <el-button @click="openSurveys"><el-icon><PictureFilled /></el-icon>勘察档案</el-button>
        <el-button type="success" @click="createSurvey"><el-icon><Plus /></el-icon>新建勘察</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <div class="info-grid" v-if="site">
        <div class="item"><span class="label">站点名称</span><span class="value">{{ site.site_name }}</span></div>
        <div class="item"><span class="label">站点编码</span><span class="value">{{ site.site_code }}</span></div>
        <div class="item"><span class="label">类型</span><span class="value">{{ site.site_type || '-' }}</span></div>
        <div class="item"><span class="label">状态</span><span class="value">{{ site.status }}</span></div>
        <div class="item"><span class="label">地址</span><span class="value">{{ site.address || '-' }}</span></div>
      </div>
    </el-card>

    <!-- 当前工单 -->
    <el-card class="mt16" v-loading="workOrdersLoading">
      <template #header>
        <div class="card-header">
          <span>当前工单</span>
          <el-button type="primary" size="small" @click="showHistoryDialog">
            <el-icon><Document /></el-icon>查看历史工单
          </el-button>
        </div>
      </template>
      <el-empty v-if="!currentWorkOrders.length" description="暂无进行中的工单" />
      <el-table v-else :data="currentWorkOrders" stripe>
        <el-table-column prop="title" label="工单标题" min-width="180" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ formatWorkOrderType(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">{{ formatWorkOrderStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)">{{ formatPriority(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="指派给" width="120">
          <template #default="{ row }">
            {{ getUserName(row.assigned_to) }}
          </template>
        </el-table-column>
        <el-table-column prop="assigned_at" label="分配时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.assigned_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewWorkOrder(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 历史工单对话框 -->
    <el-dialog v-model="historyDialogVisible" title="历史工单" width="80%" :close-on-click-modal="false">
      <el-table :data="historyWorkOrders" v-loading="historyLoading" stripe max-height="500">
        <el-table-column prop="title" label="工单标题" min-width="180" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ formatWorkOrderType(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">{{ formatWorkOrderStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)">{{ formatPriority(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="指派给" width="120">
          <template #default="{ row }">
            {{ getUserName(row.assigned_to) }}
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完成时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.completed_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewWorkOrder(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="historyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const site = ref(null)
const userStore = useUserStore()
const userOptions = ref([])

// 工单相关
const workOrdersLoading = ref(false)
const currentWorkOrders = ref([])
const historyDialogVisible = ref(false)
const historyLoading = ref(false)
const historyWorkOrders = ref([])

const load = async () => {
  try {
    loading.value = true
    const res = await request.get(`/api/sites/${route.params.id}`)
    site.value = res
    await loadWorkOrders()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载站点详情失败')
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const res = await request.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = res || []
  } catch (e) {
    // 可能无权限
  }
}

const loadWorkOrders = async () => {
  try {
    workOrdersLoading.value = true
    const res = await request.get('/api/work-orders/search', {
      params: {
        site_id: route.params.id,
        limit: 100
      }
    })
    const allWorkOrders = res.work_orders || []
    // 过滤出当前进行中的工单（未完成的）
    currentWorkOrders.value = allWorkOrders.filter(wo => 
      wo.status !== 'COMPLETED' && wo.status !== 'CANCELLED'
    )
  } catch (e) {
    console.error(e)
    ElMessage.error('加载工单失败')
  } finally {
    workOrdersLoading.value = false
  }
}

const showHistoryDialog = async () => {
  historyDialogVisible.value = true
  try {
    historyLoading.value = true
    const res = await request.get('/api/work-orders/search', {
      params: {
        site_id: route.params.id,
        limit: 100
      }
    })
    const allWorkOrders = res.work_orders || []
    // 历史工单包括已完成和已取消的
    historyWorkOrders.value = allWorkOrders.filter(wo => 
      wo.status === 'COMPLETED' || wo.status === 'CANCELLED'
    )
  } catch (e) {
    console.error(e)
    ElMessage.error('加载历史工单失败')
  } finally {
    historyLoading.value = false
  }
}

const getUserName = (userId) => {
  if (!userId) return '-'
  const user = userOptions.value.find(u => u.id === userId)
  return user ? (user.full_name || user.username) : userId
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatWorkOrderType = (type) => {
  const map = {
    'INSPECTION': '检查',
    'INSTALLATION': '安装',
    'MAINTENANCE': '维护',
    'REPAIR': '维修'
  }
  return map[type] || type
}

const formatWorkOrderStatus = (status) => {
  const map = {
    'PENDING': '待分配',
    'ASSIGNED': '已分配',
    'ACCEPTED': '已接受',
    'IN_PROGRESS': '进行中',
    'SUBMITTED': '已提交',
    'UNDER_REVIEW': '审核中',
    'APPROVED': '已批准',
    'REJECTED': '已拒绝',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消'
  }
  return map[status] || status
}

const formatPriority = (priority) => {
  const map = {
    'HIGH': '高',
    'NORMAL': '普通',
    'LOW': '低'
  }
  return map[priority] || priority
}

const getStatusTagType = (status) => {
  const map = {
    'PENDING': 'info',
    'ASSIGNED': 'warning',
    'ACCEPTED': 'primary',
    'IN_PROGRESS': 'primary',
    'SUBMITTED': 'success',
    'UNDER_REVIEW': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'COMPLETED': 'success',
    'CANCELLED': 'info'
  }
  return map[status] || 'info'
}

const getPriorityTagType = (priority) => {
  const map = {
    'HIGH': 'danger',
    'NORMAL': 'primary',
    'LOW': 'info'
  }
  return map[priority] || 'info'
}

const viewWorkOrder = (workOrder) => {
  router.push({ name: 'WorkOrderReview', query: { id: workOrder.id } })
}

onMounted(() => {
  load()
  loadUsers()
})

const openSurveys = () => {
  router.push({ name: 'SiteSurveys', params: {}, query: { site_id: route.params.id } })
}
const createSurvey = () => {
  router.push({ name: 'SiteSurveyNew', query: { site_id: route.params.id } })
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.info-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.item .label { color: var(--text-secondary); margin-right:8px; }
.item .value { color: var(--text-primary); font-weight: 500; }
.mt16 { margin-top: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
