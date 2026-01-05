<template>
  <el-card v-loading="loading">
    <el-alert
      v-if="errorMessage"
      type="error"
      :closable="true"
      show-icon
      title="生命周期加载失败"
      :description="errorMessage"
      class="mb12"
    />
    <!-- 设备信息概览 -->
    <div v-if="equipmentInfo" class="equipment-overview">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="设备SN">
          <el-text tag="b" type="success" style="font-family: 'Courier New', monospace; font-size: 16px">
            {{ equipmentInfo.serial_number }}
          </el-text>
        </el-descriptions-item>
        <el-descriptions-item label="设备类型">
          {{ equipmentInfo.equipment_name || '未知' }}
        </el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag :type="getStatusType(equipmentInfo.status)">
            {{ getStatusText(equipmentInfo.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="条码">
          {{ equipmentInfo.barcode || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="供应商">
          {{ equipmentInfo.vendor || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="所在仓库">
          {{ displayWarehouseName }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- OMC 设备状态 -->
    <div v-if="equipmentInfo" class="omc-status">
      <div class="omc-status-header">
        <h3>OMC 设备状态</h3>
        <el-button
          type="primary"
          size="small"
          :loading="omcLoading"
          :disabled="refreshCooldown > 0"
          @click="loadOmcStatus"
        >
          <span v-if="refreshCooldown > 0">
            刷新 OMC 状态 ({{ refreshCooldown }}s)
          </span>
          <span v-else>
            刷新 OMC 状态
          </span>
        </el-button>
      </div>
      <div class="omc-status-body">
        <div v-if="omcStatus">
          <el-tag :type="omcStatus.online ? 'success' : 'danger'">
            {{ omcStatus.online ? '在线' : '离线或未知' }}
          </el-tag>
          <el-tag
            :type="omcStatus.activated ? 'success' : 'info'"
            style="margin-left: 8px"
          >
            {{ omcStatus.activated ? '已激活' : '未激活或未知' }}
          </el-tag>
          <span
            v-if="omcStatus.checked_at"
            class="omc-checked-at"
          >
            最近检测时间：{{ formatTime(omcStatus.checked_at) }}
          </span>
        </div>
        <div v-else>
          <span>尚未查询 OMC 状态</span>
        </div>
      </div>
    </div>

    <el-divider v-if="equipmentInfo" />

    <!-- 生命周期时间轴 -->
    <div v-if="lifecycleStages.length > 0" class="lifecycle-container">
      <h3 style="margin-bottom: 24px">
        <el-icon><TrendCharts /></el-icon>
        生命周期追踪
      </h3>

      <el-timeline>
        <el-timeline-item
          v-for="(stage, index) in lifecycleStages"
          :key="index"
          :timestamp="stage.timestamp"
          placement="top"
          :type="stage.type"
          :color="stage.color"
          :icon="stage.icon"
          :size="stage.size"
        >
          <el-card>
            <template #header>
              <div class="stage-header">
                <el-tag :type="stage.tagType" size="large">
                  {{ stage.title }}
                </el-tag>
                <span v-if="stage.operator" class="operator-info">
                  操作人: {{ stage.operator }}
                </span>
              </div>
            </template>

            <div class="stage-content">
              <p v-if="stage.description" class="stage-description">
                {{ stage.description }}
              </p>

              <el-descriptions v-if="stage.details" :column="2" border size="small">
                <el-descriptions-item
                  v-for="(detail, key) in stage.details"
                  :key="key"
                  :label="key"
                >
                  {{ detail }}
                </el-descriptions-item>
              </el-descriptions>

              <div v-if="stage.location" class="location-info">
                <el-icon><Location /></el-icon>
                <span>{{ stage.location }}</span>
              </div>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </div>

    <el-empty
      v-else-if="sn && !loading && !errorMessage"
      description="未找到设备信息或暂无生命周期记录"
    />
    <el-empty
      v-else-if="sn && !loading && errorMessage"
      description="生命周期加载失败"
    />
    <el-empty
      v-else-if="!sn && !loading"
      description="暂无设备序列号"
    />
  </el-card>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { TrendCharts, Location, Box, Aim, CircleCheck, Tools, Checked, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const props = defineProps({
  sn: {
    type: String,
    default: ''
  }
})

const loading = ref(false)
const equipmentInfo = ref(null)
const lifecycleEvents = ref([])
const errorMessage = ref('')
const omcLoading = ref(false)
const omcStatus = ref(null)
const refreshCooldown = ref(0)
let cooldownTimer = null

const displayWarehouseName = computed(() => {
  const info = equipmentInfo.value || {}
  if (info.warehouse_id !== undefined && info.warehouse_id !== null) {
    return info.warehouse_name || '-'
  }
  if (info.warehouse_id === null) {
    if (info.last_warehouse_name) return `已出库（上个仓库：${info.last_warehouse_name}）`
    return '已出库'
  }
  return info.warehouse_name || info.last_warehouse_name || info.stock_in_warehouse_name || '-'
})

const loadOmcStatus = async () => {
  if (!props.sn) {
    ElMessage.warning('暂无设备SN，无法查询OMC状态')
    return
  }
  if (refreshCooldown.value > 0) {
    ElMessage.warning(`请等待 ${refreshCooldown.value}s 后再刷新 OMC 状态`)
    return
  }

  omcLoading.value = true
  omcStatus.value = null

  try {
    const res = await request.get(`/api/omc/devices/${props.sn}/status`)
    omcStatus.value = res
    startCooldown()
  } catch (error) {
    console.error('查询OMC状态失败:', error)
    ElMessage.error('查询OMC状态失败')
  } finally {
    omcLoading.value = false
  }
}

const startCooldown = () => {
  refreshCooldown.value = 10
  if (cooldownTimer) return
  cooldownTimer = setInterval(() => {
    if (refreshCooldown.value > 0) {
      refreshCooldown.value -= 1
    }
    if (refreshCooldown.value <= 0) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

const loadLifecycle = async () => {
  if (!props.sn) return

  loading.value = true
  equipmentInfo.value = null
  lifecycleEvents.value = []
  errorMessage.value = ''

  try {
    const res = await request.get(`/api/equipment/instances/${props.sn}/lifecycle-events`)
    equipmentInfo.value = res?.equipment || null
    lifecycleEvents.value = Array.isArray(res?.events) ? res.events : []

    if (!equipmentInfo.value && lifecycleEvents.value.length === 0) {
      ElMessage.warning('未找到该设备的信息')
    }
  } catch (error) {
    console.error('查询设备生命周期失败:', error)
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    const detailText = typeof detail === 'string' ? detail : ''
    const statusText = status ? `HTTP ${status}` : '网络/服务异常'
    let hint = '请检查后端服务是否已启动，以及版本是否已升级支持 lifecycle-events 接口。'
    if (status === 404) {
      hint = '接口不存在（可能后端未升级或路由未注册）。'
    } else if (status === 401 || status === 403) {
      hint = '权限不足或登录失效，请重新登录后再试。'
    }
    errorMessage.value = `${statusText}${detailText ? `：${detailText}` : ''}。${hint}`
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (props.sn) {
    loadLifecycle()
  }
})

watch(
  () => props.sn,
  (newSn, oldSn) => {
    if (newSn && newSn !== oldSn) {
      loadLifecycle()
    }
  }
)

onUnmounted(() => {
  if (cooldownTimer) {
    clearInterval(cooldownTimer)
    cooldownTimer = null
  }
})

const lifecycleStages = computed(() => {
  const stages = []

  const events = Array.isArray(lifecycleEvents.value) ? lifecycleEvents.value : []
  events.forEach((record) => {
    const action = record?.action
    const ts = record?.operated_at
    if (!action || !ts) return

    if (action === 'stock_in') {
      stages.push({
        title: '📦 设备入库',
        timestamp: ts,
        type: 'primary',
        color: '#409EFF',
        tagType: 'primary',
        size: 'large',
        icon: Box,
        description: record.notes || '设备已录入系统，完成入库登记',
        details: record.details || {
          设备SN: equipmentInfo.value?.serial_number || props.sn || '-',
          条码: equipmentInfo.value?.barcode || '-',
          供应商: equipmentInfo.value?.vendor || '-',
          仓库: equipmentInfo.value?.stock_in_warehouse_name || equipmentInfo.value?.warehouse_name || equipmentInfo.value?.last_warehouse_name || '-'
        }
      })
      return
    }

    if (action === 'stock_out') {
      stages.push({
        title: '🚚 设备出库',
        timestamp: ts,
        type: 'success',
        color: '#67C23A',
        tagType: 'success',
        size: 'large',
        icon: Aim,
        description: record.notes || '设备已出库',
        operator: record.operator?.name || equipmentInfo.value?.issued_to_name,
        details: record.details || {
          领料人: equipmentInfo.value?.issued_to_name || '-',
          出库时间: formatTime(ts)
        }
      })
      return
    }

    if (action === 'bind') {
      const siteName = record?.site?.name || '未知站点'
      const cellId = record?.cell_info?.cell_id || '-'
      stages.push({
        title: '🔗 设备绑定',
        timestamp: ts,
        type: 'success',
        color: '#10b981',
        tagType: 'success',
        size: 'normal',
        icon: CircleCheck,
        description: `设备绑定到 ${siteName} 的小区 ${cellId}`,
        operator: record.operator?.name,
        details: {
          站点: `${siteName} (ID: ${record?.site?.id || '-'})`,
          小区: `扇区${record?.cell_info?.sector_id || '-'} ${record?.cell_info?.band || ''}`,
          检查ID: record.inspection_id || '-'
        },
        location: record.latitude && record.longitude ? `${record.latitude}, ${record.longitude}` : null
      })
      return
    }

    if (action === 'unbind') {
      const siteName = record?.site?.name || '未知站点'
      const cellId = record?.cell_info?.cell_id || '-'
      stages.push({
        title: '🔓 设备解绑',
        timestamp: ts,
        type: 'warning',
        color: '#ef4444',
        tagType: 'danger',
        size: 'normal',
        icon: Tools,
        description: `设备从 ${siteName} 的小区 ${cellId} 解绑`,
        operator: record.operator?.name,
        details: {
          站点: `${siteName} (ID: ${record?.site?.id || '-'})`,
          小区: `扇区${record?.cell_info?.sector_id || '-'} ${record?.cell_info?.band || ''}`
        }
      })
      return
    }

    if (action === 'rebind') {
      const siteName = record?.site?.name || '未知站点'
      const cellId = record?.cell_info?.cell_id || '-'
      stages.push({
        title: '🔄 重新绑定',
        timestamp: ts,
        type: 'warning',
        color: '#f59e0b',
        tagType: 'warning',
        size: 'normal',
        icon: Tools,
        description: `设备重新绑定到 ${siteName} 的小区 ${cellId}`,
        operator: record.operator?.name,
        details: {
          原设备: record.previous_equipment_sn || '-',
          新站点: `${siteName} (ID: ${record?.site?.id || '-'})`,
          新小区: `扇区${record?.cell_info?.sector_id || '-'} ${record?.cell_info?.band || ''}`
        }
      })
      return
    }

    if (action === 'inspection_completed') {
      stages.push({
        title: '🧾 检查完成',
        timestamp: ts,
        type: 'success',
        color: '#22c55e',
        tagType: 'success',
        size: 'large',
        icon: Checked,
        description: record.notes || '检查项已完成，设备状态更新为“已检查”',
        operator: record.operator?.name || '检查人员',
        details: record.details || {}
      })
      return
    }

    if (action === 'return_requested') {
      stages.push({
        title: '↩️ 退库申请（待收货）',
        timestamp: ts,
        type: 'warning',
        color: '#f59e0b',
        tagType: 'warning',
        size: 'large',
        icon: Box,
        description: record.notes || '退库申请已提交，等待仓库收货确认',
        operator: record.operator?.name,
        details: record.details || {}
      })
      return
    }

    if (action === 'return_received') {
      stages.push({
        title: '📥 退库收货确认',
        timestamp: ts,
        type: 'success',
        color: '#10b981',
        tagType: 'success',
        size: 'large',
        icon: Box,
        description: record.notes || '仓库已收货确认，设备已回库',
        operator: record.operator?.name || '仓库',
        details: record.details || {}
      })
      return
    }

    if (action === 'return_rejected') {
      stages.push({
        title: '⛔ 退库拒收',
        timestamp: ts,
        type: 'danger',
        color: '#ef4444',
        tagType: 'danger',
        size: 'large',
        icon: Tools,
        description: record.notes || '仓库拒收退库申请',
        operator: record.operator?.name || '仓库',
        details: record.details || {}
      })
      return
    }

    if (action === 'void_stock_in') {
      stages.push({
        title: '🧹 撤销入库',
        timestamp: ts,
        type: 'warning',
        color: '#f59e0b',
        tagType: 'warning',
        size: 'normal',
        icon: Tools,
        description: record.notes || '撤销入库',
        operator: record.operator?.name,
        details: record.details || {}
      })
      return
    }

    if (action === 'edit_instance_info') {
      stages.push({
        title: '✏️ 编辑实例信息',
        timestamp: ts,
        type: 'info',
        color: '#0ea5e9',
        tagType: 'info',
        size: 'normal',
        icon: Tools,
        description: record.notes || '编辑设备实例信息',
        operator: record.operator?.name,
        details: record.details || {}
      })
      return
    }

    if (action === 'damaged_marked') {
      stages.push({
        title: '⚠️ 损坏/报损',
        timestamp: ts,
        type: 'danger',
        color: '#ef4444',
        tagType: 'danger',
        size: 'large',
        icon: WarningFilled,
        description: record.notes || '设备标记为“损坏/报损”',
        operator: record.operator?.name,
        details: record.details || {}
      })
      return
    }

    if (action === 'omc_first_online') {
      stages.push({
        title: '🌐 首次上线',
        timestamp: ts,
        type: 'info',
        color: '#0ea5e9',
        tagType: 'info',
        size: 'large',
        icon: TrendCharts,
        description: record.notes || 'OMC 首次检测到设备上线',
        operator: record.operator?.name || '系统(OMC)',
        details: {
          设备SN: equipmentInfo.value?.serial_number || props.sn || '-',
          记录来源: 'OMC'
        }
      })
      return
    }

    if (action === 'omc_first_activated') {
      stages.push({
        title: '⚡ 首次激活',
        timestamp: ts,
        type: 'success',
        color: '#22c55e',
        tagType: 'success',
        size: 'large',
        icon: Checked,
        description: record.notes || 'OMC 首次检测到设备激活',
        operator: record.operator?.name || '系统(OMC)',
        details: {
          设备SN: equipmentInfo.value?.serial_number || props.sn || '-',
          记录来源: 'OMC'
        }
      })
    }
  })

  // 按时间倒序排序（最新的在前）
  return stages.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
})

const getStatusType = (status) => {
  const typeMap = {
    in_stock: 'info',
    issued: 'primary',
    pending_inspection: 'warning',
    inspected: 'success',
    return_pending_receive: 'warning',
    damaged: 'danger',
    // 兼容保留（历史值）
    allocated: 'warning',
    returned: 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    in_stock: '库存中',
    issued: '已出库',
    pending_inspection: '待检查',
    inspected: '已检查',
    return_pending_receive: '退库待收货',
    damaged: '损坏/报损',
    // 兼容保留（历史值）
    allocated: '已分配(旧)',
    returned: '已退库(旧)'
  }
  return textMap[status] || status
}

const formatTime = (isoString) => {
  if (!isoString) return ''

  const date = new Date(isoString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${year}-${month}-${day} ${hours}:${minutes}`
}
</script>

<style scoped>
.equipment-overview {
  margin-bottom: 24px;
}

.omc-status {
  margin-bottom: 24px;
}

.omc-status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.omc-status-body {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #606266;
}

.omc-checked-at {
  margin-left: 8px;
  color: #909399;
}

.lifecycle-container {
  padding: 16px 0;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.operator-info {
  color: #909399;
  font-size: 14px;
}

.stage-content .stage-description {
  margin: 0 0 16px 0;
  color: #606266;
  font-size: 14px;
}

.stage-content .location-info {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
  font-family: 'Courier New', monospace;
}
</style>
