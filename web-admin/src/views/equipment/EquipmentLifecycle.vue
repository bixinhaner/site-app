<template>
  <div class="page">
    <div class="page-header">
      <h1>设备生命周期追踪</h1>
      <el-input
        v-model="searchSN"
        placeholder="输入设备序列号查询"
        clearable
        style="width: 400px"
        @keyup.enter="searchEquipment"
      >
        <template #append>
          <el-button :icon="Search" @click="searchEquipment" />
        </template>
      </el-input>
    </div>

    <el-card v-loading="loading">
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
            {{ equipmentInfo.warehouse_name || '-' }}
          </el-descriptions-item>
        </el-descriptions>
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

      <el-empty v-else-if="searchSN && !loading" description="未找到设备信息或暂无生命周期记录" />
      <el-empty v-else description="请输入设备序列号开始查询" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search, TrendCharts, Location, Box, Aim, CircleCheck, Tools, Checked } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const searchSN = ref('')
const equipmentInfo = ref(null)
const bindingHistory = ref([])

// 搜索设备
const searchEquipment = async () => {
  if (!searchSN.value.trim()) {
    ElMessage.warning('请输入设备序列号')
    return
  }

  loading.value = true
  equipmentInfo.value = null
  bindingHistory.value = []

  try {
    const token = localStorage.getItem('token')
    
    // 并行获取设备信息和绑定历史
    const [equipmentRes, historyRes] = await Promise.all([
      // 获取设备实例信息（这里需要调用设备API，简化处理）
      axios.get(`/api/equipment/instances/search?serial_number=${searchSN.value}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => ({ data: null })),
      
      // 获取绑定历史
      axios.get(`/api/inspections/equipment-history/${searchSN.value}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => ({ data: { history: [] } }))
    ])

    equipmentInfo.value = equipmentRes.data
    bindingHistory.value = historyRes.data.history || []

    if (!equipmentInfo.value && bindingHistory.value.length === 0) {
      ElMessage.warning('未找到该设备的信息')
    }
  } catch (error) {
    console.error('查询设备失败:', error)
    ElMessage.error('查询设备失败')
  } finally {
    loading.value = false
  }
}

// 计算生命周期阶段
const lifecycleStages = computed(() => {
  const stages = []

  // 1. 入库阶段
  if (equipmentInfo.value?.created_at) {
    stages.push({
      title: '📦 设备入库',
      timestamp: formatTime(equipmentInfo.value.created_at),
      type: 'primary',
      color: '#409EFF',
      tagType: 'primary',
      size: 'large',
      icon: Box,
      description: '设备已录入系统，完成入库登记',
      details: {
        '设备SN': equipmentInfo.value.serial_number,
        '条码': equipmentInfo.value.barcode || '-',
        '供应商': equipmentInfo.value.vendor || '-',
        '仓库': equipmentInfo.value.warehouse_name || '-'
      }
    })
  }

  // 2. 分配/出库阶段
  if (equipmentInfo.value?.issued_at) {
    stages.push({
      title: '🚚 设备出库',
      timestamp: formatTime(equipmentInfo.value.issued_at),
      type: 'success',
      color: '#67C23A',
      tagType: 'success',
      size: 'large',
      icon: Aim,
      description: '设备已分配并出库',
      operator: equipmentInfo.value.issued_to_name,
      details: {
        '领料人': equipmentInfo.value.issued_to_name || '-',
        '出库时间': formatTime(equipmentInfo.value.issued_at)
      }
    })
  }

  // 3. 绑定阶段（从历史记录获取）
  bindingHistory.value.forEach((record, index) => {
    const isFirst = index === bindingHistory.value.length - 1

    if (record.action === 'bind') {
      stages.push({
        title: isFirst ? '🔗 首次绑定' : '🔗 设备绑定',
        timestamp: formatTime(record.operated_at),
        type: 'success',
        color: '#10b981',
        tagType: 'success',
        size: isFirst ? 'large' : 'normal',
        icon: CircleCheck,
        description: `设备绑定到 ${record.site.name} 的小区 ${record.cell_info.cell_id}`,
        operator: record.operator.name,
        details: {
          '站点': `${record.site.name} (ID: ${record.site.id})`,
          '小区': `扇区${record.cell_info.sector_id} ${record.cell_info.band || ''}`,
          '检查ID': record.inspection_id
        },
        location: record.latitude && record.longitude 
          ? `${record.latitude}, ${record.longitude}` 
          : null
      })
    } else if (record.action === 'unbind') {
      stages.push({
        title: '🔓 设备解绑',
        timestamp: formatTime(record.operated_at),
        type: 'warning',
        color: '#ef4444',
        tagType: 'danger',
        size: 'normal',
        icon: Tools,
        description: `设备从 ${record.site.name} 的小区 ${record.cell_info.cell_id} 解绑`,
        operator: record.operator.name,
        details: {
          '站点': `${record.site.name} (ID: ${record.site.id})`,
          '小区': `扇区${record.cell_info.sector_id} ${record.cell_info.band || ''}`
        }
      })
    } else if (record.action === 'rebind') {
      stages.push({
        title: '🔄 重新绑定',
        timestamp: formatTime(record.operated_at),
        type: 'warning',
        color: '#f59e0b',
        tagType: 'warning',
        size: 'normal',
        icon: Tools,
        description: `设备重新绑定到 ${record.site.name} 的小区 ${record.cell_info.cell_id}`,
        operator: record.operator.name,
        details: {
          '原设备': record.previous_equipment_sn,
          '新站点': `${record.site.name} (ID: ${record.site.id})`,
          '新小区': `扇区${record.cell_info.sector_id} ${record.cell_info.band || ''}`
        }
      })
    }
  })

  // 4. 投入使用阶段（如果设备状态为已激活）
  if (equipmentInfo.value?.status === 'activated') {
    stages.push({
      title: '✅ 投入使用',
      timestamp: formatTime(equipmentInfo.value.updated_at),
      type: 'success',
      color: '#10b981',
      tagType: 'success',
      size: 'large',
      icon: Checked,
      description: '设备已完成部署，正式投入使用',
      details: {
        '当前状态': getStatusText(equipmentInfo.value.status)
      }
    })
  }

  // 按时间倒序排序（最新的在前）
  return stages.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
})

// 获取状态类型
const getStatusType = (status) => {
  const typeMap = {
    'in_stock': 'info',
    'allocated': 'warning',
    'issued': 'primary',
    'pending_inspection': 'warning',
    'inspected': 'success',
    'activated': 'success',
    'returned': 'danger'
  }
  return typeMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const textMap = {
    'in_stock': '库存中',
    'allocated': '已分配',
    'issued': '已出库',
    'pending_inspection': '待检查',
    'inspected': '已检查',
    'activated': '已激活',
    'returned': '已退库'
  }
  return textMap[status] || status
}

// 格式化时间
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
.page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.equipment-overview {
  margin-bottom: 24px;
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

.stage-content {
  .stage-description {
    margin: 0 0 16px 0;
    color: #606266;
    font-size: 14px;
  }

  .location-info {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #909399;
    font-size: 13px;
    font-family: 'Courier New', monospace;
  }
}
</style>
