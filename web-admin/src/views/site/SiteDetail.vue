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
        <div class="item"><span class="label">状态</span><span class="value">{{ siteStatusText(site.status) }}</span></div>
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

    <!-- 设备在线/激活状态 -->
    <el-card class="mt16" v-loading="deviceStatusLoading">
      <template #header>
        <div class="card-header">
          <span>设备在线 / 激活状态</span>
          <div>
            <span v-if="deviceStatusCheckedAt" style="margin-right: 12px; color: #909399;">
              最近检查时间：{{ formatDate(deviceStatusCheckedAt) }}
            </span>
            <el-button size="small" @click="loadDeviceStatus(false)">加载</el-button>
            <el-button
              size="small"
              type="primary"
              :disabled="deviceRefreshCooldown > 0"
              @click="loadDeviceStatus(true)"
            >
              <span v-if="deviceRefreshCooldown > 0">
                刷新状态 ({{ deviceRefreshCooldown }}s)
              </span>
              <span v-else>
                刷新状态
              </span>
            </el-button>
          </div>
        </div>
      </template>
      <el-empty v-if="!devices.length && !deviceStatusLoading" description="暂无绑定设备记录" />
      <el-table v-else :data="devices" size="small" stripe>
        <el-table-column prop="sn" label="设备 SN" min-width="180" />
        <el-table-column prop="equipment_type" label="设备类型" width="120" />
        <el-table-column prop="equipment_model" label="设备型号" min-width="160" />
        <el-table-column label="扇区信息" min-width="160">
          <template #default="{ row }">
            扇区 {{ row.sector_id || '-' }} / Band {{ row.band || '-' }} / Cell {{ row.cell_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="在线状态" width="200">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="onlineRealtimeTagType(row.online)" size="small" class="mr4">
                {{ onlineRealtimeText(row.online) }}
              </el-tag>
              <el-tag :type="everOnlineTagType(row.ever_online)" size="small">
                {{ everOnlineText(row.ever_online) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="激活状态" width="220">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="activeRealtimeTagType(row.activated)" size="small" class="mr4">
                {{ activeRealtimeText(row.activated) }}
              </el-tag>
              <el-tag :type="everActiveTagType(row.ever_activated)" size="small">
                {{ everActiveText(row.ever_activated) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="安装人" width="140">
          <template #default="{ row }">
            {{ row.installer_name || row.installer_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="bound_at" label="绑定时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.bound_at) }}
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
import { surveyArchivesApi } from '@/api/surveyArchives'

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

// 设备状态
const deviceStatusLoading = ref(false)
const devices = ref([])
const deviceStatusCheckedAt = ref(null)

const load = async () => {
  try {
    loading.value = true
    const res = await request.get(`/api/sites/${route.params.id}`)
    site.value = res
    await loadWorkOrders()
    await loadDeviceStatus(false)
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

const siteStatusText = (status) => {
  const map = {
    survey_pending: '勘察中',
    planning: '规划中',
    planned: '规划完成',
    construction: '施工中',
    pending_online: '待上线',
    online_pending_activation: '已上线待激活',
    operational: '已开通',
    maintenance: '维护中'
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

const onlineRealtimeText = (val) => {
  if (val === true) return '当前在线'
  if (val === false) return '当前离线'
  return '待检测'
}
const onlineRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'danger'
  return 'info'
}
const everOnlineTagType = (val) => (val ? 'success' : 'info')
const everOnlineText = (val) => (val ? '曾上线' : '未曾上线')

const activeRealtimeText = (val) => {
  if (val === true) return '当前已激活'
  if (val === false) return '当前未激活'
  return '待检测'
}
const activeRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'warning'
  return 'info'
}
const everActiveTagType = (val) => (val ? 'success' : 'info')
const everActiveText = (val) => (val ? '曾激活' : '未曾激活')

const deviceRefreshCooldown = ref(0)
let deviceCooldownTimer = null

const loadDeviceStatus = async (refresh = false) => {
  if (refresh && deviceRefreshCooldown.value > 0) {
    ElMessage.warning(`请等待 ${deviceRefreshCooldown.value}s 后再刷新设备状态`)
    return
  }
  try {
    deviceStatusLoading.value = true
    const res = await request.get(`/api/sites/${route.params.id}/omc/devices`, {
      params: { refresh: refresh ? 1 : 0 }
    })
    devices.value = Array.isArray(res.devices) ? res.devices : []
    deviceStatusCheckedAt.value = res.checked_at || null

    if (refresh) {
      startDeviceCooldown()
    }
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载设备状态失败')
  } finally {
    deviceStatusLoading.value = false
  }
}

const viewWorkOrder = (workOrder) => {
  router.push({ name: 'WorkOrderReview', query: { id: workOrder.id } })
}

onMounted(() => {
  load()
  loadUsers()
  // 默认加载一次设备ever状态，实时状态为“待检测”
  loadDeviceStatus(false)
})

const startDeviceCooldown = () => {
  deviceRefreshCooldown.value = 10
  if (deviceCooldownTimer) return
  deviceCooldownTimer = setInterval(() => {
    if (deviceRefreshCooldown.value > 0) {
      deviceRefreshCooldown.value -= 1
    }
    if (deviceRefreshCooldown.value <= 0) {
      clearInterval(deviceCooldownTimer)
      deviceCooldownTimer = null
    }
  }, 1000)
}

const openSurveys = async () => {
  try {
    const res = await surveyArchivesApi.page({
      page: 1,
      page_size: 1,
      site_id: route.params.id
    })
    const items = Array.isArray(res?.items) ? res.items : []
    if (!items.length) {
      ElMessage.info('当前站点暂无勘察档案')
      return
    }
    const archive = items[0]
    router.push({ name: 'SurveyArchiveDetail', params: { id: archive.id } })
  } catch (e) {
    console.error(e)
    ElMessage.error('获取勘察档案失败')
  }
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
.status-cell { display: flex; align-items: center; gap: 4px; }
.mr4 { margin-right: 4px; }
</style>
