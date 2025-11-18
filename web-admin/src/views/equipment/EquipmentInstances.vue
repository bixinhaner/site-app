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
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              text
              @click="gotoLifecycle(row)"
            >
              设备跟踪
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 绑定历史弹窗（改为生命周期视图） -->
    <el-dialog
      v-model="historyDialogVisible"
      title="设备生命周期"
      width="70%"
      top="5vh"
    >
      <EquipmentLifecycleTimeline
        v-if="currentEquipment && currentEquipment.serial_number"
        :sn="currentEquipment.serial_number"
      />
      <el-empty
        v-else
        description="未找到设备序列号，无法查询生命周期"
      />
    </el-dialog>
  </div>
  
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { stockApi } from '../../api/stock'
import { ElMessage } from 'element-plus'
import { equipmentApi } from '../../api/equipment'
import { Document } from '@element-plus/icons-vue'
import EquipmentLifecycleTimeline from '@/components/equipment/EquipmentLifecycleTimeline.vue'

const router = useRouter()

const loading = ref(false)
const selectedEquipmentId = ref('')
const status = ref('')
const items = ref([])
const keyword = ref('')
const equipmentOptions = ref([])

// 绑定历史 / 生命周期弹窗相关
const historyDialogVisible = ref(false)
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

// 跳转到设备生命周期追踪页面，并自动带入 SN
const gotoLifecycle = (row) => {
  if (!row?.serial_number) {
    ElMessage.warning('该实例缺少 SN，无法追踪')
    return
  }
  router.push({
    name: 'EquipmentLifecycle',
    query: { sn: row.serial_number }
  })
}

// 显示设备生命周期（使用与生命周期页面一致的视图）
const showBindingHistory = (equipment) => {
  currentEquipment.value = equipment
  historyDialogVisible.value = true
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
</style>
