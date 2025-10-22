<template>
  <div class="page">
    <div class="page-header">
      <h1>设备实例清单</h1>
      <div class="header-actions">
        <el-select v-model="selectedEquipmentId" filterable clearable placeholder="设备类型" style="width: 320px" @visible-change="v=> v && loadEquipments()">
          <el-option v-for="eq in equipmentOptions" :key="eq.id" :label="`${eq.equipment_name} (${eq.equipment_code})`" :value="eq.id" />
        </el-select>
        <el-select v-model="status" clearable placeholder="状态" style="width: 160px">
          <el-option label="库存中" value="in_stock" />
          <el-option label="已分配" value="allocated" />
          <el-option label="已出库" value="issued" />
          <el-option label="已退库" value="returned" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索SN/条码/供应商" clearable style="width: 220px" />
        <el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button>
      </div>
    </div>
    <el-card>
      <el-table :data="displayedItems" v-loading="loading" stripe>
        <el-table-column prop="serial_number" label="SN" width="220">
          <template #default="{ row }">
            <el-space>
              <span>{{ row.serial_number }}</span>
              <el-button text size="small" @click="copy(row.serial_number)">复制</el-button>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="barcode" label="条码" width="200" />
        <el-table-column prop="vendor" label="供应商" width="140" />
        <el-table-column prop="warehouse_name" label="所在仓库" width="160" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="绑定信息" width="300">
          <template #default="{ row }">
            <el-space direction="vertical" :size="2" style="width: 100%">
              <el-tag v-if="row.binding_info" type="success" size="small">
                {{ row.binding_info.site_name }} - {{ row.binding_info.cell_id }}
              </el-tag>
              <el-button 
                v-if="row.serial_number" 
                text 
                type="primary" 
                size="small" 
                @click="showBindingHistory(row)"
              >
                <el-icon><Document /></el-icon> 查看历史
              </el-button>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
    
    <!-- 绑定历史弹窗 -->
    <el-dialog v-model="historyDialogVisible" title="设备绑定历史" width="70%" top="5vh">
      <div v-loading="loadingHistory">
        <el-empty v-if="bindingHistory.length === 0" description="暂无历史记录" />
        
        <el-timeline v-else>
          <el-timeline-item
            v-for="record in bindingHistory"
            :key="record.id"
            :timestamp="formatTime(record.operated_at)"
            placement="top"
            :color="getActionColor(record.action)"
          >
            <el-card>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <el-tag :type="getActionTagType(record.action)" size="large">
                    {{ getActionText(record.action) }}
                  </el-tag>
                  <span style="color: #909399; font-size: 14px">
                    操作人: {{ record.operator.name }}
                  </span>
                </div>
              </template>
              
              <el-descriptions :column="2" border>
                <el-descriptions-item label="站点">
                  {{ record.site.name }} (ID: {{ record.site.id }})
                </el-descriptions-item>
                <el-descriptions-item label="小区">
                  扇区{{ record.cell_info.sector_id }}
                  <el-tag v-if="record.cell_info.band" size="small" style="margin-left: 8px">
                    {{ record.cell_info.band }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="设备SN">
                  <el-text tag="b" type="success" style="font-family: 'Courier New', monospace">
                    {{ record.equipment_sn }}
                  </el-text>
                </el-descriptions-item>
                <el-descriptions-item v-if="record.previous_equipment_sn" label="原设备SN">
                  <el-text tag="b" style="font-family: 'Courier New', monospace">
                    {{ record.previous_equipment_sn }}
                  </el-text>
                </el-descriptions-item>
                <el-descriptions-item v-if="record.latitude && record.longitude" label="GPS位置" :span="2">
                  <el-text style="font-family: 'Courier New', monospace; font-size: 12px">
                    {{ record.latitude }}, {{ record.longitude }}
                    <el-tag v-if="record.gps_accuracy" size="small" style="margin-left: 8px">
                      精度: {{ record.gps_accuracy }}m
                    </el-tag>
                  </el-text>
                </el-descriptions-item>
                <el-descriptions-item v-if="record.notes" label="备注" :span="2">
                  {{ record.notes }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>
  </div>
  
</template>

<script setup>
import { ref, computed } from 'vue'
import { stockApi } from '../../api/stock'
import { ElMessage } from 'element-plus'
import { equipmentApi } from '../../api/equipment'
import { Document } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const selectedEquipmentId = ref('')
const status = ref('')
const items = ref([])
const keyword = ref('')
const equipmentOptions = ref([])

// 绑定历史相关
const historyDialogVisible = ref(false)
const loadingHistory = ref(false)
const bindingHistory = ref([])
const currentEquipment = ref(null)

const load = async () => {
  if (!selectedEquipmentId.value) {
    ElMessage.info('请输入设备类型ID')
    return
  }
  try {
    loading.value = true
    const res = await stockApi.getEquipmentInstances(selectedEquipmentId.value, status.value ? { status: status.value } : {})
    items.value = res?.instances || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载设备实例失败')
  } finally {
    loading.value = false
  }
}

const displayedItems = computed(() => {
  if (!keyword.value) return items.value
  const kw = keyword.value.toLowerCase()
  return items.value.filter(i =>
    (i.serial_number || '').toLowerCase().includes(kw) ||
    (i.barcode || '').toLowerCase().includes(kw) ||
    (i.vendor || '').toLowerCase().includes(kw)
  )
})

const loadEquipments = async () => {
  try {
    const res = await equipmentApi.getEquipmentList({ limit: 200 })
    equipmentOptions.value = res || []
  } catch (e) {
    console.error(e)
  }
}

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

// 显示设备绑定历史
const showBindingHistory = async (equipment) => {
  currentEquipment.value = equipment
  historyDialogVisible.value = true
  loadingHistory.value = true
  bindingHistory.value = []
  
  try {
    const token = localStorage.getItem('access_token')
    const response = await axios.get(
      `/api/inspections/equipment-history/${equipment.serial_number}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    )
    
    bindingHistory.value = response.data.history || []
  } catch (error) {
    console.error('获取绑定历史失败:', error)
    ElMessage.error('获取绑定历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 获取操作类型的颜色
const getActionColor = (action) => {
  const colorMap = {
    'bind': '#10b981',
    'unbind': '#ef4444',
    'rebind': '#f59e0b'
  }
  return colorMap[action] || '#909399'
}

// 获取操作类型的标签类型
const getActionTagType = (action) => {
  const typeMap = {
    'bind': 'success',
    'unbind': 'danger',
    'rebind': 'warning'
  }
  return typeMap[action] || 'info'
}

// 获取操作类型的文本
const getActionText = (action) => {
  const textMap = {
    'bind': '绑定设备',
    'unbind': '解绑设备',
    'rebind': '重新绑定'
  }
  return textMap[action] || action
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
  const seconds = String(date.getSeconds()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
</style>
